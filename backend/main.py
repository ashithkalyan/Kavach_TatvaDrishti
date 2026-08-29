"""
KAVACH — Karnataka AI Voice & Crime Hub
FastAPI Backend v2 — wired to the KSP-compliant schema + brain orchestrator
"""
import json
import os
import queue
import sqlite3
import tempfile
import threading
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Header, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

from brain import (brain as kavach_brain, memory_engine, prediction_engine, similarity_engine,
                    timeline_engine, recommendation_engine, graph_engine, ingestion_engine,
                    mo_fingerprint, reasoning_trace, ollama_client, hotspot_forecast,
                    document_context, prediction_tracking, feedback_engine, identity_confidence,
                    case_memory)
from services import pdf_export, audit_log, ncrb_reference, catalyst_adapter, risk_scoring
import auth

app = FastAPI(title="KAVACH API", version="2.0.0", docs_url="/api/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                    allow_methods=["*"], allow_headers=["*"])

DB_PATH = os.getenv("DB_PATH", "kavach.db")


@app.on_event("startup")
async def _ensure_audit_schema():
    # CREATE TABLE IF NOT EXISTS is idempotent — safe even if seed_data.py
    # already created it. Guarantees these tables (and any additive
    # column migrations inside their own init_schema()/init_context_schema()
    # — see memory_engine.py's full_response_json for a concrete example)
    # get applied to a DB that was seeded before this code existed,
    # WITHOUT a manual migration step or re-running seed_data.py (which
    # would wipe real case data). This is not optional housekeeping: a
    # reported bug (full conversation state vanishing on reload) traced
    # back to exactly this — the migration code existed but nothing
    # actually called it against the already-seeded database, because
    # memory_engine.init_schema()/init_context_schema() used to be called
    # ONLY from seed_data.py's one-time setup, never on server boot.
    try:
        conn = get_conn()
        audit_log.init_schema(conn)
        document_context.init_schema(conn)
        memory_engine.init_schema(conn)
        memory_engine.init_context_schema(conn)
        prediction_tracking.init_schema(conn)
        feedback_engine.init_schema(conn)
        identity_confidence.init_schema(conn)
        id_backfilled = identity_confidence.backfill_all_identities(conn)
        if id_backfilled:
            print(f"[startup] Logged initial identity-confidence snapshots for {id_backfilled} identities")
        case_memory.init_schema(conn)
        # One-time (idempotent — see backfill_historical_predictions()'s
        # own docstring) walk-forward backtest across the seeded
        # CrimeTrend history, so the prediction-accuracy feature has a
        # real, multi-year settled track record from the very first
        # request instead of an empty table. Fast (~1s for this
        # project's data volume) and safe to run on every boot; already-
        # recorded targets are skipped.
        backfilled = prediction_tracking.backfill_historical_predictions(conn)
        if backfilled:
            print(f"[startup] Backfilled {backfilled} historical predictions for accuracy tracking")
        conn.close()
    except Exception as e:
        # Never crash the server over a schema hiccup, but also never
        # swallow it silently — a migration that failed to apply is
        # exactly the kind of thing that causes a confusing 500 several
        # requests later instead of a clear signal here.
        print(f"[startup] schema init/migration warning: {e}")


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def rows(cursor) -> List[dict]:
    return [dict(r) for r in cursor.fetchall()]


def require_auth(authorization: Optional[str] = Header(None)) -> int:
    """
    FastAPI dependency — validates the 'Authorization: Bearer <token>'
    header against real, server-side session tokens (auth.py). Applied
    to every endpoint that touches case, offender, or network data —
    this is what makes 'online with login credentials' actually mean
    something, rather than a login screen that isn't wired to anything.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header — please log in")
    token = authorization.removeprefix("Bearer ").strip()
    conn = get_conn()
    try:
        user_id = auth.validate_token(conn, token)
    finally:
        conn.close()
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid — please log in again")
    return user_id


def require_admin(user_id: int = Depends(require_auth)) -> int:
    """Gates the audit log to admin/supervisor roles — an accountability
    log that any officer could read defeats its own purpose."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT Role FROM Users WHERE UserID=?", (user_id,)).fetchone()
    finally:
        conn.close()
    role = (row["Role"] if row else "").lower()
    if role not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin or supervisor role required for the audit log")
    return user_id


# ─── Pydantic models ────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    language: Optional[str] = "en"


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str


class TranslateRequest(BaseModel):
    text: str
    target_language: Optional[str] = "kn"


class AccusedIngestEntry(BaseModel):
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None
    father_or_spouse_name: Optional[str] = None


class VictimIngestEntry(BaseModel):
    name: str
    age: Optional[int] = None
    gender: Optional[str] = None


class IngestConfirmRequest(BaseModel):
    crime_no: str
    case_no: str
    registration_date: str
    police_station_id: int
    case_category_id: Optional[int] = 1
    crime_major_head_id: Optional[int] = None
    crime_minor_head_id: Optional[int] = None
    case_status_id: Optional[int] = 1
    brief_facts: Optional[str] = ""
    accused: List[AccusedIngestEntry] = []
    victims: List[VictimIngestEntry] = []


# ─── Auth (real: bcrypt + server-side session tokens) ───────────────────────

@app.post("/api/auth/login")
async def login(req: LoginRequest):
    conn = get_conn()
    user = auth.authenticate(conn, req.username, req.password)
    if not user:
        conn.close()
        raise HTTPException(status_code=401, detail="Invalid username or password")
    session = auth.create_session(conn, user["UserID"])
    conn.close()
    return {
        "success": True,
        "user": {
            "id": user["UserID"], "username": user["Username"], "role": user["Role"],
            "full_name": user["FirstName"] or user["Username"].title(),
            "badge_number": f"KSP/{user['Role'][:3].upper()}/{user['UserID']:03d}",
            "district": user["DistrictName"] or "State HQ",
        },
        "token": session["token"], "expires_at": session["expires_at"],
    }


@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    conn = get_conn()
    try:
        result = auth.register_user(conn, req.username, req.password, req.role)
    except ValueError as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))
    session = auth.create_session(conn, result["user_id"])
    conn.close()
    return {"success": True, "user": result, "token": session["token"]}


@app.post("/api/auth/logout")
async def logout(token: str = Query(...)):
    conn = get_conn()
    auth.revoke_session(conn, token)
    conn.close()
    return {"success": True}


@app.get("/api/auth/validate")
async def validate_session(token: str = Query(...)):
    conn = get_conn()
    user_id = auth.validate_token(conn, token)
    conn.close()
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid — please log in again")
    return {"valid": True, "user_id": user_id}


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/api/dashboard/overview")
async def dashboard_overview(user_id: int = Depends(require_auth)):
    conn = get_conn()
    total_firs = conn.execute("SELECT COUNT(*) FROM CaseMaster").fetchone()[0]
    open_cases = conn.execute("SELECT COUNT(*) FROM vw_fir_flat WHERE status='Under Investigation'").fetchone()[0]
    charge_sheeted = conn.execute("SELECT COUNT(*) FROM vw_fir_flat WHERE status='Charge-Sheeted'").fetchone()[0]
    total_accused = conn.execute("SELECT COUNT(*) FROM PersonIdentity").fetchone()[0]
    arrested = conn.execute("SELECT COUNT(DISTINCT AccusedMasterID) FROM ArrestSurrender").fetchone()[0]
    high_risk = conn.execute("SELECT COUNT(*) FROM PersonIdentity WHERE RiskCategory IN ('HIGH','EXTREME')").fetchone()[0]
    repeat = conn.execute("SELECT COUNT(*) FROM PersonIdentity WHERE IsRepeatOffender=1").fetchone()[0]
    gang_members = conn.execute("SELECT COUNT(*) FROM PersonIdentity WHERE GangAffiliation IS NOT NULL").fetchone()[0]

    recent_firs = rows(conn.execute("""
        SELECT fir_number, registration_date, district, crime_type, status, police_station
        FROM vw_fir_flat ORDER BY registration_date DESC LIMIT 8
    """))
    crime_dist = rows(conn.execute("""
        SELECT crime_type, COUNT(*) as count FROM vw_fir_flat GROUP BY crime_type ORDER BY count DESC LIMIT 8
    """))
    district_dist = rows(conn.execute("""
        SELECT district, COUNT(*) as count FROM vw_fir_flat GROUP BY district ORDER BY count DESC LIMIT 8
    """))
    latest_year = conn.execute("SELECT MAX(Year) FROM CrimeTrend").fetchone()[0] or 2025
    monthly = rows(conn.execute("""
        SELECT Month as month, SUM(CaseCount) as count FROM CrimeTrend WHERE Year=? GROUP BY Month ORDER BY Month
    """, (latest_year,)))
    conn.close()

    return {
        "kpis": {
            "total_firs": total_firs, "open_cases": open_cases, "total_accused": total_accused,
            "arrested": arrested, "high_risk_offenders": high_risk, "repeat_offenders": repeat,
            "gang_members": gang_members, "charge_sheeted": charge_sheeted,
        },
        "recent_firs": recent_firs, "crime_distribution": crime_dist,
        "district_distribution": district_dist, "monthly_trend_2024": monthly,
        "trend_year": latest_year,
    }


