"""Demo estimasi lokasi sumber asap dari pesan env ESP32 (Wokwi), TANPA mengubah server.py.

Cara pakai (dari folder processing-server, venv aktif):
    python demo_lokasi.py            # live: dengarkan edge/+/env dari Wokwi dapur dan kamar
    python demo_lokasi.py --simulasi # offline: tiga skenario bawaan, tanpa MQTT

Pembacaan tiap node disimpan dengan waktu tiba di server dan kedaluwarsa setelah JENDELA_S detik,
karena firmware hanya mengirim saat ada lonjakan (tidak ada pesan "sudah tenang").
"""

import json
import sys
import time

sys.path.append("..")
import classify_fire

JENDELA_S = 30.0
latest = {}  # device_id -> {"gas_rate_of_rise", "temp_rate_of_rise", "at"}


def tampilkan(now):
    aktif = {d: r for d, r in latest.items() if now - r["at"] <= JENDELA_S}
    for d in list(latest):
        if d not in aktif:
            del latest[d]
    print(f"\n  node aktif (<= {JENDELA_S:.0f} dtk): {len(aktif)}")
    for d, r in aktif.items():
        c = classify_fire.classify_fire(r["gas_rate_of_rise"], r["temp_rate_of_rise"])
        print(f"    {d}: gas {r['gas_rate_of_rise']:.1f}/dtk, suhu {r['temp_rate_of_rise']:.1f} C/dtk "
              f"-> {'KEBAKARAN' if c['is_fire'] else 'bukan'} (conf {c['confidence']})")
    print(f"  => lokasi sumber: {classify_fire.estimate_source_location(aktif)}")


def terima(device_id, gas_rate, temp_rate, now):
    latest[device_id] = {"gas_rate_of_rise": gas_rate, "temp_rate_of_rise": temp_rate, "at": now}
    print(f"[env] {device_id}: gas_rate={gas_rate}, temp_rate={temp_rate}")
    tampilkan(now)


def simulasi():
    print("Skenario 1: hanya dapur, gas dan suhu naik")
    terima("esp32_dapur", 20.5, 8.1, 0)
    print("\nSkenario 2: kamar gasnya lebih cepat tapi suhu tidak naik -> tetap dapur")
    terima("esp32_kamar", 60.0, 0.1, 5)
    print("\nSkenario 3: kamar juga memenuhi dua ambang dengan gas lebih cepat -> pindah ke kamar")
    terima("esp32_kamar", 90.0, 3.0, 8)
    print("\nSkenario 4: 40 detik kemudian tidak ada pesan baru -> kedaluwarsa")
    tampilkan(48)


def live():
    from shared.mqtt_connection import create_client, topic

    def on_env(client, userdata, msg):
        p = json.loads(msg.payload.decode())
        terima(p["device_id"], p["gas_rate_of_rise"], p["temp_rate_of_rise"], time.time())

    client = create_client(role="demo-lokasi")
    client.message_callback_add(topic("edge/+/env"), on_env)
    client.subscribe(topic("edge/+/env"))
    client.loop_start()
    print("Mendengarkan edge/+/env ... (Ctrl+C untuk berhenti)")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    simulasi() if "--simulasi" in sys.argv else live()
