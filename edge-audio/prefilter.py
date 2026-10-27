"""Pre-filtering tahap 1 untuk audio (Bab 5.1).
TODO (Annis): isi fungsi di bawah, kalibrasi AMPLITUDE_THRESHOLD pakai sampel nyata.
"""

import numpy as np

# TODO: kalibrasi nilai ini pakai sampel suara nyata (Bab 9, skenario 1-3).
# Nilai sementara, HARUS diganti setelah uji coba.
AMPLITUDE_THRESHOLD = 0.3


def compute_rms(audio_samples: np.ndarray) -> float:
    """Hitung RMS amplitudo dari array sample audio (mono, float -1..1).
    TODO: isi implementasinya. Rumus: sqrt(mean(samples**2))
    """
    raise NotImplementedError("TODO: implementasikan compute_rms")


def compute_dominant_frequency(audio_samples: np.ndarray, sample_rate: int) -> float:
    """Hitung frekuensi dominan lewat FFT. Dipakai untuk klasifikasi awal
    (pecahan kaca biasanya > 3-4 kHz) — lihat Bab 5.2.1.
    TODO: isi implementasinya pakai np.fft.rfft.
    """
    raise NotImplementedError("TODO: implementasikan compute_dominant_frequency")


def should_send(rms: float) -> bool:
    """Tahap 1: tentukan apakah window ini layak dikirim ke processing-server."""
    return rms > AMPLITUDE_THRESHOLD
