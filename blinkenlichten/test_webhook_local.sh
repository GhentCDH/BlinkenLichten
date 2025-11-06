#!/bin/bash
# Quick test script for GitHub webhook endpoint
# Usage: ./test_webhook_local.sh [commit-message]

WEBHOOK_URL="${WEBHOOK_URL:-http://localhost:55155/webhook}"
WEBHOOK_SECRET="${WEBHOOK_SECRET:-test-secret}"

# Default test message
COMMIT_MSG="${1:-feat: test webhook integration}"

echo "Testing webhook with commit: $COMMIT_MSG"
echo "URL: $WEBHOOK_URL"
echo ""

# Create payload
PAYLOAD=$(cat <<EOF
{
  "commits": [
    {
      "message": "$COMMIT_MSG",
      "author": {
        "name": "Test User",
        "email": "test@example.com"
      },
      "id": "abc123"
    }
  ],
  "repository": {
    "name": "test-repo",
    "full_name": "user/test-repo"
  }
}
EOF
)

# Generate HMAC-SHA256 signature
SIGNATURE=$(echo -n "$PAYLOAD" | openssl dgst -sha256 -hmac "$WEBHOOK_SECRET" | sed 's/^.* /sha256=/')

echo "Payload:"
echo "$PAYLOAD" | python3 -m json.tool
echo ""

# Send webhook
echo "Sending webhook..."
RESPONSE=$(curl -s -w "\nHTTP Status: %{http_code}\n" -X POST "$WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "X-Hub-Signature-256: $SIGNATURE" \
  -d "$PAYLOAD")

echo ""
echo "Response:"
echo "$RESPONSE"
echo ""

# Test examples
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Try these examples:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Valid (should trigger rainbow):"
echo "  ./test_webhook_local.sh 'feat: add new feature'"
echo "  ./test_webhook_local.sh 'fix: resolve bug'"
echo "  ./test_webhook_local.sh 'chore: update deps'"
echo "  ./test_webhook_local.sh 'docs: improve README'"
echo ""
echo "Invalid (should trigger flash red):"
echo "  ./test_webhook_local.sh 'Added new feature'"
echo "  ./test_webhook_local.sh 'WIP: work in progress'"
echo "  ./test_webhook_local.sh 'fix bug'"
echo ""
