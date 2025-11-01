#include <FastLED.h>
#include "CRGBW-final.h"
#include <ESPmDNS.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Arduino.h>
#include <WebServer.h>

// ================= FORWARD DECLARATIONS =================
void setupWiFi();
void setupSerial();
void setupMDNS();
void setupFastLED();
void handleSetBrightness();
void handleShutdown();
void handleRainbow();
void setupWebServer();
void showAll(CRGB color);
void rainbowSnakeEffect(int duration_ms);
void setWarmWhite(int brightness);
// ========================================================

// ================= USER CONFIG =================
#define NUM_LEDS   300      // Set to your strip length
#define DATA_PIN   13      // Set to your data pin
#define COLOR_DELAY 10    // ms per color
// ===============================================


// Standard FastLED CRGB array
CRGB leds[NUM_LEDS];

// Set up the RGBW emulation (change W3 to W2 for RGBW order if needed)
Rgbw rgbw = Rgbw(
    kRGBWDefaultColorTemp,
    kRGBWExactColors,      // Mode: exact color matching
    W3                     // W placement: W3=GRBW, W2=RGBW
);

typedef SK6812<DATA_PIN, RGB> ControllerT;
static RGBWEmulatedController<ControllerT, GRB> rgbwEmu(rgbw);

// WiFi credentials
const char* ap_ssid = "Cumulus"; 
const char* ap_password = "";

// Web server on port 80
WebServer server(80);

// Flag to control the main loop
volatile bool shouldRunEffect = false;
volatile int effectType = 0; // 0: none, 1: rainbow

// Setup WiFi Access Point
void setupWiFi() {  
  Serial.print("Connecting to WiFi Access Point: ");
  Serial.println(ap_ssid);
  
  WiFi.begin(ap_ssid, ap_password);
    
  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }

  Serial.println();
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
  Serial.printf("Connect to: %s\n", ap_ssid);
  Serial.printf("Password: %s\n", ap_password);
}


void setupSerial(){
  Serial.begin(115200);
  while (!Serial) {
    ; // Wait for serial port to connect. Needed for native USB
  }
}

// Setup mDNS service discovery
void setupMDNS() {
  // Initialize mDNS
  if (!MDNS.begin("osc-to-midi")) {
    Serial.println("Error starting mDNS");
    return;
  }
  Serial.println("mDNS responder started");
  
  // Add OSC UDP service to mDNS-SD
  MDNS.addService("http", "tcp", 80);
  Serial.println("mDNS service registered: osc-to-midi._osc._udp.local on port 8888");
}

void setupFastLED() {
  FastLED.addLeds(&rgbwEmu, leds, NUM_LEDS);
  FastLED.setBrightness(128); // Set initial brightness (0-255)
}

// HTTP POST handler for warm white brightness control
void handleSetBrightness() {
  if (server.hasArg("brightness")) {
    int brightness = server.arg("brightness").toInt();
    setWarmWhite(brightness);
    server.send(200, "application/json", "{\"status\":\"ok\",\"brightness\":" + String(brightness) + "}");
    Serial.printf("Set warm white brightness to: %d\n", brightness);
  } else {
    server.send(400, "application/json", "{\"error\":\"Missing brightness parameter\"}");
  }
}

// HTTP POST handler for shutdown (all lights off)
void handleShutdown() {
  showAll(CRGB::Black);
  server.send(200, "application/json", "{\"status\":\"ok\",\"message\":\"Lights turned off\"}");
  Serial.println("Lights shutdown");
}

// HTTP POST handler for rainbow effect
void handleRainbow() {
  int duration = 5000; // Default 5000ms
  if (server.hasArg("duration")) {
    duration = server.arg("duration").toInt();
  }
  rainbowSnakeEffect(duration);
  server.send(200, "application/json", "{\"status\":\"ok\",\"duration\":" + String(duration) + "}");
  Serial.printf("Rainbow effect triggered for %d ms\n", duration);
}

// Setup web server routes
void setupWebServer() {
  server.on("/brightness", HTTP_POST, handleSetBrightness);
  server.on("/shutdown", HTTP_POST, handleShutdown);
  server.on("/rainbow", HTTP_POST, handleRainbow);
  server.begin();
  Serial.println("Web server started");
}

void setup() {
  setupSerial();
  setupWiFi();
  setupMDNS();
  setupFastLED();
  setupWebServer();
  delay(100);
}

void showAll(CRGB color) {
  fill_solid(leds, NUM_LEDS, color);
  FastLED.show();
  delay(50);
  fill_solid(leds, NUM_LEDS, color);
  FastLED.show();
  FastLED.clear();
  delay(10);
}


// 5 second rainbow snake effect when triggered
void rainbowSnakeEffect(int duration_ms) {
  unsigned long startTime = millis();
  while (millis() - startTime < duration_ms) {
    for (int i = 0; i < NUM_LEDS; i++) {
      leds[i] = CHSV((i * 256 / NUM_LEDS + (millis() / 10)) % 256, 255, 255);
    }
    FastLED.show();
    delay(200);
  }
  showAll(CRGB::Black);
}

// set warm white color for the rbgw leds
void setWarmWhite(int brightness) {
  int clampBrightness = constrain(brightness, 0, 100);
  int whiteValue = map(clampBrightness, 0, 100, 0, 255);
  if (whiteValue < 10) {
    showAll(CRGB::Black); // Turn off LEDs
    return; // Avoid very low brightness
  }
  //else 
  for (int i = 0; i < NUM_LEDS; i++) {
    leds[i] = CRGB::White;
    //set brightness or the led
    leds[i].fadeToBlackBy(255 - whiteValue);
  }
  FastLED.show();
}

void loop() {
  server.handleClient();
  delay(10); // Small delay to prevent blocking
}
