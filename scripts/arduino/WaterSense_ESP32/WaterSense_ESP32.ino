#include <Wire.h>
#include <U8g2lib.h>
#include <driver/gpio.h>

// WaterSense Prototype 2: ESP32-S3 tank controller.
// Wiring follows the Prototype 2 diagram. The buzzer on GPIO 42 is not used.

// Must exactly match the station_code registered on the backend.
const char* STATION_CODE = "WS-PROTOTYPE-02";

// -------- PINS --------
#define OLED_SDA 8
#define OLED_SCL 9

#define TRIG_PIN 17
#define ECHO_PIN 18

// HW-038 leak strip: S to GPIO 4 (ADC), + to GPIO 5. Powered only while it is
// read, which slows corrosion of the exposed traces.
#define LEAK_PIN 4
#define LEAK_POWER_PIN 5

// YF-S201: yellow to GPIO 16, red to GPIO 6 (3.3 V from the pin), black to GND.
#define FLOW_PIN 16
#define FLOW_POWER_PIN 6

// SRD-05VDC relay module IN1 switches the real pump. Low-level trigger:
// the relay closes when IN is LOW.
#define RELAY_PIN 21
#define RELAY_ON LOW
#define RELAY_OFF HIGH

// Optional SG90 servo that sweeps while the pump runs, as a visible cue
// (orange to GPIO 7, red to 5V, brown to GND).
#define SERVO_PIN 7
// Buzzer + to GPIO 42, - to GND.
#define BUZZER_PIN 42

// Fixed LEDC channels so the buzzer's frequency changes never retime the
// servo: channels share a timer in pairs (2-3 and 6-7).
const int SERVO_CHANNEL = 2;
const int BUZZER_CHANNEL = 6;
const int SERVO_MIN_ANGLE = 20;
const int SERVO_MAX_ANGLE = 160;
const int SERVO_STEP = 4;          // degrees per 20 ms: about 1.4 s per sweep

// -------- LEVEL SENSOR --------
// 1 = HC-SR04 (blind zone about 2 cm, suits a short container; ECHO is 5 V,
//     so it needs a 1k/2k divider), 0 = waterproof JSN-SR04T (blind zone
//     about 20-25 cm, so the water must stay at least 25 cm below it).
#define USE_HCSR04 1

// -------- TANK --------
// Distance from the sensor down to the water surface. Measure both on the
// real container. TANK_FULL_CM must stay above BLIND_ZONE_CM.
#if USE_HCSR04
const float TANK_EMPTY_CM = 15.0;  // measured: empty 700 ml bottle read 15.1 cm (13 Nov)
const float TANK_FULL_CM = 5.0;    // closest reliable reading; half full read 8.4 cm
#else
const float TANK_EMPTY_CM = 30.0;  // JSN-SR04T in a 30 cm rig: only 8 cm of usable travel
const float TANK_FULL_CM = 22.0;
#endif
const float OUT_OF_TANK_MARGIN_CM = 10.0;
// About 0.5 L between the empty and full marks of the 700 ml demo bottle;
// matches pump_capacity_liters on the backend.
const float TANK_CAPACITY_L = 0.5;

// Same thresholds as Prototype 1 and the backend.
const int PUMP_START_PERCENT = 20;
const int PUMP_STOP_PERCENT = 85;
// Even a manual or scheduled run stops here, so the bucket can't overflow.
const int HARD_STOP_PERCENT = 95;

// -------- DEMO FILL (simulated) --------
// Like Prototype 1: while the pump runs the level rises at a pump-like rate,
// then drains back to the real sensor reading after it stops, so the tank
// cycles on its own for a table demo. Never lower than the sensor, so real
// water always wins. Flagged as level_simulated in the telemetry and as
// "SIM" on the OLED. Set to false to show the sensor only.
const bool SIMULATED_FILL = true;
const float SIM_FILL_PERCENT_PER_S = 4.0;   // about 1.2 L/min into the 0.5 L bottle
const float SIM_DRAIN_PERCENT_PER_S = 1.0;  // stands in for water being used

