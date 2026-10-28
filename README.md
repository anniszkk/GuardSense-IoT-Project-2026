# GuardSense

Sistem deteksi dini **pecahan kaca** dan **kebakaran** berbasis multisensor untuk rumah.

Dua jalur sensor bekerja bersama:

- **Audio (2 HP Android sebagai mikrofon).** Klip suara 3 detik dikirim ke server, lalu diklasifikasi dengan
  YAMNet (model AI pre-trained) menjadi pecahan kaca atau alarm asap. Ada pemeriksaan tambahan supaya
  suara TV atau musik tidak langsung dianggap kaca pecah.
- **Gas dan suhu (2 ESP32 dengan MQ-2 dan DHT22, di dapur dan kamar).** Firmware menghitung laju kenaikan
  gas dan suhu. Kebakaran ditetapkan bila keduanya naik bersamaan, dan lokasi sumber dipilih dari node
  dengan kenaikan gas tercepat.

Semua data lewat broker MQTT (HiveMQ), diolah di server Python di laptop, dan ditampilkan di dashboard web
(status sistem, kartu perangkat, grafik telemetri, riwayat kejadian).

```
HP A (mic)  ──┐
HP B (mic)  ──┼─> MQTT broker (HiveMQ) <─> processing-server (laptop) ─> dashboard (localhost:8000)
ESP32 dapur ──┤                                       │
ESP32 kamar ──┘                                       └─> alert dipublikasikan kembali ke broker
```

Penjelasan lengkap (sensor, algoritma, hasil uji, batasan) ada di
[`docs/GuardSense_Dokumen_Proyek.md`](docs/GuardSense_Dokumen_Proyek.md).

## Cara menjalankan

Yang dibutuhkan: Python 3.10 atau lebih baru, koneksi internet (broker publik HiveMQ), dan untuk bagian
perangkat: HP Android dengan Termux dan Termux:API (dari F-Droid), serta VS Code dengan ekstensi
PlatformIO dan Wokwi.

### 1. Pengaturan bersama

Salin `.env.example` menjadi `.env`, lalu isi `PROJECT_ID` dengan nama unik kelompok. Nilai ini ikut
membentuk nama topic MQTT, jadi harus **sama** di laptop, HP, dan firmware ESP32
(`esp32-firmware-*/src/config.h`). Jangan dibiarkan default karena broker bersifat publik.

### 2. Server dan dashboard (laptop)

```bash
cd processing-server
python -m venv venv
venv\Scripts\activate
python -m pip install -r requirements.txt
python server.py
```

Dashboard terbuka di <http://localhost:8000>. Perangkat lain di WiFi yang sama bisa membukanya lewat
alamat IP laptop. Unduhan TensorFlow cukup besar, dan model YAMNet diunduh saat klip audio pertama masuk.
Tanpa TensorFlow, server tetap jalan dengan klasifikasi cadangan berbasis aturan.

### 3. Mikrofon (HP A dan HP B)

Di Termux:

```bash
pkg update && pkg install python git termux-api ffmpeg
cd edge-audio
pip install -r requirements.txt
termux-wake-lock
python hp_edge.py
```

HP kedua dijalankan dengan `DEVICE_ID=hpB python hp_edge.py`. Detail pengaturan izin mikrofon ada di
`edge-audio/README.md`.

### 4. ESP32 (simulasi Wokwi)

Buka folder `esp32-firmware-dapur` (atau `esp32-firmware-kamar`) di VS Code, build lewat PlatformIO
(`Ctrl+Alt+B`), lalu tekan `F1` dan pilih **Wokwi: Start Simulator**. Klik komponen MQ-2 dan DHT22 untuk
menggeser nilai gas dan suhu. Satu jendela VS Code menjalankan satu node.

### 5. Uji tanpa perangkat

Dari folder `processing-server`, dengan virtual environment aktif:

```bash
python test_liveness_b.py              # uji logika dua HP dan alarm (11 skenario)
python publish_env.py bahaya           # kirim pesan gas-suhu palsu ke server yang sedang jalan
python demo_lokasi.py --simulasi       # demo estimasi lokasi sumber asap
python test_recording.py rekaman.wav   # nilai rekaman sendiri (butuh ffmpeg)
```

## Struktur folder

```
GuardSense/
├── edge-audio/              Skrip HP (Termux): rekam terus-menerus, kirim klip 3 detik tiap 2 detik
│   ├── hp_edge.py           program utama
│   ├── continuous_capture.py, prefilter.py
│   └── samples*/            sampel suara uji (kaca, non-event, alarm, bunyi dering rumah tangga)
├── esp32-firmware-dapur/    Proyek PlatformIO + diagram Wokwi untuk node dapur
├── esp32-firmware-kamar/    Sama, untuk node kamar (hanya DEVICE_ID yang berbeda)
├── processing-server/       Server Python di laptop
│   ├── server.py            MQTT, liveness, cooldown, alert, API dan hosting dashboard
│   ├── classify_audio.py    YAMNet, pola beep, klasifikasi kaca dan alarm
│   ├── classify_fire.py     korelasi gas-suhu dan estimasi lokasi sumber
│   └── test_*.py, publish_env.py, demo_lokasi.py
├── dashboard/               Halaman web (index.html dan assets)
├── shared/                  Kode bersama: koneksi MQTT, skema pesan, fitur audio
├── docs/                    Dokumen proyek (arsitektur, algoritma, hasil uji)
└── .env.example             contoh pengaturan PROJECT_ID dan broker
```

## Pembuat

Dikerjakan oleh kelompok GuardSense:

| Nama | Bagian |
|---|---|
| **Annis Fakhiroh Akbar** | Jalur audio: edge-audio, klasifikasi pecahan kaca dan alarm asap |
| **Binar** | Jalur gas dan suhu: firmware ESP32 (MQ-2, DHT22), klasifikasi kebakaran |
| **Lila** | Integrasi: processing-server, cloud/MQTT, dashboard |
