# Repository Scaffold & Claude Code Task Roadmap

**Project:** Global Kinect Sales Intelligence
**Repositories:**
  - `globalkinect/sales-intelligence` (Python backend + admin app)
  - `globalkinect/hubspot-briefing-card` (TypeScript UI extension — separate, later phase)
**Python version:** 3.12
**Last updated:** April 2026

---

## How to use this document

This is the document Claude Code operates against. The first half describes the repository structure Claude Code should produce. The second half breaks the initial build into ten sequenced tasks, each self-contained enough to be handed to Claude Code as a single session.

**Suggested workflow:**

1. Michael creates an empty private repo `globalkinect/sales-intelligence` on GitHub
2. Clone it locally, open a Claude Code session at the repo root
3. Run Task 01 end-to-end; review the PR; merge
4. Proceed to Task 02; repeat
5. Each task produces a working milestone that can be verified independently

**The discipline:** do not skip tasks or run them out of order. They build on each other. Task 05 (scoring) assumes Task 04 (Vibe adapter) is merged. Task 08 (Perplexity integration) assumes Task 07 (lead persistence) is in place.

---

## Part 1: Repository scaffold

### Top-level layout

```
sales-intelligence/
├── .github/
│   ├── workflows/
│   │   ├── ci.yml                    # pytest + ruff + mypy on every PR
│   │   └── deploy.yml                # Cloud Run deploy on merge to main
│   └── CODEOWNERS
├── .gitignore
├── .env.example                      # all env vars documented, no real secrets
├── README.md                         # see stub below
├── pyproject.toml                    # Poetry or uv; see dependency list below
├── alembic.ini
├── docker/
│   ├── worker.Dockerfile             # pipeline worker + sync worker image
│   └── admin.Dockerfile              # admin app image
│
├── docs/
│   ├── 01-vision.md                  # copied from phase 0
│   ├── 02-schema.md                  # copied from phase 0
│   ├── 03-hubspot-contract.md        # copied from phase 0
│   ├── 04-repo-and-tasks.md          # this document
│   ├── runbook.md                    # ops: how to run, debug, restore
│   └── adr/                          # architecture decision records, added as decisions are made
│
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── (migrations added per task)
│
├── src/
│   └── gk_sales/
│       ├── __init__.py
│       ├── config/
│       │   ├── __init__.py
│       │   └── settings.py           # Pydantic BaseSettings; reads env
│       │
│       ├── db/
│       │   ├── __init__.py
│       │   ├── engine.py             # SQLAlchemy async engine factory
│       │   ├── session.py            # Session context manager
│       │   └── models/               # One file per table
│       │       ├── __init__.py
│       │       ├── base.py           # DeclarativeBase + shared mixins
│       │       ├── segments.py
│       │       ├── leads.py
│       │       ├── prompt_versions.py
│       │       ├── generation_events.py
│       │       ├── lead_research.py
│       │       ├── lead_email_drafts.py
│       │       ├── lead_phone_scripts.py
│       │       ├── sdr_edits.py
│       │       ├── lead_activity.py
│       │       ├── lead_outcomes.py
│       │       ├── reply_classifications.py
│       │       ├── pipeline_runs.py
│       │       ├── suppression_list.py
│       │       ├── sales_users.py
│       │       ├── agent_reports.py
│       │       ├── agent_recommendation_outcomes.py
│       │       └── sync_state.py
│       │
│       ├── domain/                   # Pure business logic, no I/O
│       │   ├── __init__.py
│       │   ├── rubrics/
│       │   │   ├── __init__.py
│       │   │   ├── base.py           # RubricProtocol
│       │   │   ├── cfo_first_v1.py   # ported from sales-engine
│       │   │   └── owner_first_v1.py # ported from sales-engine
│       │   ├── dedupe.py             # the 3-way dedupe rule
│       │   └── suppression.py        # suppression_list lookups
│       │
│       ├── adapters/                 # External service clients
│       │   ├── __init__.py
│       │   ├── vibe.py               # Explorium / Vibe Prospecting
│       │   ├── perplexity.py         # Research generation
│       │   ├── anthropic_client.py   # Claude API for drafts + agents
│       │   └── hubspot/
│       │       ├── __init__.py
│       │       ├── client.py         # HTTP client with retry/backoff
│       │       ├── push.py           # Create contact/deal/engagement
│       │       ├── pull.py           # Incremental sync logic
│       │       └── bootstrap.py      # Idempotent custom-property setup
│       │
│       ├── pipeline/
│       │   ├── __init__.py
│       │   ├── run.py                # Orchestrator: the weekly job
│       │   ├── fetch.py              # Vibe fetch + enrichment
│       │   ├── score.py              # Apply rubric, filter to top N
│       │   ├── generate.py           # Research + email seq + phone script
│       │   └── persist.py            # Postgres inserts + HubSpot push
│       │
│       ├── sync/
│       │   ├── __init__.py
│       │   ├── engagements.py        # Pull emails, meetings, calls, notes
│       │   ├── deals.py              # Pull deal stage changes
│       │   ├── owners.py             # Sync sales_users from HubSpot
│       │   └── edits.py              # Detect SDR edits, populate sdr_edits
│       │
│       ├── agents/                   # Built later; stubs from day one
│       │   ├── __init__.py
│       │   ├── strategist.py         # Agent 1 (advisory)
│       │   └── reviewer.py           # Agent 2 (advisory)
│       │
│       ├── admin/                    # FastAPI admin app
│       │   ├── __init__.py
│       │   ├── main.py               # FastAPI app factory
│       │   ├── auth.py               # Google SSO + email allowlist
│       │   ├── routes/
│       │   │   ├── __init__.py
│       │   │   ├── runs.py
│       │   │   ├── leads.py
│       │   │   ├── segments.py
│       │   │   ├── reports.py
│       │   │   ├── suppression.py
│       │   │   ├── metrics.py
│       │   │   └── api.py            # Internal API for UI extension
│       │   ├── templates/            # Jinja2 HTML
│       │   └── static/
│       │
│       └── util/
│           ├── __init__.py
│           ├── logging.py            # Structured logging; JSON in prod
│           ├── secrets.py            # Google Secret Manager client
│           ├── hashing.py            # Prompt fingerprints, content hashes
│           └── time.py               # UTC-everywhere helpers
│
├── scripts/
│   ├── bootstrap_hubspot.py          # One-time custom property setup
│   ├── run_pipeline_once.py          # Manual trigger for testing
│   ├── run_sync_once.py              # Manual sync trigger
│   └── backfill_*.py                 # Migration helpers
│
└── tests/
    ├── __init__.py
    ├── conftest.py                   # pytest fixtures
    ├── unit/
    │   ├── test_rubrics.py
    │   ├── test_dedupe.py
    │   ├── test_vibe_adapter.py
    │   ├── test_hashing.py
    │   └── ...
    ├── integration/
    │   ├── test_pipeline_e2e.py      # With mocked external APIs
    │   └── test_sync_e2e.py
    └── live/                         # Marked @pytest.mark.live, skipped in CI
        ├── test_vibe_live.py
        ├── test_hubspot_live.py
        └── test_anthropic_live.py
```

