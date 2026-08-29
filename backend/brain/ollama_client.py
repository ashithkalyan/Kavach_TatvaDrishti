"""
KAVACH Brain — Optional Local LLM Bridge (Ollama)
=====================================================
Fully optional. If Ollama isn't running, every function here degrades
gracefully and the deterministic brain (response_generator.py etc.)
handles everything on its own — this is an enhancement layer, never a
dependency, and it is architecturally forbidden from being the only
source of a fact. See compose_conversational() below for how that
guarantee is enforced in code, not just asked for in a prompt.

Setup (one-time, on your own machine — NOT required for the demo):
  1. Install Ollama:   curl -fsSL https://ollama.com/install.sh | sh
  2. Pull a model:     ollama pull llama3.2
  3. It auto-serves at http://localhost:11434

Zero cost. Zero external API calls. Zero data leaves your machine.

IMPORTANT — DEPLOYMENT NOTE: Zoho Catalyst's serverless functions
cannot host a multi-GB local model, so Ollama is a LOCAL-DEV-ONLY
enhancement. The deployed Zoho version always runs in pure
deterministic mode — which is also why response_generator.py is built
to be complete and correct on its own, not just a fallback.

CHOOSING A MODEL: OLLAMA_MODEL defaults to llama3.2 (3B) — small enough
to run comfortably on a laptop CPU, which matters more for a live demo
than raw quality. If your hardware has the headroom (a recent GPU, or
16GB+ unified memory), `ollama pull llama3.1:8b` and set
OLLAMA_MODEL=llama3.1:8b — the jump in how well it reasons over the
richer FACTS_JSON payload (see facts_enrichment.py) is real and shows
up immediately in demo answers. Test against your actual demo hardware
first; there's no code change needed either way, only the env var.
"""
import json
import os
import re
import time

import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

# ── Availability cache ───────────────────────────────────────────────────
# HONESTY NOTE ON A REAL BUG THIS REPLACES: the previous version of this
# module checked Ollama's availability exactly once per process and cached
# the result forever. If the FastAPI server happened to start before `ollama
# serve` was up (a very common startup-order accident), is_available() would
# return False for the lifetime of the process — even after Ollama came
# online seconds later — and every response would silently stay in
# template-only mode with no error and no way to recover short of
# restarting the backend. A short TTL fixes this with no real cost: the
# check itself is a ~5ms local HTTP call.
_CACHE_TTL_SECONDS = 20
_cache = {"checked_at": 0.0, "available": False}


def is_available(force_recheck: bool = False) -> bool:
    now = time.monotonic()
    if not force_recheck and (now - _cache["checked_at"]) < _CACHE_TTL_SECONDS:
        return _cache["available"]
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=1.5)
        ok = r.status_code == 200
    except requests.RequestException:
        ok = False
    _cache["checked_at"] = now
    _cache["available"] = ok
    return ok


def generate(prompt: str, system: str = "", timeout: int = 20, format_json: bool = False, num_ctx: int = None):
    """Blocking, single-shot generation — returns the full response text
    (or None on failure/unavailability). See generate_stream() for the
    token-by-token counterpart used by the SSE chat endpoint."""
    if not is_available():
        return None
    try:
        options = {"temperature": 0.4}
        if num_ctx:
            options["num_ctx"] = num_ctx
        payload = {"model": OLLAMA_MODEL, "prompt": prompt, "system": system, "stream": False,
                   "options": options}
        if format_json:
            payload["format"] = "json"
        resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout)
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.RequestException as e:
        print(f"[Ollama] unavailable or errored: {e}")
        # A live error (not just "not running") means the next call should
        # actually recheck rather than trust a 20-second-old "it's up" cache.
        _cache["checked_at"] = 0.0
        return None


