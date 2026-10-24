#include <Stepper.h>
#include <U8g2lib.h>
#include <Wire.h>

// ============================================
// WATERSENSE AI - ARDUINO UNO R3 DEMO
// ============================================

// -------- STATION IDENTITY --------
// Must exactly match the station_code already registered on the backend.
const char* STATION_CODE = "WS-PROTOTYPE-01";

// -------- PIN CONFIGURATION --------
const int LEVEL_PIN = A0;        // Potentiometer: simulated tank level
const int WATER_SENSOR_PIN = A1; // Water contact sensor
const int PIR_PIN = 2;           // PIR motion sensor
// OLED: SDA -> A4, SCL -> A5 (hardware I2C), address 0x3C

const int MOTOR_IN1 = 4;
const int MOTOR_IN2 = 5;
const int MOTOR_IN3 = 6;
const int MOTOR_IN4 = 7;

const int GREEN_LED = 8;
const int YELLOW_LED = 9;
const int RED_LED = 10;

// -------- OLED DISPLAY --------
// 128x64 SSD1306 in page-buffer mode (128 bytes of RAM instead of 1 KB, which
// the Uno can't spare). If the image looks shifted with a stripe of noise down
// one edge, the module is an SH1106: swap SSD1306 for SH1106 in this line.
U8G2_SSD1306_128X64_NONAME_1_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE);

// -------- TANK --------
// Shown on the OLED only. Keep in sync with the station's capacity and the
// backend's rated pump flow (PUMP_FLOW_LPM) so both screens agree.
const long TANK_CAPACITY_L = 5000;
const float PUMP_FLOW_LPM = 20.0;

// -------- WATER LEVEL SETTINGS --------
// Analog readings range from 0 to 1023. These drive the LEDs only.
const int LOW_LEVEL_THRESHOLD = 341;
const int MEDIUM_LEVEL_THRESHOLD = 682;

// -------- AUTOMATIC PUMP CONTROL --------
// Hysteresis: the pump starts when the tank drops to PUMP_START_PERCENT and
// keeps running until it refills to PUMP_STOP_PERCENT, like a float switch.
// The backend mirrors these values, so change both together.
const int PUMP_START_PERCENT = 20;
const int PUMP_STOP_PERCENT = 85;

// -------- MOTOR SETTINGS --------
const int STEPS_PER_REVOLUTION = 2048;
Stepper pumpMotor(
  STEPS_PER_REVOLUTION,
  MOTOR_IN1, MOTOR_IN3, MOTOR_IN2, MOTOR_IN4
);

const int MOTOR_SPEED_RPM = 12;
// Small step chunks keep the motor turning continuously while the loop still
// reads sensors and reports every SENSOR_INTERVAL_MS.
const int STEPS_PER_CHUNK = 16;

// -------- SENSOR SETTINGS --------
// Calibrate after comparing dry and wet readings in the Serial Monitor.
const int WATER_WET_THRESHOLD = 100;

const unsigned long SENSOR_INTERVAL_MS = 500;
const unsigned long PIR_WARMUP_MS = 30000;
const unsigned long FULL_BANNER_MS = 4000;

// The potentiometer's ADC value jitters a few counts, which flips the percent
// between neighbours (74/75/74...). Average several samples and only move the
// reported level when the raw value has really changed.
const int LEVEL_SAMPLES = 16;
const int LEVEL_DEADBAND_RAW = 6;

// -------- GLOBAL VARIABLES --------
int rawLevel = 0;
int lastLevelRaw = -1000;
int waterSensorValue = 0;
int levelPercent = 0;

bool motionDetected = false;
bool waterDetected = false;

bool pumpOn = false;
unsigned long pumpRunMs = 0;   // total motor run time since boot
unsigned long fullBannerUntil = 0;

unsigned long lastSensorRead = 0;
unsigned long bootTime = 0;
byte frame = 0;                // animation tick, advances every redraw

