"""
KAVACH Brain — Explainability / Audit Reasoning Trace
=========================================================
Every time KAVACH draws an inference (same suspect detected, cases
linked, network connection surfaced, forecast produced), it should be
able to show its exact working — not necessarily on the main chat
bubble every time, but always available for audit. This module builds
that structured trace.

This is what separates "the AI said so" from "the AI said so, and
here is exactly which four data points led there, and how much each
one contributed" — which is the difference between a black box and a
tool a police department can actually stand behind in court.
"""

STANDARD_IDENTITY_FACTORS = [
    "name_similarity",
    "father_or_spouse_name_match",
    "age_consistency",
    "district_match",
    "phone_match",
    "vehicle_match",
    "fingerprint_match",
    "location_overlap",
]

# Factors we genuinely compute vs. factors that are integration stubs —
# being explicit about this distinction IS the honesty the trace exists for.
_COMPUTABLE_FACTORS = {
    "name_similarity", "father_or_spouse_name_match", "age_consistency",
    "district_match", "phone_match", "vehicle_match", "location_overlap",
}
_STUB_FACTORS = {
    "fingerprint_match": "Requires integration with KSP's AFIS system — not computed by KAVACH.",
}


def factor(name: str, status: str, weight: float = 0.0, detail: str = ""):
    """status: 'match' | 'no_match' | 'not_available'"""
    if name in _STUB_FACTORS and status != "not_available":
        # guard against ever accidentally claiming a stub factor "matched"
        status = "not_available"
        detail = _STUB_FACTORS[name]
    return {"factor": name, "status": status, "weight": weight, "detail": detail}


def build_trace(conclusion: str, factors: list) -> dict:
    """
    factors: list of dicts produced by factor() above.
    Confidence is derived ONLY from factors actually computed (status
    'match' or 'no_match') — 'not_available' factors are excluded from
    the confidence math and listed separately, so a missing biometric
    check can never silently inflate or deflate a score.
    """
    computed = [f for f in factors if f["status"] != "not_available"]
    unavailable = [f for f in factors if f["status"] == "not_available"]

    matched_weight = sum(f["weight"] for f in computed if f["status"] == "match")
    total_weight = sum(f["weight"] for f in computed) or 1.0
    confidence = round(matched_weight / total_weight, 3) if total_weight else 0.0

    return {
        "conclusion": conclusion,
        "confidence": confidence,
        "confidence_pct": f"{round(confidence * 100)}%",
        "factors_matched": [f for f in computed if f["status"] == "match"],
        "factors_not_matched": [f for f in computed if f["status"] == "no_match"],
        "factors_unavailable": unavailable,
        "factor_coverage": f"{len(computed)}/{len(factors)} factors computed",
    }


def summarise_for_officer(trace: dict) -> str:
    """Short, plain-language version for the chat bubble — the full
    trace stays available via the API for anyone who wants to audit it."""
    matched = [f["factor"].replace("_", " ") for f in trace["factors_matched"]]
    if not matched:
        return f"{trace['conclusion']} — confidence {trace['confidence_pct']} (no strong corroborating factors)."
    reasons = ", ".join(matched[:3])
    more = f" (+{len(matched) - 3} more)" if len(matched) > 3 else ""
    return f"{trace['conclusion']} — confidence {trace['confidence_pct']}, based on: {reasons}{more}."
