"""PIC: Lila. Orkestrasi utama: subscribe MQTT, simpan state device, (nanti) panggil
klasifikasi, publish alert, dan serve dashboard di localhost:8000.
"""

import sys
import json
import time
import threading
import os
from collections import deque

import os
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(repo_root)
from shared.mqtt_connection import create_client, topic
from shared.messages import AlertMessage

import classify_audio
import classify_fire

# ---------------------------------------------------------------------------
# Global state (protected by lock because accessed from MQTT thread & Flask thread)
# ---------------------------------------------------------------------------
_state_lock = threading.Lock()
# device_id -> {"kind": "audio"/"env", "data": payload, "last_seen": epoch}
latest_readings: dict[str, dict] = {}
# Recent alert history (max 200 entries)
event_history: deque[dict] = deque(maxlen=200)
# Cool‑down tracker: (event_type, location) -> last publish epoch
_last_alert_time: dict[tuple[str, str | None], float] = {}
# Fire detection buffer: location -> timestamp of last candidate detection
_fire_candidate: dict[str, float] = {}

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _now() -> float:
    return time.time()

def _is_online(last_seen: float, threshold: float = 15.0) -> bool:
    return (_now() - last_seen) < threshold

# ---------------------------------------------------------------------------
# MQTT callbacks
# ---------------------------------------------------------------------------
def on_connect(client, userdata, flags, reason_code, properties):
    print(f"[MQTT] connect: {reason_code}")
    client.subscribe(topic("edge/+/audio"))
    client.subscribe(topic("edge/+/env"))

def store_reading(msg, kind: str):
    """Parse JSON payload and store it in ``latest_readings``.
    Returns (device_id, payload) or ``None`` on failure.
    """
    try:
        payload = json.loads(msg.payload.decode())
    except (ValueError, UnicodeDecodeError):
        print(f"[{kind}] payload bukan JSON valid, diabaikan: {msg.payload!r}")
        return None
    device_id = payload.get("device_id") or msg.topic.split("/")[-2]
    with _state_lock:
        latest_readings[device_id] = {"kind": kind, "data": payload, "last_seen": _now()}
    return device_id, payload

# ---------------------------------------------------------------------------
# Audio handling
# ---------------------------------------------------------------------------
def _fallback_glass_break(payload: dict) -> tuple[bool, float, str]:
    # Simple heuristic: high dominant freq & RMS
    rms = payload.get("rms_amplitude", 0)
    freq = payload.get("dominant_freq_hz", 0)
    if freq > 3000 and rms > 0.02:
        return True, 0.7, "fallback heuristic"
    return False, 0.0, "fallback heuristic"

def on_audio_message(client, userdata, msg):
    result = store_reading(msg, "audio")
    if result is None:
        return
    device_id, payload = result
    print(f"[audio] {device_id}: {payload}")

    rms = payload.get("rms_amplitude")
    freq = payload.get("dominant_freq_hz")
    duration = payload.get("duration_s")

    # Try real classification, fallback otherwise
    try:
        broken, confidence, reason = classify_audio.classify_glass_break(rms, freq, duration)
    except NotImplementedError:
        broken, confidence, reason = _fallback_glass_break(payload)
    except Exception as e:
        print(f"[audio] error in classify_glass_break: {e}")
        broken, confidence, reason = False, 0.0, str(e)

    if not broken:
        return

    # Liveness / cross‑device check – gather recent audio readings (3 s window)
    with _state_lock:
        now = _now()
        recent = {
            dev: info["data"] for dev, info in latest_readings.items()
            if info["kind"] == "audio" and now - info["last_seen"] <= 3.0
        }
    # Need both hpA and hpB to decide level
    hpA = recent.get("hpA")
    hpB = recent.get("hpB")
    level = "VERIFY"
    if hpA and hpB:
        rmsA = hpA.get("rms_amplitude", 0)
        rmsB = hpB.get("rms_amplitude", 0)
        # Compute symmetric ratio safely (avoid div zero)
        ratio = max(rmsA, rmsB) / max(min(rmsA, rmsB), 0.001)
        try:
            # Original library returns True when amplitudes are comparable (TV)
            liveness = classify_audio.liveness_check_amplitude_ratio(rmsA, rmsB)
        except AttributeError:
            # Fallback: treat ratio <= 3 as comparable
            liveness = ratio <= 3
        if liveness:
            level = "VERIFY"  # amplitudes setara → kemungkinan TV
        else:
            level = "ALERT"   # satu HP jauh lebih keras → pecahan kaca
        try:
            # Prefer library function if available
            liveness = classify_audio.liveness_check_amplitude_ratio(rmsA, rmsB)
        except AttributeError:
            # Fallback: ratio > 3 indicates imbalance
            liveness = (max(rmsA, rmsB) / (min(rmsA, rmsB) + 1e-9)) > 3
        if liveness:
            level = "ALERT"  # one HP jauh lebih keras → pecahan kaca
        else:
            level = "VERIFY"  # rasio setara → kemungkinan TV
    else:
        # Only one device seen; treat as VERIFY (cannot decide)
        level = "VERIFY"

    publish_alert(client, event_type="glass_break", confidence=confidence, location_hint=device_id, source=device_id, level=level)

