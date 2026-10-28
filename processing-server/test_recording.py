"""Uji klasifikasi pada REKAMAN SENDIRI (misal dari HP), tanpa MQTT/server.

Cara pakai (dari folder processing-server, venv aktif):
    python test_recording.py rekaman1.m4a rekaman2.wav ...

Tiap file dipotong jadi window 2 detik (geser 1 detik, mirip window di
hp_edge.py), lalu tiap window dijalankan lewat jalur yang sama dengan server:
gerbang RMS -> YAMNet (skor kaca + konteks TV/Speech/Music) dan fallback
rule-based (rasio band tinggi) sebagai pembanding. Kolom `top3` = 3 kelas
YAMNet dengan skor tertinggi di window itu, buat lihat apa yang "didengar" model.

Format apa pun yang bisa dibaca ffmpeg boleh (m4a, mp3, wav, ogg).
"""

import os
import subprocess
import sys
import tempfile
import wave

import numpy as np

sys.path.append("..")
import classify_audio
from shared.audio_features import high_band_ratio

SR = 16000
WINDOW_S = 2.0
HOP_S = 1.0
RMS_GATE = 0.02  # sama dengan AMPLITUDE_THRESHOLD di edge-audio/prefilter.py


def load_16k_mono(path: str) -> np.ndarray:
    """Convert pakai ffmpeg seperti hp_edge.py (ambil channel kiri, JANGAN rata-rata)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "x.wav")
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", path,
             "-ar", str(SR), "-af", "pan=mono|c0=c0", "-sample_fmt", "s16", out],
            check=True,
        )
        with wave.open(out, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def top3(waveform, model, names) -> str:
    scores = model(waveform)[0].numpy().max(axis=0)
    idx = np.argsort(scores)[::-1][:3]
    return ", ".join(f"{names[i]} {scores[i]:.2f}" for i in idx)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    model, names = classify_audio._load_yamnet()
    win, hop = int(WINDOW_S * SR), int(HOP_S * SR)

    for path in sys.argv[1:]:
        x = load_16k_mono(path)
        print(f"\n=== {path}  ({len(x) / SR:.1f} detik) ===")
        print(f"{'t(s)':>5} {'rms':>6} {'gate':>5} {'yamnet':>7} {'glass':>5} {'media':>5} "
              f"{'hf':>5} {'rule':>5}  top3")
        starts = range(0, max(1, len(x) - win + 1), hop)
        n_glass = 0
        for s in starts:
            w = x[s:s + win]
            rms = float(np.sqrt(np.mean(np.square(w, dtype=np.float64))))
            y = classify_audio.analyze_yamnet(w)
            is_glass = y["glass_score"] > classify_audio.YAMNET_CONFIDENCE_THRESHOLD
            is_media = classify_audio.liveness_check_context(y["media_scores"])
            rule = classify_audio.classify_glass_break_hf(w)
            gate = rms > RMS_GATE
            n_glass += int(is_glass and gate)
            print(f"{s / SR:5.1f} {rms:6.3f} {'ya' if gate else 'tdk':>5} {y['glass_score']:7.2f} "
                  f"{'YA' if is_glass else '-':>5} {'TV?' if is_media else '-':>5} "
                  f"{high_band_ratio(w, SR):5.2f} {'YA' if rule['is_glass_break'] else '-':>5}  "
                  f"{top3(w, model, names)}")
        print(f"-> window lolos gerbang RMS & YAMNet bilang kaca: {n_glass}")
        print("   (kolom 'gate' = apakah edge akan mengirim window ini; 'rule' = hasil fallback)")


if __name__ == "__main__":
    main()