// -------- PUMP SAFETY --------
// No single run may last longer than this. If it does, something is wrong
// (sensor not seeing the rise, pump dry, hose off) and the pump locks out
// until the dashboard sends a new command or the board restarts.
const unsigned long MAX_RUN_MS = 120000;
// Estimate for a small 3-6 V submersible pump, used for litres pumped when
// the flow sensor sees nothing. Replace with a measured figure.
const float PUMP_NOMINAL_LPM = 1.5;
// The dashboard resends its command every reading; without it, back to auto.
const unsigned long COMMAND_TIMEOUT_MS = 10000;

// -------- ULTRASONIC --------
#if USE_HCSR04
const float BLIND_ZONE_CM = 3.0;
#else
const float BLIND_ZONE_CM = 20.0;
#endif
// With no echo the module holds ECHO high for about 40 ms, which reads as 686 cm.
const float MAX_RANGE_CM = 450.0;
const unsigned long READ_INTERVAL_MS = 200;
const int MEDIAN_SAMPLES = 5;
const int MAX_MISSED_ECHOES = 5;

// -------- LEAK --------
// 12-bit ADC: dry reads near 0. Initial threshold, check the raw value printed
// on Serial with the strip dry and then touched with a wet finger.
const int LEAK_WET_THRESHOLD = 400;

// -------- FLOW --------
// YF-S201 datasheet figure. Calibrate by running a measured litre through it.
const float PULSES_PER_LITRE = 450.0;
const unsigned long FLOW_INTERVAL_MS = 1000;

U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE, OLED_SCL, OLED_SDA);

// -------- STATE --------
volatile uint32_t flowPulses = 0;

float samples[MEDIAN_SAMPLES];
int sampleCount = 0;
int sampleIndex = 0;
int missedEchoes = MAX_MISSED_ECHOES;

float distanceCm = -1;
int levelPercent = 0;     // what the controller acts on and reports
int sensorPercent = 0;    // straight from the ultrasonic
float simLevel = -1;      // demo fill level, -1 when inactive
float flowLpm = 0;
float totalLitres = 0;
uint32_t totalPulses = 0;

int leakRaw = 0;
bool leakDetected = false;

bool pumpOn = false;
unsigned long pumpStartedAt = 0;
unsigned long pumpRunMs = 0;      // total run time since boot
char pumpMode = 'A';              // last command from the dashboard
unsigned long lastCommandAt = 0;
bool forcedFull = false;          // a forced run reached the stop level
const char* pumpFault = nullptr;  // set when the pump was stopped for safety

int servoAngle = SERVO_MIN_ANGLE;
int servoDir = 1;
unsigned long lastServo = 0;

// Buzzer: a queue of up to 4 notes played without blocking the loop.
struct Note { uint16_t freq; uint16_t ms; };
Note melody[4];
int melodyLen = 0, melodyPos = 0;
unsigned long noteEndsAt = 0;
unsigned long lastLeakAlarm = 0;

bool oledFound = false;
unsigned long lastRead = 0;
unsigned long lastFlow = 0;
unsigned long lastTick = 0;
byte frame = 0;

void IRAM_ATTR onFlowPulse() {
  flowPulses++;
}

// ============================================
// SENSORS
// ============================================
float measureDistance() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(3);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(20);
  digitalWrite(TRIG_PIN, LOW);

  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 60000);
  if (duration == 0) return -1;
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

  // Inside the blind zone the sensor reports false echoes (2-5 cm on 3.3 V),
  // which would read as a full tank and stop the pump. Treat them as misses.
  if (reading < BLIND_ZONE_CM || reading > MAX_RANGE_CM) {
    if (missedEchoes < MAX_MISSED_ECHOES) missedEchoes++;
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
  if (sampleCount < MEDIAN_SAMPLES) sampleCount++;

  distanceCm = medianDistance();
  float percent = (TANK_EMPTY_CM - distanceCm) / (TANK_EMPTY_CM - TANK_FULL_CM) * 100.0;
  sensorPercent = constrain((int)(percent + 0.5), 0, 100);
  levelPercent = sensorPercent;
}

bool simActive() {
  return simLevel >= 0;
}

void applySimulatedFill(float dtSeconds) {
  if (!SIMULATED_FILL || !probeInTank() || pumpFault) {
    simLevel = -1;
    return;
  }
  if (pumpOn) {
    if (!simActive()) simLevel = sensorPercent;
    simLevel = min(100.0f, simLevel + SIM_FILL_PERCENT_PER_S * dtSeconds);
  } else if (simActive()) {
    simLevel -= SIM_DRAIN_PERCENT_PER_S * dtSeconds;
    if (simLevel <= sensorPercent) simLevel = -1;  // back to the real reading
  }
  levelPercent = simActive() ? max(sensorPercent, (int)(simLevel + 0.5)) : sensorPercent;
}

