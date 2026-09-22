# Initial validation report — 2026-09-22

## Executed locally

Environment: Linux x86_64, Python 3.13.5, PHP 8.4.23 CLI, Pillow 12.3.0, cryptography 46.0.4, websockets 16.0, pytest 9.0.2. Native desktop tests used an isolated Xvfb X11 display at 1280×800, with the system X11/XTEST libraries through ctypes.

Final command:

```bash
MINIDESK_TEST_X11=1 xvfb-run -a -s '-screen 0 1280x800x24' python -m pytest -q
```

**Result: 53 tests passed in 7.38 seconds.** PHP syntax validation also passed for all five PHP files. The standalone PHP framing test, included in the pytest run, performed 19 additional checks of frame lengths, masking, partial messages, and rejected protocol encodings.

An installable Python wheel was successfully built with:

```bash
python -m pip wheel --no-deps --no-build-isolation .
```

The wheel is a Python package, not a self-contained Windows/Linux executable. Dependencies and Tk/system libraries still need installation.

## What those tests establish

- Invitation parsing, authenticated encryption in both directions, altered keys/kinds/pair context/ciphertext rejection, replay and reordering rejection.
- URL/TLS restrictions and bounded keyboard/mouse event validation.
- Local consent enforcement even if a relay claims a session is active; encrypted greeting required before approval.
- View-only behavior, frame acknowledgments, control revocation, and peer timeout cleanup.
- Twenty clients accepted, the 21st rejected, and a freed slot reusable. Duplicate account connections and bad credentials rejected.
- Actual PHP WebSocket transport, fragmented authentication, ping/pong, unmasked-frame rejection, account revocation, and duplicate-server lock.
- Ten simultaneously paired connections transferred and authenticated **120 payloads of 80,000 bytes each**, with acknowledgments. This is a bounded loopback exercise using synthetic encrypted bytes, not a real-video or WAN benchmark.
- Real X11 screen capture and JPEG decoding; native key injection into a test Entry widget; mouse positioning and emergency-stop detection.
- Tk viewer construction/rendering and a complete host-GUI → PHP relay → viewer-session round trip: no capture before approval, live image receipt, remote typing, revocation, and stop cleanup.

## Not executed / not claimed

No physical Windows desktop tests, Windows native executable build, Linux PyInstaller executable build, code signing, installer execution, live Internet TLS deployment, Docker image build, systemd deployment, long-duration soak test, display-manager compatibility matrix, or independent security audit was completed in this initial local run. A build workflow and deployment examples are supplied; their presence does not constitute a successful run.

Test dependencies were already available in the execution environment. The source package's wheel build was validated without downloading dependencies. Installation from a clean machine and dependency resolution should be rechecked in CI or on the intended deployment machines.

## Acceptance checklist before wider use

Test both Windows→Linux and Linux→Windows with real users; different DPI settings and supported keyboard layouts; repeated approvals/denials; firewall/NAT/TLS; restart/disconnect while keys are held; and 10 real pairs under the expected bandwidth/latency. Verify the Stop and Revoke buttons remain reachable. Review protocol handling and dependency vulnerabilities before enabling untrusted accounts.

To rerun only non-desktop tests, run `python -m pytest -q` without `MINIDESK_TEST_X11=1`; three isolated-desktop tests will be skipped. PHP integration tests skip when PHP is absent. Never opt into X11 injection tests on a personal or production desktop: use `xvfb-run`.
