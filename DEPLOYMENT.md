# Deploying KAVACH to Zoho Catalyst

This project is built to run as two real Catalyst services — an AppSail
app for the FastAPI backend, and Client hosting for the built React
frontend — plus an optional Cache integration for the cross-session
memory engine. This doc is deliberately explicit about what's been
verified against Zoho's current public documentation versus what still
needs a one-time confirmation step during your own `catalyst` CLI
deploy, because a deployment doc that quietly guesses is worse than one
that says so.

## What's real here

- **`backend/app-config.json`** — a genuine AppSail configuration file,
  in the actual schema Catalyst uses (`command`, `buildPath`, `stack`,
  `memory`, `env_variables` — confirmed against Zoho's own
  Catalyst-Managed-Runtimes documentation, not guessed).
- **`backend/main.py`'s `if __name__ == "__main__":` block** mirrors
  Zoho's own documented AppSail Python pattern (their reference example
  reads `X_ZOHO_CATALYST_LISTEN_PORT` and binds `0.0.0.0`) — translated
  from their Flask example to FastAPI + uvicorn.
- **`services/catalyst_adapter.py`** is a genuine Cache integration for
  the officer "working context" that makes multi-turn reference
  resolution work (see `brain/reference_resolver.py`) — read-through in
  front of SQLite, which stays the source of truth. It's inert (falls
  back to SQLite-only) unless `CATALYST_CACHE_ENABLED=true` **and**
  actually running on AppSail.
- **`catalyst.json`** at the project root now correctly configures
  Client hosting (`frontend/dist`) — the version this replaced used an
  invalid serverless-Functions schema (`handler: main.handler`) that
  can't actually run a FastAPI app; that was wrong and has been fixed.

## What needs a one-time confirmation on your side

1. **The exact `stack` identifier for Python.** Zoho's docs confirm the
   *field* (`"stack"`) and show `"java8"` as the Java example, but don't
   publish a literal Python identifier string anywhere I could verify.
   Run `catalyst appsail:init` from `backend/` — the CLI interactively
   lists the current valid stack values — and it'll either confirm
   `"python3"` (what this file currently has) or correct it. This is a
   one-line fix if it's wrong.
2. **FastAPI isn't one of Catalyst's featured Python frameworks** —
   their help guides cover Flask, Django, Bottle, and CherryPy
   specifically. AppSail's actual contract is just "listen on
   `X_ZOHO_CATALYST_LISTEN_PORT` via whatever `command` you give it,"
   which is framework-agnostic — `uvicorn`/FastAPI fits that contract —
   but it's not one of their walked-through examples, so treat the
   first deploy as a smoke test, not a certainty.
3. **`zcatalyst_sdk.initialize(req=request)` and a FastAPI request.**
   Zoho's own SDK examples all initialize against a Flask (WSGI)
   `request` object. This project's `catalyst_adapter.py` tries that
   exact pattern first; if a FastAPI/Starlette `Request` doesn't satisfy
   whatever the SDK expects, every call is wrapped in try/except and
   falls back to SQLite-only — nothing breaks, the Cache acceleration
   just doesn't activate. Check `GET /api/health`'s `catalyst_cache`
   field after your first deploy to see whether it did.
4. **Project linking itself** (`catalyst init`, `.catalystrc`, your
   actual Project ID) is inherently account-specific and can't be
   pre-filled by anyone outside your Zoho account — run `catalyst init`
   from the project root once, which will also register the AppSail app
   this doc describes into the root `catalyst.json` automatically.

## Suggested deploy sequence

```bash
# from the project root
catalyst init                       # links this directory to your Catalyst project
cd backend
catalyst appsail:init               # picks up backend/app-config.json; confirms the stack value
catalyst appsail:deploy
cd ../frontend
npm install && npm run build        # produces frontend/dist, which catalyst.json's client.source points at
cd ..
catalyst deploy                     # deploys Client hosting
```

After deploying, hit `<your-appsail-url>/api/health` — it reports DB
connectivity, seeded record count, and (new) a `catalyst_cache` block
showing whether the Cache integration actually activated, so you're not
guessing.
