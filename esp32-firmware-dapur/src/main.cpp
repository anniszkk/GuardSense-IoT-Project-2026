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

// Ambang awal. Nilai final ditentukan setelah pengujian.
float GAS_RATE_THRESHOLD = 5.0;   // unit ADC per detik
float TEMP_RATE_THRESHOLD = 0.5;  // derajat C per detik

float lastGasValue = 0;
float lastTempValue = 0;
bool hasPreviousReading = false;

unsigned long lastReadMillis = 0;    // jadwal baca sensor (tiap 2 detik)
unsigned long lastSampleMillis = 0;  // waktu sampel VALID terakhir, dasar hitung laju
unsigned long lastPublishMillis = 0; // waktu pesan terakhir terkirim (lonjakan atau heartbeat)

// Saat tenang tetap kirim satu pesan tiap 10 detik (heartbeat), supaya server tahu
// node ini masih hidup (server menganggap online bila ada pesan dalam 15 detik).
const unsigned long HEARTBEAT_MS = 10000;

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

    String clientId =
        String(PROJECT_ID) + "-" + String(DEVICE_ID);

    if (mqttClient.connect(clientId.c_str())) {
      Serial.println(" tersambung!");
    } else {
      Serial.print(" gagal, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" coba lagi 2 detik...");
      delay(2000);
    }
  }
}

// Catatan: hasil ini adalah ADC mentah, bukan ppm terkalibrasi.
float readGasPpmEstimate() {
  return (float)analogRead(MQ2_PIN);
}

void publishReading(
    float gasValue,
    float gasRate,
    float tempC,
    float tempRate
) {
  String topic = String("guardsense/") + PROJECT_ID +
                 "/edge/" + DEVICE_ID + "/env";

  String payload = String("{\"device_id\":\"") + DEVICE_ID +
                   "\",\"gas_ppm_est\":" + String(gasValue, 2) +
                   ",\"gas_rate_of_rise\":" + String(gasRate, 2) +
                   ",\"temperature_c\":" + String(tempC, 2) +
                   ",\"temp_rate_of_rise\":" + String(tempRate, 2) + "}";
  // Tanpa timestamp: millis() hanya waktu sejak nyala, bukan epoch.
  // Server mencatat waktu saat pesan tiba.

  bool success = mqttClient.publish(topic.c_str(), payload.c_str());

  if (success) {
    Serial.println("Terkirim ke " + topic);
    Serial.println(payload);
  } else {
    Serial.println("Gagal mengirim data MQTT.");
  }
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  Serial.println("=== GuardSense Gas-Suhu ===");
  Serial.print("Device: ");
  Serial.println(DEVICE_ID);

  connectWiFi();
}

void loop() {
  if (!mqttClient.connected()) {
    connectMQTT();
  }

  mqttClient.loop();

  unsigned long now = millis();

  // Membaca sensor setiap dua detik.
  if (now - lastReadMillis < 2000) {
    return;
  }

  lastReadMillis = now;

  float gasValue = readGasPpmEstimate();
  float tempC = dht.readTemperature();

  if (isnan(tempC)) {
    Serial.println("Gagal membaca DHT22. Sampel dilewati.");
    return;
  }

  // Selang dihitung dari sampel valid terakhir, supaya sampel yang
  // dilewati tidak membuat laju terlihat dua kali lebih besar.
  float dtSeconds = hasPreviousReading
      ? (now - lastSampleMillis) / 1000.0
      : 0.0;
  lastSampleMillis = now;

  float gasRate = 0.0;
  float tempRate = 0.0;

  // Sampel pertama hanya menjadi baseline.
  if (hasPreviousReading && dtSeconds > 0.0) {
    gasRate = (gasValue - lastGasValue) / dtSeconds;
    tempRate = (tempC - lastTempValue) / dtSeconds;
  }

  lastGasValue = gasValue;
  lastTempValue = tempC;
  hasPreviousReading = true;

  // Tahap 1: pre-filtering di ESP32.
  bool gasRising = gasRate >= GAS_RATE_THRESHOLD;
  bool tempRising = tempRate >= TEMP_RATE_THRESHOLD;

  Serial.println("------------------------------");
  Serial.printf("Gas ADC: %.2f\r\n", gasValue);
  Serial.printf("Suhu: %.2f C\r\n", tempC);
  Serial.printf("Laju gas: %.2f ADC/detik\r\n", gasRate);
  Serial.printf("Laju suhu: %.2f C/detik\r\n", tempRate);
  Serial.printf("Gas melewati ambang: %s\r\n",
                gasRising ? "YA" : "TIDAK");
  Serial.printf("Suhu melewati ambang: %s\r\n",
                tempRising ? "YA" : "TIDAK");

  // Kirim jika salah satu indikator melewati ambang, atau sebagai heartbeat.
  if (gasRising || tempRising || now - lastPublishMillis >= HEARTBEAT_MS) {
    publishReading(gasValue, gasRate, tempC, tempRate);
    lastPublishMillis = now;
  }
}