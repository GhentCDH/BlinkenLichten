#!/usr/bin/env python3
"""
Test script for GitHub webhook validation and conventional commits checking.
"""

import json
import hmac
import hashlib

# Test data from GitHub docs
TEST_SECRET = "It's a Secret to Everybody"
TEST_PAYLOAD = "Hello, World!"
EXPECTED_SIG = "sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17"

# Test verification function
def verify_github_signature(payload_body, signature_header, secret):
    if not signature_header or not secret:
        return False
    
    hash_object = hmac.new(
        secret.encode('utf-8'),
        msg=payload_body if isinstance(payload_body, bytes) else payload_body.encode('utf-8'),
        digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()
    return hmac.compare_digest(expected_signature, signature_header)

# Test 1: Signature verification with GitHub's test data
print("Test 1: GitHub signature verification")
result = verify_github_signature(TEST_PAYLOAD, EXPECTED_SIG, TEST_SECRET)
print(f"  Expected: True, Got: {result}")
assert result == True, "Signature verification failed!"
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

import re
CONVENTIONAL_TYPES = {
    'feat', 'fix', 'chore', 'docs', 'style', 
    'refactor', 'perf', 'test', 'build', 'ci', 'revert'
}

def check_conventional_commits(commits):
    pattern = re.compile(r'^(\w+)(\([^\)]+\))?!?:\s+.+')
    
    for commit in commits:
        message = commit.get('message', '')
        first_line = message.split('\n')[0]
        
        match = pattern.match(first_line)
        if not match:
            return False
        
        commit_type = match.group(1)
        if commit_type not in CONVENTIONAL_TYPES:
            return False
    
    return True

result = check_conventional_commits(valid_commits)
print(f"  Expected: True, Got: {result}")
assert result == True, "Valid commits check failed!"
print("  ✓ PASSED\n")

# Test 3: Invalid conventional commits
print("Test 3: Invalid conventional commits")
invalid_commits = [
    {"message": "Added a new feature"},  # No type
    {"message": "feat add new feature"},  # Missing colon
    {"message": "foo: invalid type"},     # Unknown type
]

result = check_conventional_commits(invalid_commits)
print(f"  Expected: False, Got: {result}")
assert result == False, "Invalid commits check failed!"
print("  ✓ PASSED\n")

# Test 4: Mixed valid/invalid commits
print("Test 4: Mixed valid/invalid commits")
mixed_commits = [
    {"message": "feat: add feature"},
    {"message": "WIP: work in progress"},  # Invalid
]

result = check_conventional_commits(mixed_commits)
print(f"  Expected: False, Got: {result}")
assert result == False, "Mixed commits check failed!"
print("  ✓ PASSED\n")

# Test 5: Sample GitHub push webhook payload
print("Test 5: Full webhook payload simulation")
sample_payload = {
    "commits": [
        {
            "message": "feat(webhook): add GitHub webhook support\n\nImplements signature validation and conventional commits checking.",
            "author": {"name": "Test User"}
        },
        {
            "message": "fix: correct typo in documentation",
            "author": {"name": "Test User"}
        }
    ]
}

payload_bytes = json.dumps(sample_payload).encode('utf-8')
test_secret = "my-webhook-secret"

# Generate signature
hash_object = hmac.new(
    test_secret.encode('utf-8'),
    msg=payload_bytes,
    digestmod=hashlib.sha256
)
signature = "sha256=" + hash_object.hexdigest()

# Verify
sig_valid = verify_github_signature(payload_bytes, signature, test_secret)
commits_valid = check_conventional_commits(sample_payload['commits'])

print(f"  Signature valid: {sig_valid}")
print(f"  Commits valid: {commits_valid}")
assert sig_valid == True, "Signature validation failed!"
assert commits_valid == True, "Commits validation failed!"
print("  ✓ PASSED\n")

print("=" * 50)
print("All tests passed! ✓")
print("=" * 50)
