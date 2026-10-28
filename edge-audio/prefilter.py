"""Fitur audio sederhana di edge (Bab 5.1): RMS dan frekuensi dominan.

AMPLITUDE_THRESHOLD (0.005) hanya membuang keheningan nyaris total, BUKAN membedakan
jenis suara. Pada rekaman mikrofon HP asli, RMS tidak bisa membedakan kaca pecah dari
suara lain: klip kaca RMS-nya cuma 0.007-0.02, setara atau lebih pelan dari bising
angin/kendaraan dan jauh lebih pelan dari suara sesudahnya (disapu/diinjak). Pembedaan
kaca vs suara lain sepenuhnya dilakukan di processing-server (YAMNet; lihat
processing-server/classify_audio.py dan docs Bab 5.1 serta 9.1).

compute_dominant_frequency hanya informasi tambahan di payload: pada window yang
berisi bising rendah yang berlangsung terus (mic HP) hasilnya ~100 Hz walau ada kaca
pecah, jadi tidak dipakai untuk keputusan.

should_send dipakai mode "window" (EDGE_MODE=window); mode utama "continuous"
memakai gerbang yang sama lewat continuous_capture.MIN_RMS.
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
    """Hitung frekuensi dominan lewat FFT (informasi tambahan; tidak dipakai untuk
    keputusan kaca, lihat docstring modul).

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
