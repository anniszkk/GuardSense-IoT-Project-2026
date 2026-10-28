"""Uji logika liveness bagian B (rasio RMS dua HP) di server.py, TANPA HP dan TANPA MQTT.

Cara pakai (dari folder processing-server, venv aktif):
    python test_liveness_b.py

Memakai payload "tanpa klip" (jalur rule lama di classify_audio_clip) supaya cepat dan tidak
butuh TensorFlow; yang diuji adalah keputusan alert dari state dua HP, bukan YAMNet.
Waktu dipalsukan (FakeTime) supaya skenario selisih detik bisa diatur persis.
"""

import json
import sys

sys.path.append("..")
import server


class FakeTime:
    def __init__(self):
        self.t = 0.0

    def time(self):
        return self.t


class FakeClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, **kw):
        self.published.append(json.loads(payload))


class Msg:
    def __init__(self, d):
        self.payload = json.dumps(d).encode()


def clip(device, rms, glass):
    # glass=True: frekuensi 5 kHz -> rule lama menganggap kaca; False: 200 Hz -> bukan kaca.
    return {"device_id": device, "rms_amplitude": rms,
            "dominant_freq_hz": 5000.0 if glass else 200.0, "duration_s": 2.0}


def fresh():
    server._recent_audio.clear()
    server._last_alert_at.clear()
    ft = FakeTime()
    server.time = ft
    return ft, FakeClient()


def send(ft, client, t, d):
    ft.t = t
    server.on_audio_message(client, None, Msg(d))


def run(name, steps, expect_type, expect_reason=None):
    ft, c = fresh()
    for t, d in steps:
        send(ft, c, t, d)
    got = [(a["event_type"], a["reason"]) for a in c.published]
    ok = got == [(expect_type, expect_reason)]
    print(("OK   " if ok else "GAGAL"), name, "->", got)
    return ok


results = [
    run("1. hanya HP A (tidak ada HP lain)",
        [(100, clip("hpA", 0.03, True))],
        "glass_break"),
    run("2. RMS kedua HP setara (kemungkinan TV)",
        [(100, clip("hpB", 0.020, False)), (101, clip("hpA", 0.021, True))],
        "glass_break_needs_verification", "amplitude_equal"),
    run("3. HP A jauh lebih keras (kemungkinan kaca asli)",
        [(100, clip("hpB", 0.007, False)), (101, clip("hpA", 0.05, True))],
        "glass_break"),
    run("4. HP B aktif tapi tidak ada klip di sekitar kejadian (hening -> timpang)",
        [(70, clip("hpB", 0.007, False)), (100, clip("hpA", 0.04, True))],
        "glass_break"),
    run("5. HP B sudah lama tidak terlihat (dianggap mati -> tidak menilai)",
        [(0, clip("hpB", 0.007, False)), (100, clip("hpA", 0.04, True))],
        "glass_break"),
    run("6. klip HP B di luar jendela +-3 detik tidak dihitung (timpang)",
        [(95, clip("hpB", 0.04, False)), (100, clip("hpA", 0.04, True))],
        "glass_break"),
]

# 7. Dua alasan sekaligus: konteks media (bagian A) + RMS setara (bagian B) lewat jalur fungsi langsung.
ft, c = fresh()
server.classify_audio.classify_audio_clip = lambda payload, _orig=server.classify_audio.classify_audio_clip: {
    **_orig(payload), "is_media": True}
send(ft, c, 100, clip("hpB", 0.020, False))
send(ft, c, 101, clip("hpA", 0.021, True))
got = [(a["event_type"], a["reason"]) for a in c.published]
ok7 = got == [("glass_break_needs_verification", "media_context,amplitude_equal")]
print(("OK   " if ok7 else "GAGAL"), "7. media + setara (dua alasan)", "->", got)
results.append(ok7)

print()
print(f"{sum(results)}/{len(results)} skenario lolos")
sys.exit(0 if all(results) else 1)
