"""PIC: Lila. Orkestrasi utama: subscribe MQTT, panggil klasifikasi
(classify_audio.py punya Annis, classify_fire.py punya Binar), publish alert,
dan serve dashboard di localhost:8000.
Lihat docx Bab 3 (arsitektur), Bab 6 (MQTT), Bab 7 (dashboard).
"""

import sys
import json

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
    # TODO: panggil classify_audio.classify_glass_break(...) / liveness check,
    # lalu publish AlertMessage kalau lolos semua pengecekan.


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
            pass
    except KeyboardInterrupt:
        print("Berhenti.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
