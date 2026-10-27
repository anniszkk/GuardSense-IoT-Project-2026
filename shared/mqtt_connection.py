"""Satu implementasi koneksi MQTT, dipakai SEMUA node Python
(edge-audio/ dan processing-server/). Jangan duplikasi logika ini di tempat lain.

Diadaptasi dari pola yang sama dengan contoh PocketGuard
(https://github.com/myudak/contoh-project-iot1/blob/main/shared/mqtt_connection.py).
"""

import os
import uuid

from dotenv import load_dotenv
import paho.mqtt.client as mqtt

load_dotenv()

# Default: HiveMQ public broker. Tidak perlu akun; siapa pun bisa baca topic publik.
DEFAULT_HOST = "broker.hivemq.com"
DEFAULT_PROJECT_ID = "guardsense_kelompok_03"


def project_id() -> str:
    value = os.getenv("PROJECT_ID", DEFAULT_PROJECT_ID)
    if not value.replace("_", "").replace("-", "").isalnum():
        raise ValueError("PROJECT_ID hanya boleh berisi huruf, angka, - dan _")
    return value


def topic(suffix: str) -> str:
    """Contoh: topic('edge/hpA/audio') -> 'guardsense/<PROJECT_ID>/edge/hpA/audio'
    Lihat docs/GuardSense_Dokumen_Proyek.docx Bab 6.2 untuk daftar topic lengkap.
    """
    return f"guardsense/{project_id()}/{suffix}"


def create_client(role: str, will: tuple[str, str] | None = None) -> mqtt.Client:
    """Connect ke broker sesuai .env. `will` = (topic, payload) yang dipublish
    broker (retained) kalau client ini putus koneksi tiba-tiba."""
    host = os.getenv("MQTT_HOST") or DEFAULT_HOST
    if project_id() == DEFAULT_PROJECT_ID:
        print(f"[MQTT] Peringatan: PROJECT_ID masih default '{DEFAULT_PROJECT_ID}'. "
              f"Ganti di .env supaya topic tidak bercampur dengan kelompok lain.")

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"{project_id()}-{role}-{uuid.uuid4().hex[:8]}",
        protocol=mqtt.MQTTv311,
    )
    username = os.getenv("MQTT_USERNAME", "")
    password = os.getenv("MQTT_PASSWORD", "")
    if username:
        client.username_pw_set(username, password)

    use_tls = os.getenv("MQTT_TLS", "true").lower() == "true"
    if use_tls:
        client.tls_set()
    else:
        if os.getenv("ALLOW_INSECURE_LOCAL") != "true":
            raise RuntimeError("TLS dimatikan. Hanya boleh untuk development lokal lewat ALLOW_INSECURE_LOCAL=true")

    if will is not None:
        client.will_set(will[0], will[1], qos=1, retain=True)

    port = int(os.getenv("MQTT_PORT", "8883" if use_tls else "1883"))
    client.connect(host, port, keepalive=30)
    return client
