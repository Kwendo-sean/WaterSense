#include <Wire.h>
#include <U8g2lib.h>
#include <esp32-hal-rgb-led.h>

// Must exactly match the station_code registered on the backend.
const char* STATION_CODE = "WS-PROTOTYPE-02";

// OLED configuration
#define OLED_SDA 8
#define OLED_SCL 9

// JSN-SR04T sensor pins
#define TRIG_PIN 17
#define ECHO_PIN 18

// Final direct-wired prototype pin map.
#define WATER_SENSOR_PIN 4
#define WATER_SENSOR_POWER_PIN 5
#define FLOW_POWER_PIN 6
#define FLOW_PIN 16
#define RELAY_PIN 21
#define BUZZER_PIN 42
#define RGB_LED_PIN 48

// -------- TANK --------
// Distance from the sensor to the water surface. Measure both on the real
// container; these are placeholders. TANK_FULL_CM must stay above BLIND_ZONE_CM.
const float TANK_EMPTY_CM = 100.0;
const float TANK_FULL_CM = 25.0;

const int LOW_PERCENT = 20;
const int FULL_PERCENT = 85;

// -------- ULTRASONIC --------
// The sensor can't see anything closer than this.
const float BLIND_ZONE_CM = 20.0;
// With no echo the module holds ECHO high for about 40 ms, which reads as 686 cm.
// Anything past the rated range is that timeout, not an empty tank.
const float MAX_RANGE_CM = 450.0;
const unsigned long READ_INTERVAL_MS = 200;
// Median of the last few echoes removes the odd wild reading.
const int MEDIAN_SAMPLES = 5;
const int MAX_MISSED_ECHOES = 5;

// -------- FLOW --------
// YF-S201 datasheet figure, about 7.5 Hz per L/min. Calibrate by pumping a
// measured litre and dividing the pulse count printed on Serial.
const float PULSES_PER_LITRE = 450.0;
const unsigned long FLOW_INTERVAL_MS = 1000;

// Common two-channel SRD-05VDC-SL-C modules are low-level triggered.
// Channel 1 is kept OFF at boot. The short T test is capped at three seconds.
const bool RELAY_ACTIVE_LOW = true;
const unsigned long PUMP_TEST_MS = 3000;
const unsigned long MAX_PUMP_RUN_MS = 30000;

// Measured during the live diagnostic: dry=0, wet roughly 900-2400.
const int WATER_WET_THRESHOLD = 500;

// The status register reads 0x00, not an SSD1306's 0x03, so drive it as an SH1106.
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE, OLED_SCL, OLED_SDA);

// -------- GLOBAL VARIABLES --------
volatile uint32_t flowPulses = 0;

float samples[MEDIAN_SAMPLES];
int sampleCount = 0;
int sampleIndex = 0;
int missedEchoes = MAX_MISSED_ECHOES;

float distanceCm = -1;
int levelPercent = 0;
float flowLpm = 0;
float totalLitres = 0;
uint32_t totalPulses = 0;
int waterRaw = 0;
bool waterDetected = false;
bool pumpOn = false;
char pumpMode = 'A';
unsigned long pumpStartedAt = 0;
unsigned long pumpRunMs = 0;
unsigned long pumpTestUntil = 0;

unsigned long lastRead = 0;
unsigned long lastFlow = 0;
byte frame = 0;

void IRAM_ATTR onFlowPulse() {
  flowPulses++;
}

void setPump(bool on) {
  if (on == pumpOn) return;
  unsigned long now = millis();
  if (on) {
    pumpStartedAt = now;
  } else if (pumpOn) {
    pumpRunMs += now - pumpStartedAt;
  }
  pumpOn = on;
  digitalWrite(RELAY_PIN, RELAY_ACTIVE_LOW ? !on : on);
  Serial.println(on ? "PUMP=ON" : "PUMP=OFF");
}

void handlePumpCommand() {
  while (Serial.available()) {
    char command = Serial.read();
    if (command == 'T' || command == 't') {
      // A deliberate short hardware test; leak detection still overrides it.
      pumpMode = 'T';
      pumpTestUntil = millis() + PUMP_TEST_MS;
      if (!waterDetected) setPump(true);
    } else if (command == '1') {
      pumpMode = '1';
    } else if (command == '0') {
      pumpMode = '0';
      setPump(false);
    } else if (command == 'A' || command == 'a') {
      pumpMode = 'A';
    }
  }
}

