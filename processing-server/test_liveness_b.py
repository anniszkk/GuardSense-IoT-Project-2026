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

def alarm_result(media=False, source="yamnet"):
    return {"is_glass_break": False, "confidence": 0.0, "is_alarm": True, "alarm_confidence": 0.9,
            "alarm_source": source, "method": "yamnet", "is_media": media, "fallback_reason": None}


# 8-11. Alarm asap: logika liveness sama dengan kaca, jenis alert fire_alarm, cooldown 30 detik.
orig_classify = server.classify_audio.classify_audio_clip
quiet = {**alarm_result(), "is_alarm": False, "alarm_confidence": 0.0, "alarm_source": None}
# Hanya HP A yang "mendengar" alarm; klip HP lain dianggap bukan alarm (cuma jadi pembanding RMS).
server.classify_audio.classify_audio_clip = lambda payload: alarm_result() if payload["device_id"] == "hpA" else quiet
ft, c = fresh()
send(ft, c, 100, clip("hpA", 0.03, False))
got = [(a["event_type"], a["reason"]) for a in c.published]
ok8 = got == [("fire_alarm", None)]
print(("OK   " if ok8 else "GAGAL"), "8. alarm, hanya HP A", "->", got)
results.append(ok8)

ft, c = fresh()
send(ft, c, 100, clip("hpB", 0.020, False))
send(ft, c, 101, clip("hpA", 0.021, False))
got = [(a["event_type"], a["reason"]) for a in c.published]
ok9 = got == [("fire_alarm_needs_verification", "amplitude_equal")]
print(("OK   " if ok9 else "GAGAL"), "9. alarm, RMS dua HP setara", "->", got)
results.append(ok9)

ft, c = fresh()
send(ft, c, 100, clip("hpA", 0.03, False))
send(ft, c, 115, clip("hpA", 0.03, False))   # 15 dtk: kaca sudah lewat cooldown 10, alarm belum (30)
send(ft, c, 135, clip("hpA", 0.03, False))   # 35 dtk sejak alert pertama: lolos lagi
got = [a["event_type"] for a in c.published]
ok10 = got == ["fire_alarm", "fire_alarm"]
print(("OK   " if ok10 else "GAGAL"), "10. cooldown alarm 30 detik", "->", got)
results.append(ok10)
# 11. Alarm yang hanya dikenali dari pola beep (YAMNet tidak yakin) -> perlu verifikasi.
server.classify_audio.classify_audio_clip = lambda payload: alarm_result(source="beep_pattern")
ft, c = fresh()
send(ft, c, 100, clip("hpA", 0.03, False))
got = [(a["event_type"], a["reason"]) for a in c.published]
ok11 = got == [("fire_alarm_needs_verification", "beep_pattern")]
print(("OK   " if ok11 else "GAGAL"), "11. alarm hanya dari pola beep", "->", got)
results.append(ok11)
server.classify_audio.classify_audio_clip = orig_classify

print()
print(f"{sum(results)}/{len(results)} skenario lolos")
sys.exit(0 if all(results) else 1)
