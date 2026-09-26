"""
Central configuration for the Book2Trek voice-AI layer.

Everything that talks to an external service reads its settings here and each
has a working *fallback*, so the whole package imports, runs, and tests green
with no API keys. Set the real keys in .env (see .env.example) to go live.
"""
from __future__ import annotations

import os


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


# --- Auth / API ------------------------------------------------------------
JWT_SECRET = _get("JWT_SECRET", "dev-secret-change-me")
JWT_ALGO = "HS256"
JWT_TTL_MIN = int(_get("JWT_TTL_MIN", "120"))
API_BASE_URL = _get("API_BASE_URL", "http://127.0.0.1:5000")

# --- Cache (Redis, with in-memory fallback) --------------------------------
REDIS_URL = _get("REDIS_URL", "")          # empty -> in-memory cache
CACHE_TTL_SEC = int(_get("CACHE_TTL_SEC", "60"))

# --- Celery (async notifications; eager fallback) --------------------------
CELERY_BROKER_URL = _get("CELERY_BROKER_URL", "")   # empty -> eager (inline)

# --- Voice stack -----------------------------------------------------------
OPENAI_API_KEY = _get("OPENAI_API_KEY", "")
DEEPGRAM_API_KEY = _get("DEEPGRAM_API_KEY", "")
LIVEKIT_URL = _get("LIVEKIT_URL", "")
LIVEKIT_API_KEY = _get("LIVEKIT_API_KEY", "")
LIVEKIT_API_SECRET = _get("LIVEKIT_API_SECRET", "")

LLM_MODEL = _get("LLM_MODEL", "gpt-4o-mini")
TTS_VOICE = _get("TTS_VOICE", "alloy")
# Deepgram nova-2 supports many languages; "multi" auto-detects for the
# multilingual claim (Hindi/English code-switching etc.).
ASR_MODEL = _get("ASR_MODEL", "nova-2")
ASR_LANGUAGE = _get("ASR_LANGUAGE", "multi")
EMBED_MODEL = _get("EMBED_MODEL", "text-embedding-3-small")


def have_openai() -> bool:
    return bool(OPENAI_API_KEY)


def live_mode() -> bool:
    """True only when real external calls should be made (keys + opt-in)."""
    return bool(OPENAI_API_KEY) and _get("RUN_LIVE", "0") == "1"
