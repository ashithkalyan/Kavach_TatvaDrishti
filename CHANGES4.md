# KAVACH — Change Log: Grounding Bugs, Full Persistence, and Four New Features

As with every prior round (`CHANGES.md`/`CHANGES2.md`/`CHANGES3.md`):
every claim below was verified by running the actual code against the
actual seeded `kavach.db`, over real HTTP where it mattered, not just
written and assumed to work. This round in particular turned up several
real bugs that weren't part of the original ask — each is called out
explicitly below, not folded quietly into "misc fixes".

## Part 1 — The reported grounding bug (and three more like it)

The reported symptom: typing gibberish, or a real name not in the
database, returned a confident "Found 30 matching records" instead of
an honest zero. Root-caused to **four separate, compounding bugs**, all
fixed and verified together:

1. **The clarification gate checked the wrong signal.** `has_prior
   context` meant "does this session have any prior turns" — so after
   your first message, every subsequent unrecognized message skipped
   the safety check and fell into an unconditional "30 most recent
   records" query. Fixed: the gate now checks for a genuinely
   *resolvable focus* (a suspect/FIR/district actually in context), not
   just "history exists".
2. **Pure greetings could hit the same path.** "hello" could trigger a
   fake-30-records reply if stale context existed from earlier
   sessions. Greetings/thanks/bye/acknowledgements now short-circuit to
   an honest reply with zero database query, unconditionally.
3. **A working district query was silently corrupted.** "show theft
   cases in Bengaluru Urban" — a perfectly normal query — was being
   broken by "Urban" getting misread as a person-name fragment, which a
   separate resolver bug then used as a raw SQL filter, guaranteeing
   zero results for a valid query. Fixed both halves: extraction no
   longer double-counts a word that's part of an already-matched
   district, and the resolver no longer treats "name attempted, found
   nobody" the same as "no name filter at all".
4. **The worst one:** when a name search matched nobody,
   `person_lookup`/`network_query` silently substituted an unrelated
   "top 30 by risk" / "top 10 most-connected" list and let the reply
   attribute a REAL, unrelated person's profile to whatever was typed.
   Fixed: no match now means an honest zero, never a substitute.

Also: a zero-result reply for a name search now names the actual
search term ("No records found for 'ashith'") instead of a generic
message.

## Part 2 — Full turn-state persistence (the "reload loses everything" bug)

`conversation_memory` now stores each assistant turn's *complete*
response (reasoning trace, results, network snapshot, document draft —
everything) as JSON, not just the reply text. `GET /api/chat/history`
and `CrimeChat.jsx`'s `loadSession()` were fixed to actually use it —
this includes the specific two-line bug reported (`sql_generated` being
nulled out on reload despite the column already holding the value).
This is what keeps the Reasoning button, the network tab, and the
document review card intact when switching chat sessions and back.

A related bug found while building this: the document-save outcome
("FIR ... is now live") wasn't persisted anywhere, so it reverted to
the blank edit form on reload — fixed via a small `save_result_json`
column on the existing per-session document table.

**A real deployment gap found while testing both of the above:** the
migration code for these new columns existed but was never actually
called on server startup against an *already-seeded* database — only
`seed_data.py`'s one-time setup called it. Fixed by adding it to the
startup hook (idempotent, safe on every boot) and applying it directly
to the shipped `kavach.db` so it works out of the box.

## Part 3 — PDF export: reasoning trace + a hand-drawn network diagram

`services/pdf_export.py` now renders, per assistant turn: intent +
confidence, the SQL, the full pipeline trace, the self-critique note,
any document draft, and — the genuinely hard part — a network snapshot
drawn directly with reportlab's circle/line primitives (there's no
"embed a live graph" shortcut). Went through two rounds of layout
fixes after the first version had label overlap; the final version
uses an elliptical layout matched to the available page width and
places labels above/below based on position to avoid collisions.
Verified by rendering real PDFs and visually inspecting the output.

## Part 4 — Four new features

**1. Prediction accuracy tracking** (rated highest priority). New
`brain/prediction_tracking.py`: every forecast is recorded with a
strict "trained only on data before its own target month" rule (no
leakage, checked in code), settled against real `CrimeTrend` data once
available, and aggregated into accuracy stats. A one-time walk-forward
backtest across the full seeded history populated **5,040 real settled
predictions** immediately, so this has a genuine multi-year track
record from the first run, not an empty table. Honest result: ~10%
direction accuracy, because the seeded `CrimeTrend` data is close to
random with little real trend signal — documented plainly in the API
response rather than hidden; real KSP data would show this mechanism's
true performance.

**2. Case outcome feedback loop.** New `brain/feedback_engine.py`:
officers mark a recommended lead useful/not-useful/inconclusive per
case; `recommendation_engine.py` now attaches each lead's track record
and re-ranks within its priority tier accordingly (a timeline-gap lead
never stops being urgent regardless of feedback). UI: thumbs buttons on
each recommended lead in the FIR detail view.

**3. Identity confidence that changes over time.** New
`brain/identity_confidence.py`: confidence is recomputed from scratch
from every linked case record (consistent father/spouse name across
records raises it; an age progression that doesn't match the calendar
gap, or a different father/spouse name on a later record, lowers it and
flags `needs_review`) and logged as a trajectory, never patched
incrementally. Backfilled for all 681 existing identities on startup —
genuinely found **19 real contradictions** in the seeded data this way.
Wired live into `commit_draft()` so new evidence updates it
immediately. UI: a new "Identity" tab on the accused profile page
showing the current score and full history.

**4. Investigation knowledge surviving officer transfer.** New
`brain/case_memory.py`: tagged case notes (important person /
unresolved thread / dead end / general), resolvable without deleting
history, plus a case briefing that assembles those notes with lead
feedback (#2) and the existing investigation-update log. Answerable
directly in chat — "brief me on FIR X", or "what's still unresolved on
this case" using session context with no FIR number typed. Deliberately
scoped to the CASE, never the officer, which is the entire point. UI:
a Case Notes section in the FIR detail view with an add-note form and
resolve action.

**A genuine bug found and fixed while building #4:**
`extract_fir_number_candidate()` silently failed to find an FIR number
in ordinary natural-language phrasing ("brief me on 1001...", "what
about FIR 1001...") — it stripped every space from the whole message
before matching a word-boundary regex, which collapsed prose into the
number and destroyed the boundary right where it mattered. This had
likely been silently degrading FIR-number recognition for any
natural-language query for a while, not just this new feature. Fixed
to match a tolerant digit-run against the *original* text first, so
real word boundaries around prose survive.

## Honesty notes carried over from this round

- No synthetic data was ever fabricated for the feedback loop or case
  notes — both start genuinely empty and grow only from real use. The
  prediction backfill is different: it's a legitimate backtest against
  real historical `CrimeTrend` data, not invented feedback, which is
  why it was safe to seed and the other two weren't.
- Every claim of "found N real issues in the seeded data" (19
  identities, the FIR-extraction bug, the district-query bug) was
  independently reproduced against `kavach.db`, not inferred from
  reading code.