void updatePump(unsigned long now) {
  // A detected leak always stops every mode immediately.
  if (waterDetected) {
    setPump(false);
    return;
  }

  if (pumpMode == 'T') {
    if ((long)(now - pumpTestUntil) >= 0) {
      setPump(false);
      pumpMode = '0';
    }
    return;
  }

  // Normal operation requires a valid level signal.
  if (distanceCm < 0 || distanceCm < BLIND_ZONE_CM || pumpMode == '0') {
    setPump(false);
    return;
  }

  if (pumpMode == '1') {
    setPump(true);
  } else if (pumpMode == 'A') {
    if (!pumpOn && levelPercent <= LOW_PERCENT) setPump(true);
    if (pumpOn && levelPercent >= FULL_PERCENT) setPump(false);
  }

  if (pumpOn && now - pumpStartedAt >= MAX_PUMP_RUN_MS) {
    Serial.println("PUMP SAFETY TIMEOUT");
    setPump(false);
    pumpMode = '0';
  }
}

void updateWaterContact() {
  // The small contact board is powered only while sampled. This frees a real
  // 3V3 header for the ultrasonic module and reduces probe corrosion.
  digitalWrite(WATER_SENSOR_POWER_PIN, HIGH);
  delay(20);
  waterRaw = analogRead(WATER_SENSOR_PIN);
  digitalWrite(WATER_SENSOR_POWER_PIN, LOW);
  waterDetected = waterRaw >= WATER_WET_THRESHOLD;
}

float measureDistance() {
  // Send ultrasonic trigger pulse
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(3);

  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(20);
  digitalWrite(TRIG_PIN, LOW);

  // Read echo with 60ms timeout
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 60000);

  if (duration == 0) {
    return -1;
  }

  // Convert time to distance in centimetres
  return (duration * 0.0343) / 2.0;
}

float medianDistance() {
  float sorted[MEDIAN_SAMPLES];
  memcpy(sorted, samples, sizeof(float) * sampleCount);
  for (int i = 1; i < sampleCount; i++) {
    float v = sorted[i];
    int j = i - 1;
    while (j >= 0 && sorted[j] > v) {
      sorted[j + 1] = sorted[j];
      j--;
    }
    sorted[j + 1] = v;
  }
  return sorted[sampleCount / 2];
}

void updateLevel() {
  float reading = measureDistance();

  if (reading < 0 || reading > MAX_RANGE_CM) {
    if (missedEchoes < MAX_MISSED_ECHOES) {
      missedEchoes++;
    }
    if (missedEchoes >= MAX_MISSED_ECHOES) {
      sampleCount = 0;
      sampleIndex = 0;
      distanceCm = -1;
    }
    return;
  }

  missedEchoes = 0;
  samples[sampleIndex] = reading;
  sampleIndex = (sampleIndex + 1) % MEDIAN_SAMPLES;
  if (sampleCount < MEDIAN_SAMPLES) {
    sampleCount++;
  }

  distanceCm = medianDistance();
  float percent = (TANK_EMPTY_CM - distanceCm) / (TANK_EMPTY_CM - TANK_FULL_CM) * 100.0;
  levelPercent = constrain((int)(percent + 0.5), 0, 100);
}

void updateFlow(unsigned long now) {
  noInterrupts();
  uint32_t pulses = flowPulses;
  flowPulses = 0;
  interrupts();

  unsigned long elapsed = now - lastFlow;
  lastFlow = now;

  flowLpm = pulses / PULSES_PER_LITRE * 60000.0 / elapsed;
  totalLitres += pulses / PULSES_PER_LITRE;
  totalPulses += pulses;

  Serial.print("Distance: ");
  if (distanceCm < 0) {
    Serial.print("No echo detected");
  } else {
    Serial.print(distanceCm, 1);
    Serial.print(" cm | Level: ");
    Serial.print(levelPercent);
    Serial.print("%");
  }
  Serial.print(" | Flow: ");
  Serial.print(flowLpm, 2);
  Serial.print(" L/min | Total: ");
  Serial.print(totalLitres, 3);
  Serial.print(" L | Pulses: ");
  Serial.print(totalPulses);
  Serial.print(" | Flow pin: ");
  Serial.print(digitalRead(FLOW_PIN));
  Serial.print(" | Water raw: ");
  Serial.print(waterRaw);
  Serial.print(" | Contact: ");
  Serial.print(waterDetected ? "WET" : "DRY");
  Serial.print(" | Pump: ");
  Serial.println(pumpOn ? "ON" : "OFF");

  sendTelemetry();
}

