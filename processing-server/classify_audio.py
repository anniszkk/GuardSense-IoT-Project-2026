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

# Alarm asap (Bab 5.2.2). "Alarm" dan "Buzzer" SENGAJA tidak dipakai: terlalu umum (jam weker,
# bel microwave, klakson) dan bunyi beep kecil rumah tangga akan ikut memicu.
ALARM_CLASS_NAMES = {"Fire alarm", "Smoke detector, smoke alarm"}
# Berbeda dengan kaca (transient, cukup satu frame), alarm berbunyi terus-menerus, jadi yang dinilai
# adalah skor frame TERTINGGI KEDUA (butuh minimal 2 frame YAMNet di atas ambang): satu "ting" sesaat
# tidak cukup. 0.35: di edge-audio/samples2/ alarm "Fire alarm" skornya 0.4-1.0, sedangkan seluruh
# rekaman kaca dan negatif (samples/, samples1/) tidak pernah di atas 0.03. Dua dari empat sampel
# (bel bergaya musik, nada EAS) memang tidak dikenali YAMNet sebagai alarm. Perlu divalidasi lewat mic HP
# dan dengan bunyi beep rumah tangga (microwave, jam weker, bel pintu) yang belum ada di set uji.
ALARM_CONFIDENCE_THRESHOLD = 0.35

# Alarm rumah tangga (timer dapur, jam weker) juga berbunyi berulang, tapi bukan alarm asap. YAMNet
# mengenalinya sebagai "Alarm clock": di sampel uji skornya 0.96-0.99, sedangkan alarm asap beneran
# 0.00-0.14 (selisih lebar). Kalau skor ini tinggi, pola beep TIDAK dipakai. Telephone bell dan Doorbell
# sengaja tidak dipakai: alarm sekolah dan nada EAS pun menyentuh 0.75 / 0.58 di kelas itu.
RING_DIAG_CLASS_NAMES = ("Ding", "Bell")
HOUSEHOLD_ALARM_CLASS = "Alarm clock"
HOUSEHOLD_ALARM_THRESHOLD = 0.5

# Kepercayaan tetap untuk alarm yang hanya dikenali dari pola beep (tidak ada skor model).
BEEP_ONLY_CONFIDENCE = 0.5

