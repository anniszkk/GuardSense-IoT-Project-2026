# GuardSense

Sistem Deteksi Dini Pecahan Kaca dan Kebakaran Berbasis Multisensor.
Dokumen lengkap (arsitektur, sensor, algoritma, pengujian) ada di `docs/GuardSense_Dokumen_Proyek.docx`.

## Struktur folder

| Folder | Isi | PIC |
|---|---|---|
| `edge-audio/` | Script Python untuk HP A & HP B (Termux) — rekam audio, hitung RMS amplitudo, kirim ke MQTT | **Annis** |
| `esp32-firmware/` | Project PlatformIO untuk ESP32 + MQ-2 + DHT22 (dua instance: dapur & kamar), bisa disimulasikan di Wokwi langsung dari VS Code | **Binar** |
| `processing-server/` | Server Python di laptop — subscribe semua topic MQTT, jalankan klasifikasi (audio & gas/suhu), publish status alert, host dashboard | **Lila** (orkestrasi) + Annis/Binar (isi fungsi klasifikasi masing-masing) |
| `dashboard/` | Halaman web dashboard (status real-time, riwayat event) | **Lila** |
| `shared/` | Kode yang dipakai bersama (koneksi MQTT, skema pesan) — jangan diduplikasi di folder lain | Semua |
| `docs/` | Dokumen proyek, diagram, catatan | Semua |

## Cara mulai (tiap orang)

1. Clone repo ini, `cd GuardSense`.
2. Baca README di folder bagianmu masing-masing dulu sebelum mulai ngoding.
3. Salin `.env.example` jadi `.env`, isi `PROJECT_ID` dengan nama unik kelompok (jangan dibiarkan default, supaya topic MQTT tidak bercampur dengan kelompok lain).
4. Ikuti TODO yang ada di tiap file stub.

## Alur data singkat

```
HP A (mic)  ──┐
HP B (mic)  ──┼─> MQTT Broker (HiveMQ) <─> processing-server (laptop) ─> dashboard
ESP32 dapur ──┤         (cloud)                  │
ESP32 kamar ──┘                                  └─> publish alert kembali ke broker
```

Detail lengkap ada di `docs/GuardSense_Dokumen_Proyek.docx` Bab 3 (Arsitektur) dan Bab 10 (Pembagian Tugas).
