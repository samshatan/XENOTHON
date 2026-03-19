"""
NER Agent – named-entity recognition using spaCy + regex.

Extracts:
    persons       : PERSON entities
    organisations : ORG entities
    dates         : DATE entities
    pan_numbers   : PAN card numbers  (AAAAA9999A pattern)
    gstin_numbers : GSTIN             (15-char alphanumeric)
    emails        : e-mail addresses
    phone_numbers : Indian / generic phone numbers
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# ── Regex patterns ──────────────────────────────────────────────────────────
_PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b")
_GSTIN_RE = re.compile(
    r"\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}\b"
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+91[\-\s]?)?[6-9]\d{9}(?!\d)"
    r"|(?<!\d)(?:\+?\d{1,3}[\-\s]?)?\(?\d{3}\)?[\-\s]?\d{3}[\-\s]?\d{4}(?!\d)"
)


def _dedupe(lst: List[str]) -> List[str]:
    seen = set()
    out = []
    for item in lst:
        low = item.strip().lower()
        if low and low not in seen:
            seen.add(low)
            out.append(item.strip())
    return out


def _run_ner(text: str) -> Dict[str, Any]:
    import spacy

    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        # Model not downloaded yet – try to download it
        import subprocess
        import sys

        subprocess.run(
            [sys.executable, "-m", "spacy", "download", "en_core_web_sm"],
            check=False,
        )
        nlp = spacy.load("en_core_web_sm")

    # spaCy has a default max_length; handle very large docs gracefully
    max_chars = 500_000
    if len(text) > max_chars:
        text = text[:max_chars]

    doc = nlp(text)

    persons: List[str] = []
    organisations: List[str] = []
    dates: List[str] = []

    for ent in doc.ents:
        if ent.label_ == "PERSON":
            persons.append(ent.text)
        elif ent.label_ == "ORG":
            organisations.append(ent.text)
        elif ent.label_ == "DATE":
            dates.append(ent.text)

    pan_numbers = _PAN_RE.findall(text)
    gstin_numbers = _GSTIN_RE.findall(text)
    emails = _EMAIL_RE.findall(text)
    phone_numbers = _PHONE_RE.findall(text)

    return {
        "persons": _dedupe(persons),
        "organisations": _dedupe(organisations),
        "dates": _dedupe(dates),
        "pan_numbers": _dedupe(pan_numbers),
        "gstin_numbers": _dedupe(gstin_numbers),
        "emails": _dedupe(emails),
        "phone_numbers": _dedupe(phone_numbers),
        "entity_count": len(persons) + len(organisations) + len(dates),
    }


async def run_ner_agent(state: dict) -> dict:
    ocr_results: Dict[str, Any] = state.get("ocr_results", {})
    text: str = ocr_results.get("text", "")

    if not text.strip():
        logger.warning("NER agent: no text to process")
        state["ner_results"] = {
            "persons": [],
            "organisations": [],
            "dates": [],
            "pan_numbers": [],
            "gstin_numbers": [],
            "emails": [],
            "phone_numbers": [],
            "entity_count": 0,
            "warning": "No text available for NER",
        }
        return state

    loop = asyncio.get_event_loop()
    try:
        results = await loop.run_in_executor(None, _run_ner, text)
    except Exception as exc:
        logger.exception("NER agent failed: %s", exc)
        results = {
            "persons": [],
            "organisations": [],
            "dates": [],
            "pan_numbers": [],
            "gstin_numbers": [],
            "emails": [],
            "phone_numbers": [],
            "entity_count": 0,
            "error": str(exc),
        }

    state["ner_results"] = results
    logger.info(
        "NER agent complete – orgs=%d  persons=%d  dates=%d",
        len(results.get("organisations", [])),
        len(results.get("persons", [])),
        len(results.get("dates", [])),
    )
    return state