### Why this structure

A few deliberate choices:

- **`src/` layout**, not a flat `sales_intelligence/` at the root. This is the modern Python standard and prevents "import from the checkout works but import from the installed package doesn't" bugs.
- **`domain/` has no I/O.** Scoring logic, dedupe rules, suppression checks — all pure functions. This makes testing trivial and keeps business rules from getting tangled with HTTP or DB code.
- **`adapters/` is the only place external services are touched.** If Vibe changes its API, there's exactly one file to update. Same for HubSpot, Perplexity, Anthropic.
- **`pipeline/` and `sync/` are separate** because they have different lifecycles (pipeline runs weekly, sync runs hourly) and different failure modes. Merging them would be convenient now and painful later.
- **Every table gets its own model file**, not one big `models.py`. 16 tables in one file is unreadable. One per file scales.
- **Tests mirror the src/ structure**, with `live/` tests explicitly gated behind a pytest marker so they only run when Michael wants them to (they cost money).

### Dependency manifest (`pyproject.toml`)

```toml
[project]
name = "gk-sales"
version = "0.1.0"
description = "Global Kinect Sales Intelligence"
requires-python = ">=3.12"
dependencies = [
    # Core
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "httpx>=0.27",
    "tenacity>=8.3",
    "structlog>=24.1",

    # Database
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.29",
    "alembic>=1.13",

    # Web (admin app)
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
    "jinja2>=3.1",
    "python-multipart>=0.0.9",
    "authlib>=1.3",                    # Google SSO
    "itsdangerous>=2.2",               # session cookies

    # External APIs
    "anthropic>=0.25",

    # GCP
    "google-cloud-secret-manager>=2.19",

    # Utilities
    "python-dotenv>=1.0",
    "python-dateutil>=2.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2",
    "pytest-asyncio>=0.23",
    "pytest-mock>=3.12",
    "respx>=0.21",                     # httpx mocking
    "ruff>=0.4",
    "mypy>=1.10",
    "faker>=25.0",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.12"
strict = true
plugins = ["pydantic.mypy"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "live: tests that call real external APIs (skipped by default)",
    "slow: tests that take > 1 second",
]
```

