"""Bandingin langsung hasil classify_glass_break (non-AI, rule-based) vs
classify_glass_break_yamnet (AI) untuk file yang SAMA -- biar kelihatan
kalau ada yang beda, dan apakah threshold rule-based (FREQ_THRESHOLD_HZ,
MIN_RMS, MAX_DURATION_S di classify_audio.py) perlu diubah.

Ini murni alat VALIDASI yang jalan lokal di laptop (server), TIDAK lewat
MQTT -- jadi aman dipakai bolak-balik buat ngecek audio baru tanpa nambah
beban ke broker publik. Pipeline live tetap cuma pakai classify_glass_break
(non-AI) lewat server.py seperti biasa.

Cara pakai (dari folder processing-server, venv aktif, butuh tensorflow +
tensorflow-hub + soundfile sudah terinstall):

  1) Mode batch -- cek semua file di edge-audio/samples/ (kaca pecah) dan
     edge-audio/samples1/ (non-event) sekaligus:
         python test_crosscheck.py

  2) Mode satu file -- cek file audio BARU tanpa perlu dipindah ke folder
     samples/ dulu, kasih langsung path-nya:
         python test_crosscheck.py path/ke/audio_baru.wav

Untuk tiap file, script ini:
  1. Hitung RMS + frekuensi dominan + durasi pakai fungsi yang SAMA dengan
     yang dipakai HP asli (edge_audio.prefilter), bukan dihitung ulang
     dengan cara lain -- supaya hasilnya representatif dengan pipeline asli.
  2. Jalankan classify_glass_break (non-AI) dari angka-angka itu.
  3. Convert ke 16kHz mono, jalankan classify_glass_break_yamnet (AI).
  4. Cetak tabel perbandingan + tandai kalau dua-duanya TIDAK sepakat.
"""

import os
import subprocess
import sys
import wave

import numpy as np

sys.path.insert(0, os.path.join("..", "edge-audio"))
from prefilter import compute_rms, compute_dominant_frequency  # noqa: E402

import classify_audio  # noqa: E402

SAMPLES_DIR = os.path.join("..", "edge-audio", "samples")
SAMPLES1_DIR = os.path.join("..", "edge-audio", "samples1")
TMP_DIR = "_crosscheck_16k"


def load_wav_mono_float(path: str):
    with wave.open(path, "rb") as wf:
        n_frames = wf.getnframes()
        sample_rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        n_channels = wf.getnchannels()
        raw = wf.readframes(n_frames)

    if sampwidth != 2:
        raise ValueError(f"{path}: harus 16-bit PCM, ini {sampwidth * 8}-bit")

    data = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
    if n_channels > 1:
        data = data.reshape(-1, n_channels).mean(axis=1)
    data /= 32768.0
    return data, sample_rate


def convert_to_16k(src_path: str, dst_path: str):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src_path, "-ar", "16000", "-ac", "1", dst_path],
        check=True,
    )


def run_file(path: str, fname: str, label: str):
    samples, sample_rate = load_wav_mono_float(path)
    rms = compute_rms(samples)
    freq = compute_dominant_frequency(samples, sample_rate)
    duration_s = len(samples) / sample_rate

    rule_result = classify_audio.classify_glass_break(rms, freq, duration_s)

    dst_16k = os.path.join(TMP_DIR, f"{label}_{fname}")
    convert_to_16k(path, dst_16k)
    yamnet_result = classify_audio.classify_glass_break_yamnet(dst_16k)

    return {
        "rms": rms,
        "freq": freq,
        "duration_s": duration_s,
        "rule": rule_result,
        "yamnet": yamnet_result,
    }


def run_folder(folder: str, label: str):
    if not os.path.isdir(folder):
        return []
    wav_files = sorted(f for f in os.listdir(folder) if f.lower().endswith(".wav") and "_16k" not in f)
    return [(fname, run_file(os.path.join(folder, fname), fname, label)) for fname in wav_files]


def print_section(title: str, results: list, expected: bool):
    print(f"=== {title} (harapannya is_glass_break={expected}) ===")
    disagreements = 0
    for fname, r in results:
        rule_v = r["rule"]["is_glass_break"]
        yamnet_v = r["yamnet"]["is_glass_break"]
        agree = rule_v == yamnet_v
        both_correct = rule_v == expected and yamnet_v == expected
        mark = "OK " if both_correct else ("!! " if not agree else "XX ")
        if not agree:
            disagreements += 1
        print(
            f"{mark}{fname:45s} "
            f"rms={r['rms']:.4f} freq={r['freq']:7.1f}Hz dur={r['duration_s']:.2f}s | "
            f"rule={rule_v!s:5} (conf={r['rule']['confidence']:.2f}) | "
            f"yamnet={yamnet_v!s:5} (conf={r['yamnet']['confidence']:.4f})"
        )
    print(f"-> {disagreements} file dengan hasil rule-based vs YAMNet BERBEDA\n")
    return disagreements


def main():
    os.makedirs(TMP_DIR, exist_ok=True)

    glass_results = run_folder(SAMPLES_DIR, "glass")
    nonevent_results = run_folder(SAMPLES1_DIR, "nonevent")

    d1 = print_section("samples/ (kaca pecah)", glass_results, True)
    d2 = print_section("samples1/ (non-event)", nonevent_results, False)

    total_disagree = d1 + d2
    if total_disagree == 0:
        print("Rule-based dan YAMNet SEPAKAT di semua file -> threshold rule-based "
              "(FREQ_THRESHOLD_HZ, MIN_RMS, MAX_DURATION_S) sudah cukup baik, "
              "tidak perlu diubah berdasarkan data ini.")
    else:
        print(f"Ada {total_disagree} file yang hasilnya beda antara rule-based dan YAMNet -- "
              f"cek baris bertanda '!!' di atas, pertimbangkan sesuaikan threshold "
              f"di classify_audio.py (FREQ_THRESHOLD_HZ / MIN_RMS / MAX_DURATION_S).")


if __name__ == "__main__":
    main()
