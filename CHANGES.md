# KAVACH — Change Log

This documents what was changed, why, and — most importantly — what is
still genuinely blocked and needs your action. Every claim below was
verified by running the actual code (unit-level Python tests, a live
FastAPI server hit with real HTTP requests, and a full `npm run build`
of the frontend), not just written and assumed to work.

## ⚠️ Read this first: items 4 & 9 (real dataset)

**No row-level KSP dataset was ever uploaded** — only this project's own
code (whose `backend/seed_data.py` generates 500 synthetic FIRs with
`Faker` + `random.seed(42)`) and the ER-diagram PDF, which is schema
documentation (table/column definitions) with zero data rows. This was
verified directly against the shipped `kavach.db`.

**What was done instead of pretending this was solved:**
- `backend/import_real_dataset.py` — a ready-to-adapt importer. Point it
  at your real file, edit the `COLUMN_MAPPING` at the top to match its
  actual headers, and run it. It reuses the exact same
  identity-resolution and risk-scoring pipeline as live document
  ingestion (see item 3), so bulk-imported records get the same quality
  as one-at-a-time entries.
- The synthetic data generator (`seed_data.py`) was left in place, not
  deleted — removing it would leave the app with an empty, undemoable
  database. It's clearly labelled as synthetic throughout.
- The chat UI's data-provenance notice was reworded to be accurate
  rather than either overclaiming "real data" or silently shipping
  incorrect information.

**Action needed from you:** get the actual KSP datathon dataset file,
then adapt and run `import_real_dataset.py`.

## 1. Response "polishing" — sound conversational, not like a form letter
- `brain/ollama_client.py`: fixed a real bug where the Ollama
  availability check cached `False` forever if the backend started
  before Ollama did — meaning polishing could silently stay off for the
  life of the process even after Ollama came online. Now rechecks every
  20s.
- Added `compose_conversational()` — hands the LLM the actual result
  rows (not just a single templated sentence) to write a fuller,
  natural reply, then verifies the output against those same rows
  before trusting it (see item 6).
- `brain/response_generator.py`: template phrasing now has multiple
  varied phrasings instead of one fixed "Found N records" line, so even
  the no-LLM fallback path doesn't read as robotic.

## 2. Language switching — the whole app, not just chat
- **Root cause:** there was no shared language state anywhere — every
  page held its own local `language` variable, and only `CrimeChat.jsx`
  ever wired one up. Every other page (Dashboard, Analytics, Cases,
  Profiles, Network) never even showed a language toggle.
- Added `frontend/src/i18n/` — a `LanguageContext` (global, shared
  state) and a `translations.js` dictionary covering every page's UI
  chrome, plus accurate Kannada names for Karnataka's 12 districts and
  the 14 KSP crime-type categories (finite vocabularies, translated
  instantly with no network call).
- Fixed `POST /api/translate` — the frontend already called this for
  free-form text, but the route didn't exist on the backend at all
  (a silent 404). It's now real, and honestly reports
  `translation_available: false` rather than pretending when the local
  model isn't running.
- Fixed voice: text-to-speech previously only ever spoke in Kannada,
  never in English — now symmetric. Voice-input errors (permission
  denied, no speech, unsupported language) previously failed completely
  silently — every failure now shows a clear message.

## 3. PDF-to-database ingestion
- **Root cause:** extraction worked, but the actual DB-write function
  (`commit_draft()`) existed and was never called from anywhere — no
  API route, no UI button. The code even had a comment admitting this:
  *"nothing has been written to the database... next integration step."*
- Built the missing half: `POST /api/ingest/confirm`, wired to an
  expanded `commit_draft()` that writes CaseMaster + Accused + Victim,
  and runs every new accused through the same identity-linking and
  risk-scoring logic used at bulk-seed time.
- Built the missing UI: `Cases.jsx`'s upload modal now shows an
  editable review form (every extracted field is a real input/dropdown)
  and a genuine "Confirm & Save" button.
- Verified end-to-end, including that a second case with the same
  accused name/age/district correctly links to the same identity and
  escalates their risk score — not just that the form submits.

## 5. Small network graph inside chat
- New `frontend/src/components/MiniNetworkGraph.jsx` — a small, fully
  static (no zoom/pan/drag) Cytoscape instance.
