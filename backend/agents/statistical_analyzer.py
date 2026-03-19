"""
statistical_analyzer.py — Pure-Python statistical anomaly detection.

Checks for:
  - Suspiciously round salary figures
  - Unprofessional punctuation (exclamation marks, ALL CAPS)
  - Mixed date formats (copy-paste artifact)
  - Duplicate 5-word phrases
  - Double-space editing artifacts
  - Invalid Indian phone numbers

No AI API calls — instant, zero cost, always available.
"""

from __future__ import annotations

import re
from typing import Any


# ── Helpers ──────────────────────────────────────────────────────────────────

def _flag(issue: str, severity: str) -> dict[str, str]:
    return {"issue": issue, "severity": severity}


# ── Individual checks ────────────────────────────────────────────────────────

def _check_round_salaries(text: str, doc_type: str) -> tuple[list, int]:
    flags, penalty = [], 0
    pattern = r"(?:rs\.?|inr|₹)\s*([\d,]+)"
    for match in re.finditer(pattern, text, re.IGNORECASE):
        raw = match.group(1).replace(",", "")
        try:
            amount = int(raw)
        except ValueError:
            continue
        if amount > 10_000 and amount % 10_000 == 0:
            flags.append(_flag(
                f"Salary ₹{match.group(1)} is suspiciously round — "
                "real offers use odd figures like ₹47,500",
                "LOW"
            ))
            penalty += 5
        if doc_type == "job_offer" and amount > 5_000_000:
            flags.append(_flag(
                f"Salary ₹{match.group(1)} is extremely high — verify carefully",
                "MEDIUM"
            ))
            penalty += 8
    return flags, penalty


def _check_punctuation(text: str) -> tuple[list, int]:
    flags, penalty = [], 0
    if text.count("!") > 2:
        flags.append(_flag(
            f"Excessive exclamation marks ({text.count('!')}) — unprofessional for corporate documents",
            "MEDIUM"
        ))
        penalty += 8
    caps_words = re.findall(r"\b[A-Z]{4,}\b", text)
    if len(caps_words) > 10:
        flags.append(_flag(
            f"{len(caps_words)} ALL-CAPS words found — unusual for professional documents",
            "LOW"
        ))
        penalty += 5
    return flags, penalty


def _check_date_formats(text: str) -> tuple[list, int]:
    flags, penalty = [], 0
    formats_found: set[str] = set()
    checks = [
        (r"\d{2}/\d{2}/\d{4}", "DD/MM/YYYY"),
        (r"\d{2}-\d{2}-\d{4}", "DD-MM-YYYY"),
        (r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s+\d{4}", "Month DD YYYY"),
        (r"\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)", "DD Month YYYY"),
    ]
    for pattern, label in checks:
        if re.search(pattern, text, re.IGNORECASE):
            formats_found.add(label)
    if len(formats_found) > 1:
        flags.append(_flag(
            f"Multiple date formats detected {formats_found} — "
            "indicates copy-pasted content from different sources",
            "MEDIUM"
        ))
        penalty += 12
    return flags, penalty


def _check_duplicate_phrases(text: str) -> tuple[list, int]:
    flags, penalty = [], 0
    words = text.lower().split()
    seen: dict[str, int] = {}
    for i in range(len(words) - 4):
        phrase = " ".join(words[i : i + 5])
        # Skip trivial phrases (all stopwords)
        if len(set(phrase.split()) - {"the", "a", "an", "in", "of", "to", "and", "is", "are", "was"}) < 3:
            continue
        if phrase in seen and seen[phrase] != i:
            flags.append(_flag(
                f"Duplicate phrase detected: '{phrase[:60]}…' — copy-paste artifact",
                "HIGH"
            ))
            penalty += 15
            break  # one flag is enough
        seen[phrase] = i
    return flags, penalty


def _check_double_spaces(text: str) -> tuple[list, int]:
    flags, penalty = [], 0
    count = text.count("  ")
    if count > 5:
        flags.append(_flag(
            f"{count} double-space sequences found — common sign of text editing/replacement",
            "LOW"
        ))
        penalty += 5
    return flags, penalty


def _check_phone_numbers(text: str) -> tuple[list, int]:
    flags, penalty = [], 0
    phones = re.findall(r"\b(\d[\d\s\-]{8,11}\d)\b", text)
    for phone in phones:
        digits = re.sub(r"\D", "", phone)
        if len(digits) == 10 and digits[0] not in "6789":
            flags.append(_flag(
                f"Phone number {phone} doesn't start with 6-9 — invalid Indian mobile number",
                "MEDIUM"
            ))
            penalty += 8
            break
    return flags, penalty


# ── Public API ───────────────────────────────────────────────────────────────

def detect_statistical_anomalies(text: str, doc_type: str = "unknown") -> dict[str, Any]:
    """
    Run all statistical checks against document text.

    Returns:
        {
          "stat_flags": [...],
          "stat_penalty": int,
          "checks_run": 6,
          "anomalies_found": int
        }
    """
    all_flags: list[dict] = []
    total_penalty = 0

    for check_fn, args in [
        (_check_round_salaries,  (text, doc_type)),
        (_check_punctuation,     (text,)),
        (_check_date_formats,    (text,)),
        (_check_duplicate_phrases, (text,)),
        (_check_double_spaces,   (text,)),
        (_check_phone_numbers,   (text,)),
    ]:
        try:
            f, p = check_fn(*args)  # type: ignore[call-arg]
            all_flags.extend(f)
            total_penalty += p
        except Exception:
            pass  # never crash the pipeline

    return {
        "stat_flags": all_flags,
        "stat_penalty": min(total_penalty, 40),  # cap at 40 pts
        "checks_run": 6,
        "anomalies_found": len(all_flags),
    }


# ── Self-test ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    sample_text = """
    Dear Candidate,

    We are pleased to offer you the position at FakeCorp!!!!
    Your salary will be Rs. 50,00,000 per annum.

    Interview Date: 15/03/2024
    Joining Date: 1st March 2024

    We are pleased to offer you this opportunity to join our team.

    Contact us at: +91 5123456789
    """

    result = detect_statistical_anomalies(sample_text, "job_offer")
    import json
    print(json.dumps(result, indent=2))
    assert result["anomalies_found"] >= 2, "Expected at least 2 anomalies"
    assert result["stat_penalty"] >= 10, "Expected penalty >= 10"
    print("\n✅ statistical_analyzer.py self-test passed")