enum WaterLevel {
  LEVEL_LOW,
  LEVEL_MEDIUM,
  LEVEL_HIGH
};

WaterLevel currentLevel = LEVEL_LOW;

// ============================================
// SETUP
// ============================================
void setup() {
  Serial.begin(9600);

  pinMode(PIR_PIN, INPUT);

  pinMode(GREEN_LED, OUTPUT);
  pinMode(YELLOW_LED, OUTPUT);
  pinMode(RED_LED, OUTPUT);

  pinMode(MOTOR_IN1, OUTPUT);
  pinMode(MOTOR_IN2, OUTPUT);
  pinMode(MOTOR_IN3, OUTPUT);
  pinMode(MOTOR_IN4, OUTPUT);

  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);

  pumpMotor.setSpeed(MOTOR_SPEED_RPM);
  releaseMotor();

  oled.begin();
  oled.setBusClock(400000);  // fast I2C so redraws barely pause the motor
  drawSplash();

  bootTime = millis();

  Serial.println();
  Serial.println(F("================================"));
  Serial.println(F("       WATERSENSE AI DEMO"));
  Serial.println(F("================================"));
  Serial.println(F("Starting sensors and pump..."));
  Serial.println(F("PIR sensor warming up for 30 seconds."));
  Serial.println();

  delay(1500);  // let the splash screen be seen
}

// ============================================
// MAIN LOOP
// ============================================
void loop() {
  unsigned long now = millis();

  if (now - lastSensorRead >= SENSOR_INTERVAL_MS) {
    lastSensorRead = now;
    readSensors();
    updateWaterLevel();
    updatePump();
    updateIndicators();
    printStatus();
    sendTelemetryJSON();
    drawScreen();
  }

  if (pumpOn) {
    unsigned long started = millis();
    pumpMotor.step(STEPS_PER_CHUNK);
    pumpRunMs += millis() - started;
  }
}

// ============================================
// READ SENSORS
// ============================================
void readSensors() {
  long sum = 0;
  for (int i = 0; i < LEVEL_SAMPLES; i++) {
    sum += analogRead(LEVEL_PIN);
  }
  rawLevel = sum / LEVEL_SAMPLES;
  waterSensorValue = analogRead(WATER_SENSOR_PIN);

  // Always track the true ends of the range so 0% and 100% are reachable.
  if (abs(rawLevel - lastLevelRaw) >= LEVEL_DEADBAND_RAW || rawLevel <= 2 || rawLevel >= 1021) {
    lastLevelRaw = rawLevel;
    levelPercent = map(rawLevel, 0, 1023, 0, 100);
    levelPercent = constrain(levelPercent, 0, 100);
  }

  motionDetected = digitalRead(PIR_PIN) == HIGH;

  // This is an initial threshold, not a calibrated value.
  waterDetected = waterSensorValue > WATER_WET_THRESHOLD;
}

// ============================================
// CLASSIFY SIMULATED WATER LEVEL
// ============================================
void updateWaterLevel() {
  if (rawLevel < LOW_LEVEL_THRESHOLD) {
    currentLevel = LEVEL_LOW;
  }
  else if (rawLevel < MEDIUM_LEVEL_THRESHOLD) {
    currentLevel = LEVEL_MEDIUM;
  }
  else {
    currentLevel = LEVEL_HIGH;
  }
}

// ============================================
// AUTOMATIC PUMP CONTROL
// ============================================
void updatePump() {
  if (!pumpOn && levelPercent <= PUMP_START_PERCENT) {
    pumpOn = true;
    Serial.println(F("PUMP: ON - tank low, refilling."));
  }
  else if (pumpOn && levelPercent >= PUMP_STOP_PERCENT) {
    pumpOn = false;
    releaseMotor();
    fullBannerUntil = millis() + FULL_BANNER_MS;
    Serial.println(F("PUMP: OFF - tank full."));
  }
}

