Mata Kuliah Internet of Things

**GuardSense**

*Sistem Deteksi Dini Pecahan Kaca dan Kebakaran Berbasis Multisensor*

Dokumen Perencanaan Proyek (untuk diskusi kelompok)

*Diperbarui 28 Oktober 2026: ditambahkan status implementasi dan hasil kalibrasi jalur audio (Bab 4.1, 5.1, 5.2.1, 5.2.1.1, 6.2, 8, 9.1, 10.1). Ditambahkan hasil uji gas-suhu di Wokwi, server, dan dashboard (Bab 4.2, 4.3, 5.1, 5.2.2, 6.2, 7, 8, 9.2, 10.2). Notifikasi ke HP lain belum diperbarui.*

# 1. Masalah dan Ide

## 1.1 Latar Belakang Masalah

Di rumah/kos yang dihuni lebih dari satu orang, penghuni sering berada di ruangan berbeda (kamar, dapur, ruang tamu) sehingga tidak langsung tahu saat terjadi kecelakaan rumah tangga di ruangan lain. Dua jenis kejadian yang jadi fokus GuardSense:

- Kaca pecah secara tidak sengaja — misalnya gelas/piring kaca jatuh, anak kecil tidak sengaja memecahkan jendela/kaca lemari, atau hewan peliharaan (kucing/anjing) tanpa sengaja menyenggol dan memecahkan benda kaca saat pemilik rumah sedang di ruangan lain. Kejadian semacam ini cukup umum terjadi: data klaim asuransi rumah tangga mencatat ribuan klaim akibat kerusakan tidak sengaja oleh hewan peliharaan dalam beberapa tahun terakhir, termasuk kasus jendela pecah akibat anjing menabraknya dan cermin pecah akibat hewan peliharaan menabrak furnitur (Aviva, 2024). Kejadian ini perlu diketahui penghuni lain dengan cepat, baik untuk memastikan tidak ada yang terluka maupun supaya pecahan segera dibersihkan sebelum ada yang terinjak (termasuk oleh hewan peliharaan itu sendiri).

- Kebakaran kecil yang baru terdeteksi setelah membesar, karena tidak ada yang mendengar alarm asap atau mencium bau asap tepat waktu.

Kedua kejadian ini sama-sama jarang terjadi namun selalu butuh respons cepat ketika terjadi, sehingga cocok untuk sistem yang terus memantau di latar belakang dan langsung memberi notifikasi begitu terdeteksi — mirip prinsip pada sistem pemantauan rumah yang mengklasifikasikan suara "kerusakan properti" (property damage), termasuk pecahan kaca, retak, dan suara jatuh, sebagai kategori tersendiri yang terpisah dari kategori keamanan/intrusi, lalu meneruskan notifikasinya ke penghuni (Vivint LLC, paten US10922935B2, "Detecting a premise condition using audio analytics").

## 1.2 Ide Solusi

GuardSense adalah sistem multisensor yang memantau dua titik di rumah/kos (misalnya dapur dan kamar) secara bersamaan untuk:

- Mendeteksi suara pecahan kaca lewat mikrofon HP, sebagai indikasi kecelakaan rumah tangga (bukan indikasi pencurian/intrusi) yang perlu segera diketahui penghuni lain.

- Mendeteksi potensi kebakaran lewat kombinasi bunyi alarm asap (ditangkap mikrofon HP) dengan kadar gas/asap dan suhu (ESP32), dengan filter untuk mengurangi kesalahan deteksi dari asap luar (misalnya bakaran sampah tetangga) yang masuk lewat ventilasi.

Begitu salah satu event terdeteksi dan tervalidasi, sistem mengirim notifikasi real-time ke penghuni lain lewat MQTT, serta menampilkan status dan riwayat kejadian di dashboard lokal. Notifikasi ini berfungsi sebagai pengingat cepat ("ada kaca pecah di dapur, tolong dicek"), bukan alarm keamanan yang memicu tindakan darurat seperti menghubungi pihak berwajib.

## 1.3 Mengapa Berbeda dari Ide Lain

Dibanding draf-draf sejenis yang sudah ada (pemantau ruang belajar, ketersediaan parkir, dll.), GuardSense berfokus pada deteksi event rumah tangga yang jarang-tapi-perlu-respons-cepat, dengan tantangan teknis utama: membedakan event asli dari gangguan sejenis (noise, asap luar) menggunakan kombinasi karakteristik sinyal (amplitudo, frekuensi, rate-of-rise), bukan sekadar threshold tunggal. Fokusnya juga sengaja diarahkan ke keselamatan dan koordinasi antarpenghuni (household safety/notification), bukan ke sistem keamanan anti-pencurian, supaya cakupan algoritma dan skenario pengujian tetap realistis untuk tugas kuliah.

# 2. Pemenuhan Ketentuan Tugas

| **Ketentuan**                           | **Pemenuhan di GuardSense**                                                                                                                                                                         |
|-----------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Minimal 2 edge device dan 2 sensor      | 4 edge device: HP A & HP B (mikrofon), ESP32 dapur & ESP32 kamar (MQ-2 + DHT22). 2 jenis sensor: mikrofon (audio) dan gas/suhu (MQ-2 + DHT22).                                                      |
| Minimal 2 jenis data processing         | (1) Pre-filtering berbasis fitur sinyal di edge (RMS amplitudo, rate-of-rise). (2) Klasifikasi event (model AI YAMNet untuk audio dan/atau rule berbasis korelasi gas-suhu) di processing server. |
| Algoritma AI atau algoritma lain        | Kombinasi keduanya: algoritma lain (rule-based threshold, rate-of-rise) untuk pre-filtering, dan algoritma AI (YAMNet, model audio classification pre-trained) untuk klasifikasi akhir.             |
| Minimal 1 protokol komunikasi ke cloud  | MQTT ke broker publik (HiveMQ), seluruh edge device publish data/hasil ke broker, processing server subscribe untuk mengolah dan mem-publish ulang status.                                          |
| Dashboard satu jaringan dengan pengguna | Dashboard web dijalankan sebagai server lokal di laptop (processing server), diakses lewat browser oleh perangkat lain yang berada di WiFi/hotspot yang sama.                                       |

# 3. Arsitektur Sistem

Alur data dari sensor hingga notifikasi mengikuti empat lapis standar IoT: Sensor & Edge, Jaringan, Cloud, dan Dashboard.

## 3.1 Komponen Utama

| **Komponen**      | **Device**                   | **Peran**                                                                               |
|-------------------|------------------------------|-----------------------------------------------------------------------------------------|
| Edge 1            | HP A (misal: dapur)          | Rekam audio terus-menerus, hitung RMS amplitudo, kirim clip bila melewati ambang        |
| Edge 2            | HP B (misal: kamar)          | Sama seperti Edge 1, titik berbeda untuk validasi silang                                |
| Edge 3            | ESP32 + MQ-2 + DHT22 (dapur) | Baca kadar gas/asap dan suhu, hitung rate-of-rise, kirim data bila melewati ambang      |
| Edge 4            | ESP32 + MQ-2 + DHT22 (kamar) | Sama seperti Edge 3, titik berbeda untuk lokasi sumber asap                             |
| Processing Server | Laptop                       | Subscribe semua topic MQTT, jalankan klasifikasi (YAMNet/rule korelasi), host dashboard |
| Dashboard         | Browser (laptop/HP lain)     | Tampilkan status, riwayat event, dan grafik, diakses dalam jaringan lokal yang sama     |

## 3.2 Alur Data

1.  HP A/B merekam audio dan ESP32 membaca gas/suhu secara kontinu di edge masing-masing.

2.  Setiap edge menjalankan pre-filtering lokal (lihat Bab 5) untuk menyaring data yang layak dikirim.

3.  Data yang lolos filter dipublish ke broker MQTT dengan topic sesuai titik dan jenis sensor.

4.  Processing server (laptop) subscribe seluruh topic, menjalankan klasifikasi tahap dua, dan menentukan status akhir (Normal / Alert).

5.  Hasil klasifikasi dipublish kembali ke broker sebagai topic notifikasi/alert.

6.  Dashboard menampilkan status real-time dan riwayat, sementara penghuni lain menerima notifikasi (getar/bunyi) di HP masing-masing.

# 4. Sensor dan Edge Device

