"""PIC: Lila. Orkestrasi utama: subscribe MQTT, panggil klasifikasi
(classify_audio.py punya Annis, classify_fire.py punya Binar), publish alert,
dan serve dashboard di localhost:8000.
Lihat docx Bab 3 (arsitektur), Bab 6 (MQTT), Bab 7 (dashboard).

on_audio_message: klasifikasi audio lewat classify_audio.classify_audio_clip (Annis; YAMNet
utama, rule-based cadangan), liveness check bagian A (konteks TV/bicara/musik di klip yang sama)
dan bagian B (rasio RMS antar HP, butuh 2 HP aktif; ambang belum dikalibrasi), lalu cooldown alert.
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

# Jeda minimum antar alert untuk (device, jenis event) yang sama.
ALERT_COOLDOWN_S = 10.0
ALARM_COOLDOWN_S = 30.0  # alarm asap berbunyi terus-menerus, jadi jedanya lebih panjang daripada kaca
_last_alert_at = {}  # (device_id, event_type) -> epoch detik alert terakhir yang dikirim

# State khusus audio untuk liveness bagian B (sengaja terpisah dari latest_readings milik Lila).
# Waktu memakai jam SERVER saat klip tiba, bukan timestamp HP, karena jam dua HP bisa selisih beberapa detik.
AUDIO_KEEP_S = 60.0    # simpan RMS klip tiap HP selama ini
PEER_MATCH_S = 3.0     # klip HP lain yang tiba dalam +-3 detik dianggap meliput kejadian yang sama
PEER_ONLINE_S = 30.0   # HP lain dianggap aktif kalau ada klip dalam 30 detik terakhir
_recent_audio = {}     # device_id -> list[(waktu_tiba, rms)]


def _remember_audio(device_id: str, now: float, rms: float):
    entries = _recent_audio.setdefault(device_id, [])
    entries.append((now, rms))
    while entries and now - entries[0][0] > AUDIO_KEEP_S:
        entries.pop(0)


def check_amplitude_liveness(device_id: str, rms: float, now: float):
    """Liveness bagian B (Bab 5.2.1.1). Return (status, detail):
    - "tidak_ada_hp_lain": HP lain tidak aktif -> tidak menilai (tidak mengubah keputusan)
    - "timpang": satu HP jauh lebih keras -> kemungkinan kejadian lokal (kaca asli)
    - "setara": RMS kedua HP hampir sama -> kemungkinan sumber tersebar (TV)
    HP lain aktif tapi tidak mengirim klip di sekitar waktu itu = klipnya hening (di bawah gerbang
    RMS edge), jadi RMS-nya dianggap 0 (sangat pelan -> timpang).
    """
    active = {d: v for d, v in _recent_audio.items()
              if d != device_id and v and now - v[-1][0] <= PEER_ONLINE_S}
    if not active:
        return "tidak_ada_hp_lain", None
    peer, peer_rms = None, -1.0
    for d, v in active.items():
        near = [r for (t, r) in v if abs(t - now) <= PEER_MATCH_S]
        r = max(near) if near else 0.0
        if r > peer_rms:
            peer, peer_rms = d, r
    ratio = classify_audio.amplitude_ratio(rms, peer_rms)
    equal = classify_audio.liveness_check_amplitude_ratio(rms, peer_rms)
    return ("setara" if equal else "timpang"), {"peer": peer, "own_rms": rms, "peer_rms": peer_rms, "ratio": ratio}


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

    now = time.time()
    rms = payload.get("rms_amplitude")
    if rms is not None:
        _remember_audio(device_id, now, rms)

    # YAMNet utama, rule-based fallback (lihat classify_audio.classify_audio_clip).
    result = classify_audio.classify_audio_clip(payload)
    print(f"[audio] {device_id} -> method={result['method']} glass={result['is_glass_break']} "
          f"conf={result['confidence']:.2f} alarm={result['is_alarm']} alarm_conf={result['alarm_confidence']:.2f} "
          f"media={result['is_media']}"
          + (f" (fallback: {result['fallback_reason']})" if result["fallback_reason"] else ""))

    # Dua jenis kejadian audio dengan logika liveness dan cooldown yang sama (jenis alert beda).
    if result["is_glass_break"]:
        _emit_audio_alert(client, device_id, "glass_break", result["confidence"], result, rms, now)
    if result["is_alarm"]:
        # Alarm yang hanya dikenali dari pola beep (YAMNet tidak yakin) kurang pasti: beep timer/microwave
        # berpola sama, jadi diberi label "perlu verifikasi" (alert tidak dibuang).
        extra = ["beep_pattern"] if result.get("alarm_source") == "beep_pattern" else []
        _emit_audio_alert(client, device_id, "fire_alarm", result["alarm_confidence"], result, rms, now, extra)


def _emit_audio_alert(client, device_id: str, base_type: str, confidence: float, result: dict, rms, now: float,
                      extra_reasons=()):
    """Liveness A+B lalu cooldown, lalu publish. base_type: "glass_break" | "fire_alarm"."""
    reasons = list(extra_reasons)
    # Bagian A liveness: terindikasi TV/media di klip yang sama -> "perlu verifikasi" (Bab 5.2.1.1).
    if result["is_media"]:
        reasons.append("media_context")
    # Bagian B liveness: RMS kedua HP hampir sama -> kemungkinan sumber tersebar seperti TV.
    # Ambang belum dikalibrasi; kegagalannya aman (hanya label, alert tidak dibuang).
    status, detail = check_amplitude_liveness(device_id, rms if rms is not None else 0.0, now)
    if status != "tidak_ada_hp_lain":
        print(f"[liveness-B] {device_id} rms={detail['own_rms']:.4f} {detail['peer']} rms={detail['peer_rms']:.4f} "
              f"rasio={detail['ratio']:.2f} (batas setara < {classify_audio.AMPLITUDE_RATIO_EQUAL_MAX}) -> {status}")
    if status == "setara":
        reasons.append("amplitude_equal")
    event_type = f"{base_type}_needs_verification" if reasons else base_type
    # Satu pecahan kaca biasanya menyebar ke 2-3 klip berurutan (lihat uji kaca4-8.m4a), dan alarm
    # berbunyi terus -- jangan kirim alert berulang untuk kejadian yang sama.
    cooldown = ALARM_COOLDOWN_S if base_type == "fire_alarm" else ALERT_COOLDOWN_S
    key = (device_id, event_type)
    since = now - _last_alert_at.get(key, 0.0)
    if since < cooldown:
        print(f"[audio] {device_id} {event_type} diredam (cooldown, {since:.1f}s < {cooldown:.0f}s)")
        return
    _last_alert_at[key] = now
    publish_alert(client, event_type=event_type, confidence=confidence,
                  source=device_id, reason=",".join(reasons) or None)


def on_env_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    print(f"[env] {payload}")
    # TODO: panggil classify_fire.classify_fire(...) dan estimate_source_location(...),
    # lalu publish AlertMessage kalau lolos.


def publish_alert(client, event_type: str, confidence: float, location_hint: str = None,
                  source: str = None, reason: str = None):
    alert = AlertMessage(event_type=event_type, confidence=confidence,
                          location_hint=location_hint, source=source, reason=reason)
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
