# MinimalDesk 0.1

A small **attended remote desktop** application for **Windows and Linux/X11**, with a **PHP relay** and a hard limit of **20 connected client accounts**. This is an independent MVP, not AnyDesk software or a production-grade replacement.

**Status:** source implementation with automated unit, live PHP relay, and isolated Linux/X11 desktop tests. Windows backend and native build automation are supplied; Windows desktop acceptance testing, signed installers, public TLS deployment, and WAN performance certification remain outstanding. See [test report](docs/TEST_REPORT.md).

## What it does

- Share a desktop with one viewer after explicit local host approval.
- View-only by default; optionally approve mouse movement, clicks, scrolling, and basic keyboard input.
- One-use, five-minute invitations; a separate server account/token for each endpoint.
- Application-layer AES-256-GCM encryption for screen images and control messages, plus WSS/TLS in deployment.
- Visible sharing indicator, Stop button, control revocation, and host emergency stop `Ctrl+Alt+F12`.
- Adjustable 1–10 FPS (default 5), JPEG frames scaled to fit 1280×720, and frame acknowledgments to avoid a backlog.
- Self-hosted PHP 8.2+ CLI relay; no database or Composer packages.

**20 clients means at most 10 host/viewer pairs.** Idle authenticated clients also occupy slots. The 21st account is refused. An account can have one live connection; a client can participate in one session. This is not 20 simultaneous two-person sessions. Administrators may provision more accounts, but the simultaneous limit remains 20.

Not included: unattended access, hidden/background operation, file transfer, clipboard synchronization, audio, recording, multi-monitor selection, administrator elevation, or a remote shell. Linux hosting requires X11, not Wayland. Use only on devices you own or are authorized to support.

## Get the code

This MVP is isolated in the `minimaldesk/` folder on branch `minimaldesk-php-mvp` of the existing repository; the legacy C# application is untouched.

```bash
git clone --branch minimaldesk-php-mvp --single-branch https://github.com/kishordgupta/control_pc_via_lan_csharp.git
cd control_pc_via_lan_csharp/minimaldesk
```

For the standalone source ZIP, extract it and open its `minimaldesk` directory instead. All commands below start at this project directory.

## Install the client

Install Python **3.11 or newer** with Tk support. Python 3.12 is the CI build target.

### Windows

Use the official Python installer with Tcl/Tk and the Python launcher enabled. In Command Prompt:

```bat
scripts\install-windows.cmd
scripts\run-windows.cmd
```

For visible diagnostics: `.venv\Scripts\python.exe -m minimaldesk`.

### Linux (Ubuntu/Debian, X11 desktop)

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-tk libx11-6 libxtst6 libxcb1
bash scripts/install-linux.sh
.venv/bin/python -m minimaldesk
```

Other distributions need equivalent Python/Tk, X11, XTEST, and XCB packages. Do not run the desktop app as root. See [installation](docs/INSTALLATION.md) for details.

## Deploy the PHP relay

On a Linux server with Docker Engine and the Compose plugin installed, point a domain at that server and allow inbound TCP 80/443:

```bash
cp .env.example .env
# Edit .env: MINIDESK_DOMAIN=your.actual.domain
docker compose build relay
docker compose run --rm relay php bin/users.php add host1
docker compose run --rm relay php bin/users.php add helper1
docker compose up -d
```

Save each printed token privately; it is shown only once. Give each person their own username and token. Both clients use `wss://your.actual.domain/ws`.

The Compose deployment puts Caddy in front of the PHP process for HTTPS/WSS. Port 8080 is deliberately **not published**. Keep one relay instance; do not scale it horizontally. The PHP process is a persistent CLI service, **not a PHP page** for shared hosting or PHP-FPM.

For direct PHP/systemd installation or a localhost-only development test, see [installation](docs/INSTALLATION.md).

## Start a session

1. Both people connect to the same relay using **different accounts**.
2. The host selects **Share this computer** and privately sends the complete invitation to the helper.
3. The helper pastes the invitation, optionally checks **Request keyboard and mouse control**, and selects **Join invitation**.
4. The host checks the incoming account name and chooses **Allow view only**, **Allow keyboard + mouse**, or **Deny**. Nothing is captured before approval.
5. Either person can stop. The host can also revoke control without ending screen sharing.

The invitation works for one attempt only. A denied, expired, stopped, or disconnected session requires a new invitation and approval. See the [usage guide](docs/USAGE.md).

## Build portable native applications

Run on each target operating system:

```text
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
python scripts/build.py
```

Output is the complete `dist/MinimalDesk/` directory: `MinimalDesk.exe` on Windows or `MinimalDesk` on Linux. Do not copy just the executable. Builds are unsigned and require target-machine testing. PyInstaller is not a Windows/Linux cross-compiler.

The included GitHub Actions workflow tests on Linux and then builds separate Windows and Linux artifacts. A workflow file is not evidence that a build succeeded; check the Actions result before distributing anything.

## Tests and documentation

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
# On an isolated Linux virtual display, also test real capture and input:
MINIDESK_TEST_X11=1 xvfb-run -a -s '-screen 0 1280x800x24' python -m pytest -q
```

[Installation](docs/INSTALLATION.md) · [Usage](docs/USAGE.md) · [Architecture and protocol](docs/ARCHITECTURE.md) · [Security model](SECURITY.md) · [Test report](docs/TEST_REPORT.md)

License: MIT for this new project. Dependencies retain their respective licenses. Review and test this MVP before exposing it to untrusted users or using it with sensitive information.
