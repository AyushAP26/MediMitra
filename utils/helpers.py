# ==========================================
# utils/helpers.py — Language & Text Utilities
# ==========================================
import re
import logging
from langdetect import detect, LangDetectException
from data.static_data import NORMALIZATION

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "en": "English", "hi": "Hindi", "kn": "Kannada", "te": "Telugu",
    "ta": "Tamil", "ml": "Malayalam", "gu": "Gujarati", "mr": "Marathi",
    "bn": "Bengali", "pa": "Punjabi", "ur": "Urdu", "or": "Odia"
}

def normalize_symptom_token(s: str) -> str:
    if not s: return ""
    s = str(s).lower().strip()
    s = re.sub(r"[^\w\s]", "", s)
    if s in NORMALIZATION: return NORMALIZATION[s]
    for k, v in NORMALIZATION.items():
        if k in s: return v
    return s

def detect_lang_safe(text: str) -> str:
    """
    Detect language with improved handling for short English medical phrases.
    langdetect is unreliable with short phrases like "I have fever".
    """
    try:
        text_lower = text.lower().strip()

        english_indicators = [
            "i have", "i am", "i feel", "i'm having", "i've been",
            "what is", "what are", "how to", "how do",
            "do i have", "could this be", "is this",
        ]
        if any(indicator in text_lower for indicator in english_indicators):
            return "en"

        # Detect script for Indian languages
        if any('\u0980' <= char <= '\u09FF' for char in text): return "bn"
        if any('\u0A00' <= char <= '\u0A7F' for char in text): return "pa"
        if any('\u0A80' <= char <= '\u0AFF' for char in text): return "gu"
        if any('\u0B00' <= char <= '\u0B7F' for char in text): return "or"
        if any('\u0B80' <= char <= '\u0BFF' for char in text): return "ta"
        if any('\u0C00' <= char <= '\u0C7F' for char in text): return "te"
        if any('\u0C80' <= char <= '\u0CFF' for char in text): return "kn"
        if any('\u0D00' <= char <= '\u0D7F' for char in text): return "ml"
        if any('\u0900' <= char <= '\u097F' for char in text):
            try:
                detected = detect(text)
                if detected in ['mr', 'ne']: return detected
            except Exception:
                pass
            return "hi"

        detected = detect(text)
        is_all_ascii = all(ord(c) < 128 for c in text.strip())
        if detected in ['no', 'da', 'sv', 'nl', 'af'] and is_all_ascii and len(text.split()) <= 3:
            return "en"
        return detected
    except (LangDetectException, Exception):
        return "en"
