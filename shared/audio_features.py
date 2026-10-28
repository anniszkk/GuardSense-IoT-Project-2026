"""Fitur audio yang dipakai di edge-audio/ (HP) DAN processing-server/ (laptop,
untuk fallback rule-based), jadi ditaruh di shared/ supaya tidak diduplikasi.
"""

import numpy as np

HF_CUTOFF_HZ = 2000.0   # batas bawah "band tinggi" (pecahan kaca banyak energi di atas ini)
HF_HIGHPASS_HZ = 200.0  # buang rumble/dengung/handling noise sebelum dihitung
_FRAME = 2048


def high_band_ratio(audio_samples: np.ndarray, sample_rate: int) -> float:
    """Rasio energi band tinggi (>= HF_CUTOFF_HZ) terhadap total energi
    (>= HF_HIGHPASS_HZ), dihitung hanya di frame-frame yang energinya
    mendekati puncak window.

    Pengganti FFT satu window penuh + argmax ("frekuensi dominan"): untuk
    window 2 detik berisi event transient singkat, bising rendah yang
    berlangsung terus-menerus (mic HP, dengung ruangan) menenggelamkan puncak
    event dan hasilnya jadi ~100 Hz. Rasio per-frame-keras tidak terpengaruh.
    Return 0.0..1.0.
    """
    if audio_samples.size < _FRAME:
        return 0.0

    freqs = np.fft.rfftfreq(_FRAME, d=1.0 / sample_rate)
    window = np.hanning(_FRAME)
    hop = _FRAME // 2
    totals, highs = [], []
    for i in range(0, audio_samples.size - _FRAME + 1, hop):
        power = np.abs(np.fft.rfft(audio_samples[i:i + _FRAME] * window)) ** 2
        power[freqs < HF_HIGHPASS_HZ] = 0.0
        totals.append(power.sum())
        highs.append(power[freqs >= HF_CUTOFF_HZ].sum())

    totals = np.array(totals)
    highs = np.array(highs)
    loud = totals >= 0.3 * totals.max()
    denom = totals[loud].sum()
    if denom <= 0:
        return 0.0
    return float(highs[loud].sum() / denom)
