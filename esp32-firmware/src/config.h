// PIC: Binar. Isi nilai-nilai ini (jangan commit WiFi password asli ke Git publik
// kalau pakai hardware beneran — untuk Wokwi, SSID "Wokwi-GUEST" tidak butuh password).

#pragma once

// --- WiFi ---
// Di simulasi Wokwi, WiFi virtual sudah tersedia otomatis lewat SSID ini:
#define WIFI_SSID "Wokwi-GUEST"
#define WIFI_PASSWORD ""

// --- MQTT (samakan dengan .env di root project) ---
#define MQTT_HOST "broker.hivemq.com"
#define MQTT_PORT 8883  // TLS. Untuk simulasi awal boleh pakai 1883 (tanpa TLS) dulu
                         // kalau library TLS di ESP32 terasa ribet buat tahap belajar.

// TODO: ganti sesuai nama kelompok, HARUS sama dengan PROJECT_ID di .env Python
#define PROJECT_ID "guardsense_kelompok_XX"

// TODO: ganti "esp32_dapur" di satu board, "esp32_kamar" di board satunya
#define DEVICE_ID "esp32_dapur"

// --- Pin sensor (sesuaikan dengan diagram.json) ---
#define DHT_PIN 4
#define DHT_TYPE DHT22
#define MQ2_PIN 34  // analog pin
