#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>
#include "wifi_secrets.h"   // copy wifi_secrets.example.h to wifi_secrets.h and fill it in

// WaterSense Wi-Fi check for a bare ESP32-S3: no sensors, nothing wired.
// Joins Wi-Fi and calls the WaterSense health endpoint every 5 seconds, so we
// know the board can reach the server before moving the real rig off USB.
// It only reads; nothing is written to any station.
//
// Built-in RGB LED (GPIO 48):
//   blue  = joining Wi-Fi
//   green = server answered
//   red   = Wi-Fi up but the server did not answer

const char* HEALTH_URL = "https://watersense.selenos.world/api/v1/health";
const int RGB_PIN = 48;

unsigned long lastCheck = 0;
int ok = 0, failed = 0;

void led(uint8_t r, uint8_t g, uint8_t b) { rgbLedWrite(RGB_PIN, r, g, b); }

void joinWifi() {
  led(0, 0, 30);
  Serial.printf("Joining \"%s\"", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  unsigned long started = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - started < 20000) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("WIFI OK  ip=%s  signal=%d dBm\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
  } else {
    Serial.println("WIFI FAILED: check the name and password, and that it is 2.4 GHz");
    led(30, 0, 0);
  }
}

void checkServer() {
  WiFiClientSecure tls;
  // Demo shortcut: encrypted but the certificate is not verified.
  tls.setInsecure();
  HTTPClient http;
  http.setTimeout(8000);
  unsigned long t = millis();
  http.begin(tls, HEALTH_URL);
  int code = http.GET();
  unsigned long ms = millis() - t;
  if (code == 200) {
    ok++;
    led(0, 30, 0);
    Serial.printf("SERVER OK  %lu ms  %s  (ok %d / failed %d)\n", ms, http.getString().c_str(), ok, failed);
  } else {
    failed++;
    led(30, 0, 0);
    Serial.printf("SERVER FAILED  code=%d %s  (ok %d / failed %d)\n", code, http.errorToString(code).c_str(), ok, failed);
  }
  http.end();
}

void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("WATERSENSE WIFI TEST");
  joinWifi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    joinWifi();
    return;
  }
  if (millis() - lastCheck >= 5000) {
    lastCheck = millis();
    checkServer();
  }
}
