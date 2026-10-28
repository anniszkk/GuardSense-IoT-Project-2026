# dashboard/ — PIC: Lila

Halaman web yang di-serve oleh `processing-server/server.py` di `http://0.0.0.0:8000` (akses lokal via `http://localhost:8000`).
Bisa diakses dari perangkat lain (HP / laptop) yang berada di WiFi/hotspot yang sama sesuai Bab 7 dokumen proyek.

## Status Implementasi

- [x] Tampilkan status tiap edge device (Normal / Alert / Offline / Verifikasi) real-time (`hpA`, `hpB`, `esp32_dapur`, `esp32_kamar`).
- [x] Tampilkan riwayat event dengan timestamp, level, jenis kejadian, sumber, lokasi terduga, akurasi, dan keterangan alasan (liveness TV/media, pola beep, kenaikan gas-suhu).
- [x] Grafik real-time amplitudo audio (RMS hpA & hpB), laju gas (RoR dapur & kamar), serta suhu ruangan (°C).
- [x] Metode koneksi: Menggunakan polling endpoint lokal (`/api/state`, `/api/events`, `/api/telemetry`) setiap 1.5 detik ke `processing-server`.
  - **Alasan pemilihan polling endpoint lokal daripada WebSocket MQTT:**
    1. **Stabilitas demo tanpa internet stabil:** Saat pengujian atau presentasi di jaringan lokal (hotspot HP / lab kampus tanpa akses internet keluar ke port 8884 WSS HiveMQ), dashboard tetap dapat berkomunikasi dengan processing server laptop tanpa terhalang firewall/proxy.
    2. **Orkestrasi terpusat:** Processing server sudah melakukan filtering liveness A & B, cooldown, dan korelasi gas-suhu, sehingga dashboard menerima status yang sudah diolah dan tervalidasi, bukan payload mentah audio klip (b64) yang berukuran puluhan kilobyte per detik.
    3. **Buffer riwayat:** Server laptop menyimpan riwayat event dan telemetri dalam memory buffer, sehingga saat dashboard dibuka atau di-refresh, grafik dan log langsung terisi lengkap.