## 4.1 Mikrofon (HP Android)

**Fungsi:** Menangkap gelombang suara di sekitar HP untuk mendeteksi event akustik seperti pecahan kaca dan bunyi alarm asap.

**Lokasi pemasangan:** HP diletakkan di titik tetap, idealnya jauh dari ventilasi/jendela langsung agar tidak mudah terpengaruh suara dari luar.

**Cara pakai (teknis):** Lewat Termux, `termux-microphone-record` merekam **terus-menerus** ke satu file opus (`-l 0 -e opus -r 16000 -b 96 -c 1`). Opsi `-r 16000` wajib: tanpa itu Termux merekam di 8 kHz, sehingga seluruh suara di atas 4 kHz (ciri utama pecahan kaca) hilang dan klasifikasi gagal total. Skrip Python membaca file itu sambil terus tumbuh (ffmpeg, hanya bagian yang belum diproses), memotong klip 3 detik tiap 2 detik (tumpang-tindih 1 detik supaya satu kejadian tidak terpotong di batas klip), dan mengirim klip yang tidak hening ke processing server. File rekaman dimulai ulang tiap 30 menit, dengan celah rekam sekitar 5-9 detik tiap pergantian (perkiraan, belum diukur di HP).

Mode lama (rekam 2 detik, berhenti, mulai lagi) masih tersedia sebagai cadangan (`EDGE_MODE=window`), tetapi punya jeda tak terekam sekitar 1,3-2,5 detik tiap siklus sehingga HP hanya mendengar sekitar 34% waktu; karena itu tidak dipakai sebagai mode utama.

**Fitur yang diambil:** Amplitudo RMS (seberapa keras), frekuensi dominan (FFT, hanya sebagai informasi tambahan), dan rasio energi band tinggi (di atas 2 kHz) dari tiap klip. Klip audio itu sendiri ikut dikirim supaya bisa diklasifikasi YAMNet di server.

**Alasan dipilih:** Satu-satunya cara praktis mendeteksi pecahan kaca dari jarak tertentu tanpa sensor tambahan; sound merambat lewat udara sehingga tidak butuh kontak fisik seperti sensor getar.

## 4.2 Sensor Gas/Asap MQ-2

**Fungsi:** Mendeteksi kadar gas mudah terbakar dan asap di udara sebagai indikasi langsung adanya pembakaran/kebakaran.

**Lokasi pemasangan:** Dipasang di ESP32, idealnya di titik yang berisiko kebakaran (dapur) dan satu titik lain (kamar) untuk perbandingan lokasi, dijauhkan dari jendela/ventilasi agar tidak gampang false alarm dari asap luar.

**Cara pakai (teknis):** MQ-2 dihubungkan ke pin analog ESP32, dibaca berkala (misal tiap 1-2 detik), nilai mentah dikonversi ke estimasi ppm sesuai datasheet/kalibrasi sederhana. Saat ini firmware mengirim nilai ADC mentah (0-4095) dan belum mengonversinya ke ppm (lihat Bab 8).

**Fitur yang diambil:** Nilai konsentrasi gas/asap dan rate-of-rise (laju kenaikan dari waktu ke waktu), bukan sekadar nilai ambang tunggal.

**Alasan dipilih:** Mendeteksi asap secara langsung dari udara, melengkapi bunyi alarm yang hanya bisa ditangkap bila sudah berbunyi; juga jadi dasar untuk membedakan sumber asap dari dalam vs luar rumah.

## 4.3 Sensor Suhu & Kelembapan DHT22

**Fungsi:** Mengukur suhu di sekitar ESP32 sebagai validasi tambahan untuk kebakaran, karena pembakaran aktif menghasilkan panas di dekat sumbernya.

**Lokasi pemasangan:** Satu paket dengan ESP32 dan MQ-2 di tiap titik.

**Cara pakai (teknis):** DHT22 terhubung ke pin digital ESP32, dibaca berkala bersamaan dengan pembacaan MQ-2. Saat ini firmware hanya membaca suhu; kelembapan belum dibaca (lihat Bab 9.2).

**Fitur yang diambil:** Suhu saat ini dan rate-of-rise suhu, dikorelasikan dengan rate-of-rise gas untuk keputusan akhir.

**Alasan dipilih:** Asap yang menyusup dari luar (misalnya bakaran sampah tetangga) umumnya tidak disertai kenaikan suhu di dalam ruangan, sedangkan kebakaran aktif di dalam rumah biasanya diikuti kenaikan suhu di sekitar sumbernya. Kombinasi ini menekan angka false alarm dari sumber eksternal, meski tidak menghilangkannya sepenuhnya (lihat Bab 8: Batasan Sistem).

# 5. Data Processing dan Algoritma

Sistem memakai dua tahap pemrosesan dengan sifat berbeda: tahap pertama menyaring data di edge (ringan, rule-based), tahap kedua mengklasifikasi event di processing server (lebih berat, bisa melibatkan model AI).

## 5.1 Tahap 1 — Pre-filtering di Edge

Tujuan tahap ini adalah mengurangi data yang perlu dikirim dan diproses lebih lanjut, supaya sistem hanya bereaksi saat ada indikasi event, bukan memproses semua data mentah terus-menerus.

| **Sumber**           | **Perhitungan**                                                  | **Kondisi kirim ke cloud**                                         |
|----------------------|------------------------------------------------------------------|--------------------------------------------------------------------|
| Mikrofon (HP A/B)    | RMS amplitudo per klip rekaman                                   | Klip tidak hening (RMS di atas 0,005)                              |
| MQ-2 + DHT22 (ESP32) | Rate-of-rise (selisih nilai per satuan waktu) untuk gas dan suhu | Laju kenaikan gas dan/atau suhu melewati ambang kecepatan tertentu; saat tenang tetap mengirim satu pesan tiap 10 detik (heartbeat) agar server tahu node masih hidup |

Jenis algoritma: rule-based / threshold logic — termasuk kategori "algoritma lain" sesuai ketentuan tugas.

**Temuan kalibrasi (audio):** pada rekaman mikrofon HP asli, RMS tidak bisa membedakan pecahan kaca dari suara lain. Klip kaca pecah hanya berkisar RMS 0,007-0,02 (event singkat "diencerkan" oleh bising sekitar), sama atau lebih pelan daripada bising angin/kendaraan (0,009-0,013), dan jauh lebih pelan daripada suara sesudahnya (disapu/diinjak, 0,05-0,16). Ambang awal 0,02 justru memblokir klip kaca yang dikenali YAMNet, sehingga diturunkan ke 0,005 (sedikit di atas keheningan total). Dengan demikian gerbang tahap 1 untuk audio hanya berfungsi membuang keheningan; pembedaan kaca dari suara lain sepenuhnya dilakukan di tahap 2. Pemicu lonjakan suara (lonjakan RMS dan lonjakan energi di atas 2 kHz) juga dicoba dan tidak dipakai: rekaman negatif punya lonjakan sebesar kaca, sedangkan kaca yang pelan tidak melewati rasio.

## 5.2 Tahap 2 — Klasifikasi di Processing Server

Data yang lolos tahap 1 diteruskan ke laptop untuk diklasifikasi lebih akurat.

### 5.2.1 Klasifikasi Audio (Pecahan Kaca)

**Jalur utama — YAMNet (AI):** Klip dikirim ke laptop sebagai WAV 16 kHz mono, lalu model pre-trained YAMNet (521 kelas AudioSet, tanpa training sendiri) dijalankan sekali per klip. Skor pecahan kaca adalah nilai **maksimum antar-frame** (kejadian transient hanya menempati 1-2 frame, rata-rata akan meredamnya) dari kelas **Glass, Shatter, dan Chink/clink**. Kelas Breaking dan Smash/crash sengaja tidak dipakai: pada uji, Breaking menyala 0,60 untuk pintu kayu dibanting, sedangkan Smash/crash selalu di bawah 0,12 untuk kaca. Klip dianggap pecahan kaca bila skor di atas **0,35** (diturunkan dari 0,5; lihat Bab 9.1).

