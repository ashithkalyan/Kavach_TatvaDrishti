"""
KAVACH Brain — Chat-Session Document Context
================================================
Scratch, session-scoped text storage for "chat with a PDF" (see
main.py's /api/chat/upload-document and brain.py's document_intent
routing). Deliberately NOT the case database (CaseMaster/Accused/
Victim) — a PDF an officer drops into a chat is a document under
discussion, not a verified record, until they explicitly extract it
AND confirm the review form (see ingestion_engine.py's parse_fields()/
commit_draft() and main.py's /api/ingest/confirm, which is still the
ONLY code path that ever writes to the case tables).

One document per chat session, keyed by session_id: uploading a new
file into the same session replaces the previous one (this is meant to
be "the document we're currently discussing", not a growing archive).
Scoped by (user_id, session_id) together everywhere it's read, the same
discipline memory_engine.get_session_history() uses, so an officer
guessing another officer's session_id gets nothing back.

Also holds `save_result_json` — the outcome of confirming this
session's extracted draft into a real case (see main.py's POST
/api/ingest/confirm and POST /api/chat/document/{session_id}/save-result).
This is what lets DocumentReviewCard.jsx show its "Saved — FIR ... is
now live" confirmation again after a page reload or switching chat
sessions and back, instead of reverting to the blank edit form — a
reported bug (the "FIR saved box... goes off" complaint). A fresh
upload into the same session clears any previous save_result, since
it's now a different, unsaved document.
"""
import sqlite3


def init_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chat_document_context (
            session_id     TEXT PRIMARY KEY,
            user_id        INTEGER NOT NULL,
            filename       TEXT,
            document_text  TEXT NOT NULL,
            char_count     INTEGER NOT NULL,
            extraction_engine TEXT,
            save_result_json TEXT,
            uploaded_at    TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Additive migration for DBs seeded before save_result_json existed.
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chat_document_context)").fetchall()}
    if "save_result_json" not in cols:
        conn.execute("ALTER TABLE chat_document_context ADD COLUMN save_result_json TEXT")
    conn.commit()


def store_document(conn: sqlite3.Connection, user_id: int, session_id: str,
                    filename: str, text: str, extraction_engine: str = None):
    """Upsert — a new upload into the same session replaces whatever was
    there before, matching the 'document we're currently discussing'
    model described in the module docstring. Explicitly clears any
    previous save_result: a freshly uploaded file is, by definition, not
    yet saved."""
    conn.execute(
        """INSERT INTO chat_document_context
               (session_id, user_id, filename, document_text, char_count, extraction_engine,
                save_result_json, uploaded_at)
           VALUES (?,?,?,?,?,?, NULL, CURRENT_TIMESTAMP)
           ON CONFLICT(session_id) DO UPDATE SET
             user_id=excluded.user_id, filename=excluded.filename,
             document_text=excluded.document_text, char_count=excluded.char_count,
             extraction_engine=excluded.extraction_engine, save_result_json=NULL,
             uploaded_at=CURRENT_TIMESTAMP""",
        (session_id, user_id, filename, text, len(text or ""), extraction_engine),
    )
    conn.commit()


def get_document(conn: sqlite3.Connection, user_id: int, session_id: str):
    """Returns {"filename", "text", "char_count", "extraction_engine",
    "uploaded_at", "save_result"} or None. Scoped by (user_id,
    session_id) together — never just session_id — so this can never
    leak one officer's uploaded document into another officer's chat.
    `save_result` is None until store_save_result() has been called for
    this session's current document."""
    if not session_id:
        return None
    row = conn.execute(
        """SELECT filename, document_text, char_count, extraction_engine, uploaded_at, save_result_json
           FROM chat_document_context WHERE session_id=? AND user_id=?""",
        (session_id, user_id),
    ).fetchone()
    if not row:
        return None
    save_result = None
    if row[5]:
        import json
        try:
            save_result = json.loads(row[5])
        except (json.JSONDecodeError, TypeError):
            save_result = None
    return {"filename": row[0], "text": row[1], "char_count": row[2],
            "extraction_engine": row[3], "uploaded_at": row[4], "save_result": save_result}


def store_save_result(conn: sqlite3.Connection, user_id: int, session_id: str, save_result: dict) -> bool:
    """Records the outcome of confirming this session's document into a
    real case (fir_number, accused[], note — the same shape
    POST /api/ingest/confirm returns). Returns False if there's no
    document row for this (user_id, session_id) to attach the result to
    (e.g. the document was already cleared) — the caller should treat
    that as a harmless no-op, not an error; the save itself already
    succeeded regardless."""
    import json
    cur = conn.execute(
        "UPDATE chat_document_context SET save_result_json=? WHERE session_id=? AND user_id=?",
        (json.dumps(save_result, default=str), session_id, user_id),
    )
    conn.commit()
    return cur.rowcount > 0


def clear_document(conn: sqlite3.Connection, user_id: int, session_id: str) -> bool:
    cur = conn.execute(
        "DELETE FROM chat_document_context WHERE session_id=? AND user_id=?", (session_id, user_id)
    )
    conn.commit()
    return cur.rowcount > 0
