"""Kirim pesan env palsu (meniru firmware ESP32) ke broker, untuk menguji server tanpa Wokwi.

Cara pakai (dari folder processing-server, venv aktif, server.py sedang jalan):
    python publish_env.py bahaya    # dapur: lonjakan gas+suhu dua kali -> VERIFY lalu BAHAYA
    python publish_env.py lokasi    # dapur lalu kamar (gas kamar lebih cepat) -> lokasi berpindah ke kamar
    python publish_env.py tenang    # satu pesan laju nol (tidak boleh menimbulkan alert)

Payload sama dengan firmware: device_id, gas_ppm_est, gas_rate_of_rise, temperature_c, temp_rate_of_rise.
"""

import json
import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))  # jalan dari folder mana pun
from shared.mqtt_connection import create_client, topic


def kirim(client, device_id, gas, gas_rate, temp, temp_rate):
    payload = {"device_id": device_id, "gas_ppm_est": gas, "gas_rate_of_rise": gas_rate,
               "temperature_c": temp, "temp_rate_of_rise": temp_rate}
    info = client.publish(topic(f"edge/{device_id}/env"), json.dumps(payload))
    info.wait_for_publish()
    print(f"kirim {device_id}: gas_rate={gas_rate}, temp_rate={temp_rate}")


SKENARIO = {
    # (jeda detik sebelum kirim, device, gas, laju gas, suhu, laju suhu)
    "bahaya": [
        (0, "esp32_dapur", 2000, 20.5, 45.0, 8.1),
        (4, "esp32_dapur", 3000, 25.0, 65.0, 10.0),
    ],
    "lokasi": [
        (0, "esp32_dapur", 2000, 20.5, 45.0, 8.1),
        (4, "esp32_dapur", 3000, 25.0, 65.0, 10.0),
        (4, "esp32_kamar", 3500, 60.0, 55.0, 5.0),
        (4, "esp32_kamar", 4000, 90.0, 70.0, 7.0),
    ],
    "tenang": [
        (0, "esp32_dapur", 400, 0.0, 24.0, 0.0),
    ],
}


def main():
    nama = sys.argv[1] if len(sys.argv) > 1 else ""
    if nama not in SKENARIO:
        print(__doc__)
        sys.exit(1)
    client = create_client(role="publish-env")
    client.loop_start()
    time.sleep(1)
    for jeda, *data in SKENARIO[nama]:
        time.sleep(jeda)
        kirim(client, *data)
    time.sleep(1)
    client.loop_stop()
    client.disconnect()


if __name__ == "__main__":
    main()