void updateLeak() {
  digitalWrite(LEAK_POWER_PIN, HIGH);
  delay(5);
  leakRaw = analogRead(LEAK_PIN);
  digitalWrite(LEAK_POWER_PIN, LOW);
  leakDetected = leakRaw > LEAK_WET_THRESHOLD;
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
}

// ============================================
// COMMANDS FROM THE DASHBOARD (via the bridge)
// A auto, 1 on, 0 off, S scheduled run
// ============================================
void readCommands() {
  while (Serial.available()) {
    char c = Serial.read();
    if (c != 'A' && c != '1' && c != '0' && c != 'S') continue;  // skips newlines
    lastCommandAt = millis();
    if (c != pumpMode) {
      pumpMode = c;
      forcedFull = false;
      pumpFault = nullptr;  // a new command is the operator acknowledging a fault
      Serial.print("MODE: ");
      Serial.println(c);
    }
  }
  if (pumpMode != 'A' && millis() - lastCommandAt > COMMAND_TIMEOUT_MS) {
    pumpMode = 'A';
    Serial.println("MODE: A (no commands, back to automatic)");
  }
}

// ============================================
// BUZZER
// ============================================
void play(std::initializer_list<Note> notes) {
  melodyLen = 0;
  for (const Note& n : notes) {
    if (melodyLen < 4) melody[melodyLen++] = n;
  }
  melodyPos = 0;
  noteEndsAt = 0;
}

void updateBuzzer(unsigned long now) {
  if (melodyPos >= melodyLen) return;
  if (noteEndsAt != 0 && now < noteEndsAt) return;
  if (noteEndsAt != 0) melodyPos++;
  if (melodyPos >= melodyLen) {
    ledcWriteTone(BUZZER_PIN, 0);
    noteEndsAt = 0;
    return;
  }
  ledcWriteTone(BUZZER_PIN, melody[melodyPos].freq);  // freq 0 is a rest
  noteEndsAt = now + melody[melodyPos].ms;
}

// ============================================
// SERVO (pump stand-in)
// ============================================
void writeServo(int angle) {
  // 50 Hz, 14-bit: 500-2500 us pulse for 0-180 degrees
  uint32_t us = 500 + (uint32_t)angle * 2000 / 180;
  ledcWrite(SERVO_PIN, us * 16383 / 20000);
}

void updateServo(unsigned long now) {
  if (!pumpOn || now - lastServo < 20) return;
  lastServo = now;
  servoAngle += servoDir * SERVO_STEP;
  if (servoAngle >= SERVO_MAX_ANGLE || servoAngle <= SERVO_MIN_ANGLE) {
    servoAngle = constrain(servoAngle, SERVO_MIN_ANGLE, SERVO_MAX_ANGLE);
    servoDir = -servoDir;
  }
  writeServo(servoAngle);
}

// ============================================
// PUMP CONTROL
// ============================================
// The relay board runs on 5 V, so a 3.3 V HIGH can still leak enough current
// through its opto-coupler to hold the relay on. For OFF the pin is released
// (high impedance) and the board's own pull-up switches the relay off; for ON
// it is driven LOW.
void relayWrite(bool on) {
  if (on) {
    digitalWrite(RELAY_PIN, LOW);
    pinMode(RELAY_PIN, OUTPUT);
  } else {
    pinMode(RELAY_PIN, INPUT);
  }
}

void setPump(bool on) {
  if (on == pumpOn) return;
  pumpOn = on;
  relayWrite(on);
  if (on) {
    pumpStartedAt = millis();
    play({{1320, 80}, {0, 40}, {1760, 120}});    // rising chirp
  } else {
    servoAngle = SERVO_MIN_ANGLE;
    servoDir = 1;
    writeServo(SERVO_MIN_ANGLE);                 // park
    if (!pumpFault) play({{1760, 80}, {0, 40}, {1320, 120}});  // falling chirp
  }
  Serial.println(on ? "PUMP: ON" : "PUMP: OFF");
}

