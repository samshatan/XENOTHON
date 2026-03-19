"""
govt_verifier.py — GSTIN and CIN format validation.

Uses Indian government registration number formats to detect fabricated IDs.
No API calls needed — pure regex + format rules.

GSTIN: 2-digit state code + 5 letters + 4 digits + 1 letter + 1 alphanumeric + Z + 1 alphanumeric
CIN:   U or L + 5 digits + 2-letter state code + 4 digits + 3 letters + 6 digits
"""

from __future__ import annotations

import re
from typing import Any

# ── Indian State Codes ────────────────────────────────────────────────────────
# GSTIN numeric state code → state abbreviation
GSTIN_STATE_CODES: dict[str, str] = {
    "01": "JK", "02": "HP", "03": "PB", "04": "CH", "05": "UT",
    "06": "HR", "07": "DL", "08": "RJ", "09": "UP", "10": "BR",
    "11": "SK", "12": "AR", "13": "NL", "14": "MN", "15": "MI",
    "16": "TR", "17": "ML", "18": "AS", "19": "WB", "20": "JH",
    "21": "OD", "22": "CG", "23": "MP", "24": "GJ", "27": "MH",
    "29": "KA", "30": "GA", "32": "KL", "33": "TN", "36": "TG",
    "37": "AP", "97": "OT",
}

# CIN 2-letter state code → state name (for mismatch detection)
CIN_STATE_CODES: set[str] = {
    "JK", "HP", "PB", "CH", "UT", "HR", "DL", "RJ", "UP", "BR",
    "SK", "AR", "NL", "MN", "MI", "TR", "ML", "AS", "WB", "JH",
    "OD", "CG", "MP", "GJ", "MH", "KA", "GA", "KL", "TN", "TG", "AP",
}

# ── GSTIN Validation ──────────────────────────────────────────────────────────
_GSTIN_PATTERN = re.compile(
    r"^\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}Z[A-Z\d]{1}$"
)


def validate_gstin_format(gstin: str) -> dict[str, Any]:
    """
    Validate GSTIN format and state code.

    Returns dict with penalty (0 = valid, >0 = suspicious/invalid).
    """
    gstin = gstin.strip().upper()

    if not _GSTIN_PATTERN.match(gstin):
        return {
            "penalty": 25,
            "valid_format": False,
            "flag": f"Invalid GSTIN format '{gstin}' — does not match required pattern",
        }

    state_code = gstin[:2]
    if state_code not in GSTIN_STATE_CODES:
        return {
            "penalty": 20,
            "valid_format": False,
            "flag": f"GSTIN '{gstin}' has invalid state code '{state_code}'",
        }

    return {
        "penalty": 0,
        "valid_format": True,
        "state": GSTIN_STATE_CODES[state_code],
        "gstin": gstin,
    }


# ── CIN Validation ────────────────────────────────────────────────────────────
_CIN_PATTERN = re.compile(
    r"^[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}$"
)


def validate_cin_format(cin: str) -> dict[str, Any]:
    """
    Validate CIN format and embedded state code.
    """
    cin = cin.strip().upper()

    if not _CIN_PATTERN.match(cin):
        return {
            "penalty": 30,
            "valid_format": False,
            "flag": f"Invalid CIN format '{cin}' — likely fabricated",
        }

    state_code = cin[6:8]
    if state_code not in CIN_STATE_CODES:
        return {
            "penalty": 20,
            "valid_format": False,
            "flag": f"CIN '{cin}' has unrecognised state code '{state_code}'",
        }

    return {
        "penalty": 0,
        "valid_format": True,
        "state": state_code,
        "cin": cin,
    }


# ── Cross-verification ────────────────────────────────────────────────────────

def cross_verify_ids(entities: dict[str, Any]) -> dict[str, Any]:
    """
    Validate all GSTINs and CINs found in extracted entities.
    Also cross-checks that GSTIN state matches CIN state.

    Args:
        entities: dict from NER agent containing 'gstin' and 'cin' lists.

    Returns:
        {"govt_penalty": int, "govt_flags": [...]}
    """
    flags: list[dict] = []
    total_penalty = 0

    gstin_states: list[str] = []
    cin_states: list[str] = []

    # Validate each GSTIN
    for gstin in entities.get("gstin", []):
        result = validate_gstin_format(str(gstin))
        if result["penalty"] > 0:
            flags.append({
                "issue": result.get("flag", "Invalid GSTIN"),
                "severity": "HIGH",
            })
            total_penalty += result["penalty"]
        elif result.get("state"):
            gstin_states.append(result["state"])

    # Validate each CIN
    for cin in entities.get("cin", []):
        result = validate_cin_format(str(cin))
        if result["penalty"] > 0:
            flags.append({
                "issue": result.get("flag", "Invalid CIN"),
                "severity": "HIGH",
            })
            total_penalty += result["penalty"]
        elif result.get("state"):
            cin_states.append(result["state"])

    # Cross-check: GSTIN state vs CIN state
    if gstin_states and cin_states:
        if not set(gstin_states) & set(cin_states):
            flags.append({
                "issue": (
                    f"State mismatch: GSTIN indicates {gstin_states} "
                    f"but CIN indicates {cin_states} — "
                    "registration numbers belong to different states"
                ),
                "severity": "HIGH",
            })
            total_penalty += 20

    return {
        "govt_penalty": min(total_penalty, 50),
        "govt_flags": flags,
    }


# ── Self-test ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json

    print("Test 1 — invalid GSTIN:")
    r1 = validate_gstin_format("INVALIDGSTIN123")
    print(json.dumps(r1, indent=2))
    assert r1["penalty"] > 0

    print("\nTest 2 — valid GSTIN (Maharashtra):")
    r2 = validate_gstin_format("27AABCU9603R1ZX")
    print(json.dumps(r2, indent=2))
    assert r2["penalty"] == 0
    assert r2["state"] == "MH"

    print("\nTest 3 — invalid CIN:")
    r3 = validate_cin_format("FAKECIN12345")
    print(json.dumps(r3, indent=2))
    assert r3["penalty"] > 0

    print("\nTest 4 — cross_verify with invalid IDs:")
    r4 = cross_verify_ids({"gstin": ["INVALIDGSTIN"], "cin": ["FAKECIN"]})
    print(json.dumps(r4, indent=2))
    assert r4["govt_penalty"] > 30

    print("\n✅ govt_verifier.py self-test passed")
