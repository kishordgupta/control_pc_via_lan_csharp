"""Small, explicit input backends; no keyboard logging or background service."""
from __future__ import annotations
import ctypes
import os
import sys
from .validation import validate_input


def enable_dpi_awareness() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        except (AttributeError, OSError):
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except (AttributeError, OSError):
                pass


class X11Backend:
    """X11/XTEST through the system libraries; no additional Python input package."""
    def __init__(self):
        if os.environ.get("XDG_SESSION_TYPE") == "wayland" or os.environ.get("WAYLAND_DISPLAY"):
            raise RuntimeError("Hosting requires X11. Log out and choose an Xorg/X11 desktop session.")
        if not os.environ.get("DISPLAY"):
            raise RuntimeError("No X11 display; start MinimalDesk inside your graphical desktop")
        try:
            self.x = ctypes.CDLL("libX11.so.6")
            self.xt = ctypes.CDLL("libXtst.so.6")
        except OSError as exc:
            raise RuntimeError("Install the system libX11 and libXtst libraries") from exc
        P, I, U, L = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint, ctypes.c_ulong
        signatures = {
            "XOpenDisplay": ([ctypes.c_char_p], P), "XCloseDisplay": ([P], I),
            "XDefaultScreen": ([P], I), "XDisplayWidth": ([P,I], I), "XDisplayHeight": ([P,I], I),
            "XStringToKeysym": ([ctypes.c_char_p], L), "XKeysymToKeycode": ([P,L], ctypes.c_ubyte),
            "XQueryKeymap": ([P,ctypes.POINTER(ctypes.c_ubyte)], I), "XSync": ([P,I], I),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(self.x, name); fn.argtypes, fn.restype = args, result
        for name, args in {
            "XTestQueryExtension": [P] + [ctypes.POINTER(I)]*4,
            "XTestFakeKeyEvent": [P,U,I,L], "XTestFakeButtonEvent": [P,U,I,L],
            "XTestFakeMotionEvent": [P,I,I,I,L],
        }.items():
            fn = getattr(self.xt, name); fn.argtypes, fn.restype = args, I
        self.display = self.x.XOpenDisplay(None)
        if not self.display:
            raise RuntimeError("Cannot open the current X11 display")
        values = [I() for _ in range(4)]
        if not self.xt.XTestQueryExtension(self.display, *[ctypes.byref(v) for v in values]):
            self.close(); raise RuntimeError("This X11 server does not provide XTEST input support")
        self.screen = self.x.XDefaultScreen(self.display)
        self.width = self.x.XDisplayWidth(self.display, self.screen)
        self.height = self.x.XDisplayHeight(self.display, self.screen)

    def keycode(self, key: str) -> int:
        code = self.x.XKeysymToKeycode(self.display, self.x.XStringToKeysym(key.encode("ascii")))
        if not code:
            raise ValueError(f"Key is unavailable in the host keyboard layout: {key}")
        return code

    def key(self, key: str, down: bool) -> None:
        self.xt.XTestFakeKeyEvent(self.display, self.keycode(key), int(down), 0)
        self.x.XSync(self.display, 0)

    def move(self, x: float, y: float) -> None:
        self.xt.XTestFakeMotionEvent(self.display, self.screen,
                                    round(x*(self.width-1)), round(y*(self.height-1)), 0)
        self.x.XSync(self.display, 0)

    def button(self, button: str, down: bool) -> None:
        self.xt.XTestFakeButtonEvent(self.display, {"left":1,"middle":2,"right":3}[button], int(down), 0)
        self.x.XSync(self.display, 0)

    def scroll(self, steps: int) -> None:
        for _ in range(abs(steps)):
            code = 4 if steps > 0 else 5
            self.xt.XTestFakeButtonEvent(self.display, code, 1, 0)
            self.xt.XTestFakeButtonEvent(self.display, code, 0, 0)
        self.x.XSync(self.display, 0)

    def stop_requested(self) -> bool:
        keys = (ctypes.c_ubyte * 32)()
        self.x.XQueryKeymap(self.display, keys)
        def down(name: str) -> bool:
            code = self.keycode(name)
            return bool(keys[code // 8] & (1 << (code % 8)))
        return (down("Control_L") or down("Control_R")) and (down("Alt_L") or down("Alt_R")) and down("F12")

    def close(self) -> None:
        if self.display:
            self.x.XCloseDisplay(self.display)
            self.display = None


class WindowsBackend:
    def __init__(self):
        from ctypes import wintypes as w
        class Mouse(ctypes.Structure):
            _fields_ = [("dx", w.LONG), ("dy", w.LONG), ("mouseData", w.DWORD),
                        ("dwFlags", w.DWORD), ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
        class Keyboard(ctypes.Structure):
            _fields_ = [("wVk", w.WORD), ("wScan", w.WORD), ("dwFlags", w.DWORD),
                        ("time", w.DWORD), ("dwExtraInfo", ctypes.c_size_t)]
        class Payload(ctypes.Union):
            _fields_ = [("mi", Mouse), ("ki", Keyboard)]
        class Input(ctypes.Structure):
            _fields_ = [("type", w.DWORD), ("payload", Payload)]
        self.Mouse, self.Keyboard, self.Payload, self.Input = Mouse, Keyboard, Payload, Input
        self.api = ctypes.WinDLL("user32", use_last_error=True)
        self.api.SendInput.argtypes = [w.UINT, ctypes.POINTER(Input), ctypes.c_int]
        self.api.SendInput.restype = w.UINT
        self.api.GetAsyncKeyState.argtypes = [ctypes.c_int]
        self.api.GetAsyncKeyState.restype = w.SHORT
        self.width, self.height = self.api.GetSystemMetrics(0), self.api.GetSystemMetrics(1)
        self.codes = {"BackSpace": 0x08, "Tab": 0x09, "Return": 0x0D, "Escape": 0x1B,
            "space": 0x20, "Prior": 0x21, "Next": 0x22, "End": 0x23, "Home": 0x24,
            "Left": 0x25, "Up": 0x26, "Right": 0x27, "Down": 0x28, "Insert": 0x2D,
            "Delete": 0x2E, "Shift_L": 0xA0, "Shift_R": 0xA1, "Control_L": 0xA2,
            "Control_R": 0xA3, "Alt_L": 0xA4, "Alt_R": 0xA5, "Super_L": 0x5B,
            "Super_R": 0x5C, "Caps_Lock": 0x14, "semicolon": 0xBA, "equal": 0xBB,
            "comma": 0xBC, "minus": 0xBD, "period": 0xBE, "slash": 0xBF, "grave": 0xC0,
            "bracketleft": 0xDB, "backslash": 0xDC, "bracketright": 0xDD, "apostrophe": 0xDE}
        self.codes.update({f"F{i}": 0x6F + i for i in range(1, 13)})
        self.extended = {"Prior", "Next", "End", "Home", "Left", "Up", "Right", "Down",
                         "Insert", "Delete", "Control_R", "Alt_R", "Super_L", "Super_R"}

    def send(self, event) -> None:
        if self.api.SendInput(1, ctypes.byref(event), ctypes.sizeof(self.Input)) != 1:
            raise OSError("Windows blocked input; elevated apps and secure desktops are not supported")

    def key(self, key: str, down: bool) -> None:
        vk = ord(key.upper()) if len(key) == 1 and key.isascii() and key.isalnum() else self.codes[key]
        flags = (0 if down else 2) | (1 if key in self.extended else 0)
        self.send(self.Input(type=1, payload=self.Payload(ki=self.Keyboard(wVk=vk, dwFlags=flags))))

    def mouse(self, flags: int, x: int = 0, y: int = 0, data: int = 0) -> None:
        self.send(self.Input(type=0, payload=self.Payload(mi=self.Mouse(dx=x, dy=y, mouseData=data & 0xFFFFFFFF, dwFlags=flags))))

    def move(self, x: float, y: float) -> None:
        self.mouse(0x8001, round(x * 65535), round(y * 65535))

    def button(self, button: str, down: bool) -> None:
        flags = {"left": (0x2, 0x4), "right": (0x8, 0x10), "middle": (0x20, 0x40)}
        self.mouse(flags[button][0 if down else 1])

    def scroll(self, steps: int) -> None:
        self.mouse(0x0800, data=120 * steps)

    def stop_requested(self) -> bool:
        return all(self.api.GetAsyncKeyState(key) & 0x8000 for key in (0x11, 0x12, 0x7B))

    def close(self) -> None:
        pass


class InputController:
    def __init__(self, backend=None):
        if backend is None:
            if sys.platform == "win32":
                backend = WindowsBackend()
            elif sys.platform == "linux":
                backend = X11Backend()
            else:
                raise RuntimeError("Unsupported host operating system")
        self.backend = backend
        self.enabled = False
        self.keys: set[str] = set()
        self.buttons: set[str] = set()

    def enable(self, enabled: bool) -> None:
        self.enabled = enabled
        if not enabled:
            self.release_all()

    def release_all(self) -> None:
        for key in tuple(self.keys):
            try:
                self.backend.key(key, False)
            except Exception:
                pass
        for button in tuple(self.buttons):
            try:
                self.backend.button(button, False)
            except Exception:
                pass
        self.keys.clear()
        self.buttons.clear()

    def handle(self, message: dict) -> None:
        if not self.enabled:
            return
        m = validate_input(message)
        op = m["op"]
        if op == "release_all":
            self.release_all()
        elif op == "move":
            self.backend.move(m["x"], m["y"])
        elif op == "scroll":
            self.backend.scroll(m["steps"])
        elif op == "key":
            if m["down"] or m["key"] in self.keys:
                self.backend.key(m["key"], m["down"])
            if m["down"]:
                self.keys.add(m["key"])
            else:
                self.keys.discard(m["key"])
        elif op == "button":
            if m["down"] or m["button"] in self.buttons:
                self.backend.button(m["button"], m["down"])
            if m["down"]:
                self.buttons.add(m["button"])
            else:
                self.buttons.discard(m["button"])

    def close(self) -> None:
        self.enable(False)
        self.backend.close()