void stopForFault(const char* reason) {
  pumpFault = reason;
  setPump(false);
  play({{880, 300}, {0, 120}, {880, 300}});
  Serial.print("PUMP FAULT: ");
  Serial.println(reason);
}

// Further than the empty tank means the probe is looking past the container
// (lifted out, tilted, pointed at the room), not that the tank is empty.
bool probeInTank() {
  return distanceCm >= 0 && distanceCm <= TANK_EMPTY_CM + OUT_OF_TANK_MARGIN_CM;
}

void updatePump() {
  bool levelKnown = probeInTank();

  // Safety stops apply in every mode.
  if (pumpOn && leakDetected) { stopForFault("LEAK"); return; }
  if (pumpOn && !levelKnown) { stopForFault("NO LEVEL"); return; }
  if (pumpOn && millis() - pumpStartedAt > MAX_RUN_MS) { stopForFault("TIMEOUT"); return; }
  if (pumpFault) return;

  bool forced = pumpMode == '1' || pumpMode == 'S';
  if (forced && levelKnown && levelPercent >= HARD_STOP_PERCENT) forcedFull = true;

  bool want = pumpOn;
  if (pumpMode == '0' || !levelKnown || leakDetected) {
    want = false;
  } else if (forced) {
    want = !forcedFull;
  } else if (!pumpOn && levelPercent <= PUMP_START_PERCENT) {
    want = true;   // automatic: tank low
  } else if (pumpOn && levelPercent >= PUMP_STOP_PERCENT) {
    want = false;  // automatic: refilled
  }
  setPump(want);
}

// Leak, sensor loss and run timeout clear on their own in auto once the
// cause is gone, except a timeout, which waits for a dashboard command.
void clearFaults() {
  if (!pumpFault) return;
  if (pumpFault[0] == 'L' && !leakDetected) pumpFault = nullptr;
  else if (pumpFault[0] == 'N' && probeInTank()) pumpFault = nullptr;
}

// ============================================
// SERIAL OUTPUT
// ============================================
void printStatus() {
  Serial.print("Distance: ");
  if (distanceCm < 0) {
    Serial.print("NO ECHO");
  } else {
    Serial.print(distanceCm, 1);
    Serial.print(" cm (");
    Serial.print(levelPercent);
    Serial.print("%)");
  }
  Serial.print(" | Leak raw: ");
  Serial.print(leakRaw);
  Serial.print(leakDetected ? " WET" : " dry");
  Serial.print(" | Flow pin: ");
  Serial.print(digitalRead(FLOW_PIN));
  Serial.print(" ");
  Serial.print(flowLpm, 2);
  Serial.print(" L/min, ");
  Serial.print(totalPulses);
  Serial.print(" pulses | Pump: ");
  Serial.print(pumpOn ? "ON" : "off");
  Serial.print(" mode ");
  Serial.print(pumpMode);
  if (pumpFault) {
    Serial.print(" FAULT ");
    Serial.print(pumpFault);
  }
  Serial.print(" | OLED: ");
  Serial.println(oledFound ? "ok" : "NOT FOUND");
}

// One JSON line per second for scripts/arduino_serial_bridge.py. Level and
// distance are left out with no echo, so a lost sensor never reads as empty.
void sendTelemetry() {
  float pumpLpm = flowLpm > 0.1 ? flowLpm : PUMP_NOMINAL_LPM;
  Serial.print("{\"station_code\":\"");
  Serial.print(STATION_CODE);
  Serial.print("\",\"source\":\"esp32\",\"flow_rate_l_min\":");
  Serial.print(flowLpm, 2);
  Serial.print(",\"flow_total_liters\":");
  Serial.print(totalLitres, 3);
  Serial.print(",\"pump_on\":");
  Serial.print(pumpOn ? "true" : "false");
  Serial.print(",\"pump_run_ms\":");
  Serial.print(pumpRunMs);
  Serial.print(",\"pump_mode\":\"");
  Serial.print(pumpMode);
  Serial.print("\",\"flow_lpm\":");
  Serial.print(pumpLpm, 2);
  Serial.print(",\"water_contact\":");
  Serial.print(leakDetected ? "true" : "false");
  Serial.print(",\"level_simulated\":");
  Serial.print(simActive() ? "true" : "false");
  if (distanceCm >= 0) {
    Serial.print(",\"distance_cm\":");
    Serial.print(distanceCm, 1);
    Serial.print(",\"water_level_percent\":");
    Serial.print(levelPercent);
  }
  Serial.println("}");
}

