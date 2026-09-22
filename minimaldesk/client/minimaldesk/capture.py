from __future__ import annotations
import io
import os
import queue
import sys
import threading
from PIL import Image, ImageGrab


def capture_desktop(quality: int = 65) -> tuple[int, int, bytes]:
    if sys.platform == "linux":
        if os.environ.get("XDG_SESSION_TYPE") == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
            raise RuntimeError("Hosting requires an X11 desktop session, not Wayland")
        if not os.environ.get("DISPLAY"):
            raise RuntimeError("Run from a logged-in graphical X11 desktop")
        image = ImageGrab.grab(xdisplay=os.environ["DISPLAY"])
    elif sys.platform == "win32":
        image = ImageGrab.grab(all_screens=False, include_layered_windows=True)
    else:
        raise RuntimeError("Hosting is supported on Windows and Linux/X11 only")
    width, height = image.size
    if not 1 <= width <= 16384 or not 1 <= height <= 16384:
        raise RuntimeError("Unsupported desktop size")
    image = image.convert("RGB")
    image.thumbnail((1280, 720), Image.Resampling.BILINEAR)
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=max(35, min(85, quality)))
    jpeg = output.getvalue()
    if len(jpeg) > 1_048_000:
        raise RuntimeError("Frame exceeds the relay limit; lower JPEG quality")
    return width, height, jpeg


def decode_frame(jpeg: bytes) -> Image.Image:
    if len(jpeg) > 1_048_000:
        raise ValueError("Frame too large")
    image = Image.open(io.BytesIO(jpeg))
    if image.format != "JPEG" or not 1 <= image.width <= 1280 or not 1 <= image.height <= 720:
        raise ValueError("Invalid JPEG dimensions or format")
    image.load()
    return image.convert("RGB")


class CaptureWorker:
    def __init__(self, quality: int = 65):
        self.quality = quality
        self.result: queue.Queue[tuple[str, object]] = queue.Queue(1)
        self.requested, self.stopped = threading.Event(), threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True, name="minimaldesk-capture")
        self.thread.start()

    def request(self) -> None:
        self.requested.set()

    def stop(self) -> None:
        self.stopped.set()
        self.requested.set()

    def run(self) -> None:
        while not self.stopped.is_set():
            self.requested.wait()
            self.requested.clear()
            if self.stopped.is_set():
                return
            try:
                item = ("frame", capture_desktop(self.quality))
            except Exception as exc:
                item = ("error", str(exc))
            try:
                self.result.put_nowait(item)
            except queue.Full:
                pass  # Never accumulate old desktop images.
