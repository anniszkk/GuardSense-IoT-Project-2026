# processing-server/ — PIC: Lila (orkestrasi), Annis & Binar (isi klasifikasi)

Jalan di laptop. Subscribe semua topic MQTT dari edge-audio dan esp32-firmware,
jalankan klasifikasi tahap 2, publish hasil ke topic alert, dan host dashboard.

Lihat `docs/GuardSense_Dokumen_Proyek.md` Bab 5.2, 5.3, 6, 7 dan 9.1.

## Setup

Disarankan memakai virtual environment:

```bash
python -m venv venv
venv\Scripts\activate          # Windows (PowerShell/cmd)
python -m pip install -r requirements.txt
```

`requirements.txt` memuat TensorFlow dan tensorflow-hub untuk YAMNet (berat; unduhan sekitar
500 MB, model YAMNet diunduh dari TF-Hub saat klip pertama masuk). Jika TensorFlow tidak
terpasang, server tetap jalan dan memakai cadangan rule-based untuk audio (tercatat di log:
`method=rule_hf`).

## File

| File | Isi | PIC |
|---|---|---|
| `server.py` | Orkestrasi: subscribe topic, panggil fungsi klasifikasi, publish alert, cooldown, liveness bagian B, (dashboard menyusul) | Lila |
| `classify_audio.py` | Klasifikasi pecahan kaca: YAMNet (utama, ambang 0,35), rule-based rasio band tinggi (cadangan), liveness A dan fungsi rasio untuk B | Annis |
| `classify_fire.py` | Klasifikasi kebakaran (korelasi gas-suhu) + estimasi lokasi sumber (belum diimplementasikan) | Binar |
| `test_recording.py` | Menilai rekaman sendiri (m4a/mp3/ogg/wav) per window, tanpa MQTT | Annis |
| `test_liveness_b.py` | Uji simulasi liveness bagian B (7 skenario) | Annis |

`test_yamnet_batch.py` dan `test_crosscheck.py` adalah skrip lama yang mencari file `.wav`
(file `.wav` tidak ikut di git), sehingga di clone baru tidak menemukan apa-apa; gunakan
`test_recording.py`.

## Jalankan

```bash
python server.py
```

Server mencetak satu baris per klip: `[audio] hpA -> method=yamnet glass=... conf=... media=...`.
Alert dikirim ke topic `alerts` dengan jenis `glass_break` atau `glass_break_needs_verification`
(field `reason`: `media_context` dan/atau `amplitude_equal`). Alert yang sama untuk HP dan jenis
yang sama diredam 10 detik. Ambang rasio liveness B (1,5) belum dikalibrasi dan bisa diubah lewat
env `LIVENESS_RATIO`.

Dashboard (`http://localhost:8000`) belum dibuat.

## Menguji tanpa HP

```bash
python test_recording.py ..\edge-audio\samples\kaca6.m4a
python test_liveness_b.py
```

Kolom `top3` di `test_recording.py` menunjukkan tiga kelas YAMNet teratas tiap window, berguna
untuk memahami kenapa suatu rekaman tidak terdeteksi.
