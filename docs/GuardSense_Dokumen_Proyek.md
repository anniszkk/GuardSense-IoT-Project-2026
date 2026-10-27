Mata Kuliah Internet of Things

**GuardSense**

*Sistem Deteksi Dini Pecahan Kaca dan Kebakaran Berbasis Multisensor*

Dokumen Perencanaan Proyek (untuk diskusi kelompok)

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

**Cara pakai (teknis):** Lewat Termux, gunakan termux-microphone-record untuk merekam audio singkat (window 1-2 detik berurutan) dalam format .wav, kemudian file diproses dengan Python (numpy/scipy untuk FFT, atau langsung dikirim ke processing server bila lolos pre-filter).

**Fitur yang diambil:** Amplitudo RMS (seberapa keras) dan frekuensi dominan (lewat FFT) dari tiap window rekaman.

**Alasan dipilih:** Satu-satunya cara praktis mendeteksi pecahan kaca dari jarak tertentu tanpa sensor tambahan; sound merambat lewat udara sehingga tidak butuh kontak fisik seperti sensor getar.

## 4.2 Sensor Gas/Asap MQ-2

**Fungsi:** Mendeteksi kadar gas mudah terbakar dan asap di udara sebagai indikasi langsung adanya pembakaran/kebakaran.

**Lokasi pemasangan:** Dipasang di ESP32, idealnya di titik yang berisiko kebakaran (dapur) dan satu titik lain (kamar) untuk perbandingan lokasi, dijauhkan dari jendela/ventilasi agar tidak gampang false alarm dari asap luar.

**Cara pakai (teknis):** MQ-2 dihubungkan ke pin analog ESP32, dibaca berkala (misal tiap 1-2 detik), nilai mentah dikonversi ke estimasi ppm sesuai datasheet/kalibrasi sederhana.

**Fitur yang diambil:** Nilai konsentrasi gas/asap dan rate-of-rise (laju kenaikan dari waktu ke waktu), bukan sekadar nilai ambang tunggal.

**Alasan dipilih:** Mendeteksi asap secara langsung dari udara, melengkapi bunyi alarm yang hanya bisa ditangkap bila sudah berbunyi; juga jadi dasar untuk membedakan sumber asap dari dalam vs luar rumah.

## 4.3 Sensor Suhu & Kelembapan DHT22

**Fungsi:** Mengukur suhu di sekitar ESP32 sebagai validasi tambahan untuk kebakaran, karena pembakaran aktif menghasilkan panas di dekat sumbernya.

**Lokasi pemasangan:** Satu paket dengan ESP32 dan MQ-2 di tiap titik.

**Cara pakai (teknis):** DHT22 terhubung ke pin digital ESP32, dibaca berkala bersamaan dengan pembacaan MQ-2.

**Fitur yang diambil:** Suhu saat ini dan rate-of-rise suhu, dikorelasikan dengan rate-of-rise gas untuk keputusan akhir.

**Alasan dipilih:** Asap yang menyusup dari luar (misalnya bakaran sampah tetangga) umumnya tidak disertai kenaikan suhu di dalam ruangan, sedangkan kebakaran aktif di dalam rumah biasanya diikuti kenaikan suhu di sekitar sumbernya. Kombinasi ini menekan angka false alarm dari sumber eksternal, meski tidak menghilangkannya sepenuhnya (lihat Bab 8: Batasan Sistem).

# 5. Data Processing dan Algoritma

Sistem memakai dua tahap pemrosesan dengan sifat berbeda: tahap pertama menyaring data di edge (ringan, rule-based), tahap kedua mengklasifikasi event di processing server (lebih berat, bisa melibatkan model AI).

## 5.1 Tahap 1 — Pre-filtering di Edge

Tujuan tahap ini adalah mengurangi data yang perlu dikirim dan diproses lebih lanjut, supaya sistem hanya bereaksi saat ada indikasi event, bukan memproses semua data mentah terus-menerus.

| **Sumber**           | **Perhitungan**                                                  | **Kondisi kirim ke cloud**                                         |
|----------------------|------------------------------------------------------------------|--------------------------------------------------------------------|
| Mikrofon (HP A/B)    | RMS amplitudo per window rekaman                                 | Amplitudo melewati ambang kekerasan suara tertentu                 |
| MQ-2 + DHT22 (ESP32) | Rate-of-rise (selisih nilai per satuan waktu) untuk gas dan suhu | Laju kenaikan gas dan/atau suhu melewati ambang kecepatan tertentu |

