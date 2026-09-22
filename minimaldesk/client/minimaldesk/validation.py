from __future__ import annotations
import math
from urllib.parse import urlsplit

SPECIAL_KEYS = frozenset({
    "BackSpace", "Tab", "Return", "Escape", "Delete", "Insert", "Home", "End",
    "Prior", "Next", "Left", "Right", "Up", "Down", "Shift_L", "Shift_R",
    "Control_L", "Control_R", "Alt_L", "Alt_R", "Super_L", "Super_R", "Caps_Lock",
    "space", "minus", "equal", "bracketleft", "bracketright", "backslash",
    "semicolon", "apostrophe", "comma", "period", "slash", "grave",
    *(f"F{i}" for i in range(1, 13)),
})
SHIFTED = dict(zip(
    "exclam at numbersign dollar percent asciicircum ampersand asterisk parenleft parenright underscore plus braceleft braceright bar colon quotedbl less greater question asciitilde".split(),
    "1 2 3 4 5 6 7 8 9 0 minus equal bracketleft bracketright backslash semicolon apostrophe comma period slash grave".split(),
))


def normalize_key(key: str) -> str | None:
    key = SHIFTED.get(key, key)
    if len(key) == 1 and key.isascii() and key.isalnum():
        return key.lower()
    return key if key in SPECIAL_KEYS else None


def validate_input(m: object) -> dict:
    if not isinstance(m, dict):
        raise ValueError("Input must be an object")
    op = m.get("op")
    if op == "release_all":
        return {"op": op}
    if op == "move":
        x, y = m.get("x"), m.get("y")
        for value in (x, y):
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Coordinates must be finite and normalized")
        return {"op": op, "x": float(x), "y": float(y)}
    if op == "button" and isinstance(m.get("button"), str) and m.get("button") in {"left", "middle", "right"} and type(m.get("down")) is bool:
        return {"op": op, "button": m["button"], "down": m["down"]}
    if op == "scroll" and type(m.get("steps")) is int and -5 <= m["steps"] <= 5:
        return {"op": op, "steps": m["steps"]}
    if op == "key" and isinstance(m.get("key"), str) and normalize_key(m["key"]) == m["key"] and type(m.get("down")) is bool:
        return {"op": op, "key": m["key"], "down": m["down"]}
    raise ValueError("Unsupported input event")


def validate_url(url: str) -> str:
    p = urlsplit(url.strip())
    if not p.hostname or p.username or p.password or p.query or p.fragment or p.path != "/ws":
        raise ValueError("Use wss://your-server.example/ws; do not put credentials in the URL")
    if p.scheme != "wss" and not (p.scheme == "ws" and p.hostname in {"127.0.0.1", "::1", "localhost"}):
        raise ValueError("TLS (wss://) is required except for localhost development")
    _ = p.port  # Validate malformed port numbers too.
    return url.strip()
