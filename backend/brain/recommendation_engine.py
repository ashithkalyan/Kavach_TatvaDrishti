"""
KAVACH Brain — Investigator Recommendation Engine
=====================================================
Turns "this case is similar to that one" into a concrete, prioritised
checklist of investigative leads — this is what actually satisfies the
challenge's Investigator Decision Support requirement, rather than
just surfacing a similarity score and leaving the officer to figure
out what to do with it.

Deterministic rule set: crime-type-specific leads + gap-driven leads
(pulled straight from timeline_engine's missing-stage output) +
network-driven leads (pulled from graph_engine's discovered
connections). Every recommendation states WHY it's being suggested —
consistent with the rest of KAVACH's explainability posture.

Every lead now carries a stable `key` (crime-type-scoped) — added so
feedback_engine.py can track a lead's real-world usefulness over many
different cases of the same crime type, not just show a static
checklist forever. See recommend_leads_with_stats() below for where
that history gets attached back onto the checklist.
"""

CRIME_TYPE_LEADS = {
    "Vehicle Theft": [
        {"key": "toll_fastag_cctv", "lead": "Check nearby toll booth CCTV / FASTag logs for the vehicle's plate"},
        {"key": "petrol_pump_cctv", "lead": "Check petrol pump CCTV within 2 km of the theft location"},
        {"key": "chop_shop_intel", "lead": "Cross-reference vehicle chop-shop / spare-parts market intelligence"},
        {"key": "prior_mo_match", "lead": "Check for prior vehicle-theft FIRs with a matching MO signature"},
    ],
    "Chain Snatching": [
        {"key": "pawn_shop_check", "lead": "Check jewellery pawn shops within the district for the stolen item"},
        {"key": "atm_bank_cctv", "lead": "Check nearby ATM / bank CCTV for the getaway vehicle"},
        {"key": "known_offenders", "lead": "Cross-reference known chain-snatching offenders active in the area"},
    ],
    "Cybercrime": [
        {"key": "cdr_request", "lead": "Request Call Detail Records (CDR) for the fraudulent number"},
        {"key": "upi_trace", "lead": "Trace the UPI / bank transaction chain to the receiving account"},
        {"key": "mule_account_check", "lead": "Check whether the receiving (mule) account has appeared in other cybercrime FIRs"},
    ],
    "Robbery": [
        {"key": "scene_escape_cctv", "lead": "Check CCTV at the scene and along likely escape routes"},
        {"key": "associate_crossref", "lead": "Cross-reference known associates of any already-identified suspect"},
        {"key": "pawn_secondhand_check", "lead": "Check pawn shops / second-hand markets for stolen items"},
    ],
    "Dacoity": [
        {"key": "gang_mo_crossdistrict", "lead": "Check for organised-gang MO signature matches across districts"},
        {"key": "weapon_procurement_intel", "lead": "Check firearms/weapon procurement intelligence if a firearm was used"},
    ],
    "Drug Offense": [
        {"key": "informant_network", "lead": "Check informant network for supply-chain intelligence"},
        {"key": "known_peddling_locations", "lead": "Cross-reference known drug-peddling locations nearby"},
        {"key": "contact_call_records", "lead": "Request call records for identified contacts"},
    ],
    "Burglary": [
        {"key": "fingerprint_fsl", "lead": "Lift fingerprints at the entry point and forward to FSL"},
        {"key": "loitering_cctv", "lead": "Check nearby CCTV for suspicious loitering before the incident"},
        {"key": "burglary_mo_crossref", "lead": "Cross-reference known burglary MO signatures in the district"},
    ],
    "Murder": [
        {"key": "fsl_weapon_report", "lead": "Request FSL report on any weapon/forensic evidence recovered"},
        {"key": "victim_movements", "lead": "Map victim's last-known movements and contacts"},
        {"key": "victim_cdr", "lead": "Check CDR for the victim's phone in the hours before the incident"},
    ],
}

GENERIC_LEADS = [
    {"key": "accused_call_records", "lead": "Check the accused's phone for call records around the time of the incident"},
    {"key": "accused_prior_addresses", "lead": "Verify the accused's known previous addresses"},
    {"key": "accused_prior_vehicles", "lead": "Check for previously used vehicles linked to the accused"},
    {"key": "network_associates", "lead": "Cross-reference known associates via the criminal network graph"},
]

