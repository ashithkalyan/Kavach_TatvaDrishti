"""
KAVACH Brain — Identity Confidence That Changes Over Time
==============================================================
resolve_or_link_person_identity() (see ingestion_engine.py) already
computes a match confidence at the MOMENT one new accused record is
being linked to an existing PersonIdentity — but that number is scoped
to one link event and is never revisited. This module adds the thing
that was missing: an OVERALL, per-identity confidence that is
RECOMPUTED FROM SCRATCH every time new evidence arrives, so it can
genuinely rise as corroborating records accumulate, and genuinely fall
(with an explicit review flag) when new evidence contradicts what was
already on file — exactly the two directions described in this
project's own feature request:

    New Evidence
          |
    Supports identity? --- Yes --> Confidence increases
          |
          No
          |
    Conflicts with identity? --> Flag for review

WHY RECOMPUTED FROM SCRATCH, NEVER INCREMENTALLY PATCHED: an identity's
confidence has to be a function of the CURRENT total evidence, not a
running tally that can drift from what the evidence actually shows
(e.g. a record being corrected or a case being reclassified must be
able to raise OR lower confidence, not just add to a one-way counter).
compute_identity_confidence() re-derives it every call directly from
PersonIdentityLink + Accused + CaseMaster; record_confidence_snapshot()
is the only thing that persists anything, and only writes a new
history row when the recomputed value actually differs from the last
one (see its own docstring) — the log is a genuine trajectory, not a
timestamped copy of the same number.

FACTORS (all computed from real, already-recorded fields — never
invented): more independently linked case records raise confidence
(more corroboration); a consistent father/spouse name across every
linked record is a positive signal; an age progression that doesn't
line up with the calendar gap between two cases, or a different
father/spouse name recorded on a later case, are contradictions that
lower confidence and set status='needs_review'.
"""
import sqlite3