# ─── Chat (now backed by the full brain orchestrator) ────────────────────────

@app.post("/api/chat")
async def chat(req: ChatRequest, user_id: int = Depends(require_auth)):
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:8]}"
    conn = get_conn()
    try:
        # HONESTY / PRIVACY FIX: this used to be hardcoded to user_id=1
        # regardless of who was actually logged in, which meant every
        # officer's chat memory, working context, and history sidebar
        # were silently shared under one identity. Now it uses the real
        # authenticated user from the session token.
        result = kavach_brain.process_query(conn, user_id=user_id, session_id=session_id,
                                             message=req.message, language=req.language or "en")
    finally:
        conn.close()

    # Audit log — best-effort, must never break the actual chat response.
    try:
        audit_conn = get_conn()
        audit_log.log(audit_conn, user_id=user_id, session_id=session_id, endpoint="/api/chat",
                       query_text=req.message, intent=result.get("intent"),
                       result_count=result.get("result_count"))
        audit_conn.close()
    except Exception:
        pass

    accused_ids = list({r["person_id"] for r in result["results"] if r.get("person_id")})[:10]
    fir_ids = list({r["fir_number"] for r in result["results"] if r.get("fir_number")})[:10]

    return {
        "session_id": result["session_id"], "message": result["message"],
        "interpretation": result["interpretation"], "sql_generated": result["sql_generated"],
        "intent": result["intent"], "filters_applied": [], "insights": result.get("insights"),
        "follow_up_suggestions": result["follow_up_suggestions"], "results": result["results"],
        "result_count": result["result_count"], "accused_ids": accused_ids, "fir_ids": fir_ids,
        "error": None, "timestamp": result["timestamp"],
        # new, additive fields — existing frontend ignores unknown fields safely
        "alias_matches": result["alias_matches"], "memory_recalled": result["memory_recalled"],
        "pipeline_trace": result["pipeline_trace"], "routed_engine": result["routed_engine"],
        "identity_reasoning_trace": result.get("identity_reasoning_trace"),
        "needs_clarification": result.get("needs_clarification", False),
        "network_snapshot": result.get("network_snapshot"),
        # response_source powers the "✓ Grounded" badge in the frontend's
        # Reasoning panel: "ollama_grounded" (Ollama phrased it, verified
        # against the facts), "ollama_polish" (phrasing only, facts came
        # straight from the template), "template" (no LLM involved),
        # or "general_knowledge" (curated reference answer, not case data).
        # "document_grounded" is the same idea, one layer further: answered
        # from an attached document's extracted text, not the database at
        # all — see brain/document_context.py and ollama_client.answer_from_document().
        "response_source": result.get("response_source", "template"),
        # Self-critique note (Layer 3) — a short, already-grounding-checked
        # observation surfaced ONLY when it clears a real bar (see
        # ollama_client._clears_notable_bar()); usually None, which is
        # expected, not a failure.
        "notable_insight": result.get("notable_insight"),
        # Chat-with-a-PDF fields — both None unless a document is attached
        # to this session and this turn's message was routed to the
        # document-chat path (see brain.py's document_intent routing).
        "document_attached": result.get("document_attached"),
        "document_draft": result.get("document_draft"),
    }


@app.get("/api/chat/sessions")
async def list_chat_sessions(user_id: int = Depends(require_auth)):
    """Session list for the conversation-history sidebar — groups
    conversation_memory by session_id so a refreshed page (or a
    different device) can show past conversations, not just the
    current one held in React state."""
    conn = get_conn()
    session_rows = rows(conn.execute("""
        SELECT session_id,
               MIN(timestamp) as started_at,
               MAX(timestamp) as last_active,
               COUNT(*) as turn_count,
               (SELECT message_text FROM conversation_memory cm2
                WHERE cm2.session_id = cm.session_id AND cm2.role='user'
                ORDER BY turn_index ASC LIMIT 1) as first_message
        FROM conversation_memory cm WHERE user_id=?
        GROUP BY session_id ORDER BY last_active DESC LIMIT 50
    """, (user_id,)))
    conn.close()
    return {"sessions": session_rows}


@app.get("/api/chat/history/{session_id}")
async def get_chat_history(session_id: str, user_id: int = Depends(require_auth)):
    conn = get_conn()
    # get_session_history filters by (user_id, session_id) together, so an
    # officer guessing another officer's session_id simply gets an empty
    # result rather than someone else's conversation.
    history = memory_engine.get_session_history(conn, user_id=user_id, session_id=session_id, limit=50)
    conn.close()
    return {"session_id": session_id, "history": history}


@app.delete("/api/chat/history/{session_id}")
async def clear_chat_history(session_id: str, user_id: int = Depends(require_auth)):
    conn = get_conn()
    conn.execute("DELETE FROM conversation_memory WHERE session_id=? AND user_id=?", (session_id, user_id))
    conn.commit()
    conn.close()
    return {"success": True}


# ─── Chat with a PDF ───────────────────────────────────────────────────────
# Upload a document straight into a chat session as SCRATCH CONTEXT — not
# the case database. See brain/document_context.py's module docstring for
# exactly what "scratch" means here, and brain.py's document_intent routing
# for how a message with a document attached gets answered (document Q&A)
# vs. turned into a case review draft (extraction) vs. treated as an
# ordinary database query (neither).

