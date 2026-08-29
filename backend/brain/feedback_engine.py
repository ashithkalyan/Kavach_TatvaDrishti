"""
KAVACH Brain — Case Outcome Feedback Loop
=============================================
Closes the OTHER loop this project's recommendation engine never acted
on: KAVACH suggests investigative leads (see recommendation_engine.py),
but until now had no way to know whether an officer actually followed
one, or whether it helped. This module lets an officer record the
outcome of a specific lead on a specific case, and aggregates those
outcomes over time into a per-(crime type, lead) track record:

    KAVACH gives recommendation
            -> officer acts on it
            -> officer records what happened
            -> system remembers the outcome
            -> future recommendations for the SAME crime type show
               "X% of officers found this useful" evidence alongside
               the lead, not just a static checklist

See recommendation_engine.recommend_leads_with_stats() for where this
gets attached back onto the checklist, and where a track record is
also used as a (secondary, priority-tier-respecting) re-ranking signal.

HONESTY NOTE: unlike prediction_tracking.py's backfill (a legitimate
walk-forward backtest against REAL historical case-count data), this
module is NEVER seeded with synthetic feedback — a lead's usefulness on
a real case is an officer's genuine judgement call, not something that
can be honestly fabricated after the fact. It starts empty and grows
only from real feedback, which is the correct, honest state for a
brand-new feature — see lead_stats()'s zero-feedback return shape and
crime_type_summary()'s empty-list return for a crime type nobody has
given feedback on yet.
"""
import sqlite3

VALID_OUTCOMES = {"useful", "not_useful", "inconclusive"}


def init_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS lead_feedback (
            feedback_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            fir_number    TEXT NOT NULL,
            lead_key      TEXT NOT NULL,
            crime_type    TEXT NOT NULL,
            lead_text     TEXT,
            outcome       TEXT NOT NULL,        -- 'useful' | 'not_useful' | 'inconclusive'
            notes         TEXT,
            officer_id    INTEGER,
            recorded_at   TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(fir_number, lead_key)
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_lead_feedback_lookup
        ON lead_feedback (crime_type, lead_key)
    """)
    conn.commit()


def record_feedback(conn: sqlite3.Connection, fir_number: str, lead_key: str, crime_type: str,
                     lead_text: str, outcome: str, officer_id: int = None, notes: str = None) -> dict:
    """
    One feedback record per (fir_number, lead_key) — an officer can
    UPDATE their own earlier judgement on the same case+lead (e.g.
    "inconclusive" now, "useful" once it later pans out), which is why
    this is an upsert rather than prediction_tracking.record_prediction()'s
    "first one wins": a lead's real-world usefulness on a SPECIFIC case
    can genuinely become clearer as the investigation progresses, unlike
    a forecast's target month, which either already happened or didn't.
    """
    outcome = (outcome or "").strip().lower()
    if outcome not in VALID_OUTCOMES:
        return {"success": False, "reason": f"outcome must be one of {sorted(VALID_OUTCOMES)}"}
    if not fir_number or not lead_key or not crime_type:
        return {"success": False, "reason": "fir_number, lead_key, and crime_type are all required"}

    conn.execute("""
        INSERT INTO lead_feedback (fir_number, lead_key, crime_type, lead_text, outcome, notes, officer_id)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(fir_number, lead_key) DO UPDATE SET
            outcome=excluded.outcome, notes=excluded.notes, officer_id=excluded.officer_id,
            lead_text=excluded.lead_text, recorded_at=CURRENT_TIMESTAMP
    """, (fir_number, lead_key, crime_type, lead_text, outcome, notes, officer_id))
    conn.commit()
    return {"success": True}


def lead_stats(conn: sqlite3.Connection, crime_type: str, lead_key: str) -> dict:
    """Historical track record for ONE lead type within one crime type,
    across every case it's ever been given feedback on — what
    recommend_leads_with_stats() attaches to each suggested lead.
    `useful_rate_pct` is None (not 0) until at least one judged
    (useful/not_useful) piece of feedback exists — a lead nobody has
    weighed in on yet is unproven, not "0% useful"."""
    rows = conn.execute(
        "SELECT outcome, COUNT(*) FROM lead_feedback WHERE crime_type=? AND lead_key=? GROUP BY outcome",
        (crime_type, lead_key),
    ).fetchall()
    counts = {o: 0 for o in VALID_OUTCOMES}
    for outcome, c in rows:
        if outcome in counts:
            counts[outcome] = c
    total = sum(counts.values())
    judged = counts["useful"] + counts["not_useful"]  # inconclusive excluded from the rate itself
    return {
        "total_feedback": total,
        "useful_count": counts["useful"],
        "not_useful_count": counts["not_useful"],
        "inconclusive_count": counts["inconclusive"],
        "useful_rate_pct": round(100 * counts["useful"] / judged, 1) if judged else None,
    }


def case_feedback(conn: sqlite3.Connection, fir_number: str) -> list:
    """Every feedback record an officer has left for ONE specific case —
    used to show what's already been marked when reopening a case's
    recommendations, so the officer isn't re-asked about a lead they
    already judged."""
    rows = conn.execute(
        """SELECT lead_key, lead_text, outcome, notes, officer_id, recorded_at
           FROM lead_feedback WHERE fir_number=? ORDER BY recorded_at DESC""",
        (fir_number,),
    ).fetchall()
    return [
        {"lead_key": r[0], "lead_text": r[1], "outcome": r[2], "notes": r[3],
         "officer_id": r[4], "recorded_at": r[5]}
        for r in rows
    ]


def crime_type_summary(conn: sqlite3.Connection, crime_type: str = None) -> list:
    """
    Ranked leaderboard of lead types by historical usefulness — grouped
    by crime type (or across all crime types, if crime_type is None) —
    this is the "For this type of crime, X historically produced useful
    outcomes more often" answer, computed fresh from the permanent
    feedback log every time, never a cached guess. Empty list is the
    honest, expected result for a crime type nobody has given feedback
    on yet — not an error.
    """
    where, params = ["1=1"], []
    if crime_type:
        where.append("crime_type=?"); params.append(crime_type)
    where_sql = " AND ".join(where)

    rows = conn.execute(f"""
        SELECT crime_type, lead_key,
               MAX(lead_text) as lead_text,
               SUM(CASE WHEN outcome='useful' THEN 1 ELSE 0 END) as useful,
               SUM(CASE WHEN outcome='not_useful' THEN 1 ELSE 0 END) as not_useful,
               SUM(CASE WHEN outcome='inconclusive' THEN 1 ELSE 0 END) as inconclusive,
               COUNT(*) as total
        FROM lead_feedback WHERE {where_sql}
        GROUP BY crime_type, lead_key
        ORDER BY crime_type, (useful * 1.0 / NULLIF(useful + not_useful, 0)) DESC, total DESC
    """, params).fetchall()

    out = []
    for r in rows:
        judged = r[3] + r[4]
        out.append({
            "crime_type": r[0], "lead_key": r[1], "lead_text": r[2],
            "useful_count": r[3], "not_useful_count": r[4], "inconclusive_count": r[5],
            "total_feedback": r[6],
            "useful_rate_pct": round(100 * r[3] / judged, 1) if judged else None,
        })
    return out
