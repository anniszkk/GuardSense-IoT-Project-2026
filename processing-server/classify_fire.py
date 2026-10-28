"""GuardSense: klasifikasi gas-suhu dan estimasi lokasi."""

# Ambang awal yang sama dengan firmware.
# Nilai final harus disesuaikan setelah kalibrasi.
GAS_RATE_THRESHOLD = 5.0
TEMP_RATE_THRESHOLD = 0.5


def classify_fire(
    gas_rate_of_rise: float,
    temp_rate_of_rise: float,
) -> dict:
    """Kandidat kebakaran jika gas DAN suhu naik melewati ambang."""

    gas_rising = gas_rate_of_rise >= GAS_RATE_THRESHOLD
    temp_rising = temp_rate_of_rise >= TEMP_RATE_THRESHOLD

    is_fire = gas_rising and temp_rising

    if is_fire:
        confidence = 0.8
    elif gas_rising or temp_rising:
        confidence = 0.3
    else:
        confidence = 0.0

    return {
        "is_fire": is_fire,
        "confidence": confidence,
        "gas_rising": gas_rising,
        "temp_rising": temp_rising,
    }


def estimate_source_location(readings: dict) -> str:
    """Pilih node yang memenuhi kedua ambang dan memiliki
    kenaikan gas paling cepat.
    """

    candidates = {}

    for device_id, data in readings.items():
        if not isinstance(data, dict):
            continue

        try:
            gas_rate = float(data["gas_rate_of_rise"])
            temp_rate = float(data["temp_rate_of_rise"])
        except (KeyError, TypeError, ValueError):
            continue

        if (
            gas_rate >= GAS_RATE_THRESHOLD
            and temp_rate >= TEMP_RATE_THRESHOLD
        ):
            candidates[device_id] = gas_rate

    if not candidates:
        return "belum_diketahui"

    return max(candidates, key=candidates.get)