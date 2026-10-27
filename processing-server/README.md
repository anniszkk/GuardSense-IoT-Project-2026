# processing-server/ — PIC: Lila (orkestrasi), Annis & Binar (isi klasifikasi)

Jalan di laptop. Subscribe semua topic MQTT dari edge-audio dan esp32-firmware,
jalankan klasifikasi tahap 2, publish hasil ke topic alert, dan host dashboard.

Lihat `docs/GuardSense_Dokumen_Proyek.docx` Bab 5.2, 5.3, 6, 7.

## Setup

```bash
python -m pip install -r requirements.txt
```

## File

| File | Isi | PIC |
|---|---|---|
| `server.py` | Orkestrasi: subscribe topic, panggil fungsi klasifikasi, publish alert, jalankan dashboard | Lila |
| `classify_audio.py` | Klasifikasi pecahan kaca (rule-based dan/atau YAMNet) + liveness check | Annis |
| `classify_fire.py` | Klasifikasi kebakaran (korelasi gas-suhu) + estimasi lokasi sumber | Binar |

## Jalankan

```bash
python server.py
```

Buka `http://localhost:8000` untuk dashboard.
