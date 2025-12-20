"""
WLED JSON API wrapper for BlinkenLichten.

Provides simple HTTP-based control of WLED devices via their JSON API.
Documentation: https://kno.wled.ge/interfaces/json-api/
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional


class WLEDError(Exception):
    """Base exception for WLED API errors."""
    pass


class WLEDController:
    """Controller for WLED device via JSON API."""

    def __init__(self, endpoint: Optional[str] = None):
        """
        Initialize WLED controller.

        Args:
            endpoint: WLED endpoint URL (e.g., "http://wled.local")
                     If None, reads from WLED_ENDPOINT env var or defaults to "http://wled.local"
        """
        self.endpoint = endpoint or os.environ.get('WLED_ENDPOINT', 'http://wled.local')
        # Ensure no trailing slash
        self.endpoint = self.endpoint.rstrip('/')
        self.api_url = f"{self.endpoint}/json/state"

    def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send JSON payload to WLED API.

        Args:
            payload: Dictionary to send as JSON

        Returns:
            Response from WLED as dictionary

        Raises:
            WLEDError: On network or API errors
        """
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.api_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=5.0) as response:
                return json.loads(response.read().decode('utf-8'))

        except urllib.error.URLError as e:
            raise WLEDError(f"Failed to connect to WLED at {self.endpoint}: {e}")
        except json.JSONDecodeError as e:
            raise WLEDError(f"Invalid JSON response from WLED: {e}")
        except Exception as e:
            raise WLEDError(f"Unexpected error communicating with WLED: {e}")

    def set_brightness(self, brightness: int) -> None:
        """
        Set brightness using W channel of RGBW with solid color effect.

        Args:
            brightness: 0-100 percentage
        """
        # Convert 0-100 to 0-255 for WLED
        wled_brightness = int((brightness / 100.0) * 255)

        payload = {
            "on": True,
            "seg": [{
                "fx": 0,  # Solid color effect
                "col": [[0, 0, 0, wled_brightness]]  # RGBW with only W channel
            }]
        }
        self._send_request(payload)
        print(f"WLED: Set brightness to {brightness}% (W={wled_brightness})")

    def _set_effect(self, effect_id: int, effect_name: str, color_rgb: Optional[tuple] = None) -> None:
        """
        Set a WLED effect with optional color.

        Args:
            effect_id: WLED effect ID
            effect_name: Human-readable effect name for logging
            duration_ms: Duration in milliseconds (for logging only, handled by caller)
            color_rgb: Optional tuple of (R, G, B) values (0-255)
        """
        segment: Dict[str, Any] = {"fx": effect_id}
        if color_rgb is not None:
            r, g, b = color_rgb
            segment["col"] = [[r, g, b, 0]]  # RGB color with W=0

        payload = {"on": True, "seg": [segment]}
        self._send_request(payload)

        if color_rgb is not None:
            r, g, b = color_rgb
            print(f"WLED: {effect_name} effect with color RGB({r}, {g}, {b})")
        else:
            print(f"WLED: {effect_name} effect")

    def set_effect_breathe(self, color_rgb: tuple) -> None:
        """
        Trigger Breathe effect (ID 2) with specified color.

        Args:
            color_rgb: Tuple of (R, G, B) values (0-255)
            duration_ms: Duration in milliseconds (for logging only, handled by caller)
        """
        self._set_effect(effect_id=2, effect_name="Breathe", color_rgb=color_rgb)

    def set_effect_rainbow(self) -> None:
        """
        Trigger Rainbow effect (ID 9).        
        """
        self._set_effect(effect_id=9, effect_name="Rainbow")

    def turn_on(self, brightness: Optional[int] = None) -> None:
        """
        Turn on LEDs.

        Args:
            brightness: Optional brightness 0-100. If provided, sets W channel brightness.
        """
        if brightness is not None:
            self.set_brightness(brightness)
        else:
            payload = {"on": True}
            self._send_request(payload)
            print("WLED: Turned on")

    def turn_off(self) -> None:
        """Turn off all LEDs."""
        payload = {"on": False}
        self._send_request(payload)
        print("WLED: Turned off")


if __name__ == "__main__":
    import time

    DELAY = 5  # seconds between each test

    print("=== WLED Controller Test ===\n")
    wled = WLEDController(endpoint="http://192.168.88.216")
    print(f"Testing WLED at: {wled.endpoint}\n")

    try:
        print("1. Turn on")
        wled.turn_on()
        time.sleep(DELAY)

        print("\n2. Set brightness to 50%")
        wled.set_brightness(50)
        time.sleep(DELAY)

        print("\n3. Set brightness to 100%")
        wled.set_brightness(100)
        time.sleep(DELAY)

        print("\n4. Breathe effect (red)")
        wled.set_effect_breathe((255, 0, 0))
        time.sleep(DELAY)

        print("\n5. Breathe effect (blue)")
        wled.set_effect_breathe((0, 0, 255))
        time.sleep(DELAY)

        print("\n6. Rainbow effect")
        wled.set_effect_rainbow()
        time.sleep(DELAY)

        print("\n7. Turn off")
        wled.turn_off()

        print("\n=== Test complete ===")

    except WLEDError as e:
        print(f"\nError: {e}")
