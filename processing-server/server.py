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
    # clip_b64 puluhan ribu karakter -- jangan ikut dicetak, ringkas saja.
    summary = {k: v for k, v in payload.items() if k != "clip_b64"}
    summary["clip_b64"] = f"<{len(payload.get('clip_b64') or '')} chars>"
    print(f"[audio] {summary}")

    device_id = payload.get("device_id", "unknown")
    if not payload.get("clip_b64") and any(
            payload.get(k) is None for k in ("rms_amplitude", "dominant_freq_hz", "duration_s")):
        # Tanpa klip, classify_audio_clip butuh ketiga fitur ini (lihat shared/messages.py AudioReading).
        print(f"[audio] payload tidak punya klip dan fiturnya belum lengkap, dilewati: {device_id}")
        return

    # YAMNet utama, rule-based fallback (lihat classify_audio.classify_audio_clip).
    result = classify_audio.classify_audio_clip(payload)
    print(f"[audio] {device_id} -> method={result['method']} glass={result['is_glass_break']} "
          f"conf={result['confidence']:.2f} media={result['is_media']}"
          + (f" (fallback: {result['fallback_reason']})" if result["fallback_reason"] else ""))

    # TODO (Annis): liveness bagian B (classify_audio.liveness_check_amplitude_ratio)
    # butuh RMS terakhir dari HP lain -- tunggu latest_readings (Lila) dan 2 HP aktif.

    if result["is_glass_break"]:
        # Bagian A liveness: terindikasi TV/media -> "perlu verifikasi", bukan ALERT penuh (Bab 5.2.1.1).
        event_type = "glass_break_needs_verification" if result["is_media"] else "glass_break"
        publish_alert(client, event_type=event_type,
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
