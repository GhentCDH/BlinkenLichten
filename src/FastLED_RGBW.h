#ifndef FastLED_RGBW_h
#define FastLED_RGBW_h

#include <FastLED.h>

// CRGB-compatible container that adds a dedicated white channel per pixel.
// The layout intentionally mirrors CRGB so we can reuse FastLED's controllers.
struct CRGBW {
    union {
        struct {
            union {
                uint8_t g;
                uint8_t green;
            };
            union {
                uint8_t r;
                uint8_t red;
            };
            union {
                uint8_t b;
                uint8_t blue;
            };
            union {
                uint8_t w;
                uint8_t white;
            };
        };
        uint8_t raw[4];
    };

    CRGBW() = default;

    CRGBW(uint8_t rd, uint8_t grn, uint8_t blu, uint8_t wht) {
        r = rd;
        g = grn;
        b = blu;
        w = wht;
    }

    // Convenience ctor: derive white channel while preserving hue.
    CRGBW(uint8_t rd, uint8_t grn, uint8_t blu) {
        uint8_t minComponent = rd;
        if (grn < minComponent) {
            minComponent = grn;
        }
        if (blu < minComponent) {
            minComponent = blu;
        }

        w = minComponent;
        r = rd - minComponent;
        g = grn - minComponent;
        b = blu - minComponent;
    }

    inline CRGBW &operator=(const CRGB &rhs) __attribute__((always_inline)) {
        r = rhs.r;
        g = rhs.g;
        b = rhs.b;
        w = 0;
        return *this;
    }

    inline CRGBW &operator=(const CHSV &rhs) __attribute__((always_inline)) {
        CRGB rgb;
        rgb = rhs;
        *this = rgb;
        return *this;
    }

    inline operator CRGB() const __attribute__((always_inline)) {
        return CRGB(r, g, b);
    }
};

// Translate an RGBW LED count into the CRGB-sized buffer FastLED expects.
inline uint16_t getRGBWsize(uint16_t ledCount) {
    uint32_t totalBytes = static_cast<uint32_t>(ledCount) * 4u;
    uint16_t rgbSlots = totalBytes / 3u;
    if ((totalBytes % 3u) != 0u) {
        ++rgbSlots;
    }
    return rgbSlots;
}

// Helper versions of fill_solid and nscale8 that respect the extra channel.
inline void fill_solid(CRGBW *leds, int numToFill, const CRGBW &color) {
    for (int i = 0; i < numToFill; ++i) {
        leds[i] = color;
    }
}

inline void fadeToBlackBy(CRGBW *leds, int numLeds, uint8_t fadeBy) {
    for (int i = 0; i < numLeds; ++i) {
        leds[i].r = scale8(leds[i].r, 255 - fadeBy);
        leds[i].g = scale8(leds[i].g, 255 - fadeBy);
        leds[i].b = scale8(leds[i].b, 255 - fadeBy);
        leds[i].w = scale8(leds[i].w, 255 - fadeBy);
    }
}

#endif
