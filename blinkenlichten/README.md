# BlinkenLichten LED Controller

HTTP-to-serial bridge for controlling LED strips via web interface and GitHub webhooks.

## Features

- 🌐 **Web Interface** - Control LEDs via browser
- 🎨 **LED Effects** - Rainbow, flash red, brightness control
- 🔗 **GitHub Webhooks** - Validate Conventional Commits with LED feedback
- 🔒 **Secure** - HMAC-SHA256 signature verification
- ⚡ **Fast** - Non-blocking HTTP responses

## Quick Start

### 1. Install Dependencies

```bash
uv sync
```

### 2. Run the Server

```bash
uv run blinkenlichten.py
```

The server starts on port 55155 with these endpoints:

- `GET /` - Web interface
- `GET /rainbow` - Trigger rainbow effect
- `POST /brightness?brightness=0-100` - Set brightness
- `POST /flashred` - Flash red effect
- `POST /on` - Turn lights on
- `POST /off` - Turn lights off
- `POST /webhook` - GitHub webhook endpoint

### 3. Access Web Interface

Open http://localhost:55155/ in your browser.

## GitHub Webhook Integration

Configure GitHub to send push events to your server and get real-time LED feedback based on commit quality!

✅ **All commits follow Conventional Commits** → 🌈 Rainbow effect  
❌ **Any invalid commits** → 🔴 Flash red effect

See [WEBHOOK.md](./WEBHOOK.md) for detailed setup instructions.

## Project Structure

```
blinkenlichten/
├── blinkenlichten.py      # Main HTTP server
├── index.html             # Web interface
├── test_webhook.py        # Unit tests for webhook validation
├── test_webhook_local.sh  # Manual webhook testing script
├── pyproject.toml         # Python dependencies
├── README.md              # This file
└── WEBHOOK.md             # GitHub webhook setup guide
```

## Serial Commands

The server translates HTTP requests to serial commands sent to the ESP32:

| Command | Format | Example |
|---------|--------|---------|
| Brightness | `brightness <0-100>` | `brightness 75` |
| Rainbow | `rainbow <duration_ms>` | `rainbow 5000` |
| Flash Red | `flashred <duration_ms>` | `flashred 3000` |
| On | `on 0` | `on 0` |
| Shutdown | `shutdown 0` | `shutdown 0` |

## Configuration

Environment variables:

- `WEBHOOK_SECRET` - GitHub webhook secret token (required for webhooks)

Command-line arguments:

```bash
uv run blinkenlichten.py [port] [serial_device]
```

Examples:
```bash
# Use custom port
uv run blinkenlichten.py 8080

# Use custom serial device
uv run blinkenlichten.py 55155 /dev/ttyUSB0
```

## Testing

### Run Unit Tests

```bash
python3 test_webhook.py
```

### Test Webhook Locally

```bash
export WEBHOOK_SECRET="your-secret-here"
./test_webhook_local.sh "feat: test webhook"
```

## Development

The server uses Python's built-in `http.server` with:
- HMAC-SHA256 for webhook signature validation
- Regex pattern matching for Conventional Commits
- pyserial for ESP32 communication

## License

MIT

## Related Files

- [WEBHOOK.md](./WEBHOOK.md) - Detailed GitHub webhook setup
- [../src/main.cpp](../src/main.cpp) - ESP32 firmware
- [../platformio.ini](../platformio.ini) - PlatformIO configuration