// One JSON line per second for scripts/arduino_serial_bridge.py. Level and
// distance are left out with no echo, so a lost sensor never reads as empty.
void sendTelemetry() {
  Serial.print("{\"station_code\":\"");
  Serial.print(STATION_CODE);
  Serial.print("\",\"source\":\"esp32\",\"flow_rate_l_min\":");
  Serial.print(flowLpm, 2);
  Serial.print(",\"flow_total_liters\":");
  Serial.print(totalLitres, 3);
  Serial.print(",\"water_contact\":");
  Serial.print(waterDetected ? "true" : "false");
  Serial.print(",\"pump_on\":");
  Serial.print(pumpOn ? "true" : "false");
  Serial.print(",\"pump_run_ms\":");
  Serial.print(pumpRunMs + (pumpOn ? millis() - pumpStartedAt : 0));
  Serial.print(",\"pump_mode\":\"");
  Serial.print(pumpMode);
  Serial.print("\"");
  if (distanceCm >= 0) {
    Serial.print(",\"distance_cm\":");
    Serial.print(distanceCm, 1);
    Serial.print(",\"water_level_percent\":");
    Serial.print(levelPercent);
  }
  Serial.println("}");
}

const char* statusText() {
  if (waterDetected) return "LEAK";
  if (distanceCm < 0) return "NO SIGNAL";
  if (distanceCm < BLIND_ZONE_CM) return "TOO CLOSE";
  if (pumpOn) return "PUMP ON";
  if (levelPercent <= LOW_PERCENT) return "LOW";
  if (levelPercent >= FULL_PERCENT) return "FULL";
  return "NORMAL";
}

// Warnings blink so they read from across the table.
bool statusIsWarning() {
  return waterDetected || distanceCm < BLIND_ZONE_CM || levelPercent <= LOW_PERCENT;
}

void updateIndicators() {
  if (waterDetected || distanceCm < 0) rgbLedWrite(RGB_LED_PIN, 45, 0, 0);
  else if (distanceCm < BLIND_ZONE_CM || levelPercent <= LOW_PERCENT) rgbLedWrite(RGB_LED_PIN, 45, 20, 0);
  else if (flowLpm > 0.05) rgbLedWrite(RGB_LED_PIN, 0, 15, 45);
  else rgbLedWrite(RGB_LED_PIN, 0, 45, 0);
}

void drawHeader() {
  oled.setFont(u8g2_font_6x10_tr);
  oled.drawStr(0, 8, "WATERSENSE");

  const char* status = statusText();
  int width = oled.getStrWidth(status) + 6;
  int x = 128 - width;

  if (statusIsWarning() && (frame & 2)) {
    oled.drawStr(x + 3, 8, status);
  } else {
    oled.drawRBox(x, 0, width, 10, 2);
    oled.setDrawColor(0);
    oled.drawStr(x + 3, 8, status);
    oled.setDrawColor(1);
  }

  oled.drawHLine(0, 12, 128);
}

void drawTank() {
  const int x = 1, y = 15, w = 30, h = 49;
  oled.drawRFrame(x, y, w, h, 3);

  // Pump start and stop marks beside the tank
  int inner = h - 4;
  oled.drawHLine(x + w + 1, y + 2 + inner - inner * LOW_PERCENT / 100, 3);
  oled.drawHLine(x + w + 1, y + 2 + inner - inner * FULL_PERCENT / 100, 3);

  if (distanceCm < 0) {
    oled.setFont(u8g2_font_helvB12_tr);
    oled.drawStr(x + 11, y + 30, "?");
    return;
  }

  int fill = inner * levelPercent / 100;
  if (fill <= 0) return;

  // Water, with a small wave rolling along the surface
  for (int i = 0; i < w - 4; i++) {
    int wave = (fill > 3 && fill < inner) ? (((i + frame) / 3) % 2) : 0;
    int top = y + 2 + inner - fill + wave;
    oled.drawVLine(x + 2 + i, top, y + 2 + inner - top);
  }
}