Jenis algoritma: rule-based / threshold logic — termasuk kategori "algoritma lain" sesuai ketentuan tugas.

## 5.2 Tahap 2 — Klasifikasi di Processing Server

Data yang lolos tahap 1 diteruskan ke laptop untuk diklasifikasi lebih akurat.

### 5.2.1 Klasifikasi Audio (Pecahan Kaca)

**Pendekatan A (rule-based):** Cek apakah amplitudo RMS tinggi, frekuensi dominan di atas sekitar 3-4 kHz, dan durasi event singkat (\<0.5 detik, bersifat transient). Kombinasi ciri ini membedakan pecahan kaca dari suara keras lain seperti pintu dibanting atau benda jatuh.

**Pendekatan B (AI, opsional/upgrade):** Gunakan model pre-trained YAMNet (521 kelas suara dari dataset AudioSet) untuk audio clip yang terkirim, ambil skor probabilitas kelas Glass shatter, Glass, Breaking, dan Crockery breaking and smashing. Tidak perlu training dari nol karena model sudah dilatih sebelumnya.

**Keputusan akhir:** Event dianggap pecahan kaca bila salah satu pendekatan (atau keduanya, bila dipakai bersamaan) memberi hasil positif di atas ambang kepercayaan tertentu.

### 5.2.1.1 Liveness Check — Membedakan Event Asli dari Suara TV/Sinetron

Suara pecahan kaca juga umum muncul dari adegan TV, film, atau sinetron, sehingga berpotensi memicu false alarm bila hanya mengandalkan klasifikasi bunyi semata. Masalah ini dikenal di industri sebagai "sound event liveness detection" — membedakan apakah suatu bunyi berasal dari kejadian nyata atau dari pemutaran ulang lewat speaker (Google/perangkat smart-home, paten US11863961B2, "Method and system for detecting sound event liveness using a microphone array"). Paten tersebut menggunakan microphone array dan estimasi arah datang suara (direction of arrival) untuk mengenali apakah bunyi berasal dari lokasi sumber yang sudah dikenali sebagai perangkat pemutar (misalnya TV yang posisinya tetap), atau dari lokasi lain yang berarti kejadian nyata. GuardSense mengadaptasi prinsip ini dengan dua pendekatan yang lebih sederhana, memanfaatkan perangkat yang sudah ada tanpa microphone array presisi:

**A. Validasi konteks suara di sekitar event (via YAMNet):** YAMNet, selain mendeteksi kelas Glass shatter, juga bisa mendeteksi kelas Television, Speech, dan Music pada window audio yang sama atau yang berdekatan waktunya. Jika skor Glass shatter tinggi namun disertai skor Television/Speech/Music yang juga tinggi pada saat bersamaan atau tepat sebelum-sesudahnya, event ditandai sebagai kemungkinan berasal dari TV/sinetron dan tidak langsung dianggap ALERT (bisa ditandai "perlu verifikasi" di dashboard, bukan langsung notifikasi darurat). Jika skor Glass shatter tinggi tanpa disertai suara dialog/musik/televisi di sekitarnya, event lebih meyakinkan sebagai kejadian nyata.

**B. Perbandingan amplitudo antar dua mikrofon (proxy sederhana pengganti DoA):** Karena GuardSense sudah memakai dua HP di dua titik berbeda, posisi ini bisa difungsikan sebagai microphone array sederhana. Suara TV cenderung tersebar relatif merata ke seluruh ruangan sehingga amplitudo yang tertangkap di kedua HP relatif setara. Suara pecahan kaca nyata adalah sumber titik (point source) yang intensitasnya turun tajam seiring jarak, sehingga amplitudo di HP yang lebih dekat jauh lebih tinggi dibanding HP yang lebih jauh. Rasio amplitudo antar kedua HP dipakai sebagai sinyal tambahan: rasio timpang menguatkan dugaan event nyata, rasio yang relatif setara menguatkan dugaan suara dari sumber tetap seperti TV.

