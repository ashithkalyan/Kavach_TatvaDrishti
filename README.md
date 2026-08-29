# KAVACH — Karnataka AI Voice & Crime Hub

> **Karnataka State Police | SCRB | Challenge 1 Submission**
> *A self-hosted Conversational AI & Crime Analytics Platform — zero external LLM API dependency*

---

## What makes KAVACH different

Every other team at this hackathon will wire up a call to an external LLM API. **KAVACH doesn't.** The entire reasoning pipeline — natural language understanding, Indian name/alias resolution, SQL generation, crime forecasting, network discovery, case similarity — is built in-house, runs entirely on your own infrastructure, and costs nothing per query.

This isn't a limitation dressed up as a feature. In a law-enforcement context, an opaque model call that occasionally hallucinates a fact is a real liability. KAVACH's default path is deterministic and fully explainable: every answer traces back to a specific database row, a specific matched pattern, a specific SQL query — nothing is invented. Optional local-LLM polishing (via Ollama, also self-hosted) can improve phrasing, but is never allowed to add facts.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  React Frontend — Dashboard · Chat · Network · Analytics ·  │
│                    Cases · Profiles                         │
└───────────────────────────┬───────────────────────────────────┘
                            │ REST (axios)
┌───────────────────────────▼───────────────────────────────────┐
│  FastAPI Backend                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │            KAVACH BRAIN  (backend/brain/)              │  │
│  │                                                          │  │
│  │  Language & Identity        Analysis Engines            │  │
│  │  ├─ alias_resolver          ├─ similarity_engine         │  │
│  │  ├─ transliteration         ├─ graph_engine (networkx)   │  │
│  │  ├─ entity_extractor        ├─ prediction_engine         │  │
│  │  └─ abbreviation_glossary   └─ mo_fingerprint            │  │
│  │                                                          │  │
│  │  Memory & Workflow           Orchestration               │  │
│  │  ├─ memory_engine            ├─ intent_engine             │  │
│  │  ├─ timeline_engine          ├─ sql_builder                │  │
│  │  ├─ recommendation_engine    ├─ response_generator         │  │
│  │  ├─ reasoning_trace          ├─ ollama_client (optional)   │  │
│  │  └─ ingestion_engine         └─ brain.py (orchestrator)    │  │
│  └───────────────────────────────────────────────────────┘  │
└───────────────────────────┬───────────────────────────────────┘
                            │