// ============================================
// OLED
// ============================================
const char* statusText() {
  if (leakDetected) return "LEAK";
  if (pumpFault) return "FAULT";
  if (distanceCm < 0) return "NO SIGNAL";
  if (distanceCm < BLIND_ZONE_CM) return "TOO CLOSE";
  if (!probeInTank()) return "AIM PROBE";  // 9 chars max fits beside the title
  if (pumpOn) return simActive() ? "SIM FILL" : "FILLING";
  if (levelPercent <= PUMP_START_PERCENT) return "LOW";
  if (levelPercent >= PUMP_STOP_PERCENT) return "FULL";
  return "NORMAL";
}

// Warnings blink so they read from across the table.
bool statusIsWarning() {
  return leakDetected || pumpFault || distanceCm < BLIND_ZONE_CM || !probeInTank() ||
         (!pumpOn && levelPercent <= PUMP_START_PERCENT);
}

// ---- Small icons, 7x7 px, (x, y) is the top-left corner ----
void iconDrop(int x, int y) {
  oled.drawDisc(x + 3, y + 4, 2);
  oled.drawTriangle(x + 1, y + 4, x + 5, y + 4, x + 3, y);
}

// Impeller: spins while the pump runs
void iconPump(int x, int y, bool spinning) {
  static const int8_t dx[4] = {3, 2, 0, -2};
  static const int8_t dy[4] = {0, 2, 3, 2};
  int cx = x + 3, cy = y + 3, a = spinning ? frame % 4 : 0;
  oled.drawCircle(cx, cy, 3);
  oled.drawLine(cx - dx[a], cy - dy[a], cx + dx[a], cy + dy[a]);
}

void iconBase(int x, int y, bool wet) {
  if (wet) {
    oled.drawTriangle(x, y + 6, x + 6, y + 6, x + 3, y);
    oled.setDrawColor(0);
    oled.drawVLine(x + 3, y + 2, 2);
    oled.drawPixel(x + 3, y + 5);
    oled.setDrawColor(1);
  } else {
    oled.drawHLine(x, y + 6, 7);   // floor
    oled.drawFrame(x + 1, y + 1, 5, 5);
  }
}

