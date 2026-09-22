from __future__ import annotations
import json
import queue
import socket
import threading
import time
from websockets.sync.client import connect
from .validation import validate_url


class Transport:
    """Bounded network queues. The Tk thread never waits for network I/O."""
    def __init__(self, url: str, user: str, token: str):
        self.url, self.user, self.token = validate_url(url), user, token
        self.inbox: queue.Queue[tuple[str, object]] = queue.Queue(64)
        self.outbox: queue.Queue[dict] = queue.Queue(128)
        self.stopping, self.finished = threading.Event(), threading.Event()
        self.connection = None
        self.thread = threading.Thread(target=self.run, daemon=True, name="minimaldesk-network")

    def start(self) -> None:
        self.thread.start()

    def send(self, message: dict) -> None:
        if not self.stopping.is_set():
            try:
                self.outbox.put_nowait(message)
            except queue.Full:
                self.notify("error", "Network queue full; disconnected to release remote input")
                self.stop()

    def notify(self, kind: str, value: object) -> None:
        try:
            self.inbox.put_nowait((kind, value))
        except queue.Full:
            self.stop()

    def stop(self) -> None:
        self.stopping.set()
        connection = self.connection
        if connection is not None:
            try:
                connection.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    def run(self) -> None:
        try:
            with connect(self.url, compression=None, max_size=1_500_000, max_queue=16,
                         open_timeout=10, close_timeout=1, ping_interval=15, ping_timeout=10,
                         proxy=None) as ws:
                self.connection = ws
                if self.stopping.is_set():
                    return
                ws.send(json.dumps({"t": "auth", "v": 1, "user": self.user, "token": self.token}))
                self.token = ""  # Credentials are not written to a file or log.
                last_ping = time.monotonic()
                while not self.stopping.is_set():
                    for _ in range(32):
                        try:
                            message = self.outbox.get_nowait()
                        except queue.Empty:
                            break
                        ws.send(json.dumps(message, separators=(",", ":"), allow_nan=False))
                    if time.monotonic() - last_ping >= 10:
                        ws.send('{"t":"ping"}')
                        last_ping = time.monotonic()
                    try:
                        raw = ws.recv(timeout=0.02)
                    except TimeoutError:
                        continue
                    if not isinstance(raw, str):
                        raise ValueError("Server sent non-JSON data")
                    message = json.loads(raw)
                    if not isinstance(message, dict):
                        raise ValueError("Invalid server message")
                    self.notify("message", message)
        except Exception as exc:
            if not self.stopping.is_set():
                self.notify("error", f"Connection ended: {type(exc).__name__}: {exc}")
        finally:
            self.token = ""
            self.connection = None
            self.finished.set()
            self.notify("disconnected", "Disconnected")
