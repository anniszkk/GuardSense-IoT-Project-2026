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
ROTATE_S = 1800.0         # file rekaman dimulai ulang tiap ~30 menit (cuma supaya file tidak membengkak;
                          # decode tidak bergantung panjang file karena dibaca dari offset, lihat decode())


class StrideExtractor:
    """feed(pcm, seg_start) -> list klip yang SUDAH lengkap dan tidak hening.

    pcm = potongan sinyal (float32 mono 16 kHz) yang DIMULAI di sampel absolut `seg_start`
    dari awal file rekaman -- bukan seluruh file (lihat FileCapture.decode). Pemanggil
    mendecode mulai dari `next_start_s` supaya biaya baca tidak tumbuh bersama file.
    """

    def __init__(self):
        self.next_start = 0   # sampel absolut awal klip berikutnya

    @property
    def next_start_s(self) -> float:
        return self.next_start / SR

    def feed(self, pcm: np.ndarray, seg_start: int = 0) -> list:
        win, stride = int(WIN_S * SR), int(STRIDE_S * SR)
        if self.next_start < seg_start:
            # Potongan dimulai setelah klip berikutnya (data hilang): lompat ke awal potongan.
            self.next_start = seg_start
        clips = []
        while True:
            lo = self.next_start - seg_start
            if lo + win > len(pcm):
                break
            clip = pcm[lo:lo + win]
            self.next_start += stride
            if float(np.sqrt(np.mean(np.square(clip, dtype=np.float64)))) >= MIN_RMS:
                clips.append(clip.copy())
        return clips


class FileCapture:
    """Satu rekaman opus yang berjalan terus lewat termux-microphone-record."""

    def __init__(self, path: str, device_id: str = "hp"):
        self.path = path
        self.device_id = device_id

    def start(self, cleanup: bool = True):
        """cleanup=True: "-q" + jeda dulu (bersihkan rekaman nyangkut dari run sebelumnya).
        cleanup=False dipakai saat rotasi: rekaman lama baru saja di-stop(), langsung start
        supaya celah rotasi pendek (tiap panggilan termux-api ~1 detik)."""
        if cleanup:
            subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
            time.sleep(0.5)
        if os.path.exists(self.path):
            os.remove(self.path)
        for attempt in range(5):
            r = subprocess.run(
                # -l 0 = tanpa batas waktu. -r 16000 WAJIB (default 8 kHz membuang suara > 4 kHz).
                # -b 96: opus 48 kbps diduga meredam transient frekuensi tinggi (kaca) -> skor YAMNet turun.
                ["termux-microphone-record", "-f", self.path, "-l", "0", "-e", "opus",
                 "-r", "16000", "-b", "96", "-c", "1"],
                capture_output=True, text=True,
            )
            out = (r.stdout + r.stderr).lower()
            if "already in progress" not in out:
                return
            print(f"[{self.device_id}] Masih ada rekaman lama nyangkut, stop dulu... ({attempt + 1}/5)")
            subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
            time.sleep(0.5)
        raise RuntimeError("Gagal mulai rekaman. Coba manual: termux-microphone-record -q")

    def decode(self, start_s: float = 0.0) -> np.ndarray:
        """Decode file yang sudah tertulis, MULAI dari detik `start_s` -> float32 mono 16 kHz.

        Dibaca dari offset (ffmpeg -ss sebelum -i = seek akurat), jadi biaya per poll hanya
        beberapa detik audio terakhir berapa pun panjang file -- tidak perlu merotasi file
        tiap menit (rotasi = celah ~9 detik tanpa rekaman).
        Halaman Ogg terakhir bisa belum lengkap: ffmpeg bisa mengeluh, jadi pakai
        stdout apa adanya walau return code bukan 0."""
        if not os.path.exists(self.path):
            return np.zeros(0, dtype=np.float32)
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, start_s):.3f}", "-i", self.path,
             "-af", "pan=mono|c0=c0", "-ar", str(SR), "-f", "s16le", "-"],
            capture_output=True,
        )
        raw = r.stdout[: len(r.stdout) // 2 * 2]
        return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

    def stop(self):
        subprocess.run(["termux-microphone-record", "-q"], capture_output=True)