┌───────────────────────────▼───────────────────────────────────┐
│  SQLite — schema matches the KSP FIR System ER diagram        │
│  (CaseMaster, Accused, Victim, ComplainantDetails,             │
│   ArrestSurrender, Act/Section, CrimeHead/SubHead, ...)        │
│  + KAVACH Intelligence Layer (PersonIdentity, Phone,           │
│    Vehicle, PersonNetworkLink, ConversationMemory, ...)        │
└─────────────────────────────────────────────────────────────┘
```

---

## The brain, module by module

| Module | What it does |
|---|---|
| `alias_resolver.py` | Resolves Indian name/nickname variants (Manju ↔ Manja ↔ Manjunath) via a curated dictionary, phonetic normalisation, and fuzzy matching — plus `cluster_identities()`, which runs at data-ingestion time to link the same person across FIRs even when each one spells the name differently |
| `transliteration.py` | Kannada Unicode script resolution (ಮಂಜು ↔ Manju) and cross-community spelling-variant resolution (Mohammed/Mohd/Muhammad) |
| `entity_extractor.py` | Crime type, district, date-range, and person-name extraction from free text (English + common Kanglish terms) |
| `abbreviation_glossary.py` | Police terminology (FIR, BNS, NDPS, DySP, ...) recognised and expanded on request |
| `memory_engine.py` | Persistent conversation memory — in-session context AND cross-session recall via a self-built TF/cosine similarity engine, plus a per-officer "working context" (current suspect, district, recent searches) that survives logout |
| `intent_engine.py` | Pattern-based, explainable intent classification |
| `sql_builder.py` | Deterministic, parameterised SQL generation against the schema's flattened views |
| `response_generator.py` | Grounded, bilingual (English/Kannada) response templates — never free-form generation of facts |
| `ollama_client.py` | **Optional** local LLM bridge for phrasing polish — see setup below |
| `similarity_engine.py` | Case-linkage analysis: weighted feature + MO-text similarity, used by real criminology to spot serial offenders |
| `graph_engine.py` | Multi-entity criminal network graph (Person/Phone/Vehicle/Location/Case) using classical graph algorithms — path-finding, centrality, community detection — via `networkx` |
| `prediction_engine.py` | Transparent statistical forecasting (trend + seasonality + festival/monsoon/election adjustment) — deliberately not a black-box trained model; see the module docstring for why |
| `mo_fingerprint.py` | Structured "crime signature" extraction and comparison |
| `timeline_engine.py` | Stage-classifies investigation updates into the canonical FIR→Arrest→Chargesheet→Court pipeline, and reports which stages are missing |
| `recommendation_engine.py` | Rule-based investigative-lead checklist, driven by crime type + timeline gaps + network hits |
| `reasoning_trace.py` | Structured, audit-ready confidence/evidence trace for any inference KAVACH makes |
| `ingestion_engine.py` | Live PDF/photo FIR ingestion — extraction (pdfplumber/Tesseract OCR) → structured draft → **human-confirmed** commit to the live database |
| `brain.py` | The orchestrator — chains all of the above into one pipeline per query |

**A few honest design notes**, documented in full in the relevant module's docstring:
- Network discovery uses classical graph algorithms, not a Graph Neural Network — a GNN needs thousands of labelled examples to be trustworthy, which this dataset doesn't have. Classical algorithms are exact and fully explainable.
- Crime forecasting is transparent statistical modelling, not a "trained ML model" — more honest, more auditable at this data volume, and the exact arithmetic is always inspectable.
- Fingerprint matching is a defined data-model slot for AFIS integration, never a fabricated result.
- "Public order" forecasting is driven only by festival calendars and historical case volume — never demographic or religious composition of an area.
- Caste/religion fields exist in `ComplainantDetails` for schema fidelity to KSP's own ER diagram (they support the SC/ST Prevention of Atrocities Act's protected-category handling) but are never read by any analytics, risk-scoring, or prediction code in this project.

---

## Quick Start

```bash
cd backend
pip install -r requirements.txt --break-system-packages
python seed_data.py          # builds the KSP-schema database + runs identity clustering
uvicorn main:app --reload    # http://localhost:8000, docs at /api/docs
```

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

**Demo logins** (real bcrypt-hashed passwords — printed by `seed_data.py` on every run):
`investigator1` / `analyst1` / `supervisor1` / `admin`, password `Kavach@2026` for all four.
New accounts can also be created from the login screen's "Create Account" tab — this calls
a real `/api/auth/register` endpoint, not a mock.

### Authentication — how it actually works
- Passwords are hashed with **bcrypt** (`backend/auth.py`), never stored in plain text
- Login issues a random 32-byte session token, stored server-side in an `AuthSession` table with a 12-hour expiry
- 12 endpoints touching case/offender/network data require a valid `Authorization: Bearer <token>` header (`require_auth` dependency in `main.py`) — try calling `/api/dashboard/overview` without a token and you'll get a real 401, not demo data
- The frontend attaches the token automatically via an axios interceptor once logged in, and force-logs-out on a 401 (expired/revoked session) rather than silently breaking

### Getting this actually online (Zoho Catalyst)
This is the one part that has to happen outside this repo, in your own Zoho account:

1. **Database**: SQLite on a persistent disk is a legitimate "online" database — it doesn't need to become Postgres to be real. Catalyst's Functions support persistent storage; point `DATABASE_URL`/`DB_PATH` at that mounted path.
2. Deploy `backend/` as a Catalyst Function (Python runtime) — entry point is `main:app`, run once via `python seed_data.py` on first boot to initialise the schema.
3. Deploy `frontend/dist` (after `npm run build`) to Catalyst Web Hosting.
4. Set `VITE_API_URL` in the frontend build to your deployed function's public URL.
5. **Before going live**: change the four demo passwords (`Kavach@2026`) — either via `/api/auth/register` for new accounts or by re-running `seed_data.py` with different values in the `demo_users` list.

If you later want a fully independent hosted database (Postgres) instead of SQLite-on-a-disk, the query layer in `main.py` uses standard parameterised SQL throughout — the migration is mechanical, but budget real time for testing it, since SQLite and Postgres do differ in a few functions (date handling, `AUTOINCREMENT` vs `SERIAL`). Not attempted here because there's no Postgres instance in this environment to verify it against, and shipping unverified SQL changes right before a demo is a bad trade.

---

### Optional: enable local LLM polishing (Ollama)
```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama pull llama3.2
# That's it — brain/ollama_client.py auto-detects it at localhost:11434.
# Everything works identically without this step; it only affects phrasing.
```
**Deployment note:** Zoho Catalyst's serverless functions can't host a multi-GB local model, so this step is local-dev-only. The deployed version always runs in pure deterministic mode — which is also why the response templates are built to be complete on their own, not just a fallback.

---

## Try these in KAVACH Chat

```
"Show me repeat offenders with 2+ convictions"
"Who is connected to <any gang member name>?"          → live graph traversal
"Forecast robbery trend in Bengaluru Urban next month"  → statistical forecast
"Tell me about Shivu"                                    → alias resolution in action
"Show gang members with EXTREME risk"
```

New standalone endpoints beyond chat: `/api/predict`, `/api/similarity/{fir}`, `/api/timeline/{fir}`, `/api/recommendations/{fir}`, `/api/ingest/document` (upload a real FIR PDF/photo).

---

## Database

Schema matches the **actual KSP FIR System ER diagram** supplied for this hackathon — `CaseMaster`, `Accused`, `Victim`, `ComplainantDetails`, `ArrestSurrender`, `ChargesheetDetails`, `Act`/`Section`, `CrimeHead`/`CrimeSubHead`, and every lookup table (`District`, `Unit`, `Rank`, `Designation`, `Employee`, ...) — not a simplified stand-in.

500 synthetic FIRs are generated with realistic Karnataka data, including **deliberate cross-FIR name-spelling variance** so identity clustering has real work to do — running `seed_data.py` prints exactly how many raw accused records got resolved into shared identities and by which method (alias dictionary / phonetic / fuzzy).

---

## Team

| Member | Role |
|---|---|
| Person 1 | AI/Backend — brain modules, schema, FastAPI |
| Person 2 | Frontend/UI — React, Cytoscape, voice, PDF export |
| Person 3 | Analytics/Docs — charts, demo video, submission |

---

*KAVACH — Protecting Karnataka through Intelligent Policing*
