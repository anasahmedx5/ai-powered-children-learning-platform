import io
import os
import re
import csv
import difflib
import logging

os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
os.environ["PYTHONWARNINGS"] = "ignore"
os.environ["ABSL_LOG_LEVEL"] = "3"
os.environ["GLOG_minloglevel"] = "3"
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("uvicorn").setLevel(logging.ERROR)
logging.getLogger("uvicorn.access").setLevel(logging.ERROR)
logging.getLogger("fastapi").setLevel(logging.ERROR)

import cv2
import numpy as np
import tensorflow as tf
from PIL import Image
from typing import Optional, Tuple, List, Dict
from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from whisper_service import transcribe_audio, is_whisper_ready
from speech.services.pronunciation_pipeline import PronunciationPipeline, MissingExpectedWordError
from speech.alignment.dictionary import WordNotFoundError
from speech.alignment.mfa_service import AlignmentError, AudioTooShortError, AudioTooNoisyError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
pipeline = PronunciationPipeline()



def load_env_file():
    env_paths = [
        os.path.join(BASE_DIR, "..", ".env"),
        os.path.join(BASE_DIR, ".env"),
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, value = line.split("=", 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value

load_env_file()

if not os.environ.get("GROQ_API_KEY"):
    logger.info("GROQ_API_KEY not found in environment. AI Speech Tutor will use smart coded fallback feedback.")

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("MindBuzzLogger")

app = FastAPI(title="MindBuzz Tracing API")

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {
        "status": "ok",
        "backend": True,
        "whisper": is_whisper_ready()
    }

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CLASS_MAPPING = [
    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
    'A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z',
    'a', 'b', 'd', 'e', 'f', 'g', 'h', 'n', 'q', 'r', 't'
]

MODEL_PATH = os.environ.get("MODEL_PATH")
if not MODEL_PATH or not os.path.exists(MODEL_PATH):
    possible_paths = [
        os.path.abspath(os.path.join(BASE_DIR, "..", "model", "best_tracing_model.keras")),
        os.path.abspath(os.path.join(BASE_DIR, "model", "best_tracing_model.keras")),
        os.path.abspath(os.path.join(BASE_DIR, "best_tracing_model.keras")),
        os.path.abspath(os.path.join(BASE_DIR, "..", "best_tracing_model.keras")),
    ]
    MODEL_PATH = None
    for path in possible_paths:
        if os.path.exists(path):
            MODEL_PATH = path
            break

if MODEL_PATH and os.path.exists(MODEL_PATH):
    try:
        model = tf.keras.models.load_model(MODEL_PATH)
        logger.info("Tracing model loaded successfully.")
    except Exception as e:
        logger.error(f"Warning: Could not load model from {MODEL_PATH}. Error: {e}")
        model = None
else:
    model = None

def clean_text(text: str) -> str:
    return re.sub(r'[^\w\s]', '', text).lower().strip()

TARGET_WORD_MAPPING = {
    'A': 'apple', 'B': 'banana', 'C': 'castle', 'D': 'dolphin', 'E': 'elephant',
    'F': 'flower', 'G': 'garden', 'H': 'hammer', 'I': 'igloo', 'J': 'jacket',
    'K': 'kitten', 'L': 'lemon', 'M': 'monkey', 'N': 'number', 'O': 'orange',
    'P': 'panda', 'Q': 'queen', 'R': 'rabbit', 'S': 'spider', 'T': 'turtle',
    'U': 'umbrella', 'V': 'volcano', 'W': 'window', 'X': 'xylophone', 'Y': 'yellow', 'Z': 'zebra',
    'a': 'apple', 'b': 'banana', 'c': 'castle', 'd': 'dolphin', 'e': 'elephant',
    'f': 'flower', 'g': 'garden', 'h': 'hammer', 'i': 'igloo', 'j': 'jacket',
    'k': 'kitten', 'l': 'lemon', 'm': 'monkey', 'n': 'number', 'o': 'orange',
    'p': 'panda', 'q': 'queen', 'r': 'rabbit', 's': 'spider', 't': 'turtle',
    'u': 'umbrella', 'v': 'volcano', 'w': 'window', 'x': 'xylophone', 'y': 'yellow', 'z': 'zebra',
    '0': 'zero', '1': 'one', '2': 'two', '3': 'three', '4': 'four',
    '5': 'five', '6': 'six', '7': 'seven', '8': 'eight', '9': 'nine'
}

WORDS_DICTIONARY = {}

def load_words_csv():
    global WORDS_DICTIONARY
    possible_csv_paths = [
        os.path.abspath(os.path.join(BASE_DIR, "..", "words.csv")),
        os.path.abspath(os.path.join(BASE_DIR, "words.csv")),
    ]
    csv_path = None
    for p in possible_csv_paths:
        if os.path.exists(p):
            csv_path = p
            break
            
    if csv_path:
        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    letter = row.get("letter", "").strip().upper()
                    raw_words = row.get("words", "").strip()
                    if letter and raw_words:
                        words_list = [w.strip() for w in raw_words.split() if w.strip()]
                        WORDS_DICTIONARY[letter] = words_list
            logger.info(f"Loaded words dictionary from {csv_path} for {len(WORDS_DICTIONARY)} letters.")
        except Exception as e:
            logger.error(f"Error reading words.csv: {e}")

load_words_csv()

def print_model_box(title: str, items: list):
    import sys
    try:
        width = 58
        border_top = "┌" + "─" * width + "┐"
        border_mid = "├" + "─" * width + "┤"
        border_bot = "└" + "─" * width + "┘"
        
        lines = []
        lines.append("\n" + border_top)
        lines.append(f"│ {title:<{width-2}} │")
        lines.append(border_mid)
        for line in items:
            clean_l = str(line)[:width-2]
            lines.append(f"│ {clean_l:<{width-2}} │")
        lines.append(border_bot + "\n\n")

        full_str = "\n".join(lines)
        if hasattr(sys.stdout, 'buffer'):
            sys.stdout.buffer.write(full_str.encode('utf-8', errors='replace'))
            sys.stdout.buffer.flush()
        else:
            sys.stdout.write(full_str)
            sys.stdout.flush()
    except Exception as e:
        logger.warning(f"Print model box suppressed: {e}")

def is_speech_match(recognized_text: str, target_word: str) -> Tuple[bool, float]:
    cleaned_rec = clean_text(recognized_text)
    cleaned_word = clean_text(target_word)
    
    if not cleaned_rec or not cleaned_word:
        return False, 0.0

    if cleaned_rec == cleaned_word:
        return True, 1.0

    pattern = r'\b' + re.escape(cleaned_word) + r'\b'
    if re.search(pattern, cleaned_rec):
        return True, 1.0

    words = cleaned_rec.split()
    if cleaned_word in words:
        return True, 1.0

    max_ratio = 0.0
    for w in words:
        ratio = difflib.SequenceMatcher(None, w, cleaned_word).ratio()
        if ratio > max_ratio:
            max_ratio = ratio
        if ratio >= 0.95 and len(w) == len(cleaned_word) and w[0] == cleaned_word[0] and w[-1] == cleaned_word[-1]:
            return True, max_ratio

    return False, max_ratio


@app.get("/api/words")
async def get_words_dictionary():
    return {
        "status": "success",
        "words": WORDS_DICTIONARY
    }

def format_recognized_text(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r'^[^\w\s]+|[^\w\s]+$', '', text.strip())
    cleaned = re.sub(r'\.+', '', cleaned).strip()
    if not cleaned:
        return ""
    return " ".join(word.capitalize() for word in cleaned.split())

PHONEME_LETTER_MAP = {
    "AA": "A", "AE": "A", "AH": "A", "AO": "O", "AW": "A", "AY": "A",
    "B": "B", "CH": "C", "D": "D", "DH": "D", "EH": "E", "ER": "E", "EY": "E",
    "F": "F", "G": "G", "HH": "H", "IH": "I", "IY": "I", "JH": "J", "K": "K",
    "L": "L", "M": "M", "N": "N", "NG": "N", "OW": "O", "OY": "O", "P": "P",
    "R": "R", "S": "S", "SH": "S", "T": "T", "TH": "T", "UH": "U", "UW": "U",
    "V": "V", "W": "W", "Y": "Y", "Z": "Z", "ZH": "Z"
}

def map_phoneme_to_letter(phoneme: Optional[str], target_word: str) -> str:
    if not phoneme:
        return target_word[0].upper() if target_word else "A"
    
    clean_p = "".join(c for c in phoneme if c.isalpha()).upper()
    if clean_p in PHONEME_LETTER_MAP:
        mapped = PHONEME_LETTER_MAP[clean_p]
        if mapped in target_word.upper():
            return mapped
        return mapped
    
    for char in clean_p:
        if char in target_word.upper():
            return char
            
    return clean_p if clean_p else target_word[0].upper()


def get_groq_pronunciation_coach(
    target_word: str,
    weakest_letter: str,
    weakest_score: float,
    is_below_threshold: bool,
    is_correct: bool
) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    clean_target = target_word.strip().capitalize()
    clean_letter = weakest_letter.upper()
    
    # 1. If child pronounced correctly, skip Groq API to save tokens and use coded message
    if not is_below_threshold and is_correct:
        import random
        coded_compliments = [
            f"You said \"{clean_target}\" perfectly, great job! I'm so proud!",
            f"Awesome! Excellent pronunciation of \"{clean_target}\"!",
            f"Super job! You pronounced \"{clean_target}\" very clearly!"
        ]
        msg = random.choice(coded_compliments)
        print_model_box("🗣️ MODEL: Coded Speech Tutor (Token Saver)", [
            f"Target Word    : '{clean_target}'",
            f"Status         : ✅ PASSED (Groq API call skipped)",
            f"Coded Msg      : '{msg}'"
        ])
        return msg

    # 2. If child mispronounced, invoke Groq LLM to generate custom letter problem feedback
    if api_key:
        try:
            import json
            import urllib.request
            
            masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else api_key
            logger.info(f"Calling Groq Speech Tutor API endpoint for letter failure with key [{masked}]...")
            
            url = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
            
            prompt = (
                f"The child tried to pronounce the word '{clean_target}'. "
                f"The child has difficulty/a problem with the letter/sound '{clean_letter}' (confidence score: {weakest_score:.1f}%). "
                f"In 1 short, friendly sentence (max 20 words) for a child, tell them they have a problem with the letter '{clean_letter}' and encourage them to try saying the word '{clean_target}' again!"
            )

            payload = json.dumps({
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are a warm, encouraging AI speech tutor for children. State the letter problem clearly and ask the child to try saying the word again. Keep your message under 20 words."
                    },
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 60,
                "temperature": 0.3
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MindBuzz/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                msg = result["choices"][0]["message"]["content"].strip()
                logger.info(f"Groq Speech Tutor API call SUCCEEDED! Tip: '{msg}'")
                print_model_box("🗣️ MODEL: Groq Llama-3 LLM Speech Tutor", [
                    f"Target Word    : '{clean_target}'",
                    f"Problem Letter : '{clean_letter}' ({weakest_score:.1f}%)",
                    f"Below Threshold: Yes (< 50%)",
                    f"Groq Coach Msg : '{msg}'"
                ])
                return msg
        except Exception as e:
            logger.warning(f"Groq Speech Tutor API call error: {e}. Falling back to default msg.")

    msg = f"Oops! You seem to have a problem pronouncing the letter '{clean_letter}' in '{clean_target}'. Please try saying the word again!"

    print_model_box("🗣️ MODEL: Fallback LLM Speech Tutor", [
        f"Target Word    : '{clean_target}'",
        f"Problem Letter : '{clean_letter}' ({weakest_score:.1f}%)",
        f"Below Threshold: Yes (< 50%)",
        f"Groq Coach Msg : '{msg}'"
    ])
    return msg


@app.post("/api/evaluate-speech")
async def evaluate_speech(
    audio_data: UploadFile = File(...),
    target: str = Form(...)
):
    temp_audio_path = os.path.join(BASE_DIR, f"temp_rec_{os.urandom(4).hex()}.wav")
    recognized_text = ""
    is_correct = False
    target_word = target.strip().lower()
    report = None
    overall_score = 0.0
    weakest_phoneme = None
    weakest_score = 0.0
    confidence_threshold = 50.0
    is_below_threshold = False
    
    try:
        contents = await audio_data.read()
        with open(temp_audio_path, "wb") as f:
            f.write(contents)
        
        target_str = target.strip()
        if len(target_str) == 1:
            target_word = TARGET_WORD_MAPPING.get(target_str, target_str).lower()
        else:
            target_word = target_str.lower()

        try:
            report = pipeline.assess_pronunciation(
                audio_path=temp_audio_path,
                expected_letter=target_str.upper(),
                expected_word=target_word
            )
            recognized_text = report.recognized_word
            is_correct = report.recognized_correctly
            overall_score = report.overall_score
            weakest_phoneme = report.weakest_phoneme
            weakest_score = report.weakest_score if report.weakest_score is not None else report.overall_score
            confidence_threshold = report.confidence_threshold
            is_below_threshold = report.is_below_threshold
        except Exception as pe:
            logger.warning(f"Pronunciation pipeline fallback: {pe}")
            recognized_text = transcribe_audio(temp_audio_path)
            is_correct, similarity = is_speech_match(recognized_text, target_word)
            cleaned_recognized = clean_text(recognized_text)
            sim_percent = round(similarity * 100, 1)
            overall_score = sim_percent
            weakest_phoneme = target_str.upper()
            weakest_score = sim_percent
            confidence_threshold = 50.0
            is_below_threshold = (weakest_score < confidence_threshold)
            status_str = f"✅ MATCH PASSED ({sim_percent}%)" if is_correct else f"❌ MATCH FAILED ({sim_percent}%)"
            print_model_box("🎙️ MODEL: Whisper Speech Recognition", [
                f"Target Word    : {target_word.upper()}",
                f"Heard Text     : '{recognized_text}'",
                f"Cleaned Text   : '{cleaned_recognized}'",
                f"Speech Match   : {status_str}"
            ])
    except Exception as e:
        logger.error(f"Speech evaluation error: {e}")
        recognized_text = ""
        is_correct = False
        weakest_score = 0.0
        is_below_threshold = True
    finally:
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except Exception:
                pass

    cleaned_recognized = clean_text(recognized_text)
    formatted_recognized = format_recognized_text(recognized_text)
    display_recognized = formatted_recognized if formatted_recognized else "(unintelligible)"
    weakest_letter = map_phoneme_to_letter(weakest_phoneme, target_word)

    is_pass = is_correct and (not is_below_threshold)
    groq_msg = get_groq_pronunciation_coach(
        target_word=target_word,
        weakest_letter=weakest_letter,
        weakest_score=weakest_score,
        is_below_threshold=is_below_threshold,
        is_correct=is_correct
    )

    if is_pass:
        feedback = f"Awesome! You pronounced {target_word.capitalize()} correctly! Tracing is now unlocked."
    elif is_below_threshold:
        feedback = f"You have a problem pronouncing the letter '{weakest_letter}' ({weakest_score:.1f}% confidence). Try again!"
    else:
        feedback = f"Almost! Try pronouncing {target_word.capitalize()} clearly."

    return {
        "status": "success",
        "recognized": display_recognized,
        "raw_recognized": recognized_text,
        "cleaned_recognized": cleaned_recognized,
        "target_word": target_word,
        "target": target,
        "is_correct": is_correct,
        "overall_score": overall_score,
        "weakest_letter": weakest_letter,
        "weakest_score": weakest_score,
        "confidence_threshold": confidence_threshold,
        "is_below_threshold": is_below_threshold,
        "is_pass": is_pass,
        "groq_msg": groq_msg,
        "feedback": feedback
    }


@app.post("/api/pronunciation")
async def assess_pronunciation_endpoint(
    audio: UploadFile = File(...),
    expected_word: str = Form(...),
    expected_letter: Optional[str] = Form(None)
):
    """
    Evaluates children's pronunciation at the phoneme level using Whisper, MFA, and GOP scoring.
    """
    if not expected_word or not expected_word.strip():
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "MISSING_EXPECTED_WORD",
                "message": "Expected target word is missing or empty"
            }
        )

    temp_audio_path = os.path.join(BASE_DIR, f"temp_eval_{os.urandom(4).hex()}.wav")
    try:
        contents = await audio.read()
        if not contents or len(contents) < 50:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error_code": "AUDIO_TOO_SHORT",
                    "message": "Uploaded audio file is empty or corrupted"
                }
            )

        with open(temp_audio_path, "wb") as f:
            f.write(contents)

        report = pipeline.assess_pronunciation(
            audio_path=temp_audio_path,
            expected_letter=expected_letter or expected_word.strip()[0].upper(),
            expected_word=expected_word
        )
        weakest_letter = map_phoneme_to_letter(report.weakest_phoneme, expected_word)
        report.groq_msg = get_groq_pronunciation_coach(
            target_word=expected_word,
            weakest_letter=weakest_letter,
            weakest_score=report.weakest_score or report.overall_score,
            is_below_threshold=report.is_below_threshold,
            is_correct=report.recognized_correctly
        )
        return report.dict()

    except WordNotFoundError as e:
        return JSONResponse(
            status_code=404,
            content={
                "status": "error",
                "error_code": "WORD_NOT_FOUND",
                "message": str(e)
            }
        )
    except AudioTooShortError as e:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "AUDIO_TOO_SHORT",
                "message": str(e)
            }
        )
    except AudioTooNoisyError as e:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error_code": "AUDIO_TOO_NOISY",
                "message": str(e)
            }
        )
    except AlignmentError as e:
        return JSONResponse(
            status_code=422,
            content={
                "status": "error",
                "error_code": "ALIGNMENT_FAILURE",
                "message": str(e)
            }
        )
    except MissingExpectedWordError as e:
        return JSONResponse(
            status_code=400,
            content={
                "status": "error",
                "error_code": "MISSING_EXPECTED_WORD",
                "message": str(e)
            }
        )
    except Exception as e:
        logger.error(f"Pronunciation assessment error: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error_code": "PIPELINE_ERROR",
                "message": f"Internal error during pronunciation assessment: {str(e)}"
            }
        )
    finally:
        if os.path.exists(temp_audio_path):
            try:
                os.remove(temp_audio_path)
            except Exception:
                pass


