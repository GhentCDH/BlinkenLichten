"""
Simple HTTP server that sends serial commands on incoming requests.
Usage: python3 http_serial.py [port] [serial_device]
"""

import sys
import os
import json
import hmac
import hashlib
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
try:
    import serial  # type: ignore
except ImportError:  # Provide a graceful fallback so the server can start without hardware during tests
    serial = None  # type: ignore
    class _DummySerial:
        def __init__(self, *a, **kw):
            self.is_open = True
        def write(self, data: bytes):
            print(f"[DRY-RUN serial] write -> {data!r}")
        def flush(self):
            pass
        def close(self):
            self.is_open = False
    def _dummy_serial_factory(*a, **kw):
        print("Warning: pyserial not installed. Running in dry-run mode (no actual serial I/O). Install with 'pip install pyserial' for real hardware.")
        return _DummySerial()


# Configuration
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 55156
SERIAL_DEVICE = sys.argv[2] if len(sys.argv) > 2 else '/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0'
SERIAL_BAUDRATE = 115200
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')

# Conventional Commits types as per https://www.conventionalcommits.org/
CONVENTIONAL_TYPES = {
    'feat', 'fix', 'chore', 'docs', 'style', 
    'refactor', 'perf', 'test', 'build', 'ci', 'revert'
}

def send_serial_command(command,ser):
    """Send a command to the serial device."""
    try:
        ser.write(f'{command}\n'.encode("ascii"))
        ser.flush()
        print(f"Command sent: {command}")
        return True, f'Command sent: {command}'
    except Exception as e:
        print(f"Error sending command: {command} - {str(e)}")
        return False, f'Error: {str(e)}'

