"""GuardSense processing server
PIC: Lila. Orkestrasi utama: subscribe MQTT, simpan state device, panggil klasifikasi
audio (classify_audio punya Annis) dan gas/suhu (classify_fire punya Binar),
lakukan liveness check (A: media context, B: RMS ratio antar HP), cooldown alert,
publish alert ke topic alerts, dan host dashboard web Flask di localhost:8000.
Lihat docs/GuardSense_Dokumen_Proyek.md Bab 3, 5, 6, 7.
"""

import sys
import json
import time
import time as _real_time
import os
from collections import deque
import threading

def _format_time(epoch_sec: float) -> str:
    try:
        return _real_time.strftime("%H:%M:%S", _real_time.localtime(epoch_sec))
    except Exception:
        return f"{epoch_sec:.1f}s"

def _format_datetime(epoch_sec: float) -> str:
    try:
        return _real_time.strftime("%Y-%m-%d %H:%M:%S", _real_time.localtime(epoch_sec))
    except Exception:
        return f"{epoch_sec:.1f}s"

# Add repository root to sys.path so shared modules are importable
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

from shared.mqtt_connection import create_client, topic
from shared.messages import AlertMessage

import classify_audio
import classify_fire

# ---------------------------------------------------------------------------
# Global state (protected by lock because accessed from MQTT thread & Flask thread)
# ---------------------------------------------------------------------------
_state_lock = threading.Lock()
# device_id -> {"kind": "audio"|"env", "data": payload, "last_seen": epoch}
latest_readings: dict[str, dict] = {}
# Recent alert history (max 200 entries)
event_history: deque[dict] = deque(maxlen=200)
# Recent time-series telemetry for dashboard charts (max 300 entries)
telemetry_history: deque[dict] = deque(maxlen=300)
# Env cooldown tracker: (device_id, event_type, level) -> last publish epoch
_last_alert_time: dict[tuple, float] = {}
# Fire detection candidate buffer: device_id -> timestamp of first detection
_fire_candidate: dict[str, float] = {}

# ---------------------------------------------------------------------------
# Audio-specific state & helpers (liveness B & cooldown)
# ---------------------------------------------------------------------------
ALERT_COOLDOWN_S = 10.0
ALARM_COOLDOWN_S = 30.0  # alarm suara terus-menerus, jadi cooldown lebih panjang
_last_alert_at: dict[tuple[str, str], float] = {}  # (device_id, event_type) -> epoch

AUDIO_KEEP_S = 60.0    # keep RMS samples per HP for this many seconds
PEER_MATCH_S = 3.0     # consider another HP's sample if within +-3s
PEER_ONLINE_S = 30.0   # a HP is online for audio if it sent a sample within this window
_recent_audio: dict[str, list[tuple[float, float]]] = {}  # device_id -> [(timestamp, rms)]


def _now() -> float:
    return time.time()


def _is_online(last_seen: float, threshold: float = 15.0) -> bool:
    return (_now() - last_seen) < threshold


def _remember_audio(device_id: str, now: float, rms: float) -> None:
    entries = _recent_audio.setdefault(device_id, [])
    entries.append((now, rms))
    while entries and now - entries[0][0] > AUDIO_KEEP_S:
        entries.pop(0)


def check_amplitude_liveness(device_id: str, rms: float, now: float):
    """Liveness B – bandingkan RMS HP ini dengan RMS HP lain yang online dalam rentang waktu +-3 detik.
    Returns (status, detail):
        "tidak_ada_hp_lain" - HP lain tidak aktif
        "timpang" - amplitudo berbeda jauh (kemungkinan pecahan kaca lokal nyata)
        "setara" - amplitudo berimbang (kemungkinan TV / speaker media)
    """
    active = {
        d: v for d, v in _recent_audio.items()
        if d != device_id and v and now - v[-1][0] <= PEER_ONLINE_S
    }
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
    status = "setara" if equal else "timpang"
    detail = {"peer": peer, "own_rms": rms, "peer_rms": peer_rms, "ratio": ratio}
    return status, detail


