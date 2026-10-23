#include <Stepper.h>

// ============================================
// WATERSENSE AI - ARDUINO UNO R3 DEMO
// ============================================

// -------- STATION IDENTITY --------
// Must exactly match the station_code already registered on the backend.
const char* STATION_CODE = "WS-PROTOTYPE-01";

// -------- PIN CONFIGURATION --------
const int LEVEL_PIN = A0;       // Potentiometer: simulated tank level
const int WATER_SENSOR_PIN = A1; // Water contact sensor
const int PIR_PIN = 2;          // PIR motion sensor

const int MOTOR_IN1 = 4;
const int MOTOR_IN2 = 5;
const int MOTOR_IN3 = 6;
const int MOTOR_IN4 = 7;

const int GREEN_LED = 8;
const int YELLOW_LED = 9;
const int RED_LED = 10;
const int BUZZER_PIN = 11;

// -------- WATER LEVEL SETTINGS --------
// Analog readings range from 0 to 1023.
const int LOW_LEVEL_THRESHOLD = 341;
const int MEDIUM_LEVEL_THRESHOLD = 682;

// -------- MOTOR SETTINGS --------
const int STEPS_PER_REVOLUTION = 2048;
Stepper pumpMotor(
  STEPS_PER_REVOLUTION,
  MOTOR_IN1, MOTOR_IN3, MOTOR_IN2, MOTOR_IN4
);

const int MOTOR_SPEED_RPM = 10;

// Run the motor in short bursts to simulate pumping.
const int PUMP_STEPS = 256;
const unsigned long PUMP_INTERVAL_MS = 2000;

// -------- SENSOR SETTINGS --------
// Calibrate these after checking your water sensor's
// readings in the Serial Monitor.
const int WATER_WET_THRESHOLD = 100;

const unsigned long SENSOR_INTERVAL_MS = 500;
const unsigned long PIR_WARMUP_MS = 30000;

// -------- GLOBAL VARIABLES --------
int rawLevel = 0;
int waterSensorValue = 0;
int levelPercent = 0;

bool motionDetected = false;
bool waterDetected = false;

unsigned long lastSensorRead = 0;
unsigned long lastPumpRun = 0;
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

  digitalWrite(GREEN_LED, LOW);
  digitalWrite(YELLOW_LED, LOW);
  digitalWrite(RED_LED, LOW);
  digitalWrite(BUZZER_PIN, LOW);

  pumpMotor.setSpeed(MOTOR_SPEED_RPM);

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

  // Read and process sensors periodically.
  if (now - lastSensorRead >= SENSOR_INTERVAL_MS) {
    lastSensorRead = now;
    readSensors();
    updateWaterLevel();
    updateIndicators();
    printStatus();
    sendTelemetryJSON();
  }

  // Run the simulated pump when the level is low.
  // Wait for PIR warm-up before automatic pumping.
  if (currentLevel == LEVEL_LOW &&
      now - bootTime >= PIR_WARMUP_MS &&
      now - lastPumpRun >= PUMP_INTERVAL_MS) {

    lastPumpRun = now;

    Serial.println("PUMP: Low level - running pump motor.");

    pumpMotor.step(PUMP_STEPS);
  }
}

// ============================================
// READ SENSORS
// ============================================
void readSensors() {
  rawLevel = analogRead(LEVEL_PIN);
  waterSensorValue = analogRead(WATER_SENSOR_PIN);

  levelPercent = map(rawLevel, 0, 1023, 0, 100);
  levelPercent = constrain(levelPercent, 0, 100);

  motionDetected = digitalRead(PIR_PIN) == HIGH;

  // This is an initial threshold, not a calibrated value.
  // Adjust after comparing dry and wet sensor readings.
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
// LEDS AND BUZZER
// ============================================
void updateIndicators() {
  // Turn all level LEDs off before selecting one.
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

  Serial.print(" | Water sensor ADC: ");
  Serial.print(waterSensorValue);

  Serial.print(" | Water contact: ");
  Serial.print(waterDetected ? "DETECTED" : "NOT DETECTED");

  Serial.print(" | Motion: ");
  Serial.println(motionDetected ? "DETECTED" : "NONE");
}

// ============================================
// JSON LINE FOR scripts/arduino_serial_bridge.py
// One self-contained JSON object per line. The bridge script parses each
// serial line independently, so this must stay on its own println-terminated
// line, separate from printStatus() above.
// ============================================
void sendTelemetryJSON() {
  Serial.print("{\"station_code\":\"");
  Serial.print(STATION_CODE);
  Serial.print("\",\"water_level_percent\":");
  Serial.print(levelPercent);
  Serial.println("}");
}
