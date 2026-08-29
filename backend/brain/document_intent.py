"""
KAVACH Brain — Document-Chat Intent Detection
=================================================
Small, explainable pattern set that decides — ONLY when a PDF/photo is
already attached to the current chat session (see document_context.py)
— whether a message is:

  'extract'   a request to pull the document into a case REVIEW DRAFT.
              Covers both plain extraction language ("extract this into
              a case") and database-commit language ("put it in the
              database", "save this to the database"). Both are handled
              IDENTICALLY on purpose: neither one ever writes to
              CaseMaster/Accused/Victim from chat. commit_draft() is
              only ever called from main.py's /api/ingest/confirm, and
              that endpoint is only ever called when an officer clicks
              "Confirm & Save" on the rendered review card — see
              brain.py's _handle_document_extract() and this module's
              `explicit_commit` flag, which only changes the WORDING of
              the reply (making the "you still need to confirm" framing
              more prominent when the officer used commit-flavoured
              language), never the behaviour.

  'query'     a question ABOUT the document's content, answered from its
              extracted text via Ollama (see
              ollama_client.answer_from_document()) — never the case
              database, and never confused with a verified database
              fact (response_source="document_grounded" downstream).

  None        nothing document-specific matched — treat the message as
              an ordinary case-database query, exactly as if no document
              were attached. This keeps an attached PDF from silently
              hijacking a real query like "show repeat offenders in
              Mysuru" just because a file happens to be sitting in the
              session.

Deliberately pattern-based rather than routed through the general
intent_engine.py — a document being attached is session STATE, not a
property of the sentence alone, so it gets its own small, explainable
classifier layered in front of the normal pipeline (see brain.py).
"""
import re

_COMMIT_PATTERNS = [
    r'\bput (it|this|that) (in|into) the database\b',
    r'\badd (this|it|that) to the database\b',
    r'\bsave (this|it|that) to the database\b',
    r'\bstore (this|it|that) in the database\b',
    r'\bcommit (this|it|that)\b',
    r'\bfile (this|it) into the database\b',
]

_EXTRACT_PATTERNS = [
    r'\bextract (this|it|that)( document| file| pdf)?( into| as)? a case\b',
    r'\bextract (this|it|that) (document|file|pdf)\b',
    r'\bconvert (this|it|that) (into|to) a case\b',
    r'\bturn (this|it|that) into a case\b',
    r'\bmake (this|it|that) a case\b',
    r'\bcreate a case (out of|from) (this|it|that)\b',
    r'\bfile (this|it|that) as a case\b',
    r'\bpull (this|it|that) into (a )?(review|case)\b',
    r'\bstart (a )?(case|ingestion) from (this|it|that)\b',
]

_QUERY_PATTERNS = [
    r'\bthis (document|file|pdf|report)\b',
    r'\b(in|from|on) (this|the attached|the uploaded)\b',
    r'\bsummari[sz]e (this|it)\b',
    r'\bsummary of (this|it)\b',
    r'\bwhat does (this|it) say\b',
    r"\bwhat'?s in (this|it)\b",
    r'\baccording to (this|it|the document)\b',
    r'\bthe (attached|uploaded) (file|document|pdf)\b',
    r'\bdoes (this|it) mention\b',
]


def classify(message: str, has_any_entity: bool) -> dict:
    """
    Returns {"mode": "extract"|"query"|None, "explicit_commit": bool,
    "matched_pattern": str|None}.

    `has_any_entity` should be the SAME has_any_entity_early flag
    brain.py already computes (districts/crime_types/names/dates/FIR
    number detected) — it drives the conservative no-signal fallback
    below, so a message that clearly names a district or crime type is
    never assumed to be about the document.
    """
    t = " ".join((message or "").lower().split())

    for p in _COMMIT_PATTERNS:
        if re.search(p, t):
            return {"mode": "extract", "explicit_commit": True, "matched_pattern": p}
    for p in _EXTRACT_PATTERNS:
        if re.search(p, t):
            return {"mode": "extract", "explicit_commit": False, "matched_pattern": p}
    for p in _QUERY_PATTERNS:
        if re.search(p, t):
            return {"mode": "query", "explicit_commit": False, "matched_pattern": p}

    # Conservative fallback: a document is attached, the message carries
    # NO case-database signal at all (no district/crime type/name/date/
    # FIR number), and it's more than a one-word reply — the most likely
    # target of an otherwise generic question ("what happened here?",
    # "who's involved?") is the document just uploaded, not an unscoped
    # trawl of the whole case database. Mirrors this codebase's existing
    # "when in doubt, don't guess at the database — but do use the
    # context that's actually in front of you" stance.
    word_count = len(t.split())
    if not has_any_entity and word_count >= 2:
        return {"mode": "query", "explicit_commit": False,
                "matched_pattern": "no case-data signal, document attached — assumed about the document"}

    return {"mode": None, "explicit_commit": False, "matched_pattern": None}
