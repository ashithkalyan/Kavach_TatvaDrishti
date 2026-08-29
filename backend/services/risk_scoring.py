"""
KAVACH Risk Scoring Service
Computes criminological risk scores for accused persons.
"""
from typing import Dict, List, Tuple


SEVERITY_MAP = {
    "Murder": 10, "Dacoity": 9, "Rape": 10, "Attempt to Murder": 8,
    "Kidnapping": 8, "Robbery": 7, "Drug Offense": 6, "Assault": 5,
    "Burglary": 5, "Fraud": 5, "Cybercrime": 5, "Domestic Violence": 5,
    "Vehicle Theft": 4, "Chain Snatching": 4, "Theft": 3,
}

RISK_COLORS = {
    "EXTREME": "#C0392B",
    "HIGH":    "#E67E22",
    "MEDIUM":  "#F39C12",
    "LOW":     "#27AE60",
}

RISK_DESCRIPTIONS = {
    "EXTREME": "Immediate action required. Subject poses severe threat to public safety.",
    "HIGH":    "Prioritised surveillance recommended. Active criminal history.",
    "MEDIUM":  "Regular monitoring advised. Moderate criminal background.",
    "LOW":     "Standard monitoring. Limited criminal history.",
}


def compute_risk_score(
    prior_convictions: int,
    crimes_committed: List[str],
    network_size: int,
    active_cases: int,
    years_active: int = 1,
    gang_affiliated: bool = False,
) -> Dict:
    """
    Returns a comprehensive risk assessment dictionary.
    """
    breakdown = {}
    total = 0.0

    # ── Prior Convictions (35 pts) ────────────────────────────────────────────
    conv_score = min(35, prior_convictions * 8)
    breakdown["Prior Convictions"] = {
        "score": conv_score,
        "max": 35,
        "detail": f"{prior_convictions} conviction(s) on record"
    }
    total += conv_score

    # ── Crime Severity (25 pts) ───────────────────────────────────────────────
    if crimes_committed:
        max_severity = max(SEVERITY_MAP.get(c, 3) for c in crimes_committed)
        sev_score = min(25, max_severity * 2.5)
    else:
        sev_score = 0
    top_crime = max(crimes_committed, key=lambda c: SEVERITY_MAP.get(c, 0)) if crimes_committed else "N/A"
    breakdown["Crime Severity"] = {
        "score": round(sev_score, 1),
        "max": 25,
        "detail": f"Highest severity crime: {top_crime}"
    }
    total += sev_score

    # ── Criminal Network (20 pts) ─────────────────────────────────────────────
    net_score = min(20, network_size * 3)
    if gang_affiliated:
        net_score = min(20, net_score + 8)
    breakdown["Criminal Network"] = {
        "score": net_score,
        "max": 20,
        "detail": f"{network_size} known associate(s)" + (" — Gang affiliated" if gang_affiliated else "")
    }
    total += net_score

    # ── Recidivism / Activity (15 pts) ───────────────────────────────────────
    if active_cases > 0 or prior_convictions > 0:
        rec_score = min(15, (active_cases + prior_convictions) * 3)
    else:
        rec_score = 0
    breakdown["Recidivism Risk"] = {
        "score": rec_score,
        "max": 15,
        "detail": f"{active_cases} active case(s), {years_active} year(s) of activity"
    }
    total += rec_score

    # ── Final Score & Category ────────────────────────────────────────────────
    final_score = round(min(100.0, total), 1)

    if final_score >= 80:
        category = "EXTREME"
    elif final_score >= 60:
        category = "HIGH"
    elif final_score >= 35:
        category = "MEDIUM"
    else:
        category = "LOW"

    return {
        "score": final_score,
        "category": category,
        "color": RISK_COLORS[category],
        "description": RISK_DESCRIPTIONS[category],
        "breakdown": breakdown,
        "recommendation": _get_recommendation(category, top_crime if crimes_committed else "N/A", prior_convictions)
    }


def describe_existing_risk(
    risk_score: float,
    risk_category: str,
    prior_convictions: int,
    network_size: int,
    gang_affiliated: bool = False,
) -> Dict:
    """
    Explains an ALREADY-COMPUTED risk score/category (e.g. read straight
    off PersonIdentity or vw_person_flat) in the same {score, category,
    description, breakdown, recommendation} shape compute_risk_score()
    returns for a FRESH computation — used wherever we want to narrate an
    existing figure rather than recompute one from raw inputs. Kept as
    one shared function (instead of the two near-identical inline dicts
    this used to be duplicated as, in main.py's /api/accused/{id} and,
    now, brain/facts_enrichment.py) so the two call sites can never
    silently drift apart.

    Also returns a one-line `headline` — a compact, English-only summary
    meant for the chat brain's LLM-facts payload (see
    facts_enrichment.enrich_person_facts()), not the REST profile
    response, which reads `description`/`breakdown`/`recommendation`
    instead.
    """
    category = risk_category or "LOW"
    prior_component = min(60, prior_convictions * 10)
    network_component = min(20, network_size * 5)

    headline = f"{category} ({risk_score}/100) — driven mainly by {prior_convictions} linked case(s)"
    if network_size:
        headline += f" and {network_size} known associate(s)"
    if gang_affiliated:
        headline += ", gang-affiliated"

    return {
        "score": risk_score,
        "category": category,
        "description": f"{category} risk based on {prior_convictions} linked case(s).",
        "breakdown": {
            "Prior Case Linkage": {"score": prior_component, "max": 60,
                                    "detail": f"{prior_convictions} FIR(s) linked to this identity"},
            "Network": {"score": network_component, "max": 20,
                        "detail": f"{network_size} known associate(s)"},
        },
        "recommendation": (
            "Immediate surveillance recommended." if category == "EXTREME" else
            "Active monitoring recommended." if category == "HIGH" else
            "Standard verification protocol."
        ),
        "headline": headline,
    }


def _get_recommendation(category: str, top_crime: str, prior_convictions: int) -> str:
    recs = {
        "EXTREME": (
            f"Immediate arrest and judicial remand recommended. "
            f"Subject has extensive criminal history involving {top_crime}. "
            f"Ensure no bail without detailed background check. "
            f"Alert neighbouring police stations."
        ),
        "HIGH": (
            f"Active surveillance and regular reporting mandatory. "
            f"Coordinate with local PS for whereabouts tracking. "
            f"Cross-reference with other open cases involving {top_crime}."
        ),
        "MEDIUM": (
            f"Periodic monitoring via assigned beat officer. "
            f"Verify address and employment. "
            f"Document any changes in behaviour pattern."
        ),
        "LOW": (
            f"Standard verification of antecedents. "
            f"Ensure regular appearance for court hearings. "
            f"Community liaison officer to monitor."
        ),
    }
    return recs.get(category, "Standard protocol.")
