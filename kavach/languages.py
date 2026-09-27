"""Language metadata for the 22 scheduled Indian languages + English.

Support matrix (docs.sarvam.ai, Sep 2026):
  * Saaras v3 STT, Sarvam Vision OCR, sarvam-translate:v1: all 23
  * Bulbul v3 TTS: 11 (bn, en, gu, hi, kn, ml, mr, od, pa, ta, te)
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str
    name: str
    native: str
    script: str
    tts: bool
    speaker: str | None = None  # default Bulbul v3 voice


_SCRIPTS: dict[str, str] = {
    "Deva": r"ऀ-ॿ",
    "Beng": r"ঀ-৿",
    "Guru": r"਀-੿",
    "Gujr": r"઀-૿",
    "Orya": r"଀-୿",
    "Taml": r"஀-௿",
    "Telu": r"ఀ-౿",
    "Knda": r"ಀ-೿",
    "Mlym": r"ഀ-ൿ",
    "Arab": r"؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿",
    "Olck": r"᱐-᱿",
    "Mtei": r"ꯀ-꯿ঀ-৿",
    "Latn": r"A-Za-z",
}

LANGUAGES: dict[str, Language] = {
    lang.code: lang
    for lang in [
        Language("hi-IN", "Hindi", "हिन्दी", "Deva", True, "shubh"),
        Language("bn-IN", "Bengali", "বাংলা", "Beng", True, "shubh"),
        Language("ta-IN", "Tamil", "தமிழ்", "Taml", True, "kavitha"),
        Language("te-IN", "Telugu", "తెలుగు", "Telu", True, "shubh"),
        Language("mr-IN", "Marathi", "मराठी", "Deva", True, "shubh"),
        Language("gu-IN", "Gujarati", "ગુજરાતી", "Gujr", True, "shubh"),
        Language("kn-IN", "Kannada", "ಕನ್ನಡ", "Knda", True, "shubh"),
        Language("ml-IN", "Malayalam", "മലയാളം", "Mlym", True, "shubh"),
        Language("pa-IN", "Punjabi", "ਪੰਜਾਬੀ", "Guru", True, "shubh"),
        Language("od-IN", "Odia", "ଓଡ଼ିଆ", "Orya", True, "shubh"),
        Language("en-IN", "English", "English", "Latn", True, "shubh"),
        Language("as-IN", "Assamese", "অসমীয়া", "Beng", False),
        Language("ur-IN", "Urdu", "اردو", "Arab", False),
        Language("ne-IN", "Nepali", "नेपाली", "Deva", False),
        Language("kok-IN", "Konkani", "कोंकणी", "Deva", False),
        Language("ks-IN", "Kashmiri", "کٲشُر", "Arab", False),
        Language("sd-IN", "Sindhi", "سنڌي", "Arab", False),
        Language("sa-IN", "Sanskrit", "संस्कृतम्", "Deva", False),
        Language("sat-IN", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ", "Olck", False),
        Language("mni-IN", "Manipuri", "মৈতৈলোন্", "Mtei", False),
        Language("brx-IN", "Bodo", "बर'", "Deva", False),
        Language("mai-IN", "Maithili", "मैथिली", "Deva", False),
        Language("doi-IN", "Dogri", "डोगरी", "Deva", False),
    ]
}

DEFAULT_LANGUAGE = "hi-IN"


def get(code: str | None) -> Language:
    return LANGUAGES.get(code or "", LANGUAGES[DEFAULT_LANGUAGE])


def script_ratio(text: str, script: str) -> float:
    """Share of letters in `text` that belong to `script` (0..1).

    Digits, punctuation and whitespace are ignored. Used to detect an LLM
    answering in the wrong language, a failure mode we observed in testing.
    """
    letters = [ch for ch in text if unicodedata.category(ch)[0] in ("L", "M")]
    if not letters:
        return 0.0
    pattern = re.compile(f"[{_SCRIPTS[script]}]")
    return sum(1 for ch in letters if pattern.match(ch)) / len(letters)


def is_in_language(text: str, code: str, threshold: float = 0.6) -> bool:
    return script_ratio(text, get(code).script) >= threshold


def detect_script_language(text: str) -> str | None:
    """Cheap offline guess of the language from its dominant script."""
    best, best_ratio = None, 0.0
    for script in ("Deva", "Beng", "Guru", "Gujr", "Orya", "Taml", "Telu", "Knda", "Mlym", "Arab", "Olck", "Latn"):
        ratio = script_ratio(text, script)
        if ratio > best_ratio:
            best, best_ratio = script, ratio
    if best is None or best_ratio < 0.5:
        return None
    first = {"Deva": "hi-IN", "Beng": "bn-IN", "Latn": "en-IN", "Arab": "ur-IN", "Olck": "sat-IN"}
    if best in first:
        return first[best]
    return next(lang.code for lang in LANGUAGES.values() if lang.script == best)
