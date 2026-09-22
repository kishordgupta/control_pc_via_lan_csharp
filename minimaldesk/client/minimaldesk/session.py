"""UI-independent consent and session state machine. All methods use the UI thread."""
from __future__ import annotations
import json
import os
import re
import struct
import time
from collections.abc import Callable
from .crypto import HEX_ID, SecureChannel, invitation, parse_invitation
from .validation import validate_input


def encode_json(data: dict) -> bytes:
    return json.dumps(data, separators=(",", ":"), allow_nan=False).encode()


def decode_json(raw: bytes) -> dict:
    if len(raw) > 2048:
        raise ValueError("Control message too large")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("Object required")
    return data


class Session:
    def __init__(self, send: Callable[[dict], None], emit: Callable[[str, object], None]):
        self.send, self.emit = send, emit
        self.connected = False
        self.user = ""
        self.reset()

    def reset(self) -> None:
        self.state = "idle"
        self.awaiting_stop = False
        self.role = self.room = self.pair = self.peer = ""
        self.secret: bytes | None = None
        self.channel: SecureChannel | None = None
        self.approved = self.control = self.verified = False
        self.requested = False
        self.waiting_frame: tuple[int, float] | None = None
        self.frame_number = 0
        self.last_peer = self.last_alive = time.monotonic()
        self.started = time.monotonic()

    def begin_host(self) -> None:
        if not self.connected or self.state != "idle" or self.awaiting_stop:
            raise ValueError("Connect first; only one session at a time")
        self.reset()
        self.role, self.state = "host", "creating"
        self.secret = os.urandom(32)
        self.send({"t": "host"})

    def begin_join(self, invite: str, request_control: bool) -> None:
        if not self.connected or self.state != "idle" or self.awaiting_stop:
            raise ValueError("Connect first; only one session at a time")
        room, secret = parse_invitation(invite)
        self.reset()
        self.role, self.state = "viewer", "joining"
        self.room, self.secret, self.requested = room, secret, request_control
        self.send({"t": "join", "room": room})

    def approve(self, control: bool = False) -> None:
        if self.role != "host" or self.state != "pending" or not self.verified:
            raise ValueError("No verified request to approve")
        self.control = bool(control and self.requested)
        self.approved, self.state = True, "approving"
        self.send({"t": "approve", "control": self.control})

    def stop(self, reason: str = "Session stopped") -> None:
        pending = self.awaiting_stop or self.state != "idle"
        if self.state != "idle" and self.connected:
            self.send({"t": "stop"})
        self.reset()
        self.awaiting_stop = bool(pending and self.connected)
        self.emit("ended", reason)

    def disconnect(self, reason: str = "Disconnected") -> None:
        self.connected = False
        self.reset()
        self.emit("disconnected", reason)

    def revoke(self) -> None:
        if self.role == "host" and self.state == "active":
            self.control = False
            self.emit("revoked", None)
            self.sealed("permission", encode_json({"control": False}))
            self.send({"t": "revoke"})

    def sealed(self, kind: str, payload: bytes) -> None:
        if self.channel is None:
            raise ValueError("No encrypted channel")
        self.send({"t": "relay", "kind": kind, "body": self.channel.seal(kind, payload)})

    def handle(self, message: dict) -> None:
        try:
            self._handle(message)
        except (ValueError, TypeError, KeyError, struct.error, OverflowError) as exc:
            self.stop("Invalid or unauthenticated peer message")
            self.emit("error", f"Session closed: {exc}")

    def _handle(self, m: dict) -> None:
        t = m.get("t")
        if t == "ready":
            if m.get("v") != 1:
                raise ValueError("Unsupported server version")
            self.connected = True
            self.user = str(m["user"])
            self.emit("ready", self.user)
        elif t == "hosted" and self.role == "host" and self.state == "creating":
            if not HEX_ID.fullmatch(m["room"]):
                raise ValueError("Invalid room ID")
            self.room, self.state = m["room"], "waiting"
            self.emit("invitation", invitation(self.room, self.secret))
        elif t == "paired" and self.state in {"waiting", "joining"}:
            if not HEX_ID.fullmatch(m["pair"]) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", m["peer"]):
                raise ValueError("Invalid peer metadata")
            self.pair, self.peer = m["pair"], m["peer"]
            self.channel = SecureChannel(self.secret, self.room, self.pair, self.role)
            self.state = "pending"
            self.started = time.monotonic()
            if self.role == "viewer":
                self.sealed("hello", encode_json({"v": 1, "requested_control": self.requested}))
            self.emit("pending", self.peer)
        elif t == "active":
            # A relay message alone can NEVER grant host-side access.
            if self.role == "host" and self.state == "approving" and self.approved:
                self.state = "active"
                self.last_peer = self.last_alive = time.monotonic()
                self.sealed("accept", encode_json({"control": self.control}))
                self.emit("started", {"role": self.role, "peer": self.peer, "control": self.control})
        elif t == "control_revoked":
            self.control = False
            self.emit("revoked", None)
        elif t == "relay" and self.channel is not None and self.state != "idle":
            if m.get("pair") != self.pair:
                raise ValueError("Wrong session generation")
            kind = m["kind"]
            raw = self.channel.open(kind, m["body"])
            self.last_peer = time.monotonic()
            if kind == "hello" and self.role == "host" and self.state == "pending" and not self.verified:
                hello = decode_json(raw)
                if hello.get("v") != 1 or type(hello.get("requested_control")) is not bool:
                    raise ValueError("Invalid peer greeting")
                self.verified, self.requested = True, hello["requested_control"]
                self.emit("request", {"peer": self.peer, "control": self.requested})
            elif kind == "accept" and self.role == "viewer" and self.state == "pending":
                accepted = decode_json(raw)
                if type(accepted.get("control")) is not bool:
                    raise ValueError("Invalid permission")
                self.control, self.state = bool(accepted["control"] and self.requested), "active"
                self.last_alive = time.monotonic()
                self.emit("started", {"role": self.role, "peer": self.peer, "control": self.control})
            elif kind == "frame" and self.role == "viewer" and self.state == "active":
                if len(raw) < 13:
                    raise ValueError("Truncated frame")
                number, width, height = struct.unpack("!III", raw[:12])
                if not 1 <= width <= 16384 or not 1 <= height <= 16384:
                    raise ValueError("Invalid desktop dimensions")
                self.emit("frame", (number, width, height, raw[12:]))
            elif kind == "input" and self.role == "host" and self.state == "active" and self.approved and self.control:
                self.emit("input", validate_input(decode_json(raw)))
            elif kind == "ack" and self.role == "host" and self.state == "active":
                number = decode_json(raw).get("id")
                if self.waiting_frame and type(number) is int and number == self.waiting_frame[0]:
                    self.waiting_frame = None
            elif kind == "permission" and self.role == "viewer" and self.state == "active":
                if decode_json(raw).get("control") is not False:
                    raise ValueError("Remote permission escalation rejected")
                self.control = False
                self.emit("revoked", None)
            elif kind != "alive":
                # Ignore late input after a local revoke; never execute it.
                if kind != "input":
                    raise ValueError("Unexpected encrypted message")
        elif t == "ended":
            self.reset()
            self.emit("ended", str(m.get("reason", "Session ended")))
        elif t == "error":
            code = str(m.get("code", "server_error"))
            if code == "no_session":
                self.awaiting_stop = False
            if self.state in {"creating", "joining"}:
                self.reset()
                self.emit("ended", code)
            self.emit("error", code)

    def send_frame(self, width: int, height: int, jpeg: bytes) -> bool:
        if self.role != "host" or self.state != "active" or not self.approved or self.waiting_frame:
            return False
        self.frame_number += 1
        self.sealed("frame", struct.pack("!III", self.frame_number, width, height) + jpeg)
        self.waiting_frame = (self.frame_number, time.monotonic())
        return True

    def ack_frame(self, number: int) -> None:
        if self.role == "viewer" and self.state == "active":
            self.sealed("ack", encode_json({"id": number}))

    def send_input(self, event: dict) -> None:
        if self.role == "viewer" and self.state == "active" and self.control:
            self.sealed("input", encode_json(validate_input(event)))

    def tick(self) -> None:
        now = time.monotonic()
        if self.state in {"pending", "approving"} and now - self.started > 31:
            self.stop("Approval timed out")
        if self.state == "active":
            if now - self.last_peer > 15 or (self.waiting_frame and now - self.waiting_frame[1] > 10):
                self.stop("Peer stopped responding")
            elif now - self.last_alive >= 3:
                self.sealed("alive", b"1")
                self.last_alive = now
