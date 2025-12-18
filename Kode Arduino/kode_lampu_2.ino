#include <Wire.h>
#include <BH1750.h>
#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <ArduinoJson.h>

// ================= WIFI =================
const char* ssid = "RsiaDwnt";
const char* password = "kismissss";

// ================= SERVER =================
const char* URL_LIGHT_STATUS   = "http://103.151.63.68:8014/api/light-status/";
const char* URL_AI_DECISION    = "http://103.151.63.68:8014/api/lighting-decision/";

// ================= PIN =================
#define RELAY_PIN D5
#define SDA_PIN   D2
#define SCL_PIN   D1

// ================= OBJECT =================
BH1750 lightMeter;

// ================= VAR =================
String mode  = "AUTO";   // AUTO / MANUAL
String lampu = "OFF";    // ON / OFF
float lux    = 0;

// =================================================
void setup() {
  Serial.begin(115200);

  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, HIGH); // relay OFF

  Wire.begin(SDA_PIN, SCL_PIN);
  lightMeter.begin(BH1750::CONTINUOUS_HIGH_RES_MODE);

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi Connected");
}

// =================================================
void loop() {

  // 1️⃣ Ambil MODE & STATUS dari server
  fetchLightStatus();

  // 2️⃣ Baca lux
  lux = lightMeter.readLightLevel();
  if (lux <= 0 || lux > 65535) {
    Serial.println("Lux invalid, skip processing");
    delay(3000);
    return;
  }

  // 3️⃣ MODE MANUAL
  if (mode == "MANUAL") {
    if (lampu == "ON") relayOn();
    else relayOff();
  }

  // 4️⃣ MODE AUTO
  else if (mode == "AUTO") {
    sendLuxToAI(lux);
    fetchLightStatus();   // ambil keputusan AI
    if (lampu == "ON") relayOn();
    else relayOff();
  }

  Serial.printf("Mode: %s | Lux: %.2f | Lampu: %s\n",
                mode.c_str(), lux, lampu.c_str());

  delay(5000);
}

// =================================================
void fetchLightStatus() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi not connected, skip fetchLightStatus");
    return;
  }

  HTTPClient http;
  WiFiClient client;
  http.begin(client, URL_LIGHT_STATUS);

  int retries = 3;
  int httpCode = -1;
  while (retries > 0) {
    httpCode = http.GET();
    if (httpCode > 0) break; // berhasil
    Serial.println("HTTP GET failed, retrying...");
    retries--;
    delay(500);
  }

  if (httpCode > 0) {
    String payload = http.getString();
    Serial.println("Response server:");
    Serial.println(payload);

    StaticJsonDocument<200> doc;
    DeserializationError error = deserializeJson(doc, payload);

    if (error) {
      Serial.print("deserializeJson() failed: ");
      Serial.println(error.c_str());
      http.end();
      return;
    }

    // Gunakan default value lama jika parsing gagal
    mode  = doc["mode"] | mode;
    lampu = doc["status"] | lampu;

    Serial.printf("Parsed Mode: %s | Parsed Lampu: %s\n", mode.c_str(), lampu.c_str());
  } else {
    Serial.print("HTTP GET failed after retries, code: ");
    Serial.println(httpCode);
  }

  http.end();
}

// =================================================
void sendLuxToAI(float luxVal) {
  if (WiFi.status() != WL_CONNECTED) return;

  HTTPClient http;
  WiFiClient client;
  http.begin(client, URL_AI_DECISION);
  http.addHeader("Content-Type", "application/json");

  StaticJsonDocument<100> doc;
  doc["ambient_light_lux"] = luxVal;

  String body;
  serializeJson(doc, body);

  int httpCode = http.POST(body);
  if (httpCode > 0) {
    Serial.print("POST response code: ");
    Serial.println(httpCode);
  } else {
    Serial.print("POST failed, error: ");
    Serial.println(http.errorToString(httpCode).c_str());
  }

  http.end();
}

// =================================================
void relayOn() {
  digitalWrite(RELAY_PIN, LOW);
}

void relayOff() {
  digitalWrite(RELAY_PIN, HIGH);
}