**Keputusan akhir (dengan liveness check):** Event ditandai ALERT penuh hanya jika lolos klasifikasi Glass shatter DAN tidak terindikasi berasal dari TV/media berdasarkan salah satu atau kedua validasi di atas. Jika terindikasi dari TV namun tetap ingin dicatat, event bisa ditampilkan di dashboard dengan label tingkat keyakinan lebih rendah, bukan dihapus begitu saja.

### 5.2.2 Klasifikasi Alarm Asap / Kebakaran

**Audio:** Cek pola bunyi berulang periodik dengan frekuensi relatif konstan (ciri khas bunyi alarm), atau gunakan YAMNet dengan kelas Fire alarm, Smoke detector smoke alarm, Alarm, Buzzer.

**Gas & suhu:** Logika korelasi: ALERT hanya dipicu bila rate-of-rise gas DAN rate-of-rise suhu sama-sama melewati ambang dalam rentang waktu yang sama. Jika gas naik namun suhu stabil, kemungkinan asap berasal dari luar dan tidak langsung dianggap ALERT (lihat Bab 8).

**Lokasi sumber:** Dengan dua titik ESP32 (dapur dan kamar), node dengan kadar gas tertinggi/kenaikan tercepat dianggap sebagai perkiraan lokasi sumber asap (pendekatan sederhana berbasis perbandingan nilai antarnode, bukan triangulasi presisi).

## 5.3 Ringkasan Jenis Algoritma per Tahap

| **Tahap**                           | **Isi pemrosesan**                                             | **Kategori algoritma**                |
|-------------------------------------|----------------------------------------------------------------|---------------------------------------|
| 1\. Pre-filtering (edge)            | RMS amplitudo, rate-of-rise gas & suhu, perbandingan ke ambang | Algoritma lain (rule-based/threshold) |
| 2\. Klasifikasi (processing server) | YAMNet (model AI pre-trained) dan/atau rule korelasi gas-suhu  | Algoritma AI dan/atau algoritma lain  |

# 6. Komunikasi dan Cloud

## 6.1 Protokol: MQTT

Seluruh edge device dan processing server berkomunikasi lewat broker MQTT publik (contoh: HiveMQ, broker.hivemq.com, port 8883 untuk TLS), tanpa perlu membuat akun. Pola publish/subscribe dipilih karena cocok untuk banyak perangkat dan notifikasi real-time, serta publisher dan subscriber tidak perlu saling kenal — keduanya cukup terhubung ke broker yang sama.

## 6.2 Struktur Topic (contoh)

| **Topic**                                      | **Diisi oleh**    | **Isi payload**                                                    |
|------------------------------------------------|-------------------|--------------------------------------------------------------------|
| guardsense/\<PROJECT_ID\>/edge/hpA/audio       | HP A              | Hasil pre-filter audio: amplitudo, frekuensi dominan, timestamp    |
| guardsense/\<PROJECT_ID\>/edge/hpB/audio       | HP B              | Sama seperti di atas, titik berbeda                                |
| guardsense/\<PROJECT_ID\>/edge/esp32_dapur/env | ESP32 dapur       | Kadar gas, suhu, rate-of-rise, timestamp                           |
| guardsense/\<PROJECT_ID\>/edge/esp32_kamar/env | ESP32 kamar       | Sama seperti di atas, titik berbeda                                |
| guardsense/\<PROJECT_ID\>/alerts               | Processing server | Status klasifikasi akhir: jenis event, lokasi, tingkat kepercayaan |

PROJECT_ID diganti dengan nama unik kelompok agar topic tidak bercampur dengan kelompok lain yang memakai broker publik yang sama.

# 7. Dashboard

**Penempatan:** Dashboard berupa web app yang dijalankan sebagai server lokal di laptop (processing server), diakses lewat browser di alamat seperti http://localhost:8000.

**Syarat jaringan:** Supaya penghuni lain bisa membuka dashboard dari HP/laptop masing-masing, perangkat tersebut harus berada di WiFi/hotspot yang sama dengan laptop server. Ini memenuhi ketentuan "dashboard harus satu jaringan dengan pengguna", meski data yang ditampilkan bersumber dari broker MQTT di cloud.