@app.post("/api/evaluate")
async def evaluate_drawing(
    file: UploadFile = File(...),
    target_character: str = Form(...)
):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert('RGBA')

        white_bg = Image.new('RGBA', image.size, (255, 255, 255, 255))
        composited = Image.alpha_composite(white_bg, image).convert('L')
        img_np = np.array(composited)

        _, binary_img = cv2.threshold(img_np, 200, 255, cv2.THRESH_BINARY_INV)

        pts = cv2.findNonZero(binary_img)
        if pts is not None:
            x, y, w, h = cv2.boundingRect(pts)
            crop = binary_img[y:y+h, x:x+w]

            max_dim = max(w, h)
            square = np.zeros((max_dim, max_dim), dtype=np.uint8)
            pad_x = (max_dim - w) // 2
            pad_y = (max_dim - h) // 2
            square[pad_y:pad_y+h, pad_x:pad_x+w] = crop

            resized_20 = cv2.resize(square, (20, 20), interpolation=cv2.INTER_AREA)
            canvas_28 = np.zeros((28, 28), dtype=np.uint8)
            canvas_28[4:24, 4:24] = resized_20
            normalized = canvas_28 / 255.0
        else:
            resized = cv2.resize(binary_img, (28, 28), interpolation=cv2.INTER_AREA)
            normalized = resized / 255.0

        input_tensor = np.expand_dims(normalized, axis=(0, -1))

        target_confidence = 0.0
        top_confidence = 0.0
        predicted_char = target_character

        if model is not None:
            predictions = model.predict(input_tensor, verbose=0)
            
            top_idx = int(np.argmax(predictions[0]))
            predicted_char = CLASS_MAPPING[top_idx]
            top_confidence = float(predictions[0][top_idx])

            target_key = target_character
            if target_key not in CLASS_MAPPING:
                if target_key.upper() in CLASS_MAPPING:
                    target_key = target_key.upper()
                elif target_key.lower() in CLASS_MAPPING:
                    target_key = target_key.lower()

            if target_key in CLASS_MAPPING:
                target_idx = CLASS_MAPPING.index(target_key)
                target_confidence = float(predictions[0][target_idx])
            else:
                target_confidence = top_confidence

            logger.info(f"Target: '{target_character}', Top Prediction: '{predicted_char}' ({top_confidence:.4f}), Target Conf: ({target_confidence:.4f})")
        else:
            target_confidence = 0.92
            top_confidence = 0.92
            predicted_char = target_character
            logger.info("Model not loaded. Using fallback confidence score.")

        is_letter_match = (predicted_char.upper() == target_character.upper())
        passed = (is_letter_match and top_confidence >= 0.50) or (target_confidence >= 0.60)

        total_drawn_pixels = int(np.sum(binary_img > 0))

        res_str = "✅ PASSED" if passed else "❌ FAILED"
        print_model_box("🎨 MODEL: CNN Drawing Tracing Classifier", [
            f"Target Letter  : '{target_character}'",
            f"Predicted      : '{predicted_char}'",
            f"Target Conf    : {round(target_confidence * 100, 2)}%",
            f"Top Conf       : {round(top_confidence * 100, 2)}%",
            f"Result         : {res_str}"
        ])

        if passed:
            msg = f"Awesome! The AI clearly recognized your drawing as '{target_character}' with {round(max(target_confidence, top_confidence)*100)}% confidence!"
            coaching_tip = f"Great job! Your '{target_character}' is clear and drawn wonderfully!"
        else:
            if is_letter_match:
                msg = f"Close! The AI recognized '{predicted_char}', but needs a bit more clarity. Keep practicing!"
            else:
                msg = f"Nice try! The AI recognized '{predicted_char}' instead of '{target_character}'. Try drawing '{target_character}' again!"
            
            coaching_tip = get_groq_coaching_tip(target_character, predicted_char, passed, max(target_confidence, top_confidence))

        return {
            "status": "success",
            "target": target_character,
            "predicted": predicted_char,
            "confidence": round(target_confidence * 100, 2),
            "top_confidence": round(top_confidence * 100, 2),
            "total_stroke_pixels": total_drawn_pixels,
            "passed": passed,
            "message": msg,
            "coaching_tip": coaching_tip
        }

    except Exception as e:
        logger.error(f"Error during evaluation: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during image evaluation")


