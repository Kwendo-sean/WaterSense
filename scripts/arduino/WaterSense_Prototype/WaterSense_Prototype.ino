#include <Stepper.h>

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

const int MOTOR_IN1 = 4;
const int MOTOR_IN2 = 5;
const int MOTOR_IN3 = 6;
const int MOTOR_IN4 = 7;

const int GREEN_LED = 8;
const int YELLOW_LED = 9;
const int RED_LED = 10;
const int BUZZER_PIN = 11;

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

unsigned long lastSensorRead = 0;
unsigned long bootTime = 0;

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
  pinMode(BUZZER_PIN, OUTPUT);

  pinMode(MOTOR_IN1, OUTPUT);
  pinMode(MOTOR_IN2, OUTPUT);
  pinMode(MOTOR_IN3, OUTPUT);
  pinMode(MOTOR_IN4, OUTPUT);

  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  pumpMotor.setSpeed(MOTOR_SPEED_RPM);
  releaseMotor();

  bootTime = millis();

  Serial.println();
  Serial.println("================================");
  Serial.println("       WATERSENSE AI DEMO");
  Serial.println("================================");
  Serial.println("Starting sensors and pump...");
  Serial.println("PIR sensor warming up for 30 seconds.");
  Serial.println();
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
    Serial.println("PUMP: ON - tank low, refilling.");
  }
  else if (pumpOn && levelPercent >= PUMP_STOP_PERCENT) {
    pumpOn = false;
    releaseMotor();
    Serial.println("PUMP: OFF - tank full.");
    beep(2);
  }
}

// De-energise the coils so the stepper doesn't heat up while idle.
void releaseMotor() {
  digitalWrite(MOTOR_IN1, LOW);
  digitalWrite(MOTOR_IN2, LOW);
  digitalWrite(MOTOR_IN3, LOW);
  digitalWrite(MOTOR_IN4, LOW);
}

void beep(int times) {
  for (int i = 0; i < times; i++) {
    digitalWrite(BUZZER_PIN, HIGH);
    delay(120);
    digitalWrite(BUZZER_PIN, LOW);
    delay(120);
  }
}

// ============================================
// LEDS AND BUZZER
// ============================================
void updateIndicators() {
  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);

  if (currentLevel == LEVEL_LOW) {
    digitalWrite(RED_LED, HIGH);
    digitalWrite(BUZZER_PIN, HIGH);
  }
  else if (currentLevel == LEVEL_MEDIUM) {
    digitalWrite(YELLOW_LED, HIGH);
    digitalWrite(BUZZER_PIN, LOW);
  }
  else {
    digitalWrite(GREEN_LED, HIGH);
    digitalWrite(BUZZER_PIN, LOW);
  }
}

// ============================================
// SERIAL MONITOR STATUS
// ============================================
void printStatus() {
  Serial.print("Level ADC: ");
  Serial.print(rawLevel);

  Serial.print(" | Level: ");
  Serial.print(levelPercent);
  Serial.print("%");

  Serial.print(" | Status: ");
  if (currentLevel == LEVEL_LOW) {
    Serial.print("LOW");
  }
  else if (currentLevel == LEVEL_MEDIUM) {
    Serial.print("MEDIUM");
  }
  else {
    Serial.print("HIGH");
  }

  Serial.print(" | Pump: ");
  Serial.print(pumpOn ? "ON" : "OFF");

  Serial.print(" | Water sensor ADC: ");
  Serial.print(waterSensorValue);

  Serial.print(" | Water contact: ");
  Serial.print(waterDetected ? "DETECTED" : "NOT DETECTED");

  Serial.print(" | Motion: ");
  Serial.println(motionDetected ? "DETECTED" : "NONE");
}

// ============================================
// JSON LINE FOR scripts/arduino_serial_bridge.py
// One self-contained JSON object per line. The bridge parses each line
// independently, so this must stay on its own println-terminated line.
// ============================================
void sendTelemetryJSON() {
  Serial.print("{\"station_code\":\"");
  Serial.print(STATION_CODE);
  Serial.print("\",\"water_level_percent\":");
  Serial.print(levelPercent);
  Serial.print(",\"level_raw\":");
  Serial.print(rawLevel);
  Serial.print(",\"pump_on\":");
  Serial.print(pumpOn ? "true" : "false");
  Serial.print(",\"pump_run_ms\":");
  Serial.print(pumpRunMs);
  Serial.print(",\"water_contact\":");
  Serial.print(waterDetected ? "true" : "false");
  // The PIR reads garbage while warming up, so leave motion out until then.
  if (millis() - bootTime >= PIR_WARMUP_MS) {
    Serial.print(",\"motion\":");
    Serial.print(motionDetected ? "true" : "false");
  }
  Serial.println("}");
}
