# BlinkenLichten

> WLED-controlled LED strip with a Python HTTP bridge, webhook-driven effects, and a minimalist web UI.

BlinkenLichten lets you control an addressable LED strip using WLED's JSON API.

A Python webserver exposes HTTP endpoints (and a basic HTML page) and reacts to GitHub webhooks with some processing behind it:

* For a push message it checks the commit messages. If it follows the Conventional Commits specification you get a celebratory rainbow; if any commit breaks the rules the strip flashes red.
* For successfully finished workflows, the led strip reacts with green flashes.


## 1. Overview & architecture

- WLED device controls the LED strip via its JSON API.
- Host machine runs `blinkenlichten/blinkenlichten.py` bridging HTTP → WLED JSON API.
- GitHub sends webhook events & selects effect.


![Architecture diagram](./media/schema.svg)

---

## 2. WLED Configuration

BlinkenLichten communicates with a WLED device via its JSON API:

- **Endpoint**: Configure via `WLED_ENDPOINT` environment variable
- **Default**: `http://wled.local` (mDNS hostname)
- **API documentation**: https://kno.wled.ge/interfaces/json-api/

### Effect Mapping

The Python server maps HTTP commands to WLED effects:

| HTTP Command | WLED Effect | Details |
|--------------|-------------|---------|
| `flashred` | Breathe (ID 2) | Red color (255, 0, 0) |
| `flashgreen` | Breathe (ID 2) | Green color (0, 255, 0) |
| `rainbow` | Rainbow (ID 9) | Full rainbow effect |
| `brightness` | RGBW W channel | Warm white via W channel (0-100% → 0-255) |
| `comet` | Rainbow (ID 9) | Mapped to rainbow (no exact equivalent) |
| `twinkle` | Rainbow (ID 9) | Mapped to rainbow (no exact equivalent) |

**Effect Duration**: Effects run for the specified duration, then the server automatically restores the W channel to the saved brightness level.

**Brightness Storage**: Brightness is stored in-memory (default: 50%). This resets when the Python server restarts.

---

## 3. Python webserver

File: `blinkenlichten/blinkenlichten.py`

Start (defaults: port 55156, WLED endpoint `http://wled.local`):
```zsh
export WLED_ENDPOINT="http://wled.local"  # or use IP address
uv run blinkenlichten.py
```
Custom port:
```zsh
uv run blinkenlichten.py 8080
```

### Endpoints
| Method | Path | Query | Purpose |
|--------|------|-------|---------|
| GET | `/` | - | Serve simple HTML control page |
| GET/POST | `/rainbow` | `duration=<ms>` | Trigger rainbow effect |
| POST | `/flashred` | `duration=<ms>` | Trigger breathe red effect |
| POST | `/flashgreen` | `duration=<ms>` | Trigger breathe green effect |
| POST | `/comet` | `duration=<ms>` | Trigger effect (mapped to rainbow) |
| POST | `/twinkle` | `duration=<ms>` | Trigger effect (mapped to rainbow) |
| GET | `/brightness` | - | Get current brightness from memory |
| POST | `/brightness` | `brightness=<0-100>` | Set W channel brightness |
| POST | `/on` | - | Turn lights on (restore saved brightness) |
| POST | `/off` / `/shutdown` | - | Turn lights off |
| POST | `/webhook` | - | GitHub push webhook (signature + commit checks) |
| GET | `/webhook` | `payload=<json>` | Testing webhook logic (no signature) |

### Webhook logic
- Signature: `X-Hub-Signature-256 = 'sha256=' + HMAC_SHA256(raw_body, WEBHOOK_SECRET)`
- Payload formats supported:
    - `application/json` (raw body is JSON)
    - `application/x-www-form-urlencoded` (JSON under `payload` form field)
- Commit validation: each commit's first line must match Conventional Commits pattern: `type(scope)?: description` with allowed types: `feat, fix, chore, docs, style, refactor, perf, test, build, ci, revert`.
- Result mapping:
    - All commits valid → `rainbow 5000`
    - Any invalid → `flashred 5000`


---

## 4. Installation & running

### Requirements
- Python 3.10+
- WLED device on the network (with mDNS hostname `wled.local` or accessible IP address)
- No external Python dependencies (uses stdlib only)

### Using uv (recommended)
```zsh
# Set WLED endpoint
export WLED_ENDPOINT="http://wled.local"  # or "http://192.168.1.100"

# Optional: Set webhook secret for GitHub webhooks
export WEBHOOK_SECRET="your-github-webhook-secret"

# Start server
uv run blinkenlichten.py
```

Visit: http://localhost:55156/

