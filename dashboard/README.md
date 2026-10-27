# dashboard/ — PIC: Lila

Halaman web yang di-serve oleh `processing-server/server.py` di `localhost:8000`.
Diakses dari perangkat lain yang berada di WiFi/hotspot yang sama (docx Bab 7).

## TODO

- [ ] Tampilkan status tiap edge device (Normal / Alert) real-time
- [ ] Tampilkan riwayat event dengan timestamp dan lokasi
- [ ] Grafik amplitudo (audio) dan gas/suhu dari waktu ke waktu
- [ ] Sambungkan ke MQTT lewat WebSocket (broker.hivemq.com port 8884 WSS) atau
      polling endpoint dari server.py -- pilih salah satu, catat alasannya di laporan
