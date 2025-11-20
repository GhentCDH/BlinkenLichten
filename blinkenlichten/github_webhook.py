"""
GitHub webhook processing and commit validation.

This module handles GitHub webhook payloads, validates commit messages against
Conventional Commits format, and determines which LED effects to trigger.
"""

import json
import hmac
import hashlib
import re
from typing import Dict, List, Any, Optional, Tuple


# Conventional Commits types as per https://www.conventionalcommits.org/
CONVENTIONAL_TYPES = {
    'feat', 'fix', 'chore', 'docs', 'style',
    'refactor', 'perf', 'test', 'build', 'ci', 'revert'
}

# Regex patterns
CONVENTIONAL_COMMIT_PATTERN = re.compile(r'^(\w+)(\([^\)]+\))?!?:\s+.+')
VERSION_TAG_PATTERN = re.compile(r'^v?\d+\.\d+\.\d+.*$')


def verify_github_signature(
    raw_body: bytes,
    signature_header: str,
    secret: str
) -> Dict[str, Any]:
    """
    Verify GitHub webhook signature using HMAC-SHA256.

    Args:
        raw_body: Raw HTTP request body as received (bytes)
        signature_header: Value of X-Hub-Signature-256 header
        secret: Webhook secret

    Returns:
        Dictionary with:
        - 'valid': bool - Whether signature is valid
        - 'message': str - Human-readable status message
        - 'error': Optional[str] - Error details if validation failed
    """
    if not signature_header:
        return {
            'valid': False,
            'message': 'Missing signature header',
            'error': 'X-Hub-Signature-256 header not provided'
        }

    if not secret:
        return {
            'valid': False,
            'message': 'Secret not configured',
            'error': 'WEBHOOK_SECRET environment variable not set'
        }

    try:
        mac = hmac.new(secret.encode('utf-8'), msg=raw_body, digestmod=hashlib.sha256)
        expected = 'sha256=' + mac.hexdigest()
        valid = hmac.compare_digest(expected, signature_header)

        return {
            'valid': valid,
            'message': 'Signature valid' if valid else 'Signature mismatch',
            'error': None if valid else 'Computed signature does not match provided signature'
        }
    except Exception as e:
        return {
            'valid': False,
            'message': 'Signature verification failed',
            'error': f'Exception during verification: {str(e)}'
        }


def is_conventional_commit(message: str) -> Dict[str, Any]:
    """
    Check if a commit message follows Conventional Commits format.

    Args:
        message: Full commit message (may contain multiple lines)

    Returns:
        Dictionary with:
        - 'valid': bool - Whether commit message is valid
        - 'commit_type': Optional[str] - The type (feat, fix, etc.) if valid
        - 'scope': Optional[str] - The scope if present
        - 'message': str - First line of commit message
        - 'error': Optional[str] - Error description if invalid
    """
    first_line = message.split('\n')[0].strip()

    if not first_line:
        return {
            'valid': False,
            'commit_type': None,
            'scope': None,
            'message': first_line,
            'error': 'Empty commit message'
        }

    match = CONVENTIONAL_COMMIT_PATTERN.match(first_line)
    if not match:
        return {
            'valid': False,
            'commit_type': None,
            'scope': None,
            'message': first_line,
            'error': f'Does not match Conventional Commits format (type(scope)?: description)'
        }

    commit_type = match.group(1)
    scope = match.group(2)  # Will be None or "(scope)" with parentheses

    # Clean up scope (remove parentheses)
    if scope:
        scope = scope.strip('()')

    if commit_type not in CONVENTIONAL_TYPES:
        return {
            'valid': False,
            'commit_type': commit_type,
            'scope': scope,
            'message': first_line,
            'error': f'Unknown commit type "{commit_type}". Allowed types: {", ".join(sorted(CONVENTIONAL_TYPES))}'
        }

    return {
        'valid': True,
        'commit_type': commit_type,
        'scope': scope,
        'message': first_line,
        'error': None
    }


