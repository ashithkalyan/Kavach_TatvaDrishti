"""
KAVACH Brain — Investigation Knowledge That Survives Officer Transfer
==========================================================================
Everything else KAVACH remembers is scoped to the officer having the
conversation (conversation_memory, investigator_context) — genuinely
useful for that officer's own workflow, but it means the moment a case
changes hands, all of that context evaporates for whoever picks it up
next. This module is the other half: CASE-scoped, not officer-scoped,
institutional memory that survives exactly the handoff conversation
memory doesn't —

    Officer A investigates
            |
    Important case knowledge stored (this module + feedback_engine.py
            |                          + the pre-existing InvestigationUpdate log)
    Officer A transferred
            |
    Officer B receives the case
            |
    KAVACH gives Officer B the investigation history

"these leads were already checked, this connection remains unresolved,
these are the important people" for whichever officer asks, regardless
of who wrote it or when.

THREE KINDS of institutional memory, deliberately kept separate rather
than force-fit into one shape, because they answer different questions:

  case_notes (this module)   free-form notes an officer leaves for
                              whoever picks the case up next — tagged
                              by `kind` (important_person /
                              unresolved_thread / failed_lead / general)
                              so they can be filtered/grouped
                              meaningfully instead of read as a wall of
                              text. `unresolved_thread` notes can be
                              marked resolved later WITHOUT deleting the
                              record — the fact that something WAS open
                              and later got closed, and by roughly when,
                              stays visible.

  lead_feedback (feedback_engine.py, Feature 2)   "was this recommended
                              lead useful" is ALREADY exactly "which
                              leads were already checked, and what
                              happened" institutional memory — this
                              module reads it rather than duplicating
                              it.

  InvestigationUpdate (pre-existing, timeline_engine.py)   the case's
                              official update log. Also read here, not
                              duplicated.

case_briefing() is the single entry point that assembles all three into
one coherent answer — what brain.py's chat routing calls when an
officer asks "what's already been investigated on this case", and what
a dedicated case-briefing UI panel reads too. case_briefing_text()
renders that same dict as plain, human-readable text (a pure function,
no DB access) so the chat brain and any other consumer share one
rendering, never two independently-maintained summaries that could
drift apart.
"""
import sqlite3

VALID_NOTE_KINDS = {"important_person", "unresolved_thread", "failed_lead", "general"}


