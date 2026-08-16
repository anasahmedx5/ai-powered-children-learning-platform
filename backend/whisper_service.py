import whisper
import os
import wave
import numpy as np
import threading

model = None
is_loading = False
_lock = threading.Lock()

def _load_model_internal():
    global model, is_loading
    with _lock:
        if model is None:
            is_loading = True
            try:
                model = whisper.load_model("medium")
            except Exception as e:
                print(f"Error loading Whisper model: {e}")
            finally:
                is_loading = False

def get_model():
    if model is None:
        _load_model_internal()
    return model

def is_whisper_ready():
    return model is not None

def preload_whisper():
    t = threading.Thread(target=_load_model_internal, daemon=True)
    t.start()

preload_whisper()

def load_wav_pcm(file_path):
    try:
        with wave.open(file_path, 'rb') as wf:
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
                return None, None

            if num_channels > 1:
                audio_int16 = audio_int16[::num_channels]
                
            audio_float32 = audio_int16.astype(np.float32) / 32768.0
            return audio_float32, sample_rate
    except Exception as e:
        return None, None

def transcribe_audio(file_path):
    if not os.path.exists(file_path):
        return ""
    
    current_model = get_model()
    if current_model is None:
        return ""
    
    pcm_data, sr = load_wav_pcm(file_path)
    if pcm_data is not None and len(pcm_data) > 0:
        try:
            result = current_model.transcribe(pcm_data, language="en", fp16=False)
            return result.get("text", "").strip()
        except Exception:
            pass

    try:
        result = current_model.transcribe(file_path, language="en", fp16=False)
        return result.get("text", "").strip()
    except Exception:
        return ""


def transcribe_audio_structured(file_path):
    import time
    from speech.models.schemas import WhisperOutput, WhisperSegment

    start_time = time.time()
    if not os.path.exists(file_path):
        return WhisperOutput(
            success=False,
            recognized_text="",
            language="en",
            processing_time_ms=0,
            segments=[],
            error=f"File not found: {file_path}"
        )

    current_model = get_model()
    if current_model is None:
        return WhisperOutput(
            success=False,
            recognized_text="",
            language="en",
            processing_time_ms=0,
            segments=[],
            error="Whisper model not initialized"
        )

    raw_result = None
    pcm_data, sr = load_wav_pcm(file_path)
    if pcm_data is not None and len(pcm_data) > 0:
        try:
            raw_result = current_model.transcribe(pcm_data, language="en", fp16=False)
        except Exception:
            pass

    if raw_result is None:
        try:
            raw_result = current_model.transcribe(file_path, language="en", fp16=False)
        except Exception as e:
            elapsed_ms = int((time.time() - start_time) * 1000)
            return WhisperOutput(
                success=False,
                recognized_text="",
                language="en",
                processing_time_ms=elapsed_ms,
                segments=[],
                error=str(e)
            )

    elapsed_ms = int((time.time() - start_time) * 1000)
    text = raw_result.get("text", "").strip() if raw_result else ""
    lang = raw_result.get("language", "en") if raw_result else "en"

    raw_segments = raw_result.get("segments", []) if raw_result else []
    parsed_segments = []
    for seg in raw_segments:
        parsed_segments.append(
            WhisperSegment(
                text=seg.get("text", "").strip(),
                start=round(float(seg.get("start", 0.0)), 2),
                end=round(float(seg.get("end", 0.0)), 2)
            )
        )

    if not parsed_segments and text:
        parsed_segments.append(WhisperSegment(text=text, start=0.0, end=0.5))

    return WhisperOutput(
        success=True,
        recognized_text=text,
        language=lang,
        processing_time_ms=elapsed_ms,
        segments=parsed_segments
    )
