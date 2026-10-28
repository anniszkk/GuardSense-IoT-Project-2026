# edge-audio/ — PIC: Annis

Script Python yang jalan di HP A & HP B lewat Termux. Merekam audio **terus-menerus**
dan mengirim klip 3 detik (tiap 2 detik, tumpang-tindih 1 detik) ke MQTT selama klip itu
tidak hening. Pembeda kaca vs suara lain dikerjakan di `processing-server/` (YAMNet).

Lihat `docs/GuardSense_Dokumen_Proyek.md`: Bab 4.1 (mikrofon), 5.1 (pre-filter), 5.2.1 dan
5.2.1.1 (klasifikasi + liveness; jalan di laptop), 9.1 (hasil uji dan kalibrasi).

## File

| File | Isi |
|---|---|
| `hp_edge.py` | Program utama di HP: mode `continuous` (default) dan `window` (cadangan) |
| `continuous_capture.py` | Rekam opus tanpa henti, baca bagian baru file, potong klip 3 detik |
| `prefilter.py` | RMS dan frekuensi dominan (gerbang RMS 0,005 hanya membuang keheningan) |
| `test_prefilter_local.py` | Alat bantu menghitung RMS dan frekuensi dominan file `.wav` di laptop |
| `samples/`, `samples1/` | Rekaman uji: kaca pecah dan non-event (sampel publik + rekaman HP `kaca4-8`, `negatif1-9`) |

## Setup di HP (Termux)

```bash
pkg update && pkg install python git termux-api ffmpeg
pip install paho-mqtt python-dotenv numpy
```

Aplikasi **Termux:API** (bukan cuma paketnya) harus terpasang dari F-Droid, dan izin
mikrofon diberikan ke aplikasi itu.

Salin `.env.example` jadi `.env` di root repo, lalu isi:

```
PROJECT_ID=<nama unik kelompok>     # HARUS sama di HP A, HP B, dan laptop. Jangan pakai default.
DEVICE_ID=hpA                       # hpA di HP pertama, hpB di HP kedua
```

`PROJECT_ID` ikut membentuk nama topic MQTT. Klip audio dikirim lewat broker publik,
jadi nama yang mudah ditebak berarti audio rumah bisa didengar orang lain.

## Menjalankan

Dari folder `edge-audio` (skrip mengimpor `shared/` lewat path relatif):

```bash
termux-wake-lock
python hp_edge.py
```

HP kedua: `DEVICE_ID=hpB python hp_edge.py` (atau tulis di `.env`).

Mode `window` (rekam 2 detik, berhenti, ulang; punya jeda tak terekam sekitar 1,3–2,5 detik)
hanya sebagai cadangan:

```bash
EDGE_MODE=window python hp_edge.py
```

Beberapa hal yang perlu diperhatikan:
- `termux-microphone-record` **wajib** diberi `-r 16000`. Tanpa itu Termux merekam di 8 kHz dan
  semua suara di atas 4 kHz (ciri kaca pecah) hilang. `hp_edge.py` sudah memakainya.
- File rekaman (`_rec_live.ogg`) dimulai ulang tiap sekitar 30 menit, dengan celah rekam
  beberapa detik.
- HP sebaiknya dicolok ke charger, dan Termux dikecualikan dari optimasi baterai.

## Uji rekam manual

```bash
termux-microphone-record -f ~/tes.ogg -l 10 -e opus -r 16000 -b 96 -c 1
ffprobe -v error -show_entries stream=sample_rate -of default=nw=1 ~/tes.ogg
```

Sample rate di `ffprobe` untuk opus selalu terbaca 48000 (normal). Untuk memindahkan rekaman ke
laptop: `termux-setup-storage`, lalu `cp ~/tes.ogg ~/storage/downloads/`. Nilai rekaman itu dengan
`processing-server/test_recording.py`.

## Jika bermasalah

| Gejala | Penyebab umum |
|---|---|
| `File rekaman kosong/tidak tumbuh` | Termux:API belum terpasang atau izin mikrofon belum diberikan |
| `Masih ada rekaman lama nyangkut` | Jalankan `termux-microphone-record -q`, lalu ulangi |
| Server tidak menerima apa pun | `PROJECT_ID` HP dan laptop berbeda |
| Skor kaca selalu 0 | Rekaman 8 kHz (opsi `-r` hilang), cek dengan `ffprobe` |
