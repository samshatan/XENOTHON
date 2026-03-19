"""
email_verifier.py — Email domain authenticity checker.

Checks:
  1. Does the domain have real MX records (actual mail server)?
  2. Does the domain name match the claimed company name?
  3. Are there suspicious patterns (recruitment, hiring, jobs…)?

Requires: dnspython  (`pip install dnspython`)
"""

from __future__ import annotations

import re
from typing import Any

# ── DNS import (graceful fallback if not installed) ───────────────────────────
try:
    import dns.resolver as _dns_resolver  # type: ignore
    _DNS_AVAILABLE = True
except ImportError:
    _DNS_AVAILABLE = False


# ── Suspicious domain patterns ────────────────────────────────────────────────
_SUSPICIOUS_PATTERNS = [
    r"recruit(ment|ing)?",
    r"hir(ing|e)",
    r"jobs?",
    r"careers?",
    r"hr-india",
    r"noreply",
    r"\d{4}",           # domain ending in year (fake360.com)
    r"official",        # fake-official domains
    r"corporate",
]
_SUSPICIOUS_RE = re.compile(
    "|".join(_SUSPICIOUS_PATTERNS), re.IGNORECASE
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def extract_email_from_text(text: str) -> str:
    """Return first email address found in text, or empty string."""
    match = re.search(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text
    )
    return match.group(0) if match else ""


def _has_mx_records(domain: str) -> bool:
    """Return True if domain has at least one MX record."""
    if not _DNS_AVAILABLE:
        return True  # can't check — assume OK so we don't false-positive
    try:
        answers = _dns_resolver.resolve(domain, "MX", lifetime=5)
        return bool(answers)
    except Exception:
        return False


def _domain_matches_company(domain: str, company: str) -> bool:
    """
    Rough check: do any significant words from the company name
    appear in the email domain?
    """
    stop = {"ltd", "limited", "pvt", "private", "inc", "corp", "llp", "india"}
    words = [
        w.lower() for w in company.replace(".", " ").split()
        if len(w) > 3 and w.lower() not in stop
    ]
    domain_lower = domain.lower()
    return any(w in domain_lower for w in words)


# ── Public API ────────────────────────────────────────────────────────────────

def verify_email_domain(email: str, company_name: str) -> dict[str, Any]:
    """
    Verify whether an email address looks legitimate for the claimed company.

    Returns:
        {
          "email_penalty": int (0-30),
          "flags": [...],
          "domain": str,
          "email": str
        }
    """
    flags: list[dict] = []
    penalty = 0

    if not email:
        return {"email_penalty": 5, "flags": [], "domain": "", "email": ""}

    domain = email.split("@")[-1].lower() if "@" in email else ""

    # Check 1 — MX records
    if domain and not _has_mx_records(domain):
        flags.append({
            "issue": f"Email domain '{domain}' has no mail server (no MX records) — domain likely fake",
            "severity": "HIGH",
        })
        penalty += 20

    # Check 2 — Domain matches company
    if company_name and domain and not _domain_matches_company(domain, company_name):
        flags.append({
            "issue": (
                f"HR email '{email}' domain does not match company '{company_name}' — "
                "common sign of phishing/fake offer"
            ),
            "severity": "HIGH",
        })
        penalty += 15

    # Check 3 — Suspicious pattern
    if domain and _SUSPICIOUS_RE.search(domain):
        flags.append({
            "issue": f"Email domain '{domain}' contains a suspicious keyword — often used in fake HR emails",
            "severity": "MEDIUM",
        })
        penalty += 10

    return {
        "email_penalty": min(penalty, 30),
        "flags": flags,
        "domain": domain,
        "email": email,
    }


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    print("Test 1 — suspicious fake email domain:")
    r1 = verify_email_domain("hr@infosys-recruitment.com", "Infosys Limited")
    print(json.dumps(r1, indent=2))
    assert r1["email_penalty"] > 15, f"Expected >15, got {r1['email_penalty']}"

    print("\nTest 2 — matching domain:")
    r2 = verify_email_domain("hr@infosys.com", "Infosys Limited")
    print(json.dumps(r2, indent=2))
    assert r2["email_penalty"] < 10, f"Expected <10, got {r2['email_penalty']}"

    print("\nTest 3 — email extraction:")
    text = "Please contact hr@fakecorp-india.com for further details."
    email = extract_email_from_text(text)
    assert email == "hr@fakecorp-india.com", f"Extracted: {email}"
    print(f"Extracted: {email} ✅")

    print("\n✅ email_verifier.py self-test passed")