@app.post("/api/chat/upload-document")
async def upload_chat_document(session_id: str = Query(...), file: UploadFile = File(...),
                                user_id: int = Depends(require_auth)):
    """
    Extracts a PDF's (or photo's) text and stores it against session_id —
    reuses ingestion_engine.extract_text_from_pdf()/extract_text_from_image(),
    the exact same extraction code the Cases.jsx upload flow uses. Nothing
    here writes to CaseMaster/Accused/Victim; that only ever happens via
    POST /api/ingest/confirm, and only after an officer reviews AND
    confirms a draft (see brain.py's _handle_document_extract() and
    frontend DocumentReviewCard.jsx).
    """
    suffix = os.path.splitext(file.filename or "")[1].lower()
    file_kind = "pdf" if suffix == ".pdf" else "image" if suffix in (".png", ".jpg", ".jpeg") else None
    if not file_kind:
        raise HTTPException(status_code=400, detail="Only PDF, PNG, or JPG files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        if file_kind == "pdf":
            extraction = ingestion_engine.extract_text_from_pdf(tmp_path)
        else:
            extraction = ingestion_engine.extract_text_from_image(tmp_path)
    finally:
        os.unlink(tmp_path)

    if not extraction.get("success") or not extraction.get("text", "").strip():
        raise HTTPException(status_code=400, detail=extraction.get("error")
                             or "Couldn't extract any text from this file — it may be a scanned "
                                "image with poor quality, or corrupted.")

    conn = get_conn()
    try:
        document_context.store_document(conn, user_id=user_id, session_id=session_id,
                                         filename=file.filename or "document",
                                         text=extraction["text"], extraction_engine=extraction.get("engine"))
    finally:
        conn.close()

    return {
        "success": True, "session_id": session_id, "filename": file.filename or "document",
        "char_count": len(extraction["text"]), "engine": extraction.get("engine"),
        "reliability_note": extraction.get("reliability_note"),
        "preview": extraction["text"][:400],
    }


@app.get("/api/chat/document/{session_id}")
async def get_chat_document(session_id: str, user_id: int = Depends(require_auth)):
    """Lets the frontend restore its 'document attached' chip — AND, if
    the officer already confirmed a save earlier in this session, the
    review card's 'Saved' confirmation too (see
    DocumentReviewCard.jsx's initialSaveResult prop and this session's
    own store-save-result endpoint below) — when a past session is
    reopened (see CrimeChat.jsx's loadSession()). Read-only, no side
    effects."""
    conn = get_conn()
    try:
        doc = document_context.get_document(conn, user_id=user_id, session_id=session_id)
    finally:
        conn.close()
    if not doc:
        return {"attached": False}
    return {"attached": True, "filename": doc["filename"], "char_count": doc["char_count"],
            "save_result": doc.get("save_result")}


class DocumentSaveResultRequest(BaseModel):
    save_result: dict


@app.post("/api/chat/document/{session_id}/save-result")
async def store_chat_document_save_result(session_id: str, req: DocumentSaveResultRequest,
                                           user_id: int = Depends(require_auth)):
    """
    Called by DocumentReviewCard.jsx immediately after a successful
    POST /api/ingest/confirm, so the outcome (fir_number, accused[],
    note) survives a page reload or switching chat sessions and back —
    without this, reopening a session where a case was already saved
    would show the blank edit form again instead of the "Saved — FIR
    ... is now live" confirmation (a reported bug). Purely a record of
    something that already happened; this endpoint itself never writes
    to the case database.
    """
    conn = get_conn()
    try:
        stored = document_context.store_save_result(conn, user_id=user_id, session_id=session_id,
                                                      save_result=req.save_result)
    finally:
        conn.close()
    return {"success": True, "stored": stored}


@app.delete("/api/chat/document/{session_id}")
async def clear_chat_document(session_id: str, user_id: int = Depends(require_auth)):
    conn = get_conn()
    try:
        removed = document_context.clear_document(conn, user_id=user_id, session_id=session_id)
    finally:
        conn.close()
    return {"success": True, "removed": removed}


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest, user_id: int = Depends(require_auth)):
    """
    Server-Sent Events counterpart to POST /api/chat — same brain
    pipeline (kavach_brain.process_query), same grounding guarantees,
    but the officer sees the reply appear token-by-token instead of
    waiting several seconds for the whole thing at once.

    HOW THE SAFETY GUARANTEE SURVIVES STREAMING: process_query() itself
    is completely unchanged in control flow. It's given an optional
    `stream_sink` callback; whenever it would call one of Ollama's
    *_streaming() compose functions, every token generated is pushed to
    stream_sink as a provisional "token" event AS IT ARRIVES — but the
    same grounding check that has always gated this brain's LLM output
    still runs on the FULL text before process_query returns. If it
    passes, a "confirm" event tells the frontend every token already
    shown is final. If it fails, a "retract" event tells the frontend to
    discard everything streamed so far, and process_query falls back to
    polish_response() exactly as the non-streaming endpoint always has
    — the corrected, safe text then arrives in the final "done" event.
    Nothing is ever shown as final until it has passed the exact same
    check the blocking endpoint has always required.

    process_query() runs on a background thread (it's synchronous, and
    partly blocking on local HTTP calls to Ollama) while this generator
    drains a queue.Queue the thread's stream_sink pushes into — a plain
    producer/consumer bridge, not a rewrite of the pipeline's control
    flow.

    Event frames are `data: <json>\\n\\n` (standard SSE). `event` types:
      meta    — sent once, immediately: session_id + everything about
                this turn EXCEPT the final text (intent, sql, pipeline
                trace, results, alias matches, network snapshot, etc.)
      token   — a piece of provisional reply text
      confirm — every token sent so far is final (no text payload)
      retract — discard every token sent so far (no text payload)
      done    — sent once, at the very end: the final text + response_source
                + notable_insight + document fields (same shape POST
                /api/chat returns, minus the fields already sent in `meta`)
      error   — something went wrong server-side; frontend should show a
                connection-error message, same as a failed POST /api/chat
    """
    session_id = req.session_id or f"sess_{uuid.uuid4().hex[:8]}"
    event_queue: "queue.Queue" = queue.Queue()
    _DONE = object()

    def run_pipeline():
        conn = get_conn()
        try:
            result = kavach_brain.process_query(
                conn, user_id=user_id, session_id=session_id,
                message=req.message, language=req.language or "en",
                stream_sink=event_queue.put,
            )
            event_queue.put({"type": "__result__", "result": result})
        except Exception as e:
            event_queue.put({"type": "error", "message": str(e)})
        finally:
            conn.close()
            event_queue.put(_DONE)

    thread = threading.Thread(target=run_pipeline, daemon=True)
    thread.start()

    def sse(event: str, data: dict) -> str:
        return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

    def event_generator():
        final_result = None
        streamed_any_token = False
        was_retracted = False
        while True:
            item = event_queue.get()
            if item is _DONE:
                break
            if item.get("type") == "__result__":
                final_result = item["result"]
                continue
            if item.get("type") == "error":
                yield sse("error", {"message": item.get("message", "Unknown error")})
                continue
            if item.get("type") == "token":
                streamed_any_token = True
            elif item.get("type") == "retract":
                was_retracted = True
            # token / confirm / retract — forwarded straight through
            yield sse(item.get("type", "token"), {k: v for k, v in item.items() if k != "type"})

        if final_result is None:
            yield sse("error", {"message": "The chat pipeline did not return a result."})
            return

        accused_ids = list({r["person_id"] for r in final_result["results"] if r.get("person_id")})[:10]
        fir_ids = list({r["fir_number"] for r in final_result["results"] if r.get("fir_number")})[:10]

        # 'meta' first — everything except the final text, so the
        # frontend can render the shell (intent label, panel results,
        # network snapshot) while tokens are still arriving.
        yield sse("meta", {
            "session_id": final_result["session_id"], "message": final_result["message"],
            "intent": final_result["intent"], "sql_generated": final_result["sql_generated"],
            "insights": final_result.get("insights"),
            "follow_up_suggestions": final_result["follow_up_suggestions"], "results": final_result["results"],
            "result_count": final_result["result_count"], "accused_ids": accused_ids, "fir_ids": fir_ids,
            "alias_matches": final_result["alias_matches"], "memory_recalled": final_result["memory_recalled"],
            "pipeline_trace": final_result["pipeline_trace"], "routed_engine": final_result["routed_engine"],
            "identity_reasoning_trace": final_result.get("identity_reasoning_trace"),
            "needs_clarification": final_result.get("needs_clarification", False),
            "network_snapshot": final_result.get("network_snapshot"),
            "document_attached": final_result.get("document_attached"),
            "document_draft": final_result.get("document_draft"),
        })

        # If the pipeline never streamed real tokens for what ended up as
        # the FINAL text (clarification / general knowledge / zero-result /
        # Ollama-unavailable / document-extract paths never touch
        # stream_sink at all — see process_query's docstring — and a
        # retracted stream falls back to a fresh, never-streamed
        # polish_response() call), fake-stream the already-final,
        # already-safe text word-by-word instead, so the frontend's
        # experience is consistent either way.
        if not (streamed_any_token and not was_retracted):
            text = final_result["interpretation"] or ""
            words = text.split(" ")
            for i, w in enumerate(words):
                chunk = (w + " ") if i < len(words) - 1 else w
                yield sse("token", {"text": chunk})

        yield sse("done", {
            "text": final_result["interpretation"], "response_source": final_result.get("response_source", "template"),
            "notable_insight": final_result.get("notable_insight"),
            "timestamp": final_result["timestamp"],
        })

    return StreamingResponse(event_generator(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache", "X-Accel-Buffering": "no",
    })


