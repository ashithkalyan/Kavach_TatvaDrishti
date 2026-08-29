"""
KAVACH Brain — Crime Similarity / Case-Linkage Engine
=========================================================
A real forensic technique — criminologists call this "case linkage
analysis": comparing a case's features against historical cases to
surface likely-linked crimes, used to identify serial offenders and
organised patterns before anyone has explicitly connected the dots.

Weighted feature similarity, entirely local computation — no external
API, no training data required:
  - Categorical feature overlap: crime type, weapon, vehicle type,
    police station, time-of-day bucket
  - MO free-text similarity via the same self-built TF/cosine engine
    used by memory_engine.py

This scales to whatever case volume actually exists — the same code
runs against 500 synthetic demo records or, with a database index on
the categorical columns, against a real multi-million-record archive.
At demo scale it does a full scan in well under a second.
"""
from . import memory_engine

FEATURE_WEIGHTS = {
    "crime_type": 0.25,
    "weapon": 0.15,
    "vehicle": 0.10,
    "time_bucket": 0.10,
    "police_station": 0.10,
    "mo_text": 0.30,
}


def _time_bucket(time_str):
    if not time_str:
        return None
    try:
        h = int(str(time_str).split(":")[0])
    except (ValueError, IndexError):
        return None
    if 5 <= h < 12:
        return "morning"
    if 12 <= h < 17:
        return "afternoon"
    if 17 <= h < 21:
        return "evening"
    return "night"


def compute_similarity(case_a: dict, case_b: dict) -> dict:
    """
    Each case dict expected keys (any may be missing/None):
      crime_type, weapon, vehicle, time, police_station, mo_text
    """
    score = 0.0
    reasons = []

    if case_a.get("crime_type") and case_a["crime_type"] == case_b.get("crime_type"):
        score += FEATURE_WEIGHTS["crime_type"]
        reasons.append({"factor": "Same crime type", "detail": case_a["crime_type"],
                         "weight": FEATURE_WEIGHTS["crime_type"]})

    if case_a.get("weapon") and case_a["weapon"] == case_b.get("weapon"):
        score += FEATURE_WEIGHTS["weapon"]
        reasons.append({"factor": "Same weapon used", "detail": case_a["weapon"],
                         "weight": FEATURE_WEIGHTS["weapon"]})

    if case_a.get("vehicle") and case_a["vehicle"] == case_b.get("vehicle"):
        score += FEATURE_WEIGHTS["vehicle"]
        reasons.append({"factor": "Same vehicle type", "detail": case_a["vehicle"],
                         "weight": FEATURE_WEIGHTS["vehicle"]})

    tb_a, tb_b = _time_bucket(case_a.get("time")), _time_bucket(case_b.get("time"))
    if tb_a and tb_a == tb_b:
        score += FEATURE_WEIGHTS["time_bucket"]
        reasons.append({"factor": "Same time-of-day pattern", "detail": tb_a,
                         "weight": FEATURE_WEIGHTS["time_bucket"]})

    if case_a.get("police_station") and case_a["police_station"] == case_b.get("police_station"):
        score += FEATURE_WEIGHTS["police_station"]
        reasons.append({"factor": "Same police station jurisdiction",
                         "detail": case_a["police_station"], "weight": FEATURE_WEIGHTS["police_station"]})

    mo_a, mo_b = case_a.get("mo_text") or "", case_b.get("mo_text") or ""
    if mo_a and mo_b:
        v1 = memory_engine._tf_vector(memory_engine.tokenize(mo_a))
        v2 = memory_engine._tf_vector(memory_engine.tokenize(mo_b))
        mo_sim = memory_engine._cosine_sim(v1, v2)
        if mo_sim > 0.12:
            contrib = FEATURE_WEIGHTS["mo_text"] * mo_sim
            score += contrib
            reasons.append({"factor": "Similar MO / case description",
                             "detail": f"{int(mo_sim * 100)}% text overlap",
                             "weight": round(contrib, 3)})

    return {"score": round(min(score, 1.0) * 100, 1), "reasons": reasons}


def find_similar_cases(target_case: dict, candidate_cases: list, top_k: int = 5,
                        min_score: float = 25.0) -> list:
    """
    target_case / each item in candidate_cases: dict with a unique
    "case_id" plus the comparison fields used above.
    """
    scored = []
    for c in candidate_cases:
        if c.get("case_id") == target_case.get("case_id"):
            continue
        result = compute_similarity(target_case, c)
        if result["score"] >= min_score:
            scored.append({**c, "similarity_score": result["score"], "match_reasons": result["reasons"]})
    scored.sort(key=lambda x: -x["similarity_score"])
    return scored[:top_k]
