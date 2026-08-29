"""
KAVACH Brain — Modus Operandi Fingerprinting
================================================
Turns a case's scattered fields into one compact, comparable "crime
signature" — the same underlying idea real case-linkage analysis uses
to spot serial offenders: compare a small set of concrete tags
(time-of-day, weapon, vehicle, offender count, escape pattern) instead
of eyeballing free-text paragraphs.

    Night · Vehicle: Two-Wheeler · Weapon: Knife · 2 Offender(s) ·
    Motorbike Escape · Chain Snatching

This sits directly on top of similarity_engine.py — MO fingerprints
are what feed the "mo_text" / "weapon" / "vehicle" comparison fields
there, formalised into a first-class, displayable object rather than
being recomputed ad hoc on every comparison.
"""
from . import similarity_engine

_ESCAPE_HINTS = [
    ("Motorbike Escape", ["motorbike", "bike", "two-wheeler"]),
    ("Vehicle Escape", ["car", "vehicle used", "auto"]),
    ("On Foot", ["fled on foot", "ran away"]),
]


def build_signature(case: dict) -> dict:
    """
    case: dict with any of crime_type, weapon, vehicle, time,
          offender_count, mo_text (free-text description)
    """
    tags = []

    time_bucket = similarity_engine._time_bucket(case.get("time"))
    if time_bucket:
        tags.append(time_bucket.title())

    if case.get("crime_type"):
        tags.append(case["crime_type"])

    if case.get("weapon"):
        tags.append(f'Weapon: {case["weapon"]}')

    if case.get("vehicle"):
        tags.append(f'Vehicle: {case["vehicle"]}')

    if case.get("offender_count"):
        tags.append(f'{case["offender_count"]} Offender(s)')

    mo_text = (case.get("mo_text") or "").lower()
    for label, keywords in _ESCAPE_HINTS:
        if any(k in mo_text for k in keywords):
            tags.append(label)
            break

    return {
        "tags": tags,
        "signature_string": " · ".join(tags) if tags else "Insufficient data for a signature",
        "tag_count": len(tags),
    }


def compare_signatures(sig_a: dict, sig_b: dict) -> dict:
    """Jaccard overlap between two tag sets, plus which tags actually matched."""
    a, b = set(sig_a["tags"]), set(sig_b["tags"])
    if not a or not b:
        return {"overlap": 0.0, "shared_tags": []}
    shared = sorted(a & b)
    return {"overlap": round(len(a & b) / len(a | b), 3), "shared_tags": shared}


def find_signature_matches(target_sig: dict, candidate_cases: list, id_field: str = "case_id",
                            min_overlap: float = 0.3, top_k: int = 5) -> list:
    """candidate_cases: [{id_field: ..., "signature": {...}}]"""
    scored = []
    for c in candidate_cases:
        cmp = compare_signatures(target_sig, c["signature"])
        if cmp["overlap"] >= min_overlap:
            scored.append({**c, "signature_overlap": cmp["overlap"], "shared_tags": cmp["shared_tags"]})
    scored.sort(key=lambda x: -x["signature_overlap"])
    return scored[:top_k]