@app.get("/api/chat/export")
async def export_chat_pdf(scope: str = Query("login", pattern="^(login|all|session)$"),
                           session_id: Optional[str] = None,
                           authorization: Optional[str] = Header(None),
                           user_id: int = Depends(require_auth)):
    """
    Builds one combined PDF of the officer's chat history and returns it
    as a downloadable file.
      scope='session' + session_id  -> just that one conversation
      scope='login'                 -> everything since THIS login (used
                                        automatically right before logout)
      scope='all'                   -> the officer's entire chat history
    Kannada content renders correctly (see services/pdf_export.py) —
    this replaces the old client-side jsPDF export, which had no way to
    embed a Kannada-capable font and would have rendered Kannada chat
    turns as blank boxes.
    """
    conn = get_conn()
    try:
        user_row = conn.execute("""
            SELECT u.Username, e.FirstName FROM Users u
            LEFT JOIN Employee e ON u.EmployeeID = e.EmployeeID WHERE u.UserID=?
        """, (user_id,)).fetchone()
        officer_name = (user_row["FirstName"] if user_row and user_row["FirstName"] else None) or \
                       (user_row["Username"].title() if user_row else "Officer")

        if scope == "session" and session_id:
            turn_rows = conn.execute(
                "SELECT session_id, role, message_text, timestamp, full_response_json FROM conversation_memory "
                "WHERE user_id=? AND session_id=? ORDER BY turn_index ASC", (user_id, session_id)
            ).fetchall()
        elif scope == "login":
            token = (authorization or "").removeprefix("Bearer ").strip()
            since_ts = auth.get_session_login_time(conn, token)
            if since_ts:
                turn_rows = conn.execute(
                    "SELECT session_id, role, message_text, timestamp, full_response_json FROM conversation_memory "
                    "WHERE user_id=? AND timestamp>=? ORDER BY session_id ASC, turn_index ASC",
                    (user_id, since_ts)
                ).fetchall()
            else:
                turn_rows = []
        else:  # 'all'
            turn_rows = conn.execute(
                "SELECT session_id, role, message_text, timestamp, full_response_json FROM conversation_memory "
                "WHERE user_id=? ORDER BY session_id ASC, turn_index ASC", (user_id,)
            ).fetchall()

        # full_response (parsed from full_response_json) carries the
        # reasoning trace, network snapshot, and document draft for
        # assistant turns stored after that column existed — see
        # memory_engine.store_turn()'s docstring. None for user turns and
        # for any older assistant turn stored before it, both of which
        # pdf_export.py renders gracefully as bare text only.
        turns = []
        for r in turn_rows:
            full_response = None
            if r[4]:
                try:
                    full_response = json.loads(r[4])
                except (json.JSONDecodeError, TypeError):
                    full_response = None
            turns.append({"session_id": r[0], "role": r[1], "text": r[2], "timestamp": r[3],
                          "full_response": full_response})
    finally:
        conn.close()

    pdf_bytes = pdf_export.build_chat_history_pdf(officer_name, turns, scope=scope)
    filename = f"KAVACH-Chat-Export-{datetime.now().strftime('%Y%m%d-%H%M%S')}.pdf"
    return Response(content=pdf_bytes, media_type="application/pdf",
                     headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@app.post("/api/translate")
async def translate_text_endpoint(req: TranslateRequest, user_id: int = Depends(require_auth)):
    """
    Free-form translation for text OUTSIDE the fixed response templates
    (which already ship pre-translated — see brain/response_generator.py).
    Honest by design: if the local Ollama model isn't running,
    translation_available comes back False and `translated` is null —
    the frontend must show that plainly rather than silently leaving
    English text up under a Kannada label (see LanguageContext.jsx).
    """
    translated = ollama_client.translate_freeform(req.text, target_language=req.target_language or "kn")
    return {
        "original": req.text, "target_language": req.target_language or "kn",
        "translated": translated, "translation_available": translated is not None,
    }


# ─── FIR management ────────────────────────────────────────────────────────

@app.get("/api/fir")
async def search_fir(q: Optional[str] = None, district: Optional[str] = None,
                      crime_type: Optional[str] = None, status: Optional[str] = None,
                      year: Optional[str] = None, limit: int = Query(50, le=100), offset: int = 0,
                      user_id: int = Depends(require_auth)):
    where, params = ["1=1"], []
    if q:
        where.append("(fir_number LIKE ? OR crime_description LIKE ?)")
        params += [f"%{q}%", f"%{q}%"]
    if district:
        where.append("district=?"); params.append(district)
    if crime_type:
        where.append("crime_type=?"); params.append(crime_type)
    if status:
        where.append("status=?"); params.append(status)
    if year:
        where.append("strftime('%Y', registration_date)=?"); params.append(year)

    conn = get_conn()
    sql = f"""
        SELECT f.*, (SELECT COUNT(*) FROM Accused a WHERE a.CaseMasterID=f.fir_id) as accused_count
        FROM vw_fir_flat f WHERE {' AND '.join(where)}
        ORDER BY registration_date DESC LIMIT ? OFFSET ?
    """
    results = rows(conn.execute(sql, params + [limit, offset]))
    total = conn.execute(f"SELECT COUNT(*) FROM vw_fir_flat WHERE {' AND '.join(where)}", params).fetchone()[0]
    conn.close()
    return {"total": total, "results": results, "limit": limit, "offset": offset}


@app.get("/api/fir/{fir_number}")
async def get_fir_detail(fir_number: str, user_id: int = Depends(require_auth)):
    conn = get_conn()
    fir = conn.execute("SELECT * FROM vw_fir_flat WHERE fir_number=?", (fir_number,)).fetchone()
    if not fir:
        raise HTTPException(status_code=404, detail="FIR not found")
    fir_dict = dict(fir)
    case_id = fir_dict["fir_id"]

    accused = rows(conn.execute("""
        SELECT a.AccusedMasterID as accused_id, a.AccusedName as name, a.AgeYear as age, a.GenderID as gender,
               pi.RiskCategory as risk_category, pi.PersonIdentityID as person_id,
               CASE WHEN ars.ArrestSurrenderID IS NOT NULL THEN 1 ELSE 0 END as fa_arrested,
               COALESCE(ars.BailStatus, 'None') as bail_status
        FROM Accused a
        LEFT JOIN PersonIdentityLink pil ON a.AccusedMasterID=pil.AccusedMasterID
        LEFT JOIN PersonIdentity pi ON pil.PersonIdentityID=pi.PersonIdentityID
        LEFT JOIN ArrestSurrender ars ON ars.AccusedMasterID=a.AccusedMasterID
        WHERE a.CaseMasterID=?
    """, (case_id,)))
    for a in accused:
        a["role"] = "Main Accused"

    victims = rows(conn.execute(
        "SELECT VictimMasterID as victim_id, VictimName as name, AgeYear as age, GenderID as gender, "
        "'None' as injury_description, 'Unknown' as relation_to_accused FROM Victim WHERE CaseMasterID=?",
        (case_id,)
    ))

    updates_raw = conn.execute(
        "SELECT UpdateDate, UpdateText, OfficerName, Stage FROM InvestigationUpdate WHERE CaseMasterID=? ORDER BY UpdateDate DESC",
        (case_id,)
    ).fetchall()
    updates = [{"id": i, "update_date": u[0], "update_text": u[1], "officer_name": u[2], "stage": u[3]}
               for i, u in enumerate(updates_raw)]

    similar = rows(conn.execute("""
        SELECT fir_number, registration_date, crime_type, status, police_station
        FROM vw_fir_flat WHERE crime_type=? AND district=? AND fir_id!=?
        ORDER BY registration_date DESC LIMIT 5
    """, (fir_dict["crime_type"], fir_dict["district"], case_id)))

    conn.close()
    return {**fir_dict, "accused": accused, "victims": victims,
            "investigation_updates": updates, "similar_cases": similar}


# ─── Accused / offender profiles (PersonIdentity-backed) ─────────────────────

@app.get("/api/accused")
async def search_accused(q: Optional[str] = None, district: Optional[str] = None,
                          risk_category: Optional[str] = None, gang: Optional[str] = None,
                          repeat_only: bool = False, limit: int = Query(50, le=100), offset: int = 0,
                          user_id: int = Depends(require_auth)):
    where, params = ["1=1"], []
    if q:
        where.append("(name LIKE ? OR alias LIKE ? OR modus_operandi LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if district:
        where.append("district=?"); params.append(district)
    if risk_category:
        where.append("risk_category=?"); params.append(risk_category.upper())
    if gang:
        where.append("gang_affiliation LIKE ?"); params.append(f"%{gang}%")
    if repeat_only:
        where.append("is_repeat_offender=1")

    conn = get_conn()
    sql = f"""
        SELECT person_id as accused_id, name, alias, age, gender, district, occupation, education,
               risk_score, risk_category, modus_operandi, gang_affiliation, is_repeat_offender,
               prior_convictions, prior_convictions as total_cases
        FROM vw_person_flat WHERE {' AND '.join(where)}
        ORDER BY risk_score DESC LIMIT ? OFFSET ?
    """
    results = rows(conn.execute(sql, params + [limit, offset]))
    total = conn.execute(f"SELECT COUNT(*) FROM vw_person_flat WHERE {' AND '.join(where)}", params).fetchone()[0]
    conn.close()
    return {"total": total, "results": results}


@app.get("/api/accused/{accused_id}")
async def get_accused_profile(accused_id: int, user_id: int = Depends(require_auth)):
    conn = get_conn()
    acc = conn.execute("SELECT * FROM vw_person_flat WHERE person_id=?", (accused_id,)).fetchone()
    if not acc:
        raise HTTPException(status_code=404, detail="Accused not found")
    acc_dict = dict(acc)
    acc_dict["accused_id"] = acc_dict["person_id"]
    acc_dict["is_arrested"] = 1 if conn.execute(
        "SELECT COUNT(*) FROM ArrestSurrender ars JOIN PersonIdentityLink pil ON ars.AccusedMasterID=pil.AccusedMasterID WHERE pil.PersonIdentityID=?",
        (accused_id,)
    ).fetchone()[0] > 0 else 0

    firs = rows(conn.execute("""
        SELECT f.fir_number, f.registration_date, f.crime_type, f.district, f.police_station, f.status,
               'Suspect' as role
        FROM PersonIdentityLink pil
        JOIN Accused a ON pil.AccusedMasterID=a.AccusedMasterID
        JOIN vw_fir_flat f ON a.CaseMasterID=f.fir_id
        WHERE pil.PersonIdentityID=? ORDER BY f.registration_date DESC
    """, (accused_id,)))

    network = rows(conn.execute("""
        SELECT pi2.PersonIdentityID as connected_id, pi2.CanonicalName as connected_name,
               pi2.RiskCategory as risk_category, pi2.GangAffiliation as gang_affiliation,
               pnl.RelationshipType as relationship_type, pnl.Strength as strength
        FROM PersonNetworkLink pnl
        JOIN PersonIdentity pi2 ON pi2.PersonIdentityID = CASE WHEN pnl.PersonIdentityID_A=? THEN pnl.PersonIdentityID_B ELSE pnl.PersonIdentityID_A END
        WHERE pnl.PersonIdentityID_A=? OR pnl.PersonIdentityID_B=?
    """, (accused_id, accused_id, accused_id)))

    risk = risk_scoring.describe_existing_risk(
        risk_score=acc_dict["risk_score"], risk_category=acc_dict["risk_category"],
        prior_convictions=acc_dict["prior_convictions"], network_size=len(network),
        gang_affiliated=bool(acc_dict.get("gang_affiliation")),
    )
    risk.pop("headline", None)  # chat-facts-only field — not part of this REST response's contract

    # Current identity-confidence snapshot (see identity_confidence.py) —
    # whether this profile represents one consistent real person is a
    # SEPARATE question from how risky they are; surfaced here so an
    # officer sees both at a glance, including the "needs_review" flag
    # when linked records disagree with each other.
    id_confidence = identity_confidence.current_confidence(conn, accused_id)
    conn.close()
    return {**acc_dict, "fir_history": firs, "network_connections": network, "risk_assessment": risk,
            "identity_confidence": id_confidence}


@app.get("/api/accused/{accused_id}/identity-confidence")
async def get_identity_confidence(accused_id: int, user_id: int = Depends(require_auth)):
    """Full confidence trajectory for one identity (see
    identity_confidence.py) — current snapshot plus the complete
    history, so the UI can show confidence actually climbing (or
    dropping and flagging for review) as evidence accumulates over
    time, not just today's number."""
    conn = get_conn()
    exists = conn.execute("SELECT 1 FROM PersonIdentity WHERE PersonIdentityID=?", (accused_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail="Identity not found")
    current = identity_confidence.current_confidence(conn, accused_id)
    history = identity_confidence.confidence_history(conn, accused_id)
    conn.close()
    return {"person_identity_id": accused_id, "current": current, "history": history}


@app.get("/api/identity/needs-review")
async def list_identities_needing_review(limit: int = Query(50, le=200), user_id: int = Depends(require_auth)):
    """The actionable worklist: every identity whose linked records
    currently contain a contradiction (different father/spouse names,
    or an age progression that doesn't match the calendar gap between
    cases) — see identity_confidence.needs_review(). Empty list is the
    honest, good outcome, not an error."""
    conn = get_conn()
    flagged = identity_confidence.needs_review(conn, limit=limit)
    conn.close()
    return {"count": len(flagged), "identities": flagged}


@app.get("/api/accused/{accused_id}/network")
async def get_accused_network(accused_id: int, depth: int = Query(2, le=3), user_id: int = Depends(require_auth)):
    conn = get_conn()
    persons = conn.execute("SELECT PersonIdentityID, CanonicalName, RiskCategory, RiskScore, GangAffiliation, IsRepeatOffender FROM PersonIdentity").fetchall()
    edges_raw = conn.execute("SELECT PersonIdentityID_A, PersonIdentityID_B, RelationshipType, Strength FROM PersonNetworkLink").fetchall()
    conn.close()

    node_map = {r[0]: r for r in persons}
    G = graph_engine.build_graph(
        [{"id": str(r[0]), "type": "person", "label": r[1], "risk": r[2]} for r in persons],
        [{"source": str(a), "target": str(b), "relationship": rel} for a, b, rel, s in edges_raw],
    )
    visited = {str(accused_id)}
    frontier = {str(accused_id)}
    for _ in range(depth):
        nxt = set()
        for n in frontier:
            if n in G:
                nxt |= set(G.neighbors(n))
        frontier = nxt - visited
        visited |= frontier

    nodes = [{"data": {"id": str(pid), "label": r[1], "risk": r[2], "risk_score": r[3],
                        "gang": r[4] or "", "convictions": r[5]}}
             for pid, r in node_map.items() if str(pid) in visited]
    edges = [{"data": {"id": f"{a}-{b}", "source": str(a), "target": str(b),
                        "relationship": rel, "strength": s}}
              for a, b, rel, s in edges_raw if str(a) in visited and str(b) in visited]
    return {"nodes": nodes, "edges": edges, "center_id": str(accused_id)}


@app.get("/api/accused/{accused_id}/reasoning")
async def get_identity_reasoning(accused_id: int, user_id: int = Depends(require_auth)):
    """Standalone endpoint for the 'Why is this flagged as one person?'
    explainability panel — same trace-building code path used inline
    in chat responses, exposed directly for the profile page."""
    conn = get_conn()
    trace = kavach_brain._build_identity_reasoning_trace(conn, accused_id)
    conn.close()
    return trace


# ─── Analytics ────────────────────────────────────────────────────────────────

@app.get("/api/analytics/trends")
async def crime_trends(district: Optional[str] = None, crime_type: Optional[str] = None, year: Optional[int] = None):
    conn = get_conn()
    where, params = ["1=1"], []
    if district:
        where.append("d.DistrictName=?"); params.append(district)
    if crime_type:
        where.append("csh.CrimeHeadName=?"); params.append(crime_type)
    if year:
        where.append("ct.Year=?"); params.append(year)

    base = f"""FROM CrimeTrend ct
               JOIN District d ON ct.DistrictID=d.DistrictID
               JOIN CrimeSubHead csh ON ct.CrimeSubHeadID=csh.CrimeSubHeadID
               WHERE {' AND '.join(where)}"""
    monthly = rows(conn.execute(
        f"SELECT ct.Year as year, ct.Month as month, csh.CrimeHeadName as crime_type, "
        f"SUM(ct.CaseCount) as cases, SUM(ct.ArrestCount) as arrests {base} "
        f"GROUP BY ct.Year, ct.Month, csh.CrimeHeadName ORDER BY ct.Year, ct.Month", params))
    yearly = rows(conn.execute(
        f"SELECT ct.Year as year, SUM(ct.CaseCount) as total_cases, SUM(ct.ArrestCount) as total_arrests "
        f"{base} GROUP BY ct.Year ORDER BY ct.Year", params))
    by_crime = rows(conn.execute(
        f"SELECT csh.CrimeHeadName as crime_type, SUM(ct.CaseCount) as total {base} "
        f"GROUP BY csh.CrimeHeadName ORDER BY total DESC", params))
    conn.close()
    return {"monthly": monthly, "yearly": yearly, "by_crime_type": by_crime}


@app.get("/api/analytics/hotspots")
async def crime_hotspots(crime_type: Optional[str] = None):
    conn = get_conn()
    where, params = ["latitude IS NOT NULL"], []
    if crime_type:
        where.append("crime_type=?"); params.append(crime_type)
    hotspots = rows(conn.execute(f"""
        SELECT district, police_station, crime_type, COUNT(*) as case_count,
               AVG(latitude) as lat, AVG(longitude) as lng
        FROM vw_fir_flat WHERE {' AND '.join(where)}
        GROUP BY district, police_station, crime_type ORDER BY case_count DESC LIMIT 50
    """, params))
    conn.close()
    return {"hotspots": hotspots}


@app.get("/api/analytics/demographics")
async def demographics():
    conn = get_conn()
    age_groups = rows(conn.execute("""
        SELECT CASE WHEN age<21 THEN '18-20' WHEN age<31 THEN '21-30' WHEN age<41 THEN '31-40'
                    WHEN age<51 THEN '41-50' ELSE '51+' END as age_group, COUNT(*) as count, risk_category
        FROM vw_person_flat WHERE age IS NOT NULL GROUP BY age_group, risk_category ORDER BY age_group
    """))
    gender = rows(conn.execute("SELECT gender, COUNT(*) as count FROM vw_person_flat GROUP BY gender"))
    occupation = rows(conn.execute("""
        SELECT occupation, COUNT(*) as count FROM vw_person_flat WHERE occupation IS NOT NULL
        GROUP BY occupation ORDER BY count DESC LIMIT 10
    """))
    education = rows(conn.execute("""
        SELECT education, COUNT(*) as count FROM vw_person_flat WHERE education IS NOT NULL
        GROUP BY education ORDER BY count DESC
    """))
    conn.close()
    return {"age_groups": age_groups, "gender_distribution": gender,
            "top_occupations": occupation, "education_distribution": education}


@app.get("/api/analytics/district-summary")
async def district_summary():
    conn = get_conn()
    summary = rows(conn.execute("""
        SELECT district, COUNT(*) as total_cases,
               SUM(CASE WHEN status='Under Investigation' THEN 1 ELSE 0 END) as open_cases,
               SUM(CASE WHEN status='Charge-Sheeted' THEN 1 ELSE 0 END) as charge_sheeted,
               SUM(CASE WHEN status='Closed' THEN 1 ELSE 0 END) as closed
        FROM vw_fir_flat GROUP BY district ORDER BY total_cases DESC
    """))
    conn.close()
    return {"districts": summary}


# ─── Criminal network (global graph) ─────────────────────────────────────────

@app.get("/api/network/graph")
async def full_network_graph(limit: int = Query(100, le=300), user_id: int = Depends(require_auth)):
    conn = get_conn()
    top = rows(conn.execute("""
        SELECT PersonIdentityID as id, CanonicalName as label, RiskCategory as risk, RiskScore as risk_score,
               GangAffiliation as gang, IsRepeatOffender as convictions
        FROM PersonIdentity WHERE PersonIdentityID IN (
            SELECT DISTINCT PersonIdentityID_A FROM PersonNetworkLink
            UNION SELECT DISTINCT PersonIdentityID_B FROM PersonNetworkLink
        ) ORDER BY RiskScore DESC LIMIT ?
    """, (limit,)))
    node_ids = {t["id"] for t in top}
    nodes = [{"data": {"id": str(t["id"]), "label": t["label"], "risk": t["risk"],
                        "risk_score": t["risk_score"], "gang": t["gang"] or "Independent",
                        "convictions": t["convictions"]}} for t in top]

    raw_edges = conn.execute(f"""
        SELECT PersonIdentityID_A, PersonIdentityID_B, RelationshipType, Strength FROM PersonNetworkLink
        WHERE PersonIdentityID_A IN ({','.join('?'*len(node_ids))}) AND PersonIdentityID_B IN ({','.join('?'*len(node_ids))})
    """, list(node_ids) * 2).fetchall() if node_ids else []
    edges = [{"data": {"id": f"{a}-{b}", "source": str(a), "target": str(b),
                        "relationship": rel, "strength": s}} for a, b, rel, s in raw_edges]

    gangs = rows(conn.execute("""
        SELECT GangAffiliation as gang_affiliation, COUNT(*) as member_count, AVG(RiskScore) as avg_risk
        FROM PersonIdentity WHERE GangAffiliation IS NOT NULL GROUP BY GangAffiliation
    """))
    conn.close()
    return {"nodes": nodes, "edges": edges, "gangs": gangs, "total_nodes": len(nodes)}


@app.get("/api/network/gangs")
async def list_gangs(user_id: int = Depends(require_auth)):
    conn = get_conn()
    gangs = rows(conn.execute("""
        SELECT GangAffiliation as name, COUNT(*) as member_count, AVG(RiskScore) as avg_risk,
               GROUP_CONCAT(DISTINCT d.DistrictName) as districts, MAX(RiskScore) as max_risk
        FROM PersonIdentity pi LEFT JOIN District d ON pi.DistrictID=d.DistrictID
        WHERE GangAffiliation IS NOT NULL GROUP BY GangAffiliation ORDER BY avg_risk DESC
    """))
    conn.close()
    return {"gangs": gangs}


# ─── NEW: prediction, similarity, timeline, recommendations ─────────────────

@app.get("/api/predict")
async def predict_crime(district: str, crime_type: str, target_month: Optional[int] = None,
                         target_year: Optional[int] = None, user_id: int = Depends(require_auth)):
    conn = get_conn()
    did = conn.execute("SELECT DistrictID FROM District WHERE DistrictName=?", (district,)).fetchone()
    csh = conn.execute("SELECT CrimeSubHeadID FROM CrimeSubHead WHERE CrimeHeadName=?", (crime_type,)).fetchone()
    if not did or not csh:
        conn.close()
        raise HTTPException(status_code=404, detail="Unknown district or crime type")

    now = datetime.now()
    tm = target_month or ((now.month % 12) + 1)
    # Default target year: if no explicit month was given either, "next
    # month" naturally rolls into next year past December. If an
    # explicit month WAS given with no year, assume the next occurrence
    # of that month from today (so "predict March" in November means
    # next March, not five months in the past).
    if target_year:
        ty = target_year
    elif target_month is None:
        ty = now.year + (1 if now.month == 12 else 0)
    else:
        ty = now.year + (1 if target_month <= now.month else 0)

    # History strictly BEFORE the target month — see
    # prediction_tracking.py's module docstring for why this matters:
    # a forecast trained on data at-or-after its own target isn't a
    # forecast, it's a description, and would quietly inflate the
    # accuracy-tracking feature's own numbers.
    history_rows = conn.execute(
        """SELECT Year, Month, CaseCount FROM CrimeTrend WHERE DistrictID=? AND CrimeSubHeadID=?
           AND (Year < ? OR (Year = ? AND Month < ?)) ORDER BY Year, Month""",
        (did[0], csh[0], ty, ty, tm)
    ).fetchall()
    history = [{"year": r[0], "month": r[1], "count": r[2]} for r in history_rows]

    forecast = prediction_engine.forecast_next_month(history, target_month=tm)
    anomalies = prediction_engine.flag_anomalies(history)
    public_order = prediction_engine.public_order_forecast(history, target_month=tm)

    # Record this forecast for later accuracy comparison (see
    # brain/prediction_tracking.py) — idempotent, so repeatedly viewing
    # the same forecast never inflates or skews the accuracy record.
    # Also opportunistically settles any earlier predictions whose
    # target month now has real data on file, so the accuracy record
    # stays current without needing a separate manual step.
    record_result = prediction_tracking.record_prediction(
        conn, district_id=did[0], crime_subhead_id=csh[0], target_year=ty, target_month=tm,
        forecast=forecast, made_by=user_id,
    )
    newly_settled = prediction_tracking.settle_due_predictions(conn)
    conn.close()

    return {"district": district, "crime_type": crime_type, "target_month": tm, "target_year": ty,
            "forecast": forecast, "anomalies": anomalies, "public_order_forecast": public_order,
            "prediction_recorded": record_result,
            "newly_settled_elsewhere": newly_settled}


@app.get("/api/predict/accuracy")
async def prediction_accuracy(district: Optional[str] = None, crime_type: Optional[str] = None,
                               user_id: int = Depends(require_auth)):
    """
    The historical accuracy record for KAVACH's own crime-trend
    forecasts (see brain/prediction_tracking.py) — settles any newly-due
    predictions first, then returns the aggregate accuracy stats plus a
    recent-predictions table, optionally scoped to one district and/or
    crime type.

    HONESTY NOTE, surfaced here rather than buried in a docstring: this
    project's CrimeTrend history is placeholder/demonstration data (see
    the same disclaimer shown elsewhere in the app), and its month-to-
    month case counts are close to random rather than following a real
    seasonal/trend pattern — so the accuracy numbers here will look
    modest, which is the HONEST result of measuring a real forecasting
    method against data with little genuine signal to find, not a bug
    in the tracking mechanism itself. Swap in real KSP historical data
    (which does have genuine seasonal structure) and this exact same
    mechanism, unchanged, would show it.
    """
    conn = get_conn()
    did = csh = None
    if district:
        row = conn.execute("SELECT DistrictID FROM District WHERE DistrictName=?", (district,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Unknown district")
        did = row[0]
    if crime_type:
        row = conn.execute("SELECT CrimeSubHeadID FROM CrimeSubHead WHERE CrimeHeadName=?", (crime_type,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(status_code=404, detail="Unknown crime type")
        csh = row[0]

    newly_settled = prediction_tracking.settle_due_predictions(conn)
    summary = prediction_tracking.accuracy_summary(conn, district_id=did, crime_subhead_id=csh)
    recent = prediction_tracking.list_predictions(conn, district_id=did, crime_subhead_id=csh, limit=50)
    conn.close()

    return {
        "district": district, "crime_type": crime_type,
        "newly_settled": newly_settled,
        "summary": summary,
        "recent_predictions": recent,
        "data_note": ("Based on this project's seeded placeholder CrimeTrend data, not verified "
                       "real KSP historical records — see backend/import_real_dataset.py."),
    }


@app.get("/api/similarity/{fir_number}")
async def find_similar(fir_number: str, top_k: int = 5):
    conn = get_conn()
    target_row = conn.execute("""
        SELECT fir_id as case_id, fir_number, crime_type, weapon_used as weapon, vehicle_involved as vehicle,
               occurrence_time as time, police_station, crime_description as mo_text, offender_count
        FROM vw_fir_flat WHERE fir_number=?
    """, (fir_number,)).fetchone()
    if not target_row:
        conn.close()
        raise HTTPException(status_code=404, detail="FIR not found")
    target = dict(target_row)

    candidates = rows(conn.execute("""
        SELECT fir_id as case_id, fir_number, crime_type, weapon_used as weapon, vehicle_involved as vehicle,
               occurrence_time as time, police_station, crime_description as mo_text, district, registration_date
        FROM vw_fir_flat WHERE crime_type=? LIMIT 150
    """, (target["crime_type"],)))
    conn.close()

    matches = similarity_engine.find_similar_cases(target, candidates, top_k=top_k, min_score=20)
    signature = mo_fingerprint.build_signature(target)
    return {"target_fir": fir_number, "signature": signature, "matches": matches}


@app.get("/api/timeline/{fir_number}")
async def get_timeline(fir_number: str):
    conn = get_conn()
    case_row = conn.execute("SELECT fir_id, registration_date FROM vw_fir_flat WHERE fir_number=?", (fir_number,)).fetchone()
    if not case_row:
        conn.close()
        raise HTTPException(status_code=404, detail="FIR not found")
    updates = rows(conn.execute(
        "SELECT UpdateDate as update_date, UpdateText as update_text, OfficerName as officer_name "
        "FROM InvestigationUpdate WHERE CaseMasterID=?", (case_row["fir_id"],)
    ))
    conn.close()
    timeline = timeline_engine.build_timeline(updates, case_row["registration_date"])
    completeness = timeline_engine.timeline_completeness(timeline)
    return {"fir_number": fir_number, "timeline": timeline, "completeness": completeness}


@app.get("/api/recommendations/feedback-summary")
async def lead_feedback_summary(crime_type: Optional[str] = None, user_id: int = Depends(require_auth)):
    """
    Leaderboard of lead types by historical usefulness — see
    feedback_engine.crime_type_summary(). Empty list is the honest,
    expected result before any feedback has been recorded, not an
    error.

    IMPORTANT ROUTE-ORDERING NOTE: this static path MUST be registered
    before /api/recommendations/{fir_number} below — FastAPI/Starlette
    matches routes in registration order, so if the parameterised route
    came first, a request for this exact path would match it instead
    (with fir_number="feedback-summary") and 404 with "FIR not found"
    rather than ever reaching this function. That was a real bug here
    until this comment; if you add another static /api/recommendations/*
    route, it needs to go above the {fir_number} route too.
    """
    conn = get_conn()
    summary = feedback_engine.crime_type_summary(conn, crime_type=crime_type)
    conn.close()
    return {"crime_type": crime_type, "leads": summary}


@app.get("/api/recommendations/{fir_number}")
async def get_recommendations(fir_number: str, user_id: int = Depends(require_auth)):
    conn = get_conn()
    case_row = conn.execute("SELECT fir_id, crime_type, registration_date FROM vw_fir_flat WHERE fir_number=?",
                             (fir_number,)).fetchone()
    if not case_row:
        conn.close()
        raise HTTPException(status_code=404, detail="FIR not found")
    updates = rows(conn.execute(
        "SELECT UpdateDate as update_date, UpdateText as update_text, OfficerName as officer_name "
        "FROM InvestigationUpdate WHERE CaseMasterID=?", (case_row["fir_id"],)
    ))
    network_count = conn.execute("""
        SELECT COUNT(*) FROM PersonNetworkLink pnl
        JOIN PersonIdentityLink pil ON pnl.PersonIdentityID_A=pil.PersonIdentityID
        JOIN Accused a ON pil.AccusedMasterID=a.AccusedMasterID WHERE a.CaseMasterID=?
    """, (case_row["fir_id"],)).fetchone()[0]

    timeline = timeline_engine.build_timeline(updates, case_row["registration_date"])
    completeness = timeline_engine.timeline_completeness(timeline)
    # recommend_leads_with_stats() (not the plain recommend_leads()) —
    # each lead now also carries its historical "X% of officers found
    # this useful" track record (see feedback_engine.py) and leads are
    # re-ranked within their priority tier accordingly. Falls back
    # gracefully to the plain list (feedback stays all-neutral) for a
    # lead type nobody has judged yet — that's the expected, honest
    # state for a brand new feedback loop, not an error.
    leads = recommendation_engine.recommend_leads_with_stats(
        conn, {"crime_type": case_row["crime_type"]},
        timeline_gaps=completeness["stages_missing"], network_hit_count=network_count,
    )
    # What THIS officer (or a colleague) already recorded for THIS case
    # — lets the UI show "already marked" instead of re-asking.
    existing_feedback = {f["lead_key"]: f for f in feedback_engine.case_feedback(conn, fir_number)}
    conn.close()
    return {"fir_number": fir_number, "leads": leads, "timeline_completeness": completeness,
            "existing_feedback": existing_feedback}


class LeadFeedbackRequest(BaseModel):
    lead_key: str
    lead_text: str
    crime_type: str
    outcome: str  # 'useful' | 'not_useful' | 'inconclusive'
    notes: Optional[str] = None


@app.post("/api/recommendations/{fir_number}/feedback")
async def submit_lead_feedback(fir_number: str, req: LeadFeedbackRequest, user_id: int = Depends(require_auth)):
    """
    Records what actually happened when an officer acted on a
    recommended lead — see feedback_engine.py's module docstring for
    the full loop this closes. One record per (case, lead); recording
    again for the same case+lead updates the officer's earlier
    judgement rather than creating a duplicate.
    """
    conn = get_conn()
    case_exists = conn.execute("SELECT 1 FROM vw_fir_flat WHERE fir_number=?", (fir_number,)).fetchone()
    if not case_exists:
        conn.close()
        raise HTTPException(status_code=404, detail="FIR not found")
    result = feedback_engine.record_feedback(
        conn, fir_number=fir_number, lead_key=req.lead_key, crime_type=req.crime_type,
        lead_text=req.lead_text, outcome=req.outcome, officer_id=user_id, notes=req.notes,
    )
    conn.close()
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


class CaseNoteRequest(BaseModel):
    kind: str  # 'important_person' | 'unresolved_thread' | 'failed_lead' | 'general'
    note_text: str


@app.get("/api/cases/{fir_number}/briefing")
async def get_case_briefing(fir_number: str, user_id: int = Depends(require_auth)):
    """
    Institutional memory for one case — see case_memory.py's module
    docstring: dedicated case notes, checked-lead history
    (feedback_engine.py), and the investigation-update log, assembled
    into one briefing. This is the REST counterpart to asking KAVACH
    "what's already been investigated on this case" in chat (see
    brain.py's _handle_case_briefing()) — same underlying data, same
    rendering function, so the two can never drift apart.
    """
    conn = get_conn()
    briefing = case_memory.case_briefing(conn, fir_number)
    conn.close()
    if not briefing.get("found"):
        raise HTTPException(status_code=404, detail="FIR not found")
    return briefing


@app.get("/api/cases/{fir_number}/notes")
async def list_case_notes(fir_number: str, kind: Optional[str] = None, user_id: int = Depends(require_auth)):
    conn = get_conn()
    notes = case_memory.list_notes(conn, fir_number, kind=kind)
    conn.close()
    return {"fir_number": fir_number, "notes": notes}


@app.post("/api/cases/{fir_number}/notes")
async def add_case_note(fir_number: str, req: CaseNoteRequest, user_id: int = Depends(require_auth)):
    """
    Leaves a note for whoever picks this case up next — see
    case_memory.py's module docstring for why this is scoped to the
    CASE, never the officer: the entire point is that it's still there
    after a transfer to someone else.
    """
    conn = get_conn()
    case_exists = conn.execute("SELECT 1 FROM vw_fir_flat WHERE fir_number=?", (fir_number,)).fetchone()
    if not case_exists:
        conn.close()
        raise HTTPException(status_code=404, detail="FIR not found")
    officer_row = conn.execute("""
        SELECT u.Username, e.FirstName FROM Users u
        LEFT JOIN Employee e ON u.EmployeeID = e.EmployeeID WHERE u.UserID=?
    """, (user_id,)).fetchone()
    officer_name = (officer_row["FirstName"] if officer_row and officer_row["FirstName"] else None) or \
                   (officer_row["Username"].title() if officer_row else None)
    result = case_memory.add_note(conn, fir_number, req.kind, req.note_text,
                                   officer_id=user_id, officer_name=officer_name)
    conn.close()
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["reason"])
    return result


@app.patch("/api/cases/{fir_number}/notes/{note_id}/resolve")
async def resolve_case_note(fir_number: str, note_id: int, resolved: bool = True,
                             user_id: int = Depends(require_auth)):
    """Marks an 'unresolved_thread' note resolved (or reopens it) —
    never deletes it, so the fact that something WAS open (and roughly
    when it closed) stays visible to whoever looks at this case later."""
    conn = get_conn()
    ok = case_memory.resolve_note(conn, note_id, resolved=resolved)
    conn.close()
    if not ok:
        raise HTTPException(status_code=404, detail="Note not found")
    return {"success": True, "resolved": resolved}


@app.get("/api/case-summary/{fir_number}")
async def get_case_summary(fir_number: str, user_id: int = Depends(require_auth)):
    """
    One-click AI case summary — Timeline -> Suspects -> Victims ->
    Evidence gaps -> Open leads -> Recommendations, in one response.
    This is a COMPOSITION of already-tested modules (timeline_engine,
    recommendation_engine, similarity_engine, mo_fingerprint), not new
    inference logic — which is exactly why it's safe to ship quickly.
    """
    conn = get_conn()
    fir = conn.execute("SELECT * FROM vw_fir_flat WHERE fir_number=?", (fir_number,)).fetchone()
    if not fir:
        conn.close()
        raise HTTPException(status_code=404, detail="FIR not found")
    fir_dict = dict(fir)
    case_id = fir_dict["fir_id"]

    accused = rows(conn.execute("""
        SELECT a.AccusedName as name, a.AgeYear as age, pi.RiskCategory as risk_category,
               pi.PersonIdentityID as person_id, pi.IsRepeatOffender as is_repeat_offender
        FROM Accused a LEFT JOIN PersonIdentityLink pil ON a.AccusedMasterID=pil.AccusedMasterID
        LEFT JOIN PersonIdentity pi ON pil.PersonIdentityID=pi.PersonIdentityID
        WHERE a.CaseMasterID=?
    """, (case_id,)))
    victims = rows(conn.execute("SELECT VictimName as name, AgeYear as age, GenderID as gender FROM Victim WHERE CaseMasterID=?", (case_id,)))
    updates = rows(conn.execute(
        "SELECT UpdateDate as update_date, UpdateText as update_text, OfficerName as officer_name "
        "FROM InvestigationUpdate WHERE CaseMasterID=?", (case_id,)
    ))
    network_count = conn.execute("""
        SELECT COUNT(*) FROM PersonNetworkLink pnl
        JOIN PersonIdentityLink pil ON pnl.PersonIdentityID_A=pil.PersonIdentityID
        JOIN Accused a ON pil.AccusedMasterID=a.AccusedMasterID WHERE a.CaseMasterID=?
    """, (case_id,)).fetchone()[0]

    candidates = rows(conn.execute("""
        SELECT fir_id as case_id, fir_number, crime_type, weapon_used as weapon, vehicle_involved as vehicle,
               occurrence_time as time, police_station, crime_description as mo_text
        FROM vw_fir_flat WHERE crime_type=? AND fir_id!=? LIMIT 100
    """, (fir_dict["crime_type"], case_id)))
    conn.close()

    target_case = {"case_id": case_id, "crime_type": fir_dict["crime_type"], "weapon": fir_dict["weapon_used"],
                    "vehicle": fir_dict["vehicle_involved"], "time": fir_dict["occurrence_time"],
                    "police_station": fir_dict["police_station"], "mo_text": fir_dict["crime_description"]}
    signature = mo_fingerprint.build_signature(target_case)
    similar = similarity_engine.find_similar_cases(target_case, candidates, top_k=3, min_score=25)

    timeline = timeline_engine.build_timeline(updates, fir_dict["registration_date"])
    completeness = timeline_engine.timeline_completeness(timeline)
    leads = recommendation_engine.recommend_leads(
        {"crime_type": fir_dict["crime_type"]}, timeline_gaps=completeness["stages_missing"],
        network_hit_count=network_count,
    )

    return {
        "fir_number": fir_number, "crime_type": fir_dict["crime_type"], "district": fir_dict["district"],
        "status": fir_dict["status"], "brief_facts": fir_dict["crime_description"],
        "timeline": timeline, "timeline_completeness": completeness,
        "accused": accused, "victims": victims, "mo_signature": signature,
        "similar_cases": similar, "recommended_leads": leads[:6],
        "generated_at": datetime.now().isoformat(),
    }


# ─── NEW: document ingestion ──────────────────────────────────────────────────

@app.post("/api/ingest/document")
async def ingest_document(file: UploadFile = File(...), user_id: int = Depends(require_auth)):
    suffix = os.path.splitext(file.filename or "")[1].lower()
    file_kind = "pdf" if suffix == ".pdf" else "image" if suffix in (".png", ".jpg", ".jpeg") else None
    if not file_kind:
        raise HTTPException(status_code=400, detail="Only PDF, PNG, or JPG files are supported")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        result = ingestion_engine.ingest_document(tmp_path, file_kind)
    finally:
        os.unlink(tmp_path)
    return result


@app.post("/api/ingest/confirm")
async def confirm_ingest(req: IngestConfirmRequest, user_id: int = Depends(require_auth)):
    """
    THE missing second half of document ingestion: writes the
    investigator-reviewed-and-corrected draft into CaseMaster, Accused,
    and Victim, and runs every new accused through the same identity
    resolution + risk scoring used at bulk-seed time — see
    brain/ingestion_engine.py.commit_draft(). Never called automatically;
    only ever fires when the officer explicitly confirms the form in the
    UI (see Cases.jsx's UploadModal).
    """
    conn = get_conn()
    try:
        user_row = conn.execute("SELECT EmployeeID FROM Users WHERE UserID=?", (user_id,)).fetchone()
        employee_id = user_row[0] if user_row and user_row[0] else None
        if employee_id is None:
            fallback = conn.execute("SELECT EmployeeID FROM Employee LIMIT 1").fetchone()
            employee_id = fallback[0] if fallback else None

        payload = req.model_dump()
        result = ingestion_engine.commit_draft(conn, payload, confirmed_by_employee_id=employee_id)
    finally:
        conn.close()

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Ingestion failed"))
    return result


# ─── NEW: investigator working context ───────────────────────────────────────

@app.get("/api/context")
async def get_working_context(user_id: int = Depends(require_auth)):
    conn = get_conn()
    ctx = memory_engine.get_context(conn, user_id)
    conn.close()
    return ctx


# ─── Meta / health ─────────────────────────────────────────────────────────────

@app.get("/api/meta/districts")
async def list_districts():
    conn = get_conn()
    d = [r[0] for r in conn.execute("SELECT DistrictName FROM District ORDER BY DistrictName").fetchall()]
    conn.close()
    return {"districts": d}


@app.get("/api/meta/crime-types")
async def list_crime_types():
    conn = get_conn()
    c = [r[0] for r in conn.execute("SELECT CrimeHeadName FROM CrimeSubHead ORDER BY CrimeHeadName").fetchall()]
    conn.close()
    return {"crime_types": c}


@app.get("/api/meta/police-stations")
async def list_police_stations(district: Optional[str] = None):
    """Powers the district -> police-station cascading dropdown in the
    document-ingestion confirm form (a PDF/photo can only guess the
    district as free text; committing a case needs a real UnitID)."""
    conn = get_conn()
    if district:
        result = rows(conn.execute("""
            SELECT u.UnitID as id, u.UnitName as name, d.DistrictName as district
            FROM Unit u JOIN District d ON u.DistrictID = d.DistrictID
            WHERE d.DistrictName = ? ORDER BY u.UnitName
        """, (district,)))
    else:
        result = rows(conn.execute("""
            SELECT u.UnitID as id, u.UnitName as name, d.DistrictName as district
            FROM Unit u JOIN District d ON u.DistrictID = d.DistrictID
            ORDER BY d.DistrictName, u.UnitName
        """))
    conn.close()
    return {"police_stations": result}


@app.get("/api/meta/crime-subheads")
async def list_crime_subheads():
    """Crime sub-heads WITH their IDs (unlike /api/meta/crime-types,
    which only returns names for chat-query filtering) — the ingestion
    confirm form needs the actual CrimeSubHeadID to commit a case."""
    conn = get_conn()
    result = rows(conn.execute("""
        SELECT csh.CrimeSubHeadID as id, csh.CrimeHeadName as name,
               ch.CrimeHeadID as major_head_id, ch.CrimeGroupName as major_head_name
        FROM CrimeSubHead csh JOIN CrimeHead ch ON csh.CrimeHeadID = ch.CrimeHeadID
        ORDER BY ch.CrimeGroupName, csh.CrimeHeadName
    """))
    conn.close()
    return {"crime_subheads": result}


@app.get("/api/meta/case-statuses")
async def list_case_statuses():
    conn = get_conn()
    result = rows(conn.execute(
        "SELECT CaseStatusID as id, CaseStatusName as name FROM CaseStatusMaster ORDER BY CaseStatusID"
    ))
    conn.close()
    return {"case_statuses": result}


@app.get("/api/health")
async def health():
    try:
        conn = get_conn()
        count = conn.execute("SELECT COUNT(*) FROM CaseMaster").fetchone()[0]
        conn.close()
        return {"status": "ok", "db": "connected", "fir_records": count, "schema": "ksp_compliant_v2",
                "catalyst_cache": catalyst_adapter.status()}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@app.get("/api/analytics/hotspot-forecast")
async def analytics_hotspot_forecast(top_n: int = Query(15, ge=1, le=30),
                                      user_id: int = Depends(require_auth)):
    """
    'Projected hotspots, next 30 days' — a linear-trend/seasonal
    projection over this project's own seeded CrimeTrend history (see
    brain/hotspot_forecast.py and prediction_engine.py for exactly how,
    and their docstrings for why this is honestly a statistical
    projection, not a machine-learning model). Feeds the Analytics page
    heatmap's "Projected" toggle.
    """
    conn = get_conn()
    try:
        results = hotspot_forecast.compute(conn, top_n=top_n)
    finally:
        conn.close()
    return {"forecast_period": "next_30_days", "method": "linear trend + seasonal adjustment "
            "over this project's seeded CrimeTrend history (see prediction_engine.py)",
            "hotspots": results}


@app.get("/api/analytics/ncrb-benchmark")
async def analytics_ncrb_benchmark(user_id: int = Depends(require_auth)):
    """
    Real, sourced, published NCRB Karnataka figures alongside this
    project's own seeded (synthetic) aggregate numbers, for honest
    side-by-side context — see services/ncrb_reference.py's module
    docstring for exactly what this is and, importantly, what it is not.
    """
    conn = get_conn()
    try:
        return ncrb_reference.compare_with_seeded_data(conn)
    finally:
        conn.close()


@app.get("/api/admin/audit-log")
async def admin_audit_log(limit: int = Query(200, ge=1, le=1000),
                           user_id_filter: Optional[int] = Query(None),
                           user_id: int = Depends(require_admin)):
    """Admin/supervisor-only — 'every query is logged: who asked what,
    when.' See services/audit_log.py."""
    conn = get_conn()
    try:
        entries = audit_log.fetch(conn, limit=limit, user_id_filter=user_id_filter)
    finally:
        conn.close()
    return {"count": len(entries), "entries": entries}


@app.get("/")
async def root():
    return {"message": "KAVACH API v2 — Karnataka State Police Intelligence Platform",
            "docs": "/api/docs"}


if __name__ == "__main__":
    # Mirrors Zoho's own confirmed AppSail Python pattern (their Flask
    # example calls app.run(host='0.0.0.0', port=listen_port) reading
    # X_ZOHO_CATALYST_LISTEN_PORT) — same idea, translated to FastAPI +
    # uvicorn. app-config.json's "command" is just "python main.py", so
    # this block IS the AppSail entry point in production; falls back to
    # 8000 for local/plain dev where that env var isn't set.
    import uvicorn
    port = int(os.getenv("X_ZOHO_CATALYST_LISTEN_PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)
