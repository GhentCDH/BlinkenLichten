#include <FastLED.h>
#include "CRGBW-final.h"
#include <Arduino.h>
#include <EEPROM.h>

// ================= FORWARD DECLARATIONS =================
void setupSerial();
void setupFastLED();
void handleSerialCommand();
void processCommand(String commandBuffer);
void showAll(CRGB color);
void setWarmWhite(int brightness);
void saveToEeprom(int brightness);
int loadFromEeprom();
void rainbowSnakeEffect(int duration_ms);
void flashRedEffect(int duration_ms);
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

// EEPROM configuration
#define EEPROM_SIZE 32
#define BRIGHTNESS_ADDR 0


void setupSerial(){
  Serial.begin(115200);
  while (!Serial) {
    ; // Wait for serial port to connect. Needed for native USB
  }
  Serial.println("BlinkenLichten Initialized");

  Serial.println("Available commands:");
  Serial.println("  brightness <0-100>  - Set brightness level");
  Serial.println("  rainbow <duration_ms> - Start rainbow effect for specified duration");
  Serial.println("  shutdown 0          - Turn off the lights");
  Serial.println("  on       0           - Turn lights back on to previous brightness"); 
}

// Save brightness to EEPROM
void saveToEeprom(int brightness) {
  brightness = constrain(brightness, 0, 100);
  EEPROM.write(BRIGHTNESS_ADDR, brightness);
  EEPROM.commit();
}

// Load brightness from EEPROM
int loadFromEeprom() {
  int brightness = EEPROM.read(BRIGHTNESS_ADDR);
  if (brightness < 0 || brightness > 100) {
    brightness = 50; // Default brightness
  }
  Serial.printf("Brightness loaded from EEPROM: %d\n", brightness);
  return brightness;
}

void setupFastLED() {
  FastLED.addLeds(&rgbwEmu, leds, NUM_LEDS);
  FastLED.setBrightness(128); // Set initial brightness (0-255)
}

// Parse command and value
void processCommand(String commandBuffer) {
  commandBuffer.trim();
  
  // Parse command and value
  int spaceIndex = commandBuffer.indexOf(' ');
  if (spaceIndex > 0) {
    String command = commandBuffer.substring(0, spaceIndex);
    String valueStr = commandBuffer.substring(spaceIndex + 1);
    valueStr.trim(); // Remove leading/trailing spaces
    int value = valueStr.toInt();
    // Process commands
    if (command == "brightness") {
      setWarmWhite(value);
      saveToEeprom(value); // Save brightness to EEPROM
      Serial.printf("Brightness set to: %d\n", value);
    } else if (command == "rainbow") {
      int duration = value == 0 ? 5000 : value ;
      rainbowSnakeEffect(duration);
      Serial.printf("Rainbow effect for %d ms\n", duration);
      setWarmWhite(loadFromEeprom());
    } else if (command == "flashred") {
      int duration = value == 0 ? 5000 : value ;
      flashRedEffect(duration);
      Serial.printf("Flash red effect for %d ms\n", duration);
      setWarmWhite(loadFromEeprom());
    } else if (command == "shutdown") {
      showAll(CRGB::Black);
    } else if (command == "on") {
      value = value == 0 ? loadFromEeprom() : value ;
      setWarmWhite(value);
      Serial.printf("Turning on to brightness: %d\n", value);
    } else {
      Serial.printf("Unknown command: %s\n", command.c_str());
    }
  }
}

// Handle serial commands
void handleSerialCommand() {
  static String commandBuffer = "";
  
  // Read all available characters
  while (Serial.available()) {
    char c = Serial.read();
    
    if (c == '\n' || c == '\r') {
      // Process command when newline is received
      if (commandBuffer.length() > 0) {
        processCommand(commandBuffer);
        commandBuffer = "";
      }
    }
    else {
      // Add character to buffer
      commandBuffer += c;
    }
  }
}

void setup() {
  setupSerial();
  EEPROM.begin(EEPROM_SIZE);
  setupFastLED();

  // Load and restore previous brightness level
  int currentBrightness = loadFromEeprom();
  setWarmWhite(currentBrightness);
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


void flashRedEffect(int duration_ms) {
  unsigned long startTime = millis();
  while (millis() - startTime < duration_ms) {
    showAll(CRGB::Red);
    delay(100);
    showAll(CRGB::Black);
    delay(100);
  }
  showAll(CRGB::Black);
}

// set warm white color for the rbgw leds
void setWarmWhite(int brightness) {
  int clampBrightness = constrain(brightness, 0, 100);
  int whiteValue = map(clampBrightness, 0, 100, 0, 255);
  //else 
  for (int i = 0; i < NUM_LEDS; i++) {
    leds[i] = CRGB::White;
    //set brightness or the led
    leds[i].fadeToBlackBy(255 - whiteValue);
  }
  FastLED.show();
}

void loop() {
  handleSerialCommand(); // Read and process serial commands
  delay(1); // Small delay to prevent blocking
}

