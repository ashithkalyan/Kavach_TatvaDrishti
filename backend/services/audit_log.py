"""
KAVACH Services — Audit Log
===============================
"Every query is logged — who asked what, when" — this is the whole
module. Deliberately small: one table, one write function, one read
function. No new dependency, no separate service to deploy.

WHY THIS IS HONEST TO BUILD, NOT JUST A CHECKBOX
  user_id (the real authenticated officer — see main.py's earlier
  honesty fix around hardcoded user_id) and session_id are already on
  every /api/chat request. This just persists that pairing, plus the
  interpreted intent and result count, so a supervisor can answer
  "who looked up this person" or "what did officer X search this week"
  from real stored rows rather than the request logs of some hosting
  platform nobody would think to check.

WHAT IT DELIBERATELY DOES NOT LOG
  Full response text isn't duplicated here (conversation_memory already
  has that, and this table would just balloon for no benefit) — the
  audit log answers "who queried what, when, with what outcome", not
  "replay the whole conversation". Failed logins are handled separately
  in auth.py and aren't duplicated here either.
"""
import sqlite3
from datetime import datetime


def init_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS AuditLog (
            AuditID INTEGER PRIMARY KEY AUTOINCREMENT,
            UserID INTEGER NOT NULL,
            SessionID TEXT,
            Endpoint TEXT NOT NULL,
            QueryText TEXT,
            Intent TEXT,
            ResultCount INTEGER,
            Timestamp TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON AuditLog(UserID)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_time ON AuditLog(Timestamp)")
    conn.commit()


def log(conn: sqlite3.Connection, user_id: int, session_id: str, endpoint: str,
        query_text: str = None, intent: str = None, result_count: int = None):
    """
    Best-effort — a logging failure should never break the actual
    request it's logging. Callers wrap this in try/except (see main.py)
    rather than this function swallowing errors itself, so a genuine
    schema problem is still visible in server logs during development.
    """
    conn.execute(
        "INSERT INTO AuditLog (UserID, SessionID, Endpoint, QueryText, Intent, ResultCount, Timestamp) "
        "VALUES (?,?,?,?,?,?,?)",
        (user_id, session_id, endpoint, (query_text or "")[:500], intent, result_count,
         datetime.now().isoformat())
    )
    conn.commit()


def fetch(conn: sqlite3.Connection, limit: int = 200, user_id_filter: int = None):
    """Most-recent-first, optionally scoped to one officer. Joins in the
    officer's username/role so the viewer doesn't need a second lookup."""
    where, params = "1=1", []
    if user_id_filter:
        where = "a.UserID = ?"
        params.append(user_id_filter)
    rows = conn.execute(f"""
        SELECT a.AuditID, a.UserID, u.Username, u.Role, a.SessionID, a.Endpoint,
               a.QueryText, a.Intent, a.ResultCount, a.Timestamp
        FROM AuditLog a
        LEFT JOIN Users u ON u.UserID = a.UserID
        WHERE {where}
        ORDER BY a.Timestamp DESC LIMIT ?
    """, (*params, limit)).fetchall()
    cols = ["audit_id", "user_id", "username", "role", "session_id", "endpoint",
            "query_text", "intent", "result_count", "timestamp"]
    return [dict(zip(cols, r)) for r in rows]
