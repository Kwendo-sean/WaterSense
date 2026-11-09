#include <Wire.h>
#include <esp32-hal-rgb-led.h>
#include <U8g2lib.h>

// WaterSense ESP32-S3 N16R8 hardware diagnostic.
// Relay and pump must remain disconnected during this diagnostic.

#define WATER_SENSOR_PIN 4
#define WATER_SENSOR_POWER_PIN 5
#define OLED_SDA_PIN 8
#define OLED_SCL_PIN 9
#define FLOW_SENSOR_PIN 16
#define ULTRASONIC_TRIG_PIN 17
#define ULTRASONIC_ECHO_PIN 18
#define BUZZER_PIN 42
#define RGB_LED_PIN 48

volatile uint32_t flowPulses = 0;
U8G2_SH1106_128X64_NONAME_F_HW_I2C oled(
  U8G2_R0, U8X8_PIN_NONE, OLED_SCL_PIN, OLED_SDA_PIN
);

void IRAM_ATTR countFlowPulse() {
  flowPulses++;
}

float readDistanceCm() {
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  delayMicroseconds(3);
  digitalWrite(ULTRASONIC_TRIG_PIN, HIGH);
  delayMicroseconds(20);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);
  unsigned long duration = pulseIn(ULTRASONIC_ECHO_PIN, HIGH, 60000);
  return duration == 0 ? -1.0f : duration * 0.0343f / 2.0f;
}

void setRgb(uint8_t red, uint8_t green, uint8_t blue) {
  rgbLedWrite(RGB_LED_PIN, red, green, blue);
}

bool detectOled() {
  for (uint8_t address : {0x3C, 0x3D}) {
    Wire.beginTransmission(address);
    if (Wire.endTransmission() == 0) return true;
  }
  return false;
}

void showTelemetry(float distance, int waterRaw, uint32_t pulses) {
  char line[24];
  oled.clearBuffer();
  oled.setFont(u8g2_font_6x10_tr);
  oled.drawStr(0, 9, "WATERSENSE LIVE TEST");
  oled.drawHLine(0, 12, 128);

  if (distance < 0) {
    oled.drawStr(0, 27, "LEVEL: NO ECHO");
  } else {
    snprintf(line, sizeof(line), "DIST: %.1f cm", distance);
    oled.drawStr(0, 27, line);
  }

  snprintf(line, sizeof(line), "WATER: %d %s", waterRaw,
           waterRaw > 500 ? "WET" : "DRY");
  oled.drawStr(0, 41, line);

  snprintf(line, sizeof(line), "FLOW: %lu pulse/s", (unsigned long)pulses);
  oled.drawStr(0, 54, line);
  oled.drawStr(0, 64, "RELAY/PUMP DISCONNECTED");
  oled.sendBuffer();
}

void setup() {
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);
  pinMode(WATER_SENSOR_POWER_PIN, OUTPUT);
  digitalWrite(WATER_SENSOR_POWER_PIN, LOW);
  pinMode(WATER_SENSOR_PIN, INPUT);
  pinMode(FLOW_SENSOR_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(FLOW_SENSOR_PIN), countFlowPulse, FALLING);
  pinMode(ULTRASONIC_TRIG_PIN, OUTPUT);
  pinMode(ULTRASONIC_ECHO_PIN, INPUT);
  digitalWrite(ULTRASONIC_TRIG_PIN, LOW);

  Serial.begin(115200);
  delay(800);
  Serial.println("WATERSENSE_DIAGNOSTIC_START");
  Serial.println("RELAY_AND_PUMP=DISCONNECTED");
  Serial.println("FLOW_SIGNAL_PIN=GPIO16");

  setRgb(40, 0, 0); delay(250);
  setRgb(0, 40, 0); delay(250);
  setRgb(0, 0, 40); delay(250);
  setRgb(0, 0, 0);
  Serial.println("RGB_TEST=COMPLETE");

  Wire.begin(OLED_SDA_PIN, OLED_SCL_PIN, 100000);
  Serial.print("OLED_I2C=");
  Serial.println(detectOled() ? "DETECTED" : "NOT_FOUND");
  oled.setBusClock(100000);
  oled.begin();

  tone(BUZZER_PIN, 1800, 180);
  delay(250);
  noTone(BUZZER_PIN);
  digitalWrite(BUZZER_PIN, LOW);
  Serial.println("BUZZER_TEST=COMPLETE");

}

void loop() {
  float distance = readDistanceCm();
  // Power the low-current contact board only for the measurement. This frees
  // a real 3V3 header for the ultrasonic module and reduces probe corrosion.
  digitalWrite(WATER_SENSOR_POWER_PIN, HIGH);
  delay(20);
  int waterRaw = analogRead(WATER_SENSOR_PIN);
  digitalWrite(WATER_SENSOR_POWER_PIN, LOW);
  noInterrupts();
  uint32_t pulses = flowPulses;
  flowPulses = 0;
  interrupts();

  Serial.print("DISTANCE_CM=");
  if (distance < 0) Serial.print("NO_ECHO");
  else Serial.print(distance, 1);
  Serial.print(" WATER_RAW=");
  Serial.print(waterRaw);
  Serial.print(" FLOW_PIN_LEVEL=");
  Serial.print(digitalRead(FLOW_SENSOR_PIN));
  Serial.print(" FLOW_PULSES_PER_SEC=");
  Serial.println(pulses);

  if (distance < 0) setRgb(40, 0, 0);
  else if (waterRaw > 400) setRgb(40, 20, 0);
  else setRgb(0, 40, 0);

  showTelemetry(distance, waterRaw, pulses);

  delay(1000);
}
