"""
linguistic_agent.py — AI-powered linguistic fingerprinting for fraud detection.

Detects:
  - Template/boilerplate markers
  - Wrong corporate vocabulary
  - Copy-paste artifacts
  - AI-generated text patterns
  - Missing mandatory clauses for document type
  - Wrong legal jurisdiction references
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────
_PROMPT_TEMPLATE = """
You are an expert document authenticity analyst specialising in Indian corporate documents.

Analyse this document text for linguistic authenticity signals.

DOCUMENT TEXT:
{text}

CLAIMED COMPANY: {company}
CLAIMED DOCUMENT TYPE: {doc_type}

Check ALL of these fraud signals:

1. TEMPLATE MARKERS
   - Generic phrases like "Dear Candidate" with zero personalisation
   - Boilerplate text common in online fake offer templates
   - Missing specific company/person details that real docs always include

2. WRONG CORPORATE VOCABULARY
   - Real Infosys/TCS offers say "Cost to Company (CTC)" not "salary package"
   - Real Indian legal docs use terms like "wherein", "hereinafter", "the party of the first part"
   - Real rent agreements reference the Indian Registration Act and Stamp Act

3. COPY-PASTE ARTIFACTS
   - Same sentence or phrase appearing more than once
   - Sudden change in formality or writing style mid-document
   - Inconsistent punctuation style (Oxford comma in one place, none elsewhere)

4. WRONG JURISDICTION LANGUAGE
   - US legal terms ("first party", "pursuant to Section 5 of the UCC") in an Indian document
   - References to laws that do not exist in India

5. AI-GENERATED / MACHINE-TRANSLATED PATTERNS
   - Unnaturally perfect grammar with zero stylistic variation
   - Every sentence approximately the same length
   - No common corporate shorthand (e.g., CTC, DOJ, LWD)

6. MISSING STANDARD ELEMENTS
   - Job offer: should have designation, department, reporting manager, probation period, joining bonus if any
   - Rent agreement: should have registration number, witness details, stamp duty amount, Aadhaar references
   - Legal contract: should have governing law clause, dispute resolution / arbitration clause

Respond ONLY in valid JSON. No markdown. No backticks. No extra text:
{{"linguistic_flags":[{{"issue":"...","severity":"HIGH/MEDIUM/LOW","category":"TEMPLATE/VOCABULARY/ARTIFACT/JURISDICTION/AI_GENERATED/MISSING_ELEMENT"}}],"linguistic_penalty":0,"feels_authentic":true,"most_suspicious":"one sentence","confidence":"HIGH/MEDIUM/LOW"}}

Rules for linguistic_penalty:
- Each HIGH flag: +12 pts
- Each MEDIUM flag: +6 pts
- Each LOW flag: +2 pts
- Cap at 35
""".strip()


# ── Public API ────────────────────────────────────────────────────────────────

def analyze_linguistics(
    text: str,
    company: str,
    doc_type: str,
    cache_key: Optional[str] = None,
) -> dict[str, Any]:
    """
    Use AI to analyse linguistic authenticity of a document.

    Args:
        text:       Raw document text.
        company:    Claimed company name.
        doc_type:   Detected document type (job_offer, rental_deed, etc.)
        cache_key:  Optional key for response caching.

    Returns:
        {
            "linguistic_flags": [...],
            "linguistic_penalty": int,
            "feels_authentic": bool,
            "most_suspicious": str,
            "confidence": str
        }
    """
    _default: dict[str, Any] = {
        "linguistic_flags": [],
        "linguistic_penalty": 0,
        "feels_authentic": True,
        "most_suspicious": "Analysis unavailable",
        "confidence": "LOW",
    }

    try:
        from ai_caller import call_ai_json  # type: ignore

        # Truncate to save tokens
        text_snippet = text[:2500]
        prompt = _PROMPT_TEMPLATE.format(
            text=text_snippet,
            company=company or "Unknown",
            doc_type=doc_type or "unknown",
        )

        key = cache_key or f"ling_{hash(text[:150]) % 999_999}"
        result = call_ai_json(prompt, speed="smart", cache_key=key, fallback=_default)

        result.setdefault("linguistic_flags", [])
        result.setdefault("linguistic_penalty", 0)
        result.setdefault("feels_authentic", True)
        result.setdefault("most_suspicious", "None")
        result.setdefault("confidence", "LOW")
        return result

    except Exception as exc:
        logger.error("linguistic_agent error: %s", exc)
        return _default


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    fake_text = """
    Dear Candidate,

    We are pleased to offer you the position of Software Engineer.
    Your salary package will be Rs. 50,00,000 per annum.
    Kindly join us on 1st January 2024.
    We look forward to your joining.

    We are pleased to offer you this great opportunity.

    Regards,
    HR Team
    FakeCorp India
    """

    result = analyze_linguistics(fake_text, "FakeCorp India", "job_offer")
    print(json.dumps(result, indent=2))
    print(f"\nFeels authentic: {result['feels_authentic']}")
    print(f"Flags: {len(result['linguistic_flags'])}")
    print(f"Penalty: {result['linguistic_penalty']}")
    print("\n✅ linguistic_agent.py self-test complete")
