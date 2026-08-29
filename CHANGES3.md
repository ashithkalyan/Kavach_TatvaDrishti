# KAVACH — Change Log: Colour-Toggle Fix, Chat-with-a-PDF, AI Depth Pass

As with `CHANGES.md`/`CHANGES2.md`: every claim below was verified by
running the actual code, not just written and assumed to work. For this
round that meant: real unit tests against the actual seeded `kavach.db`,
a live `uvicorn` server hit over real HTTP sockets with `curl` (not just
FastAPI's in-process `TestClient`), a monkeypatched fake local LLM to
exercise the streaming/grounding-retraction path end-to-end (Ollama
itself isn't installed in the sandbox this was built in), and a full
`npm run build` of the frontend. Specific evidence is noted inline.

**One honest caveat up front:** everything that depends on Ollama
actually running (conversational polish, the self-critique note, live
token streaming, document Q&A) was verified for *correct behaviour when
Ollama is absent* (graceful degradation — this was live-tested) and for
*correct logic when Ollama responds* (via a monkeypatched fake model
standing in for the real `ollama serve` process — see item 3.4). It was
not verified against a real running Ollama instance, because one isn't
available in this environment. Pull `llama3.2`, run `ollama serve`, and
the exact same code path that was tested against the fake model runs
against the real one — nothing else needs to change.

## 1. Fix — colour toggle was rebuilding the whole graph

`frontend/src/pages/Network.jsx`: `colorMode` was in the Cytoscape-
build effect's dependency array, so switching Risk/Gang colouring tore
down and re-ran `cose-bilkent` with `randomize: true`, scattering every
node to a new layout for a purely cosmetic change. Split into two
effects — the build effect now only depends on `[graphData, filterRisk,
filterGang]`; a second, lightweight effect updates a `colorModeRef` and
calls `cy.style().update()` on colour-mode change, which repaints nodes
in place with no destroy and no re-layout.

## 2. New feature — chat with a PDF

- `backend/brain/document_context.py` (new): session-scoped scratch
  storage for one document's extracted text, keyed by `(user_id,
  session_id)`. Deliberately not the case database — see its module
  docstring.
- `backend/brain/document_intent.py` (new): a small, explainable
  pattern classifier — `extract` (pulls the document into a review
  draft; covers both plain extraction language and "put it in the
  database" commit language, handled identically on purpose, since
  neither ever writes to the database) / `query` (a question about the
  document's content) / `None` (an ordinary case query — never hijacked
  just because a document happens to be attached).
- `backend/brain/brain.py`: two new handlers,
  `_handle_document_query()` and `_handle_document_extract()`, routed
  in ahead of intent classification whenever a document is attached.
  Reuses `ingestion_engine.parse_fields()` and
  `resolve_or_link_person_identity()` exactly as-is (same code Cases.jsx's
  upload flow uses) — the only new thing is surfacing a live "possible
  existing record" hint per candidate name before the officer even opens
  the review card.
- `backend/main.py`: `POST /api/chat/upload-document`, `GET`/`DELETE
  /api/chat/document/{session_id}`.
- `frontend/src/components/DocumentReviewCard.jsx` (new): renders
  **inline in the chat thread**, not a redirect to another page — same
  editable-fields-then-confirm shape as `Cases.jsx`'s upload modal
  (which is why `LabeledInput`/`LabeledSelect`/`LabeledTextarea`/
  `PersonListEditor` were pulled out into `components/FormFields.jsx`,
  so both places share one implementation instead of two copies
  drifting apart).
- `frontend/src/pages/CrimeChat.jsx`: a 📎 attach button, a persistent
  "document attached" chip with a way to detach it, and rendering of
  the review card inline in the AI message that carries it.

**The commit gate holds regardless of phrasing.** Whether the officer
says "extract this into a case" or "put it in the database", the
handler only ever builds and returns a draft — there is no code path
from chat to `commit_draft()`. The only way a case record gets written
is `POST /api/ingest/confirm`, which only ever fires from an explicit
"Confirm & Save" click. Verified directly: after asking the live server
to "put it in the database" for an uploaded FIR, `SELECT COUNT(*) FROM
CaseMaster WHERE CrimeNo=...` was `0`.

Verified end-to-end over a real HTTP connection (not just in-process):
uploaded an actual generated PDF, confirmed correct 18-digit crime-number
and district extraction, asked a question about it and got the honest
"Ollama isn't running" message (rather than a guess), and confirmed
`GET /api/chat/document/{session_id}` correctly reports the attached
file after the fact.

## 3. AI depth pass (four layers, all in `backend/brain/`)

**3.1 — Richer grounding facts (`facts_enrichment.py`, new).**
`response_generator.build_facts()` used to hand the LLM a flat 5-row
sample and a count. Now, for `person_lookup`/`repeat_offender_search`,
the top-ranked person's case history, gang context, network size, and a
plain-English risk explanation (reusing a new shared
`services/risk_scoring.describe_existing_risk()` — also used to
de-duplicate the identical breakdown logic that used to live inline in
`main.py`'s `/api/accused/{id}`) are added. For
`crime_type_search`/`statistics_query`/`location_search`, a
month-over-month trend and a district (or, if already scoped to one
district, police-station) breakdown are added. Every number is computed
in Python and hedged into `FACTS_JSON`; the model's only job stays
"phrase these facts naturally" — verified directly against the real
seeded data (`enrich_person_facts`/`enrich_trend_facts` run against
`kavach.db` and inspected).

Also widened `_looks_grounded()`'s name check to the whole facts payload
(previously just the old 5-row `sample`, which would have rejected
perfectly grounded output the moment it referenced one of these new
richer fields) plus the officer's own query terms and recent
conversation text, so a name the *officer* typed is never treated as a
hallucination just because the deterministic query returned zero rows
for it.

**3.2 — Conversation memory.** The last few already-generated turns
(not raw DB rows) are now passed into the compose prompt as
`RECENT_CONVERSATION`, explicitly labelled "tone/continuity only — not a
source of facts" and kept in a clearly separate prompt section from
`FACTS_JSON`.

**3.3 — Self-critique note.** `compose_conversational()` now asks the
same call for structured `{"reply", "notable"}` output — a short,
already grounding-checked observation surfaced only when it clears a
real bar (`_clears_notable_bar()`: not empty, not just the result count
restated, sane length). Returned as a new `notable_insight` field,
rendered as a distinct "🧭 Worth noting" box in the chat UI. Falls back
to treating the whole output as the reply with no note if a small local
model ignores the JSON instruction and returns plain text — degraded
gracefully rather than rejected.

**3.4 — Real token streaming, without weakening the grounding
guarantee.** `POST /api/chat/stream` (new, SSE) replaces the blocking
wait with live tokens via Ollama's own `stream: true` endpoint
(`ollama_client.generate_stream()`). The hard part: this codebase's
non-negotiable rule is that ungrounded LLM output must never reach the
officer — streaming tokens live, by definition, means showing text
before the grounding check has run on the finished output. Resolved
with a token/confirm/retract protocol: every token is pushed to the
frontend as *provisional*; once the full text is in, the same
grounding check that has always gated this brain's LLM output still
runs; if it passes, a `confirm` event marks everything shown as final;
if it fails, a `retract` event tells the frontend to discard everything
streamed and a corrected, safe reply follows. `process_query()`'s
control flow is completely unchanged — it's just given an optional
`stream_sink` callback; a background thread runs it while a
`queue.Queue` bridges tokens out to the SSE response.

**This was the highest-risk part of the whole build, so it got the
most scrutiny:** monkeypatched `ollama_client.generate_stream` to
simulate two scenarios against the *real* running server — (a) a
grounded fake reply, which streamed live and ended with
`response_source: "ollama_grounded"`, and (b) a fake reply that
hallucinates a name absent from the facts, which streamed live, was
retracted, and was replaced with the safe deterministic fallback text —
confirmed the fabricated name never reached the final payload. Also
stress-tested the frontend's SSE frame parser against a fake stream
split at arbitrary byte boundaries (including mid-frame splits) to
confirm it doesn't depend on frames arriving as clean chunks.

Paths that never involve a live LLM call (clarification, general
knowledge, zero-result replies, document-extract) are "fake-streamed" —
the already-final, already-safe text is sent word-by-word — so the
frontend experience is consistent either way without needing a second
code path.

## Everything else — unchanged on purpose

No changes to `entity_extractor.py`, `intent_engine.py`,
`alias_resolver.py`, `sql_builder.py`, identity resolution, or risk
*scoring* (only risk *explanation* was factored out, see 3.1) — none of
that was in scope this round, and touching shared resolution code to
chase a cosmetic improvement in one new feature (see
`_handle_document_extract()`'s note on `identity_hints` filtering) was
deliberately avoided.
