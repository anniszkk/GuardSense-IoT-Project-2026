"""Jalan di HP A dan HP B lewat Termux (python hp_edge.py).
Rekam audio -> pre-filter -> publish ke MQTT kalau lolos ambang.

TODO (Annis):
  1. Ganti DEVICE_ID jadi "hpA" di HP pertama, "hpB" di HP kedua.
  2. Isi record_audio_window() pakai termux-microphone-record.
  3. Isi prefilter.compute_rms() dan compute_dominant_frequency() di prefilter.py.
"""

import sys
import time

sys.path.append("..")  # supaya bisa import shared/
from shared.mqtt_connection import create_client, topic
from shared.messages import AudioReading
from prefilter import compute_rms, compute_dominant_frequency, should_send

# TODO: ganti sesuai HP ("hpA" di satu HP, "hpB" di HP satunya)
DEVICE_ID = "hpA"

WINDOW_SECONDS = 1.5


def record_audio_window():
    """TODO: rekam audio WINDOW_SECONDS detik lewat termux-microphone-record,
    baca file .wav hasilnya, kembalikan (samples: np.ndarray, sample_rate: int).
    """
    raise NotImplementedError("TODO: implementasikan record_audio_window")


def main():
    client = create_client(role=DEVICE_ID)
    client.loop_start()
    print(f"[{DEVICE_ID}] Mulai merekam & memantau audio...")

    try:
        while True:
            samples, sample_rate = record_audio_window()
            rms = compute_rms(samples)

            if should_send(rms):
                freq = compute_dominant_frequency(samples, sample_rate)
                reading = AudioReading(
                    device_id=DEVICE_ID,
                    rms_amplitude=rms,
                    dominant_freq_hz=freq,
                )
                client.publish(topic(f"edge/{DEVICE_ID}/audio"), str(reading.to_dict()))
                print(f"[{DEVICE_ID}] Terkirim: rms={rms:.3f} freq={freq}")

            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"[{DEVICE_ID}] Berhenti.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