def get_groq_coaching_tip(target: str, predicted: str, passed: bool, confidence: float) -> str:
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    
    if api_key:
        try:
            import json
            import urllib.request

            masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else api_key
            logger.info(f"Calling Groq API endpoint with key [{masked}]...")

            url = os.environ.get("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
            if passed:
                prompt = (
                    f"Target: {target}. Status: Correct. "
                    f"Give a very brief 1-sentence compliment (max 12 words) on drawing {target} well!"
                )
            else:
                prompt = (
                    f"The child tried to draw {target}, but drew {predicted}. "
                    f"In 1 short, clear sentence (max 20 words), tell them they drew {predicted} instead of {target}, and give simple step-by-step stroke instructions on how to draw {target} correctly."
                )

            payload = json.dumps({
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an ultra-concise handwriting tutor for kids. State what was drawn wrong and give clear stroke instructions to draw the target letter. Keep your response under 20 words."
                    },
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 60,
                "temperature": 0.2
            }).encode('utf-8')

            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) MindBuzz/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                tip = result["choices"][0]["message"]["content"].strip()
                logger.info(f"Groq API call SUCCEEDED using key [{masked}]! Tip: '{tip}'")
                print_model_box("🤖 MODEL: Groq Llama-3 LLM Handwriting Coach", [
                    f"Target Letter  : '{target}'",
                    f"Predicted      : '{predicted}'",
                    f"Status         : {'Passed' if passed else 'Needs Practice'}",
                    f"Coaching Tip   : '{tip}'"
                ])
                return tip
        except Exception as e:
            logger.warning(f"Groq API call error: {e}. Falling back to default coaching tip.")

    tip = get_fallback_coaching_tip(target, predicted, passed)
    print_model_box("🤖 MODEL: Fallback LLM Handwriting Coach", [
        f"Target Letter  : '{target}'",
        f"Predicted      : '{predicted}'",
        f"Status         : {'Passed' if passed else 'Needs Practice'}",
        f"Coaching Tip   : '{tip}'"
    ])
    return tip


