"""PIC: Annis. Klasifikasi audio (pecahan kaca) + liveness check.
Lihat docx Bab 5.2.1 dan 5.2.1.1.

Jalur utama: YAMNet (classify_audio_clip -> analyze_yamnet). Fallback kalau
YAMNet tidak tersedia/gagal: rule-based rasio energi band tinggi
(classify_glass_break_hf). classify_glass_break (frekuensi dominan) tetap ada
hanya untuk payload lama tanpa klip.

Threshold rule-based awal dikalibrasi pakai sampel suara publik
(edge-audio/samples/ vs samples1/, lihat juga edge-audio/prefilter.py):
- Frekuensi dominan: semua sampel kaca pecah > 3000 Hz (rentang
  3313-11217 Hz), semua sampel non-event < 1100 Hz. TAPI itu pada klip yang
  sudah dipotong; pada rekaman HP (window 2 detik, ada bising rendah) hasilnya
  ~100 Hz, makanya jalur fallback memakai rasio energi band tinggi.
- Durasi: sampel kaca pecah 1.33-2.78 detik (event singkat/transient).

MASIH perlu divalidasi ulang pakai rekaman HP asli (Bab 9, skenario 1-3)
sebelum dipakai sebagai keputusan final -- sampel di atas dari sumber
publik (freesound dll), bukan rekaman lewat mic HP yang sebenarnya dipakai.
"""

# TODO: validasi ulang pakai rekaman HP asli (Bab 9).
FREQ_THRESHOLD_HZ = 3000.0  # kaca pecah: dominant freq biasanya > 3-4 kHz
MIN_RMS = 0.005  # selaras dengan AMPLITUDE_THRESHOLD di edge-audio/prefilter.py
MAX_DURATION_S = 3.0  # pecahan kaca adalah event singkat (transient)