**Cadangan — rule-based:** Dipakai hanya bila YAMNet tidak tersedia (TensorFlow atau model gagal dimuat). Klip dianggap kaca bila RMS minimal 0,005 dan rasio energi band tinggi (di atas 2 kHz setelah high-pass 200 Hz, dihitung di frame yang keras) minimal 0,5. Versi awal (frekuensi dominan di atas 3 kHz dan durasi di bawah 0,5 detik) terbukti tidak andal pada rekaman HP: FFT satu window penuh didominasi bising rendah yang berlangsung terus-menerus (hasilnya sekitar 100 Hz), sehingga ciri kaca yang singkat tertimbun. Cadangan ini juga menyala untuk suara logam bernada tinggi (kunci, lonceng), jadi lebih lemah daripada YAMNet.

**Keputusan akhir:** Keputusan diambil dari YAMNet; rule-based hanya dipakai bila YAMNet gagal. Setelah ada alert, alert berikutnya untuk HP dan jenis event yang sama diredam selama 10 detik (cooldown), karena satu pecahan kaca biasanya tertangkap di 2-3 klip berurutan.

### 5.2.1.1 Liveness Check — Membedakan Event Asli dari Suara TV/Sinetron

Suara pecahan kaca juga umum muncul dari adegan TV, film, atau sinetron, sehingga berpotensi memicu false alarm bila hanya mengandalkan klasifikasi bunyi semata. Masalah ini dikenal di industri sebagai "sound event liveness detection" — membedakan apakah suatu bunyi berasal dari kejadian nyata atau dari pemutaran ulang lewat speaker (Google/perangkat smart-home, paten US11863961B2, "Method and system for detecting sound event liveness using a microphone array"). Paten tersebut menggunakan microphone array dan estimasi arah datang suara (direction of arrival) untuk mengenali apakah bunyi berasal dari lokasi sumber yang sudah dikenali sebagai perangkat pemutar (misalnya TV yang posisinya tetap), atau dari lokasi lain yang berarti kejadian nyata. GuardSense mengadaptasi prinsip ini dengan dua pendekatan yang lebih sederhana, memanfaatkan perangkat yang sudah ada tanpa microphone array presisi:

**A. Validasi konteks suara di sekitar event (via YAMNet):** YAMNet, selain mendeteksi kelas Glass shatter, juga bisa mendeteksi kelas Television, Speech, dan Music pada window audio yang sama atau yang berdekatan waktunya. Jika skor Glass shatter tinggi namun disertai skor Television/Speech/Music yang juga tinggi pada saat bersamaan atau tepat sebelum-sesudahnya, event ditandai sebagai kemungkinan berasal dari TV/sinetron dan tidak langsung dianggap ALERT (bisa ditandai "perlu verifikasi" di dashboard, bukan langsung notifikasi darurat). Jika skor Glass shatter tinggi tanpa disertai suara dialog/musik/televisi di sekitarnya, event lebih meyakinkan sebagai kejadian nyata.

**B. Perbandingan amplitudo antar dua mikrofon (proxy sederhana pengganti DoA):** Karena GuardSense sudah memakai dua HP di dua titik berbeda, posisi ini bisa difungsikan sebagai microphone array sederhana. Suara TV cenderung tersebar relatif merata ke seluruh ruangan sehingga amplitudo yang tertangkap di kedua HP relatif setara. Suara pecahan kaca nyata adalah sumber titik (point source) yang intensitasnya turun tajam seiring jarak, sehingga amplitudo di HP yang lebih dekat jauh lebih tinggi dibanding HP yang lebih jauh. Rasio amplitudo antar kedua HP dipakai sebagai sinyal tambahan: rasio timpang menguatkan dugaan event nyata, rasio yang relatif setara menguatkan dugaan suara dari sumber tetap seperti TV.

**Status implementasi (diperbarui):**

- *Bagian A sudah dibuat dengan cakupan lebih sempit daripada rancangan.* Penilaian dilakukan pada **klip yang sama**: bila rata-rata skor Television, Speech, atau Music selama klip di atas 0,3 dan klip itu juga lolos klasifikasi kaca, event dikirim sebagai jenis `glass_break_needs_verification` (bukan `glass_break`) ke topic alerts. Belum dikerjakan: konteks klip sebelum dan sesudahnya. Label "perlu verifikasi" sudah tampil di dashboard (hasil penggabungan branch integrasi).
- *Uji simulasi (offline):* tiga sampel kaca ditempel di atas bicara dan musik dengan dua tingkat volume latar (12 campuran). Kaca polos: skor media maksimal 0,01-0,05, tidak ditandai. Pada seluruh campuran, skor media 0,34-0,94 sehingga ditandai TV. Pada 7 dari 12 campuran skor kaca tetap di atas ambang (0,43-0,90) sehingga menghasilkan "perlu verifikasi"; pada 5 campuran lainnya skor kaca jatuh ke 0,00-0,11 karena latar menutupi kaca, sehingga tidak ada alert sama sekali. Ini aman terhadap TV, tetapi artinya kaca asli yang pecah saat TV keras bisa terlewat. Belum diuji dengan pemutaran lewat mikrofon HP.
- *Bagian B sudah dibuat di server, tetapi ambangnya belum dikalibrasi.* Server menyimpan RMS klip tiap HP (dengan jam server saat klip tiba, karena jam dua HP bisa selisih beberapa detik). Saat satu HP mendeteksi kaca, RMS-nya dibandingkan dengan klip HP lain yang tiba dalam 3 detik; rasio di bawah 1,5 dianggap "setara" (kemungkinan sumber tersebar seperti TV) dan event diberi jenis `glass_break_needs_verification` dengan alasan `amplitude_equal`. Nilai 1,5 hanya tebakan awal dan harus ditentukan dari uji dua HP sungguhan (skenario 5). HP lain yang tidak mengirim klip di sekitar kejadian dianggap hening (rasio timpang); HP lain yang tidak terlihat lebih dari 30 detik dianggap mati dan bagian B tidak menilai. Kegagalan ambang ini aman: kaca asli hanya diberi label "perlu verifikasi", alert tidak dibuang. Logika sudah lolos 11 skenario uji simulasi (7 untuk kaca, 4 untuk alarm); belum diuji dengan dua HP.

**Keputusan akhir (dengan liveness check):** Event ditandai ALERT penuh hanya jika lolos klasifikasi Glass shatter DAN tidak terindikasi berasal dari TV/media berdasarkan salah satu atau kedua validasi di atas. Jika terindikasi dari TV namun tetap ingin dicatat, event bisa ditampilkan di dashboard dengan label tingkat keyakinan lebih rendah, bukan dihapus begitu saja.

### 5.2.2 Klasifikasi Alarm Asap / Kebakaran

**Audio:** Cek pola bunyi berulang periodik dengan frekuensi relatif konstan (ciri khas bunyi alarm), atau gunakan YAMNet dengan kelas Fire alarm, Smoke detector smoke alarm, Alarm, Buzzer.

*Implementasi (diperbarui):* dua jalur pada klip audio yang sama dengan jalur kaca. (1) YAMNet: hanya kelas Fire alarm dan Smoke detector/smoke alarm yang dipakai (Alarm dan Buzzer ditinggalkan karena terlalu umum: jam weker, bel microwave, klakson). Berbeda dengan kaca yang transient, alarm berbunyi terus-menerus, sehingga yang dinilai adalah skor frame tertinggi KEDUA (bunyi bertahan minimal 2 frame YAMNet), ambang 0,35. (2) Pola beep, hanya diperiksa bila YAMNet tidak yakin: alarm dari merek berbeda nadanya berbeda (sampel uji 1,1-6 kHz) tetapi polanya sama, yaitu beep 0,3-1,2 detik berisi satu nada stabil, berulang dengan nada dan durasi yang sama. Detektor ini (numpy saja, tanpa TensorFlow, sehingga tetap jalan di jalur cadangan) mencari segmen beep dari envelope RMS, memeriksa nadanya lewat FFT, lalu menghitung beep bernada sama (selisih maksimal 5%, durasi selisih maksimal 30%): terdeteksi bila ada dua beep lengkap bernada sama, atau tiga beep termasuk potongan di tepi klip. Alarm yang hanya dikenali lewat pola beep (YAMNet tidak yakin) diberi label `fire_alarm_needs_verification` dengan alasan `beep_pattern`, karena beep timer atau microwave berpola sama. Logika liveness check (bagian A dan B) dan cooldown sama dengan kaca; jenis alert `fire_alarm` / `fire_alarm_needs_verification`, cooldown 30 detik (alarm berbunyi terus). Dua penyesuaian dari uji lewat mikrofon HP: pola beep hanya menerima nada 800 Hz ke atas (bicara dan dengung bernada rendah sempat lolos sebagai beep), dan pola beep dibatalkan bila YAMNet membaca klip sebagai "Alarm clock" (skor di atas 0,5), karena timer dapur dan jam weker berbunyi berulang tetapi bukan alarm asap. Hasil pengujian ada di Bab 9.1.

