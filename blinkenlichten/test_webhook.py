#!/usr/bin/env python3
"""
Test script for GitHub webhook validation and conventional commits checking.
"""

import json
import github_webhook

# Test data from GitHub docs
TEST_SECRET = "It's a Secret to Everybody"
TEST_PAYLOAD = "Hello, World!"
EXPECTED_SIG = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"

# Test 1: Signature verification with GitHub's test data
print("Test 1: GitHub signature verification")
result = github_webhook.verify_github_signature(
    TEST_PAYLOAD.encode('utf-8'),
    EXPECTED_SIG,
    TEST_SECRET
)
print(f"  Expected: valid=True, Got: valid={result['valid']}")
assert result['valid'] == True, f"Signature verification failed! {result['error']}"
print("  ✓ PASSED\n")

# Test 2: Valid conventional commits
print("Test 2: Valid conventional commits")
valid_commits = [
    {"message": "feat: add new feature"},
    {"message": "fix: resolve bug in parser"},
    {"message": "chore: update dependencies"},
    {"message": "docs: improve README"},
    {"message": "feat(api)!: breaking change in API\n\nBREAKING CHANGE: details here"},
]

result = github_webhook.validate_commits(valid_commits)
print(f"  Expected: all_valid=True, Got: all_valid={result['all_valid']}")
print(f"  Summary: {result['summary']}")
assert result['all_valid'] == True, "Valid commits check failed!"
assert result['valid_commits'] == 5, "Expected 5 valid commits"
assert result['invalid_commits'] == 0, "Expected 0 invalid commits"
print("  ✓ PASSED\n")

# Test 3: Invalid conventional commits
print("Test 3: Invalid conventional commits")
invalid_commits = [
    {"message": "Added a new feature", "id": "abc123", "author": {"name": "Test"}},  # No type
    {"message": "feat add new feature", "id": "def456", "author": {"name": "Test"}},  # Missing colon
    {"message": "foo: invalid type", "id": "ghi789", "author": {"name": "Test"}},     # Unknown type
]

result = github_webhook.validate_commits(invalid_commits)
print(f"  Expected: all_valid=False, Got: all_valid={result['all_valid']}")
print(f"  Summary: {result['summary']}")
print(f"  Errors: {len(result['errors'])} found")
assert result['all_valid'] == False, "Invalid commits check failed!"
assert result['invalid_commits'] == 3, "Expected 3 invalid commits"
assert len(result['errors']) == 3, "Expected 3 error messages"
print("  ✓ PASSED\n")

# Test 4: Mixed valid/invalid commits
print("Test 4: Mixed valid/invalid commits")
mixed_commits = [
    {"message": "feat: add feature", "id": "aaa111", "author": {"name": "Test"}},
    {"message": "WIP: work in progress", "id": "bbb222", "author": {"name": "Test"}},  # Invalid
]

result = github_webhook.validate_commits(mixed_commits)
print(f"  Expected: all_valid=False, Got: all_valid={result['all_valid']}")
print(f"  Summary: {result['summary']}")
assert result['all_valid'] == False, "Mixed commits check failed!"
assert result['valid_commits'] == 1, "Expected 1 valid commit"
assert result['invalid_commits'] == 1, "Expected 1 invalid commit"
print("  ✓ PASSED\n")

# Test 5: Full webhook payload simulation (push event)
print("Test 5: Full push webhook payload simulation")
sample_payload = {
    "commits": [
        {
            "id": "abc123456",
            "message": "feat(webhook): add GitHub webhook support\n\nImplements signature validation and conventional commits checking.",
            "author": {"name": "Test User"}
        },
        {
            "id": "def789012",
            "message": "fix: correct typo in documentation",
            "author": {"name": "Test User"}
        }
    ]
}

payload_bytes = json.dumps(sample_payload).encode('utf-8')
test_secret = "my-webhook-secret"

# Generate signature (using standard hmac for signature generation)
import hmac
import hashlib
hash_object = hmac.new(
    test_secret.encode('utf-8'),
    msg=payload_bytes,
    digestmod=hashlib.sha256
)
signature = "sha256=" + hash_object.hexdigest()

# Test the full process_webhook function
result = github_webhook.process_webhook(
    raw_body=payload_bytes,
    signature_header=signature,
    event_type='push',
    content_type='application/json',
    webhook_secret=test_secret
)

print(f"  Status: {result['status']}")
print(f"  Effect: {result['effect']}")
print(f"  Message: {result['message']}")
assert result['status'] == 'success', "Webhook processing failed!"
assert result['effect'] == 'rainbow', "Expected rainbow effect for valid commits!"
assert result['status_code'] == 200, "Expected status code 200"
print("  ✓ PASSED\n")

# Test 6: Workflow run event on version tag
print("Test 6: Workflow run event on version tag")
workflow_payload = {
    "workflow_run": {
        "name": "CI",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "v1.2.3"
    }
}

result = github_webhook.process_workflow_run_event(workflow_payload)
print(f"  Should trigger: {result['should_trigger']}")
print(f"  Effect: {result['effect']}")
print(f"  Reason: {result['reason']}")
assert result['should_trigger'] == True, "Should trigger for successful workflow on version tag"
assert result['effect'] == 'flashgreen', "Expected flashgreen effect"
print("  ✓ PASSED\n")

# Test 7: Workflow run event not on version tag
print("Test 7: Workflow run event not on version tag")
workflow_payload = {
    "workflow_run": {
        "name": "CI",
        "status": "completed",
        "conclusion": "success",
        "head_branch": "main"
    }
}

result = github_webhook.process_workflow_run_event(workflow_payload)
print(f"  Should trigger: {result['should_trigger']}")
print(f"  Reason: {result['reason']}")
assert result['should_trigger'] == False, "Should not trigger for non-version tag"
assert result['effect'] is None, "Expected no effect"
print("  ✓ PASSED\n")

# Test 8: Test is_version_tag function
print("Test 8: Version tag detection")
assert github_webhook.is_version_tag("v1.0.0") == True, "Should match v1.0.0"
assert github_webhook.is_version_tag("1.2.3") == True, "Should match 1.2.3"
assert github_webhook.is_version_tag("v2.1.0-beta") == True, "Should match v2.1.0-beta"
assert github_webhook.is_version_tag("main") == False, "Should not match 'main'"
assert github_webhook.is_version_tag("feature-branch") == False, "Should not match 'feature-branch'"
print("  ✓ PASSED\n")

print("=" * 50)
print("All tests passed! ✓")
print("=" * 50)