### Configuration
- `WLED_ENDPOINT`: WLED device URL (default: `http://wled.local`)
- `WEBHOOK_SECRET`: GitHub webhook secret for signature validation (optional but recommended)
- Port: First command-line argument (default: 55156)

## 5. Container deployment

The production service runs as the rootless `ghentcdh` user on `dash`. A Podman
Quadlet publishes host port 80 to port 55156 in the container and starts the
service automatically after a reboot.

The tracked `blinkenlichten.container` is a template. Its environment variables
are defined directly in the Quadlet as required, but `WEBHOOK_SECRET` is empty so
that credentials are never committed to Git. Set the secret in the deployed copy
before starting the service.

### One-time server setup

These are the only commands that require `sudo`:

```sh
sudo apt-get update
sudo apt-get install -y podman uidmap passt

printf '%s\n' 'net.ipv4.ip_unprivileged_port_start=79' \
  | sudo tee /etc/sysctl.d/90-rootless-low-ports.conf >/dev/null
sudo sysctl --system
sudo loginctl enable-linger ghentcdh
```

The persistent sysctl permits rootless services to bind ports 79 and above.
User lingering starts the Quadlet at boot without requiring an interactive login.

### Build and transfer

Run these commands from the repository root. `--platform linux/amd64` is used for
both the build and archive export so the ARM image from a development machine is
never transferred to the x86 server.

```sh
docker buildx build \
  --platform linux/amd64 \
  --load \
  --tag localhost/blinkenlichten:0.2.0-amd64 \
  .

docker image inspect \
  localhost/blinkenlichten:0.2.0-amd64 \
  --format '{{.Architecture}}'

docker image save \
  --platform linux/amd64 \
  localhost/blinkenlichten:0.2.0-amd64 \
  | ssh ghentcdh@dash podman load
```

The architecture printed by `docker image inspect` must be `amd64` before the
image is transferred.

### Install the Quadlet

```sh
ssh ghentcdh@dash 'mkdir -p ~/.config/containers/systemd'

scp blinkenlichten.container \
  ghentcdh@dash:/home/ghentcdh/.config/containers/systemd/blinkenlichten.container

ssh -t ghentcdh@dash \
  'chmod 600 ~/.config/containers/systemd/blinkenlichten.container && sensible-editor ~/.config/containers/systemd/blinkenlichten.container'
```

In the remote editor, replace the empty value below with the GitHub webhook
secret shared with this service:

```ini
Environment="WEBHOOK_SECRET=replace-with-the-shared-secret"
```

Then reload and start the generated user service:

```sh
ssh ghentcdh@dash 'systemctl --user daemon-reload'
ssh ghentcdh@dash 'systemctl --user restart blinkenlichten.service'
```

Do not run `systemctl enable` for the generated service. The Quadlet's
`WantedBy=default.target` declaration and user lingering handle boot startup.

### Verify the deployment

```sh
ssh ghentcdh@dash 'systemctl --user status blinkenlichten.service'
ssh ghentcdh@dash 'podman ps --filter name=systemd-blinkenlichten'
ssh ghentcdh@dash 'podman image inspect localhost/blinkenlichten:0.2.0-amd64 --format "{{.Architecture}}"'
curl --noproxy '*' --fail http://gcdhdash/
```

The service is available at `http://gcdhdash/` and
`http://gcdhdash.ugent.be/`.

View service logs with:

```sh
ssh ghentcdh@dash 'journalctl --user -u blinkenlichten.service -f'
```

To locate an HTTP device such as WLED on the IoT subnet without installing
additional tools:

```sh
ssh ghentcdh@dash \
  'seq 1 254 | xargs -P 32 -I{} sh -c '\''nc -z -w 1 192.168.4.{} 80 && echo 192.168.4.{}:80 open'\'''
```

The current WLED device is reachable at `http://192.168.4.80` and is configured
as `WLED_ENDPOINT` directly in `blinkenlichten.container`.

### Deploy an update

Rebuild and transfer the same amd64-only tag, then restart the Quadlet. Do not
copy the Quadlet template again unless its configuration changed, because doing
so replaces the deployed webhook secret with the empty template value.

```sh
docker buildx build \
  --platform linux/amd64 \
  --load \
  --tag localhost/blinkenlichten:0.2.0-amd64 \
  .

docker image save \
  --platform linux/amd64 \
  localhost/blinkenlichten:0.2.0-amd64 \
  | ssh ghentcdh@dash podman load

ssh ghentcdh@dash 'systemctl --user restart blinkenlichten.service'
```

## License
MIT license

## Credits

Developed for GhentCDH.
