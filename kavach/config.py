"""Runtime configuration, read from the environment (and a local .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def _load_dotenv() -> None:
    """Minimal .env loader: real environment variables always win."""
    if not _ENV_FILE.exists():
        return
    for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, default))


@dataclass(frozen=True)
class Settings:
    sarvam_api_key: str
    # Models (verified against docs.sarvam.ai, Sep 2026)
    reasoning_model: str = "sarvam-105b"
    chat_model: str = "sarvam-105b-conversations"
    stt_model: str = "saaras:v3"
    tts_model: str = "bulbul:v3"
    # Limits
    max_upload_mb: int = 25
    max_audio_seconds: int = 900  # batch STT allows up to 2 h; cap for cost/latency
    max_text_chars: int = 12000
    max_pdf_pages: int = 10  # Sarvam Vision per-job cap
    rest_stt_max_seconds: float = 29.5  # REST STT hard limit is 30 s
    # Operations
    rate_limit_per_minute: int = 12
    request_timeout_seconds: float = 90.0
    job_timeout_seconds: int = 240  # fits inside a 300 s serverless function limit


@lru_cache
def get_settings() -> Settings:
    _load_dotenv()
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not key:
        raise RuntimeError("SARVAM_API_KEY is not set (add it to .env or the environment).")
    return Settings(
        sarvam_api_key=key,
        reasoning_model=os.environ.get("KAVACH_REASONING_MODEL", Settings.reasoning_model),
        chat_model=os.environ.get("KAVACH_CHAT_MODEL", Settings.chat_model),
        max_upload_mb=_int("KAVACH_MAX_UPLOAD_MB", Settings.max_upload_mb),
        max_audio_seconds=_int("KAVACH_MAX_AUDIO_SECONDS", Settings.max_audio_seconds),
        rate_limit_per_minute=_int("KAVACH_RATE_LIMIT_PER_MINUTE", Settings.rate_limit_per_minute),
    )