def validate_commits(commits: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Validate multiple commits against Conventional Commits format.

    Args:
        commits: List of commit objects from GitHub webhook payload

    Returns:
        Dictionary with:
        - 'all_valid': bool - True if all commits are valid
        - 'total_commits': int - Total number of commits
        - 'valid_commits': int - Number of valid commits
        - 'invalid_commits': int - Number of invalid commits
        - 'errors': List[Dict] - Details about invalid commits
        - 'summary': str - Human-readable summary
    """
    if not commits:
        return {
            'all_valid': True,
            'total_commits': 0,
            'valid_commits': 0,
            'invalid_commits': 0,
            'errors': [],
            'summary': 'No commits to validate'
        }

    errors = []
    valid_count = 0

    for idx, commit in enumerate(commits):
        message = commit.get('message', '')
        commit_id = commit.get('id', 'unknown')[:7]  # Short SHA
        author = commit.get('author', {}).get('name', 'Unknown')

        result = is_conventional_commit(message)

        if result['valid']:
            valid_count += 1
        else:
            errors.append({
                'commit_id': commit_id,
                'author': author,
                'message': result['message'],
                'error': result['error']
            })

    total = len(commits)
    invalid_count = total - valid_count
    all_valid = invalid_count == 0

    summary = f"Validated {total} commit(s): {valid_count} valid, {invalid_count} invalid"

    return {
        'all_valid': all_valid,
        'total_commits': total,
        'valid_commits': valid_count,
        'invalid_commits': invalid_count,
        'errors': errors,
        'summary': summary
    }


def extract_commits_from_payload(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Safely extract commits array from GitHub push event payload.

    Args:
        payload: GitHub webhook payload

    Returns:
        List of commit objects (empty list if none found)
    """
    return payload.get('commits', [])


def is_version_tag(ref: str) -> bool:
    """
    Check if a ref is a version tag (e.g., v1.0.0, 2.1.3).

    Args:
        ref: Git ref (branch name, tag name, etc.)

    Returns:
        True if ref matches semantic versioning pattern
    """
    return bool(VERSION_TAG_PATTERN.match(ref))


def process_workflow_run_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process GitHub workflow_run webhook event.

    Determines if a flashgreen effect should be triggered based on workflow
    completion status and whether it ran on a version tag.

    Args:
        payload: GitHub workflow_run webhook payload

    Returns:
        Dictionary with:
        - 'should_trigger': bool - Whether to trigger an effect
        - 'effect': Optional[str] - Effect name ('flashgreen' or None)
        - 'duration': int - Effect duration in milliseconds
        - 'workflow': Dict - Workflow details
        - 'reason': str - Human-readable explanation
    """
    workflow_run = payload.get('workflow_run', {})
    conclusion = workflow_run.get('conclusion')
    status = workflow_run.get('status')
    head_branch = workflow_run.get('head_branch', '')
    workflow_name = workflow_run.get('name', 'Unknown')

    workflow_details = {
        'name': workflow_name,
        'status': status,
        'conclusion': conclusion,
        'head_branch': head_branch
    }

    # Check for successful workflow on version tag
    if status == 'completed' and conclusion == 'success' and is_version_tag(head_branch):
        return {
            'should_trigger': True,
            'effect': 'flashgreen',
            'duration': 5000,
            'workflow': workflow_details,
            'reason': f'Workflow "{workflow_name}" succeeded on version tag "{head_branch}"'
        }

    # Workflow completed successfully but not on version tag
    if status == 'completed' and conclusion == 'success':
        return {
            'should_trigger': False,
            'effect': None,
            'duration': 0,
            'workflow': workflow_details,
            'reason': f'Workflow succeeded but not on version tag (branch: {head_branch})'
        }

    # Workflow not successful or not completed
    return {
        'should_trigger': False,
        'effect': None,
        'duration': 0,
        'workflow': workflow_details,
        'reason': f'Workflow not successful (status: {status}, conclusion: {conclusion})'
    }


def process_push_event(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process GitHub push webhook event.

    Validates commits and determines which effect to trigger based on
    Conventional Commits validation.

    Args:
        payload: GitHub push webhook payload

    Returns:
        Dictionary with:
        - 'should_trigger': bool - Whether to trigger an effect
        - 'effect': str - Effect name ('rainbow' or 'flashred')
        - 'duration': int - Effect duration in milliseconds
        - 'validation': Dict - Commit validation results
        - 'reason': str - Human-readable explanation
    """
    commits = extract_commits_from_payload(payload)

    if not commits:
        return {
            'should_trigger': False,
            'effect': None,
            'duration': 0,
            'validation': {
                'all_valid': True,
                'total_commits': 0,
                'valid_commits': 0,
                'invalid_commits': 0,
                'errors': []
            },
            'reason': 'No commits in push event'
        }

    validation = validate_commits(commits)

    if validation['all_valid']:
        return {
            'should_trigger': True,
            'effect': 'rainbow',
            'duration': 5000,
            'validation': validation,
            'reason': f'All {validation["total_commits"]} commit(s) are valid Conventional Commits'
        }
    else:
        return {
            'should_trigger': True,
            'effect': 'flashred',
            'duration': 5000,
            'validation': validation,
            'reason': f'{validation["invalid_commits"]} of {validation["total_commits"]} commit(s) failed validation'
        }


def process_webhook(
    raw_body: bytes,
    signature_header: str,
    event_type: str,
    content_type: str,
    webhook_secret: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main webhook processing function.

    Orchestrates signature verification, payload parsing, and event processing.

    Args:
        raw_body: Raw HTTP request body (bytes)
        signature_header: X-Hub-Signature-256 header value
        event_type: X-GitHub-Event header value
        content_type: Content-Type header value
        webhook_secret: Optional webhook secret for signature verification

    Returns:
        Dictionary with:
        - 'status': str - 'success', 'error', or 'no_action'
        - 'status_code': int - HTTP status code to return
        - 'effect': Optional[str] - LED effect to trigger
        - 'duration': int - Effect duration in milliseconds
        - 'message': str - Human-readable message
        - 'details': Dict - Event-specific details
    """
    # Verify signature if secret is configured
    if webhook_secret:
        sig_result = verify_github_signature(raw_body, signature_header, webhook_secret)
        if not sig_result['valid']:
            return {
                'status': 'error',
                'status_code': 403,
                'effect': None,
                'duration': 0,
                'message': 'Signature verification failed',
                'details': {
                    'signature_error': sig_result['error'],
                    'event_type': event_type
                }
            }
    else:
        print("Warning: WEBHOOK_SECRET not set, skipping signature validation")

    # Parse JSON payload based on content type
    payload_json_bytes: Optional[bytes] = None
    content_type_lower = content_type.lower()

    if 'application/json' in content_type_lower:
        payload_json_bytes = raw_body
    elif 'application/x-www-form-urlencoded' in content_type_lower:
        # GitHub may send form-encoded data with JSON in 'payload' field
        try:
            from urllib.parse import parse_qs
            form = parse_qs(raw_body.decode('utf-8'))
            payload_str = form.get('payload', [None])[0]
            if payload_str:
                payload_json_bytes = payload_str.encode('utf-8')
        except Exception as e:
            return {
                'status': 'error',
                'status_code': 400,
                'effect': None,
                'duration': 0,
                'message': 'Failed to parse form-encoded body',
                'details': {'parse_error': str(e)}
            }
    else:
        # Try JSON as last resort
        payload_json_bytes = raw_body

    if not payload_json_bytes:
        return {
            'status': 'error',
            'status_code': 400,
            'effect': None,
            'duration': 0,
            'message': 'Missing payload',
            'details': {'content_type': content_type}
        }

    # Parse JSON
    try:
        payload = json.loads(payload_json_bytes.decode('utf-8'))
    except json.JSONDecodeError as e:
        return {
            'status': 'error',
            'status_code': 400,
            'effect': None,
            'duration': 0,
            'message': 'Invalid JSON in payload',
            'details': {'json_error': str(e)}
        }

    # Process based on event type
    if event_type == 'workflow_run':
        result = process_workflow_run_event(payload)
        if result['should_trigger']:
            return {
                'status': 'success',
                'status_code': 200,
                'effect': result['effect'],
                'duration': result['duration'],
                'message': result['reason'],
                'details': result['workflow']
            }
        else:
            return {
                'status': 'no_action',
                'status_code': 200,
                'effect': None,
                'duration': 0,
                'message': result['reason'],
                'details': result['workflow']
            }

    elif event_type == 'push':
        result = process_push_event(payload)
        if result['should_trigger']:
            return {
                'status': 'success',
                'status_code': 200,
                'effect': result['effect'],
                'duration': result['duration'],
                'message': result['reason'],
                'details': {
                    'validation': result['validation'],
                    'commits': result['validation']['total_commits']
                }
            }
        else:
            return {
                'status': 'no_action',
                'status_code': 200,
                'effect': None,
                'duration': 0,
                'message': result['reason'],
                'details': {'validation': result['validation']}
            }

    else:
        return {
            'status': 'error',
            'status_code': 400,
            'effect': None,
            'duration': 0,
            'message': f'Unsupported event type: {event_type}',
            'details': {'event_type': event_type}
        }
