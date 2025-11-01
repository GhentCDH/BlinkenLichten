#include <FastLED.h>
#include "CRGBW-final.h"
#include <ESPmDNS.h>
#include <WiFi.h>
#include <WiFiUdp.h>
#include <Arduino.h>


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
const char* ap_password = "blinkenlichten";

// Setup WiFi Access Point
void setupWiFi() {  
  Serial.print("Connecting to WiFi Access Point: ");
  Serial.println(ap_ssid);
  
  WiFi.mode(WIFI_STA);
  WiFi.begin(ap_ssid, ap_password);
    
  while (WiFi.status() != WL_CONNECTED) {
    delay(200);
    Serial.print(".");
  }

  Serial.println();
  Serial.println("WiFi Access Point created!");
  Serial.print("AP IP address: ");
  Serial.println(WiFi.softAPIP());
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

void setup() {
  setupSerial();
  setupWiFi();
  setupMDNS();
  setupFastLED();
  delay(100);
}

void showAll(CRGB color) {
  fill_solid(leds, NUM_LEDS, color);
  FastLED.show();
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

  rainbowSnakeEffect(5000); // 5 second rainbow snake effect
  showAll(CRGB::Black); // Turn off LEDs
  delay(5000);


  setWarmWhite(100); // Set warm white at half brightness
  delay(500);
  showAll(CRGB::Black); // Turn off LEDs
  delay(500);       // Hold for 5 seconds
  setWarmWhite(50); // Set warm white at half brightness
  delay(500);
  showAll(CRGB::Black); // Turn off LEDs
  delay(500);       // Hold for 5 seconds
  setWarmWhite(25); // Set warm white at quarter brightness
  delay(500);
  showAll(CRGB::Black); // Turn off LEDs
  delay(500);       // Hold for 5 seconds
  setWarmWhite(12); // Set warm white at quarter brightness
  delay(500);
  showAll(CRGB::Black); // Turn off LEDs
  delay(500);       // Hold for 5 seconds
  setWarmWhite(8); // Set warm white at quarter brightness
  delay(500);
  showAll(CRGB::Black); // Turn off LEDs
  delay(500);       // Hold for 5 seconds
}
