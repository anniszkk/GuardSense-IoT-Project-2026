# esp32-firmware/ — PIC: Binar

Project PlatformIO untuk ESP32 + MQ-2 (gas/asap) + DHT22 (suhu). Dua instance
dibuat dari project ini: satu untuk "dapur", satu untuk "kamar" (ganti `DEVICE_ID`
di `src/config.h`).

Lihat `docs/GuardSense_Dokumen_Proyek.docx`:
- Bab 4.2 & 4.3 (sensor MQ-2 & DHT22)
- Bab 5.1 (pre-filtering rate-of-rise)
- Bab 5.2.2 (klasifikasi kebakaran — sebagian bisa dihitung di sini, sebagian di processing-server)

## Cara jalanin di Wokwi (tanpa hardware fisik dulu)

1. Buka folder `esp32-firmware/` ini di VS Code.
2. Pastikan ekstensi **PlatformIO** dan **Wokwi for VS Code** sudah terpasang (keduanya
   sudah kelihatan di sidebar kamu).
3. Build dulu lewat PlatformIO (ikon centang di status bar bawah, atau `Ctrl+Alt+B`).
4. Tekan `F1` -> ketik "Wokwi: Start Simulator" -> Enter.
5. Simulasi jalan dengan wiring dari `diagram.json`. Klik komponen MQ-2/DHT22 di
   diagram untuk muncul slider nilai gas/suhu manual (dipakai untuk testing skenario
   di Bab 9, No. 6-7 — ganti pemicu fisik dupa/obat nyamuk jadi geser slider).

> **Catatan:** Part ID komponen MQ-2/DHT22 di `diagram.json` ini contoh awal — kalau
> saat dibuka di Wokwi ada yang error/tidak ketemu, klik tombol "+" di editor diagram
> Wokwi, cari "DHT22" / "MQ-2" / "gas sensor", lalu sesuaikan `id` dan pin-nya di
> `diagram.json` dan `src/config.h` supaya cocok.

## Setelah hardware fisik ESP32+MQ-2+DHT22 datang

1. Wiring fisik sesuai pin yang sama dengan `src/config.h`.
2. Sambungkan ESP32 ke laptop lewat USB.
3. PlatformIO -> Upload (bukan Wokwi Simulator lagi). Kode tidak perlu diubah
   kecuali `WIFI_SSID`/`WIFI_PASSWORD` (ganti dari "Wokwi-GUEST" ke WiFi asli).

## TODO

- [ ] Kalibrasi `readGasPpmEstimate()` di `main.cpp` (konversi ADC ke estimasi ppm)
- [ ] Kalibrasi `GAS_RATE_THRESHOLD` dan `TEMP_RATE_THRESHOLD`
- [ ] Verifikasi/benerin part ID di `diagram.json` sesuai yang tersedia di Wokwi
- [ ] Setelah dua instance (dapur & kamar) jalan, test logika lokasi sumber asap
      (dikerjakan di `processing-server/classify_fire.py`, bukan di firmware ini)
