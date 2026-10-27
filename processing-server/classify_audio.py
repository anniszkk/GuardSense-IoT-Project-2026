"""PIC: Annis. Klasifikasi audio (pecahan kaca) + liveness check.
Lihat docx Bab 5.2.1 dan 5.2.1.1.

classify_glass_break (rule-based) sudah diisi. Threshold hasil kalibrasi
awal pakai sampel suara publik (edge-audio/samples/ vs samples1/, lihat
juga catatan di edge-audio/prefilter.py):
- Frekuensi dominan: semua sampel kaca pecah > 3000 Hz (rentang
  3313-11217 Hz), semua sampel non-event (masak, podcast, ngomong,
  pintu dibanting, tawa, TV static, room tone) < 1100 Hz. Pemisahnya
  bersih, jadi frekuensi dipakai sebagai penentu utama di sini -- BUKAN
  RMS (lihat alasannya di edge-audio/prefilter.py).
- Durasi: sampel kaca pecah 1.33-2.78 detik (event singkat/transient).

MASIH perlu divalidasi ulang pakai rekaman HP asli (Bab 9, skenario 1-3)
sebelum dipakai sebagai keputusan final -- sampel di atas dari sumber
publik (freesound dll), bukan rekaman lewat mic HP yang sebenarnya dipakai.
"""

# TODO: validasi ulang pakai rekaman HP asli (Bab 9).
FREQ_THRESHOLD_HZ = 3000.0  # kaca pecah: dominant freq biasanya > 3-4 kHz
MIN_RMS = 0.02  # selaras dengan AMPLITUDE_THRESHOLD di edge-audio/prefilter.py
MAX_DURATION_S = 3.0  # pecahan kaca adalah event singkat (transient)


def classify_glass_break(rms_amplitude: float, dominant_freq_hz: float, duration_s: float) -> dict:
    """Pendekatan A (rule-based) -- Bab 5.2.1.
    Return dict: {"is_glass_break": bool, "confidence": float}
    """
    if rms_amplitude < MIN_RMS:
        # Nyaris hening, bukan event -- sejalan dengan filter di prefilter.py.
        return {"is_glass_break": False, "confidence": 0.0}

    freq_ok = dominant_freq_hz > FREQ_THRESHOLD_HZ
    duration_ok = duration_s <= MAX_DURATION_S

    if not (freq_ok and duration_ok):
        return {"is_glass_break": False, "confidence": 0.0}

    # Confidence naik makin jauh frekuensi di atas ambang, dibatasi ke 1.0.
    margin = (dominant_freq_hz - FREQ_THRESHOLD_HZ) / FREQ_THRESHOLD_HZ
    confidence = min(1.0, 0.5 + margin)
    return {"is_glass_break": True, "confidence": confidence}


# Kelas AudioSet (yamnet_class_map.csv) yang relevan dengan pecahan kaca.
# Index resminya: 435 Glass, 436 "Chink, clink", 437 Shatter,
# 463 "Smash, crash", 464 Breaking -- dicari lewat nama (bukan index
# hardcoded) di _load_yamnet supaya tidak salah kalau urutan file berubah.
GLASS_BREAK_CLASS_NAMES = {"Glass", "Chink, clink", "Shatter", "Smash, crash", "Breaking"}

# TODO: kalibrasi ambang ini pakai klip audio nyata (Bab 9). 0.3 adalah
# nilai awal yang umum dipakai sebagai starting point untuk skor YAMNet.
YAMNET_CONFIDENCE_THRESHOLD = 0.3

_yamnet_model = None
_yamnet_class_names = None


def _load_yamnet():
    """Load model YAMNet dari TF-Hub (sekali saja, di-cache di module-level
    supaya tidak reload tiap kali classify_glass_break_yamnet dipanggil --
    inilah bagian "berat" yang dihindari di tahap prefilter/Bab 5.1).
    """
    global _yamnet_model, _yamnet_class_names
    if _yamnet_model is None:
        import csv
        import tensorflow_hub as hub

        _yamnet_model = hub.load("https://tfhub.dev/google/yamnet/1")
        class_map_path = _yamnet_model.class_map_path().numpy().decode("utf-8")
        _yamnet_class_names = []
        with open(class_map_path) as f:
            reader = csv.reader(f)
            next(reader)  # skip header: index,mid,display_name
            for row in reader:
                _yamnet_class_names.append(row[2])
    return _yamnet_model, _yamnet_class_names


def classify_glass_break_yamnet(audio_clip_path: str) -> dict:
    """Pendekatan B (AI, opsional/upgrade) -- Bab 5.2.1.

    Load klip audio (harus mono, 16000 Hz -- syarat input YAMNet), jalankan
    inference, ambil skor rata-rata untuk kelas-kelas di GLASS_BREAK_CLASS_NAMES,
    dan pakai skor TERTINGGI di antara kelas-kelas itu sebagai confidence.

    Return dict: {"is_glass_break": bool, "confidence": float}
    """
    import numpy as np
    import soundfile as sf

    model, class_names = _load_yamnet()

    waveform, sample_rate = sf.read(audio_clip_path, dtype="float32")
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)  # mix ke mono

    if sample_rate != 16000:
        raise ValueError(
            f"YAMNet butuh sample rate 16000 Hz, file ini {sample_rate} Hz. "
            f"Resample dulu, misal: ffmpeg -i in.wav -ar 16000 -ac 1 out.wav"
        )

    scores, _embeddings, _spectrogram = model(waveform)
    mean_scores = scores.numpy().mean(axis=0)  # rata-rata skor antar-frame

    glass_score = 0.0
    for name in GLASS_BREAK_CLASS_NAMES:
        idx = class_names.index(name)
        glass_score = max(glass_score, float(mean_scores[idx]))

    return {
        "is_glass_break": glass_score > YAMNET_CONFIDENCE_THRESHOLD,
        "confidence": glass_score,
    }


def liveness_check_context(yamnet_scores: dict) -> bool:
    """Bagian A liveness check (Bab 5.2.1.1): True kalau terindikasi suara TV/media
    (skor Television/Speech/Music tinggi bersamaan), False kalau event murni.
    TODO: implementasikan.
    """
    raise NotImplementedError("TODO: implementasikan liveness_check_context")


def liveness_check_amplitude_ratio(rms_hp_a: float, rms_hp_b: float) -> bool:
    """Bagian B liveness check (Bab 5.2.1.1): True kalau rasio amplitudo antar
    dua HP relatif SETARA (indikasi sumber tersebar seperti TV), False kalau
    timpang (indikasi event lokal/asli).
    TODO: implementasikan + tentukan ambang rasio hasil kalibrasi.
    """
    raise NotImplementedError("TODO: implementasikan liveness_check_amplitude_ratio")