def init_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS identity_confidence_log (
            log_id             INTEGER PRIMARY KEY AUTOINCREMENT,
            person_identity_id INTEGER NOT NULL,
            confidence         REAL NOT NULL,
            status             TEXT NOT NULL,      -- 'stable' | 'needs_review'
            evidence_count     INTEGER NOT NULL,
            reason             TEXT,
            recorded_at        TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_identity_confidence_log_person
        ON identity_confidence_log (person_identity_id, log_id)
    """)
    conn.commit()


def compute_identity_confidence(conn: sqlite3.Connection, person_identity_id: int) -> dict:
    """
    Recomputes confidence for ONE identity from every currently-linked
    accused record. See this module's docstring for the factor list.
    Never writes anything — see record_confidence_snapshot() for that.
    """
    rows = conn.execute("""
        SELECT a.AccusedMasterID, a.AgeYear, a.FatherOrSpouseName, cm.CrimeRegisteredDate,
               cm.PoliceStationID
        FROM PersonIdentityLink pil
        JOIN Accused a ON pil.AccusedMasterID = a.AccusedMasterID
        JOIN CaseMaster cm ON a.CaseMasterID = cm.CaseMasterID
        WHERE pil.PersonIdentityID = ?
        ORDER BY cm.CrimeRegisteredDate
    """, (person_identity_id,)).fetchall()

    evidence_count = len(rows)
    if evidence_count == 0:
        return {"confidence": 0.0, "status": "needs_review", "evidence_count": 0,
                "reason": "No linked case records — nothing to verify this identity against.",
                "contradictions": ["No linked records"]}
    if evidence_count == 1:
        return {"confidence": 65.0, "status": "stable", "evidence_count": 1,
                "reason": "Only one linked case record so far — a reasonable starting identity, "
                          "not yet corroborated by an independent record.",
                "contradictions": []}

    father_names = {r[2].strip().lower() for r in rows if r[2] and r[2].strip()}
    contradictions = []
    if len(father_names) > 1:
        contradictions.append(f"{len(father_names)} different father/spouse names recorded across linked cases")

    # Age progression vs. the calendar gap between cases — allow 2 years
    # of slack either way for ordinary recording imprecision (rounded
    # ages, birthday timing) before calling it a genuine contradiction.
    dated_ages = [(r[3], r[1]) for r in rows if r[3] and r[1] is not None]
    dated_ages.sort()
    age_issue_pairs = 0
    for i in range(1, len(dated_ages)):
        d0, a0 = dated_ages[i - 1]
        d1, a1 = dated_ages[i]
        try:
            elapsed = int(d1[:4]) - int(d0[:4])
        except (ValueError, TypeError):
            continue
        if abs((a1 - a0) - elapsed) > 2:
            age_issue_pairs += 1
    if age_issue_pairs:
        contradictions.append(f"{age_issue_pairs} case pair(s) where the age progression doesn't match "
                               f"the calendar gap between them")

    base = 60.0
    evidence_bonus = min(35.0, (evidence_count - 1) * 5.0)  # each extra corroborating record helps, with a cap
    father_bonus = 5.0 if len(father_names) == 1 else 0.0
    contradiction_penalty = len(contradictions) * 25.0

    confidence = max(5.0, min(99.0, base + evidence_bonus + father_bonus - contradiction_penalty))
    status = "needs_review" if contradictions else "stable"

    reason_bits = [f"{evidence_count} linked case records"]
    if len(father_names) == 1:
        reason_bits.append("consistent father/spouse name across all of them")
    elif not father_names:
        reason_bits.append("no father/spouse name on file to cross-check")
    reason_bits.extend(contradictions)
    reason = "; ".join(reason_bits)

    return {"confidence": round(confidence, 1), "status": status, "evidence_count": evidence_count,
            "reason": reason, "contradictions": contradictions}


def record_confidence_snapshot(conn: sqlite3.Connection, person_identity_id: int) -> dict:
    """
    Recomputes and, ONLY if it meaningfully changed from the last
    recorded snapshot (confidence moved by >= 0.5, or the status
    flipped), appends a new row to the permanent history log. Call this
    whenever new evidence for an identity arrives — see
    ingestion_engine.commit_draft(), which calls this for every accused
    record it links or creates.

    Returns the computed dict (see compute_identity_confidence()) plus
    `logged: bool` so callers can tell whether this call actually added
    a new history point.
    """
    computed = compute_identity_confidence(conn, person_identity_id)
    last = conn.execute(
        "SELECT confidence, status FROM identity_confidence_log WHERE person_identity_id=? ORDER BY log_id DESC LIMIT 1",
        (person_identity_id,),
    ).fetchone()
    if last and abs(last[0] - computed["confidence"]) < 0.5 and last[1] == computed["status"]:
        return {**computed, "logged": False}

    conn.execute(
        """INSERT INTO identity_confidence_log
               (person_identity_id, confidence, status, evidence_count, reason)
           VALUES (?,?,?,?,?)""",
        (person_identity_id, computed["confidence"], computed["status"],
         computed["evidence_count"], computed["reason"]),
    )
    conn.commit()
    return {**computed, "logged": True}


def confidence_history(conn: sqlite3.Connection, person_identity_id: int) -> list:
    """Full trajectory for one identity, oldest first — what lets the UI
    literally show confidence climbing from 65% to 95% over time (or
    dropping and flagging for review), not just the current number."""
    rows = conn.execute(
        """SELECT confidence, status, evidence_count, reason, recorded_at
           FROM identity_confidence_log WHERE person_identity_id=? ORDER BY log_id ASC""",
        (person_identity_id,),
    ).fetchall()
    return [
        {"confidence": r[0], "status": r[1], "evidence_count": r[2], "reason": r[3], "recorded_at": r[4]}
        for r in rows
    ]


def current_confidence(conn: sqlite3.Connection, person_identity_id: int) -> dict:
    """The latest recorded snapshot, or a freshly computed (but
    unlogged) one if this identity has never been snapshotted yet —
    always returns a usable answer, never None."""
    row = conn.execute(
        """SELECT confidence, status, evidence_count, reason, recorded_at
           FROM identity_confidence_log WHERE person_identity_id=? ORDER BY log_id DESC LIMIT 1""",
        (person_identity_id,),
    ).fetchone()
    if row:
        return {"confidence": row[0], "status": row[1], "evidence_count": row[2],
                "reason": row[3], "recorded_at": row[4]}
    return {**compute_identity_confidence(conn, person_identity_id), "recorded_at": None}


def needs_review(conn: sqlite3.Connection, limit: int = 50) -> list:
    """Every identity whose LATEST snapshot is status='needs_review' —
    the actionable 'these identities have contradictory evidence and
    should be looked at' worklist. Only considers each identity's most
    recent snapshot (an identity that WAS flagged and has since been
    resolved/corrected no longer appears)."""
    rows = conn.execute("""
        SELECT l.person_identity_id, l.confidence, l.reason, l.recorded_at, pi.CanonicalName
        FROM identity_confidence_log l
        JOIN PersonIdentity pi ON l.person_identity_id = pi.PersonIdentityID
        WHERE l.log_id IN (
            SELECT MAX(log_id) FROM identity_confidence_log GROUP BY person_identity_id
        ) AND l.status = 'needs_review'
        ORDER BY l.confidence ASC LIMIT ?
    """, (limit,)).fetchall()
    return [
        {"person_identity_id": r[0], "confidence": r[1], "reason": r[2], "recorded_at": r[3], "name": r[4]}
        for r in rows
    ]


def backfill_all_identities(conn: sqlite3.Connection) -> int:
    """
    One-time initialization: computes and logs a starting confidence
    snapshot for every PersonIdentity that has at least one linked
    accused record but no confidence history yet — so this feature has
    a real, populated starting point (including some genuinely flagged
    'needs_review' identities, if this project's seeded data happens to
    contain any inconsistent records) rather than an empty table until
    the next chat-driven case extraction. Idempotent: already-
    snapshotted identities are left alone (record_confidence_snapshot()
    only logs when something actually changed — a re-run of this
    function costs one no-op read per identity, nothing more).
    """
    ids = conn.execute("SELECT DISTINCT PersonIdentityID FROM PersonIdentityLink").fetchall()
    logged = 0
    for (pid,) in ids:
        result = record_confidence_snapshot(conn, pid)
        if result["logged"]:
            logged += 1
    return logged
