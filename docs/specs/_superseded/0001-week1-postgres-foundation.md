> SUPERSEDED by 0001-week1-supabase-foundation.md on 2026-05-03.

# Spec 0001 — Week 1: Postgres Foundation, Auth Scaffold, Ingestion Spine

**Status:** Draft for review
**Author:** Claude (with Michael)
**Date:** 2026-05-03
**Target completion:** end of week 1 of the one-month build
**Predecessors:** `docs/architecture/target-state-v2.md`, `docs/audit/0001-existing-sales-engine.md`
**Successors:** Spec 0002 (Week 2 — HubSpot bidirectional sync + Instantly push)

---

## What this spec is for

This is the document Claude Code works from for week 1 of the build. It specifies, concretely, what gets built: every table, every script, every decision point. After this spec is reviewed and accepted, Claude Code can execute it without needing to re-derive choices.

Anything not specified here is **out of scope for week 1**. Adding scope mid-week is a defect, not flexibility.

---

## Scope

In scope:
- Stand up isolated Cloud SQL Postgres instance for the sales engine
- Create all schema tables defined in target-state-v2 §4
- Seed pipelines, seed initial users, seed pipeline stages
- Build the dedup library (`services/dedup.py`)
- Rewire `scripts/vibe_prospecting_scan.py` to dual-write (Postgres + Notion)
- One-shot backfill: import existing HubSpot Contacts/Companies into Postgres
- One-shot backfill: walk `leads/Reports/<slug>/` folders, create matching `contacts` and `assets` rows
- Set up Clerk auth scaffold (account, application, JWT validation in FastAPI)
- Verify end-to-end: a fresh Vibe scan produces deduplicated rows in Postgres; a test JWT validates against the FastAPI middleware

Out of scope (defer to week 2 or later):
- HubSpot bidirectional sync (write-back from Postgres to HubSpot) — week 2
- Instantly push or webhook receiver — week 2
- Notion sync direction flip (still dual-writing to Notion this week) — week 3
- Asset generation services (research, email, sequence, call, linkedin) — week 3
- SDR dashboard UI — week 4
- Retiring `sales-engine/` v1 — week 3 (after v2 services replace it)
- Login flows beyond a basic JWT validation test — week 4 (full dashboard auth)

---

## Pre-flight checks

Before any code work starts, confirm:

- [ ] Clerk account created at `clerk.com`, application provisioned named **"Global Kinect Sales"**
- [ ] Cloud SQL Postgres instance provisioned in GCP — instance name `gk-sales-prod`, region `europe-west2` (London), tier `db-f1-micro` for now (~$30/month, sufficient for the foreseeable scale)
- [ ] Postgres `gk_sales` database created on that instance
- [ ] Postgres user `gk_sales_app` created with full schema privileges on `gk_sales`
- [ ] Connection string accessible via env var `SALES_DATABASE_URL` in the new env file
- [ ] Branch created: `git checkout -b week-1-postgres-foundation`

If any of these aren't done, do them first and confirm before starting code work.

---

## Filesystem layout

All week-1 work lives under these new paths in the existing `c:\dev\globalkinect\sales` repo:

```
sales/
├── sales_db/                          NEW — week 1 home
│   ├── __init__.py
│   ├── migrations/                    forward-only schema migrations
│   │   ├── 0001_users_and_pipelines.sql
│   │   ├── 0002_companies_and_contacts.sql
│   │   ├── 0003_deals_and_activities.sql
│   │   ├── 0004_sequences_and_assets.sql
│   │   ├── 0005_accounts_and_runs.sql
│   │   └── 0006_seed_data.sql
│   ├── runner.py                      migration runner (mirrors existing migrations/run_migrations.py pattern)
│   ├── connection.py                  Postgres connection helper using SALES_DATABASE_URL
│   └── README.md                      how to run migrations against gk_sales
├── sales_services/                    NEW
│   ├── __init__.py
│   ├── dedup.py                       Contact dedup library
│   └── auth.py                        Clerk JWT validation helpers
├── sales_ingestion/                   NEW
│   ├── __init__.py
│   ├── hubspot_backfill.py            one-shot HubSpot → Postgres import
│   └── reports_backfill.py            one-shot leads/Reports/ folder walk → Postgres
├── sales_api/                         NEW (skeleton only this week — full API is week 2/4)
│   ├── __init__.py
│   ├── main.py                        FastAPI app with /healthz and /me endpoints only
│   └── auth_middleware.py             JWT validation middleware
└── scripts/
    └── vibe_prospecting_scan.py       MODIFIED — now dual-writes Postgres + Notion
```

