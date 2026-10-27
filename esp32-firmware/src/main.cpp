// PIC: Binar
// Firmware ESP32: baca MQ-2 + DHT22, hitung rate-of-rise, publish ke MQTT
// kalau lolos ambang (pre-filtering tahap 1 -- lihat docx Bab 5.1).
//
// Jalan di simulasi Wokwi (F1 -> "Wokwi: Start Simulator") TANPA hardware fisik.
// Begitu ESP32 asli datang, cukup upload lewat PlatformIO, kode ini tidak perlu diubah
// (asal wiring fisik pin-nya sama dengan config.h).

#include <WiFi.h>
#include <PubSubClient.h>
#include <DHT.h>
#include "config.h"

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
DHT dht(DHT_PIN, DHT_TYPE);

// TODO (Binar): kalibrasi dua nilai ini lewat pengujian (docx Bab 5.1, Bab 9 skenario 6-7)
float GAS_RATE_THRESHOLD = 5.0;   // satuan: unit ADC per detik, sesuaikan
float TEMP_RATE_THRESHOLD = 0.5;  // satuan: derajat C per detik

float lastGasValue = 0;
float lastTempValue = 0;
unsigned long lastReadMillis = 0;

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("Menyambung ke WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(300);
    Serial.print(".");
  }
  Serial.println(" tersambung!");
}

void connectMQTT() {
  mqttClient.setServer(MQTT_HOST, MQTT_PORT);
  while (!mqttClient.connected()) {
    Serial.print("Menyambung ke MQTT broker...");
    String clientId = String(PROJECT_ID) + "-" + String(DEVICE_ID);
    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(" tersambung!");
    } else {
      Serial.print(" gagal, rc="); Serial.print(mqttClient.state());
      Serial.println(" coba lagi 2 detik...");
      delay(2000);
    }
  }
}

// TODO (Binar): kalibrasi konversi nilai ADC mentah MQ-2 ke estimasi ppm
// (lihat datasheet MQ-2 / contoh kalibrasi umum di internet).
float readGasPpmEstimate() {
  int raw = analogRead(MQ2_PIN);
  // placeholder sederhana -- HARUS diganti dengan kalibrasi nyata
  return (float)raw;
}

void publishReading(float gasPpm, float gasRate, float tempC, float tempRate) {
  String topic = String("guardsense/") + PROJECT_ID + "/edge/" + DEVICE_ID + "/env";
  String payload = String("{\"device_id\":\"") + DEVICE_ID +
                    "\",\"gas_ppm_est\":" + String(gasPpm, 2) +
                    ",\"gas_rate_of_rise\":" + String(gasRate, 2) +
                    ",\"temperature_c\":" + String(tempC, 2) +
                    ",\"temp_rate_of_rise\":" + String(tempRate, 2) +
                    ",\"timestamp\":" + String(millis()) + "}";
  mqttClient.publish(topic.c_str(), payload.c_str());
  Serial.println("Terkirim: " + payload);
}

void setup() {
  Serial.begin(115200);
  dht.begin();
  connectWiFi();
}

void loop() {
  if (!mqttClient.connected()) {
    connectMQTT();
  }
  mqttClient.loop();

  unsigned long now = millis();
  if (now - lastReadMillis >= 2000) {  // baca tiap 2 detik
    float dtSeconds = (now - lastReadMillis) / 1000.0;
    lastReadMillis = now;

    float gasPpm = readGasPpmEstimate();
    float tempC = dht.readTemperature();

    if (isnan(tempC)) {
      Serial.println("Gagal baca DHT22!");
      return;
    }

    // Tahap 1: hitung rate-of-rise (lihat docx Bab 5.1)
    float gasRate = (gasPpm - lastGasValue) / dtSeconds;
    float tempRate = (tempC - lastTempValue) / dtSeconds;
    lastGasValue = gasPpm;
    lastTempValue = tempC;

    // Kirim hanya kalau salah satu laju kenaikan lewat ambang
    if (gasRate > GAS_RATE_THRESHOLD || tempRate > TEMP_RATE_THRESHOLD) {
      publishReading(gasPpm, gasRate, tempC, tempRate);
    }
  }
}