# Jalur kedua untuk alarm: POLA BEEP (Bab 5.2.2: "pola bunyi berulang dengan frekuensi konstan").
# Alarm dari merek/model berbeda nadanya beda (1-6 kHz) tapi polanya sama: beep 0.3-1.2 detik berisi
# satu nada murni, berulang dengan nada dan durasi yang sama. YAMNet menilai "jenis suara", jadi sebagian
# alarm (bel bergaya musik, nada EAS) lolos darinya; pola ini tidak peduli nadanya.
BEEP_FRAME_S = 0.02
BEEP_ON_FRACTION = 0.25     # beep = envelope di atas 25% puncak klip
BEEP_MIN_S, BEEP_MAX_S = 0.3, 1.2
BEEP_EDGE_MIN_S = 0.15     # potongan beep di tepi klip
BEEP_MIN_HZ = 800.0         # nada beep alarm/timer 1-6 kHz; suara bicara/dengung (< 800 Hz) bukan beep
BEEP_TONAL_MIN = 0.2        # >= 20% energi (di atas 300 Hz) di sekitar satu puncak; alarm EAS kaya harmonik (0.27)
BEEP_FREQ_TOL = 0.05        # dua beep dianggap "nada sama" bila selisih <= 5%
BEEP_DUR_TOL = 0.3          # dan durasi selisih <= 30%

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
    Skor alarm = skor frame tertinggi KEDUA dari kelas ALARM_CLASS_NAMES (bunyi harus bertahan
    minimal 2 frame; kalau klip cuma 1 frame, dipakai yang tertinggi).
    alarm_clock_score = skor frame tertinggi kelas "Alarm clock" (jam weker/timer dapur), dipakai untuk
    membatalkan pola beep.
    Return {"glass_score": float, "alarm_score": float, "alarm_clock_score": float, "media_scores": {nama: float}}.
    """
    model, class_names = _load_yamnet()
    scores, _embeddings, _spectrogram = model(waveform)
    scores = scores.numpy()  # (frames, 521)

    glass_score = max(float(scores[:, class_names.index(n)].max()) for n in GLASS_BREAK_CLASS_NAMES)
    media_scores = {n: float(scores[:, class_names.index(n)].mean()) for n in MEDIA_CLASS_NAMES}
    alarm_cols = [class_names.index(n) for n in ALARM_CLASS_NAMES]
    alarm_frames = sorted(scores[:, alarm_cols].max(axis=1), reverse=True)
    alarm_score = float(alarm_frames[1] if len(alarm_frames) >= 2 else alarm_frames[0])
    alarm_clock_score = float(scores[:, class_names.index(HOUSEHOLD_ALARM_CLASS)].max())
    # Hanya diagnostik (tidak dipakai keputusan): bunyi denting/lonceng sering terbaca kaca (Chink, clink).
    ring_scores = {n: float(scores[:, class_names.index(n)].max()) for n in RING_DIAG_CLASS_NAMES}
    return {"glass_score": glass_score, "alarm_score": alarm_score, "alarm_clock_score": alarm_clock_score,
            "ring_scores": ring_scores, "media_scores": media_scores}


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


def detect_beep_train(waveform, sample_rate: int = 16000) -> dict:
    """Deteksi rangkaian beep berulang dengan nada stabil (alarm asap; beep timer dan bel elektronik juga ikut).

    Segmen "nyala" dari envelope RMS 20 ms; segmen yang menyentuh tepi klip dianggap terpotong (hanya bukti pendukung).
    Tiap segmen diperiksa nadanya (FFT); beep yang nadanya (dan durasinya) sama dikelompokkan.
    Terdeteksi bila ada 2 beep lengkap bernada sama, atau 3 beep bernada sama termasuk potongan di tepi klip.
    Return {"is_beep_train": bool, "n_beeps": int, "freq_hz": float|None}.
    """
    import numpy as np

    x = np.asarray(waveform, dtype=np.float64)
    h = int(BEEP_FRAME_S * sample_rate)
    n = len(x) // h
    if n < 10:
        return {"is_beep_train": False, "n_beeps": 0, "freq_hz": None}
    env = np.sqrt((x[: n * h].reshape(n, h) ** 2).mean(axis=1))
    if env.max() <= 0:
        return {"is_beep_train": False, "n_beeps": 0, "freq_hz": None}
    on = env > BEEP_ON_FRACTION * env.max()

    beeps = []  # (freq, durasi, terpotong_tepi)
    i = 0
    while i < n:
        if not on[i]:
            i += 1
            continue
        j = i
        while j < n and on[j]:
            j += 1
        dur = (j - i) * BEEP_FRAME_S
        edge = i == 0 or j == n
        # Beep lengkap: BEEP_MIN_S..BEEP_MAX_S. Potongan di tepi klip: cukup >= BEEP_EDGE_MIN_S, hanya
        # jadi bukti pendukung (nada sama dengan beep lengkap). Nada terus-menerus (siren, dengung)
        # bukan rangkaian beep, jadi segmen yang lebih panjang dari BEEP_MAX_S dibuang.
        if dur <= BEEP_MAX_S and dur >= (BEEP_EDGE_MIN_S if edge else BEEP_MIN_S):
            seg = x[i * h:j * h]
            power = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
            freqs = np.fft.rfftfreq(len(seg), 1.0 / sample_rate)
            m = freqs > 300.0
            if power[m].sum() > 0:
                f_pk = freqs[m][power[m].argmax()]
                near = m & (np.abs(freqs - f_pk) <= 0.04 * f_pk)
                if f_pk >= BEEP_MIN_HZ and power[near].sum() / power[m].sum() >= BEEP_TONAL_MIN:
                    beeps.append((float(f_pk), dur, edge))
        i = j

    full = [b for b in beeps if not b[2]]
    cut = [b for b in beeps if b[2]]
    best, best_f = 0, None
    for a in full:
        same_full = [b for b in full if b is not a
                     and abs(b[0] - a[0]) <= BEEP_FREQ_TOL * a[0] and abs(b[1] - a[1]) <= BEEP_DUR_TOL * a[1]]
        same_edge = [b for b in cut if abs(b[0] - a[0]) <= BEEP_FREQ_TOL * a[0]]
        total = 1 + len(same_full) + len(same_edge)
        # Dua beep lengkap bernada sama, atau tiga beep (termasuk potongan di tepi klip).
        if (1 + len(same_full) >= 2 or total >= 3) and total > best:
            best, best_f = total, a[0]
    return {"is_beep_train": best >= 2, "n_beeps": best, "freq_hz": best_f}


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
            "is_media": bool, "is_alarm": bool, "alarm_confidence": float,
            "alarm_source": "yamnet"|"beep_pattern"|None, "fallback_reason": str|None}.
    is_media = terindikasi suara TV/media (liveness bagian A); hanya terisi dari YAMNet.
    is_alarm = bunyi alarm asap: YAMNet (kelas Fire alarm); kalau YAMNet tidak yakin, baru pola beep berulang (detect_beep_train).
    Pola beep tidak butuh TensorFlow, jadi tetap jalan di jalur cadangan. Alarm yang hanya dikenali dari
    pola beep (alarm_source == "beep_pattern") kurang pasti: beep timer/microwave berpola sama.
    """
    clip_b64 = payload.get("clip_b64")
    no_alarm = {"is_alarm": False, "alarm_confidence": 0.0, "alarm_source": None}
    if not clip_b64:
        # Payload lama tanpa klip: pakai rule-based lama dari fitur yang dikirim edge.
        r = classify_glass_break(payload["rms_amplitude"], payload["dominant_freq_hz"], payload["duration_s"])
        return {**r, **no_alarm, "method": "rule_legacy", "is_media": False,
                "fallback_reason": "tidak ada klip di payload"}

    try:
        waveform = decode_clip(clip_b64)
    except Exception as e:
        # Klip rusak: tidak ada yang bisa dianalisis lagi dari audio.
        return {"is_glass_break": False, "confidence": 0.0, **no_alarm, "method": "none", "is_media": False,
                "fallback_reason": f"klip tidak valid: {type(e).__name__}: {e}"}

    try:
        y = analyze_yamnet(waveform)
    except Exception as e:  # TensorFlow belum terpasang, model gagal di-load, dll.
        r = classify_glass_break_hf(waveform)
        beep = detect_beep_train(waveform)
        alarm = {"is_alarm": beep["is_beep_train"], "alarm_confidence": BEEP_ONLY_CONFIDENCE if beep["is_beep_train"] else 0.0,
                 "alarm_source": "beep_pattern" if beep["is_beep_train"] else None}
        return {**r, **alarm, "method": "rule_hf", "is_media": False,
                "fallback_reason": f"YAMNet tidak tersedia: {type(e).__name__}: {e}"}

    # Alarm: YAMNet dulu. Pola beep hanya diperiksa kalau YAMNet TIDAK yakin DAN bukan jam weker/timer.
    if y["alarm_score"] > ALARM_CONFIDENCE_THRESHOLD:
        is_alarm, alarm_conf, alarm_source = True, y["alarm_score"], "yamnet"
    elif y["alarm_clock_score"] <= HOUSEHOLD_ALARM_THRESHOLD and detect_beep_train(waveform)["is_beep_train"]:
        is_alarm, alarm_conf, alarm_source = True, BEEP_ONLY_CONFIDENCE, "beep_pattern"
    else:
        is_alarm, alarm_conf, alarm_source = False, y["alarm_score"], None
    return {
        "is_glass_break": y["glass_score"] > YAMNET_CONFIDENCE_THRESHOLD,
        "confidence": y["glass_score"],
        "is_alarm": is_alarm,
        "alarm_confidence": alarm_conf,
        "alarm_source": alarm_source,
        "alarm_clock_score": y["alarm_clock_score"],
        "ring_scores": y["ring_scores"],
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


# Bagian B liveness (Bab 5.2.1.1): rasio RMS antar dua HP. TV menyebar rata ke ruangan, jadi RMS
# di kedua HP hampir sama; kaca pecah itu sumber titik, jadi HP yang dekat jauh lebih keras.
# BELUM DIKALIBRASI dengan dua HP sungguhan -- 1.5 hanya tebakan awal (override: env LIVENESS_RATIO).
# Kalau salah, kegagalannya aman: kaca asli hanya diberi label "perlu verifikasi", tidak dibuang.
import os as _os

AMPLITUDE_RATIO_EQUAL_MAX = float(_os.getenv("LIVENESS_RATIO", "1.5"))
RATIO_RMS_FLOOR = 0.005  # sama dengan gerbang RMS edge; mencegah pembagian dengan nilai ~0


def amplitude_ratio(rms_a: float, rms_b: float) -> float:
    """Rasio >= 1: RMS yang lebih besar dibagi yang lebih kecil (keduanya diberi lantai RATIO_RMS_FLOOR)."""
    hi = max(rms_a, rms_b, RATIO_RMS_FLOOR)
    lo = max(min(rms_a, rms_b), RATIO_RMS_FLOOR)
    return hi / lo


def liveness_check_amplitude_ratio(rms_hp_a: float, rms_hp_b: float) -> bool:
    """Bagian B liveness check (Bab 5.2.1.1): True kalau rasio amplitudo antar dua HP
    relatif SETARA (indikasi sumber tersebar seperti TV), False kalau timpang
    (indikasi event lokal/asli)."""
    return amplitude_ratio(rms_hp_a, rms_hp_b) < AMPLITUDE_RATIO_EQUAL_MAX