**Gas & suhu:** Logika korelasi: ALERT hanya dipicu bila rate-of-rise gas DAN rate-of-rise suhu sama-sama melewati ambang dalam rentang waktu yang sama. Jika gas naik namun suhu stabil, kemungkinan asap berasal dari luar dan tidak langsung dianggap ALERT (lihat Bab 8).

*Implementasi:* `classify_fire.py` menilai satu pesan env: `classify_fire(gas_rate, temp_rate)` menyatakan kebakaran (confidence 0,8) bila laju gas minimal 5 ADC/detik DAN laju suhu minimal 0,5 °C/detik; bila hanya salah satu, bukan kebakaran (confidence 0,3). `estimate_source_location` memilih node yang memenuhi kedua ambang dengan laju gas tertinggi, atau `belum_diketahui` bila tidak ada. Firmware mengirim bila salah satu laju melewati ambang (pre-filtering tahap 1), sehingga keputusan "kedua-duanya" ada di tahap 2. `server.py` (hasil penggabungan branch integrasi) memanggil kedua fungsi ini di `on_env_message`: lonjakan pertama dari sebuah node dikirim sebagai `fire_smoke_needs_verification`, dan `fire_smoke` penuh baru terbit bila lonjakan kedua dari node yang sama datang dalam 10 detik (konstanta `FIRE_CONFIRM_WINDOW_S`); cooldown 20 detik per node dan level. Belum dikerjakan: jendela waktu yang menggabungkan pesan gas dan suhu dari sampel berbeda, serta kedaluwarsa pembacaan lama untuk estimasi lokasi (server memakai pembacaan terakhir tiap node tanpa batas umur). `processing-server/demo_lokasi.py` mendemonstrasikan logika lokasi dengan kedaluwarsa 30 detik.

**Lokasi sumber:** Dengan dua titik ESP32 (dapur dan kamar), node dengan kadar gas tertinggi/kenaikan tercepat dianggap sebagai perkiraan lokasi sumber asap (pendekatan sederhana berbasis perbandingan nilai antarnode, bukan triangulasi presisi).

## 5.3 Ringkasan Jenis Algoritma per Tahap

| **Tahap**                           | **Isi pemrosesan**                                             | **Kategori algoritma**                |
|-------------------------------------|----------------------------------------------------------------|---------------------------------------|
| 1\. Pre-filtering (edge)            | RMS amplitudo, rate-of-rise gas & suhu, perbandingan ke ambang | Algoritma lain (rule-based/threshold) |
| 2\. Klasifikasi (processing server) | YAMNet (AI, jalur utama audio; rule-based rasio band tinggi sebagai cadangan) dan rule korelasi gas-suhu | Algoritma AI dan/atau algoritma lain  |

# 6. Komunikasi dan Cloud

## 6.1 Protokol: MQTT

Seluruh edge device dan processing server berkomunikasi lewat broker MQTT publik (contoh: HiveMQ, broker.hivemq.com, port 8883 untuk TLS), tanpa perlu membuat akun. Pola publish/subscribe dipilih karena cocok untuk banyak perangkat dan notifikasi real-time, serta publisher dan subscriber tidak perlu saling kenal — keduanya cukup terhubung ke broker yang sama.

## 6.2 Struktur Topic (contoh)

| **Topic**                                      | **Diisi oleh**    | **Isi payload**                                                    |
|------------------------------------------------|-------------------|--------------------------------------------------------------------|
| guardsense/\<PROJECT_ID\>/edge/hpA/audio       | HP A              | Klip audio 3 detik (WAV 16 kHz mono, base64) + RMS, frekuensi dominan, rasio energi band tinggi, timestamp |
| guardsense/\<PROJECT_ID\>/edge/hpB/audio       | HP B              | Sama seperti di atas, titik berbeda                                |
| guardsense/\<PROJECT_ID\>/edge/esp32_dapur/env | ESP32 dapur       | Gas (ADC mentah), suhu, rate-of-rise gas dan suhu; tanpa timestamp (server memakai waktu tiba pesan) |
| guardsense/\<PROJECT_ID\>/edge/esp32_kamar/env | ESP32 kamar       | Sama seperti di atas, titik berbeda                                |
| guardsense/\<PROJECT_ID\>/alerts               | Processing server | Status klasifikasi akhir: jenis event (`glass_break`, `fire_alarm`, `fire_smoke`, dan masing-masing versi `_needs_verification`), lokasi, tingkat kepercayaan, alasan |

PROJECT_ID diganti dengan nama unik kelompok agar topic tidak bercampur dengan kelompok lain yang memakai broker publik yang sama.

**Catatan privasi dan trafik:** Karena klip audio dikirim lewat broker publik, siapa pun yang tahu atau menebak nama topic bisa mendengarnya; PROJECT_ID default tidak boleh dipakai. Satu klip sekitar 128 KB (base64), sekitar 500 kbps terus-menerus per HP. Jika audio dianggap terlalu sensitif atau trafik jadi masalah, alternatifnya broker privat atau pengiriman klip dalam format terkompresi (opus, sekitar 8 kali lebih kecil).

# 7. Dashboard

**Penempatan:** Dashboard berupa web app yang dijalankan sebagai server lokal di laptop (processing server), diakses lewat browser di alamat seperti http://localhost:8000.

**Syarat jaringan:** Supaya penghuni lain bisa membuka dashboard dari HP/laptop masing-masing, perangkat tersebut harus berada di WiFi/hotspot yang sama dengan laptop server. Ini memenuhi ketentuan "dashboard harus satu jaringan dengan pengguna", meski data yang ditampilkan bersumber dari broker MQTT di cloud.

**Konten yang ditampilkan:** Status masing-masing edge (Normal/Alert), riwayat event dengan timestamp dan lokasi, grafik amplitudo/gas/suhu dari waktu ke waktu, dan indikator umum sistem (misal status ARM/DISARM bila ditambahkan). Status implementasi: halaman sudah dibuat (`dashboard/index.html`, dilayani `server.py` di port 8000, polling tiap 1,5 detik) dengan status sistem (Aman, Perlu verifikasi, Bahaya), kartu empat perangkat, tiga grafik (25 titik terakhir), riwayat 15 kejadian, dan alarm suara beep opsional. Belum ada: indikator ARM/DISARM, notifikasi ke HP lain, dan uji akses dari perangkat lain.

# 8. Batasan Sistem

Beberapa keterbatasan yang perlu didokumentasikan secara jujur, bukan diklaim sebagai sistem yang sempurna:

- Asap dari luar yang pekat atau tertiup angin kencang ke arah sensor tetap berpotensi memicu ALERT meski bukan kebakaran di dalam rumah, karena rate-of-rise-nya bisa menyerupai pembakaran aktif. Mitigasi: menjauhkan sensor dari ventilasi/jendela langsung, serta menambahkan syarat kondisi bertahan beberapa pembacaan berturut-turut sebelum ALERT dikirim (bukan dari satu pembacaan sesaat).

- Sensor gas MQ-2 adalah sensor murah dengan akurasi terbatas dan perlu kalibrasi manual; nilai ppm yang dihasilkan bersifat estimasi, bukan pengukuran presisi laboratorium. Saat ini firmware mengirim nilai ADC mentah (0-4095), belum dikonversi ke ppm, dan pembacaan mendekati batas 4095 pada kadar tinggi (simulasi: 4014), sehingga kenaikan di wilayah itu hampir tidak terlihat.

- Deteksi pecahan kaca berbasis audio dapat salah mengenali suara lain yang mirip secara akustik (misalnya benturan logam atau benda keras lain); ambang batas perlu dikalibrasi dengan sampel suara nyata sebelum demo.

- Estimasi lokasi sumber asap hanya berbasis perbandingan nilai antarnode (node dengan kenaikan tercepat/tertinggi), bukan triangulasi presisi, sehingga akurasi lokasi bersifat kasar (per-ruangan, bukan per-titik).

