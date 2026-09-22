# Installation and operations

Commands assume the new project's directory, `minimaldesk/`, not the legacy repository root. Source installation is usable without a native executable build.

## 1. Desktop clients

### Windows

Target: Windows 10/11 x64, Python 3.11+ with Tcl/Tk. The Python installer must include the `py` launcher. This target is implemented but has not been exercised on a physical Windows machine in the initial validation environment.

From Command Prompt:

```bat
scripts\install-windows.cmd
scripts\run-windows.cmd
```

Equivalent manual installation:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install --no-deps -e .
.venv\Scripts\python.exe -m minimaldesk
```

The host shares its primary display. Run both normal desktop programs without elevation. UAC prompts, the sign-in/lock screen, and elevated applications are not supported. This application does not bypass Windows security boundaries.

### Linux

Target: a logged-in X11/Xorg desktop. Ubuntu/Debian example:

```bash
sudo apt-get update
sudo apt-get install -y python3-venv python3-tk libx11-6 libxtst6 libxcb1
bash scripts/install-linux.sh
.venv/bin/python -m minimaldesk
```

`echo "$XDG_SESSION_TYPE"` should report `x11` for hosting. Log out and select an Xorg/X11 session using your display manager when available. Do not merely change environment variables: that does not create a supported display server. Wayland hosting is deliberately refused; native Wayland capture/permission portals are not implemented. The Linux code captures the current X11 root display without monitor selection; a multi-monitor root may span screens.

Tk uses your desktop session. A terminal-only SSH login cannot host a real logged-in desktop. Do not expose the X server or disable X authorization to work around a display error.

### Settings and credentials

Enter the server, account name, and administrator-issued token in the app. Tokens are not saved to a configuration file, and the token field is cleared after login. Optional environment variables are `MINIDESK_URL`, `MINIDESK_USER`, and `MINIDESK_TOKEN`; prefer the masked GUI field on shared machines. Environment variables are not a secret vault. Never put account tokens or invitation secrets in command-line URLs, logs, issues, or commits.

## 2. Recommended server deployment: PHP + Caddy + Docker

Requirements: a Linux server, Docker Engine/Compose, a domain you control, and DNS pointing to this server. Open TCP 80 and 443 at the host/network firewall. No inbound desktop-client ports are required; clients make outbound connections to the relay.

```bash
cp .env.example .env
# Set MINIDESK_DOMAIN to a real domain, e.g. support.your-domain.org
docker compose build relay
docker compose run --rm relay php bin/users.php add host1
docker compose run --rm relay php bin/users.php add helper1
docker compose up -d
docker compose logs --tail=50 relay caddy
```

Caddy requests and renews a certificate for your configured domain. DNS and network reachability must be correct. Enter `wss://support.your-domain.org/ws` on both desktops. The supplied Caddy configuration does not publish the relay's health endpoint.

Each `add` command prints a random account token once. Save it in a password manager and distribute privately. There is no default account or password. `users.json` contains SHA-256 hashes of random 256-bit credentials, not plaintext tokens or human-chosen password hashes.

### Account management

```bash
docker compose exec relay php bin/users.php list
docker compose exec relay php bin/users.php add helper2
docker compose exec relay php bin/users.php revoke helper2
```

A removed or changed credential disconnects an existing session within approximately five seconds. To rotate, revoke and then add the same account name. An account cannot be used simultaneously by two clients.

### Operation and backup

```bash
docker compose ps
docker compose logs --tail=100 relay
# Stop without deleting account/certificate volumes:
docker compose down
# Apply reviewed code changes:
docker compose up -d --build
```

Back up the `relay_data` volume securely. Do not use `docker compose down -v` unless you intend to delete accounts and certificate state. Account data is private; do not serve its directory as a website. The relay keeps sessions in memory and drops them on restart. Clients do not reconnect silently.

Run exactly **one relay instance**. The file lock prevents duplicate processes using the same data directory; independent deployments with different directories do not share a global cap. `MINIDESK_MAX_CLIENTS` accepts 1–20 and rejects larger values. The application limit is not a commercial load or availability guarantee. Container image tags and dependency versions must be reviewed for updates before production use.