### Environment configuration (`.env.example`)

```bash
# === Database ===
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/gk_sales
DATABASE_POOL_SIZE=5

# === External APIs ===
VIBE_API_KEY=                          # Explorium / Vibe Prospecting
PERPLEXITY_API_KEY=
ANTHROPIC_API_KEY=
HUBSPOT_PRIVATE_APP_TOKEN=

# === HubSpot ===
HUBSPOT_PORTAL_ID=
HUBSPOT_DEFAULT_PIPELINE=default
HUBSPOT_NEW_LEAD_STAGE=appointmentscheduled

# === Admin app ===
ADMIN_SESSION_SECRET=                  # random 64-char string
ADMIN_GOOGLE_CLIENT_ID=
ADMIN_GOOGLE_CLIENT_SECRET=
ADMIN_ALLOWED_EMAILS=michael@globalkinect.co.uk

# === Runtime ===
ENV=development                         # development | staging | production
LOG_LEVEL=INFO
PIPELINE_DRY_RUN=false                  # If true, no writes to DB or HubSpot

# === Limits ===
PIPELINE_MAX_LEADS_PER_RUN=75           # Safety cap
PIPELINE_CONTROL_STREAM_PCT=20          # % of leads from segment-blind rule
```

### README stub

Claude Code should produce a README along these lines (expand during Task 01):

```markdown
# Global Kinect Sales Intelligence

Weekly lead generation, scoring, and AI-powered outreach drafting with HubSpot integration.

## What this is
See `docs/01-vision.md`.

## Repository layout
See `docs/04-repo-and-tasks.md`.

## Quickstart (development)

    # Install
    uv sync --dev

    # Set up local Postgres (Docker)
    docker compose -f docker/dev.yml up -d

    # Run migrations
    alembic upgrade head

    # Copy env template
    cp .env.example .env
    # fill in keys...

    # Run tests
    pytest

    # Manual pipeline trigger (dry run)
    python scripts/run_pipeline_once.py --segment cfo-mid-market --limit 5 --dry-run

## Deployment
See `docs/runbook.md`.

## Architecture
See `docs/01-vision.md` and `docs/02-schema.md`.
```

---

## Part 2: The first 10 Claude Code tasks

Each task is designed to be a single focused Claude Code session. They're ordered so each merge produces something verifiable and unblocks the next.

### Task 01 — Project scaffold and CI

**Goal:** Claude Code opens an empty repo and produces the directory structure, `pyproject.toml`, `.gitignore`, `.env.example`, CI workflow, and a trivial "hello world" entry point.

**Inputs:** This document (docs 01-04) already in `docs/`.

**Outputs:**
- Full directory tree per Part 1 above (empty `__init__.py` files in every package)
- `pyproject.toml` with dependency list
- `.gitignore` covering Python, Docker, venv, secrets
- `.env.example` with all env vars documented
- `.github/workflows/ci.yml` running ruff + mypy + pytest on every push
- `src/gk_sales/__main__.py` printing "GK Sales Intelligence v0.1.0"
- README.md matching stub above
- At least one passing test in `tests/unit/test_smoke.py` confirming the package imports

**Acceptance:**
- `uv sync --dev` (or `poetry install`) succeeds
- `pytest` runs with at least one passing test
- `ruff check .` passes
- `mypy src/` passes
- `python -m gk_sales` prints the version string
- CI workflow on a test PR goes green

**Estimated effort:** Small. 30-60 minutes of Claude Code work.

---

### Task 02 — Configuration, logging, and database engine

**Goal:** Wire up Pydantic settings, structured logging, and an async SQLAlchemy engine. No tables yet — just the plumbing.

**Inputs:** Task 01 merged. `.env` file with a real `DATABASE_URL` for local dev.

