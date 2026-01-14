"""
Simple HTTP server that controls WLED via JSON API on incoming requests.
Usage: python3 blinkenlichten.py [port]
"""

import sys
import os
import json
import time
import threading
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import github_webhook
import wled


logger = logging.getLogger(__name__)


# Configuration
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 55156
WLED_ENDPOINT = os.environ.get('WLED_ENDPOINT', 'http://192.168.88.216')
WEBHOOK_SECRET = os.environ.get('WEBHOOK_SECRET', '')


# In-memory brightness storage
class BrightnessStore:
    """Simple in-memory brightness persistence."""
    _brightness: int = 50  # Default 50%

    @classmethod
    def get(cls) -> int:
        return cls._brightness

    @classmethod
    def set(cls, value: int) -> None:
        cls._brightness = max(0, min(100, value))  # Clamp 0-100


class SerialHandler(BaseHTTPRequestHandler):
    wled_controller = None  # Class variable to hold WLED controller

    # Effect configuration mapping
    EFFECT_MAP = {
        'rainbow': {'default_duration': 5000, 'wled_effect': 'rainbow'},
        'flashred': {'default_duration': 5000, 'wled_effect': 'flashred'},
        'flashgreen': {'default_duration': 5000, 'wled_effect': 'flashgreen'},
        'comet': {'default_duration': 10000, 'wled_effect': 'rainbow'},  # Mapped to rainbow
        'twinkle': {'default_duration': 5000, 'wled_effect': 'rainbow'},  # Mapped to rainbow
    }

    def _trigger_effect_with_restoration(self, effect: str, duration_ms: int) -> None:
        """
        Trigger an effect and schedule restoration to default state.

        Args:
            effect: Effect name ('rainbow', 'flashred', 'flashgreen')
            duration_ms: Duration in milliseconds
        """
        # Trigger the effect
        if effect == 'rainbow':
            self.wled_controller.set_effect_rainbow()
        elif effect == 'flashred':
            self.wled_controller.set_effect_breathe((255, 0, 0))
        elif effect == 'flashgreen':
            self.wled_controller.set_effect_breathe((0, 255, 0))
        else:
            raise ValueError(f"Unknown effect: {effect}")

        # Schedule restoration in a background thread
        def restore_default():
            time.sleep(duration_ms / 1000.0)  # Convert ms to seconds
            try:
                brightness = BrightnessStore.get()
                self.wled_controller.set_brightness(brightness)
                print(f"Restored to default brightness: {brightness}")
            except wled.WLEDError as e:
                print(f"Failed to restore brightness: {e}")

        threading.Thread(target=restore_default, daemon=True).start()
    
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
        elif path == '/brightness':
            # GET /brightness - retrieve current brightness from memory
            brightness = BrightnessStore.get()
            print(f"Current brightness: {brightness}")

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'brightness': brightness}).encode())
        elif path == '/rainbow':
            # Support GET /rainbow?duration=<ms>
            duration = int(params.get('duration', ['5000'])[0])
            print(f"Triggering rainbow effect (GET): {duration}ms")

            try:
                self._trigger_effect_with_restoration('rainbow', duration)
                self.send_response(200)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f'Rainbow effect triggered for {duration}ms'.encode())
            except wled.WLEDError as e:
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f'Error: {str(e)}'.encode())
        elif path == '/webhook':
            # Accept webhook payload via GET for testing purposes (no signature validation)
            logger.info(
                "Webhook request arrived (GET test mode): client=%s path=%s",
                self.client_address[0],
                self.path,
            )
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

            # Trigger effect if determined
            if result['effect']:
                logger.info(
                    "Webhook processed (GET): status=%s effect=%s duration_ms=%s message=%s",
                    result.get('status'),
                    result.get('effect'),
                    result.get('duration'),
                    result.get('message'),
                )
                try:
                    self._trigger_effect_with_restoration(result['effect'], result['duration'])
                except wled.WLEDError as e:
                    logger.exception("WLED error while triggering effect")

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
            delivery_id = self.headers.get('X-GitHub-Delivery', '')
            signature_header = self.headers.get('X-Hub-Signature-256', '')
            event_type = self.headers.get('X-GitHub-Event', '')
            content_type = self.headers.get('Content-Type', '')

            # Read raw body (used for signature verification)
            content_length = int(self.headers.get('Content-Length', 0))
            raw_body = self.rfile.read(content_length)

            logger.info(
                "Webhook request arrived: method=POST client=%s delivery=%s event=%s content_type=%s bytes=%d signature_present=%s",
                self.client_address[0],
                delivery_id or "-",
                event_type or "-",
                content_type or "-",
                len(raw_body),
                bool(signature_header),
            )

            # Process webhook using the github_webhook module
            result = github_webhook.process_webhook(
                raw_body=raw_body,
                signature_header=signature_header,
                event_type=event_type,
                content_type=content_type,
                webhook_secret=WEBHOOK_SECRET if WEBHOOK_SECRET else None
            )

            # Log the result
            logger.info(
                "Webhook processed: delivery=%s event=%s status=%s code=%s effect=%s duration_ms=%s message=%s",
                delivery_id or "-",
                event_type or "-",
                result.get('status'),
                result.get('status_code'),
                result.get('effect'),
                result.get('duration'),
                result.get('message'),
            )
            if result['status'] == 'error':
                logger.warning("Webhook error details: %s", result.get('details'))
            elif result['effect']:
                logger.info(
                    "Webhook effect selected: effect=%s duration_ms=%s",
                    result.get('effect'),
                    result.get('duration'),
                )
                if 'validation' in result['details']:
                    validation = result['details']['validation']
                    if validation.get('errors'):
                        logger.info("Webhook validation errors: count=%d", len(validation['errors']))
                        for error in validation['errors']:
                            logger.info("  - %s: %s", error.get('commit_id'), error.get('error'))

            # Trigger effect if determined
            if result['effect']:
                try:
                    self._trigger_effect_with_restoration(result['effect'], result['duration'])
                except wled.WLEDError as e:
                    logger.exception("WLED error while triggering effect")

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
        
        # Handle different endpoints
        try:
            if path == '/effect':
                # Unified effect endpoint: POST /effect?name=<effect>&duration=<ms>
                effect_name = params.get('name', [None])[0]
                if not effect_name:
                    self.send_response(400)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'Missing required parameter: name\n')
                    return

                if effect_name not in self.EFFECT_MAP:
                    self.send_response(400)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    valid_effects = ', '.join(self.EFFECT_MAP.keys())
                    self.wfile.write(f'Invalid effect name. Valid effects: {valid_effects}\n'.encode())
                    return

                effect_config = self.EFFECT_MAP[effect_name]
                duration = int(params.get('duration', [str(effect_config['default_duration'])])[0])
                wled_effect = effect_config['wled_effect']

                self._trigger_effect_with_restoration(wled_effect, duration)
                message = f'{effect_name.capitalize()} effect triggered for {duration}ms'

            elif path == '/shutdown' or path == '/off':
                self.wled_controller.turn_off()
                message = 'LEDs turned off'

            elif path == '/on':
                brightness = BrightnessStore.get()
                self.wled_controller.turn_on(brightness)
                message = f'LEDs turned on at brightness {brightness}'

            elif path == '/brightness':
                brightness = int(params.get('brightness', ['50'])[0])
                BrightnessStore.set(brightness)
                self.wled_controller.set_brightness(brightness)
                message = f'Brightness set to {brightness}'

            else:
                self.send_response(404)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'Unknown endpoint\n')
                return

            # Success response
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(message.encode())

        except wled.WLEDError as e:
            print(f"WLED Error: {str(e)}")
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f'Error: {str(e)}'.encode())
        except ValueError as e:
            self.send_response(400)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f'Invalid parameter: {str(e)}'.encode())

    def log_message(self, format, *args):
        logger.info("%s - %s", self.address_string(), format % args)

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    print("Starting BlinkenLichten HTTP to WLED bridge...")
    print(f"Listening on port: {PORT}")
    print(f"WLED endpoint: {WLED_ENDPOINT}")
    print(f"Web interface: http://0.0.0.0:{PORT}/")
    if WEBHOOK_SECRET:
        print(f"GitHub webhook secret: configured (length={len(WEBHOOK_SECRET)})")
    else:
        print("GitHub webhook secret: NOT configured (set WEBHOOK_SECRET env var)")
    print("\nEndpoints:")
    print("  POST /effect?name=<effect>&duration=<ms> - Trigger effect (rainbow, flashred, flashgreen, comet, twinkle)")
    print("       Available effects:")
    print("         - rainbow (default 5000ms)")
    print("         - flashred (default 5000ms)")
    print("         - flashgreen (default 5000ms)")
    print("         - comet (default 10000ms)")
    print("         - twinkle (default 5000ms)")
    print("  GET  /rainbow?duration=<ms> - Trigger rainbow effect (default 5000ms)")
    print("  GET  /brightness - Get current brightness (from memory)")
    print("  POST /brightness?brightness=<0-100> - Set brightness (W channel)")
    print("  POST /on - Turn lights on")
    print("  POST /off - Turn lights off")
    print("  POST /shutdown - Turn lights off")
    print("  POST /webhook - GitHub webhook (validates signature, checks conventional commits)")
    print("  GET  /webhook?payload=<json> - Test webhook with provided JSON payload (no signature validation)")

    # Initialize WLED controller
    SerialHandler.wled_controller = wled.WLEDController(WLED_ENDPOINT)

    server = HTTPServer(('0.0.0.0', PORT), SerialHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