# ---------------------------------------------------------------------------
# Helper to store incoming reading in the global state & telemetry history
# ---------------------------------------------------------------------------
def store_reading(msg, kind: str):
    """Parse JSON payload and store it in latest_readings and telemetry_history.
    Returns (device_id, payload) or None on failure.
    """
    try:
        payload = json.loads(msg.payload.decode())
    except (ValueError, UnicodeDecodeError):
        print(f"[{kind}] payload not valid JSON, ignored: {msg.payload!r}")
        return None
    device_id = payload.get("device_id") or msg.topic.split("/")[-2]
    now = _now()
    clean_data = {k: v for k, v in payload.items() if k != "clip_b64"}
    with _state_lock:
        latest_readings[device_id] = {"kind": kind, "data": clean_data, "last_seen": now}
        tele_item = {
            "timestamp": now,
            "time_str": _format_time(now),
            "device_id": device_id,
            "kind": kind,
        }
        if kind == "env":
            tele_item.update({
                "gas_ppm_est": payload.get("gas_ppm_est"),
                "gas_rate_of_rise": payload.get("gas_rate_of_rise"),
                "temperature_c": payload.get("temperature_c"),
                "temp_rate_of_rise": payload.get("temp_rate_of_rise"),
            })
        elif kind == "audio":
            tele_item.update({
                "rms_amplitude": payload.get("rms_amplitude", 0.0),
                "dominant_freq_hz": payload.get("dominant_freq_hz"),
            })
        telemetry_history.append(tele_item)
    return device_id, payload


# ---------------------------------------------------------------------------
# Audio handling (PIC Annis + Integrasi Lila)
# ---------------------------------------------------------------------------
def _fallback_glass_break(payload: dict) -> tuple[bool, float, str]:
    rms = payload.get("rms_amplitude", 0)
    freq = payload.get("dominant_freq_hz", 0)
    if freq > 3000 and rms > 0.02:
        return True, 0.7, "fallback heuristic"
    return False, 0.0, "fallback heuristic"


def on_audio_message(client, userdata, msg):
    payload = json.loads(msg.payload.decode())
    summary = {k: v for k, v in payload.items() if k != "clip_b64"}
    summary["clip_b64"] = f"<{len(payload.get('clip_b64') or '')} chars>"
    print(f"[audio] {summary}")

    device_id = payload.get("device_id", "unknown")
    if not payload.get("clip_b64") and any(
        payload.get(k) is None for k in ("rms_amplitude", "dominant_freq_hz", "duration_s")
    ):
        print(f"[audio] payload tidak punya klip dan fiturnya belum lengkap, dilewati: {device_id}")
        return

    now = _now()
    rms = payload.get("rms_amplitude")
    if rms is not None:
        _remember_audio(device_id, now, rms)

    # Store state for dashboard
    clean_data = {k: v for k, v in payload.items() if k != "clip_b64"}
    with _state_lock:
        latest_readings[device_id] = {"kind": "audio", "data": clean_data, "last_seen": now}
        telemetry_history.append({
            "timestamp": now,
            "time_str": _format_time(now),
            "device_id": device_id,
            "kind": "audio",
            "rms_amplitude": rms if rms is not None else 0.0,
            "dominant_freq_hz": payload.get("dominant_freq_hz"),
        })

    # Primary classification (YAMNet) with fallback to rule-based
    try:
        result = classify_audio.classify_audio_clip(payload)
    except NotImplementedError:
        broken, confidence, reason = _fallback_glass_break(payload)
        result = {
            "method": "fallback",
            "is_glass_break": broken,
            "confidence": confidence,
            "fallback_reason": reason,
            "is_alarm": False,
            "alarm_confidence": 0.0,
            "is_media": False,
            "alarm_source": None,
        }
    except Exception as e:
        print(f"[audio] classification error: {e}")
        return

    print(
        f"[audio] {device_id} -> method={result['method']} glass={result['is_glass_break']} "
        f"conf={result['confidence']:.2f} alarm={result['is_alarm']} alarm_conf={result['alarm_confidence']:.2f} "
        f"media={result['is_media']}"
        + (f" (fallback: {result['fallback_reason']})" if result.get("fallback_reason") else "")
    )

    if result["is_glass_break"]:
        _emit_audio_alert(client, device_id, "glass_break", result["confidence"], result, rms, now)
    if result["is_alarm"]:
        extra = ["beep_pattern"] if result.get("alarm_source") == "beep_pattern" else []
        _emit_audio_alert(client, device_id, "fire_alarm", result["alarm_confidence"], result, rms, now, extra)


