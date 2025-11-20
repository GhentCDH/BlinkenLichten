"""
Simple HTTP server that sends serial commands on incoming requests.
Usage: python3 http_serial.py [port] [serial_device]
"""

import sys
import os
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import github_webhook
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
            # Accept webhook payload via GET for testing purposes (no signature validation)
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

            # Process webhook using the github_webhook module
            # For GET testing, we assume it's a push event and skip signature validation
            result = github_webhook.process_webhook(
                raw_body=payload_body,
                signature_header='',  # No signature for GET testing
                event_type='push',
                content_type='application/json',
                webhook_secret=None  # Skip signature validation for testing
            )

            # Send command if an effect should be triggered
            if result['effect']:
                command = f"{result['effect']} {result['duration']}"
                print(f"Webhook (GET): {result['message']} -> {result['effect']}")
                send_serial_command(command, self.serial_connection)

            # Respond
            self.send_response(result['status_code'])
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            resp = {
                'status': result['status'],
                'message': result['message'],
                'effect': result['effect'],
                'details': result['details']
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

            # Get headers
            signature_header = self.headers.get('X-Hub-Signature-256', '')
            event_type = self.headers.get('X-GitHub-Event', '')
            content_type = self.headers.get('Content-Type', '')

            # Process webhook using the github_webhook module
            result = github_webhook.process_webhook(
                raw_body=raw_body,
                signature_header=signature_header,
                event_type=event_type,
                content_type=content_type,
                webhook_secret=WEBHOOK_SECRET if WEBHOOK_SECRET else None
            )

            # Log the result
            print(f"Webhook ({event_type}): {result['message']}")
            if result['status'] == 'error':
                print(f"  Error details: {result['details']}")
            elif result['effect']:
                print(f"  Effect: {result['effect']} for {result['duration']}ms")
                if 'validation' in result['details']:
                    validation = result['details']['validation']
                    if validation.get('errors'):
                        print(f"  Validation errors:")
                        for error in validation['errors']:
                            print(f"    - {error['commit_id']}: {error['error']}")

            # Send command to LED strip if an effect was determined
            if result['effect']:
                command = f"{result['effect']} {result['duration']}"
                send_serial_command(command, self.serial_connection)

            # Respond to GitHub
            self.send_response(result['status_code'])
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                'status': result['status'],
                'message': result['message'],
                'effect': result['effect']
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
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
            duration = params.get('duration', ['10000'])[0]
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