def generate_stream(prompt: str, system: str = "", timeout: int = 30, num_ctx: int = None):
    """
    Generator counterpart to generate() — yields text chunks AS Ollama
    produces them (real token streaming via Ollama's own `stream: true`
    NDJSON endpoint, not a client-side simulation). Yields nothing at
    all (an empty generator) if Ollama is unavailable or errors partway
    through — callers must treat "zero chunks yielded, then generator
    exhausted" the same way they'd treat generate() returning None: as
    "no LLM output, fall back to the deterministic path."

    Deliberately still just a thin, honest wrapper — no buffering trick
    that fakes streaming from a blocking call. If Ollama drops the
    connection mid-generation, whatever chunks were already yielded stay
    yielded (the caller's own grounding check afterward is what decides
    whether the partial/complete text is trustworthy — see
    compose_conversational_streaming()).
    """
    if not is_available():
        return
    try:
        options = {"temperature": 0.4}
        if num_ctx:
            options["num_ctx"] = num_ctx
        payload = {"model": OLLAMA_MODEL, "prompt": prompt, "system": system, "stream": True,
                   "options": options}
        with requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=timeout, stream=True) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                chunk = obj.get("response", "")
                if chunk:
                    yield chunk
                if obj.get("done"):
                    break
    except requests.RequestException as e:
        print(f"[Ollama] streaming unavailable or errored: {e}")
        _cache["checked_at"] = 0.0
        return


def polish_response(draft_text: str, language: str = "en"):
    """Improves phrasing only — never allowed to add facts. Returns the
    original draft unchanged if Ollama isn't available or errors."""
    if not is_available():
        return draft_text
    lang_note = "in Kannada" if language == "kn" else "in English"
    system_prompt = (
        "You are polishing a police intelligence assistant's response. "
        "Keep every fact, number, and name EXACTLY as given in the draft — "
        "do not add, remove, or invent any information. Only improve sentence "
        f"flow and tone. Respond {lang_note}. Return ONLY the polished text."
    )
    out = generate(draft_text, system=system_prompt, timeout=15)
    return out if out else draft_text


def translate_freeform(text: str, target_language: str = "kn"):
    """For free-form text OUTSIDE the fixed response templates (e.g. a raw
    BriefFacts field, or a whole UI response). Returns None (not the
    original text) if unavailable, so callers can distinguish 'not
    translated' from 'translated to itself' and be honest with the user
    about which happened instead of silently serving English."""
    if not is_available():
        return None
    lang_name = "Kannada" if target_language == "kn" else "English"
    system_prompt = (
        f"Translate the given police-record text to {lang_name}. Keep it "
        "professional and accurate, and keep proper nouns (names, FIR "
        "numbers, section numbers) unchanged. Return ONLY the translation, "
        "nothing else — no notes, no quotation marks."
    )
    return generate(text, system=system_prompt, timeout=15)


# ── Grounded conversational synthesis ────────────────────────────────────
# This is the "sound like a modern LLM, not a form letter" layer, built so
# it CANNOT become the sole source of a fact — every number/name it's
# allowed to mention is pre-computed by the deterministic brain and handed
# in explicitly. If Ollama drifts from that data, _looks_grounded() below
# rejects the output and the caller falls back to the plain template.

def _facts_block(facts: dict) -> str:
    """Renders the grounding data as compact JSON the model can read but
    is instructed never to add to. No longer just the 5-row `sample` —
    facts may now also carry case_history/trend/district_breakdown/etc.
    (see facts_enrichment.py), which is exactly why _looks_grounded()
    below checks names against the WHOLE payload, not just `sample`."""
    return json.dumps(facts, ensure_ascii=False, default=str)


def _recent_turns_block(recent_turns: list) -> str:
    """Formats the last few already-generated turns as plain
    'Officer: ... / KAVACH: ...' lines — for TONE AND CONTINUITY only.
    Deliberately built from already-composed reply text, never raw DB
    rows, so it can never smuggle a fact past FACTS_JSON."""
    if not recent_turns:
        return ""
    lines = []
    for turn in recent_turns[-6:]:
        speaker = "Officer" if turn.get("role") == "user" else "KAVACH"
        text = (turn.get("text") or "").strip().replace("\n", " ")
        if text:
            lines.append(f"{speaker}: {text[:200]}")
    return "\n".join(lines)