**Outputs:**
- `src/gk_sales/config/settings.py` — `Settings(BaseSettings)` class loading all env vars from `.env.example`
- `src/gk_sales/util/logging.py` — structlog configuration with JSON output in production, pretty output in dev
- `src/gk_sales/db/engine.py` — `async_engine` factory
- `src/gk_sales/db/session.py` — `async with session_scope() as session:` context manager
- `src/gk_sales/db/models/base.py` — `DeclarativeBase` with `id: UUID`, `created_at`, `updated_at` mixins
- Unit tests in `tests/unit/test_settings.py` and `tests/unit/test_logging.py`
- A small Alembic setup: `alembic.ini`, `migrations/env.py` wired to the settings module

**Acceptance:**
- `alembic current` runs without error against a local Postgres
- `python -c "from gk_sales.config.settings import settings; print(settings.env)"` works
- Structured logs appear when `ENV=development` (pretty) vs `ENV=production` (JSON)
- All tests still pass

**Estimated effort:** Small-medium. 1-2 hours.

---

### Task 03 — Schema migration: all 16 tables

**Goal:** Translate `docs/02-schema.md` plus the two additions from doc 03 (`sync_state`, `leads` ALTERs) into a single large Alembic migration. Also produce all SQLAlchemy model files.

**Inputs:** Task 02 merged. `docs/02-schema.md` and `docs/03-hubspot-contract.md` (schema additions section).

**Outputs:**
- One migration file: `migrations/versions/0001_initial_schema.py` creating all 16+ tables, indexes, constraints
- One SQLAlchemy model file per table in `src/gk_sales/db/models/`
- `src/gk_sales/db/models/__init__.py` exporting all models for easy imports
- Seed migration data: `cfo-mid-market` and `owner-smb-contractor` rows in `segments` with correct rubric names and filter JSONB from the Run 2/3/4 work
- Unit tests verifying each model can be instantiated and serialises correctly
- An integration test spinning up a test Postgres (via testcontainers or docker-compose) and running `alembic upgrade head` clean

**Acceptance:**
- `alembic upgrade head` on a fresh database produces all tables exactly as spec'd
- `alembic downgrade base` cleanly removes everything
- Every table referenced in doc 02 exists with the columns, types, and indexes described
- `sync_state` and the ALTER columns on `leads` are included
- Seed segments visible after migration

**Estimated effort:** Medium-large. 3-5 hours. This is the most important task to get right — mistakes compound.

**Notes for Claude Code:**
- Generate migration by hand, do not rely on autogenerate for this scale
- Use `server_default=func.now()` for `created_at`, not Python `datetime.now()`
- `updated_at` triggers: use a trigger function `refresh_updated_at()` applied to every table
- Test with `DROP DATABASE` + `CREATE DATABASE` between runs to catch state bugs

---

### Task 04 — Vibe Prospecting adapter

**Goal:** Port the Vibe API logic from the existing `sales-engine` Python scripts into a proper adapter module.

**Inputs:** Task 03 merged. Access to Vibe API key (in `.env`). Knowledge of fetch + enrich + export flow from existing scripts.

