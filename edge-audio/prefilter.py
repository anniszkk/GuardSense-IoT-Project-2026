"""Pre-filtering tahap 1 untuk audio (Bab 5.1).

compute_rms dan compute_dominant_frequency sudah diisi (Annis).

AMPLITUDE_THRESHOLD sudah dikalibrasi awal pakai sampel suara publik
(lihat edge-audio/samples/ = kaca pecah, samples1/ = non-event, diuji
lewat test_prefilter_local.py). Hasilnya: RMS sampel kaca pecah ada di
rentang ~0.02-0.13, sedangkan sampel non-event (masak, pintu dibanting,
dll) justru ada yang RMS-nya LEBIH TINGGI (~0.04-0.22). Jadi RMS di
tahap ini TIDAK dipakai untuk membedakan jenis suara -- cuma untuk
menyaring kondisi nyaris hening (misal room tone, RMS ~0.0035) biar
tidak terus-menerus dikirim ke processing-server. Pembedaan kaca pecah
vs suara lain dilakukan di tahap 2 (processing-server/classify_audio.py)
pakai frekuensi dominan, yang jauh lebih bersih pemisahannya (lihat
dokumentasi di file itu).

TODO: validasi ulang pakai rekaman HP asli di posisi pemasangan
sebenarnya sebelum dipakai final (Bab 9, skenario 1-3) -- RMS sensitif
terhadap jarak mic-sumber suara dan gain rekaman tiap perangkat.
"""

import numpy as np

# Ambang nyaris-hening, BUKAN ambang pembeda jenis suara (lihat docstring
# di atas). Hasil kalibrasi awal, lihat Bab 9 untuk validasi ulang.
# Diturunkan 0.02 -> 0.005 setelah uji rekaman HP asli (kaca4/kaca5.m4a, 16 kHz):
# RMS window 2 detik untuk kaca pecah cuma 0.007-0.023 (event singkat "diencerkan"
# bising sekitarnya), lebih RENDAH daripada bising angin/kendaraan di window lain
# (0.009-0.013) dan jauh di bawah suara setelah kaca (disapu/diinjak, 0.05-0.09).
# Jadi RMS tidak bisa membedakan; gerbang ini cuma membuang keheningan nyaris total.
AMPLITUDE_THRESHOLD = 0.005


def compute_rms(audio_samples: np.ndarray) -> float:
    """Hitung RMS (root mean square) amplitudo dari array sample audio
    (mono, float -1..1). RMS dipakai sebagai ukuran 'seberapa keras' suara
    pada satu window rekaman -- lihat Bab 5.1.
    """
    if audio_samples.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio_samples, dtype=np.float64))))


def compute_dominant_frequency(audio_samples: np.ndarray, sample_rate: int) -> float:
    """Hitung frekuensi dominan lewat FFT. Dipakai untuk klasifikasi awal
    (pecahan kaca biasanya > 3-4 kHz) -- lihat Bab 5.2.1.

    Memakai window Hanning untuk mengurangi spectral leakage, dan
    mengabaikan bin DC (indeks 0) supaya tidak salah mendeteksi 0 Hz
    sebagai 'frekuensi dominan' akibat offset rata-rata sinyal.
    """
    if audio_samples.size < 2:
        return 0.0

    windowed = audio_samples * np.hanning(len(audio_samples))
    spectrum = np.fft.rfft(windowed)
    magnitude = np.abs(spectrum)
    freqs = np.fft.rfftfreq(len(audio_samples), d=1.0 / sample_rate)

    if len(magnitude) <= 1:
        return 0.0

    peak_index = int(np.argmax(magnitude[1:])) + 1  # skip bin DC (indeks 0)
    return float(freqs[peak_index])


def should_send(rms: float) -> bool:
    """Tahap 1: tentukan apakah window ini layak dikirim ke processing-server."""
    return rms > AMPLITUDE_THRESHOLD