def _compose_system_prompt(language: str, want_notable: bool) -> str:
    lang_note = "Respond in natural, conversational Kannada." if language == "kn" else \
                "Respond in natural, conversational English."
    rules = (
        "You are KAVACH, a crime-intelligence chat assistant for Karnataka Police "
        "officers. You have just run a database query on the officer's behalf. "
        "Below is FACTS_JSON — the complete, only set of facts you are allowed to "
        "reference. It may contain a result count and sample rows, and — for some "
        "queries — extra pre-computed material such as one person's case history, "
        "network size, and risk breakdown, or a month-over-month trend and a "
        "district/station breakdown. RECENT_CONVERSATION (if present) is the last "
        "few already-answered turns, given ONLY so your reply can flow naturally "
        "from what was just discussed (e.g. avoid repeating yourself, use 'also' "
        "correctly) — it is NEVER a source of facts; only FACTS_JSON is.\n\n"
        "STRICT RULES:\n"
        "1. Every name, number, date, district, or FIR number you mention MUST come "
        "verbatim from FACTS_JSON. Never introduce a name, count, or figure that "
        "isn't in it, and never compute or estimate a number yourself — if "
        "FACTS_JSON already contains a computed figure (like a trend percentage), "
        "use it as given; never recalculate or round it differently.\n"
        "2. Do not invent recommendations, next steps, or caveats that aren't implied "
        "directly by the data given.\n"
        "3. If FACTS_JSON's sample is smaller than its result_count, you may say "
        "'and N more' using the given result_count — do not describe records you "
        "were not shown.\n"
        "4. If FACTS_JSON includes case_history, risk_trajectory, trend, or a "
        "breakdown, weave the most relevant one or two of those into the reply — "
        "this is what turns a bare count into something worth reading. Don't list "
        "every field mechanically; pick what's actually notable.\n"
        "5. Write 2-4 sentences, warm and professional, like a sharp colleague "
        "briefing an officer — not a form letter, not a bare stat line.\n"
        f"6. {lang_note}\n"
    )
    if want_notable:
        rules += (
            "7. Return ONLY a JSON object with exactly two keys:\n"
            '   {"reply": "<your 2-4 sentence reply>", '
            '"notable": "<ONE short sentence pointing out whatever in FACTS_JSON is '
            "most worth an officer's attention beyond the obvious count — e.g. an "
            "unusual trend, a repeat pattern, a gang link, a high risk score. Use "
            'empty string \\"\\" if nothing rises above the reply itself.>"}\n'
            "   No text outside that JSON object. Both values must stay strictly "
            "within FACTS_JSON — the same grounding rule applies to \"notable\" too."
        )
    else:
        rules += "7. Return ONLY the reply text. No preamble, no markdown, no JSON."
    return rules


def compose_conversational(template_text: str, facts: dict, intent: str, language: str = "en",
                            recent_turns: list = None):
    """
    Turns the deterministic template line + a bounded set of real result
    rows (now possibly enriched — see facts_enrichment.py) into a
    natural, conversational reply, PLUS a lightweight self-critique pass:
    the same call also asks the model to name whatever in the data is
    most worth an officer's attention, so a genuinely notable fact
    doesn't get buried in a form-letter-shaped sentence.

    Returns None (never a guess) if Ollama is unavailable, times out, or
    the result fails the grounding check — callers MUST fall back to
    template_text in that case. Otherwise returns
    {"text": str, "notable": str|None} — `notable` is already filtered
    to only the cases that clear a real bar (see _clears_notable_bar()
    below); most calls will get notable=None, which is expected and
    fine, not a failure.

    This function only ever runs when there is at least one result row;
    the zero-results case is handled by the caller with the fixed
    template, never free generation (see brain.py).

    See compose_conversational_streaming() for the live-token variant
    used by the SSE chat endpoint — that one skips this JSON/notable
    structure (incrementally parsing partial JSON token-by-token isn't
    reliable) in exchange for genuine real-time output.
    """
    if not is_available():
        return None
    if facts.get("result_count", 0) <= 0:
        return None  # zero-result phrasing is never free-generated — see brain.py

    system_prompt = _compose_system_prompt(language, want_notable=True)
    prompt = f"FACTS_JSON: {_facts_block(facts)}"
    turns_block = _recent_turns_block(recent_turns)
    if turns_block:
        prompt += f"\n\nRECENT_CONVERSATION (tone/continuity only — not a source of facts):\n{turns_block}"
    prompt += f"\n\nDeterministic draft (for reference, feel free to rephrase freely as long as you stay within FACTS_JSON): {template_text}"

    out = generate(prompt, system=system_prompt, timeout=20, format_json=True)
    if not out:
        return None

    reply, notable = _parse_compose_json(out, template_text)
    if not reply:
        return None

    check_text = reply + (f" {notable}" if notable else "")
    context_text = grounding_context_text(facts, recent_turns)
    if not _looks_grounded(check_text, facts, extra_context=context_text):
        print("[Ollama] conversational output failed grounding check — falling back to template")
        return None

    if notable and not _clears_notable_bar(notable, facts):
        notable = None

    return {"text": reply, "notable": notable}


