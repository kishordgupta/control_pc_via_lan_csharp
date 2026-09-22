"""Versioned, direction-bound authenticated encryption; no server-held session key.

This is an experimental protocol, not an independently audited cryptosystem.
A new 256-bit invitation secret is generated for each one-use host session.
"""
from __future__ import annotations
import base64
import os
import re
import struct
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

HEX_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_PLAIN = 1_048_500
KINDS = frozenset({"hello", "accept", "frame", "input", "ack", "alive", "permission"})


def invitation(room: str, secret: bytes) -> str:
    if not HEX_ID.fullmatch(room) or len(secret) != 32:
        raise ValueError("Invalid invitation material")
    key = base64.urlsafe_b64encode(secret).decode().rstrip("=")
    return f"MD1.{room}.{key}"


def parse_invitation(text: str) -> tuple[str, bytes]:
    parts = text.strip().split(".")
    if len(parts) != 3 or parts[0] != "MD1" or not HEX_ID.fullmatch(parts[1]):
        raise ValueError("Paste the complete MD1 invitation from the host")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", parts[2]):
        raise ValueError("Invalid invitation key")
    secret = base64.b64decode(parts[2] + "=", altchars=b"-_", validate=True)
    if invitation(parts[1], secret) != text.strip():
        raise ValueError("Non-canonical invitation")
    return parts[1], secret


class SecureChannel:
    def __init__(self, secret: bytes, room: str, pair: str, role: str):
        if len(secret) != 32 or not HEX_ID.fullmatch(room) or not HEX_ID.fullmatch(pair) or role not in {"host", "viewer"}:
            raise ValueError("Invalid channel material")
        self.context = f"MinimalDesk/v1/{room}/{pair}/".encode()
        self.tx_direction = role
        self.rx_direction = "viewer" if role == "host" else "host"
        def key(direction: str) -> AESGCM:
            raw = HKDF(algorithm=hashes.SHA256(), length=32, salt=bytes.fromhex(room + pair),
                       info=b"MinimalDesk/v1/" + direction.encode()).derive(secret)
            return AESGCM(raw)
        self.tx = key(self.tx_direction)
        self.rx = key(self.rx_direction)
        self.sent = self.received = 0

    def _aad(self, direction: str, kind: str) -> bytes:
        if kind not in KINDS:
            raise ValueError("Unknown encrypted message kind")
        return self.context + direction.encode() + b"/" + kind.encode()

    def seal(self, kind: str, payload: bytes) -> str:
        if len(payload) > MAX_PLAIN or self.sent >= (1 << 64) - 1:
            raise ValueError("Payload or counter limit exceeded")
        aad = self._aad(self.tx_direction, kind)
        self.sent += 1
        nonce = os.urandom(12)
        data = self.tx.encrypt(nonce, struct.pack("!Q", self.sent) + payload, aad)
        return base64.b64encode(nonce + data).decode("ascii")

    def open(self, kind: str, encoded: str) -> bytes:
        if not isinstance(encoded, str) or not 48 <= len(encoded) <= 1_400_000:
            raise ValueError("Invalid encrypted message length")
        raw = base64.b64decode(encoded, validate=True)
        if len(raw) < 36:
            raise ValueError("Truncated encrypted message")
        try:
            plain = self.rx.decrypt(raw[:12], raw[12:], self._aad(self.rx_direction, kind))
        except InvalidTag as exc:
            raise ValueError("Invitation mismatch or altered message") from exc
        sequence = struct.unpack("!Q", plain[:8])[0]
        if sequence <= self.received:
            raise ValueError("Replayed or reordered message")
        self.received = sequence
        return plain[8:]
