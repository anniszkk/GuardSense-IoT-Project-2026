"""PIC: Annis. Klasifikasi audio (pecahan kaca) + liveness check.
Lihat docx Bab 5.2.1 dan 5.2.1.1.
"""


def classify_glass_break(rms_amplitude: float, dominant_freq_hz: float, duration_s: float) -> dict:
    """Pendekatan A (rule-based) -- Bab 5.2.1.
    TODO: isi threshold hasil kalibrasi (Bab 9, skenario 1-3).
    Return dict: {"is_glass_break": bool, "confidence": float}
    """
    raise NotImplementedError("TODO: implementasikan classify_glass_break (rule-based)")


def classify_glass_break_yamnet(audio_clip_path: str) -> dict:
    """Pendekatan B (AI, opsional/upgrade) -- Bab 5.2.1.
    TODO: load YAMNet, ambil skor kelas Glass shatter / Glass / Breaking /
    Crockery breaking and smashing.
    Return dict: {"is_glass_break": bool, "confidence": float}
    """
    raise NotImplementedError("TODO: implementasikan classify_glass_break_yamnet (opsional)")


def liveness_check_context(yamnet_scores: dict) -> bool:
    """Bagian A liveness check (Bab 5.2.1.1): True kalau terindikasi suara TV/media
    (skor Television/Speech/Music tinggi bersamaan), False kalau event murni.
    TODO: implementasikan.
    """
    raise NotImplementedError("TODO: implementasikan liveness_check_context")


def liveness_check_amplitude_ratio(rms_hp_a: float, rms_hp_b: float) -> bool:
    """Bagian B liveness check (Bab 5.2.1.1): True kalau rasio amplitudo antar
    dua HP relatif SETARA (indikasi sumber tersebar seperti TV), False kalau
    timpang (indikasi event lokal/asli).
    TODO: implementasikan + tentukan ambang rasio hasil kalibrasi.
    """
    raise NotImplementedError("TODO: implementasikan liveness_check_amplitude_ratio")
