import numpy as np
import logging

logger = logging.getLogger("MindBuzzLogger")

FRICATIVES = {"S", "SH", "F", "TH", "V", "Z", "ZH", "HH"}
VOWELS = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}
NASALS_PLOSIVES = {"B", "D", "G", "K", "P", "T", "M", "N", "NG", "JH", "CH"}


def compute_phoneme_gop_score(
    audio: np.ndarray,
    sample_rate: int,
    start: float,
    end: float,
    phoneme: str,
    recognized_correctly: bool,
    similarity_ratio: float = 1.0
) -> float:
    clean_ph = "".join(c for c in phoneme if c.isalpha()).upper()
    start_idx = max(0, int(start * sample_rate))
    end_idx = min(len(audio), int(end * sample_rate))

    if end_idx <= start_idx or len(audio) == 0:
        return 50.0

    segment = audio[start_idx:end_idx]
    if len(segment) < 10:
        return 50.0

    rms = np.sqrt(np.mean(segment ** 2))
    frame_len = max(10, int(sample_rate * 0.01))
    n_subframes = max(1, len(segment) // frame_len)
    sub_energies = [
        np.sqrt(np.mean(segment[i * frame_len : (i + 1) * frame_len] ** 2))
        for i in range(n_subframes)
    ]
    mean_e = np.mean(sub_energies) if sub_energies else 1e-4
    std_e = np.std(sub_energies) if sub_energies else 0.0
    stability = 1.0 - min(1.0, std_e / (mean_e + 1e-4))

    zero_crossings = np.diff(np.signbit(segment))
    zcr = np.mean(zero_crossings) if len(zero_crossings) > 0 else 0.0

    category_match_score = 0.85
    if clean_ph in FRICATIVES:
        if zcr > 0.15:
            category_match_score = min(1.0, 0.80 + zcr)
        else:
            category_match_score = max(0.40, zcr * 4.0)
    elif clean_ph in VOWELS:
        if zcr < 0.25 and rms > 0.01:
            category_match_score = min(1.0, 0.85 + stability * 0.15)
        else:
            category_match_score = max(0.50, 1.0 - zcr)
    else:
        category_match_score = min(1.0, 0.75 + stability * 0.25)

    recognition_factor = 0.95 if recognized_correctly else max(0.35, similarity_ratio)

    raw_gop = (0.50 * category_match_score + 0.30 * stability + 0.20 * min(1.0, rms * 20)) * recognition_factor
    final_score = min(100.0, max(0.0, raw_gop * 100.0))

    return float(round(final_score, 1))
