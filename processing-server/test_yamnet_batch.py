"""Test classify_glass_break_yamnet() ke semua file di edge-audio/samples/
(kaca pecah) dan edge-audio/samples1/ (non-event) sekaligus.

Cara pakai (dari folder processing-server, venv aktif):
    python test_yamnet_batch.py

Script ini otomatis convert tiap .wav ke 16kHz mono dulu (syarat YAMNet)
pakai ffmpeg, simpan di folder sementara _yamnet_16k/, baru dites.
"""

import os
import subprocess
import sys

from classify_audio import classify_glass_break_yamnet

SAMPLES_DIR = os.path.join("..", "edge-audio", "samples")       # kaca pecah
SAMPLES1_DIR = os.path.join("..", "edge-audio", "samples1")     # non-event
TMP_DIR = "_yamnet_16k"


def convert_to_16k(src_path: str, dst_path: str):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src_path, "-ar", "16000", "-ac", "1", dst_path],
        check=True,
    )


def run_batch(folder: str, label: str):
    if not os.path.isdir(folder):
        print(f"(folder {folder} tidak ditemukan, dilewati)")
        return []

    results = []
    wav_files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".wav") and "_16k" not in f)

    for fname in wav_files:
        src = os.path.join(folder, fname)
        dst = os.path.join(TMP_DIR, f"{label}_{fname}")
        convert_to_16k(src, dst)
        result = classify_glass_break_yamnet(dst)
        results.append((fname, result))

    return results


def main():
    os.makedirs(TMP_DIR, exist_ok=True)

    print("=== samples/ (kaca pecah, harus is_glass_break=True) ===")
    glass_results = run_batch(SAMPLES_DIR, "glass")
    for fname, r in glass_results:
        mark = "OK " if r["is_glass_break"] else "XX "
        print(f"{mark}{fname:45s} confidence={r['confidence']:.4f}  {r}")

    print()
    print("=== samples1/ (non-event, harus is_glass_break=False) ===")
    nonevent_results = run_batch(SAMPLES1_DIR, "nonevent")
    for fname, r in nonevent_results:
        mark = "OK " if not r["is_glass_break"] else "XX "
        print(f"{mark}{fname:45s} confidence={r['confidence']:.4f}  {r}")

    print()
    n_glass_correct = sum(1 for _, r in glass_results if r["is_glass_break"])
    n_nonevent_correct = sum(1 for _, r in nonevent_results if not r["is_glass_break"])
    print(f"Ringkasan: kaca pecah benar {n_glass_correct}/{len(glass_results)}, "
          f"non-event benar {n_nonevent_correct}/{len(nonevent_results)}")


if __name__ == "__main__":
    sys.exit(main())
