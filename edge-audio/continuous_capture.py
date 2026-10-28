"""Mode rekam-terus untuk hp_edge.py: satu proses rekam berjalan tanpa berhenti,
skrip membaca file tiap ~1 detik dan mengirim klip 3 detik tiap 2 detik (tumpang-tindih
1 detik), selama klip itu tidak hening.

Kenapa: mode per-window (rekam 2 detik -> stop -> mulai lagi) punya jeda ~1.3-2.5 detik
tiap siklus (tiap panggilan termux-microphone-record ~1 detik), sehingga kaca yang pecah
di jeda tidak terekam dan yang jatuh di batas window terpotong. Di sini tidak ada jeda,
dan karena klip saling tumpang-tindih, kejadian <= 1 detik selalu utuh di setidaknya satu klip.

Kenapa BUKAN trigger lonjakan suara: dicoba (lonjakan RMS dan lonjakan energi > 2 kHz) dan
tidak membedakan kaca dari suara lain di rekaman mic HP -- negatif punya lonjakan sebesar
kaca, sedangkan kaca yang pelan tidak melewati rasio. Pembeda tetap YAMNet di server.

Encoder harus yang bisa dibaca saat masih direkam: opus (.ogg). AAC (.m4a) tidak bisa
(metadata moov baru ditulis di akhir). Sudah diuji di HP: ffprobe bisa baca .ogg yang
masih direkam.

StrideExtractor murni numpy (tanpa Termux), jadi bisa diuji di laptop dengan rekaman yang
di-feed bertahap.
"""

import os
import subprocess
import time

import numpy as np

SR = 16000
WIN_S = 3.0               # panjang klip yang dikirim
STRIDE_S = 2.0            # jarak antar klip (WIN_S - STRIDE_S = tumpang-tindih)
MIN_RMS = 0.005           # klip dengan RMS rata-rata di bawah ini = hening, tidak dikirim
ROTATE_S = 60.0           # file rekaman dimulai ulang tiap ~60 detik (decode tidak membengkak)


class StrideExtractor:
    """feed(pcm_penuh_sejauh_ini) -> list klip yang SUDAH lengkap dan tidak hening.

    pcm = seluruh sinyal file rekaman saat ini (float32 mono 16 kHz), bertambah tiap poll.
    """

    def __init__(self):
        self.next_start = 0

    def feed(self, pcm: np.ndarray) -> list:
        win, stride = int(WIN_S * SR), int(STRIDE_S * SR)
        clips = []
        while len(pcm) >= self.next_start + win:
            clip = pcm[self.next_start:self.next_start + win]
            self.next_start += stride
            if float(np.sqrt(np.mean(np.square(clip, dtype=np.float64)))) >= MIN_RMS:
                clips.append(clip.copy())
        return clips


class FileCapture:
    """Satu rekaman opus yang berjalan terus lewat termux-microphone-record."""

    def __init__(self, path: str, device_id: str = "hp"):
        self.path = path
        self.device_id = device_id

    def start(self):
        # "-q" sekali di awal: bersihkan rekaman nyangkut dari run sebelumnya.
        subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
        time.sleep(0.5)
        if os.path.exists(self.path):
            os.remove(self.path)
        for attempt in range(5):
            r = subprocess.run(
                # -l 0 = tanpa batas waktu. -r 16000 WAJIB (default 8 kHz membuang suara > 4 kHz).
                ["termux-microphone-record", "-f", self.path, "-l", "0", "-e", "opus",
                 "-r", "16000", "-b", "48", "-c", "1"],
                capture_output=True, text=True,
            )
            out = (r.stdout + r.stderr).lower()
            if "already in progress" not in out:
                return
            print(f"[{self.device_id}] Masih ada rekaman lama nyangkut, stop dulu... ({attempt + 1}/5)")
            subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
            time.sleep(0.5)
        raise RuntimeError("Gagal mulai rekaman. Coba manual: termux-microphone-record -q")

    def decode(self) -> np.ndarray:
        """Decode seluruh file yang sudah tertulis -> float32 mono 16 kHz.
        Halaman Ogg terakhir bisa belum lengkap: ffmpeg bisa mengeluh, jadi pakai
        stdout apa adanya walau return code bukan 0."""
        if not os.path.exists(self.path):
            return np.zeros(0, dtype=np.float32)
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", self.path, "-af", "pan=mono|c0=c0",
             "-ar", str(SR), "-f", "s16le", "-"],
            capture_output=True,
        )
        raw = r.stdout[: len(r.stdout) // 2 * 2]
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    def stop(self):
        subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