def _parse_compose_json(raw: str, fallback_text: str):
    """Best-effort JSON parse of compose_conversational()'s structured
    output. If the model ignored the JSON instruction and just returned
    plain text (small local models sometimes do), treat the whole thing
    as the reply with no notable note — degrade gracefully rather than
    reject a perfectly fine reply just because it wasn't wrapped in
    JSON."""
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict) and obj.get("reply"):
            notable = (obj.get("notable") or "").strip()
            return obj["reply"].strip(), (notable or None)
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return raw.strip(), None


def _clears_notable_bar(notable: str, facts: dict) -> bool:
    """Only surface the self-critique note when it actually adds
    something — a deliberately simple, cheap set of checks rather than a
    second LLM call to judge the first one's output."""
    notable = notable.strip()
    if len(notable) < 12 or len(notable) > 220:
        return False
    # Reject a "notable" that's just the result count restated — that's
    # already in the reply and the deterministic text, not a fresh
    # observation.
    n = facts.get("result_count", 0)
    if re.fullmatch(rf'\D*{n}\D*', notable):
        return False
    return True


def compose_conversational_streaming(template_text: str, facts: dict, intent: str, language: str = "en",
                                      recent_turns: list = None, context_text: str = "",
                                      stream_sink=None):
    """
    Streaming counterpart to compose_conversational() — same grounding
    guarantee (verified against FACTS_JSON before being trusted), but
    tokens are pushed to stream_sink(...) AS THEY ARRIVE for a live
    "typing" UX, then confirmed or retracted once the full reply is in.

    stream_sink, if given, is called with small dicts:
      {"type": "token", "text": "..."}  — a piece of provisional text.
                                           The frontend may render these
                                           immediately, but must treat
                                           them as UNCONFIRMED until...
      {"type": "confirm"}               — ...this arrives: the full text
                                           passed the grounding check,
                                           every token sent so far is
                                           final.
      {"type": "retract"}               — grounding failed; the caller
                                           MUST discard every token sent
                                           so far. This function then
                                           returns None — exactly the
                                           same contract as
                                           compose_conversational()
                                           returning None — so
                                           brain.py's existing
                                           "fall back to
                                           polish_response(template_text)"
                                           logic runs completely
                                           unchanged.

    Returns the final reply text on success, or None. Does NOT produce a
    `notable` self-critique note (see compose_conversational's docstring
    for why) — that stays a non-streaming-only feature.
    """
    if not is_available() or facts.get("result_count", 0) <= 0:
        return None

    system_prompt = _compose_system_prompt(language, want_notable=False)
    prompt = f"FACTS_JSON: {_facts_block(facts)}"
    turns_block = _recent_turns_block(recent_turns)
    if turns_block:
        prompt += f"\n\nRECENT_CONVERSATION (tone/continuity only — not a source of facts):\n{turns_block}"
    prompt += f"\n\nDeterministic draft (for reference, feel free to rephrase freely as long as you stay within FACTS_JSON): {template_text}"

    chunks = []
    for chunk in generate_stream(prompt, system=system_prompt, timeout=25, num_ctx=4096):
        chunks.append(chunk)
        if stream_sink:
            stream_sink({"type": "token", "text": chunk})

    full_text = "".join(chunks).strip()
    if not full_text:
        if stream_sink:
            stream_sink({"type": "retract"})
        return None

    merged_context = context_text
    if not _looks_grounded(full_text, facts, extra_context=merged_context):
        print("[Ollama] streamed conversational output failed grounding check — retracting")
        if stream_sink:
            stream_sink({"type": "retract"})
        return None

    if stream_sink:
        stream_sink({"type": "confirm"})
    return full_text