def init_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS case_notes (
            note_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            fir_number   TEXT NOT NULL,
            kind         TEXT NOT NULL,        -- see VALID_NOTE_KINDS
            note_text    TEXT NOT NULL,
            officer_id   INTEGER,
            officer_name TEXT,
            resolved     INTEGER DEFAULT 0,     -- for 'unresolved_thread' notes only — 0/1
            created_at   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_case_notes_fir ON case_notes (fir_number)")
    conn.commit()


def add_note(conn: sqlite3.Connection, fir_number: str, kind: str, note_text: str,
             officer_id: int = None, officer_name: str = None) -> dict:
    kind = (kind or "general").strip().lower()
    if kind not in VALID_NOTE_KINDS:
        return {"success": False, "reason": f"kind must be one of {sorted(VALID_NOTE_KINDS)}"}
    if not note_text or not note_text.strip():
        return {"success": False, "reason": "note_text is required"}
    cur = conn.execute(
        "INSERT INTO case_notes (fir_number, kind, note_text, officer_id, officer_name) VALUES (?,?,?,?,?)",
        (fir_number, kind, note_text.strip(), officer_id, officer_name),
    )
    conn.commit()
    return {"success": True, "note_id": cur.lastrowid}


def resolve_note(conn: sqlite3.Connection, note_id: int, resolved: bool = True) -> bool:
    """Marks an 'unresolved_thread' note resolved (or reopens it) —
    never deletes it, so the full trail (something WAS open, and
    roughly when it got closed) stays visible to whoever looks at this
    case later, which is the entire point of institutional memory."""
    cur = conn.execute("UPDATE case_notes SET resolved=? WHERE note_id=?", (1 if resolved else 0, note_id))
    conn.commit()
    return cur.rowcount > 0


def list_notes(conn: sqlite3.Connection, fir_number: str, kind: str = None) -> list:
    where, params = ["fir_number=?"], [fir_number]
    if kind:
        where.append("kind=?"); params.append(kind)
    rows = conn.execute(
        f"""SELECT note_id, kind, note_text, officer_name, resolved, created_at FROM case_notes
            WHERE {' AND '.join(where)} ORDER BY created_at DESC""", params,
    ).fetchall()
    return [
        {"note_id": r[0], "kind": r[1], "note_text": r[2], "officer_name": r[3],
         "resolved": bool(r[4]), "created_at": r[5]}
        for r in rows
    ]


def case_briefing(conn: sqlite3.Connection, fir_number: str) -> dict:
    """
    Assembles everything institutionally known about ONE case —
    dedicated notes, the investigation update log, and recorded lead
    feedback — into a single structured briefing. {"found": False} for
    an unknown FIR number; every other key is always present (as an
    empty list where there's nothing yet), never missing.
    """
    from . import feedback_engine  # local import avoids a circular import at module load time

    case_row = conn.execute(
        """SELECT fir_id, crime_type, district, police_station, status, registration_date
           FROM vw_fir_flat WHERE fir_number=?""",
        (fir_number,),
    ).fetchone()
    if not case_row:
        return {"found": False}

    updates = conn.execute(
        "SELECT UpdateDate, UpdateText, OfficerName FROM InvestigationUpdate WHERE CaseMasterID=? ORDER BY UpdateDate ASC",
        (case_row[0],),
    ).fetchall()

    notes = list_notes(conn, fir_number)
    important_people = [n for n in notes if n["kind"] == "important_person"]
    unresolved = [n for n in notes if n["kind"] == "unresolved_thread" and not n["resolved"]]
    resolved_threads = [n for n in notes if n["kind"] == "unresolved_thread" and n["resolved"]]
    failed_leads_notes = [n for n in notes if n["kind"] == "failed_lead"]
    general_notes = [n for n in notes if n["kind"] == "general"]

    checked_leads = feedback_engine.case_feedback(conn, fir_number)

    officers = sorted({r[2] for r in updates if r[2]} | {n["officer_name"] for n in notes if n.get("officer_name")})

    return {
        "found": True,
        "fir_number": fir_number, "crime_type": case_row[1], "district": case_row[2],
        "police_station": case_row[3], "status": case_row[4], "registration_date": case_row[5],
        "investigation_updates": [{"date": r[0], "text": r[1], "officer": r[2]} for r in updates],
        "important_people": important_people,
        "unresolved_threads": unresolved,
        "resolved_threads": resolved_threads,
        "failed_leads": failed_leads_notes,
        "general_notes": general_notes,
        "checked_leads": checked_leads,
        "officers_involved": officers,
    }


def case_briefing_text(briefing: dict) -> str:
    """Renders a case_briefing() dict as plain, readable text — shared
    by the chat brain (see brain.py's case-briefing routing) and
    anywhere else a human-readable summary is needed, so there is only
    ever ONE rendering of 'what this case briefing says' to keep in
    sync, not two that could quietly drift apart."""
    if not briefing.get("found"):
        return "No case found with that FIR number."

    lines = [f"Case briefing for FIR {briefing['fir_number']} ({briefing['crime_type']}, "
             f"{briefing['police_station']}, {briefing['district']}) — status: {briefing['status']}."]

    if briefing["officers_involved"]:
        lines.append(f"Officers who have worked this case: {', '.join(briefing['officers_involved'])}.")

    if briefing["important_people"]:
        names = "; ".join(n["note_text"] for n in briefing["important_people"][:5])
        lines.append(f"Important people flagged: {names}.")

    if briefing["checked_leads"]:
        useful = [l for l in briefing["checked_leads"] if l["outcome"] == "useful"]
        not_useful = [l for l in briefing["checked_leads"] if l["outcome"] == "not_useful"]
        if useful:
            lines.append("Leads already confirmed USEFUL: " +
                          "; ".join(l["lead_text"] or l["lead_key"] for l in useful) + ".")
        if not_useful:
            lines.append("Leads already checked and found NOT useful (no need to repeat these): " +
                          "; ".join(l["lead_text"] or l["lead_key"] for l in not_useful) + ".")

    if briefing["unresolved_threads"]:
        lines.append("Still UNRESOLVED: " +
                      "; ".join(n["note_text"] for n in briefing["unresolved_threads"]) + ".")

    if briefing["failed_leads"]:
        lines.append("Dead ends already tried: " +
                      "; ".join(n["note_text"] for n in briefing["failed_leads"]) + ".")

    if briefing["investigation_updates"]:
        last = briefing["investigation_updates"][-1]
        lines.append(f"{len(briefing['investigation_updates'])} investigation update(s) on file, most recent: "
                      f"\"{(last['text'] or '')[:150]}\" ({last['date']}).")

    if len(lines) == 1:
        lines.append("No additional notes, checked leads, or updates recorded yet — this looks like a fresh case.")

    return " ".join(lines)
