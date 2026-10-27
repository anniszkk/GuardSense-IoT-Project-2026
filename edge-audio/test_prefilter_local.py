"""Alat bantu testing prefilter.py DI LAPTOP, tanpa perlu HP/Termux.

Cara pakai:
    1. Download/siapkan beberapa file .wav contoh (16-bit PCM mono/stereo):
       - suara kaca pecah (cari di internet atau rekam sendiri)
       - suara lain yang BUKAN kaca (pintu dibanting, suara ngomong, dll)
    2. Jalankan:
           python test_prefilter_local.py path/ke/file.wav
    3. Catat nilai RMS dan frekuensi dominan tiap file, bandingkan antar
       kategori suara -- dari situ tentukan AMPLITUDE_THRESHOLD yang masuk
       akal di prefilter.py dan nilai ambang frekuensi di
       processing-server/classify_audio.py (Bab 5.2.1).

Catatan: script ini cuma baca WAV 16-bit PCM (format paling umum). Kalau
file kamu format lain (mp3, 24-bit, dll), convert dulu pakai ffmpeg, misal:
    ffmpeg -i input.mp3 -ar 44100 -ac 1 -sample_fmt s16 output.wav
"""

import sys
import wave

import numpy as np

from prefilter import compute_rms, compute_dominant_frequency


def load_wav_mono_float(path: str):
    with wave.open(path, "rb") as wf:
        n_frames = wf.getnframes()
        sample_rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        n_channels = wf.getnchannels()
        raw = wf.readframes(n_frames)

    if sampwidth != 2:
        raise ValueError(
            f"File ini {sampwidth * 8}-bit, script cuma support 16-bit PCM. "
            f"Convert dulu pakai ffmpeg (lihat docstring di atas)."
        )

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)  # mix ke mono
    data /= 32768.0  # normalisasi ke rentang -1..1
    return data, sample_rate


def main():
    if len(sys.argv) < 2:
        print("Pakai: python test_prefilter_local.py path/ke/file.wav")
        sys.exit(1)

    path = sys.argv[1]
    samples, sample_rate = load_wav_mono_float(path)

    rms = compute_rms(samples)
    freq = compute_dominant_frequency(samples, sample_rate)
    duration_s = len(samples) / sample_rate

    print(f"File               : {path}")
    print(f"Sample rate        : {sample_rate} Hz")
    print(f"Durasi             : {duration_s:.2f} detik")
    print(f"RMS amplitudo      : {rms:.4f}")
    print(f"Frekuensi dominan  : {freq:.1f} Hz")


if __name__ == "__main__":
    main()
