# Architecture and protocol

```text
Host desktop (Python/Tk)                       Helper desktop (Python/Tk)
  local consent + visible stop                   viewer + input focus
  Pillow capture -> bounded JPEG                JPEG decode -> scaled canvas
  optional native input backend                 explicit input events only
              |                                         |
              +---- WSS/TLS ---- Caddy ---- WSS/TLS -----+
                                   |
                         private WebSocket connection
                                   |
                     single-process PHP CLI relay
                     accounts + 20-slot admission
                     one host + one viewer per room
```

The diagram groups the two public TLS connections; each client has its own connection through Caddy to PHP. Screen/input payloads have application-layer encryption across that relay. The backend TCP link is private, not itself TLS in the bundled same-host deployment.

## Desktop implementation

`gui.py` owns Tk widgets and pumps bounded network/capture queues. `session.py` is a UI-independent consent state machine. `transport.py` uses a dedicated thread with the websockets synchronous client. `capture.py` produces JPEG frames only after host approval; one frame is in flight until the viewer acknowledges it. This sacrifices frame rate for bounded memory/latency under backpressure.

`input_control.py` uses Windows `SendInput` through ctypes or Linux's system `libX11`/`libXtst`. It starts disabled, validates events, tracks app-held keys/buttons, and releases them on revoke/normal stop. The global emergency-stop check reads only the current shortcut key state; there is no keystroke history recorder.

## Relay implementation

`Wire.php` implements bounded RFC 6455 frame parsing: masked client frames, partial frames, continuation frames, control frames, and length validation. `Relay.php` runs a nonblocking `stream_select` event loop. No database, HTTP session cookies, PHP-FPM workers, Composer packages, STUN, or TURN are used. All media travels through the relay; there is no direct peer-to-peer mode.

Admission is single-process and atomic with respect to this event loop. A file lock guards the data directory against a second relay process. Raw pending TCP sockets have a separate 48-socket bound; only authenticated clients count against the 20-user limit. Raw connection/message/byte limits reduce abuse but do not constitute a DDoS defense.

## Message sequence

1. `auth {v:1,user,token}` -> `ready`. Token travels inside TLS, not a URL.
2. Host sends `host` -> `hosted {room,expires_in}`. Client creates the invitation secret locally; it is never included in this request.
3. Viewer sends `join {room}` -> both receive `paired {pair,peer}`.
4. Viewer sends encrypted `hello {v:1,requested_control}`. Host checks its authentication tag before showing the approval prompt.
5. Local host approval sends `approve {control}`. The relay reports `active`, but the host client will not start from that message unless it already recorded local approval.
6. Host sends encrypted `accept`. Viewer ignores bare relay `active` and waits for that authenticated acceptance.
7. Host sends encrypted `frame`; viewer sends encrypted `ack`. Optional encrypted `input` flows in the reverse direction. Both send encrypted `alive` heartbeats.
8. Host `revoke` restricts the server route and also sends authenticated `permission {control:false}`. `stop`, expiry, revocation, or disconnect ends the room.

Control messages are small JSON objects. A frame plaintext is 12 bytes of network-order unsigned integers `(frame_id, original_width, original_height)` followed by JPEG bytes. Encrypted messages carry `kind` and base64 `body`; the kind is authenticated as associated data. See `crypto.py` and `SECURITY.md` for the cryptographic format.

Invitations are `MD1.<32-hex room id>.<43-character URL-safe secret>`. They are deliberately longer than a numeric PIN to avoid relying on a guessable password. There is no PAKE or user-chosen invitation password in this MVP.

## Bandwidth planning

For an illustrative 100 KiB JPEG at 5 FPS in 10 sessions, image bytes alone are about 40.96 Mbit/s incoming and the same outgoing at the relay. Base64 adds roughly one third, before JSON/TLS/TCP overhead, so budget more than 55 Mbit/s in each direction for that example. Actual JPEG sizes vary with desktop content. This is arithmetic, not a measured WAN result. Reduce FPS/resolution or introduce a video codec in a future version if necessary.

## Primary implementation references

- RFC 6455: https://datatracker.ietf.org/doc/html/rfc6455
- Pillow ImageGrab: https://pillow.readthedocs.io/en/stable/reference/ImageGrab.html
- websockets synchronous client: https://websockets.readthedocs.io/en/stable/reference/sync/client.html
- Windows SendInput/UIPI: https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-sendinput
- XTEST functions: https://www.x.org/releases/X11R7.5/doc/man/man3/XTestFakeKeyEvent.3.html
- AES-GCM API: https://cryptography.io/en/latest/hazmat/primitives/aead/
- Caddy WebSocket proxy: https://caddyserver.com/docs/caddyfile/directives/reverse_proxy
- PyInstaller native builds: https://pyinstaller.org/en/stable/
