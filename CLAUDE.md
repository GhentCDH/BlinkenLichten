# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BlinkenLichten is a WLED-controlled addressable LED strip with a Python HTTP bridge. It features webhook-driven effects that validate Conventional Commits via GitHub push events.

**Architecture:**
- WLED device controls addressable LED strips via JSON API
- Python HTTP server bridges web requests to WLED JSON API
- GitHub webhooks trigger LED effects based on commit message validation

## Common Commands

### Python Server

Start the server (default: port 55156, WLED endpoint `http://wled.local`):
```bash
export WLED_ENDPOINT="http://wled.local"  # or IP address
uv run blinkenlichten.py
```

Custom port:
```bash
uv run blinkenlichten.py <port>
```

Set webhook secret:
```bash
export WEBHOOK_SECRET="your-shared-secret"
export WLED_ENDPOINT="http://wled.local"
uv run blinkenlichten.py
```

### Testing

Run webhook unit tests:
```bash
python3 blinkenlichten/test_webhook.py
```

## Code Architecture

### WLED API Wrapper (`blinkenlichten/wled.py`)

**Key components:**
- **WLEDController class**: Manages communication with WLED device via JSON API
- **HTTP requests**: Uses stdlib `urllib.request` (no external dependencies)
- **Effect mapping**: Translates high-level commands to WLED effect IDs
- **Error handling**: Custom `WLEDError` exception for network/API failures

**Configuration:**
- `WLED_ENDPOINT`: Environment variable or constructor parameter (default: `http://wled.local`)
- 5-second timeout on HTTP requests
- JSON payload structure: `POST /json/state`

**Methods:**
- `set_brightness(brightness)`: Set W channel (0-100 → 0-255 conversion)
- `set_effect_breathe(color_rgb, duration_ms)`: Trigger breathe effect (ID 2)
- `set_effect_rainbow(duration_ms)`: Trigger rainbow effect (ID 9)
- `turn_on(brightness)` / `turn_off()`: Power control

**Effect IDs:**
- Breathe: ID 2 (used for flashred/flashgreen)
- Rainbow: ID 9 (used for rainbow/comet/twinkle)

### Python Server (`blinkenlichten/blinkenlichten.py`)

**Key components:**
- **BrightnessStore class**: In-memory brightness persistence (default: 50%, resets on restart)
- **WLED integration**: Uses `wled.WLEDController` class variable shared across handlers
- **Effect restoration**: Background threads restore W channel brightness after effect duration
- **Commit parsing**: Regex-based validation of Conventional Commits format via `github_webhook.py`
- **Non-blocking responses**: Server responds to webhooks immediately, effects trigger asynchronously

**Webhook logic flow:**
1. Validate signature using `github_webhook.verify_github_signature()`
2. Parse JSON payload (supports both `application/json` and `application/x-www-form-urlencoded`)
3. Extract commits array from push event
4. Validate each commit's first line against pattern: `type(scope)?: description`
5. Trigger effect: all valid → `rainbow 5000`, any invalid → `flashred 5000`

**Allowed commit types:**
`feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `revert`, `merge`

**Effect restoration pattern:**
```python
def _trigger_effect_with_restoration(self, effect, duration_ms):
    # Trigger WLED effect immediately
    self.wled_controller.set_effect_*()

    # Schedule restoration in background thread (daemon, non-blocking)
    def restore_default():
        time.sleep(duration_ms / 1000.0)
        self.wled_controller.set_brightness(BrightnessStore.get())

    threading.Thread(target=restore_default, daemon=True).start()
```

## WLED API Integration

The server communicates with WLED devices via HTTP JSON API at `/json/state`.

**API endpoint structure:**
- Base URL: `{WLED_ENDPOINT}/json/state` (e.g., `http://wled.local/json/state`)
- Method: POST
- Content-Type: `application/json`
- Timeout: 5 seconds

**Key API payloads:**

Set brightness (W channel):
```json
{
  "on": true,
  "seg": [{
    "col": [[0, 0, 0, 191]]  // RGBW: W=191 (75% of 255)
  }]
}
```

Trigger breathe effect (red):
```json
{
  "on": true,
  "seg": [{
    "fx": 2,
    "col": [[255, 0, 0, 0]]  // RGB red, W=0
  }]
}
```

Trigger rainbow effect:
```json
{
  "on": true,
  "seg": [{
    "fx": 9  // Rainbow effect ID
  }]
}
```

Turn off:
```json
{
  "on": false
}
```

**Effect mapping:**
- `flashred` → Breathe effect (ID 2) with red (255, 0, 0)
- `flashgreen` → Breathe effect (ID 2) with green (0, 255, 0)
- `rainbow` → Rainbow effect (ID 9)
- `comet` → Rainbow effect (ID 9) - no exact WLED equivalent
- `twinkle` → Rainbow effect (ID 9) - no exact WLED equivalent

**Duration handling:**
- WLED effects run continuously (no built-in duration)
- Python server uses background threads to restore default state after duration
- Restoration sets W channel to saved brightness value

## HTTP Endpoints

| Method | Path | Query Params | Purpose |
|--------|------|--------------|---------|
| GET | `/` | - | Serve HTML control page |
| GET/POST | `/rainbow` | `duration=<ms>` | Trigger rainbow effect |
| POST | `/flashred` | `duration=<ms>` | Trigger breathe red effect |
| POST | `/flashgreen` | `duration=<ms>` | Trigger breathe green effect |
| POST | `/comet` | `duration=<ms>` | Trigger effect (mapped to rainbow) |
| POST | `/twinkle` | `duration=<ms>` | Trigger effect (mapped to rainbow) |
| GET | `/brightness` | - | Get current brightness from memory |
| POST | `/brightness` | `brightness=<0-100>` | Set W channel brightness |
| POST | `/on` | - | Turn on to saved brightness |
| POST | `/off` or `/shutdown` | - | Turn off |
| POST | `/webhook` | - | GitHub webhook (signature required) |
| GET | `/webhook` | `payload=<json>` | Test webhook (no signature) |

**Note:** GET `/brightness` returns value from in-memory `BrightnessStore`, not queried from WLED device.

## Important Development Notes

- **WLED endpoint** must be set via `WLED_ENDPOINT` environment variable (default: `http://wled.local`)
- **Webhook secret** must be set via environment variable `WEBHOOK_SECRET` for signature validation to work
- **Brightness storage** is in-memory only (resets to 50% on server restart) - no file or EEPROM persistence
- **Effect duration** is handled by background daemon threads that restore W channel brightness after the specified duration
- **No external dependencies** - uses stdlib `urllib.request` for HTTP requests (no `requests` library needed)
- **WLED controller** is shared across all request handlers via class variable `SerialHandler.wled_controller`
- **Error handling**: Network failures return HTTP 500 with clear error messages; server continues running even if WLED is unreachable
- **Effect mapping**: `comet` and `twinkle` are mapped to rainbow effect as WLED doesn't have exact equivalents
- **ESP32 firmware** (in `src/` directory) is no longer used but remains for reference - the system now uses WLED instead
