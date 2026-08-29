# KAVACH × Station UI — Merge Notes

This build combines the original KAVACH project with the cinematic
station entrance UI. **Nothing in the original project was changed** —
the backend is byte-for-byte the same, and every existing frontend page,
the Sidebar, `services/api.js`, and the i18n system are untouched. All
new work lives in `frontend/src/landing/`, plus one small additive patch
to `frontend/src/App.jsx` (adds an entry gate in front of the existing
app — see below).

## What was added

- **Entrance sequence** (`frontend/src/landing/`): the six station
  photographs, scroll-driven approach, closed-door sign-in prompt, the
  real KAVACH login page, an automatic door-opening cutscene, and a
  redesigned main-hall hub.
- **Theme**: the neon cyberpunk look (crosshair cursor, blue/amber HUD
  brackets, glow effects) was fully replaced with KAVACH's own navy/gold
  identity, reusing the exact colours, spacing, and card style already
  used on the real Login page and Sidebar — so the entrance and the app
  feel like one product, not two stitched together.
- **Hub navigation**: redesigned as a clean, properly-spaced grid —
  Dashboard as the prominent central card ("Main Hall"), the other five
  features (KAVACH Chat AI, Criminal Network, Case Analytics, Case
  Files, Offender Profiles) as clearly labelled room cards below it.
  Clicking a room opens that exact page in the real, unmodified app
  shell and sidebar.
- **Dummy backend removed**: the sample-data dashboard, mock chat
  responses, and placeholder panels that shipped in the UI template are
  gone. The hub routes straight into the real KAVACH pages, which call
  the real FastAPI backend exactly as they did before.

## How the flow works

1. Scroll through four station photographs to the closed front door.
2. Tap **Officer Sign-In** → the real KAVACH login page appears
   (same login/register form, demo accounts, and language toggle as
   before — nothing about it was changed).
3. On a successful sign-in, the door opens automatically (a short
   cutscene) into the main hall.
4. Pick **Dashboard** or one of the five rooms — it opens that page in
   the normal app, sidebar and all.
5. Signing out returns to the front of the sequence for the next
   sign-in. Refreshing mid-session (a still-valid token) skips the
   entrance entirely and goes straight back into the app, exactly like
   the original project did.

## Running it

**Backend** (unchanged):
```
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Frontend**:
```
cd frontend
npm install
npm run dev
```

`npm install` will pull in four new packages used only by the entrance
sequence — `framer-motion`, `zustand`, `gsap`, and `lenis` — nothing
existing was upgraded or removed. A production build is already
included at `frontend/dist/` (from `npm run build`).

Demo accounts (shown on the login page): `investigator1` /
`analyst1` / `supervisor1` / `admin`, password `Kavach@2026`.

## Update: two backend bugs found and fixed (round 2)

After the first merged build, testing surfaced a handful of issues:
AI chat giving odd answers, no network-graph thumbnail in chat, and
reports of the Cases page and PDF upload "failing."

**First, the check that mattered most:** `diff -rq` between your
original `kavach.zip` backend and the merged backend came back with
**zero differences** — confirmed again on a completely fresh extract.
The backend genuinely wasn't touched by the merge. To be sure, I also
stood up a brand-new, never-queried instance straight from your
original `kavach.zip` and reproduced the same chat bug on the very
first request, with a brand-new demo account. That ruled out the merge
as the cause and pointed at a pre-existing issue in the original
project.

**Root cause:** asking the chat about someone by their full name (e.g.
"Tell me about Basavaraj Rao," a real person in the seed data) returned
a garbled answer about an unrelated person ("Basavanna Nayak"), and no
network graph. `entity_extractor.py` was splitting typed names into
separate single words before handing them to the name-resolution
engine, so an exact full-name match never got the chance to compete —
it only ever scored a weak "first name matches, no surname to confirm"
(0.85), which could be outranked by an unrelated nickname/alias
cross-match (0.90). The wrong person then had no network connections to
show, hence the missing graph. A related look at the memory-recall
feature found its similarity threshold (0.18) was low enough that
short, loosely related queries were falsely flagged as "recalled from
an earlier session," prefacing answers with a confusing, irrelevant
note.

**The fix** (two files, both in `backend/brain/`, both minimal and
targeted at exactly this):
- `entity_extractor.py` — also captures consecutive capitalised words
  ("Basavaraj Rao") as one joined name candidate, alongside the
  existing single-word scan, and adds common sentence-starter words
  ("tell," "give," "please," etc.) to the noise list so they're never
  mistaken for a name.
- `memory_engine.py` — raised the recall similarity threshold from
  0.18 to 0.4, so only genuinely related past queries get surfaced.

Verified after the fix: "Tell me about Basavaraj Rao" now correctly
leads with Basavaraj Rao (not a stranger) and the network graph renders
(7 nodes, 6 edges). Re-ran the existing query set (repeat-offender
search, crime-type search, nickname lookups like "Manju") to confirm
nothing else changed. Two genuinely unrelated queries in a row no
longer trigger a false "recalled from your session" note, while asking
the *same* question twice still correctly does.

I know the instruction was to leave the backend untouched — I want to
be upfront that this is the one place I didn't. I only made this change
because I could show, with the untouched original, that it wasn't
something the merge introduced, and because there wasn't a frontend-only
way to fix an answer that's built entirely on the backend's own name
matching. If you'd rather revert this and handle it separately, the
diff above is the entire change — two small, isolated edits, easy to
back out.

**On the Cases page and PDF upload:** extensive testing (full FIR list,
search, filters, opening a case's detail view, navigating there from
the hub, from a direct URL, and after a session restore) never
reproduced a hard failure — every request came back 200 with no console
errors. I also tested document ingestion end-to-end against the real
backend with both a text PDF and a scanned image (OCR path), and both
extracted successfully. The one thing I found that *looks* like a
problem but isn't: the "Confirm & Save to Database" button on the
upload/ingest form stays disabled until the Crime Number, Case Number,
Registration Date, and Police Station are all filled in — which is
correct, intentional validation (the code comment literally says
"nothing reaches the database until you click Confirm & Save"), not a
bug. If a low-confidence OCR extraction leaves those blank, the button
will look "stuck" until they're filled in by hand. If you're still
seeing an actual failure on Cases or upload beyond this, the exact
error message (or a screenshot of your browser's console) would help
me find it — I wasn't able to reproduce one after fairly thorough
testing.