- `brain/brain.py` now attaches a bounded 1-hop network snapshot to a
  chat response when there's an actual connection to show (never an
  empty graph).

## 6. No bluffing
- The deterministic SQL/template layer was already a strong foundation
  for this — it was kept and reinforced, not replaced.
- `ollama_client.compose_conversational()` is architecturally forbidden
  from free-generating the zero-results case — "no records found" is
  always the fixed, verified message, never something the LLM writes
  from scratch.
- Added `_looks_grounded()` — rejects any LLM-composed reply that states
  a record count inconsistent with the real one, or names a person not
  present in the data it was given; falls back to the safe template.
- Found and fixed two fabricated-content bugs while working on this:
  `Dashboard.jsx` had a hardcoded fake "alert" about a specific
  fictional offender ("ACC-001, Raju Kumar... released on bail") that
  wasn't derived from any query, and `Analytics.jsx` had four
  invented statistics ("Cybercrime rose 34% YoY", "4 organised gangs...
  cross-border operations detected") presented as real analysis. Both
  now show genuinely computed values from the actual fetched data.
- Added a direct FIR-number lookup path (`brain/brain.py`,
  `_handle_fir_number_lookup`) — found via testing that a real, valid
  FIR number was incorrectly triggering "please clarify" instead of an
  honest lookup.

## 7. Ask for clarification instead of guessing
- Was not implemented at all previously — every query, however vague,
  ran through to a result set (however empty).
- `brain/brain.py`'s `_needs_clarification()` now asks a short follow-up
  question when: (a) a person- or network-centric question doesn't
  actually name anyone, or (b) the lowest-confidence catch-all intent
  fires with zero extracted entities and no prior conversation context.
  Deliberately conservative — it doesn't interrupt genuine "no results"
  answers, which stay honest per item 6 instead.
- `CrimeChat.jsx` renders a clarification turn with distinct styling
  (a "?" avatar, purple accent) so it doesn't look like a normal answer.

## 8. Network-page auto-zoom bug
- **Root cause found:** clicking a node swaps the right-hand panel from
  the 220px gang list to the 280px profile panel, shrinking the graph's
  container by ~60px via the flex layout. Cytoscape doesn't
  automatically detect a plain CSS/flex resize of its container, so it
  kept rendering against stale pixel dimensions — producing the
  "sudden zoom" look.
- Fixed with a `ResizeObserver` on the container that calls
  `cy.resize()` on any layout change — not a full rebuild, and it
  future-proofs against any other panel-width change too.

## 10. Automated chat-history export at logout
- **Root cause:** `user_id` was hardcoded to `1` in the chat endpoint
  and several others — every officer's conversations, working context,
  and history sidebar were silently shared under one identity,
  regardless of who was actually logged in. Fixed across
  `/api/chat`, `/api/chat/sessions`, `/api/chat/history/*`, and
  `/api/context` — all now use the real authenticated user, and
  verified that one officer genuinely cannot read another's session
  history (returns empty, not an error that leaks existence).
- New `backend/services/pdf_export.py` — generates the export
  server-side with an embedded Kannada font (Noto Sans Kannada,
  Apache-licensed), so Kannada chat content renders correctly. The old
  client-side jsPDF export had no way to do this and would have shown
  blank boxes for Kannada text.
- `App.jsx`'s logout handler now downloads a combined PDF of everything
  since the current login before completing sign-out, and clears the
  active chat session on every fresh login so it starts clean.

## Other cleanup
- Removed `backend/services/llm_service.py` — a dead, unused legacy
  Gemini-based module (zero references anywhere in the codebase),
  confusing to leave alongside the real Ollama integration.
- `backend/.env.example` rewritten — the old one referenced a
  `GEMINI_API_KEY` and `GOOGLE_TRANSLATE_API_KEY` that nothing in the
  current architecture reads.
- Fixed a pre-existing, unrelated bug found while testing: `@keyframes
  spin` was referenced by loading spinners across the app (Network,
  Cases, the session-check screen) but never actually defined in the
  stylesheet, so those spinners silently never animated.
- `backend/services/risk_scoring.py` — a more complete 4-factor risk
  model that existed but was never called — is now wired into live
  ingestion (item 3), instead of sitting unused next to a cruder inline
  version.
