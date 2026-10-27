"""PIC: Binar. Klasifikasi kebakaran (korelasi gas-suhu) + estimasi lokasi.
Lihat docx Bab 5.2.2.
"""


def classify_fire(gas_rate_of_rise: float, temp_rate_of_rise: float) -> dict:
    """ALERT hanya kalau rate-of-rise gas DAN suhu sama-sama lewat ambang
    dalam rentang waktu yang sama (Bab 5.2.2).
    TODO: isi threshold hasil kalibrasi (Bab 9, skenario 6-7).
    Return dict: {"is_fire": bool, "confidence": float}
    """
    raise NotImplementedError("TODO: implementasikan classify_fire")


def estimate_source_location(readings: dict) -> str:
    """readings: {"esp32_dapur": {...}, "esp32_kamar": {...}}
    Return nama device dengan kadar gas tertinggi/kenaikan tercepat (Bab 5.2.2, Bab 9 No. 8).
    TODO: implementasikan.
    """
    raise NotImplementedError("TODO: implementasikan estimate_source_location")
