# GitHub Webhook Setup Guide

This guide shows you how to configure GitHub to send webhook events to your BlinkenLichten LED controller.

## How It Works

When you push commits to your GitHub repository:
1. GitHub sends a webhook POST request to your server at `/webhook`
2. The server validates the signature using HMAC-SHA256
3. The server checks if all commit messages follow [Conventional Commits](https://www.conventionalcommits.org/)
4. If **all commits are valid** → **Rainbow effect** 🌈
5. If **any commit is invalid** → **Flash red effect** 🔴

## Conventional Commits

Valid commit message formats:
- `feat: add new feature`
- `fix: resolve bug`
- `chore: update dependencies`
- `docs: improve documentation`
- `style: format code`
- `refactor: restructure module`
- `perf: optimize performance`
- `test: add unit tests`
- `build: update build config`
- `ci: configure CI pipeline`
- `revert: undo previous commit`

With optional scope:
- `feat(api): add endpoint`
- `fix(parser): handle edge case`

Breaking changes:
- `feat!: breaking change`
- `fix(api)!: breaking API change`

## Setup Instructions

### 1. Generate a Webhook Secret

Create a strong random secret token:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

Save this secret - you'll need it for both GitHub and your server.

### 2. Configure Environment Variable

Set the webhook secret on your server:

```bash
export WEBHOOK_SECRET="your-secret-token-here"
```

Or create a `.env` file:

```bash
echo 'WEBHOOK_SECRET=your-secret-token-here' > .env
```

### 3. Start the Server

```bash
cd blinkenlichten
uv run blinkenlichten.py
```

The server will display:
```
Starting BlinkenLichten HTTP to Serial bridge...
Listening on port: 55155
Serial device: /dev/cu.usbserial-0001
Web interface: http://0.0.0.0:55155/
GitHub webhook secret: configured (length=64)

Endpoints:
  ...
  POST /webhook - GitHub webhook (validates signature, checks conventional commits)
```

### 4. Configure GitHub Webhook

1. Go to your repository on GitHub
2. Navigate to **Settings** → **Webhooks** → **Add webhook**
3. Configure:
   - **Payload URL**: `http://your-server:55155/webhook`
   - **Content type**: `application/json`
   - **Secret**: Paste your webhook secret token
   - **Which events**: Select "Just the push event"
   - **Active**: Check this box
4. Click **Add webhook**

### 5. Expose Your Server (if needed)

If your server is behind a firewall, you'll need to expose it. Options:

#### Option A: ngrok (for testing)

```bash
ngrok http 55155
```

Use the HTTPS URL (e.g., `https://abc123.ngrok.io/webhook`) as your webhook URL.

#### Option B: Reverse Proxy (production)

Use nginx, Caddy, or similar to proxy requests to your server:

```nginx
location /webhook {
    proxy_pass http://localhost:55155/webhook;
    proxy_set_header X-Hub-Signature-256 $http_x_hub_signature_256;
}
```

## Testing

### Test with curl

Simulate a GitHub webhook (replace the secret and compute a valid signature):

```bash
# Generate test signature
SECRET="your-secret-token"
PAYLOAD='{"commits":[{"message":"feat: test webhook"}]}'
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$SECRET" | sed 's/^.* /sha256=/')

# Send webhook
curl -X POST http://localhost:55155/webhook \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIGNATURE" \
  -d "$PAYLOAD"
```

### Use the Test Script

Run the included test script to verify signature validation and commit parsing:

```bash
python3 test_webhook.py
```

Expected output:
```
Test 1: GitHub signature verification
  Expected: True, Got: True
  ✓ PASSED

...

All tests passed! ✓
```

## Examples

### Valid Commits → Rainbow 🌈

```json
{
  "commits": [
    {"message": "feat: add webhook integration"},
    {"message": "docs: update README with setup guide"},
    {"message": "chore: bump version to 1.2.0"}
  ]
}
```

Result: LEDs show rainbow effect

### Invalid Commits → Flash Red 🔴

```json
{
  "commits": [
    {"message": "Added new feature"},
    {"message": "WIP: work in progress"},
    {"message": "fix typo"}
  ]
}
```

Result: LEDs flash red

## Security Notes

1. **Never commit your webhook secret** to version control
2. Always use HTTPS in production (not HTTP)
3. The signature validation prevents unauthorized requests
4. Store the secret in environment variables or a secrets manager
5. Rotate your webhook secret periodically

## Troubleshooting

### "Forbidden: Invalid signature"

- Check that `WEBHOOK_SECRET` matches the secret configured in GitHub
- Verify the secret has no leading/trailing whitespace
- Ensure the server received the `X-Hub-Signature-256` header

### "No commits to process"

- The webhook is working, but the push had no commits (e.g., tag creation)
- This is normal and safe to ignore

### LEDs flash red for valid commits

- Check the commit message format carefully
- Ensure the type is one of: feat, fix, chore, docs, style, refactor, perf, test, build, ci, revert
- Verify there's a colon and space after the type: `feat: description` (not `feat:description`)

### Server logs show "Command sent" but LEDs don't respond

- Check serial connection to ESP32
- Verify `/dev/cu.usbserial-0001` is correct
- Ensure ESP32 firmware is running and listening for serial commands

## API Reference

### POST /webhook

Receives GitHub push events and triggers LED effects based on commit message validation.

**Headers:**
- `X-Hub-Signature-256`: HMAC-SHA256 signature (required)
- `Content-Type`: application/json

**Request Body:**
```json
{
  "commits": [
    {
      "message": "commit message",
      "author": {...},
      ...
    }
  ],
  ...
}
```

**Responses:**
- `200 OK`: Webhook processed successfully
- `400 Bad Request`: Invalid JSON payload
- `403 Forbidden`: Invalid signature

**Examples:**

Valid conventional commits:
```
→ Response: OK: Processed 3 commits - rainbow
→ LED Effect: Rainbow 🌈
```

Invalid commits:
```
→ Response: OK: Processed 2 commits - flashred
→ LED Effect: Flash Red 🔴
```

## Further Reading

- [GitHub Webhooks Documentation](https://docs.github.com/en/webhooks)
- [Conventional Commits Specification](https://www.conventionalcommits.org/)
- [HMAC Signature Validation](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)