def _emit_audio_alert(
    client,
    device_id: str,
    base_type: str,
    confidence: float,
    result: dict,
    rms,
    now: float,
    extra_reasons=(),
):
    """Combine liveness A (media context) and B (RMS ratio) then publish.
    base_type is "glass_break" or "fire_alarm".
    """
    reasons = list(extra_reasons)
    if result["is_media"]:
        reasons.append("media_context")

    status, detail = check_amplitude_liveness(device_id, rms if rms is not None else 0.0, now)
    if status != "tidak_ada_hp_lain":
        print(
            f"[liveness-B] {device_id} rms={detail['own_rms']:.4f} {detail['peer']} rms={detail['peer_rms']:.4f} "
            f"ratio={detail['ratio']:.2f} (threshold < {classify_audio.AMPLITUDE_RATIO_EQUAL_MAX}) -> {status}"
        )
    if status == "setara":
        reasons.append("amplitude_equal")
    event_type = f"{base_type}_needs_verification" if reasons else base_type
    cooldown = ALARM_COOLDOWN_S if base_type == "fire_alarm" else ALERT_COOLDOWN_S
    key = (device_id, event_type)
    since = now - _last_alert_at.get(key, 0.0)
    if since < cooldown:
        print(f"[audio] {device_id} {event_type} suppressed (cooldown {since:.1f}s < {cooldown}s)")
        return
    _last_alert_at[key] = now
    level = "VERIFY" if reasons else "ALERT"
    publish_alert(
        client,
        event_type=event_type,
        confidence=confidence,
        source=device_id,
        reason=",".join(reasons) or None,
        level=level,
    )


# ---------------------------------------------------------------------------
# Environment handling (PIC Binar + Integrasi Lila)
# ---------------------------------------------------------------------------
def _fallback_fire(payload: dict) -> tuple[bool, float, str]:
    gas = payload.get("gas_rate_of_rise", 0)
    temp = payload.get("temp_rate_of_rise", 0)
    if gas > 0.5 and temp > 2:
        return True, 0.7, "fallback heuristic"
    return False, 0.0, "fallback heuristic"


def on_env_message(client, userdata, msg):
    result = store_reading(msg, "env")
    if result is None:
        return
    device_id, payload = result
    print(f"[env] {device_id}: {payload}")

    gas_rate = payload.get("gas_rate_of_rise", 0.0)
    temp_rate = payload.get("temp_rate_of_rise", 0.0)

    try:
        res = classify_fire.classify_fire(gas_rate, temp_rate)
        if isinstance(res, dict):
            fire = res.get("is_fire", False)
            confidence = res.get("confidence", 0.0)
            reason = "gas_temp_rate_of_rise" if fire else "threshold_not_met"
        elif isinstance(res, (tuple, list)):
            fire = res[0]
            confidence = res[1] if len(res) > 1 else 0.0
            reason = res[2] if len(res) > 2 else "gas_temp_rate_of_rise"
        else:
            fire, confidence, reason = bool(res), 0.5, "gas_temp_rate_of_rise"
    except NotImplementedError:
        fire, confidence, reason = _fallback_fire(payload)
    except Exception as e:
        print(f"[env] classification error: {e}")
        return

    if not fire:
        return

    now = _now()
    with _state_lock:
        last = _fire_candidate.get(device_id)
        if last and (now - last) <= 10.0:
            level = "ALERT"
            _fire_candidate.pop(device_id, None)
        else:
            _fire_candidate[device_id] = now
            level = "VERIFY"

    # Estimasi lokasi sumber menggunakan fungsi Binar
    location_hint = device_id
    try:
        with _state_lock:
            env_readings = {
                d: info["data"] for d, info in latest_readings.items()
                if info.get("kind") == "env" and isinstance(info.get("data"), dict)
            }
        estimated = classify_fire.estimate_source_location(env_readings)
        if estimated and estimated != "belum_diketahui":
            location_hint = estimated
    except Exception as e:
        print(f"[env] estimate location error: {e}")

    # Cooldown 20 detik per device & level agar tidak banjir alert
    key = (device_id, "fire_smoke", level)
    with _state_lock:
        last_pub = _last_alert_time.get(key, 0.0)
        if now - last_pub < 20.0:
            print(f"[env] {device_id} fire_smoke suppressed (cooldown {now - last_pub:.1f}s < 20s)")
            return
        _last_alert_time[key] = now

    event_type = "fire_smoke" if level == "ALERT" else "fire_smoke_needs_verification"
    publish_alert(
        client,
        event_type=event_type,
        confidence=confidence,
        location_hint=location_hint,
        source=device_id,
        reason=reason,
        level=level,
    )