- Gas dan suhu belum digabung dalam jendela waktu. Firmware hanya mengirim saat ada lonjakan, dan `classify_fire` menilai satu pesan; bila gas dan suhu melonjak di sampel (2 detik) yang berbeda, tidak ada yang dianggap kebakaran. Penggabungan di server dalam jendela sekitar 20-30 detik dan kedaluwarsa pembacaan lama masih harus dibuat. Kadar gas yang bertahan tinggi juga tidak menimbulkan alert baru, hanya lonjakannya (pesan heartbeat tiap 10 detik tidak mengubah ini karena lajunya rendah).

- Ambang awal gas (5 ADC/detik) dan suhu (0,5 °C/detik) sangat longgar dan belum dikalibrasi: di simulasi setiap langkah slider gas melewatinya, termasuk kenaikan pelan, sehingga gas saja tidak bisa membedakan asap luar dari kebakaran; pembedanya adalah suhu. Lonjakan suhu 5-28 °C/detik hanya mungkin dari slider, bukan dari sensor nyata.

- Liveness check (pembeda suara TV/sinetron vs event nyata) menggunakan proxy sederhana (konteks suara sekitar via YAMNet dan rasio amplitudo dua mikrofon), bukan direction-of-arrival presisi seperti pada sistem komersial yang memakai microphone array tersinkronisasi. Skenario yang tetap berpotensi lolos sebagai false alarm: adegan kaca pecah di TV yang diputar tanpa dialog/musik bersamaan, atau TV yang jaraknya berbeda dari kedua HP (misalnya lebih dekat ke HP A) sehingga rasio amplitudo terlihat timpang seperti event nyata: TV juga sumber titik, jadi asumsi "TV menyebar merata" hanya berlaku bila kedua HP kira-kira sama jauhnya dari TV. Perlindungan utama untuk kasus ini adalah bagian A (konteks suara) dan penempatan HP; kalibrasi "tanda tangan" rasio TV dicatat sebagai pengembangan lanjutan.

- Skor YAMNet pada rekaman mikrofon HP bervariasi antar-klip untuk bunyi yang sama (0,00-0,95), bergantung pada posisi kejadian di dalam klip, volume, dan jarak. Kejadian yang pelan (hanya sedikit di atas bising latar) kadang terdeteksi dan kadang tidak. Kejadian berdurasi 1 detik atau kurang dijamin utuh di setidaknya satu klip; yang lebih panjang bisa terbelah di dua klip.

- Seluruh uji kaca sejauh ini memakai sampel yang diputar lewat speaker lalu direkam mikrofon HP; frekuensi tinggi sudah berkurang dibanding kaca sungguhan. Uji dengan gelas yang benar-benar pecah belum dilakukan.

- Ketukan kaca, denting gelas, kunci, dan koin belum diuji; bel, lonceng, dan denting sudah diuji sebagian lewat sampel dan hasilnya salah terbaca kaca (lihat butir berikutnya). Ambang 0,35 dipilih dari data terbatas (lihat Bab 9.1). Cadangan rule-based diketahui menyala untuk suara logam bernada tinggi.

- Latar media yang keras (musik, TV) bisa menutupi suara kaca sampai skornya mendekati nol, sehingga kaca asli saat TV keras bisa terlewat.

- Audio rumah dikirim lewat broker publik (lihat Bab 6.2). HP harus terus menyala dan dicolok ke charger, Termux perlu dikecualikan dari optimasi baterai, dan mikrofon tidak bisa dipakai bersamaan dengan aplikasi lain. Ada celah rekam saat pergantian file (tiap 30 menit).

- Liveness bagian B hanya memakai klip HP lain yang sudah tiba saat keputusan diambil; klip HP lain yang tiba hingga sekitar 2 detik sesudahnya belum ikut dinilai. Efeknya bias ke "timpang" (kaca asli tidak diberi label keliru), tetapi kasus TV bisa lolos sebagai alert penuh. Selain itu perbedaan gain mikrofon antar-HP bisa memengaruhi rasio.

- Label "perlu verifikasi" dan alasannya (konteks TV/media, amplitudo setara, pola beep, kenaikan gas-suhu) sudah tampil di riwayat event dashboard; dashboard belum diuji lintas perangkat dan belum menampilkan notifikasi getar/bunyi.

- Bunyi berdering atau berdenting bernada tinggi (bel, lonceng, nada EAS, denting) bisa terbaca YAMNet sebagai kaca lewat mikrofon HP. Pembeda yang dicoba (kemurnian nada, peringkat kelas kaca di frame puncak, skor kelas Ding dan Bell, embedding YAMNet) tidak memisahkan dengan andal; skor Bell bahkan mencapai 0,99 pada klip kaca yang benar. Embedding hanya memberi sinyal tipis dengan data sangat terbatas dan tidak dipakai.

- Deteksi alarm asap lewat mikrofon HP banyak bergantung pada pola beep: YAMNet hanya mengenali satu dari empat sampel alarm (skornya turun dari 0,85 ke atas secara offline menjadi 0,00-0,16 pada alarm sekolah), dan pola beep hanya menandai sekitar 41% klip yang bernada alarm. Penyebab yang teramati: hanya satu beep penuh di dalam jendela 3 detik, suara keras non-beep menaikkan acuan puncak, dan beep terpecah oleh gema. Per kejadian keempat alarm terdeteksi, tetapi tiga di antaranya berlabel perlu verifikasi.

- Cooldown alarm 30 detik per HP berarti alarm kedua yang bunyinya berbeda dan berbunyi dalam 30 detik setelah alert alarm sebelumnya tidak menghasilkan alert baru.

# 9. Rencana Pengujian

Pengujian mencakup skenario positif (event harus terdeteksi) dan skenario negatif (event serupa yang seharusnya tidak memicu ALERT), supaya hasil demo dan laporan lebih kredibel.

| **No** | **Skenario**                                                                                                                         | **Hasil yang diharapkan**                                                                                                                                                                                                                                         |
|--------|--------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1      | Menjatuhkan gelas/piring kaca secara terkendali di dekat HP A (simulasi kecelakaan rumah tangga)                                     | Status berubah menjadi ALERT pecahan kaca, notifikasi terkirim ke HP lain, muncul di riwayat dashboard                                                                                                                                                            |
| 2      | Simulasi hewan peliharaan menyenggol benda kaca (misal mendorong gelas kosong dari meja hingga pecah, tanpa ada orang di ruangan)    | Sistem tetap mendeteksi ALERT pecahan kaca walau tidak ada suara langkah manusia sebelumnya (menguji bahwa deteksi berbasis karakteristik suara, bukan asumsi ada orang di ruangan)                                                                               |
| 3      | Suara keras lain yang bukan kaca (pintu dibanting, buku jatuh)                                                                       | Sistem tidak menandai sebagai ALERT pecahan kaca (uji ketahanan terhadap false positive)                                                                                                                                                                          |
| 4      | Memutar adegan/cuplikan suara pecahan kaca dari TV/laptop dengan dialog atau musik latar yang menyertainya                           | Event terdeteksi sebagai Glass shatter namun ditandai "perlu verifikasi"/tidak langsung ALERT karena skor Television/Speech/Music ikut tinggi (uji liveness check bagian A)                                                                                       |
| 5      | Memutar suara pecahan kaca dari speaker/HP yang diletakkan sejajar jarak dengan kedua HP sensor (simulasi TV tanpa dialog bersamaan) | Mencatat apakah rasio amplitudo antar dua HP terlihat relatif setara (indikasi sumber tersebar) dibanding skenario 1 yang asimetris (uji liveness check bagian B, sekaligus mencatat sebagai kasus yang didokumentasikan di Bab 8 bila masih lolos sebagai ALERT) |
| 6      | Menyalakan sumber asap kecil terkendali (misal dupa/obat nyamuk) dekat sensor dapur                                                  | Gas naik cepat dan suhu ikut naik di titik yang sama dalam waktu berdekatan -\> ALERT kebakaran, lokasi terdeteksi di dapur                                                                                                                                       |
| 7      | Mensimulasikan asap luar: sumber asap di luar ruangan dengan ventilasi terbuka                                                       | Gas naik bertahap/lambat tanpa kenaikan suhu signifikan -\> sistem tidak langsung ALERT, atau ditandai sebagai kondisi perlu verifikasi manual                                                                                                                    |
| 8      | Kedua ESP32 dites bersamaan dengan sumber asap hanya di satu titik                                                                   | Node dengan kenaikan gas tertinggi/tercepat ditandai sebagai perkiraan lokasi sumber                                                                                                                                                                              |
| 9      | Uji jaringan: dashboard diakses dari HP lain di WiFi yang sama                                                                       | Dashboard dapat diakses dan menampilkan data real-time dari broker MQTT                                                                                                                                                                                           |
| 10     | Uji latensi notifikasi                                                                                                               | Waktu dari event terjadi hingga notifikasi diterima di HP lain dicatat dan dilaporkan (target idealnya di bawah beberapa detik)                                                                                                                                   |

