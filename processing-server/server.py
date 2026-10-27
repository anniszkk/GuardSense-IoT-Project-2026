"""PIC: Lila. Orkestrasi utama: subscribe MQTT, panggil klasifikasi
(classify_audio.py punya Annis, classify_fire.py punya Binar), publish alert,
dan serve dashboard di localhost:8000.
Lihat docx Bab 3 (arsitektur), Bab 6 (MQTT), Bab 7 (dashboard).

on_audio_message sudah manggil classify_audio.classify_glass_break (Annis,
rule-based, sudah tervalidasi pakai sampel nyata -- lihat edge-audio/samples).
Liveness check (Bab 5.2.1.1) BELUM disambung di sini -- masih TODO, butuh
2 HP jalan bareng untuk classify_audio.liveness_check_amplitude_ratio.
classify_glass_break_yamnet (opsional/AI) juga belum dipanggil di sini
by default karena berat (butuh TensorFlow) -- lihat processing-server/README.md.
"""

import sys
import json
import time

sys.path.append("..")
from shared.mqtt_connection import create_client, topic
from shared.messages import AlertMessage

import classify_audio
import classify_fire

# TODO (Lila): simpan state terakhir tiap device di sini (untuk dashboard & rate-of-rise)
latest_readings = {}


def on_audio_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    print(f"[audio] {payload}")

    device_id = payload.get("device_id", "unknown")
    rms = payload.get("rms_amplitude")
    freq = payload.get("dominant_freq_hz")
    duration = payload.get("duration_s")

    if rms is None or freq is None or duration is None:
        # Payload dari edge-audio belum lengkap (lihat shared/messages.py
        # AudioReading) -- butuh rms_amplitude, dominant_freq_hz, duration_s
        # semua terisi supaya classify_glass_break bisa jalan.
        print(f"[audio] payload belum lengkap (butuh rms_amplitude, dominant_freq_hz, "
              f"duration_s), dilewati: {payload}")
        return

    result = classify_audio.classify_glass_break(rms, freq, duration)
    print(f"[audio] classify_glass_break -> {result}")

    # TODO (Annis): sebelum publish alert, panggil liveness check di sini dulu
    # (classify_audio.liveness_check_context / liveness_check_amplitude_ratio)
    # supaya suara TV/media tidak memicu alert palsu -- lihat Bab 5.2.1.1.
    # Butuh minimal 2 HP terpasang untuk amplitude_ratio.

    if result["is_glass_break"]:
        publish_alert(client, event_type="glass_break",
                       confidence=result["confidence"], source=device_id)


def on_env_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    print(f"[env] {payload}")
    # TODO: panggil classify_fire.classify_fire(...) dan estimate_source_location(...),
    # lalu publish AlertMessage kalau lolos.


def publish_alert(client, event_type: str, confidence: float, location_hint: str = None, source: str = None):
    alert = AlertMessage(event_type=event_type, confidence=confidence,
                          location_hint=location_hint, source=source)
    client.publish(topic("alerts"), json.dumps(alert.to_dict()), retain=True)
    print(f"[ALERT] {alert.to_dict()}")


def main():
    client = create_client(role="processing-server")
    client.on_message = None  # set per-topic callback lewat message_callback_add

    client.message_callback_add(topic("edge/+/audio"), on_audio_message)
    client.message_callback_add(topic("edge/+/env"), on_env_message)
    client.subscribe(topic("edge/+/audio"))
    client.subscribe(topic("edge/+/env"))

    client.loop_start()
    print("Processing server jalan, subscribe ke semua topic edge...")

    # TODO (Lila): start dashboard web server di sini (Flask, port 8000)
    # dari folder ../dashboard/

    try:
        while True:
            time.sleep(1)  # loop MQTT jalan di thread lain (loop_start()), ini cuma nahan proses hidup
    except KeyboardInterrupt:
        print("Berhenti.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