# ---------------------------------------------------------------------------
# Alert publishing & history tracking
# ---------------------------------------------------------------------------
def publish_alert(
    client,
    event_type: str,
    confidence: float,
    location_hint: str = None,
    source: str = None,
    reason: str = None,
    level: str = None,
):
    if level is None:
        if "needs_verification" in event_type:
            level = "VERIFY"
        elif event_type == "normal":
            level = "NORMAL"
        else:
            level = "ALERT"

    now = _now()
    alert = AlertMessage(
        event_type=event_type,
        confidence=confidence,
        location_hint=location_hint,
        source=source,
        reason=reason,
    )
    client.publish(topic("alerts"), json.dumps(alert.to_dict()), retain=True)
    with _state_lock:
        event_history.append(
            {
                "timestamp": now,
                "event_type": event_type,
                "confidence": confidence,
                "location_hint": location_hint,
                "source": source,
                "level": level,
                "reason": reason or "auto",
            }
        )
    print(f"[ALERT] {alert.to_dict()} level={level}")


# ---------------------------------------------------------------------------
# Flask dashboard API (PIC Lila)
# ---------------------------------------------------------------------------
def create_flask_app():
    from flask import Flask, jsonify, send_from_directory

    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard"))
    app = Flask(__name__, static_folder=static_dir)

    @app.route("/")
    def root():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/<path:path>")
    def static_files(path):
        return send_from_directory(app.static_folder, path)

    @app.route("/api/state")
    def api_state():
        with _state_lock:
            state = {}
            for dev, info in latest_readings.items():
                data = info["data"].copy()
                data["online"] = _is_online(info["last_seen"])
                state[dev] = {
                    "kind": info["kind"],
                    "data": data,
                    "last_seen": info["last_seen"],
                }
            now = _now()
            overall = "NORMAL"
            for ev in list(event_history)[-20:]:
                if now - ev["timestamp"] < 30:
                    if ev["level"] == "ALERT":
                        overall = "ALERT"
                        break
                    elif ev["level"] == "VERIFY":
                        overall = "VERIFY"
        return jsonify({"devices": state, "overall": overall, "timestamp": now})

    @app.route("/api/events")
    def api_events():
        with _state_lock:
            raw_events = list(event_history)[::-1]
        events = []
        for ev in raw_events:
            item = ev.copy()
            ts = item.get("timestamp", 0)
            if isinstance(ts, (int, float)):
                item["time_str"] = _format_datetime(ts)
            else:
                item["time_str"] = str(ts)
            events.append(item)
        return jsonify(events)

    @app.route("/api/telemetry")
    def api_telemetry():
        with _state_lock:
            items = list(telemetry_history)[-100:]
        return jsonify(items)

    return app


def _run_flask():
    app = create_flask_app()
    # Host on 0.0.0.0 so devices on the same WiFi/hotspot can access the dashboard
    app.run(host="0.0.0.0", port=8000, debug=False, use_reloader=False)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main():
    # Start Flask dashboard in background daemon thread
    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()
    print("Dashboard web server berjalan di http://0.0.0.0:8000 (akses via localhost:8000)")

    client = create_client(role="processing-server")
    client.on_message = None  # callbacks set via message_callback_add
    client.message_callback_add(topic("edge/+/audio"), on_audio_message)
    client.message_callback_add(topic("edge/+/env"), on_env_message)
    client.subscribe(topic("edge/+/audio"))
    client.subscribe(topic("edge/+/env"))
    client.loop_start()
    print("Processing server jalan, subscribe ke semua topic edge...")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Berhenti.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
