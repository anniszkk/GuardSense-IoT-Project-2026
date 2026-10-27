"""Jalan di HP A dan HP B lewat Termux (python hp_edge.py).
Rekam audio -> pre-filter -> publish ke MQTT kalau lolos ambang.

TODO (Annis):
  1. Ganti DEVICE_ID jadi "hpA" di HP pertama, "hpB" di HP kedua.

Sebelum dijalankan di Termux, install dulu:
    pkg install termux-api ffmpeg
    pip install numpy paho-mqtt python-dotenv
Selain itu APLIKASI "Termux:API" (bukan cuma paketnya) harus ter-install
juga dari F-Droid, dan izin mikrofon harus diberikan ke app itu -- kalau
tidak, record_audio_window() bakal gagal dengan RuntimeError di bawah.
"""

import os
import json
import subprocess
import sys
import time
import wave

import numpy as np

sys.path.append("..")  # supaya bisa import shared/
from shared.mqtt_connection import create_client, topic
from shared.messages import AudioReading
from prefilter import compute_rms, compute_dominant_frequency, should_send

# TODO: ganti sesuai HP ("hpA" di satu HP, "hpB" di HP satunya)
DEVICE_ID = "hpA"

# HARUS integer -- termux-microphone-record -l dipakai sebagai angka bulat
# di shell script-nya, kalau kasih desimal (misal 1.5) bakal error "arithmetic
# syntax error" dan rekaman malah jadi unlimited (bukan berhenti sesuai durasi).
WINDOW_SECONDS = 2

_RECORD_PATH = "_rec_tmp.m4a"  # file rekaman mentah (AAC) dari termux-microphone-record
_WAV_PATH = "_rec_tmp.wav"     # hasil convert ke 16-bit PCM WAV, siap dipakai prefilter


def _load_wav_mono_float(path: str):
    """Sama persis dengan test_prefilter_local.py::load_wav_mono_float --
    dipakai di sini juga supaya hasil record_audio_window() format-nya
    konsisten dengan yang dipakai saat testing lokal."""
    with wave.open(path, "rb") as wf:
        n_frames = wf.getnframes()
        sample_rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        n_channels = wf.getnchannels()
        raw = wf.readframes(n_frames)

    if sampwidth != 2:
        raise ValueError(f"WAV hasil convert bukan 16-bit PCM ({sampwidth * 8}-bit)")

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)
    data /= 32768.0
    return data, sample_rate


def record_audio_window():
    """Rekam audio WINDOW_SECONDS detik lewat termux-microphone-record,
    kembalikan (samples: np.ndarray mono float -1..1, sample_rate: int).

    termux-microphone-record TIDAK bisa rekam langsung ke .wav -- cuma
    support encoder aac/amr_nb/amr_wb/opus -- jadi direkam ke .m4a (AAC)
    dulu, baru di-convert ke .wav 16-bit PCM pakai ffmpeg.
    """
    for p in (_RECORD_PATH, _WAV_PATH):
        if os.path.exists(p):
            os.remove(p)  # hapus sisa rekaman sebelumnya, supaya tidak salah baca file lama

    # Stop paksa kalau ada rekaman lama yang masih nyangkut (misal dari error
    # sebelumnya yang bikin durasi jadi unlimited). Diabaikan kalau memang
    # tidak ada rekaman yang jalan (exit code non-zero itu wajar di kasus ini).
    subprocess.run(["termux-microphone-record", "-d"], capture_output=True)
    time.sleep(0.3)

    subprocess.run(
        ["termux-microphone-record", "-f", _RECORD_PATH, "-l", str(int(WINDOW_SECONDS)), "-e", "aac"],
        check=True,
    )
    # termux-microphone-record cuma mengirim perintah ke background service lalu
    # langsung return -- rekaman baru benar-benar selesai setelah WINDOW_SECONDS,
    # jadi harus nunggu dulu sebelum baca filenya (+0.5s buffer).
    time.sleep(WINDOW_SECONDS + 0.5)

    if not os.path.exists(_RECORD_PATH):
        raise RuntimeError(
            "File rekaman tidak ditemukan. Pastikan aplikasi Termux:API ter-install "
            "(dari F-Droid, bukan cuma `pkg install termux-api`) dan izin mikrofon "
            "sudah diberikan ke aplikasi itu."
        )

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", _RECORD_PATH,
         "-ar", "44100", "-ac", "1", "-sample_fmt", "s16", _WAV_PATH],
        check=True,
    )

    return _load_wav_mono_float(_WAV_PATH)


def main():
    client = create_client(role=DEVICE_ID)
    client.loop_start()
    print(f"[{DEVICE_ID}] Mulai merekam & memantau audio...")

    try:
        while True:
            samples, sample_rate = record_audio_window()
            rms = compute_rms(samples)

            if should_send(rms):
                freq = compute_dominant_frequency(samples, sample_rate)
                duration_s = len(samples) / sample_rate
                reading = AudioReading(
                    device_id=DEVICE_ID,
                    rms_amplitude=rms,
                    dominant_freq_hz=freq,
                    duration_s=duration_s,
                )
                # json.dumps, BUKAN str(dict) -- str(dict) pakai tanda kutip
                # satu (bukan JSON valid) dan bikin server.py gagal parse
                # lewat json.loads().
                client.publish(topic(f"edge/{DEVICE_ID}/audio"), json.dumps(reading.to_dict()))
                print(f"[{DEVICE_ID}] Terkirim: rms={rms:.3f} freq={freq:.1f} dur={duration_s:.2f}")

            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"[{DEVICE_ID}] Berhenti.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
