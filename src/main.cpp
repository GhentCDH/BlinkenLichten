#include <FastLED.h>
#include "CRGBW-final.h"
#include <Arduino.h>
#include <EEPROM.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>
#include <freertos/semphr.h>

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
void flashColorEffect(int duration_ms, CRGB color);
void flashRedEffect(int duration_ms);
void flashGreenEffect(int duration_ms);
void cometEffect(int duration_ms);
void twinkleEffect(int duration_ms);
void takeLedMutex();
void giveLedMutex();
void stopEffectTask();
void startEffectTask(uint8_t effectType, int duration);
void effectTaskFunction(void* parameter);
// ========================================================

// ================= USER CONFIG =================
#define NUM_LEDS   300      // Set to your strip length
#define DATA_PIN   13      // Set to your data pin
#define COLOR_DELAY 10    // ms per color
// ===============================================


const int standard_duration_in_ms = 3000; // Default effect duration

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

// Effect type constants
#define EFFECT_RAINBOW 0
#define EFFECT_FLASHRED 1
#define EFFECT_FLASHGREEN 2
#define EFFECT_COMET 3
#define EFFECT_TWINKLE 4

// FreeRTOS task management
SemaphoreHandle_t ledMutex = NULL;
TaskHandle_t effectTaskHandle = NULL;
volatile bool stopCurrentEffect = false;

// Effect parameters struct
struct EffectParams {
  uint8_t effectType;
  int duration_ms;
};