void drawHeader() {
  iconDrop(0, 1);
  oled.setFont(u8g2_font_5x8_tr);
  oled.drawStr(10, 8, "WATERSENSE");

  oled.setFont(u8g2_font_6x10_tr);
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
  const int x = 0, y = 14, w = 27, h = 50;
  oled.drawRFrame(x, y, w, h, 3);

  // Pump start and stop marks beside the tank
  int inner = h - 4;
  oled.drawHLine(x + w + 1, y + 2 + inner - inner * PUMP_START_PERCENT / 100, 3);
  oled.drawHLine(x + w + 1, y + 2 + inner - inner * PUMP_STOP_PERCENT / 100, 3);

  if (distanceCm < 0) {
    oled.setFont(u8g2_font_helvB12_tr);
    oled.drawStr(x + 10, y + 31, "?");
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

  // Falling drops into the tank while the pump runs
  if (pumpOn) {
    int dropY = y + 3 + (frame * 3) % max(4, inner - fill);
    oled.drawDisc(x + w / 2, dropY, 1);
  }
}

void drawRightAligned(int baseline, const char* text) {
  oled.drawStr(128 - oled.getStrWidth(text), baseline, text);
}

// Right column: big level with litres and distance beside it, then one
// icon row each for pump, flow and the base leak strip.
void drawReadings() {
  const int x = 33;
  char text[24];

  oled.setFont(u8g2_font_helvB18_tr);
  if (!probeInTank()) {
    oled.drawStr(x, 33, "--%");
  } else {
    snprintf(text, sizeof(text), "%d%%", levelPercent);
    oled.drawStr(x, 33, text);
  }

  oled.setFont(u8g2_font_5x8_tr);
  if (probeInTank()) {
    snprintf(text, sizeof(text), simActive() ? "SIM %dml" : "%dml", (int)(TANK_CAPACITY_L * 1000 * levelPercent / 100.0 + 0.5));
    drawRightAligned(22, text);
  }
  if (distanceCm >= 0) snprintf(text, sizeof(text), "%.0fcm", distanceCm);
  else snprintf(text, sizeof(text), "no echo");
  drawRightAligned(32, text);

  oled.drawHLine(x, 36, 128 - x);
  oled.setFont(u8g2_font_6x10_tr);

  // Pump row turns solid while the pump runs
  if (pumpFault) {
    snprintf(text, sizeof(text), "STOP %s", pumpFault);
  } else if (pumpOn) {
    snprintf(text, sizeof(text), "PUMP ON %lus", (millis() - pumpStartedAt) / 1000);
  } else {
    const char* mode = pumpMode == '0' ? "OFF" : pumpMode == 'A' ? "AUTO" : "WAIT";
    snprintf(text, sizeof(text), "PUMP %s", mode);
  }
  if (pumpOn) {
    oled.drawBox(x, 38, 128 - x, 9);
    oled.setDrawColor(0);
    iconPump(x + 1, 39, true);
    oled.drawStr(x + 11, 46, text);
    oled.setDrawColor(1);
  } else {
    iconPump(x + 1, 39, false);
    oled.drawStr(x + 11, 46, text);
  }

  iconDrop(x + 1, 47);
  snprintf(text, sizeof(text), "%.1f L/min", flowLpm);
  oled.drawStr(x + 11, 55, text);

  // The leak row blinks while the strip is wet
  if (!leakDetected || (frame & 2)) {
    iconBase(x + 1, 56, leakDetected);
    oled.drawStr(x + 11, 64, leakDetected ? "LEAK!" : "Base dry");
  }
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

// ============================================
// SETUP / LOOP
// ============================================
void setup() {
  // Relay released (off) from the first instruction, so the pump never twitches at boot.
  relayWrite(false);

  Serial.begin(115200);

  ledcAttachChannel(SERVO_PIN, 50, 14, SERVO_CHANNEL);
  writeServo(SERVO_MIN_ANGLE);
  ledcAttachChannel(BUZZER_PIN, 2000, 10, BUZZER_CHANNEL);
  ledcWriteTone(BUZZER_PIN, 0);

  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  digitalWrite(TRIG_PIN, LOW);

  pinMode(LEAK_POWER_PIN, OUTPUT);
  digitalWrite(LEAK_POWER_PIN, LOW);
  pinMode(LEAK_PIN, INPUT);
  analogReadResolution(12);

  pinMode(FLOW_PIN, INPUT_PULLUP);
  pinMode(FLOW_POWER_PIN, OUTPUT);
  gpio_set_drive_capability((gpio_num_t)FLOW_POWER_PIN, GPIO_DRIVE_CAP_3);
  digitalWrite(FLOW_POWER_PIN, HIGH);
  attachInterrupt(digitalPinToInterrupt(FLOW_PIN), onFlowPulse, FALLING);

  Wire.begin(OLED_SDA, OLED_SCL, 100000);
  Wire.beginTransmission(0x3C);
  oledFound = Wire.endTransmission() == 0;

  // Slow I2C: long jumper wires are unreliable at 400 kHz
  oled.setBusClock(100000);
  oled.begin();
  drawSplash();
  delay(2000);

  Serial.println("WATERSENSE PROTOTYPE 2 READY");
  play({{1047, 90}, {1319, 90}, {1568, 140}});  // boot jingle
  lastFlow = lastTick = millis();
}

void loop() {
  unsigned long now = millis();

  readCommands();
  updateServo(now);
  updateBuzzer(now);

  // A wet base keeps beeping until it's dry
  if (leakDetected && now - lastLeakAlarm > 1500 && melodyPos >= melodyLen) {
    lastLeakAlarm = now;
    play({{2400, 120}, {0, 80}, {2400, 120}});
  }

  if (pumpOn) pumpRunMs += now - lastTick;
  lastTick = now;

  if (now - lastRead >= READ_INTERVAL_MS) {
    lastRead = now;
    updateLevel();
    applySimulatedFill(READ_INTERVAL_MS / 1000.0);
    updateLeak();
    clearFaults();
    updatePump();
    frame++;
    drawScreen();
  }

  if (now - lastFlow >= FLOW_INTERVAL_MS) {
    updateFlow(now);
    printStatus();
    sendTelemetry();
  }
}
