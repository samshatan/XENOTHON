"""
consistency_checker.py — Cross-field logical consistency using AI.

Detects contradictions that are very hard to fake:
  - Joining date before interview date
  - Offer date after joining date
  - HR email domain ≠ company domain
  - Unrealistic salary for role + city
  - Phone area code mismatching city
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────
_PROMPT_TEMPLATE = """
You are a senior document fraud investigator specialising in Indian corporate documents.

Check this document for internal logical consistency.

DOCUMENT TEXT (first 2000 characters):
{text}

ENTITIES EXTRACTED:
{entities_json}

Check ALL of the following:

1. DATE LOGIC
   - Is the joining date BEFORE the interview date? (impossible → flag HIGH)
   - Is the offer/issue date AFTER the joining date? (impossible → flag HIGH)
   - Are any dates in the future relative to a realistic signing date?

2. EMAIL vs COMPANY DOMAIN
   - Does the HR email domain match the company's official domain?
   - e.g. hr@infosys-jobs.com when company is Infosys = FAKE → flag HIGH
   - e.g. hr@infosys.com when company is Infosys = OK

3. SALARY REALISM (India context)
   - Is the offered salary realistic for the stated role + city?
   - Fresher getting 40+ LPA in Tier-2 city = highly suspicious → flag MEDIUM
   - Senior role getting very low salary = suspicious → flag LOW

4. PHONE vs CITY
   - Does the phone area code roughly match the city/location mentioned?

5. REGISTRATION NUMBER CONSISTENCY
   - If a state is mentioned, do CIN/GSTIN state codes match?

Respond ONLY in this exact JSON. No markdown. No backticks. No extra text:
{{"consistency_flags":[{{"issue":"exact description","severity":"HIGH/MEDIUM/LOW"}}],"consistency_penalty":0,"most_suspicious":"one sentence describing the single biggest red flag or None if all looks fine"}}

Rules for consistency_penalty:
- Each HIGH flag: +15 pts
- Each MEDIUM flag: +8 pts
- Each LOW flag: +3 pts
- Cap at 40
""".strip()


# ── Public API ────────────────────────────────────────────────────────────────

def check_consistency(entities: dict[str, Any], text: str) -> dict[str, Any]:
    """
    Use AI to check cross-field logical consistency of a document.

    Args:
        entities: Dict from NER agent (companies, dates, hr_email, etc.)
        text:     Raw OCR text from document.

    Returns:
        {
            "consistency_flags": [...],
            "consistency_penalty": int,
            "most_suspicious": str
        }
    """
    _default = {"consistency_flags": [], "consistency_penalty": 0, "most_suspicious": "None"}

    try:
        from ai_caller import call_ai_json  # type: ignore

        # Limit to 2000 chars to save tokens
        text_snippet = text[:2000].replace("{", "{{").replace("}", "}}")
        entities_json = json.dumps(entities, indent=2, default=str)

        prompt = _PROMPT_TEMPLATE.format(
            text=text_snippet,
            entities_json=entities_json,
        )

        cache_key = f"consistency_{hash(text[:200]) % 999_999}"
        result = call_ai_json(prompt, speed="smart", cache_key=cache_key, fallback=_default)

        # Ensure required keys exist
        result.setdefault("consistency_flags", [])
        result.setdefault("consistency_penalty", 0)
        result.setdefault("most_suspicious", "None")
        return result

    except Exception as exc:
        logger.error("consistency_checker error: %s", exc)
        return _default


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    test_entities = {
        "companies": ["Infosys Limited"],
        "dates": ["Interview: 15 March 2024", "Joining: 1 January 2024"],
        "hr_email": "hr@infosys-recruitment.com",
        "amounts": ["45,00,000 per annum"],
        "role": "Fresher Software Engineer",
        "city": "Guwahati",
    }
    fake_text = (
        "Dear Candidate, We are pleased to offer you the position of "
        "Fresher Software Engineer at Infosys Limited, Guwahati. "
        "Your CTC will be Rs. 45,00,000 per annum. "
        "Joining Date: 1st January 2024. "
        "Interview conducted on: 15th March 2024. "
        "Contact: hr@infosys-recruitment.com"
    )

    result = check_consistency(test_entities, fake_text)
    print(json.dumps(result, indent=2))
    print(f"\nFlags found: {len(result['consistency_flags'])}")
    print(f"Penalty: {result['consistency_penalty']}")
    print("\n✅ consistency_checker.py self-test complete")