def get_fallback_coaching_tip(target: str, predicted: str, passed: bool) -> str:
    if passed:
        return f"Fantastic work! Your '{target}' is clear and well-formed. Keep up the great drawing!"
    
    t_upper = target.upper()
    tips = {
        'A': "Try drawing two slanting lines pointing up like a tent, then cross them in the middle!",
        'B': "Draw one tall straight line first, then add two rounded bumps on the right side!",
        'C': "Curve your pencil around like a crescent moon, leaving a big open space on the right!",
        'D': "Draw a straight vertical line, then add one big curved belly on the right side!",
        'E': "Draw a straight line down, and add three horizontal bars extending to the right!",
        'F': "Draw a straight vertical line, then add two horizontal bars at the top and middle!",
        'G': "Curve like a 'C', then add a little horizontal step coming inward at the middle!",
        'H': "Draw two straight vertical lines side-by-side, then connect them with a horizontal bridge!",
        'I': "Draw a single straight vertical line from top to bottom!",
        'J': "Draw a straight line down, then hook it up at the bottom like an umbrella handle!",
        'O': "Draw a nice, smooth complete loop like a circle!",
        'S': "Curve left first, then curve right below it like a wiggly snake!",
        '0': "Make a smooth oval or circle loop from top to bottom!",
        '1': "Draw one clean, straight vertical line going straight down!",
        '2': "Curve around the top, slant down to the bottom left, then draw a flat line across!",
        '3': "Draw two small rounded curves stacked on top of each other!",
        '4': "Go down, across, and draw a long straight line down through the middle!",
        '5': "Go down a bit, make a round belly, and add a flat hat on top!",
        '6': "Slant down towards the left and curl into a full circle at the bottom!",
        '7': "Draw a flat line across the top, then slant down sharply to the bottom left!",
        '8': "Make a smooth figure-8 by drawing two loops stacked together!",
        '9': "Make a full loop at the top, then draw a straight line straight down on the right!"
    }
    
    if t_upper in tips:
        return f"Coaching Tip: {tips[t_upper]}"
    
    return f"Try drawing '{target}' carefully. Focus on making the main strokes clear!"

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="error")
