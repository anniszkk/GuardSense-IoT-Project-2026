"""Skema payload MQTT yang dipakai semua node, supaya formatnya konsisten
antara edge-audio, esp32-firmware (lihat versi C++ di config.h/main.cpp),
dan processing-server. Lihat docs/GuardSense_Dokumen_Proyek.docx Bab 6.2.
"""

import time
from dataclasses import dataclass, asdict


@dataclass
class AudioReading:
    """Dipublish oleh edge-audio/ ke topic edge/<device_id>/audio
    setelah lolos pre-filter (Bab 5.1)."""
    device_id: str          # "hpA" atau "hpB"
    rms_amplitude: float    # hasil pre-filter tahap 1
    dominant_freq_hz: float | None = None
    duration_s: float | None = None   # panjang window rekaman, dipakai classify_glass_break (Bab 5.2.1)
    high_band_ratio: float | None = None  # rasio energi >2 kHz (lihat shared/audio_features.py)
    sample_rate: int | None = None    # sample rate klip (16000, syarat YAMNet)
    clip_b64: str | None = None       # klip WAV 16-bit mono, base64 -- input YAMNet di server
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EnvReading:
    """Dipublish oleh esp32-firmware ke topic edge/<device_id>/env
    setelah lolos pre-filter rate-of-rise (Bab 5.1)."""
    device_id: str          # "esp32_dapur" atau "esp32_kamar"
    gas_ppm_est: float
    gas_rate_of_rise: float
    temperature_c: float
    temp_rate_of_rise: float
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AlertMessage:
    """Dipublish oleh processing-server ke topic alerts (Bab 5.2 & 6.2)."""
    event_type: str          # "glass_break" | "glass_break_needs_verification" | "fire_alarm" | "fire_alarm_needs_verification" | "fire_smoke" | "fire_smoke_needs_verification" | "normal"
    confidence: float        # 0.0 - 1.0
    location_hint: str | None = None   # misal "dapur", "kamar"
    source: str | None = None          # device_id yang memicu
    reason: str | None = None          # kenapa "needs_verification": "media_context" | "amplitude_equal" | "beep_pattern" (alarm hanya dari pola beep); untuk fire_smoke: "gas_temp_rate_of_rise" (gas dan suhu naik melewati ambang); bisa lebih dari satu, dipisah koma
    timestamp: float = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()

    def to_dict(self) -> dict:
        return asdict(self)