Naming note: prefix `sales_` on new top-level packages prevents collision with the existing `app/` package and makes intent obvious. Existing `app/`, `api/`, `migrations/` are untouched this week.

---

## Tasks, in order

### Task 1 — Migration runner and connection helper

Build `sales_db/runner.py` and `sales_db/connection.py`.

**`sales_db/connection.py`:**
- One function `get_connection()` that reads `SALES_DATABASE_URL` from env and returns a `psycopg2.connect()` connection.
- Use `psycopg2-binary` (already in requirements) — do not add new deps.
- All connections opened with `autocommit=False` by default.

**`sales_db/runner.py`:**
- Reads all `*.sql` files in `sales_db/migrations/` in lexicographic order.
- Maintains a `_schema_migrations` table (auto-created if absent) tracking applied migrations by filename.
- Idempotent: rerunning skips already-applied migrations.
- CLI: `python -m sales_db.runner` runs all pending migrations against the database in `SALES_DATABASE_URL`.
- Mirrors the pattern in existing `migrations/run_migrations.py` — read it, follow the same conventions.

**Acceptance:**
- `python -m sales_db.runner` against an empty database creates `_schema_migrations` and exits cleanly.
- Running it twice in a row is a no-op the second time.

### Task 2 — Migration 0001: users and pipelines

`sales_db/migrations/0001_users_and_pipelines.sql`. Creates:

```sql
-- _schema_migrations is created automatically by runner.py; do not declare here.

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- for gen_random_uuid()

CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email           text NOT NULL,
    full_name       text,
    role            text NOT NULL CHECK (role IN ('admin','sdr','manager','viewer')),
    active          boolean NOT NULL DEFAULT true,
    sso_subject     text,
    created_at      timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    last_login_at   timestamptz
);
CREATE UNIQUE INDEX users_email_lower_idx ON users (lower(email));
CREATE UNIQUE INDEX users_sso_subject_idx ON users (sso_subject) WHERE sso_subject IS NOT NULL;

CREATE TABLE pipelines (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    slug            text NOT NULL UNIQUE,
    stages          jsonb NOT NULL,
    active          boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
```

The `stages` JSONB column holds an ordered list of `{id, name, order, default_probability}` objects. Stages are seeded in migration 0006.

**Acceptance:**
- After running, `\dt` in psql shows `users` and `pipelines`.
- Inserting a duplicate email (case-insensitive) into `users` raises a unique violation.

### Task 3 — Migration 0002: companies and contacts

`sales_db/migrations/0002_companies_and_contacts.sql`. Creates `companies` and `contacts` per target-state-v2 §4. Notable points:

- `contacts.email` UNIQUE INDEX on `lower(email)` where email is not null.
- `contacts.linkedin_url` indexed (not unique — some sources don't return URL, multiple nulls allowed).
- `contacts.owner_id` FK to `users(id)` with `ON DELETE SET NULL` (don't lose Contacts when a user is deleted; just unassign).
- `contacts.status` CHECK constraint on the seven defined statuses.
- `companies.company_role` CHECK constraint on `('end_buyer','eor_provider','partner','competitor','unknown')`.
- All `*_at` timestamps default `(now() AT TIME ZONE 'utc')`.
- Trigger function `set_updated_at()` that updates `updated_at` on UPDATE; attached to both tables.

**Acceptance:**
- Inserting a Contact with the same lowercased email as an existing one fails.
- Updating any column on `contacts` automatically bumps `updated_at`.

### Task 4 — Migration 0003: deals and activities

`sales_db/migrations/0003_deals_and_activities.sql`. Creates `deals` and `activities`. Notable points:

- `deals.pipeline_id` FK to `pipelines(id)` ON DELETE RESTRICT.
- `deals.stage` is a free `text` column — validated at the application layer against the pipeline's `stages` JSONB. Don't enforce stage names at DB level; pipelines' stages can evolve.
- `deals.motion_subtype` CHECK on `('volume','curated')` OR NULL (only end-buyer pipeline uses subtype).
- `activities.performed_by` FK to `users(id)` ON DELETE SET NULL, nullable.
- `activities.performed_by_system` text, nullable. Application enforces "exactly one of performed_by / performed_by_system is non-null."
- Composite indexes per target-state §4.

**Acceptance:**
- Creating a Deal referencing a non-existent pipeline fails.
- Deleting a User does not delete their Activities — `performed_by` becomes NULL.

### Task 5 — Migration 0004: sequences and assets

`sales_db/migrations/0004_sequences_and_assets.sql`. Creates `sequences`, `sequence_steps`, `assets`. Notable points:

- `sequences.template` is free text, application-validated against known templates (`'direct_outbound_5touch'`, `'eor_partnership_long'`).
- `sequence_steps` UNIQUE on `(sequence_id, step_number)` to prevent duplicate steps.
- `assets.storage_path` is a relative path from repo root (e.g., `leads/Reports/<slug>/email.md`). Stored as text; application resolves to absolute path at read time.
- `assets.metadata` JSONB holds model name, token counts, cost, citations.

**Acceptance:**
- Cannot insert two `sequence_steps` rows with the same `(sequence_id, step_number)`.
- An `asset` with no `storage_path` fails.

### Task 6 — Migration 0005: accounts and runs

`sales_db/migrations/0005_accounts_and_runs.sql`. Creates `accounts` and `runs`. Notable:

- `accounts.account_owner_id` FK to `users(id)` ON DELETE SET NULL.
- `runs.metrics` and `runs.errors` are JSONB, nullable.
- `runs.status` CHECK on `('running','success','failed','partial')`.

**Acceptance:** straightforward — both tables exist, FKs work.

### Task 7 — Migration 0006: seed data

`sales_db/migrations/0006_seed_data.sql`. Inserts:

**Pipelines:**

```sql
INSERT INTO pipelines (slug, name, stages) VALUES
('end_buyer_sales', 'End-buyer sales',
  '[
    {"id":"new","name":"New","order":1,"default_probability":5},
    {"id":"contacted","name":"Contacted","order":2,"default_probability":10},
    {"id":"engaged","name":"Engaged","order":3,"default_probability":20},
    {"id":"meeting_booked","name":"Meeting booked","order":4,"default_probability":35},
    {"id":"demo_held","name":"Demo held","order":5,"default_probability":50},
    {"id":"proposal_sent","name":"Proposal sent","order":6,"default_probability":65},
    {"id":"negotiation","name":"Negotiation","order":7,"default_probability":80},
    {"id":"won","name":"Won","order":8,"default_probability":100},
    {"id":"lost","name":"Lost","order":9,"default_probability":0},
    {"id":"nurture","name":"Nurture","order":10,"default_probability":5}
  ]'::jsonb),
('eor_partnership', 'EOR partnership',
  '[
    {"id":"identified","name":"Identified","order":1,"default_probability":5},
    {"id":"mapped","name":"Mapped","order":2,"default_probability":10},
    {"id":"initial_call","name":"Initial call","order":3,"default_probability":20},
    {"id":"technical_eval","name":"Technical evaluation","order":4,"default_probability":35},
    {"id":"commercial_discussion","name":"Commercial discussion","order":5,"default_probability":50},
    {"id":"pilot_design","name":"Pilot design","order":6,"default_probability":65},
    {"id":"pilot_active","name":"Pilot active","order":7,"default_probability":80},
    {"id":"partnership_signed","name":"Partnership signed","order":8,"default_probability":100},
    {"id":"lost","name":"Lost","order":9,"default_probability":0},
    {"id":"paused","name":"Paused","order":10,"default_probability":10}
  ]'::jsonb);
```

**Initial admin user (Michael):**

```sql
INSERT INTO users (email, full_name, role) VALUES
  ('michael@globalkinect.ae', 'Michael Gill', 'admin');
```

(Confirm the canonical email address before running. If `michael@globalkinect.co.uk` is preferred, swap.)

**Acceptance:**
- After migration 0006, `SELECT slug, jsonb_array_length(stages) FROM pipelines` returns the two pipelines with 10 stages each.
- Michael's user row exists with `role='admin'`.

### Task 8 — Dedup library

`sales_services/dedup.py`. One module-level function:

```python
def find_existing_contact(
    conn,
    email: str | None = None,
    linkedin_url: str | None = None,
    first_name: str | None = None,
    last_name: str | None = None,
    company_id: uuid.UUID | None = None,
) -> uuid.UUID | None:
    """
    Returns the id of an existing contact that matches, or None.

    Match priority (first match wins):
    1. email match (case-insensitive) — highest confidence
    2. linkedin_url exact match — high confidence
    3. (first_name + last_name + company_id) match — medium confidence

    Returns the contact id if any rule matches; None otherwise.
    """
```

Implementation notes:
- Each match rule is a separate SQL query. Don't try to combine into one big OR — performance and readability both suffer.
- Email comparison: `lower(email) = lower(%s)`.
- LinkedIn: strip trailing slash, normalise to `https://` prefix, then exact match. The `linkedin_url` column should be normalised on insert (do this in the ingestion code, not here).
- Name+company: only matches when all three of first_name, last_name, company_id are provided. Skip silently if any is missing.

Tests:
- `tests/test_sales_dedup.py` — six cases minimum:
  - email match found (returns id)
  - email not present, linkedin match found (returns id)
  - both email and linkedin missing, name+company match found (returns id)
  - email mismatched (returns None)
  - all three missing (returns None)
  - email matches but linkedin URL also provided and doesn't match — should still return on email (priority order)

**Acceptance:** all six tests pass against a test database loaded with fixture rows.

### Task 9 — Vibe Prospecting rewire (dual-write)

`scripts/vibe_prospecting_scan.py` — modify to **add** Postgres writes alongside existing Notion writes. **Do not remove the Notion writes this week** — dual-write protects against rollback.

Modification points:

1. After each Explorium prospect is normalised into the existing dict shape, **also** call new function `write_to_postgres(prospect_dict)` from a new module `sales_ingestion/vibe_to_postgres.py`.

2. `write_to_postgres()` does:
   - Open Postgres connection
   - Resolve or create `companies` row (match by `lower(domain)` if domain known, else by name+country)
   - Run dedup against `contacts` table via `dedup.find_existing_contact()`
   - If existing contact found: log skip, do nothing further (don't update — let the human review later in dashboard)
   - If not found: insert new `contacts` row with `source='vibe'`, `status='new'`, `source_metadata` = full Explorium response JSONB
   - Wrap in a transaction; commit on success; rollback + log on failure

3. At the end of the scan, log a summary line: `Vibe scan: N attempted, M new contacts created, K duplicates skipped, J errors`.

**Acceptance:**
- Run a test scan with `--limit 5` against a known set of Explorium queries.
- Postgres `contacts` table grows by exactly the number of non-duplicates.
- Notion Lead Intake DB still receives all prospects (existing behaviour unchanged).
- Re-running the same scan adds zero new Postgres rows (dedup works).

### Task 10 — HubSpot backfill (one-shot)

`sales_ingestion/hubspot_backfill.py`. One-shot script that:

1. Pulls all Contacts from HubSpot via the HubSpot API (paginated).
2. For each Contact, also pulls the associated Company.
3. Writes Companies and Contacts into Postgres, with `source='hubspot_import'`, `hubspot_id` populated, `source_metadata` containing the full HubSpot response.
4. Uses dedup library — if a Contact already exists in Postgres (e.g., from an earlier Vibe scan), updates the `hubspot_id` field on the existing row but does not overwrite other data.
5. Logs progress every 100 Contacts.
6. CLI flags: `--dry-run` (no writes, just count), `--limit N` (process only first N), `--full` (process all).

Implementation notes:
- HubSpot API key in env: `HUBSPOT_API_KEY`. Already in the existing `.env`.
- Use the `hubspot` Python client if available; else raw `httpx` calls. Whichever is simpler.
- Backfill is one-shot — don't build for repeated execution. Future incremental sync is week 2.

**Acceptance:**
- Dry-run reports the total Contact count from HubSpot.
- A `--limit 10` run creates ≤10 new Postgres `contacts` rows, each with `hubspot_id` set.
- A subsequent `--limit 10` run with the same 10 Contacts creates zero new rows (dedup), but updates `hubspot_id` on any rows that previously didn't have one.

### Task 11 — `leads/Reports/` backfill (one-shot)

`sales_ingestion/reports_backfill.py`. One-shot script that:

1. Walks `leads/Reports/<slug>/` directories.
2. For each slug, reads the `metadata.json` to extract Contact info (name, email, role, company, linkedin, mobile).
3. Runs dedup. If Contact exists, links the assets to the existing Contact. If not, creates a new Contact with `source='manual'`, `source_metadata` containing the metadata.json.
4. For each of `report.md`, `email.md`, `sequence.md`, `call.md`, `linkedin.md` that exists in the folder, creates an `assets` row pointing at the file path.
5. **Does not modify or move any files in `leads/Reports/`** — folder remains SACRED.

CLI: `--dry-run`, `--limit N`.

**Acceptance:**
- Dry-run reports the count of folders and assets that would be processed.
- A real run creates one `contact` per folder (or links to existing) and one `asset` per markdown file present.
- `leads/Reports/` content is byte-identical before and after — no file mutations.

### Task 12 — Clerk auth scaffold

Two parts: configuration + JWT validation library.

**Configuration:**
- Clerk application configured (manual, in Clerk dashboard):
  - Application name: "Global Kinect Sales"
  - Allowed sign-in methods: Email + Google SSO (sufficient for now)
  - Frontend URL: `http://localhost:3000` for dev, `https://sales.globalkinect.ae` reserved for production
- Add to `.env`:
  ```
  CLERK_PUBLISHABLE_KEY=pk_test_...
  CLERK_SECRET_KEY=sk_test_...
  CLERK_JWKS_URL=https://...clerk.accounts.dev/.well-known/jwks.json
  ```
- These three values are taken from Clerk dashboard.

**`sales_services/auth.py` — JWT validation:**

```python
def validate_clerk_jwt(token: str) -> dict | None:
    """
    Validates a Clerk-issued JWT. Returns the decoded claims dict
    if valid, None if invalid or expired.

    Uses Clerk's JWKS endpoint to fetch and cache signing keys.
    """
```

- Use `python-jose[cryptography]` for JWT validation. Add to requirements.txt.
- Cache JWKS keys in memory with 1-hour TTL.
- On valid token, returns claims including `sub` (Clerk user ID), `email`, `name`.

**`sales_api/auth_middleware.py` — FastAPI middleware:**

- Reads `Authorization: Bearer <token>` header.
- Calls `validate_clerk_jwt(token)`.
- On success, attaches `request.state.user_claims` and looks up matching `users` row by `sso_subject` (or by email as fallback). If no `users` row exists for this email, creates one with `role='sdr'` and the matching email/name; updates `last_login_at`.
- On failure, returns 401.

**`sales_api/main.py` — minimal FastAPI app:**

- Two endpoints:
  - `GET /healthz` — public, returns `{"status":"ok"}`
  - `GET /me` — requires valid JWT, returns the matched user row from Postgres
- Run on port 8788 (Operator Console is on 8787 — do not collide).

**Acceptance:**
- Get a test JWT from Clerk's dashboard.
- `curl http://localhost:8788/healthz` returns 200.
- `curl http://localhost:8788/me` without a token returns 401.
- `curl http://localhost:8788/me -H "Authorization: Bearer <test-token>"` returns 200 with the matched user row.
- A second login with a new email creates a fresh `users` row with `role='sdr'`.

### Task 13 — End-to-end verification

A single test that exercises the whole week-1 build:

1. Drop and recreate `gk_sales` database from scratch.
2. Run all migrations: `python -m sales_db.runner`. Confirms 6 migrations applied.
3. Run HubSpot backfill with `--limit 50`. Confirm 50 new Postgres rows.
4. Run reports backfill (full). Confirm rows match folder count.
5. Run Vibe scan with `--limit 10`. Confirm new rows appear, with `source='vibe'`.
6. Confirm dedup: re-run Vibe scan with `--limit 10`. Confirm zero new rows added.
7. Confirm auth: hit `/me` with a test JWT, confirm 200 response and a matching `users` row exists.

This sequence is captured as a manual acceptance checklist (not yet automated — automation comes in week 2 alongside the bidirectional sync).

---

## Open questions to resolve before week 1 starts

1. **Confirm Michael's canonical email** — `michael@globalkinect.ae` or `michael@globalkinect.co.uk`? Used in the seed data.
2. **Confirm Cloud SQL region** — `europe-west2` (London) is suggested. Saudi data residency only applies to platform data, not sales data; sales infrastructure can sit in London. Confirm or override.
3. **Confirm Clerk vs. WorkOS** — spec assumes Clerk. If you'd rather WorkOS, flag now (changes Tasks 12 substantively).

---

## Week-1 success summary

By end of week 1, demonstrably:

- `gk_sales` Postgres database exists, isolated from platform infrastructure
- All 8 tables created with correct constraints, indexes, and FKs
- Two pipelines seeded with all stages
- Michael (admin) seeded as a `users` row
- Dedup library finds existing Contacts by email, LinkedIn, or name+company
- Vibe scans dual-write to Postgres + Notion, with dedup applied
- Existing HubSpot Contacts/Companies imported into Postgres
- Existing `leads/Reports/` content reflected as Postgres `contacts` + `assets` rows (folder untouched)
- Clerk auth scaffold working: a valid JWT validates against the FastAPI middleware, an unknown user gets a fresh `users` row created on first login

Anything beyond this is week 2. Specifically: HubSpot write-back, Instantly anything, agent rewiring, and asset generation services are NOT week-1 work.

---

## Working practice during week 1

Per the audit-first / spec-first / challenge-before-accept commitment:

- Every Claude Code session in week 1 starts by reading **this spec** and `docs/architecture/target-state-v2.md`. No code work without those two documents in context.
- Each task above is a single Claude Code session's worth of work, more or less. Don't combine them in one prompt — work through them sequentially.
- After each task, run the acceptance check. Don't move on if the check fails.
- If a task's acceptance check reveals that the spec itself was wrong, **stop and amend the spec**. Don't paper over with "I'll fix it later."
- All code lands on `week-1-postgres-foundation` branch. PR to main at end of week, after the end-to-end verification passes.

---

**End of Spec 0001.**