**Konten yang ditampilkan:** Status masing-masing edge (Normal/Alert), riwayat event dengan timestamp dan lokasi, grafik amplitudo/gas/suhu dari waktu ke waktu, dan indikator umum sistem (misal status ARM/DISARM bila ditambahkan).

# 8. Batasan Sistem

Beberapa keterbatasan yang perlu didokumentasikan secara jujur, bukan diklaim sebagai sistem yang sempurna:

- Asap dari luar yang pekat atau tertiup angin kencang ke arah sensor tetap berpotensi memicu ALERT meski bukan kebakaran di dalam rumah, karena rate-of-rise-nya bisa menyerupai pembakaran aktif. Mitigasi: menjauhkan sensor dari ventilasi/jendela langsung, serta menambahkan syarat kondisi bertahan beberapa pembacaan berturut-turut sebelum ALERT dikirim (bukan dari satu pembacaan sesaat).

- Sensor gas MQ-2 adalah sensor murah dengan akurasi terbatas dan perlu kalibrasi manual; nilai ppm yang dihasilkan bersifat estimasi, bukan pengukuran presisi laboratorium.

- Deteksi pecahan kaca berbasis audio dapat salah mengenali suara lain yang mirip secara akustik (misalnya benturan logam atau benda keras lain); ambang batas perlu dikalibrasi dengan sampel suara nyata sebelum demo.

- Estimasi lokasi sumber asap hanya berbasis perbandingan nilai antarnode (node dengan kenaikan tercepat/tertinggi), bukan triangulasi presisi, sehingga akurasi lokasi bersifat kasar (per-ruangan, bukan per-titik).

- Liveness check (pembeda suara TV/sinetron vs event nyata) menggunakan proxy sederhana (konteks suara sekitar via YAMNet dan rasio amplitudo dua mikrofon), bukan direction-of-arrival presisi seperti pada sistem komersial yang memakai microphone array tersinkronisasi. Skenario yang tetap berpotensi lolos sebagai false alarm: adegan kaca pecah di TV yang diputar tanpa dialog/musik bersamaan, atau posisi TV yang kebetulan sama jaraknya dari kedua HP sehingga rasio amplitudo terlihat timpang seperti event nyata.

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

# 10. Pembagian Tugas

Dibagi berdasarkan jalur kerja end-to-end (bukan per jenis aktivitas), supaya setiap anggota memahami penuh satu bagian sistem dari sensor sampai hasil akhir, dan kontribusinya mudah dibuktikan secara individual. Anggota: Annis, Binar, Lila.

## 10.1 Annis — Jalur Audio (Deteksi Pecahan Kaca)

| **No** | **Tugas**                                                                                       | **Output**                                                              |
|--------|-------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------|
| 1      | Setup HP A & HP B: install F-Droid, Termux, Termux:API; uji termux-microphone-record            | Kedua HP bisa merekam audio lewat Termux                                |
| 2      | Implementasi pre-filtering tahap 1: hitung RMS amplitudo per window rekaman di HP               | Script Python di edge yang kirim clip hanya saat amplitudo lewat ambang |
| 3      | Implementasi klasifikasi tahap 2 (rule-based): cek frekuensi dominan (FFT) dan durasi transient | Fungsi klasifikasi pecahan kaca versi rule-based                        |
| 4      | Implementasi klasifikasi tahap 2 (AI): load YAMNet, ambil skor kelas Glass shatter/Breaking     | Fungsi klasifikasi pecahan kaca versi YAMNet                            |
| 5      | Implementasi liveness check: validasi konteks TV/Speech via YAMNet + rasio amplitudo 2 HP       | Fungsi liveness check terintegrasi ke keputusan akhir                   |
| 6      | Kalibrasi ambang batas pakai sampel suara nyata (kaca pecah, suara keras lain, cuplikan TV)     | Nilai ambang batas final + catatan hasil kalibrasi                      |
| 7      | Menulis Bab 4.1, 5.1 (bagian audio), 5.2.1, 5.2.1.1 di laporan akhir                            | Draf bagian laporan terkait audio                                       |

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

*Dokumen ini dibuat sebagai bahan diskusi internal kelompok sebelum penyusunan laporan dan implementasi. Angka ambang batas (threshold) di seluruh dokumen bersifat indikatif dan perlu dikalibrasi dengan pengujian langsung menggunakan perangkat yang dipakai.*