**Outputs:**
- `src/gk_sales/adapters/vibe.py` with:
  - `VibeClient` class (httpx-based, with retry/backoff via tenacity)
  - `async def fetch_prospects(filter: VibeFilter, count: int) -> list[ProspectRecord]`
  - `async def enrich_emails(table_id: str) -> EnrichmentResult`
  - `async def enrich_phones(table_id: str) -> EnrichmentResult`  (new — wasn't in sales-engine)
  - `async def export_to_csv(table_id: str) -> str`  (returns CSV content)
- `src/gk_sales/domain/models.py` — dataclasses: `ProspectRecord`, `VibeFilter`, `EnrichmentResult`
- Unit tests mocking all HTTP calls via respx
- One live test (marked `@pytest.mark.live`) that fetches a tiny filter (2-3 prospects) from real Vibe, verifying the end-to-end round trip

**Acceptance:**
- `pytest tests/unit/test_vibe_adapter.py` passes
- `pytest -m live tests/live/test_vibe_live.py` passes when `VIBE_API_KEY` is set
- No Vibe-specific field names leak past the adapter — all returned data is internal `ProspectRecord` type
- Proper typing throughout (mypy strict passes)
- Credit usage logged (structured log entry per API call)

**Estimated effort:** Medium. 2-4 hours.

---

### Task 05 — Scoring rubrics (CFO-first and Owner-first)

**Goal:** Port the existing scoring logic from `process_vibe_run3.py` and `process_vibe_run4.py` into pure, testable rubric modules.

**Inputs:** Task 04 merged. The two existing scoring scripts as reference.

**Outputs:**
- `src/gk_sales/domain/rubrics/base.py` — `RubricProtocol` with a single method `score(prospect: ProspectRecord) -> ScoreResult`
- `src/gk_sales/domain/rubrics/cfo_first_v1.py` — ports the CFO-first rubric
- `src/gk_sales/domain/rubrics/owner_first_v1.py` — ports the Owner-first rubric
- `src/gk_sales/domain/models.py` extended with `ScoreResult` (total + per-bucket breakdown)
- `src/gk_sales/domain/rubrics/__init__.py` — registry dict: `{'cfo-first-v1': CFOFirstV1(), 'owner-first-v1': OwnerFirstV1()}`
- Golden tests: a fixture of 20 prospects with known expected scores (derived from actual Run 3 and Run 4 CSV outputs)

**Acceptance:**
- Running the CFO-first rubric on 20 fixture prospects produces scores matching the existing `vibe_run3_top75.csv` within ±0 points (exact match)
- Running the Owner-first rubric against Run 4 fixture produces matching scores
- No I/O, no async, no external deps — these are pure functions
- Changing a rubric requires bumping its version (v1 → v1.1) so old scores remain interpretable

**Estimated effort:** Small-medium. 2-3 hours. Most of the logic already exists.

---

### Task 06 — Dedupe and suppression

**Goal:** Implement the 3-way dedupe rule from doc 02 and the suppression list check from doc 03.

**Inputs:** Task 05 merged.

**Outputs:**
- `src/gk_sales/domain/dedupe.py` with `async def find_duplicate(session, prospect: ProspectRecord) -> UUID | None` — returns existing lead ID if a dupe is found
- `src/gk_sales/domain/suppression.py` with `async def is_suppressed(session, prospect: ProspectRecord) -> SuppressionMatch | None`
- Both check against full DB, not just current run
- Unit tests covering: no dupes, email match, linkedin match, company+name match, multiple matches
- Suppression tests: email match, domain match, LinkedIn match, company domain match, expired suppression (ignored), permanent suppression

**Acceptance:**
- Given 1,000 leads in DB and a new prospect identical to one of them by email, dedupe returns that lead's ID in < 50ms
- Suppression check treats `expires_at > now()` as active and `expires_at < now()` as expired
- Dedupe is case-insensitive on email and company; linkedin is exact match (pre-normalised)

**Estimated effort:** Small. 1-2 hours.

---

### Task 07 — Lead persistence (Vibe → scored → saved)

**Goal:** Integration layer that takes a list of Vibe prospects, scores them, deduplicates, and inserts into Postgres. No external APIs beyond Vibe and DB.

**Inputs:** Tasks 04-06 merged.

**Outputs:**
- `src/gk_sales/pipeline/fetch.py` — orchestrates Vibe fetch + email enrichment + phone enrichment
- `src/gk_sales/pipeline/score.py` — applies the right rubric based on segment config
- `src/gk_sales/pipeline/persist.py` — dedupe check, suppression check, insert lead + update segment counters
- A command in `scripts/run_pipeline_once.py`: `python scripts/run_pipeline_once.py --segment cfo-mid-market --limit 10 --dry-run`
- Integration test: mock Vibe, run the flow, verify 10 leads land in the test DB with correct scores

**Acceptance:**
- `scripts/run_pipeline_once.py --segment cfo-mid-market --limit 10` against a real (sandbox) DB produces 10 lead rows with `status='new'`
- `--dry-run` flag does Vibe fetches but no DB writes
- Running twice produces zero duplicates on the second run
- Control stream logic: exactly 20% of produced leads have `control_stream=True` (configurable via env)
- Pipeline_runs row created at start, updated at end with status and totals

**Estimated effort:** Medium. 3-5 hours.

---

### Task 08 — Research and draft generation

**Goal:** Per-lead Perplexity research + Claude-authored email sequence + phone script. Persist all artefacts with full generation provenance.

**Inputs:** Task 07 merged. Existing `prompts/research_prompt.md` and `prompts/email_prompt.md` from sales-engine as starting points.

**Outputs:**
- `src/gk_sales/adapters/perplexity.py` — Perplexity client, `async def research(lead: Lead) -> ResearchResult`
- `src/gk_sales/adapters/anthropic_client.py` — Anthropic client with the email-sequence and phone-script prompts
- `src/gk_sales/pipeline/generate.py` — orchestrates: research → email sequence (4 touches) → phone script → persist all
- Prompt versioning: on first run, insert rows into `prompt_versions` for each of the 3 prompts (research, email_sequence, phone_script). Subsequent runs reuse the same version ID by hash match.
- Every generation event writes to `generation_events` table with full prompt, full output, tokens, latency, cost
- Research output stored in `lead_research`; emails in `lead_email_drafts`; phone script in `lead_phone_scripts`

**Acceptance:**
- End-to-end test: 3 leads, full generation runs, all 12 artefacts (3 research + 12 emails + 3 phone scripts) present in DB
- Each `lead_email_drafts` row has correct `sequence_position` (1-4) and `send_offset_days` (0, 3, 7, 14)
- `generation_events.prompt_rendered` contains the actual filled-in prompt, not the template
- Cost tracking: `api_cost_usd` populated using current Anthropic + Perplexity pricing
- If a generation call fails, the lead is marked with a warning but the pipeline continues with other leads

**Estimated effort:** Large. 5-8 hours. Most complex task in the first 10.

---

### Task 09 — HubSpot push (contact + deal + draft emails)

**Goal:** After leads + artefacts are persisted, push them to HubSpot per doc 03's push flow.

**Inputs:** Task 08 merged. HubSpot Private App token in `.env`. Custom properties already bootstrapped (see scripts/bootstrap_hubspot.py).

**Outputs:**
- `src/gk_sales/adapters/hubspot/client.py` — HTTP client with retry/backoff and rate-limit handling
- `src/gk_sales/adapters/hubspot/bootstrap.py` — creates the 5 contact + 2 deal custom properties if missing (idempotent)
- `src/gk_sales/adapters/hubspot/push.py`:
  - `async def create_contact(lead) -> str` (returns HubSpot contact ID)
  - `async def create_deal(lead, contact_id) -> str` (returns deal ID)
  - `async def create_email_engagement(draft, contact_id, deal_id) -> str` (returns engagement ID)
- `src/gk_sales/pipeline/persist.py` extended: after Postgres insert, call push flow; update lead with HubSpot IDs
- `scripts/bootstrap_hubspot.py` — one-time-run script that creates custom properties
- Integration tests mocking HubSpot responses; one live test against a HubSpot sandbox

**Acceptance:**
- Pipeline end-to-end: Vibe → score → persist → research + drafts → HubSpot. One clean run produces 5 leads visible in HubSpot sandbox with all custom properties populated
- Dedupe: re-running the pipeline doesn't create duplicate HubSpot contacts
- 4 draft emails per lead appear as engagements on the HubSpot contact, all marked `hs_email_status=DRAFT`
- Deal created and associated with contact
- If HubSpot push fails for one lead, that lead's `status` becomes `push-failed` and the run continues

**Estimated effort:** Medium-large. 4-6 hours.

---

### Task 10 — Hourly sync (HubSpot → Postgres)

**Goal:** The other direction. Pull engagement updates, deal stage changes, and SDR edits back from HubSpot on an hourly cadence.

**Inputs:** Task 09 merged. At least one pushed lead in HubSpot sandbox with activity to test against.

**Outputs:**
- `src/gk_sales/adapters/hubspot/pull.py` — incremental fetch using `hs_lastmodifieddate` filter
- `src/gk_sales/sync/engagements.py` — process email engagements, upsert to `lead_activity`, detect edits
- `src/gk_sales/sync/deals.py` — process deal stage changes, insert into `lead_outcomes`
- `src/gk_sales/sync/edits.py` — core SDR edit detection logic:
  - Email status transitioned DRAFT → SENT
  - Compare `hs_email_text` to the original `lead_email_drafts.body_markdown`
  - If identical: insert `sdr_edits` row with `action='sent-as-is'`
  - If different: insert `sdr_edits` row with `action='edited-then-sent'` and store both versions
- `src/gk_sales/sync/edits.py` also handles the daily "dead draft sweep" for `action='discarded'`
- `scripts/run_sync_once.py` — manual trigger
- Cursor tracking via `sync_state` table

**Acceptance:**
- First sync run after an SDR sends an unmodified draft: `sdr_edits` row created with `action='sent-as-is'`
- First sync run after an SDR edits then sends: `sdr_edits` row created with `action='edited-then-sent'` and both versions stored
- Deal stage changes in HubSpot appear as new `lead_outcomes` rows within 1 hour
- Cursor-based sync: running sync twice in quick succession doesn't re-process the same events

**Estimated effort:** Large. 5-8 hours.

**⚠️ Critical dependency on verification item #1 from doc 03.** Before starting this task, run the 10-minute HubSpot sandbox test: does `hs_email_text` reflect the final sent content after edits? If no, Task 10's approach shifts to Plan B (webhooks + diffing), which is a different implementation. This is the discovery item that should be tested earliest — ideally during Task 09.

---

## After Task 10

Ten tasks get us to a working pipeline with bidirectional HubSpot sync. That's Phase 1 substantially complete. Still to come:

**Tasks 11-15 (Phase 1 finishing):**
- Reply classification with Claude Haiku
- Admin web app: runs, leads, segments routes
- Admin web app: reports, suppression, metrics routes
- Cloud Run deployment + Cloud Scheduler wiring
- Monitoring and alerting setup

**Tasks 16-20 (Phase 2):**
- HubSpot UI extension scaffold (separate repo)
- UI extension: briefing card component
- Internal API for UI extension
- Sales users sync from HubSpot owners
- Daily backfill jobs (edit sweeps, dormant lead cleanup)

**Tasks 21+ (Phase 3 — agent layer):**
- Agent 1 (Strategist) prompt design and implementation
- Agent 2 (Quality Reviewer) implementation
- Weekly report generation and admin UI integration
- Recommendation outcome tracking
- Control stream analytics

These later tasks can be specified when we get closer to them — what matters is that the foundation (tasks 1-10) is solid, because everything downstream depends on it.

---

## Claude Code operating notes

A few patterns that tend to help when using Claude Code on multi-task projects:

**One task per session.** Don't try to squeeze Task 03 and 04 into one session. Context quality degrades with length.

**Commit per logical unit within a task.** Task 03 produces ~16 model files plus a migration; commit models first, then migration, then tests. Three commits, one PR.

**Let Claude Code run tests itself.** Part of each task's acceptance criteria is that tests pass. Claude Code should run pytest, see failures, fix them, run again. Don't manually run tests until Claude Code says it's done.

**Review the PR, not just the description.** Claude Code will summarise what it did. Read the actual diff, especially for migration files (Task 03), API code (Task 04, 09, 10), and anything touching auth.

**Flag drift.** If Claude Code starts producing code that diverges from the design docs (e.g., creating a new model not in `02-schema.md`), stop and ask why. Usually there's a good reason — but sometimes it's missing context and needs reminder.

**Prefer explicit over clever.** These docs deliberately spell things out. When Claude Code asks "should I refactor this into a decorator?" the answer is usually "no, keep it explicit." Optimise later if needed.

---

## What this document does NOT cover

- **Actual Python code.** Claude Code writes it per the tasks above.
- **Deployment specifics.** Cloud Run configuration, secret injection, networking — addressed in Tasks 14-15.
- **UI extension details.** Separate repo, separate documentation set, covered when Phase 2 begins.
- **Agent prompt engineering.** The agent tasks (21+) will include prompt designs, but those are outside Phase 1.
- **Cost estimation per task.** Claude Code usage costs vary; budget ~$5-20 of Claude Code usage per task.

---

## Phase 0 complete

With this document, Phase 0 is done. Four artefacts total:

1. `01-vision.md` — why and how
2. `02-schema.md` — the database
3. `03-hubspot-contract.md` — the integration
4. `04-repo-and-tasks.md` — the implementation roadmap

Each document stands on its own. Together they describe a complete system ready to be built.

**Next step (Michael):**

1. Answer the six verification items from doc 03 (HubSpot tier, existing contacts, Sequences usage, etc.)
2. Create the `globalkinect/sales-intelligence` private repo
3. Drop these four docs into `docs/`
4. Open Claude Code at the repo root
5. Prompt: "Implement Task 01 from docs/04-repo-and-tasks.md"
6. Review, merge, proceed to Task 02

The design is done. The build begins.