def classify_glass_break(rms_amplitude: float, dominant_freq_hz: float, duration_s: float) -> dict:
    """Pendekatan A (rule-based, versi lama) -- Bab 5.2.1. Hanya untuk payload
    tanpa klip; tidak andal untuk window rekaman HP (lihat docstring modul).
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


# Kelas AudioSet (yamnet_class_map.csv) yang relevan dengan pecahan kaca,
# dicari lewat nama (bukan index hardcoded) supaya tidak salah kalau urutan
# file berubah. "Breaking" dan "Smash, crash" SENGAJA tidak dipakai: di sampel
# uji, "Breaking" menyala 0.60 untuk pintu kayu dibanting (false positive),
# dan "Smash, crash" selalu rendah (<=0.12) untuk kaca. Glass/Shatter/Chink
# memisahkan lebih bersih (kaca >=0.69, pintu dibanting <=0.39).
GLASS_BREAK_CLASS_NAMES = {"Glass", "Chink, clink", "Shatter"}

# Kelas konteks untuk liveness check bagian A (Bab 5.2.1.1).
MEDIA_CLASS_NAMES = {"Television", "Speech", "Music"}

# TODO: validasi dengan kaca sungguhan (bukan sampel lewat speaker) -- Bab 9.
# 0.35: dari rekaman mic HP (16 kHz), klip non-kaca <= 0.23 (uji live) / <= 0.18 (negatif1-9),
# sedangkan klip kaca jatuh di 0.37-0.97 tergantung posisi di dalam klip (kaca4: 0.82 vs 0.45).
# Dulu 0.5, tapi banyak klip kaca nyaris lolos di 0.37-0.49.
YAMNET_CONFIDENCE_THRESHOLD = 0.35
# Skor konteks TV/Speech/Music (rata-rata sepanjang klip) di atas ini -> dianggap media.
MEDIA_CONTEXT_THRESHOLD = 0.3

# Fallback rule-based (dipakai kalau YAMNet tidak tersedia / gagal).
HF_RATIO_THRESHOLD = 0.5  # hasil simulasi awal di sampel publik, perlu kalibrasi rekaman HP

_yamnet_model = None
_yamnet_class_names = None


def _load_yamnet():
    """Load model YAMNet dari TF-Hub (sekali saja, di-cache di module-level
    supaya tidak reload tiap kali dipanggil)."""
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


def analyze_yamnet(waveform) -> dict:
    """Jalankan YAMNet SEKALI pada waveform mono float32 16 kHz.

    Skor kaca = max antar-frame (event transient cuma menempati 1-2 frame,
    rata-rata akan meredamnya), diambil dari kelas-kelas GLASS_BREAK_CLASS_NAMES.
    Skor konteks media = rata-rata antar-frame (TV/dialog/musik berlangsung terus).
    Return {"glass_score": float, "media_scores": {nama: float}}.
    """
    model, class_names = _load_yamnet()
    scores, _embeddings, _spectrogram = model(waveform)
    scores = scores.numpy()  # (frames, 521)

    glass_score = max(float(scores[:, class_names.index(n)].max()) for n in GLASS_BREAK_CLASS_NAMES)
    media_scores = {n: float(scores[:, class_names.index(n)].mean()) for n in MEDIA_CLASS_NAMES}
    return {"glass_score": glass_score, "media_scores": media_scores}


def classify_glass_break_yamnet(audio_clip_path: str) -> dict:
    """Pendekatan B (AI) dari file WAV (mono 16 kHz) -- dipakai test_yamnet_batch.py.
    Return dict: {"is_glass_break": bool, "confidence": float}
    """
    import soundfile as sf

    waveform, sample_rate = sf.read(audio_clip_path, dtype="float32")
    if waveform.ndim > 1:
        waveform = waveform.mean(axis=1)
    if sample_rate != 16000:
        raise ValueError(
            f"YAMNet butuh sample rate 16000 Hz, file ini {sample_rate} Hz. "
            f"Resample dulu, misal: ffmpeg -i in.wav -ar 16000 -ac 1 out.wav"
        )
    glass_score = analyze_yamnet(waveform)["glass_score"]
    return {"is_glass_break": glass_score > YAMNET_CONFIDENCE_THRESHOLD, "confidence": glass_score}


def decode_clip(clip_b64: str, expected_rate: int = 16000):
    """Decode klip WAV base64 dari payload edge -> waveform mono float32.
    Raise ValueError kalau formatnya bukan 16-bit mono 16 kHz."""
    import base64
    import io
    import wave

    import numpy as np

    with wave.open(io.BytesIO(base64.b64decode(clip_b64)), "rb") as wf:
        if wf.getsampwidth() != 2 or wf.getnchannels() != 1 or wf.getframerate() != expected_rate:
            raise ValueError(
                f"klip harus 16-bit mono {expected_rate} Hz, dapat "
                f"{wf.getsampwidth() * 8}-bit/{wf.getnchannels()}ch/{wf.getframerate()}Hz"
            )
        raw = wf.readframes(wf.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def classify_glass_break_hf(waveform, sample_rate: int = 16000) -> dict:
    """Fallback rule-based dari klip: gerbang RMS + rasio energi band tinggi."""
    import numpy as np

    from shared.audio_features import high_band_ratio

    rms = float(np.sqrt(np.mean(np.square(waveform, dtype=np.float64)))) if waveform.size else 0.0
    ratio = high_band_ratio(waveform, sample_rate)
    is_glass = rms >= MIN_RMS and ratio >= HF_RATIO_THRESHOLD
    return {"is_glass_break": is_glass, "confidence": ratio if is_glass else 0.0}


def classify_audio_clip(payload: dict) -> dict:
    """Entry point untuk server: YAMNet utama, rule-based sebagai fallback.

    Return {"is_glass_break", "confidence", "method": "yamnet"|"rule_hf"|"rule_legacy"|"none",
            "is_media": bool, "fallback_reason": str|None}.
    is_media = terindikasi suara TV/media (liveness bagian A); hanya terisi dari YAMNet.
    """
    clip_b64 = payload.get("clip_b64")
    if not clip_b64:
        # Payload lama tanpa klip: pakai rule-based lama dari fitur yang dikirim edge.
        r = classify_glass_break(payload["rms_amplitude"], payload["dominant_freq_hz"], payload["duration_s"])
        return {**r, "method": "rule_legacy", "is_media": False, "fallback_reason": "tidak ada klip di payload"}

    try:
        waveform = decode_clip(clip_b64)
    except Exception as e:
        # Klip rusak: tidak ada yang bisa dianalisis lagi dari audio.
        return {"is_glass_break": False, "confidence": 0.0, "method": "none", "is_media": False,
                "fallback_reason": f"klip tidak valid: {type(e).__name__}: {e}"}

    try:
        y = analyze_yamnet(waveform)
    except Exception as e:  # TensorFlow belum terpasang, model gagal di-load, dll.
        r = classify_glass_break_hf(waveform)
        return {**r, "method": "rule_hf", "is_media": False,
                "fallback_reason": f"YAMNet tidak tersedia: {type(e).__name__}: {e}"}

    return {
        "is_glass_break": y["glass_score"] > YAMNET_CONFIDENCE_THRESHOLD,
        "confidence": y["glass_score"],
        "method": "yamnet",
        "is_media": liveness_check_context(y["media_scores"]),
        "fallback_reason": None,
    }


def liveness_check_context(media_scores: dict) -> bool:
    """Bagian A liveness check (Bab 5.2.1.1): True kalau terindikasi suara TV/media
    (skor Television/Speech/Music tinggi), False kalau event murni.
    media_scores = {"Television": x, "Speech": y, "Music": z} dari analyze_yamnet.
    """
    return any(score > MEDIA_CONTEXT_THRESHOLD for score in media_scores.values())


def liveness_check_amplitude_ratio(rms_hp_a: float, rms_hp_b: float) -> bool:
    """Bagian B liveness check (Bab 5.2.1.1): True kalau rasio amplitudo antar
    dua HP relatif SETARA (indikasi sumber tersebar seperti TV), False kalau
    timpang (indikasi event lokal/asli).
    TODO: implementasikan + tentukan ambang rasio hasil kalibrasi (butuh 2 HP).
    """
    raise NotImplementedError("TODO: implementasikan liveness_check_amplitude_ratio")
