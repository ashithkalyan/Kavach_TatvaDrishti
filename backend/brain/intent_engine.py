"""
KAVACH Brain — Intent Classification
=======================================
Pattern + entity based intent classifier. Deterministic and
extensible: each intent maps to a specific SQL template in
sql_builder.py, so the mapping from "what the officer meant" to "what
query ran" is always inspectable — no black box in between.
"""
import re

INTENT_PATTERNS = [
    ("repeat_offender_search", [r'repeat offend', r'habitual', r'multiple (fir|conviction|case)',
                                 r'appears? in (multiple|several|\d+) fir']),
    ("gang_query", [r'\bgang\b', r'syndicate', r'organi[sz]ed crime']),
    ("network_query", [r'network', r'connect(ed|ion)', r'associat', r'linked to',
                        r'who.*(he|she|they).*(know|linked)', r'phone', r'vehicle.*linked', r'hidden.*link']),
    ("risk_query", [r'risk score', r'high.?risk', r'extreme risk', r'dangerous', r'most wanted']),
    ("prediction_query", [r'forecast', r'predict', r'next month', r'likely to', r'expect.*increase', r'trend.*next']),
    ("similarity_query", [r'similar case', r'linked case', r'same (mo|pattern|method)', r'case linkage']),
    ("statistics_query", [r'how many', r'total (number|count)', r'trend', r'increas', r'decreas',
                           r'compare', r'which (district|station|area).*(highest|most|lowest)']),
    ("case_status_query", [r'status of', r'pending', r'under investigation', r'charge.?sheet', r'closed case']),
    ("timeline_query", [r'timeline', r'investigation (history|progress)', r'what happened (in|to)']),
    ("recommendation_query", [r'what should', r'next steps?', r'leads?', r'recommend']),
    ("person_lookup", [r'\bwho is\b', r'history of', r'profile of', r'tell me about', r'show.*history']),
    ("crime_type_search", [r'\b(murder|theft|robbery|burglary|assault|kidnap|rape|fraud|cyber|drug|dacoity|chain snatching)\b']),
    ("location_search", [r'\bin (bengaluru|bangalore|mysuru|mysore|hubballi|mangaluru|mangalore|belagavi|'
                          r'kalaburagi|davanagere|shivamogga|tumakuru|vijayapura|ballari)\b']),
]

FOLLOW_UP_PREFIXES = re.compile(r'^(only|just|filter|now show|among|from (these|those)|what about)')


def classify(text: str, entities: dict, has_prior_context: bool = False) -> dict:
    t = text.lower().strip()

    if has_prior_context and FOLLOW_UP_PREFIXES.match(t):
        return {"intent": "follow_up_filter", "confidence": 0.85,
                "matched_pattern": "follow-up refinement phrase"}

    for intent, patterns in INTENT_PATTERNS:
        for p in patterns:
            if re.search(p, t):
                return {"intent": intent, "confidence": 0.8, "matched_pattern": p}

    if entities.get("person_name_candidates"):
        return {"intent": "person_lookup", "confidence": 0.5, "matched_pattern": "name detected, no explicit verb"}
    if entities.get("crime_types"):
        return {"intent": "crime_type_search", "confidence": 0.6, "matched_pattern": "crime type detected"}
    return {"intent": "general_search", "confidence": 0.3, "matched_pattern": "no strong signal — recent records"}
