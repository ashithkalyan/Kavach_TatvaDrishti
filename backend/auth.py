"""
KAVACH — Real Authentication
================================
Replaces the "any password works" demo login with actual credential
verification: bcrypt password hashing + server-side session tokens
with expiry, stored in the same database everything else lives in —
this is what "online, with real login credentials" means in practice,
independent of whether that database is SQLite-on-a-persistent-disk
or a hosted Postgres instance.

No external auth service, no third-party API — bcrypt is a local,
standard cryptographic library (same category as networkx/scikit-learn:
a computational library you run yourself, not a call to someone else's
server).

SESSION MODEL: a random 32-byte token is generated on login, stored
server-side with an expiry, and returned to the client. Every
authenticated request sends the token back; validate_token() looks it
up and rejects anything expired or unknown. This is simpler than JWT
(no signing-key management) while being equally real — the client
never sees anything it could tamper with to forge a session.
"""
import os
import secrets
import sqlite3
from datetime import datetime, timedelta

import bcrypt

SESSION_LIFETIME_HOURS = int(os.getenv("SESSION_LIFETIME_HOURS", "12"))


def init_schema(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS AuthSession (
            Token TEXT PRIMARY KEY,
            UserID INTEGER NOT NULL,
            CreatedAt TEXT DEFAULT CURRENT_TIMESTAMP,
            ExpiresAt TEXT NOT NULL
        )
    """)
    conn.commit()


def hash_password(plain_password: str) -> str:
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def authenticate(conn: sqlite3.Connection, username: str, password: str):
    """Returns the user row dict on success, None on failure. Never
    reveals whether the username or the password was wrong — standard
    practice, prevents username enumeration."""
    row = conn.execute("""
        SELECT u.UserID, u.Username, u.PasswordHash, u.Role, e.FirstName,
               dist.DistrictName
        FROM Users u LEFT JOIN Employee e ON u.EmployeeID = e.EmployeeID
        LEFT JOIN District dist ON e.DistrictID = dist.DistrictID
        WHERE u.Username = ? AND u.IsActive = 1
    """, (username,)).fetchone()
    if not row:
        return None
    if not verify_password(password, row["PasswordHash"]):
        return None
    return dict(row)


def create_session(conn: sqlite3.Connection, user_id: int) -> dict:
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(hours=SESSION_LIFETIME_HOURS)).isoformat()
    conn.execute("INSERT INTO AuthSession (Token, UserID, ExpiresAt) VALUES (?, ?, ?)",
                 (token, user_id, expires_at))
    conn.commit()
    return {"token": token, "expires_at": expires_at}


def validate_token(conn: sqlite3.Connection, token: str):
    """Returns user_id if the token is valid and unexpired, else None."""
    if not token:
        return None
    row = conn.execute("SELECT UserID, ExpiresAt FROM AuthSession WHERE Token=?", (token,)).fetchone()
    if not row:
        return None
    if datetime.fromisoformat(row["ExpiresAt"]) < datetime.utcnow():
        conn.execute("DELETE FROM AuthSession WHERE Token=?", (token,))
        conn.commit()
        return None
    return row["UserID"]


def get_session_login_time(conn: sqlite3.Connection, token: str):
    """Returns the CreatedAt timestamp (ISO string) of the session behind
    this token, or None. Used to scope 'export all chats from this login'
    (see /api/chat/export) to exactly the turns created since the officer
    signed in — not their entire lifetime history."""
    row = conn.execute("SELECT CreatedAt FROM AuthSession WHERE Token=?", (token,)).fetchone()
    return row[0] if row else None


def revoke_session(conn: sqlite3.Connection, token: str):
    conn.execute("DELETE FROM AuthSession WHERE Token=?", (token,))
    conn.commit()


def register_user(conn: sqlite3.Connection, username: str, password: str, role: str,
                   employee_id: int = None) -> dict:
    """Real account creation — needed for 'online with login credentials'
    to mean something beyond 4 hardcoded demo accounts."""
    existing = conn.execute("SELECT UserID FROM Users WHERE Username=?", (username,)).fetchone()
    if existing:
        raise ValueError("Username already exists")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    password_hash = hash_password(password)
    cur = conn.execute(
        "INSERT INTO Users (Username, PasswordHash, EmployeeID, Role) VALUES (?,?,?,?)",
        (username, password_hash, employee_id, role)
    )
    conn.commit()
    return {"user_id": cur.lastrowid, "username": username, "role": role}
