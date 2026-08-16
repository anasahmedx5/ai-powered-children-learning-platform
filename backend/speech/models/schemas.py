from typing import List, Dict, Optional
from pydantic import BaseModel, Field


class WhisperSegment(BaseModel):
    text: str
    start: float
    end: float


class WhisperOutput(BaseModel):
    success: bool
    recognized_text: str
    language: str = "en"
    processing_time_ms: int
    segments: List[WhisperSegment] = Field(default_factory=list)
    error: Optional[str] = None


class PhonemeTimestamp(BaseModel):
    phoneme: str
    start: float
    end: float


class PhonemeAlignmentResult(BaseModel):
    phonemes: List[PhonemeTimestamp] = Field(default_factory=list)
    target_word: str
    phonetic_spelling: List[str] = Field(default_factory=list)


class PhonemeScore(BaseModel):
    phoneme: str
    score: float


class GOPResult(BaseModel):
    overall_score: float
    phoneme_scores: List[PhonemeScore] = Field(default_factory=list)
    weakest_phoneme: Optional[str] = None
    strongest_phoneme: Optional[str] = None


class PronunciationReport(BaseModel):
    letter: str
    target_word: str
    recognized_word: str
    recognized_correctly: bool
    language: str = "en"
    overall_score: float
    phoneme_scores: List[PhonemeScore] = Field(default_factory=list)
    weakest_phoneme: Optional[str] = None
    strongest_phoneme: Optional[str] = None
    weakest_score: Optional[float] = None
    confidence_threshold: float = 50.0
    is_below_threshold: bool = False
    groq_msg: Optional[str] = None
    processing_time_ms: int



class LLMPayload(BaseModel):
    letter: str
    word: str
    overall_score: float
    phoneme_scores: Dict[str, float] = Field(default_factory=dict)
