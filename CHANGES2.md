# KAVACH — Change Log: Datathon Judge-Readiness Pass

This documents the 12 requested changes from this round. As with
`CHANGES.md`, every claim below was verified by running the actual
code — a live FastAPI server hit with real HTTP requests against the
real seeded database, direct SQL unit tests, and a full `npm run build`
of the frontend — not just written and assumed to work. Several bugs in
my own first-draft code were caught this way before shipping (noted
inline below); that's the point of testing like this.

## 1. Reasoning panel (backend already had the data — this makes it visible)
- `frontend/src/pages/CrimeChat.jsx`: the separate "SQL Query" / "Why
  this answer" / "Identity confidence" pills are now one **🧠 Reasoning**
  panel per message, showing the resolver tier that matched (exact /
  alias / phonetic / fuzzy) with its confidence %, the generated SQL,
  and a grounded/polished/template badge — in that order, so the
  zero-hallucination pipeline is a 10-second demo moment instead of a
  paragraph in a doc.
- `backend/main.py` / `brain/brain.py`: added a `response_source` field
  (`ollama_grounded` / `ollama_polish` / `template` / `general_knowledge`)
  threaded through every response path so the badge is never guessed
  client-side.

## 2. Multi-turn reference resolution ("he", "that gang", "the second one", "her network")
**This was a real, confirmed bug**, not a hypothetical: verified live
that "Tell me about X" → "does he have any pending cases?" silently
dropped "he" and returned 30 unrelated records with zero person filter.
- `brain/reference_resolver.py` (new): resolves pronouns → current
  suspect, "that gang"/"the syndicate" → last gang discussed, and
  ordinal references ("the second one") → the exact ordered result list
  from the previous turn. Only ever *adds* a candidate the officer
  didn't type; never overrides an explicit name.
- `brain/memory_engine.py`: working context now also tracks
  `current_gang` and `last_turn_person_ids` / `last_turn_fir_numbers`.
- `brain/sql_builder.py`: **found and fixed a real schema gap** — cases
  couldn't be filtered by accused person at all, because `vw_fir_flat`
  has no person column (one FIR can have several accused). Added a
  proper join through `PersonIdentity → PersonIdentityLink → Accused →
  CaseMaster` for person-scoped case queries.
- Live-verified all four cases from the request: pronoun → correct
  person-filtered case results; "that gang" → correctly filtered
  `gang_query`; "the second one" → correctly resolved to the actual 2nd
  result from the prior turn; "her network" → correctly routed to
  `graph_engine` for the resolved person.
- Two bugs my own testing caught before shipping: a short glossary term
  ("mo") was matching as a substring inside ordinary words like "more"
  — fixed with `\b` word-boundary regex throughout. A resolved ordinal
  reference was being silently dropped when the message's wording was
  too generic for intent classification — fixed by upgrading the intent
  to `person_lookup` when a reference has already resolved to someone.

## 3. Bounded general-knowledge fallback (via Ollama, never via the database)
- `brain/general_knowledge.py` (new): a small curated table — procedural
  terms (FIR, charge sheet, bail, remand, etc.), an IPC↔BNS section
  cross-reference, and KAVACH's own capabilities — answered from this
  table only, **never** from the database and **never** from the LLM's
  own general knowledge. Every response is labelled "General guidance —
  not case-specific."
- The IPC→BNS section numbers (302→103, 420→318, 376→64, 498A→85, etc.)
  were cross-checked against multiple current legal-reference sources,
  not guessed — getting a section number wrong in front of police
  judges would be a real credibility problem, so this got the same
  research rigor as the Catalyst deployment claims below.
