"""
ai_caller.py — Centralized AI gateway for VerifyFlow.

All agents call `call_ai()` — never call Gemini/Groq directly.

Fallback chain:
  1. Gemini 2.5 Flash-Lite  (speed="fast",   1000 req/day free per key)
  2. Gemini 2.5 Flash       (speed="normal",   250 req/day free per key)
  3. Gemini 2.5 Pro         (speed="smart",    100 req/day free per key)
     Rotates through GEMINI_KEY_1…3 before giving up on Gemini.
  4. Groq  llama-3.3-70b    (free, no card)
  5. OpenRouter mistral-7b  (free tier)
  6. Safe default JSON       (demo never crashes)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Optional

import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── API Keys ────────────────────────────────────────────────────────────────
_GEMINI_KEYS: list[str] = [
    k for k in [
        os.getenv("GEMINI_API_KEY_1"),
        os.getenv("GEMINI_API_KEY_2"),
        os.getenv("GEMINI_API_KEY_3"),
        os.getenv("GEMINI_API_KEY_4"),
        os.getenv("GEMINI_API_KEY"),      # fallback single-key setups
    ]
    if k
]

GROQ_API_KEY       = os.getenv("GROQ_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# ── In-memory result cache (avoid repeated API calls for same doc) ───────────
_cache: dict[str, str] = {}

# ── Key rotation counter ─────────────────────────────────────────────────────
_key_index = 0


def _next_gemini_key() -> Optional[str]:
    """Return the next Gemini key in round-robin order."""
    global _key_index
    if not _GEMINI_KEYS:
        return None
    key = _GEMINI_KEYS[_key_index % len(_GEMINI_KEYS)]
    _key_index += 1
    return key


# ── Model selection by speed ─────────────────────────────────────────────────
_MODEL_MAP = {
    "fast":   "gemini-2.5-flash-lite-preview-06-17",   # 1000 RPD free
    "normal": "gemini-2.5-flash",                       # 250  RPD free
    "smart":  "gemini-2.5-pro",                         # 100  RPD free
}


def _clean_json(raw: str) -> str:
    """Strip markdown code fences so JSON.loads works cleanly."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?", "", raw)
    raw = re.sub(r"```$", "", raw)
    return raw.strip()


# ── Provider: Gemini ─────────────────────────────────────────────────────────
def _call_gemini(prompt: str, speed: str = "normal") -> Optional[str]:
    """Try all available Gemini keys before giving up."""
    model_name = _MODEL_MAP.get(speed, _MODEL_MAP["normal"])
    attempts = max(len(_GEMINI_KEYS), 1)

    for attempt in range(attempts):
        key = _next_gemini_key()
        if not key:
            break
        try:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=2048,
                ),
            )
            response = model.generate_content(prompt)
            result = response.text
            logger.info("Gemini [%s] OK (attempt %d)", model_name, attempt + 1)
            return result
        except Exception as exc:
            err = str(exc)
            if "429" in err or "RESOURCE_EXHAUSTED" in err:
                wait = (2 ** attempt) * 3
                logger.warning("Gemini 429 on key %d — waiting %ss", attempt + 1, wait)
                time.sleep(wait)
            else:
                logger.warning("Gemini error: %s", err)
                break  # non-rate-limit error; skip to next provider

    return None


# ── Provider: Groq ───────────────────────────────────────────────────────────
def _call_groq(prompt: str) -> Optional[str]:
    if not GROQ_API_KEY:
        return None
    try:
        from groq import Groq  # type: ignore
        client = Groq(api_key=GROQ_API_KEY)
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500,
        )
        result = response.choices[0].message.content
        logger.info("Groq OK — used as fallback")
        return result
    except Exception as exc:
        logger.warning("Groq error: %s", exc)
        return None


# ── Provider: OpenRouter ─────────────────────────────────────────────────────
def _call_openrouter(prompt: str) -> Optional[str]:
    if not OPENROUTER_API_KEY:
        return None
    try:
        import openai as _openai  # type: ignore
        client = _openai.OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=OPENROUTER_API_KEY,
        )
        response = client.chat.completions.create(
            model="mistralai/mistral-7b-instruct:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
        )
        result = response.choices[0].message.content
        logger.info("OpenRouter OK — used as final fallback")
        return result
    except Exception as exc:
        logger.warning("OpenRouter error: %s", exc)
        return None


# ── Public API ───────────────────────────────────────────────────────────────
def call_ai(
    prompt: str,
    speed: str = "normal",
    cache_key: Optional[str] = None,
) -> str:
    """
    Call an AI provider with automatic fallback.

    Args:
        prompt:    The full prompt string to send.
        speed:     "fast" | "normal" | "smart"
        cache_key: If provided, cache and reuse response for same doc.

    Returns:
        Raw text response string (may be JSON or natural language).
        Never raises — always returns a string.
    """
    # Cache hit
    if cache_key and cache_key in _cache:
        logger.debug("Cache hit: %s", cache_key)
        return _cache[cache_key]

    result: Optional[str] = None

    # 1. Gemini (with key rotation)
    result = _call_gemini(prompt, speed=speed)

    # 2. Groq fallback
    if not result:
        result = _call_groq(prompt)

    # 3. OpenRouter fallback
    if not result:
        result = _call_openrouter(prompt)

    # 4. Safe default so demo never crashes
    if not result:
        logger.error("All AI providers exhausted — returning safe default")
        result = json.dumps({
            "penalty": 0,
            "flags": [],
            "summary": "AI analysis temporarily unavailable. Manual review recommended.",
        })

    # Store in cache
    if cache_key:
        _cache[cache_key] = result

    return result


def call_ai_json(
    prompt: str,
    speed: str = "normal",
    cache_key: Optional[str] = None,
    fallback: Optional[dict] = None,
) -> dict:
    """
    Convenience wrapper — calls call_ai() and parses the result as JSON.

    Returns the parsed dict, or `fallback` (default {}) on parse failure.
    """
    raw = call_ai(prompt, speed=speed, cache_key=cache_key)
    try:
        return json.loads(_clean_json(raw))
    except (json.JSONDecodeError, ValueError):
        logger.warning("JSON parse failed for cache_key=%s", cache_key)
        return fallback if fallback is not None else {}


# ── Quick self-test ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing ai_caller.py …\n")

    test_prompt = (
        'Respond ONLY with valid JSON, no markdown:\n'
        '{"status": "ok", "message": "ai_caller working"}'
    )
    result = call_ai(test_prompt, speed="fast", cache_key="self_test")
    print("Result:", result)

    # Second call — should hit cache
    result2 = call_ai(test_prompt, speed="fast", cache_key="self_test")
    assert result == result2, "Cache miss!"
    print("Cache: OK")
    print("\n✅ ai_caller.py self-test passed")