void setupSerial(){
  Serial.begin(115200);
  while (!Serial) {
    ; // Wait for serial port to connect. Needed for native USB
  }
  Serial.println("BlinkenLichten Initialized");

  Serial.println("Available commands:");
  Serial.println("  brightness <0-100>  - Set brightness level");
  Serial.println("  getbrightness       - Get current brightness level");
  Serial.println("  rainbow <duration_ms> - Start rainbow effect for specified duration");
  Serial.println("  flashred <duration_ms> - Flash red effect for specified duration");
  Serial.println("  flashgreen <duration_ms> - Flash green effect for specified duration");
  Serial.println("  comet <duration_ms> - Bouncing comet effect for specified duration");
  Serial.println("  twinkle <duration_ms> - Twinkle/sparkle effect for specified duration");
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

// Mutex wrapper functions for LED access
void takeLedMutex() {
  if (ledMutex != NULL) {
    xSemaphoreTake(ledMutex, portMAX_DELAY);
  }
}

void giveLedMutex() {
  if (ledMutex != NULL) {
    xSemaphoreGive(ledMutex);
  }
}

// Stop the currently running effect task
void stopEffectTask() {
  if (effectTaskHandle != NULL) {
    stopCurrentEffect = true;
    // Wait for the task to finish and delete itself
    while (effectTaskHandle != NULL) {
      vTaskDelay(pdMS_TO_TICKS(10));
    }
    stopCurrentEffect = false;
  }
}

// Main effect task function - runs in separate FreeRTOS task
void effectTaskFunction(void* parameter) {
  EffectParams* params = (EffectParams*)parameter;
  uint8_t effectType = params->effectType;
  int duration = params->duration_ms;
  delete params;  // Free the allocated parameter

  Serial.printf("Effect %d started for %d ms\n", effectType, duration);

  // Run the appropriate effect
  switch (effectType) {
    case EFFECT_RAINBOW:
      rainbowSnakeEffect(duration);
      break;
    case EFFECT_FLASHRED:
      flashRedEffect(duration);
      break;
    case EFFECT_FLASHGREEN:
      flashGreenEffect(duration);
      break;
    case EFFECT_COMET:
      cometEffect(duration);
      break;
    case EFFECT_TWINKLE:
      twinkleEffect(duration);
      break;
  }

  // Effect finished - clear LEDs and restore brightness
  if (!stopCurrentEffect) {
    takeLedMutex();
    fill_solid(leds, NUM_LEDS, CRGB::Black);
    FastLED.show();
    giveLedMutex();

    setWarmWhite(loadFromEeprom());
    Serial.println("Effect completed, brightness restored");
  }

  // Clean up
  effectTaskHandle = NULL;
  vTaskDelete(NULL);
}

// Start a new effect task
void startEffectTask(uint8_t effectType, int duration) {
  // Stop any running effect first
  stopEffectTask();

  // Create parameters for the task
  EffectParams* params = new EffectParams;
  params->effectType = effectType;
  params->duration_ms = duration;

  // Create the effect task on Core 0, priority 1 (lower than main loop)
  xTaskCreatePinnedToCore(
    effectTaskFunction,    // Task function
    "EffectTask",          // Task name
    4096,                  // Stack size (bytes)
    params,                // Parameters
    1,                     // Priority
    &effectTaskHandle,     // Task handle
    0                      // Core 0
  );
}

// Parse command and value
void processCommand(String commandBuffer) {
  commandBuffer.trim();

  // Parse command and value
  int spaceIndex = commandBuffer.indexOf(' ');

  // Handle single-word commands (no value)
  if (spaceIndex == -1) {
    String command = commandBuffer;
    if (command == "getbrightness") {
      int brightness = loadFromEeprom();
      Serial.println(brightness);  // Output only the number for easy parsing
    } else {
      Serial.printf("Unknown command: %s\n", command.c_str());
    }
    return;
  }

  // Handle commands with values
  if (spaceIndex > 0) {
    String command = commandBuffer.substring(0, spaceIndex);
    String valueStr = commandBuffer.substring(spaceIndex + 1);
    valueStr.trim(); // Remove leading/trailing spaces
    int value = valueStr.toInt();
    // Process commands
    if (command == "brightness") {
      stopEffectTask();  // Stop any running effect first
      setWarmWhite(value);
      saveToEeprom(value); // Save brightness to EEPROM
      Serial.printf("Brightness set to: %d\n", value);
    } else if (command == "rainbow") {
      int duration = value == 0 ? standard_duration_in_ms : value;
      startEffectTask(EFFECT_RAINBOW, duration);
    } else if (command == "flashred") {
      int duration = value == 0 ? standard_duration_in_ms : value;
      startEffectTask(EFFECT_FLASHRED, duration);
    } else if (command == "flashgreen") {
      int duration = value == 0 ? standard_duration_in_ms : value;
      startEffectTask(EFFECT_FLASHGREEN, duration);
    } else if (command == "comet") {
      int duration = value == 0 ? standard_duration_in_ms : value;
      startEffectTask(EFFECT_COMET, duration);
    } else if (command == "twinkle") {
      int duration = value == 0 ? standard_duration_in_ms : value;
      startEffectTask(EFFECT_TWINKLE, duration);
    } else if (command == "shutdown") {
      stopEffectTask();  // Stop any running effect first
      takeLedMutex();
      showAll(CRGB::Black);
      giveLedMutex();
    } else if (command == "on") {
      stopEffectTask();  // Stop any running effect first
      value = value == 0 ? loadFromEeprom() : value;
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

  // Initialize FreeRTOS mutex for LED access
  ledMutex = xSemaphoreCreateMutex();
  if (ledMutex == NULL) {
    Serial.println("ERROR: Failed to create LED mutex!");
  } else {
    Serial.println("LED mutex initialized");
  }

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

// Rainbow snake effect - interruptible
void rainbowSnakeEffect(int duration_ms) {
  unsigned long startTime = millis();
  while (millis() - startTime < duration_ms && !stopCurrentEffect) {
    takeLedMutex();
    for (int i = 0; i < NUM_LEDS; i++) {
      leds[i] = CHSV((i * 256 / NUM_LEDS + (millis() / 10)) % 256, 255, 255);
    }
    FastLED.show();
    giveLedMutex();
    vTaskDelay(pdMS_TO_TICKS(200));
  }
}

// Generic flash effect with configurable color and sine-wave pulsation
void flashColorEffect(int duration_ms, CRGB color) {
  unsigned long startTime = millis();

  for (int i = 0; i < NUM_LEDS; i++) {
      leds[i].fadeToBlackBy(64);  // Gentle fade
  }

  while (millis() - startTime < duration_ms && !stopCurrentEffect) {
    unsigned long elapsed = millis() - startTime;

    // Calculate angle for 2 complete pulses (0 to 2*PI)
    float angle = 2.0 * PI * (float) elapsed / (float) duration_ms;
    float brightnessFactor = (sin(angle) + 1.0) / 2.0;  // Maps to 0.0→1.0→0.0

    // Scale input color by brightness
    CRGB scaledColor = color;
    scaledColor.r = (uint8_t)(color.r * brightnessFactor);
    scaledColor.g = (uint8_t)(color.g * brightnessFactor);
    scaledColor.b = (uint8_t)(color.b * brightnessFactor);

    // Update LEDs with smooth brightness
    takeLedMutex();
    fill_solid(leds, NUM_LEDS, scaledColor);
    FastLED.show();
    giveLedMutex();

    // Update more frequently for smooth animation (15ms)
    vTaskDelay(pdMS_TO_TICKS(15));
  }

  for (int i = 0; i < NUM_LEDS; i++) {
      leds[i].fadeToBlackBy(64);  // Gentle fade
  }
}

void flashRedEffect(int duration_ms) {
  flashColorEffect(duration_ms, CRGB::Red);
}

void flashGreenEffect(int duration_ms) {
  flashColorEffect(duration_ms, CRGB::Green);
}

// Comet effect - bouncing color-shifting comet with sparkly trail
void cometEffect(int duration_ms) {
  static uint8_t hue = 0;
  static int iDirection = 1;
  static int iPos = 0;
  const int cometSize = 5;
  const uint8_t fadeAmt = 128;
  const uint8_t deltaHue = 4;

  unsigned long startTime = millis();
  while (millis() - startTime < duration_ms && !stopCurrentEffect) {
    takeLedMutex();

    hue += deltaHue;
    iPos += iDirection;

    // Bounce at boundaries
    if (iPos == (NUM_LEDS - 1) || iPos == 0) {
      iDirection *= -1;
    }

    // Draw comet head
    for (int i = 0; i < cometSize; i++) {
      int idx = iPos - (i * iDirection);
      if (idx >= 0 && idx < NUM_LEDS) {
        leds[idx] = CHSV(hue, 255, 255);
      }
    }

    // Randomly fade all LEDs for sparkly trail effect
    for (int j = 0; j < NUM_LEDS; j++) {
      if (random(10) > 5) {
        leds[j].fadeToBlackBy(fadeAmt);
      }
    }

    FastLED.show();
    giveLedMutex();
    vTaskDelay(pdMS_TO_TICKS(50));
  }
}

// Twinkle effect - random sparkles with fading trails
void twinkleEffect(int duration_ms) {
  static const CRGB colors[] = {
    CRGB::Red, CRGB::Blue, CRGB::Purple,
    CRGB::Green, CRGB::Yellow, CRGB::Orange,
    CRGB::Cyan, CRGB::Magenta
  };
  const int colorCount = 8;
  const int density = 4; // 1/4 of LEDs light up per cycle

  unsigned long startTime = millis();
  while (millis() - startTime < duration_ms && !stopCurrentEffect) {
    takeLedMutex();

    // Fade all LEDs slightly for sparkle trail
    for (int i = 0; i < NUM_LEDS; i++) {
      leds[i].fadeToBlackBy(64);  // Gentle fade
    }

    // Add new sparkles
    for (int i = 0; i < NUM_LEDS / density; i++) {
      int pos = random(NUM_LEDS);
      leds[pos] = colors[random(colorCount)];
    }

    FastLED.show();
    giveLedMutex();
    vTaskDelay(pdMS_TO_TICKS(100));
  }
}

// set warm white color for the rbgw leds
void setWarmWhite(int brightness) {
  takeLedMutex();
  int clampBrightness = constrain(brightness, 0, 100);
  int whiteValue = map(clampBrightness, 0, 100, 0, 255);
  //else
  for (int i = 0; i < NUM_LEDS; i++) {
    leds[i] = CRGB::White;
    //set brightness or the led
    leds[i].fadeToBlackBy(255 - whiteValue);
  }
  FastLED.show();
  giveLedMutex();
}

void loop() {
  handleSerialCommand(); // Read and process serial commands
  vTaskDelay(pdMS_TO_TICKS(1)); // Small delay to prevent blocking
}