## 3. Direct PHP service, without Docker

The relay needs PHP **8.2+ CLI**, standard stream/JSON/hash functions, and no Composer dependencies. Optional `pcntl` enables graceful signal handling on Linux. PHP-FPM, `php -S`, and a shared-hosting document root are not relay deployment methods.

Copy the project to `/opt/minimaldesk`, create a non-login service account and private state directory:

```bash
sudo useradd --system --home-dir /var/lib/minimaldesk --shell /usr/sbin/nologin minimaldesk
sudo install -d -o minimaldesk -g minimaldesk -m 700 /var/lib/minimaldesk
sudo -u minimaldesk env MINIDESK_DATA=/var/lib/minimaldesk php /opt/minimaldesk/server/bin/users.php add host1
sudo -u minimaldesk env MINIDESK_DATA=/var/lib/minimaldesk php /opt/minimaldesk/server/bin/users.php add helper1
sudo cp /opt/minimaldesk/server/minimaldesk.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now minimaldesk
sudo journalctl -u minimaldesk -n 50
```

The supplied service binds only `127.0.0.1:8080`. Put a separately installed Caddy service in front, using this native-host Caddyfile (not the Docker hostname):

```caddyfile
support.your-domain.org {
    @websocket path /ws
    handle @websocket {
        reverse_proxy 127.0.0.1:8080
    }
    handle {
        respond "MinimalDesk relay. Use the desktop client." 200
    }
}
```

Validate and reload your Caddy configuration following its installation instructions. Keep port 8080 private. If the reverse proxy is on another machine, secure that internal connection too; the bundled deployment assumes a same-host/private backend.

The private health endpoint is `http://127.0.0.1:8080/healthz` and reports authenticated client count and configured limit. It does not require credentials, so do not expose it publicly without an access policy.

## 4. Local development only

```bash
php server/bin/users.php add host1
php server/bin/users.php add helper1
php server/relay.php
```

Connect two local app processes as different users to `ws://127.0.0.1:8080/ws`. Plain `ws://` is only permitted for literal loopback hosts. For two physical machines or Internet use, deploy WSS with a valid certificate; there is no certificate-verification bypass switch.

## 5. Native builds

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
python scripts/build.py
```

Build on Windows for Windows and Linux for Linux. The `dist/MinimalDesk` folder is the distributable; the build is not a signed installer. Linux binaries still depend on compatible system libraries, especially glibc/X11/XTEST. Build on an appropriate distribution and test on your oldest target. Windows code signing and installer packaging are not included. Do not ask users to disable endpoint protection for an unsigned build.

The repository's root `.github/workflows/minimaldesk.yml` recognizes either a standalone project or the nested `minimaldesk/` layout. It runs Linux tests, then creates Windows/Linux build artifacts. Check successful workflow results before describing those artifacts as built or tested.

## Troubleshooting

| Symptom | Check |
|---|---|
| `authentication failed` | Exact account name/token, correct relay; issue a new token after revocation. |
| `already connected` | Close the other app using that account, or create a separate account. |
| `server full` | Twenty authenticated clients are connected, including idle clients. Disconnect an unused client. |
| Invitation unavailable | Invitations expire after five minutes and are consumed by one attempt. Create a new one. |
| No host approval prompt | Helper must possess the full invitation secret; request expires in 30 seconds. |
| X11/display error | Run within a real authorized X11 session with XTEST; Wayland hosting is unsupported. |
| Black/protected Windows window | Protected/elevated/secure desktops may not capture or accept input. They are outside scope. |
| Slow or lagging display | Reduce FPS; check bandwidth and RTT. Frames are JPEG, not hardware-encoded video. |
| Certificate error | Fix DNS/certificate chain/time; never disable verification. |
| Lost key or mouse focus | Use viewer Release button/Escape, host Revoke control, or stop and restart the session. |
| Unexpected disconnect | Inspect relay logs, account revocation, one-hour session limit, peer timeout, or queue/rate limits. |