- Guarded so it only fires when the message carries no
  district/crime-type/name/date/FIR — a real case question that happens
  to use one of these words (e.g. someone's bail status) is never
  hijacked by a generic definition.

## 4. Real Catalyst integration (AppSail + Cache), not just hosting
- **Found a real problem first**: the shipped `catalyst.json` used an
  invalid serverless-Functions schema (`handler: main.handler`) that
  can't run a FastAPI app at all — fixed to the correct Client-hosting
  schema.
- `backend/app-config.json` (new): a genuine AppSail config in the
  actual schema (confirmed against Zoho's current docs, not guessed).
- `backend/main.py`: added the AppSail entry point (reads
  `X_ZOHO_CATALYST_LISTEN_PORT`, binds `0.0.0.0`) — **live-verified** by
  actually running `python main.py` with that env var set and hitting
  `/api/health` through it.
- `services/catalyst_adapter.py` (new): a genuine Cache integration for
  the cross-session working context (the thing that makes item 2 work
  across turns) — read-through in front of SQLite, which stays the
  source of truth. Inert unless `CATALYST_CACHE_ENABLED=true` and
  actually running on AppSail; every SDK call is wrapped so a failure
  degrades to SQLite-only rather than breaking anything.
- **See `DEPLOYMENT.md`** for exactly what's verified vs. what needs a
  one-time confirmation at your actual deploy (the precise Python
  `stack` identifier, and whether the SDK's Flask-shaped
  `initialize(req=...)` accepts a FastAPI request — I could not test
  either against real Catalyst infrastructure from this environment,
  and say so there rather than guessing silently).

## 5 & 9. Voice output — on demand, not automatic
- Previously every response was auto-spoken via `speechSynthesis`
  whether the officer wanted it or not. Replaced with a **🔊 Listen**
  button on each reply (▪ Stop while playing) — matches the explicit
  ask ("not necessarily read everything every time... give a button").

## 6. Lightweight predictive analytics ("projected hotspots, next 30 days")
- `brain/hotspot_forecast.py` (new): runs the *existing*
  `prediction_engine.py` (linear trend + seasonal adjustment — already
  honestly framed as statistical, not ML) across every district ×
  crime-type pair with enough history, ranked. Feeds the new Analytics
  heatmap's "Projected" toggle. District coordinates are the real
  average lat/lng of that district's own seeded FIRs, not invented ones.
- Live-verified: `/api/analytics/hotspot-forecast` returns real ranked
  projections against the seeded database.

## 7. Real published data alongside the synthetic seed data
- `services/ncrb_reference.py` (new): a small table of **real, sourced**
  NCRB "Crime in India" figures for Karnataka (murder counts, charge-
  sheet rates, cybercrime rank, etc. for 2022/2023) — each entry carries
  its source and year. `/api/analytics/ncrb-benchmark` shows these
  alongside this project's own seeded aggregate numbers.
- Deliberately honest framing, stated directly in the module docstring
  and the API's `disclaimer` field: this is NOT a claim that the
  synthetic 500-FIR demo dataset numerically matches real statistics —
  it can't, it's `Faker`-generated. It's real published context, not a
  live data pull and not a validation claim.

## 8. Admin audit log
- `services/audit_log.py` (new) + `AuditLog` table: every `/api/chat`
  call logs who (real authenticated `user_id`), what, when, the
  interpreted intent, and result count. `/api/admin/audit-log`,
  gated to admin/supervisor roles — live-verified both that a plain
  investigator gets `403` and that an admin sees real logged entries.

## 10. Friendlier response phrasing
- The "N records found" line now reads "I've found N matching records —
  see them in the panel on the right," per the exact example given.

## 11. Chat history sidebar
- **Tested the backend directly first**: `/api/chat/sessions` and
  `/api/chat/history/{id}` already worked correctly end-to-end (verified
  with a live login → chat → list → history round trip) — the bug
  wasn't there.
- What was actually wrong: sessions were only ever fetched *after*
  clicking History, with a silently-swallowed fetch error and no
  loading state — a slow or failed request looked identical to "no
  history at all," which is a plausible reading of "doesn't show."
  Fixed: prefetches on page load, shows a real loading/error+retry
  state, and the rail is open by default (persistent, ChatGPT-style)
  instead of hidden behind a click.

## 12. Interactive hotspot map
- `frontend/src/components/HotspotMap.jsx` (new): a real Leaflet heat
  map (OpenStreetMap tiles, `leaflet.heat`) replacing the "Case Status
  by District" bar chart on the Analytics page, with a **Current /
  Projected (next 30 days)** toggle wired to items 6's forecast
  endpoint. Point data is the real lat/lng already computed by the
  existing `/api/analytics/hotspots` endpoint — not invented
  coordinates.

## What to double check before presenting
- **`DEPLOYMENT.md`'s "needs a one-time confirmation" section** — the
  Python `stack` value and the Cache SDK's request-object compatibility
  genuinely could not be verified without real Catalyst project
  credentials; both degrade safely if wrong, but you should smoke-test
  an actual deploy before a live judge session.
- Every other claim above was run, not just written — but this was a
  large batch of changes; a final manual click-through before presenting
  is still worth your time.