// De-energise the coils so the stepper doesn't heat up while idle.
void releaseMotor() {
  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, LOW);
  digitalWrite(MOTOR_IN3, LOW);
  digitalWrite(MOTOR_IN4, LOW);
}

// ============================================
// LEDS
// ============================================
void updateIndicators() {
  digitalWrite(GREEN_LED, currentLevel == LEVEL_HIGH ? HIGH : LOW);
  digitalWrite(YELLOW_LED, currentLevel == LEVEL_MEDIUM ? HIGH : LOW);
  digitalWrite(RED_LED, currentLevel == LEVEL_LOW ? HIGH : LOW);
}

// ============================================
// OLED SCREENS
// ============================================
void drawWaterDrop(int cx, int top, int r) {
  // Teardrop: a circle with a triangle point on top.
  oled.drawDisc(cx, top + r * 2, r);
  oled.drawTriangle(cx - r + 1, top + r * 2 - 1, cx + r - 1, top + r * 2 - 1, cx, top);
}

void drawSplash() {
  oled.firstPage();
  do {
    drawWaterDrop(64, 4, 7);
    oled.setFont(u8g2_font_helvB10_tr);
    oled.drawStr(64 - oled.getStrWidth("WATERSENSE AI") / 2, 44, "WATERSENSE AI");
    oled.setFont(u8g2_font_5x8_tr);
    oled.drawStr(64 - oled.getStrWidth("Smart pump controller") / 2, 58, "Smart pump controller");
  } while (oled.nextPage());
}

// Tank graphic: outline, water fill with a surface wave, start/stop marks,
// and a falling drop while the pump is filling it.
void drawTank(int x, int y, int w, int h) {
  oled.drawRFrame(x, y, w, h, 3);
  int inner = h - 4;
  int fill = (long)inner * levelPercent / 100;
  int surface = y + 2 + inner - fill;
  if (fill > 0) {
    oled.drawBox(x + 2, surface, w - 4, fill);
    if (fill > 2) {
      // Ripple the surface so the tank looks alive.
      for (int i = 0; i < w - 4; i += 4) {
        int dip = ((i / 4 + frame) % 2 == 0) ? 1 : 0;
        oled.setDrawColor(0);
        oled.drawPixel(x + 2 + i + 1, surface + dip);
        oled.drawPixel(x + 2 + i + 2, surface + dip);
        oled.setDrawColor(1);
      }
    }
  }
  // Start / stop marks on the right edge of the tank.
  int startY = y + 2 + inner - (long)inner * PUMP_START_PERCENT / 100;
  int stopY = y + 2 + inner - (long)inner * PUMP_STOP_PERCENT / 100;
  oled.drawHLine(x + w, startY, 3);
  oled.drawHLine(x + w, stopY, 3);

  if (pumpOn) {
    // Inflow: a drop that falls from the inlet toward the water surface.
    int span = max(1, surface - (y + 4));
    int dropY = y + 3 + (frame * 5) % span;
    oled.setDrawColor(2);  // XOR so it shows over water or air
    oled.drawBox(x + w / 2 - 1, dropY, 2, 3);
    oled.setDrawColor(1);
  }
}

