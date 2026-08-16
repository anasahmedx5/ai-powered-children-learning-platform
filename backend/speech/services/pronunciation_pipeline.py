import os
import re
import time
import difflib
import logging
from typing import Dict, Any, Tuple
from whisper_service import transcribe_audio_structured
from speech.models.schemas import (
    PronunciationReport,
    LLMPayload,
    PhonemeScore
)
from speech.alignment.dictionary import PronunciationDictionary, WordNotFoundError
from speech.alignment.mfa_service import (
    MFAService,
    AlignmentError,
    AudioTooShortError,
    AudioTooNoisyError
)
from speech.gop.gop_service import GOPService

logger = logging.getLogger("MindBuzzLogger")


class MissingExpectedWordError(Exception):
    def __init__(self):
        super().__init__("Expected target word is missing or empty")


class PronunciationPipeline:

    def __init__(
        self,
        dictionary: PronunciationDictionary = None,
        aligner: MFAService = None,
        gop_service: GOPService = None
    ):
        self.dictionary = dictionary or PronunciationDictionary()
        self.aligner = aligner or MFAService()
        self.gop_service = gop_service or GOPService()

    def _clean_text(self, text: str) -> str:
        return re.sub(r'[^\w\s]', '', text or '').lower().strip()

    def _is_match(self, recognized: str, target: str) -> Tuple[bool, float]:
        clean_rec = self._clean_text(recognized)
        clean_tgt = self._clean_text(target)

        if not clean_rec or not clean_tgt:
            return False, 0.0

        if clean_rec == clean_tgt:
            return True, 1.0

        pattern = r'\b' + re.escape(clean_tgt) + r'\b'
        if re.search(pattern, clean_rec):
            return True, 1.0

        words = clean_rec.split()
        if clean_tgt in words:
            return True, 1.0

        max_ratio = 0.0
        for w in words:
            ratio = difflib.SequenceMatcher(None, w, clean_tgt).ratio()
            if ratio > max_ratio:
                max_ratio = ratio
            if ratio >= 0.95 and len(w) == len(clean_tgt) and w[0] == clean_tgt[0] and w[-1] == clean_tgt[-1]:
                return True, max_ratio

        return False, max_ratio

    def assess_pronunciation(
        self,
        audio_path: str,
        expected_letter: str,
        expected_word: str
    ) -> PronunciationReport:
        start_time = time.time()

        if not expected_word or not expected_word.strip():
            raise MissingExpectedWordError()

        if not audio_path or not os.path.exists(audio_path):
            raise AudioTooShortError(0.0)

        clean_target_word = expected_word.strip().capitalize()
        clean_letter = (expected_letter or clean_target_word[0]).strip().upper()

        whisper_output = transcribe_audio_structured(audio_path)
        if not whisper_output.success:
            logger.error(f"Whisper transcription failed: {whisper_output.error}")

        recognized_text = whisper_output.recognized_text or ""
        recognized_correctly, similarity_ratio = self._is_match(recognized_text, clean_target_word)

        phonemes = self.dictionary.get_phonemes(clean_target_word)

        alignment = self.aligner.align(
            audio_path=audio_path,
            target_word=clean_target_word,
            phonemes=phonemes
        )

        gop_result = self.gop_service.compute_gop(
            audio_path=audio_path,
            alignment=alignment,
            recognized_correctly=recognized_correctly,
            similarity_ratio=similarity_ratio
        )

        self._print_pipeline_boxes(clean_target_word, recognized_text, recognized_correctly, similarity_ratio, alignment, gop_result)

        total_processing_time_ms = int((time.time() - start_time) * 1000)

        weakest_score = None
        if gop_result.weakest_phoneme and gop_result.phoneme_scores:
            for ps in gop_result.phoneme_scores:
                if ps.phoneme == gop_result.weakest_phoneme:
                    weakest_score = ps.score
                    break
        if weakest_score is None and gop_result.phoneme_scores:
            weakest_score = min(ps.score for ps in gop_result.phoneme_scores)
        if weakest_score is None:
            weakest_score = gop_result.overall_score

        confidence_threshold = 50.0
        is_below_threshold = (weakest_score < confidence_threshold)

        report = PronunciationReport(
            letter=clean_letter,
            target_word=clean_target_word,
            recognized_word=recognized_text if recognized_text else "(unintelligible)",
            recognized_correctly=recognized_correctly,
            language=whisper_output.language or "en",
            overall_score=gop_result.overall_score,
            phoneme_scores=gop_result.phoneme_scores,
            weakest_phoneme=gop_result.weakest_phoneme,
            strongest_phoneme=gop_result.strongest_phoneme,
            weakest_score=weakest_score,
            confidence_threshold=confidence_threshold,
            is_below_threshold=is_below_threshold,
            processing_time_ms=total_processing_time_ms
        )

        return report

    def _print_pipeline_boxes(self, target_word, recognized_text, recognized_correctly, similarity_ratio, alignment, gop_result):
        import sys
        width = 58
        border_top = "┌" + "─" * width + "┐"
        border_mid = "├" + "─" * width + "┤"
        border_bot = "└" + "─" * width + "┘"

        def print_box(title, items):
            sys.stdout.write("\n" + border_top + "\n")
            sys.stdout.write(f"│ {title:<{width-2}} │\n")
            sys.stdout.write(border_mid + "\n")
            for line in items:
                clean_l = str(line)[:width-2]
                sys.stdout.write(f"│ {clean_l:<{width-2}} │\n")
            sys.stdout.write(border_bot + "\n\n")
            sys.stdout.flush()

        match_str = f"✅ MATCH PASSED ({round(similarity_ratio * 100, 1)}%)" if recognized_correctly else f"❌ MATCH FAILED ({round(similarity_ratio * 100, 1)}%)"
        print_box("🎙️ MODEL: Whisper Speech Recognition", [
            f"Target Word    : {target_word.upper()}",
            f"Heard Text     : '{recognized_text}'",
            f"Speech Match   : {match_str}"
        ])

        phoneme_seq = " -> ".join([p.phoneme for p in alignment.phonemes])
        print_box("🔍 MODEL: MFA Aligner & GOP Pronunciation Assessment", [
            f"Target Word    : {target_word.upper()}",
            f"Phonemes       : {phoneme_seq}",
            f"Overall GOP    : {gop_result.overall_score} / 100",
            f"Strongest      : {gop_result.strongest_phoneme or 'N/A'}",
            f"Weakest        : {gop_result.weakest_phoneme or 'N/A'}"
        ])

    def prepare_llm_payload(self, report: PronunciationReport) -> LLMPayload:
        scores_dict: Dict[str, float] = {
            ps.phoneme: ps.score for ps in report.phoneme_scores
        }

        return LLMPayload(
            letter=report.letter,
            word=report.target_word,
            overall_score=report.overall_score,
            phoneme_scores=scores_dict
        )