# ---------------------------------------------------------------------------
# Environment handling
# ---------------------------------------------------------------------------
def _fallback_fire(payload: dict) -> tuple[bool, float, str]:
    gas = payload.get("gas_rate_of_rise", 0)
    temp = payload.get("temp_rate_of_rise", 0)
    # BOTH must exceed thresholds
    if gas > 0.5 and temp > 2:
        return True, 0.7, "fallback heuristic"
    return False, 0.0, "fallback heuristic"

def on_env_message(client, userdata, msg):
    result = store_reading(msg, "env")
    if result is None:
        return
    device_id, payload = result
    print(f"[env] {device_id}: {payload}")

    try:
        fire, confidence, reason = classify_fire.classify_fire(
            payload.get("gas_rate_of_rise"), payload.get("temp_rate_of_rise")
        )
    except NotImplementedError:
        fire, confidence, reason = _fallback_fire(payload)
    except Exception as e:
        print(f"[env] error in classify_fire: {e}")
        fire, confidence, reason = False, 0.0, str(e)

    if not fire:
        return

    # Need two consecutive detections for real ALERT
    now = _now()
    with _state_lock:
        last = _fire_candidate.get(device_id)
        if last and now - last <= 5.0:
            # Second detection within 5 s → ALERT
            level = "ALERT"
            # reset candidate to avoid repeated alerts quickly
            _fire_candidate.pop(device_id, None)
        else:
            # First detection → store and publish VERIFY (optional)
            _fire_candidate[device_id] = now
            level = "VERIFY"
    publish_alert(client, event_type="fire_smoke", confidence=confidence, location_hint=device_id, source=device_id, level=level)

# ---------------------------------------------------------------------------
# Alert publishing with cooldown & history tracking
# ---------------------------------------------------------------------------
def publish_alert(client, event_type: str, confidence: float, location_hint: str = None, source: str = None, level: str = "ALERT"):
    key = (event_type, location_hint)
    now = _now()
    with _state_lock:
        last = _last_alert_time.get(key, 0)
        if now - last < 30:
            # cooldown active – skip publishing
            return
        _last_alert_time[key] = now
        alert = AlertMessage(event_type=event_type, confidence=confidence,
                             location_hint=location_hint, source=source)
        client.publish(topic("alerts"), json.dumps(alert.to_dict()), retain=True)
        # Record in history with explicit level
        event_history.append({
            "timestamp": now,
            "event_type": event_type,
            "confidence": confidence,
            "location_hint": location_hint,
            "source": source,
            "level": level,
            "reason": "auto" if confidence else "fallback",
        })
        print(f"[ALERT] {alert.to_dict()} level={level}")

# ---------------------------------------------------------------------------
# Flask dashboard API (runs in separate daemon thread)
# ---------------------------------------------------------------------------
def _run_flask():
    from flask import Flask, jsonify, send_from_directory
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "dashboard"))
    app = Flask(__name__, static_folder=static_dir)

    @app.route('/')
    def root():
        return send_from_directory(app.static_folder, "index.html")

    @app.route('/api/state')
    def api_state():
        with _state_lock:
            state = {}
            for dev, info in latest_readings.items():
                data = info["data"].copy()
                data["online"] = _is_online(info["last_seen"])
                state[dev] = {"kind": info["kind"], "data": data}
            # overall status based on recent alerts
            now = _now()
            overall = "NORMAL"
            for ev in list(event_history)[-20:]:
                if now - ev["timestamp"] < 30:
                    if ev["level"] == "ALERT":
                        overall = "ALERT"
                        break
                    elif ev["level"] == "VERIFY":
                        overall = "VERIFY"
        return jsonify({"devices": state, "overall": overall})

    @app.route('/api/events')
    def api_events():
        with _state_lock:
            events = list(event_history)[::-1]
        for ev in events:
            ev["timestamp"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ev["timestamp"]))
        return jsonify(events)

    app.run(host='0.0.0.0', port=8000, debug=False)

# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main():
    client = create_client(role="processing-server")
    client.on_connect = on_connect
    client.message_callback_add(topic("edge/+/audio"), on_audio_message)
    client.message_callback_add(topic("edge/+/env"), on_env_message)

    client.loop_start()
    print("Processing server jalan, menunggu data dari edge...")

    # Flask in daemon thread
    flask_thread = threading.Thread(target=_run_flask, daemon=True)
    flask_thread.start()

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
