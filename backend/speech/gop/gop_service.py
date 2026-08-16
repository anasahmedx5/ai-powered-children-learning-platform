import os
import wave
import logging
import numpy as np
from typing import List, Tuple
from speech.models.schemas import PhonemeScore, GOPResult, PhonemeAlignmentResult
from speech.gop.scoring import compute_phoneme_gop_score

logger = logging.getLogger("MindBuzzLogger")


class GOPService:

    def _read_audio(self, audio_path: str) -> Tuple[np.ndarray, int]:
        if not os.path.exists(audio_path):
            return np.array([], dtype=np.float32), 16000

        try:
            with wave.open(audio_path, 'rb') as wf:
                num_channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                nframes = wf.getnframes()
                raw_bytes = wf.readframes(nframes)

                sampwidth = wf.getsampwidth()
                if sampwidth == 2:
                    audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                elif sampwidth == 4:
                    audio_int16 = (np.frombuffer(raw_bytes, dtype=np.int32) >> 16).astype(np.int16)
                else:
                    audio_int16 = np.frombuffer(raw_bytes, dtype=np.uint8).astype(np.int16) - 128

                if num_channels > 1:
                    audio_int16 = audio_int16[::num_channels]

                audio_float = audio_int16.astype(np.float32) / 32768.0
                return audio_float, sample_rate
        except Exception as e:
            logger.error(f"Error loading audio for GOP calculation: {e}")
            return np.array([], dtype=np.float32), 16000

    def compute_gop(
        self,
        audio_path: str,
        alignment: PhonemeAlignmentResult,
        recognized_correctly: bool,
        similarity_ratio: float = 1.0
    ) -> GOPResult:
        audio, sample_rate = self._read_audio(audio_path)
        phoneme_scores: List[PhonemeScore] = []

        for item in alignment.phonemes:
            score = compute_phoneme_gop_score(
                audio=audio,
                sample_rate=sample_rate,
                start=item.start,
                end=item.end,
                phoneme=item.phoneme,
                recognized_correctly=recognized_correctly,
                similarity_ratio=similarity_ratio
            )
            phoneme_scores.append(PhonemeScore(phoneme=item.phoneme, score=round(score)))

        if not phoneme_scores:
            return GOPResult(
                overall_score=0,
                phoneme_scores=[],
                weakest_phoneme=None,
                strongest_phoneme=None
            )

        scores_list = [ps.score for ps in phoneme_scores]
        overall_score = round(float(np.mean(scores_list)))

        sorted_scores = sorted(phoneme_scores, key=lambda x: x.score)
        weakest = sorted_scores[0].phoneme if sorted_scores else None
        strongest = sorted_scores[-1].phoneme if sorted_scores else None

        return GOPResult(
            overall_score=overall_score,
            phoneme_scores=phoneme_scores,
            weakest_phoneme=weakest,
            strongest_phoneme=strongest
        )
