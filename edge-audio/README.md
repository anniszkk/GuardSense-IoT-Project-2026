# edge-audio/ — PIC: Annis

Script Python yang jalan di HP A & HP B lewat Termux. Rekam audio, hitung
pre-filter (RMS amplitudo), publish ke MQTT kalau lolos ambang.

Lihat `docs/GuardSense_Dokumen_Proyek.docx`:
- Bab 4.1 (sensor mikrofon)
- Bab 5.1 (pre-filtering tahap 1)
- Bab 5.2.1 & 5.2.1.1 (klasifikasi + liveness check — ini jalan di processing-server,
  bukan di sini, tapi hasil pre-filter dari sini yang jadi inputnya)

## Setup di HP (Termux)

```bash
pkg update && pkg install python git termux-api
pip install paho-mqtt python-dotenv numpy
```

## TODO

- [ ] `hp_edge.py` — ganti `run_device_id` jadi "hpA" di satu HP, "hpB" di HP satunya
- [ ] `prefilter.py` — isi fungsi `compute_rms()` dan tentukan `AMPLITUDE_THRESHOLD`
      lewat kalibrasi pakai sampel suara nyata (lihat Bab 5.1 & Bab 9 skenario 1-3)
- [ ] Setelah pre-filter jalan, sambungkan ke `processing-server/classify_audio.py`
      (klasifikasi + liveness check jalan di laptop, bukan di HP)