## 9.1 Hasil Pengujian dan Kalibrasi Awal Jalur Audio (diperbarui)

Metode: rekaman mikrofon HP asli (Termux, 16 kHz) untuk sampel yang diputar lewat speaker laptop, lalu dinilai YAMNet di laptop. Hasil di bawah menyangkut jalur audio saja dan berasal dari sampel terbatas. Hasil dilaporkan dalam dua pandangan: per kejadian (yang dilihat pengguna, yaitu alert yang tampil setelah cooldown dan label verifikasi) dan per klip (kepekaan detektor terhadap tiap klip 3 detik). Pandangan per kejadian menyembunyikan klip yang terlewat, sehingga kepekaan per klip dicatat terpisah. Label per klip untuk bunyi alarm berasal dari frekuensi dominan klip (perkiraan), belum dikonfirmasi satu per satu dengan pendengaran.

| **No** | **Skenario (Bab 9)** | **Status** | **Hasil sejauh ini** |
|--------|----------------------|------------|----------------------|
| 1 | Gelas kaca dijatuhkan di dekat HP A | Belum dengan gelas sungguhan | Sampel kaca lewat speaker: pada satu uji 94 detik terkirim 4 alert (skor 0,47-0,76); pada uji lain 9 alert dalam sekitar 220 detik (0,37-0,83), dan sebagian klip kaca tidak lolos karena skornya 0,2-0,34. Sesi terakhir (113 klip, satu HP): 23 klip ditandai kaca (skor 0,37-0,98, median 0,64); dari 12 kandidat kejadian 11 terdeteksi (14 alert setelah cooldown 10 detik), 2 klip berlabel perlu verifikasi karena konteks media; jumlah sampel yang diputar tidak tercatat sehingga angka ini batas atas |
| 2 | Hewan menyenggol benda kaca | Belum | - |
| 3 | Suara keras lain (pintu dibanting, buku jatuh) | Sebagian | Pintu dibanting (dua jenis), musik, bicara, tawa, bising ruangan, suara memasak, dan TV static: rekaman offline skor kaca maksimal 0,18; uji live sekitar 62 klip (122 detik) tidak ada yang ditandai kaca, skor maksimal 0,08. Buku jatuh, kunci, dan koin belum diuji |
| 4 | Kaca di TV dengan dialog/musik | Sebagian | Hanya simulasi offline (Bab 5.2.1.1); belum lewat mikrofon HP |
| 5 | Rasio amplitudo dua HP | Logika selesai, kalibrasi belum | Server sudah membandingkan RMS dua HP (11 skenario simulasi lolos: 7 kaca, 4 alarm); ambang rasio 1,5 belum dikalibrasi dengan dua HP sungguhan |
| - | Bunyi alarm asap (Bab 5.2.2, audio) | Lewat mikrofon HP (sampel via speaker) | Per kejadian: 4 dari 4 alarm terdeteksi 0-10 detik setelah mulai (fire-alarm-33770 langsung lewat YAMNet; alarm sekolah dan nada EAS +4 detik, bel 6708 +10 detik, ketiganya lewat pola beep dan berlabel perlu verifikasi). Per klip: dari 44 klip yang bernada alarm, 18 ditandai (41%); dari 211 klip mikrofon lain tidak ada yang ditandai alarm. Sebelum lewat mikrofon (offline, klip bersih) 7/7, 30/31, 4/4, 2/14 jendela |
| - | Bunyi dering rumah tangga (bel pintu, timer dapur) | Lewat mikrofon HP (sampel via speaker) | Tidak ada alert. Pembatalan Alarm clock membuang 1 klip timer yang salah, tetapi juga 1 klip nada EAS yang benar (skor Alarm clock 0,54, tepat di ambang 0,5) |
| - | Bunyi berdering/berdenting vs kaca (bel, lonceng, nada EAS, denting microwave) | Kelemahan terbuka | Enam klip salah ditandai kaca dalam satu sesi (bel 6708 empat klip, skor 0,35-0,85; awal nada EAS 0,49; satu lonceng tak teridentifikasi 0,39). Denting microwave offline juga 0,86. Belum ada pembeda andal (lihat Bab 8) |
| 10 | Latensi notifikasi | Belum | - |

Parameter yang berubah selama kalibrasi:

| **Parameter** | **Awal** | **Sekarang** | **Alasan** |
|---------------|----------|--------------|------------|
| Sample rate rekaman | Default Termux (8 kHz) | 16 kHz (`-r 16000`) | Pada 8 kHz suara di atas 4 kHz hilang; seluruh skor kaca 0 |
| Gerbang RMS | 0,02 | 0,005 | Klip kaca hanya RMS 0,007-0,02; lebih pelan dari bising angin/kendaraan |
| Ambang skor YAMNet | 0,5 | 0,35 | Klip non-kaca maksimal 0,08 (uji live) dan 0,18 (rekaman negatif); klip kaca 0,37-0,97, sering 0,37-0,49 |
| Kelas kaca | Glass shatter, Glass, Breaking, Crockery breaking | Glass, Shatter, Chink/clink | Breaking menyala 0,60 untuk pintu dibanting; Smash/crash selalu di bawah 0,12 untuk kaca |
| Skor antar-frame | Rata-rata | Maksimum | Kejadian transient hanya 1-2 frame |
| Bentuk klip | Window 2 detik, rekam-berhenti-ulang (jeda 1,3-2,5 detik) | Klip 3 detik tiap 2 detik dari rekaman kontinu | Kejadian di jeda tidak terekam, yang di batas window terpotong |
| Rotasi file rekaman | Tiap 60 detik (HP tidak mendengar sekitar 9 detik tiap 64 detik) | Tiap 30 menit | Seluruh file tidak lagi di-decode tiap detik |
| Ambang YAMNet alarm | - | 0,35 pada skor frame tertinggi kedua kelas Fire alarm dan Smoke detector | Alarm berbunyi terus; satu bunyi sesaat tidak cukup |
| Pola beep | - | 2 beep penuh bernada sama (selisih 5%, durasi 30%) atau 3 termasuk potongan; nada 800 Hz ke atas | Mengenali alarm yang tidak dikenali YAMNet (EAS, bel); bicara dan dengung rendah sempat lolos |
| Pembatalan Alarm clock | - | Pola beep dibatalkan bila skor Alarm clock di atas 0,5 | Timer dapur dan jam weker berpola beep tetapi bukan alarm asap; offline 0,96-0,99 vs alarm asap 0,00-0,14, lewat mikrofon HP timer 0,4-0,8 |

Sampel kaca terpendek (sekitar 1,3 detik) paling mudah terlewat: skornya turun dari 0,89 menjadi 0,29 ketika volume putar diturunkan ke sekitar 12% (simulasi dengan bising mikrofon HP).

## 9.2 Hasil Pengujian Jalur Gas dan Suhu (Wokwi, node dapur)

Metode: firmware dibangun dengan PlatformIO dan dijalankan di simulator Wokwi (VS Code). Gas dan suhu digeser lewat slider MQ-2 (ppm) dan DHT22 (suhu) saat simulasi berjalan; payload diamati di Serial Monitor dan nilainya dimasukkan ke `classify_fire`. Hanya node dapur yang dijalankan di Wokwi; kode node kamar sama persis (hanya `DEVICE_ID` yang berbeda) dan baru lolos build. Semua nilai berasal dari slider, bukan sensor fisik, dan ambang belum dikalibrasi.

