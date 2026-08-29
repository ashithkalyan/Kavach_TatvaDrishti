"""
KAVACH Brain — Richer Grounding Facts for Conversational Synthesis
=======================================================================
response_generator.build_facts() hands Ollama a flat 5-row sample and a
count — enough to paraphrase a query result, not enough to say anything
an investigator would actually call insight. That's why the polished
replies used to read like "a database summary with nicer punctuation."

This module computes a few EXTRA facts — still 100% deterministic,
still computed in Python — so compose_conversational() has real
material to reason about:

  enrich_person_facts()  — for person_lookup / repeat_offender_search:
                            the top-ranked person's case history, gang
                            context, network size, and a plain-English
                            explanation of WHY their risk score is what
                            it is (reusing services/risk_scoring.py's
                            breakdown logic, not a separate guess).

  enrich_trend_facts()    — for crime_type_search / statistics_query /
                            location_search: a month-over-month trend
                            ("23 this month vs 18 last month, +28%")
                            and a district (or, if already scoped to
                            one district, police-station) breakdown.

Same non-negotiable rule as the rest of this brain: every number here
is computed in Python and handed to the LLM as a fact, never left for
the LLM to work out — see ollama_client.py's module docstring for why.

WHY "MOST RECENT TWO MONTHS PRESENT IN THE DATA" AND NOT "THIS
CALENDAR MONTH": this project's seeded case dates don't line up with
whatever day it happens to be run/demoed on (see
prediction_engine.py's own docstring for the identical reasoning) — a
trend computed against today's real-world calendar would silently read
as "0 cases this month, 0 last month" forever. Anchoring to the latest
two months that actually appear in the (filtered) data keeps this
meaningful regardless of when the demo runs, and reduces to the
literal calendar once real KSP data with current dates is imported.
"""
import sqlite3

from services import risk_scoring


def enrich_person_facts(conn: sqlite3.Connection, person_id, base_facts: dict) -> dict:
    """Adds case_history, crime_type_breakdown, network_size,
    gang_context, and risk_trajectory to base_facts for ONE person.
    Only ever called for the single top-ranked person in the result set
    — the officer is looking at one profile, not asking for a summary
    of thirty people at once."""
    if not person_id:
        return base_facts
    try:
        person_id = int(person_id)
    except (TypeError, ValueError):
        return base_facts

    row = conn.execute(
        "SELECT RiskScore, RiskCategory, GangAffiliation FROM PersonIdentity WHERE PersonIdentityID=?",
        (person_id,),
    ).fetchone()
    if not row:
        return base_facts
    risk_score, risk_category, gang = row

    case_rows = conn.execute("""
        SELECT f.fir_number, f.crime_type, f.registration_date, f.district, f.status
        FROM PersonIdentityLink pil
        JOIN Accused a ON pil.AccusedMasterID = a.AccusedMasterID
        JOIN vw_fir_flat f ON a.CaseMasterID = f.fir_id
        WHERE pil.PersonIdentityID=?
        ORDER BY f.registration_date DESC
    """, (person_id,)).fetchall()
    case_history = [
        {"fir_number": r[0], "crime_type": r[1], "date": r[2], "district": r[3], "status": r[4]}
        for r in case_rows
    ]

    network_size = conn.execute(
        "SELECT COUNT(*) FROM PersonNetworkLink WHERE PersonIdentityID_A=? OR PersonIdentityID_B=?",
        (person_id, person_id),
    ).fetchone()[0]

    crime_type_breakdown = {}
    for c in case_history:
        if c["crime_type"]:
            crime_type_breakdown[c["crime_type"]] = crime_type_breakdown.get(c["crime_type"], 0) + 1

    dates = sorted(c["date"] for c in case_history if c.get("date"))
    if len(dates) >= 2:
        activity_summary = f"{len(dates)} linked case(s) spanning {dates[0]} to {dates[-1]}"
    elif len(dates) == 1:
        activity_summary = f"1 linked case, on {dates[0]}"
    else:
        activity_summary = "No linked cases on file."

    risk_desc = risk_scoring.describe_existing_risk(
        risk_score=risk_score, risk_category=risk_category,
        prior_convictions=len(case_history), network_size=network_size,
        gang_affiliated=bool(gang),
    )

    base_facts["case_history"] = case_history[:8]
    base_facts["case_history_total"] = len(case_history)
    base_facts["crime_type_breakdown"] = crime_type_breakdown
    base_facts["network_size"] = network_size
    base_facts["gang_context"] = gang or None
    base_facts["risk_trajectory"] = {
        "score": risk_score, "category": risk_category,
        "activity_summary": activity_summary,
        "driven_by": risk_desc["headline"],
    }
    return base_facts


def enrich_trend_facts(conn: sqlite3.Connection, entities: dict, base_facts: dict) -> dict:
    """Adds `trend` (month-over-month, see module docstring) and either
    `district_breakdown` or `police_station_breakdown` (whichever is
    more informative given the query's own district filter) to
    base_facts. Used only for crime_type_search / statistics_query /
    location_search — intents where the officer is asking about a
    PATTERN across cases, not one specific record."""
    where, params = ["1=1"], []
    if entities.get("districts"):
        placeholders = ",".join("?" * len(entities["districts"]))
        where.append(f"district IN ({placeholders})")
        params += list(entities["districts"])
    if entities.get("crime_types"):
        placeholders = ",".join("?" * len(entities["crime_types"]))
        where.append(f"crime_type IN ({placeholders})")
        params += list(entities["crime_types"])
    where_sql = " AND ".join(where)

    month_rows = conn.execute(f"""
        SELECT strftime('%Y-%m', registration_date) AS ym, COUNT(*) AS c
        FROM vw_fir_flat WHERE {where_sql} AND registration_date IS NOT NULL
        GROUP BY ym ORDER BY ym DESC LIMIT 2
    """, params).fetchall()

    trend = None
    if len(month_rows) == 2:
        (latest_ym, latest_c), (prev_ym, prev_c) = month_rows
        delta = latest_c - prev_c
        pct = round((delta / prev_c) * 100, 1) if prev_c else None
        trend = {
            "latest_month": latest_ym, "latest_count": latest_c,
            "previous_month": prev_ym, "previous_count": prev_c,
            "delta": delta, "percent_change": pct,
            "direction": "up" if delta > 0 else ("down" if delta < 0 else "flat"),
        }
    elif len(month_rows) == 1:
        trend = {"latest_month": month_rows[0][0], "latest_count": month_rows[0][1],
                  "previous_month": None, "previous_count": None, "delta": None,
                  "percent_change": None, "direction": "insufficient_history"}

    if len(entities.get("districts") or []) == 1:
        rows = conn.execute(f"""
            SELECT police_station, COUNT(*) AS c FROM vw_fir_flat
            WHERE {where_sql} AND police_station IS NOT NULL
            GROUP BY police_station ORDER BY c DESC LIMIT 5
        """, params).fetchall()
        base_facts["police_station_breakdown"] = [{"police_station": r[0], "count": r[1]} for r in rows]
    else:
        rows = conn.execute(f"""
            SELECT district, COUNT(*) AS c FROM vw_fir_flat
            WHERE {where_sql} AND district IS NOT NULL
            GROUP BY district ORDER BY c DESC LIMIT 5
        """, params).fetchall()
        base_facts["district_breakdown"] = [{"district": r[0], "count": r[1]} for r in rows]

    if trend:
        base_facts["trend"] = trend
    return base_facts