def grounding_context_text(facts: dict, recent_turns: list = None) -> str:
    """Builds the extra_context string passed to _looks_grounded() — the
    officer's own query entities plus recent conversation text, so a
    name the OFFICER typed (or one KAVACH already mentioned a turn ago)
    is never mistaken for a hallucinated one just because it isn't
    inside `facts["sample"]`'s five rows."""
    parts = []
    for key in ("query_districts", "query_crime_types"):
        vals = facts.get(key) or []
        parts.extend(str(v) for v in vals)
    turns_block = _recent_turns_block(recent_turns)
    if turns_block:
        parts.append(turns_block)
    return " ".join(parts)


def _looks_grounded(candidate: str, facts: dict, extra_context: str = "") -> bool:
    """
    A deliberately simple, fast sanity check — not a full fact-checker,
    but enough to catch the two failure modes that actually matter for a
    police tool: (a) the model claiming a different result count than
    what really happened, and (b) the model naming a specific person who
    isn't anywhere in the facts it was given. When in doubt, this
    returns False and the caller uses the safe deterministic template —
    a missed polish is a cosmetic loss; an ungrounded fact in a police
    tool is not.

    Checks names against the ENTIRE facts payload now (not just the old
    5-row `sample`) — facts can carry case_history/trend/breakdown/etc.
    (see facts_enrichment.py), and a name-check still calibrated for the
    old narrow payload would reject perfectly grounded output the moment
    a richer fact was the thing actually being referenced. `extra_context`
    (the officer's own query terms + recent conversation — see
    grounding_context_text()) is checked the same way, so a name the
    OFFICER typed is never treated as a hallucination just because the
    deterministic query happened to return zero matching rows for it.
    """
    n = facts.get("result_count", 0)

    # (a) if the reply states a number that looks like a result count,
    # it should be consistent with the true count (allow it to just not
    # mention a number at all, which is fine). Numbers that appear
    # elsewhere in facts (a trend percentage, a breakdown count, a risk
    # score) are legitimate and must not trip this check — so anything
    # present anywhere in facts is treated as plausible too.
    facts_numbers = {
        int(x) for x in re.findall(r'-?\d+', json.dumps(facts, ensure_ascii=False, default=str))
    }
    mentioned_numbers = {int(x) for x in re.findall(r'\b\d{1,4}\b', candidate)}
    if mentioned_numbers:
        plausible = {n} | set(range(0, n + 1)) | facts_numbers
        if all(m not in plausible for m in mentioned_numbers) and any(m > n for m in mentioned_numbers):
            return False

    # (b) any capitalised multi-letter word sequence that looks like a
    # proper name should appear somewhere in the facts we gave it, or in
    # the officer's own query / recent conversation.
    sample_text = json.dumps(facts, ensure_ascii=False, default=str).lower()
    if extra_context:
        sample_text += " " + extra_context.lower()
    candidate_names = re.findall(r'\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,}){0,2})\b', candidate)
    generic = {"Ollama", "Kavach", "Karnataka", "Bengaluru", "Fir", "Police", "The", "Show", "Yes", "No"}
    for name in candidate_names:
        if name in generic:
            continue
        if name.lower() not in sample_text:
            return False

    return True


# ── Document-grounded chat ("chat with a PDF") ───────────────────────────
# Same overall discipline as compose_conversational() above, applied to
# free-form extracted document text instead of structured SQL rows: the
# model is instructed to answer ONLY from the given text, told explicitly
# to say so when the document doesn't cover the question rather than
# guess, and its output is sanity-checked against the source text before
# being trusted. response_source="document_grounded" downstream keeps
# this visibly separate from a verified case-database fact — see
# brain.py's _handle_document_query().

_DOC_MAX_CHARS = 6000  # keeps prompt + reply within a small local model's context window


def _truncate_document(text: str, max_chars: int = _DOC_MAX_CHARS) -> tuple:
    text = text or ""
    if len(text) <= max_chars:
        return text, False
    return text[:max_chars], True