def verify_github_signature(raw_body: bytes, signature_header: str, secret: str) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256 over the raw request body.

    Args:
        raw_body: raw HTTP request body as received (bytes)
        signature_header: value of X-Hub-Signature-256 header
        secret: webhook secret

    Returns:
        True if signature matches, False otherwise. If secret or header is missing, returns False.
    """
    if not signature_header or not secret:
        return False
    mac = hmac.new(secret.encode('utf-8'), msg=raw_body, digestmod=hashlib.sha256)
    expected = 'sha256=' + mac.hexdigest()
    try:
        return hmac.compare_digest(expected, signature_header)
    except Exception:
        # Fallback simple compare if constant-time not available
        return expected == signature_header

def check_conventional_commits(commits):
    """
    Check if all commits follow Conventional Commits format.
    
    Args:
        commits: List of commit objects from GitHub webhook payload
    
    Returns:
        True if all commits are valid conventional commits, False otherwise
    """
    # Pattern: type(optional-scope): description
    # Types: feat, fix, chore, docs, style, refactor, perf, test, build, ci, revert
    pattern = re.compile(r'^(\w+)(\([^\)]+\))?!?:\s+.+')
    
    for commit in commits:
        message = commit.get('message', '')
        first_line = message.split('\n')[0]
        
        match = pattern.match(first_line)
        if not match:
            print(f"Invalid conventional commit format: {first_line}")
            return False
        
        commit_type = match.group(1)
        if commit_type not in CONVENTIONAL_TYPES:
            print(f"Unknown commit type '{commit_type}': {first_line}")
            return False
    
    print(f"All {len(commits)} commits are valid conventional commits")
    return True

class SerialHandler(BaseHTTPRequestHandler):
    serial_connection = None  # Class variable to hold serial connection
    
    def do_GET(self):
        # Parse path and query for GET endpoints
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        params = parse_qs(parsed_path.query)

        if path == '/':
            # Serve the HTML page for root path
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            html_page = ''
            with open('index.html', 'r') as f:
                html_page = f.read()
            self.wfile.write(html_page.encode())
        elif path == '/rainbow':
            # Support GET /rainbow?duration=<ms>
            duration = params.get('duration', ['5000'])[0]
            command = f'rainbow {duration}'
            print(f"Sending command (GET): {command}")
            success, message = send_serial_command(command, self.serial_connection)
            status_code = 200 if success else 500

            self.send_response(status_code)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(message.encode())
        elif path == '/webhook':
            # Accept webhook payload via GET for testing purposes
            # Prefer ?payload=<urlencoded json>; fallback to GET body if provided.
            payload_param = params.get('payload', [None])[0]
            payload_body = None
            if payload_param:
                try:
                    payload_body = payload_param.encode('utf-8')
                except Exception:
                    payload_body = None
            else:
                # Fallback: some clients may send a GET with a body (non-standard)
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    payload_body = self.rfile.read(content_length)

            if not payload_body:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Bad Request: Missing payload\n')
                return

            # Parse JSON payload
            try:
                payload = json.loads(payload_body.decode('utf-8'))
            except json.JSONDecodeError as e:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Bad Request: Invalid JSON\n')
                print(f"Webhook (GET) rejected: Invalid JSON - {e}")
                return

            # Extract commits
            commits = payload.get('commits', [])
            if not commits:
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'OK: No commits to process\n')
                print("Webhook (GET): No commits in payload")
                return

            all_valid = check_conventional_commits(commits)

            # Trigger appropriate LED effect
            if all_valid:
                command = 'rainbow 5000'
                print("Webhook (GET): All commits valid -> Rainbow effect")
            else:
                command = 'flashred 5000'
                print("Webhook (GET): Invalid commits found -> Flash red effect")

            send_serial_command(command, self.serial_connection)

            # Respond
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            resp = {
                'commits': len(commits),
                'result': 'rainbow' if all_valid else 'flashred'
            }
            self.wfile.write(json.dumps(resp).encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not found\n')
    
    def do_POST(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        params = parse_qs(parsed_path.query)
        
        # Handle GitHub webhook
        if path == '/webhook':
            # Read raw body (used for signature verification)
            content_length = int(self.headers.get('Content-Length', 0))
            raw_body = self.rfile.read(content_length)

            # Verify signature if secret configured
            signature_header = self.headers.get('X-Hub-Signature-256', '')
            if WEBHOOK_SECRET:
                if not verify_github_signature(raw_body, signature_header, WEBHOOK_SECRET):
                    self.send_response(403)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Forbidden: Invalid signature\n')
                    print("Webhook rejected: Invalid signature")
                    return
            else:
                print("Warning: WEBHOOK_SECRET not set, skipping signature validation")

            # Determine content type and extract JSON payload
            content_type = (self.headers.get('Content-Type') or '').lower()
            payload_json_bytes: bytes | None = None
            if 'application/json' in content_type:
                payload_json_bytes = raw_body
            elif 'application/x-www-form-urlencoded' in content_type:
                # Body is key=value&key=value, JSON is under 'payload'
                try:
                    form = parse_qs(raw_body.decode('utf-8'))
                    payload_str = form.get('payload', [None])[0]
                    if payload_str is not None:
                        payload_json_bytes = payload_str.encode('utf-8')
                except Exception as e:
                    payload_json_bytes = None
                    print(f"Webhook: failed to parse form-encoded body: {e}")
            else:
                # Try JSON as a last resort
                payload_json_bytes = raw_body

            if not payload_json_bytes:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Bad Request: Missing payload\n')
                print("Webhook rejected: Missing payload")
                return

            # Parse JSON payload
            try:
                payload = json.loads(payload_json_bytes.decode('utf-8'))
            except json.JSONDecodeError as e:
                self.send_response(400)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Bad Request: Invalid JSON\n')
                print(f"Webhook rejected: Invalid JSON - {e}")
                return

            event_type = self.headers.get('X-GitHub-Event', '')

            # flash green when a workflow for a versioned tag was successful
            if event_type == "workflow_run":
                workflow_run = payload.get('workflow_run', {})
                conclusion = workflow_run.get('conclusion')
                status = workflow_run.get('status')
                head_branch = workflow_run.get('head_branch', '')
                
                print(f"Workflow run event: status={status}, conclusion={conclusion}, branch={head_branch}")
                
                # Check if workflow completed successfully and branch is a version tag
                if status == 'completed' and conclusion == 'success' and self._is_version_tag(head_branch):
                    command = 'flashgreen 5000'
                    print(f"Webhook: Workflow succeeded on version tag '{head_branch}' -> Flash green effect")
                    send_serial_command(command, self.serial_connection)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'OK: Version tag workflow success - flashgreen\n')
                    return
                elif status == 'completed' and conclusion == 'success':
                    print(f"Webhook: Workflow succeeded but not on version tag (branch: {head_branch})")
                else:
                    print("Webhook: Workflow not successful or not completed")
                
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'OK: Workflow event processed\n')
                return

            # Extract commits from push event & check if they are conventional
            if event_type == "push":
                commits = payload.get('commits', [])
                if not commits:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'OK: No commits to process\n')
                    print("Webhook: No commits in payload")
                    return
                
                # Check if all commits follow Conventional Commits
                all_valid = check_conventional_commits(commits)
                
                # Trigger appropriate LED effect
                if all_valid:
                    command = 'rainbow 5000'
                    print("Webhook: All commits valid -> Rainbow effect")
                else:
                    command = 'flashred 5000'
                    print("Webhook: Invalid commits found -> Flash red effect")
                
                # Send command to LED strip
                send_serial_command(command, self.serial_connection)
                
                # Respond immediately to GitHub
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                response_msg = f'OK: Processed {len(commits)} commits - {"rainbow" if all_valid else "flashred"}\n'
                self.wfile.write(response_msg.encode())
                return
        
        command = None

        print(path)
        # Handle different endpoints
        if path == '/rainbow':
            duration = params.get('duration', ['5000'])[0]
            command = f'rainbow {duration}'
        elif path == '/flashred':
            duration = params.get('duration', ['5000'])[0]
            command = f'flashred {duration}'
        elif path == '/flashgreen':
            duration = params.get('duration', ['5000'])[0]
            command = f'flashgreen {duration}'
        elif path == '/comet':
            duration = params.get('duration', ['5000'])[0]
            command = f'comet {duration}'
        elif path == '/twinkle':
            duration = params.get('duration', ['5000'])[0]
            command = f'twinkle {duration}'
        elif path == '/shutdown' or path == '/off':
            command = 'shutdown 0'
        elif path == '/on':
            command = 'on 0'
        elif path == '/brightness':
            brightness = params.get('brightness', ['50'])[0]
            command = f'brightness {brightness}'
        
        if command:
            print(f"Sending command: {command}")
            success, message = send_serial_command(command, self.serial_connection)
            status_code = 200 if success else 500
            
            self.send_response(status_code)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(message.encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Unknown endpoint\n')

    def _is_version_tag(self, ref):
        """Check if the ref is a version tag (e.g., v1.0.0, v2.1.3, 1.0.0)"""
        import re
        # Match tags like v1.0.0, v2.1.3-beta, 1.0.0, etc.
        version_pattern = r'^v?\d+\.\d+\.\d+.*$'
        return bool(re.match(version_pattern, ref))
    
    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")

if __name__ == '__main__':
    print("Starting BlinkenLichten HTTP to Serial bridge...")
    print(f"Listening on port: {PORT}")
    print(f"Serial device: {SERIAL_DEVICE}")
    print(f"Web interface: http://0.0.0.0:{PORT}/")
    if WEBHOOK_SECRET:
        print(f"GitHub webhook secret: configured (length={len(WEBHOOK_SECRET)})")
    else:
        print("GitHub webhook secret: NOT configured (set WEBHOOK_SECRET env var)")
    print("\nEndpoints:")
    print("  GET  /rainbow?duration=<ms> - Trigger rainbow effect (default 5000ms)")
    print("  POST /rainbow?duration=<ms> - Trigger rainbow effect (default 5000ms)")
    print("  POST /flashred?duration=<ms> - Trigger flash red effect (default 5000ms)")
    print("  POST /comet?duration=<ms> - Trigger comet effect (default 5000ms)")
    print("  POST /twinkle?duration=<ms> - Trigger twinkle effect (default 5000ms)")
    print("  POST /on - Turn lights on")
    print("  POST /off - Turn lights off")
    print("  POST /shutdown - Turn lights off")
    print("  POST /brightness?brightness=<0-100> - Set brightness")
    print("  POST /webhook - GitHub webhook (validates signature, checks conventional commits)")
    print("  GET  /webhook?payload=<json> - Test webhook with provided JSON payload (no signature validation)")

    with serial.Serial(SERIAL_DEVICE, SERIAL_BAUDRATE, timeout=None) as ser: # pyright: ignore
        SerialHandler.serial_connection = ser # pyright: ignore
        server = HTTPServer(('0.0.0.0', PORT), SerialHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")
            server.shutdown()
