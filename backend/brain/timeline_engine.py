"""
KAVACH Brain — Automated Investigation Timeline
===================================================
Turns a flat list of investigation-update notes into the canonical
staged pipeline investigators actually think in:

  FIR Registered -> Statement Recorded -> Evidence Collected ->
  Suspect Identified -> Suspect Arrested -> Charge Sheet Filed ->
  Court Hearing -> Case Closed

Stage classification is keyword-based against the free-text update —
simple, deterministic, and easy to extend. Crucially, it also reports
which canonical stages are MISSING from a case's history — that gap
list is what feeds the Recommendation Engine's urgent leads.
"""

CANONICAL_STAGES = [
    "FIR Registered",
    "Victim/Witness Statement Recorded",
    "Scene of Crime / Evidence Collected",
    "Suspect Identified",
    "Suspect Arrested",
    "Charge Sheet Filed",
    "Court Hearing",
    "Case Closed",
]

_STAGE_KEYWORDS = {
    "Victim/Witness Statement Recorded": ["statement recorded", "witness statement", "victim's medical"],
    "Scene of Crime / Evidence Collected": ["scene of crime", "cctv", "fingerprint", "fsl report",
                                             "evidence", "seized", "malkhana"],
    "Suspect Identified": ["suspect identified", "look-out notice", "additional accused identified"],
    "Suspect Arrested": ["arrest", "remand", "custody"],
    "Charge Sheet Filed": ["charge sheet", "chargesheet", "committed to"],
    "Court Hearing": ["court", "bail", "hearing"],
    "Case Closed": ["closed", "final report", "acquit", "convict", "undetected"],
}


def classify_stage(update_text: str) -> str:
    t = update_text.lower()
    for stage, keywords in _STAGE_KEYWORDS.items():
        if any(k in t for k in keywords):
            return stage
    return "Investigation Update"


def build_timeline(updates: list, fir_registered_date: str) -> list:
    """
    updates: [{"update_date":..., "update_text":..., "officer_name":...}, ...]
    Returns a chronologically ordered, stage-tagged timeline, with FIR
    registration itself included as the first stage.
    """
    timeline = [{
        "date": fir_registered_date,
        "stage": "FIR Registered",
        "text": "FIR registered and investigation opened.",
        "officer": None,
    }]
    for u in updates:
        timeline.append({
            "date": u["update_date"],
            "stage": classify_stage(u["update_text"]),
            "text": u["update_text"],
            "officer": u.get("officer_name"),
        })
    timeline.sort(key=lambda x: x["date"])
    return timeline


def timeline_completeness(timeline: list) -> dict:
    """Which canonical stages are present / missing for this case —
    a direct, explainable input to the Recommendation Engine."""
    present = {t["stage"] for t in timeline}
    missing = [s for s in CANONICAL_STAGES if s not in present]
    ordered_present = sorted(
        present & set(CANONICAL_STAGES),
        key=lambda s: CANONICAL_STAGES.index(s),
    )
    return {
        "stages_present": ordered_present,
        "stages_missing": missing,
        "completeness_pct": round(
            100 * (len(CANONICAL_STAGES) - len(missing)) / len(CANONICAL_STAGES), 1
        ),
    }
