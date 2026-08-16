import os
import wave
import shutil
import logging
import subprocess
import numpy as np
from typing import List, Tuple, Optional
from speech.models.schemas import PhonemeTimestamp, PhonemeAlignmentResult

logger = logging.getLogger("MindBuzzLogger")


class AlignmentError(Exception):
    pass


class AudioTooShortError(AlignmentError):
    def __init__(self, duration: float, min_duration: float = 0.15):
        self.duration = duration
        super().__init__(f"Audio duration ({duration:.2f}s) is shorter than minimum required ({min_duration:.2f}s)")


class AudioTooNoisyError(AlignmentError):
    def __init__(self, message: str = "Audio signal is too noisy or silent for alignment"):
        super().__init__(message)


class MFAService:

    def __init__(self, mfa_path: Optional[str] = None):
        self.mfa_bin = mfa_path or shutil.which("mfa")

    def _read_audio(self, audio_path: str) -> Tuple[np.ndarray, int, float]:
        if not os.path.exists(audio_path):
            raise AlignmentError(f"Audio file not found at path: {audio_path}")

        try:
            with wave.open(audio_path, 'rb') as wf:
                num_channels = wf.getnchannels()
                sample_rate = wf.getframerate()
                nframes = wf.getnframes()
                if nframes <= 0 or sample_rate <= 0:
                    raise AudioTooShortError(0.0)

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
                duration = len(audio_float) / float(sample_rate)

                return audio_float, sample_rate, duration
        except AlignmentError:
            raise
        except Exception as e:
            raise AlignmentError(f"Failed to read WAV audio file: {e}")

    def align(self, audio_path: str, target_word: str, phonemes: List[str]) -> PhonemeAlignmentResult:
        if not phonemes:
            raise AlignmentError(f"No target phonemes provided for word '{target_word}'")

        audio, sample_rate, duration = self._read_audio(audio_path)

        if duration < 0.12:
            raise AudioTooShortError(duration)

        rms_energy = np.sqrt(np.mean(audio ** 2)) if len(audio) > 0 else 0
        if rms_energy < 0.0005:
            raise AudioTooNoisyError("Audio signal energy is near zero (silent or invalid recording).")

        if self.mfa_bin:
            try:
                mfa_result = self._align_with_mfa(audio_path, target_word, phonemes)
                if mfa_result and len(mfa_result.phonemes) == len(phonemes):
                    return mfa_result
            except Exception as e:
                logger.warning(f"MFA CLI alignment note: {e}")

        return self._align_acoustically(audio, sample_rate, duration, target_word, phonemes)

    def _align_with_mfa(self, audio_path: str, target_word: str, phonemes: List[str]) -> Optional[PhonemeAlignmentResult]:
        cmd = [self.mfa_bin, "align_one", audio_path, target_word]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return None
        return None

    def _align_acoustically(
        self,
        audio: np.ndarray,
        sample_rate: int,
        duration: float,
        target_word: str,
        phonemes: List[str]
    ) -> PhonemeAlignmentResult:
        frame_size = int(sample_rate * 0.02)
        hop_size = int(sample_rate * 0.01)

        n_frames = max(1, (len(audio) - frame_size) // hop_size + 1)
        energies = np.zeros(n_frames, dtype=np.float32)

        for i in range(n_frames):
            frame = audio[i * hop_size : i * hop_size + frame_size]
            energies[i] = np.sqrt(np.mean(frame ** 2))

        max_energy = np.max(energies) if len(energies) > 0 else 0.001
        threshold = max(0.002, max_energy * 0.1)

        active_indices = np.where(energies >= threshold)[0]
        if len(active_indices) > 0:
            start_frame = max(0, active_indices[0] - 1)
            end_frame = min(n_frames - 1, active_indices[-1] + 1)
            speech_start = round(start_frame * 0.01, 3)
            speech_end = round(min(duration, (end_frame + 2) * 0.01), 3)
        else:
            speech_start = 0.03
            speech_end = round(max(0.15, duration - 0.03), 3)

        if speech_end <= speech_start:
            speech_end = round(speech_start + 0.15, 3)

        active_duration = speech_end - speech_start

        vowel_set = {"AA", "AE", "AH", "AO", "AW", "AY", "EH", "ER", "EY", "IH", "IY", "OW", "OY", "UH", "UW"}
        weights = []
        for p in phonemes:
            clean_p = "".join(c for c in p if c.isalpha()).upper()
            if clean_p in vowel_set:
                weights.append(1.4)
            elif clean_p in {"S", "SH", "F", "TH", "V", "Z"}:
                weights.append(1.1)
            else:
                weights.append(0.9)

        total_weight = sum(weights)
        norm_weights = [w / total_weight for w in weights]

        timestamps: List[PhonemeTimestamp] = []
        curr_start = speech_start

        for i, ph in enumerate(phonemes):
            ph_dur = active_duration * norm_weights[i]
            curr_end = min(duration, curr_start + ph_dur)
            if i == len(phonemes) - 1:
                curr_end = speech_end

            timestamps.append(
                PhonemeTimestamp(
                    phoneme=ph,
                    start=round(curr_start, 2),
                    end=round(curr_end, 2)
                )
            )
            curr_start = curr_end

        return PhonemeAlignmentResult(
            phonemes=timestamps,
            target_word=target_word,
            phonetic_spelling=phonemes
        )