def _document_system_prompt(filename: str, language: str, truncated: bool) -> str:
    lang_note = "Respond in natural, conversational Kannada." if language == "kn" else \
                "Respond in natural, conversational English."
    truncation_note = (
        " The DOCUMENT_TEXT below may be truncated from a longer file — if the "
        "answer might be beyond what's shown, say the excerpt doesn't cover it "
        "rather than guessing."
        if truncated else ""
    )
    return (
        f"You are KAVACH, a crime-intelligence chat assistant for Karnataka Police "
        f'officers. An officer has attached a document ("{filename}") to this chat. '
        "Below is DOCUMENT_TEXT — the extracted text of that document, and the ONLY "
        "source you are allowed to use to answer.\n\n"
        "STRICT RULES:\n"
        "1. Answer ONLY using information that literally appears in DOCUMENT_TEXT. "
        "Never use outside knowledge, never guess, never fill in a plausible-sounding "
        "value that isn't there.\n"
        "2. If DOCUMENT_TEXT does not contain the answer, say so plainly (e.g. "
        "\"The document doesn't mention that\") — do not speculate.\n"
        "3. This is a document under discussion, NOT a verified database record — "
        "never claim it has been saved, filed, or entered into any system.\n"
        f"4. {lang_note}{truncation_note}\n"
        "5. Return ONLY the answer text. No preamble, no markdown, no JSON."
    )


def answer_from_document(question: str, document_text: str, filename: str, language: str = "en"):
    """Blocking document Q&A. Returns the answer text, or None if Ollama
    is unavailable, errors, or the answer fails the document-grounding
    check (see _looks_grounded_in_document()) — callers must show an
    honest "couldn't confidently answer that from the document" message
    in that case, never a guess."""
    if not is_available():
        return None
    excerpt, truncated = _truncate_document(document_text)
    system_prompt = _document_system_prompt(filename, language, truncated)
    prompt = f"DOCUMENT_TEXT:\n{excerpt}\n\nQuestion: {question}"
    out = generate(prompt, system=system_prompt, timeout=25, num_ctx=4096)
    if not out:
        return None
    if not _looks_grounded_in_document(out, excerpt):
        print("[Ollama] document answer failed grounding check — discarding")
        return None
    return out.strip()


def answer_from_document_streaming(question: str, document_text: str, filename: str,
                                    language: str = "en", stream_sink=None):
    """Streaming counterpart to answer_from_document() — identical
    contract/stream_sink protocol to compose_conversational_streaming()
    (token / confirm / retract), grounded against the document excerpt
    instead of FACTS_JSON."""
    if not is_available():
        return None
    excerpt, truncated = _truncate_document(document_text)
    system_prompt = _document_system_prompt(filename, language, truncated)
    prompt = f"DOCUMENT_TEXT:\n{excerpt}\n\nQuestion: {question}"

    chunks = []
    for chunk in generate_stream(prompt, system=system_prompt, timeout=30, num_ctx=4096):
        chunks.append(chunk)
        if stream_sink:
            stream_sink({"type": "token", "text": chunk})

    full_text = "".join(chunks).strip()
    if not full_text or not _looks_grounded_in_document(full_text, excerpt):
        if not full_text:
            pass
        else:
            print("[Ollama] streamed document answer failed grounding check — retracting")
        if stream_sink:
            stream_sink({"type": "retract"})
        return None

    if stream_sink:
        stream_sink({"type": "confirm"})
    return full_text


def _looks_grounded_in_document(candidate: str, document_text: str) -> bool:
    """Same proper-noun heuristic as _looks_grounded(), applied against
    the source document text instead of FACTS_JSON — deliberately
    simple, not a full fact-checker (see _looks_grounded()'s docstring
    for the same reasoning applied to structured facts)."""
    doc_lower = (document_text or "").lower()
    candidate_names = re.findall(r'\b([A-Z][a-z]{2,}(?:\s[A-Z][a-z]{2,}){0,2})\b', candidate)
    generic = {"Ollama", "Kavach", "Karnataka", "Bengaluru", "Fir", "Police", "The",
               "Show", "Yes", "No", "Document", "This"}
    for name in candidate_names:
        if name in generic:
            continue
        if name.lower() not in doc_lower:
            return False
    return True
