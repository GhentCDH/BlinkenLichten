# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BlinkenLichten is an ESP32-controlled addressable LED strip with a Python HTTP bridge. It features webhook-driven effects that validate Conventional Commits via GitHub push events.

**Architecture:**
- ESP32 firmware (PlatformIO/C++) controls addressable LED strips via serial commands
- Python HTTP server bridges web requests to serial commands
- GitHub webhooks trigger LED effects based on commit message validation

## Common Commands

### ESP32 Firmware (PlatformIO)

Build and upload to ESP32:
```bash
pio run -t upload
```

Monitor serial output:
```bash
pio device monitor -b 115200
```

### Python Server

Start the server (default: port 55155, device `/dev/cu.usbserial-0001`):
```bash
uv run blinkenlichten.py
```

Custom port/device:
```bash
uv run blinkenlichten.py <port> <serial_device>
```

Set webhook secret:
```bash
export WEBHOOK_SECRET="your-shared-secret"
uv run blinkenlichten.py
```

### Testing

Run webhook unit tests:
```bash
python3 blinkenlichten/test_webhook.py
```

## Code Architecture

### ESP32 Firmware (`src/main.cpp`)

**Key components:**
- **RGBW emulation**: Uses FastLED with custom RGBW controller wrappers (`CRGBW-final.h`, `FastLED_RGBW.h`) to drive RGBW LED strips using RGB data + white channel emulation
- **EEPROM persistence**: Stores last brightness value (0-100) at address 0, restored on boot
- **Serial protocol**: Line-based ASCII commands at 115200 baud, newline-terminated
- **Effects**: Rainbow snake (moving HSV gradient), flash red (strobing), warm white brightness control

**Configuration in `src/main.cpp`:**
- `NUM_LEDS`: Strip length (default 300)
- `DATA_PIN`: GPIO pin for LED data (default 13)
- `COLOR_DELAY`: Animation timing (default 10ms)

**Important patterns:**
- Effects temporarily override current state, then restore previous brightness from EEPROM
- `showAll()` includes double-send + clear to ensure reliable LED updates
- Command parsing uses space-delimited format: `<command> <value>`

### Python Server (`blinkenlichten/blinkenlichten.py`)

**Key components:**
- **Serial abstraction**: Falls back to dry-run mode if `pyserial` is not installed
- **Commit parsing**: Regex-based validation of Conventional Commits format
- **Non-blocking responses**: Server responds to webhooks immediately, LED commands sent asynchronously

**Webhook logic flow:**
2. Parse JSON payload (supports both `application/json` and `application/x-www-form-urlencoded`)
3. Extract commits array from push event
4. Validate each commit's first line against pattern: `type(scope)?: description`
5. Trigger effect: all valid → `rainbow 5000`, any invalid → `flashred 5000`

**Allowed commit types:**
`feat`, `fix`, `chore`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `revert`

**Serial command translation:**
- HTTP endpoints map to serial commands sent as `<command>\n`
- All commands echo to stdout for debugging
- Serial connection is shared across all request handlers via class variable

## Serial Protocol

Commands sent from Python → ESP32 (ASCII, newline-terminated):

| Command | Format | Description |
|---------|--------|-------------|
| `brightness <0-100>` | `brightness 75` | Set warm white brightness & persist to EEPROM |
| `rainbow <ms>` | `rainbow 5000` | Run rainbow snake, then restore brightness |
| `flashred <ms>` | `flashred 5000` | Flash red pattern, then restore brightness |
| `shutdown 0` | `shutdown 0` | Turn all LEDs off |
| `on <0-100>` | `on 0` | Restore EEPROM brightness (0 = use saved value) |

**Duration handling:** 0 defaults to 5000ms for effects

## HTTP Endpoints

| Method | Path | Query Params | Purpose |
|--------|------|--------------|---------|
| GET | `/` | - | Serve HTML control page |
| GET/POST | `/rainbow` | `duration=<ms>` | Trigger rainbow effect |
| POST | `/flashred` | `duration=<ms>` | Flash red effect |
| POST | `/on` | - | Turn on to saved brightness |
| POST | `/off` or `/shutdown` | - | Turn off |
| POST | `/brightness` | `brightness=<0-100>` | Set brightness |
| POST | `/webhook` | - | GitHub webhook (signature required) |
| GET | `/webhook` | `payload=<json>` | Test webhook (no signature) |

## Important Development Notes

- The ESP32 uses RGBW LED strips via emulation - changes to LED order require updating `W3` parameter in `rgbw` initialization (W3=GRBW, W2=RGBW)
- Webhook secret must be set via environment variable `WEBHOOK_SECRET` for signature validation to work
- Serial device path varies by OS: macOS typically uses `/dev/cu.usbserial-*`, Linux uses `/dev/ttyUSB*`
- The server uses a class-level serial connection shared across all request handlers - avoid closing it during request handling
- EEPROM address 0 is reserved for brightness persistence; expansion requires incrementing `BRIGHTNESS_ADDR`