void drawScreen() {
  frame++;
  bool blink = frame % 2 == 0;
  bool showFull = millis() < fullBannerUntil;
  long liters = (long)levelPercent * TANK_CAPACITY_L / 100;
  float pumpedL = pumpRunMs / 60000.0 * PUMP_FLOW_LPM;
  char buf[24];

  oled.firstPage();
  do {
    // Header: brand on the left, pump state pill on the right.
    oled.setFont(u8g2_font_5x8_tr);
    oled.drawStr(0, 7, "WATERSENSE");
    if (pumpOn) {
      oled.drawRBox(80, 0, 48, 10, 2);
      oled.setDrawColor(0);
      oled.drawStr(85, 8, "PUMP ON");
      oled.drawDisc(122, 4, blink ? 2 : 1);
      oled.setDrawColor(1);
    } else {
      oled.drawRFrame(80, 0, 48, 10, 2);
      oled.drawStr(85, 8, "PUMP OFF");
    }
    oled.drawHLine(0, 12, 128);

    drawTank(2, 15, 26, 48);

    // Big level reading.
    oled.setFont(u8g2_font_logisoso24_tn);
    itoa(levelPercent, buf, 10);
    int numW = oled.getStrWidth(buf);
    int numX = 40;
    oled.drawStr(numX, 42, buf);
    oled.setFont(u8g2_font_helvB10_tr);
    oled.drawStr(numX + numW + 2, 42, "%");

    // Liters in the tank.
    oled.setFont(u8g2_font_6x10_tf);
    snprintf(buf, sizeof(buf), "%ld L in tank", liters);
    oled.drawStr(40, 53, buf);

    // Status line: the most important thing right now.
    if (waterDetected) {
      if (blink) {
        oled.drawBox(38, 55, 90, 9);
        oled.setDrawColor(0);
      }
      oled.drawStr(41, 63, "! LEAK AT BASE");
      oled.setDrawColor(1);
    } else if (showFull) {
      oled.drawBox(38, 55, 90, 9);
      oled.setDrawColor(0);
      oled.drawStr(48, 63, "TANK FULL");
      oled.setDrawColor(1);
    } else if (pumpOn) {
      dtostrf(pumpedL, 0, 1, buf);
      strcat(buf, " L pumped");
      oled.drawStr(40, 63, buf);
    } else if (levelPercent >= PUMP_STOP_PERCENT) {
      oled.drawStr(40, 63, "Full - standby");
    } else {
      snprintf(buf, sizeof(buf), "Auto at %d%%", PUMP_START_PERCENT);
      oled.drawStr(40, 63, buf);
    }
  } while (oled.nextPage());
}

// ============================================
// SERIAL MONITOR STATUS
// ============================================
void printStatus() {
  Serial.print(F("Level ADC: "));
  Serial.print(rawLevel);

  Serial.print(F(" | Level: "));
  Serial.print(levelPercent);
  Serial.print(F("%"));

  Serial.print(F(" | Status: "));
  if (currentLevel == LEVEL_LOW) {
    Serial.print(F("LOW"));
  }
  else if (currentLevel == LEVEL_MEDIUM) {
    Serial.print(F("MEDIUM"));
  }
  else {
    Serial.print(F("HIGH"));
  }

  Serial.print(F(" | Pump: "));
  Serial.print(pumpOn ? "ON" : "OFF");

  Serial.print(F(" | Water sensor ADC: "));
  Serial.print(waterSensorValue);

  Serial.print(F(" | Water contact: "));
  Serial.print(waterDetected ? "DETECTED" : "NOT DETECTED");

  Serial.print(F(" | Motion: "));
  Serial.println(motionDetected ? "DETECTED" : "NONE");
}

// ============================================
// JSON LINE FOR scripts/arduino_serial_bridge.py
// One self-contained JSON object per line. The bridge parses each line
// independently, so this must stay on its own println-terminated line.
// ============================================
void sendTelemetryJSON() {
  Serial.print(F("{\"station_code\":\""));
  Serial.print(STATION_CODE);
  Serial.print(F("\",\"water_level_percent\":"));
  Serial.print(levelPercent);
  Serial.print(F(",\"level_raw\":"));
  Serial.print(rawLevel);
  Serial.print(F(",\"pump_on\":"));
  Serial.print(pumpOn ? "true" : "false");
  Serial.print(F(",\"pump_run_ms\":"));
  Serial.print(pumpRunMs);
  Serial.print(F(",\"water_contact\":"));
  Serial.print(waterDetected ? "true" : "false");
  // The PIR reads garbage while warming up, so leave motion out until then.
  if (millis() - bootTime >= PIR_WARMUP_MS) {
    Serial.print(F(",\"motion\":"));
    Serial.print(motionDetected ? "true" : "false");
  }
  Serial.println(F("}"));
}