void drawReadings() {
  const int x = 38;
  char text[20];

  oled.setFont(u8g2_font_helvB18_tr);
  if (distanceCm < 0) {
    oled.drawStr(x, 34, "--%");
  } else {
    snprintf(text, sizeof(text), "%d%%", levelPercent);
    oled.drawStr(x, 34, text);
  }

  oled.setFont(u8g2_font_6x10_tr);
  if (distanceCm < 0) {
    oled.drawStr(x, 44, "Check sensor");
  } else {
    snprintf(text, sizeof(text), "%.1f cm", distanceCm);
    oled.drawStr(x, 44, text);
  }

  // The flow row turns solid while water is moving
  snprintf(text, sizeof(text), "%.1f L/min", flowLpm);
  if (flowLpm > 0.05) {
    oled.drawBox(x - 1, 46, 91, 9);
    oled.setDrawColor(0);
    oled.drawStr(x, 54, text);
    oled.setDrawColor(1);
  } else {
    oled.drawStr(x, 54, text);
  }

  snprintf(text, sizeof(text), "%.2f L total", totalLitres);
  oled.drawStr(x, 64, text);
}

void drawScreen() {
  oled.clearBuffer();
  drawHeader();
  drawTank();
  drawReadings();
  oled.sendBuffer();
}

void drawSplash() {
  oled.clearBuffer();
  oled.setFont(u8g2_font_helvB12_tr);
  oled.drawStr((128 - oled.getStrWidth("WaterSense AI")) / 2, 28, "WaterSense AI");
  oled.setFont(u8g2_font_6x10_tr);
  oled.drawStr((128 - oled.getStrWidth("Intelligence for")) / 2, 44, "Intelligence for");
  oled.drawStr((128 - oled.getStrWidth("every drop")) / 2, 55, "every drop");
  oled.sendBuffer();
}

void setup() {
  Serial.begin(115200);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(WATER_SENSOR_PIN, INPUT);
  pinMode(WATER_SENSOR_POWER_PIN, OUTPUT);
  digitalWrite(WATER_SENSOR_POWER_PIN, LOW);
  pinMode(FLOW_POWER_PIN, OUTPUT);
  digitalWrite(FLOW_POWER_PIN, HIGH);
  pinMode(FLOW_PIN, INPUT_PULLUP);
  // Preload the OFF level before enabling the output to avoid a startup pulse.
  digitalWrite(RELAY_PIN, RELAY_ACTIVE_LOW ? HIGH : LOW);
  pinMode(RELAY_PIN, OUTPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  digitalWrite(TRIG_PIN, LOW);

  attachInterrupt(digitalPinToInterrupt(FLOW_PIN), onFlowPulse, FALLING);

  Serial.println("WATERSENSE ESP32 PIN MAP");
  Serial.println("OLED SDA=8 SCL=9 | WATER S=4 POWER=5");
  Serial.println("FLOW SIGNAL=16 POWER=6 | ULTRASONIC TRIG=17 ECHO=18");
  Serial.println("RELAY IN1=21 (ACTIVE LOW) | BUZZER=42 | RGB=48");
  Serial.println("PUMP SAFE OFF | COMMANDS: T=3s TEST, 1=ON, 0=OFF, A=AUTO");

  // Slow I2C: long jumper wires are unreliable at 400 kHz
  oled.setBusClock(100000);
  oled.begin();

  drawSplash();
  rgbLedWrite(RGB_LED_PIN, 35, 0, 0); delay(180);
  rgbLedWrite(RGB_LED_PIN, 0, 35, 0); delay(180);
  rgbLedWrite(RGB_LED_PIN, 0, 0, 35); delay(180);
  tone(BUZZER_PIN, 1800, 150);
  delay(2000);

  lastFlow = millis();
}

void loop() {
  unsigned long now = millis();

  handlePumpCommand();

  if (now - lastFlow >= FLOW_INTERVAL_MS) {
    updateFlow(now);
  }

  if (now - lastRead >= READ_INTERVAL_MS) {
    lastRead = now;
    updateLevel();
    updateWaterContact();
    updatePump(now);
    updateIndicators();
    frame++;
    drawScreen();
  }
}