| **No** | **Skenario (Bab 9)** | **Hasil** |
|--------|----------------------|-----------|
| - | Build firmware dapur dan kamar | Berhasil (RAM 13,7%, flash 57,8%) |
| 6 (sebagian) | Gas naik tajam, suhu tetap | ADC 3628 ke 3959: laju 165,5 ADC/detik, terkirim. `classify_fire(165,5; 0)`: bukan kebakaran, confidence 0,3 |
| 6 (sebagian) | Gas naik bertahap (1019, 1251, 1582, 1999, 2494, 3525, 4014) | Setiap langkah terkirim, laju 116-515 ADC/detik |
| - | Gas turun (3959 ke 1019) dan gas stabil | Laju -1470 dan 0, tidak terkirim |
| 6 (sebagian) | Suhu naik 24 ke 80 °C, gas tetap | 28,0 °C/detik, terkirim. `classify_fire(0; 28)`: bukan kebakaran, confidence 0,3. Kenaikan susulan 5,1 dan 6,8 °C/detik terkirim; penurunan (-5,95 sampai -7,65) tidak |
| 6 | Gas dan suhu naik di sampel yang sama | 20,5 ADC/detik dan 8,1 °C/detik, terkirim. `classify_fire(20,5; 8,1)`: kebakaran, confidence 0,8 |
| 5.2.2 | Estimasi lokasi, 4 skenario simulasi (`demo_lokasi.py --simulasi`) | Dapur bila hanya dapur memenuhi dua ambang; tetap dapur bila gas kamar lebih cepat tetapi suhunya tidak lolos; pindah ke kamar bila kamar memenuhi dua ambang dengan gas lebih cepat; `belum_diketahui` bila semua pembacaan lebih tua dari 30 detik. Offline, belum live dengan dua Wokwi |
| 7 | Asap luar (gas naik pelan, suhu stabil) | Belum diuji dengan benar: ambang gas terlalu longgar sehingga kenaikan pelan pun melewatinya |
| - | Server menerima pesan env dari Wokwi dan menerbitkan alert kebakaran | Lolos untuk node dapur. Gas naik tanpa suhu (46 ADC/detik): tidak ada alert. Gas dan suhu naik bersamaan (29,5 ADC/detik dan 6,75 °C/detik): `fire_smoke_needs_verification`. Lonjakan kedua 25 detik setelah yang pertama menjadi `fire_smoke` (saat itu jendela konfirmasi 30 detik; sekarang 10 detik, sehingga jeda segitu kini hanya VERIFY) |
| - | Pengiriman simulasi tanpa Wokwi (`publish_env.py bahaya`) | Lolos: lonjakan pertama `fire_smoke_needs_verification`, lonjakan kedua dalam 10 detik (jeda uji 4 detik) `fire_smoke` |
| - | Lokasi sumber lewat server (`publish_env.py lokasi`) | Alert dapur berlokasi `esp32_dapur`; setelah kamar melonjak dengan gas lebih cepat, alert kamar berlokasi `esp32_kamar` |
| - | Tampilan dashboard saat ada alert | Lolos: riwayat menampilkan level VERIFY, jenis "Indikasi asap (verifikasi)", sumber dan lokasi `esp32_dapur`, akurasi 80%, dan alasan; status sistem berubah menjadi BAHAYA (hero hitam) dengan 12 kejadian tercatat. Sebelum ada heartbeat, kartu ESP32 tetap OFFLINE saat tenang (0 dari 4 perangkat online walau status BAHAYA); setelah heartbeat 10 detik ditambahkan, kartu tetap ONLINE selama Wokwi berjalan |

Perbaikan dari hasil uji ini: pin gas di `diagram.json` salah nama (`AO`, seharusnya `AOUT` pada part `wokwi-gas-sensor`, sehingga pembacaan gas tidak berubah); `timestamp` dari `millis()` dihapus dari payload karena itu waktu sejak menyala, bukan epoch (server memakai waktu tiba); selang laju dihitung dari sampel valid terakhir (sampel DHT22 yang gagal tadinya membuat laju terlihat dua kali lebih besar); akhir baris Serial diubah ke CRLF agar tampilan terminal Wokwi rapi; ditambahkan heartbeat tiap 10 detik supaya server dan dashboard menganggap node online selama hidup.

Temuan lain: yang dinilai adalah laju kenaikan, bukan kadar, jadi gas yang bertahan tinggi (misalnya slider tetap di nilai besar) tidak memicu apa pun setelah lonjakan pertama; gas dan suhu yang naik di sampel berbeda tidak dianggap kebakaran (lihat Bab 8); koneksi ke broker publik putus lalu tersambung lagi sekitar tiap 30 detik di simulasi, tanpa pesan gagal kirim yang terlihat. Sebelum ada heartbeat, perangkat terlihat OFFLINE di dashboard selama tidak ada lonjakan, karena server menganggap online hanya bila ada pesan dalam 15 detik terakhir; masalah ini diatasi dengan heartbeat tiap 10 detik. Kelembapan DHT22 belum dibaca firmware.

# 10. Pembagian Tugas

Dibagi berdasarkan jalur kerja end-to-end (bukan per jenis aktivitas), supaya setiap anggota memahami penuh satu bagian sistem dari sensor sampai hasil akhir, dan kontribusinya mudah dibuktikan secara individual. Anggota: Annis, Binar, Lila.

## 10.1 Annis — Jalur Audio (Deteksi Pecahan Kaca dan Alarm Asap)

| **No** | **Tugas**                                                                                       | **Output**                                                              |
|--------|-------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| 1      | Setup HP A & HP B: install F-Droid, Termux, Termux:API; uji termux-microphone-record            | Kedua HP bisa merekam audio lewat Termux                                |
| 2      | Implementasi pre-filtering tahap 1: hitung RMS amplitudo per window rekaman di HP               | Script Python di edge yang kirim clip hanya saat amplitudo lewat ambang |
| 3      | Implementasi klasifikasi tahap 2 (rule-based): cek frekuensi dominan (FFT) dan durasi transient | Fungsi klasifikasi pecahan kaca versi rule-based                        |
| 4      | Implementasi klasifikasi tahap 2 (AI): load YAMNet, ambil skor kelas Glass, Shatter, Chink/clink  | Fungsi klasifikasi pecahan kaca versi YAMNet                            |
| 5      | Implementasi liveness check: validasi konteks TV/Speech via YAMNet + rasio amplitudo 2 HP       | Fungsi liveness check terintegrasi ke keputusan akhir                   |
| 6      | Kalibrasi ambang batas pakai sampel suara nyata (kaca pecah, suara keras lain, cuplikan TV)     | Nilai ambang batas final + catatan hasil kalibrasi                      |
| 7      | Menulis Bab 4.1, 5.1 (bagian audio), 5.2.1, 5.2.1.1, 5.2.2 (bagian audio) di laporan akhir      | Draf bagian laporan terkait audio                                       |
| 8      | Implementasi deteksi alarm asap dari audio: YAMNet (kelas Fire alarm dan Smoke detector) dengan cadangan pola beep berulang, pembatalan Alarm clock, dan alert fire_alarm | Fungsi deteksi alarm asap di classify_audio.py dan jenis alert baru di server |
| 9      | Uji alarm dan bunyi dering rumah tangga (bel pintu, timer, microwave) lewat mikrofon HP; simpan klip debug untuk analisis | Hasil uji per kejadian dan per klip (Bab 9.1) |

**Status (28 Oktober 2026):** Tugas 1 selesai. Tugas 2 selesai (gerbang diturunkan menjadi 0,005; lihat Bab 5.1). Tugas 3 selesai sebagai cadangan. Tugas 4 selesai dan menjadi jalur utama. Tugas 5 sebagian (bagian A selesai; bagian B logikanya selesai tetapi ambangnya belum dikalibrasi dengan dua HP). Tugas 6 sebagian (kalibrasi dengan rekaman HP, belum dengan kaca sungguhan). Tugas 7 sebagian (Bab 4.1, 5.1, 5.2.1, 5.2.1.1, 5.2.2 diperbarui di dokumen ini). Tugas 8 selesai di server (jalur YAMNet dan pola beep); alarm yang hanya dikenali pola beep berlabel perlu verifikasi. Tugas 9 sebagian (sampel diputar lewat speaker pada satu HP; belum dengan alarm asap atau kaca sungguhan, dan belum dengan dua HP).

