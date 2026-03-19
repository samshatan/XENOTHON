"""
6-layer AI caller with automatic fallback.

Layer 1-3 : Gemini key rotation  (google-generativeai, gemini-2.5-pro-latest)
Layer 4   : Groq                  (langchain-groq, llama-3.3-70b-versatile)
Layer 5   : OpenRouter            (openai client → openai/gpt-4o-mini)
Layer 6   : Safe default          (static JSON response)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

_GEMINI_KEYS = [
    os.getenv("GEMINI_API_KEY_1", ""),
    os.getenv("GEMINI_API_KEY_2", ""),
    os.getenv("GEMINI_API_KEY_3", ""),
]
_GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
_OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")


_SAFE_DEFAULT: Dict[str, Any] = {
    "analysis": "Unable to perform AI analysis at this time.",
    "visual_score": 50,
    "visual_flags": ["AI analysis unavailable – manual review required"],
    "gemini_analysis": "All AI providers unavailable. Please retry later.",
    "trust_score": 50,
    "verdict": "SUSPICIOUS",
    "summary": "Automated AI analysis could not be completed. Manual review recommended.",
    "red_flags": [],
    "error": "all_providers_unavailable",
}


def _clean_json_response(text: str) -> str:
    """Strip markdown fences that models sometimes wrap around JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first and last fence lines
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner).strip()
    return text


async def _call_gemini(api_key: str, prompt: str, system_prompt: str, json_mode: bool) -> Dict[str, Any]:
    import google.generativeai as genai

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-2.5-pro-latest",
        system_instruction=system_prompt if system_prompt else None,
    )

    full_prompt = prompt
    if json_mode:
        full_prompt = prompt + "\n\nRespond ONLY with valid JSON, no markdown fences."

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: model.generate_content(full_prompt),
    )
    raw = response.text
    if json_mode:
        raw = _clean_json_response(raw)
        return json.loads(raw)
    return {"text": raw}


async def _call_groq(prompt: str, system_prompt: str, json_mode: bool) -> Dict[str, Any]:
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage

    messages = []
    if system_prompt:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=prompt))

    kwargs: Dict[str, Any] = {}
    if json_mode:
        kwargs["model_kwargs"] = {"response_format": {"type": "json_object"}}

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=_GROQ_API_KEY,
        **kwargs,
    )

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: llm.invoke(messages))
    raw = response.content
    if json_mode:
        raw = _clean_json_response(raw)
        return json.loads(raw)
    return {"text": raw}


async def _call_openrouter(prompt: str, system_prompt: str, json_mode: bool) -> Dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        api_key=_OPENROUTER_API_KEY,
        base_url="https://openrouter.ai/api/v1",
    )

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    kwargs: Dict[str, Any] = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    completion = await client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=messages,
        **kwargs,
    )
    raw = completion.choices[0].message.content or "{}"
    if json_mode:
        raw = _clean_json_response(raw)
        return json.loads(raw)
    return {"text": raw}


async def call_ai(
    prompt: str,
    system_prompt: str = "",
    json_mode: bool = True,
) -> Dict[str, Any]:
    """
    Attempt each layer in sequence, returning on first success.
    Layer 6 always succeeds (returns _SAFE_DEFAULT).
    """
    # Layers 1-3: Gemini key rotation
    for idx, key in enumerate(_GEMINI_KEYS, start=1):
        if not key:
            continue
        try:
            result = await _call_gemini(key, prompt, system_prompt, json_mode)
            logger.info("AI call succeeded via Gemini layer %d", idx)
            return result
        except Exception as exc:
            logger.warning("Gemini layer %d failed: %s", idx, exc)

    # Layer 4: Groq
    if _GROQ_API_KEY:
        try:
            result = await _call_groq(prompt, system_prompt, json_mode)
            logger.info("AI call succeeded via Groq (layer 4)")
            return result
        except Exception as exc:
            logger.warning("Groq layer 4 failed: %s", exc)

    # Layer 5: OpenRouter
    if _OPENROUTER_API_KEY:
        try:
            result = await _call_openrouter(prompt, system_prompt, json_mode)
            logger.info("AI call succeeded via OpenRouter (layer 5)")
            return result
        except Exception as exc:
            logger.warning("OpenRouter layer 5 failed: %s", exc)

    # Layer 6: Safe default
    logger.error("All AI providers failed – returning safe default (layer 6)")
    return dict(_SAFE_DEFAULT)