# Stable keys for the gap-driven / network-driven leads built dynamically
# in recommend_leads() below (not table-driven like the two lists above,
# since their TEXT varies per case — e.g. includes a live count — but
# their KEY must stay fixed so feedback aggregates correctly across
# different cases).
_GAP_EVIDENCE_KEY = "gap_no_evidence_collected"
_GAP_NETWORK_SUSPECT_KEY = "gap_network_suspect_candidate"
_GAP_STATEMENT_KEY = "gap_no_witness_statement"


def recommend_leads(case: dict, timeline_gaps: list = None, network_hit_count: int = 0) -> list:
    """
    case: dict with at least crime_type
    timeline_gaps: list of missing stage names from timeline_engine.timeline_completeness()
    network_hit_count: number of associates surfaced by graph_engine for this case's accused

    Returns [{"key", "lead", "priority", "reason"}, ...] — `key` is
    scoped to (crime_type, key) for the table-driven leads, and is
    already globally distinct for the three gap-driven leads (their
    text can vary per case, e.g. embeds a live count, but the key never
    does) — see feedback_engine.py for how this is used.
    """
    leads = []
    crime_type = case.get("crime_type")

    for entry in CRIME_TYPE_LEADS.get(crime_type, []):
        leads.append({"key": entry["key"], "lead": entry["lead"], "priority": "high",
                       "reason": f"Standard lead for {crime_type} cases"})

    if timeline_gaps:
        if "Scene of Crime / Evidence Collected" in timeline_gaps:
            leads.append({
                "key": _GAP_EVIDENCE_KEY,
                "lead": "No evidence-collection stage on record — revisit scene and pull CCTV before footage is overwritten",
                "priority": "urgent", "reason": "Investigation timeline gap",
            })
        if "Suspect Identified" in timeline_gaps and network_hit_count > 0:
            leads.append({
                "key": _GAP_NETWORK_SUSPECT_KEY,
                "lead": f"{network_hit_count} known associate(s) surfaced by network analysis — review as potential suspects",
                "priority": "high", "reason": "Network graph match exists but no suspect is on record yet",
            })
        if "Victim/Witness Statement Recorded" in timeline_gaps:
            leads.append({
                "key": _GAP_STATEMENT_KEY,
                "lead": "Victim/witness statement not yet on record — schedule promptly, memory degrades fast",
                "priority": "urgent", "reason": "Investigation timeline gap",
            })

    for entry in GENERIC_LEADS:
        leads.append({"key": entry["key"], "lead": entry["lead"], "priority": "standard",
                       "reason": "General investigative checklist"})

    priority_order = {"urgent": 0, "high": 1, "standard": 2}
    leads.sort(key=lambda x: priority_order.get(x["priority"], 9))
    return leads


def recommend_leads_with_stats(conn, case: dict, timeline_gaps: list = None, network_hit_count: int = 0) -> list:
    """
    Same leads as recommend_leads(), each now also carrying its
    historical track record (see feedback_engine.lead_stats()) — how
    many times officers have marked THIS lead type useful vs not, for
    THIS crime type, across every case it's ever been suggested on.

    Within each priority tier (urgent/high/standard is never reordered
    — a timeline gap stays urgent regardless of feedback), leads with a
    proven track record are moved earlier than leads with a worse one.
    A lead with NO feedback yet is treated as neutral (kept in its
    original position, neither boosted nor buried) rather than assumed
    good or bad — there simply isn't evidence yet, which is different
    from evidence that it doesn't work.
    """
    from . import feedback_engine  # local import avoids a hard dependency for callers that don't need it

    leads = recommend_leads(case, timeline_gaps=timeline_gaps, network_hit_count=network_hit_count)
    crime_type = case.get("crime_type")
    for lead in leads:
        lead["feedback"] = feedback_engine.lead_stats(conn, crime_type, lead["key"])

    priority_order = {"urgent": 0, "high": 1, "standard": 2}

    def sort_key(lead):
        rate = lead["feedback"]["useful_rate_pct"]
        neutral = 50.0  # no feedback yet — neither boosted nor buried
        return (priority_order.get(lead["priority"], 9), -(rate if rate is not None else neutral))

    leads.sort(key=sort_key)
    return leads