## 10.2 Binar — Jalur Gas & Suhu (Deteksi Kebakaran, via Wokwi)

| **No** | **Tugas**                                                                                               | **Output**                                                      |
|--------|---------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------|
| 1      | Desain rangkaian virtual ESP32 + MQ-2 + DHT22 di Wokwi (dua instance: dapur & kamar)                    | Project Wokwi dengan 2 rangkaian siap pakai                     |
| 2      | Tulis firmware (C++/Arduino): baca sensor MQ-2 & DHT22, koneksi WiFi simulasi, publish MQTT             | Firmware ESP32 yang jalan di simulasi dan konek ke broker nyata |
| 3      | Implementasi pre-filtering tahap 1: hitung rate-of-rise gas & suhu per interval waktu                   | Logika filter di firmware sebelum data dikirim                  |
| 4      | Implementasi klasifikasi tahap 2: korelasi rate-of-rise gas & suhu untuk keputusan ALERT                | Fungsi klasifikasi kebakaran (di ESP32 atau processing server)  |
| 5      | Implementasi estimasi lokasi sumber asap (perbandingan nilai antarnode)                                 | Logika penentuan node dengan kenaikan tertinggi/tercepat        |
| 6      | Uji & kalibrasi ambang batas pakai slider virtual MQ-2/DHT22 di Wokwi (simulasi kebakaran vs asap luar) | Nilai ambang batas final + catatan hasil kalibrasi              |
| 7      | Menulis Bab 4.2, 4.3, 5.1 (bagian gas/suhu), 5.2.2 di laporan akhir                                     | Draf bagian laporan terkait gas/suhu                            |

**Status (28 Oktober 2026):** Tugas 1-3 jalan di Wokwi untuk node dapur (Bab 9.2); node kamar baru lolos build. Tugas 4 dan 5 ada di `classify_fire.py`, lolos uji offline, dan sudah dipanggil `server.py` (lolos diuji dengan Wokwi dan dashboard untuk node dapur, serta dengan pesan simulasi lewat `publish_env.py` untuk dua node). Tugas 6 sebagian: skenario slider dasar sudah diuji, sedangkan kalibrasi ambang final dan skenario asap luar yang pelan belum.

## 10.3 Lila — Integrasi, Cloud, dan Dashboard

| **No** | **Tugas**                                                                                               | **Output**                                                         |
|--------|---------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------|
| 1      | Setup broker MQTT (HiveMQ), tentukan PROJECT_ID unik, rancang struktur topic                            | Broker siap dipakai + dokumentasi struktur topic                   |
| 2      | Setup repository GitHub: struktur folder, README, akses untuk ketiga anggota                            | Repo siap dipakai bersama sejak awal development                   |
| 3      | Processing server: subscribe seluruh topic dari jalur Annis & Binar, gabungkan jadi satu status terpadu | Script Python processing server yang mengorkestrasi kedua jalur    |
| 4      | Bangun dashboard web (status real-time, riwayat event, grafik amplitudo/gas/suhu)                       | Dashboard yang bisa dijalankan sebagai server lokal                |
| 5      | Pastikan dashboard bisa diakses dari HP/laptop lain dalam satu jaringan WiFi/hotspot                    | Dashboard teruji bisa diakses lintas perangkat dalam satu jaringan |
| 6      | Koordinasi jadwal integrasi dan pengujian end-to-end bersama Annis & Binar                              | Jadwal & checklist integrasi                                       |
| 7      | Menulis Bab 3, 6, 7 di laporan akhir, serta menggabungkan seluruh bagian laporan jadi satu dokumen      | Laporan akhir tergabung dan konsisten                              |

## 10.4 Dikerjakan Bersama

- Pengujian 10 skenario di Bab 9 — terutama skenario yang butuh dua titik aktif sekaligus (liveness check, estimasi lokasi sumber asap) perlu ketiga anggota hadir bersamaan.

- Integrasi akhir: menyambungkan jalur audio (Annis), jalur gas/suhu (Binar), dan processing server/dashboard (Lila) jadi satu sistem utuh yang berjalan dari ujung ke ujung.

- Review silang laporan akhir sebelum dikumpulkan, memastikan istilah dan angka konsisten antar-bagian.

- Latihan presentasi: masing-masing menjelaskan bagian yang dikerjakan sendiri di depan kelompok sebelum presentasi ke dosen.

## 10.5 Catatan Penting

Karena bagian ESP32 (MQ-2 + DHT22) sepenuhnya memakai simulasi Wokwi tanpa perakitan perangkat fisik, disarankan untuk mengonfirmasi ke dosen terlebih dahulu apakah pendekatan ini diterima untuk pengumpulan tugas, mengingat contoh-contoh di materi praktikum (WattSense, AirAware, SortSmart) menggunakan rangkaian fisik sungguhan.

# 11. Referensi

Rujukan yang mendasari pemilihan sensor dan pendekatan algoritma di dokumen ini:

- Dufaux, A., Besacier, L., Ansorge, M., Pellandini, F. (2000). Automatic sound detection and recognition for noisy environment. IEEE EUSIPCO.

- Enhancing smart home environments: a novel pattern recognition approach to ambient acoustic event detection and localization. PMC (open access).

- Nyein Naing, W.Y., Htike, Z.Z. (2019). Glass break detection system using deep auto encoders with fuzzy rules induction algorithm. International Journal of Advanced and Applied Sciences, 6(2), 33-38.

- Mazaki, Y., Kuroyanagi, S. (2022). A Glass Breaking Sound Detection Method for Security Systems using SVM. IEICE Technical Report, NC2021-48.

- Vivint LLC (paten US10922935B2). Detecting a premise condition using audio analytics — mengklasifikasikan suara rumah ke beberapa kategori (keamanan, kondisi kesehatan, kerusakan properti, alarm), dengan pecahan kaca termasuk kategori kerusakan properti yang terpisah dari kategori keamanan/intrusi, dan hasilnya diteruskan sebagai notifikasi ke penghuni.

- Aviva (2024). What a cat-astrophe! Aviva reveals five years of pet-related home insurance claims. Data klaim menunjukkan ribuan kasus kerusakan tidak sengaja oleh hewan peliharaan di rumah pada 2019-2023, termasuk jendela dan cermin pecah akibat hewan peliharaan menabrak benda di sekitarnya — mendukung skenario kaca pecah akibat hewan peliharaan sebagai kejadian rumah tangga yang realistis, bukan hanya asumsi.

- Method and system for detecting sound event liveness using a microphone array (paten US11863961B2) — menjelaskan teknik membedakan bunyi yang berasal dari kejadian nyata dengan bunyi yang diputar ulang lewat perangkat seperti TV, menggunakan estimasi arah datang suara (direction of arrival) dari microphone array; menjadi dasar pendekatan liveness check yang diadaptasi secara sederhana di GuardSense.

- Giannoulis, P., Potamianos, G., Katsamanis, A., Maragos, P. (2014). Multi-microphone fusion for detection of speech and acoustic events in smart spaces. EURASIP EUSIPCO.

- Donohue, K.D., Saghaiannejadesfahani, S.M., Yu, J. Constant false alarm rate sound source detection with distributed microphones.

- Fire alarm algorithm using smoke and gas sensors (paten, kombinasi rate-of-rise CO/CO2 dan smoke untuk mengurangi nuisance alarm).

- Method for detecting fires (paten, penggunaan rise speed sensor signal untuk membedakan event kebakaran dari gangguan seperti draft/debu).

- Google AudioSet Ontology & YAMNet model (TensorFlow Hub) — kelas suara Glass, Glass shatter, Breaking, Fire alarm, Smoke detector smoke alarm.

- Harris, F.J. (1978). On the Use of Windows for Harmonic Analysis with the Discrete Fourier Transform. Proceedings of the IEEE, 66(1), 51–83. — dasar penggunaan window Hanning sebelum FFT pada `compute_dominant_frequency` (Bab 5.1/5.2.1) untuk mengurangi spectral leakage.

*Dokumen ini dibuat sebagai bahan diskusi internal kelompok sebelum penyusunan laporan dan implementasi. Angka ambang batas (threshold) di seluruh dokumen bersifat indikatif dan perlu dikalibrasi dengan pengujian langsung menggunakan perangkat yang dipakai.*
