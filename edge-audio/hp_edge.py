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

import base64
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
from shared.audio_features import high_band_ratio
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
        # Jaga-jaga kalau suatu saat WAV masuk sini masih multi-channel
        # (normalnya sudah mono dari ffmpeg "pan=mono|c0=c0"): pilih channel
        # RMS terbesar, JANGAN rata-ratakan (lihat catatan phase cancellation
        # di convert_to_16k's ffmpeg command di atas).
        data = data.reshape(-1, n_channels)
        channel_rms = np.sqrt(np.mean(np.square(data, dtype=np.float64), axis=0))
        data = data[:, int(np.argmax(channel_rms))]
    data /= 32768.0
    return data, sample_rate


# Rincian waktu siklus rekam terakhir (detik), dicetak di main() -- buat cari tahu
# kenapa satu siklus ~7 detik padahal window cuma 2 detik (jeda tak terekam = event bisa lolos).
_last_timing = ""


def record_audio_window():
    """Rekam audio WINDOW_SECONDS detik lewat termux-microphone-record,
    kembalikan (samples: np.ndarray mono float -1..1, sample_rate: int).

    termux-microphone-record TIDAK bisa rekam langsung ke .wav -- cuma
    support encoder aac/amr_nb/amr_wb/opus -- jadi direkam ke .m4a (AAC)
    dulu, baru di-convert ke .wav 16-bit PCM pakai ffmpeg.
    """
    global _last_timing
    t0 = time.time()
    for p in (_RECORD_PATH, _WAV_PATH):
        if os.path.exists(p):
            os.remove(p)  # hapus sisa rekaman sebelumnya, supaya tidak salah baca file lama

    # Langsung start (TANPA "-q" dulu): tiap panggilan termux-microphone-record makan
    # ~1 detik (Termux:API menyalakan proses baru), dan rekaman siklus sebelumnya sudah
    # di-stop di akhir record_audio_window(). "-q" cuma dipanggil kalau start menolak
    # karena masih ada rekaman nyangkut (misal dari error/Ctrl+C sebelumnya).
    # PENTING: stop/quit yang benar itu "-q", BUKAN "-d" ("-d" = mulai rekaman default).
    for attempt in range(5):
        start = subprocess.run(
            # -r/-b/-c WAJIB eksplisit: tanpa -r, termux merekam di 8000 Hz (AAC 12 kbps),
            # semua suara > 4 kHz hilang padahal ciri kaca pecah ada di sana (rasio
            # band tinggi = 0, YAMNet cuma "dengar" Vehicle). 16 kHz = syarat YAMNet.
            ["termux-microphone-record", "-f", _RECORD_PATH, "-l", str(int(WINDOW_SECONDS)), "-e", "aac",
             "-r", "16000", "-b", "64", "-c", "1"],
            capture_output=True, text=True,
        )
        if "already in progress" not in start.stdout.lower() and "already in progress" not in start.stderr.lower():
            break
        print(f"[{DEVICE_ID}] Masih ada rekaman lama nyangkut, stop dulu... ({attempt + 1}/5)")
        subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
        time.sleep(0.5)
    else:
        raise RuntimeError(
            "Gagal mulai rekaman baru setelah beberapa percobaan -- ada rekaman lama "
            "yang tidak mau berhenti. Coba jalankan manual: termux-microphone-record -q"
        )
    t_started = time.time()
    # termux-microphone-record cuma mengirim perintah ke background service lalu
    # langsung return -- rekaman baru benar-benar selesai setelah WINDOW_SECONDS.
    time.sleep(WINDOW_SECONDS)

    # Beri sedikit waktu supaya "-l" menghentikan rekaman & menulis metadata akhir m4a
    # (moov atom). "-q" eksplisit TIDAK dipanggil di jalur normal karena makan ~1 detik;
    # kalau file ternyata belum valid (ffmpeg gagal), baru di-stop paksa lalu dicoba lagi.
    time.sleep(0.4)
    t_stopped = time.time()

    def _convert():
        if not os.path.exists(_RECORD_PATH):
            return False
        # PENTING: filter "pan=mono|c0=c0" (ambil channel kiri), BUKAN "-ac 1" biasa --
        # "-ac 1" merata-ratakan kedua channel, dan kalau stereo-nya tidak sefase (kejadian
        # nyata di HP) rata-rata itu bisa saling membatalkan sinyal (phase cancellation).
        # 16 kHz = syarat input YAMNet, klipnya jadi kecil (~64 KB / 2 detik).
        r = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", _RECORD_PATH,
             "-ar", "16000", "-af", "pan=mono|c0=c0", "-sample_fmt", "s16", _WAV_PATH],
            capture_output=True,
        )
        return r.returncode == 0 and os.path.exists(_WAV_PATH)

    if not _convert():
        subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
        time.sleep(0.5)
        if not _convert():
            raise RuntimeError(
                "File rekaman tidak ditemukan/tidak valid. Pastikan aplikasi Termux:API ter-install "
                "(dari F-Droid, bukan cuma `pkg install termux-api`) dan izin mikrofon "
                "sudah diberikan ke aplikasi itu."
            )
    t_converted = time.time()

    result = _load_wav_mono_float(_WAV_PATH)
    _last_timing = (f"mulai={t_started - t0:.1f}s rekam={t_stopped - t_started:.1f}s "
                    f"ffmpeg={t_converted - t_stopped:.1f}s")
    return result


def main():
    client = create_client(role=DEVICE_ID)
    client.loop_start()
    print(f"[{DEVICE_ID}] Mulai merekam & memantau audio...")

    try:
        while True:
            t_cycle = time.time()
            samples, sample_rate = record_audio_window()
            rms = compute_rms(samples)

            if should_send(rms):
                freq = compute_dominant_frequency(samples, sample_rate)
                duration_s = len(samples) / sample_rate
                with open(_WAV_PATH, "rb") as f:
                    clip_b64 = base64.b64encode(f.read()).decode("ascii")
                reading = AudioReading(
                    device_id=DEVICE_ID,
                    rms_amplitude=rms,
                    dominant_freq_hz=freq,
                    duration_s=duration_s,
                    high_band_ratio=high_band_ratio(samples, sample_rate),
                    sample_rate=sample_rate,
                    clip_b64=clip_b64,
                )
                # json.dumps, BUKAN str(dict) -- str(dict) pakai tanda kutip
                # satu (bukan JSON valid) dan bikin server.py gagal parse
                # lewat json.loads().
                client.publish(topic(f"edge/{DEVICE_ID}/audio"), json.dumps(reading.to_dict()))
                print(f"[{DEVICE_ID}] Terkirim: rms={rms:.3f} freq={freq:.1f} dur={duration_s:.2f} "
                      f"| {_last_timing} total={time.time() - t_cycle:.1f}s")

            time.sleep(0.1)
    except KeyboardInterrupt:
        print(f"[{DEVICE_ID}] Berhenti.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
