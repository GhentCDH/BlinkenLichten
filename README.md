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

## License
MIT license

## Credits

Developed for GhentCDH.

