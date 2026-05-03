> **SUPERSEDED on 2026-05-03** by `docs/audit/0001-existing-sales-engine.md`. Retained for audit trail; do not consult for current state.

# Sales Repository Audit

**Generated:** 2026-04-27
**Root path:** `C:\dev\globalkinect\sales`
**Scope:** every file and directory at depth ≥ 1 except the heavy/skipped dirs noted in §4.
**Posture:** read-only inspection. No deletions or renames recommended. Drift and entanglement are flagged at the end (§5) for later triage.

---

## Section 1 — Top-level inventory

```
C:\dev\globalkinect\sales
├── .claude\                         Claude Code settings (permissions, hooks)
├── .git\                            Git repo (not recursed — 2.0 MB, 376 files)
├── .pytest_cache\                   pytest caches (not recursed)
├── .env / .env.example              Runtime secrets and template (Anthropic, Notion, Supabase, Explorium, branding path)
├── .gitignore                       6-line ignore (only `venv/`, `__pycache__/`, `*.pyc`, `.env`, `.vscode/`, `.pytest_cache/`)
├── .graphify_detect.json            Graphify tooling config (~6.5 KB)
├── .mv_test_cross                   Empty file (test/move artefact — orphaned)
├── api\                             FastAPI proxy serving the dashboard (~35 KB)
│   └── app\
│       ├── main.py                  CORS-enabled FastAPI app, /api/health and /api/notion/*
│       └── routers\
│           └── notion_proxy.py      Read-only Notion proxy for the dashboard (~15 KB)
├── app\                             Main daily sourcing engine (Python, ~1.3 MB)
│   ├── agents\                      18 deterministic + Anthropic-backed agents
│   ├── models\                      19 Pydantic models for the domain
│   ├── orchestrators\               integration_check.py (test harness for live wiring)
│   ├── prompts\                     Empty (placeholder)
│   ├── services\                    NotionService (105 KB), DiscoverySourceService (55 KB), AnthropicService (27 KB), Supabase, Operator console, config
│   ├── utils\                       logger, time, identity, target_markets
│   └── web\
│       └── operator_console.py      Local operator web app (~57 KB) — Notion-backed approve/hold/regenerate UI
├── docs\                            Operational docs (~100 KB)
│   ├── archive\                     Historical: BUILD_LOG, INTERACTION_POLISH_CHANGELOG, SALES_ENGINE_TASKLIST
│   └── *.md                         INTERACTION_POLISH, NOTION_AI_PROMPTS, NOTION_INTEGRATION_READY_CHECKLIST, SUPABASE_READY_CHECKLIST, SUPABASE_SCHEMA_REFERENCE
├── graphify-out\                    Graphify knowledge-graph output (~9 MB)
│   ├── cache\                       91 SHA-named JSON files (extraction cache)
│   ├── obsidian\                    469 markdown notes — Obsidian wiki of the codebase
│   ├── GRAPH_REPORT.md              1052 nodes / 3481 edges / 29 communities
│   ├── graph.html / graph.json / manifest.json
├── leads\                           Generated lead artefacts AND nested dashboard project (~191 MB)
│   ├── _manifest.json               Run history of `sales-engine\` runs (68 KB)
│   ├── _run.log                     Pipeline run log (30 KB)
│   ├── Archive\Dashboard\           Old dashboard artefacts
│   ├── Reports\                     Generated reports
│   └── leads\                       **TanStack Start (Vite/React) dashboard project + nested Python backend** (189 MB)
│       ├── .git\                    Separate git repo (893 KB — embedded inside parent)
│       ├── backend\                 Independent Python backend (uv-managed, alembic, pyproject.toml) — Phase 1A scaffold
│       ├── src\                     React/TypeScript dashboard (TanStack Router, Radix UI, Lovable.dev cloud-auth)
│       ├── supabase\                Lovable's Supabase migrations + config
│       ├── docs\                    Dashboard-specific docs
│       ├── package.json / bun.lockb / wrangler.jsonc / vite.config.ts
│       └── (62 company-slug subdirs from sales-engine output runs)
├── main.py                          Daily sourcing engine entry point (~23 KB) — orchestrates app/agents/* end-to-end
├── migrations\                      Supabase Postgres migrations for the main engine
│   ├── 0001_initial_sales_schema.sql
│   ├── create_migration.py          Migration scaffold script
│   └── run_migrations.py            Forward-only runner
├── pytest.ini                       `pythonpath = .`
├── requirements.txt                 9 deps: httpx, anthropic, pydantic, psycopg, pytest, dotenv, supabase, fastapi, uvicorn
├── run_integration_check.py         CLI for `app/orchestrators/integration_check.py`
├── run_operator_console.py          One-line entry into `app/web/operator_console.py`
├── sales-engine\                    Standalone per-lead Perplexity+Claude pipeline (~18 MB)
│   ├── README.md                    Full setup + usage docs (separate venv from main engine)
│   ├── config\                      Empty (placeholder)
│   ├── csv\                         4 input CSVs (Vibe exports — `gk_vibe_run4_top75.csv`, `vibe_combined_top30.csv`, etc.)
│   ├── prompts\                     research_prompt.md, email_prompt.md
│   ├── scripts\                     run_pipeline.py
│   └── requirements.txt             Independent dependency list
├── scripts\                         Operational scripts for the main engine (~52 KB)
│   ├── run_monthly_scan.ps1         Sequential ICP scans + live `main.py` + scheduler snippet
│   └── vibe_prospecting_scan.py     Explorium API → Notion Lead Intake (with two-step business→prospect flow)
├── sops\                            Operator standard operating procedures (~20 KB)
│   ├── SOP_Demo_Preparation.md
│   ├── SOP_Pipeline_Management.md
│   └── SOP_Sales_Outreach.md
├── supabase_schema_reference.sql    Reference DDL (parallel to migrations/)
├── templates\                       Outbound asset templates (~415 KB)
│   ├── decks\                       GlobalKinect_Sales_Deck.pptx
│   ├── emails\                      9 HTML/text post-demo + proposal email templates (.ae and .co.uk pairs)
│   └── proposals\                   Empty (placeholder)
├── tests\                           24 pytest modules covering every agent + service (~1.7 MB)
├── venv\                            Python 3.13 virtualenv (not recursed — 109 MB)
├── discovery_sources.json           21+ active RSS / HTML / manual sources, 8 lanes (33 KB) — primary feed config
├── discovery_sources.example.json   Template version (9.3 KB)
├── strategic_account_entries.example.json   Template for hand-curated accounts (4.4 KB)
└── (21 root-level *.md files — see §3)
```

### Top-level directory size summary

| Dir | Size | Notes |
|---|---|---|
| `leads\` | **191 MB** | Mostly the nested `leads\leads\` dashboard (189 MB) — see §5 |
| `venv\` | 109 MB | Skipped |
| `sales-engine\` | 18 MB | Skipped its own `.venv` if present |
| `graphify-out\` | 9 MB | 469 markdown notes + 91 cache JSON |
| `.git\` | 2 MB | Skipped |
| `tests\` | 1.7 MB | Includes `__pycache__` |
| `app\` | 1.3 MB | Source code |
| `templates\` | 415 KB | |
| `docs\` | 100 KB | |
| `scripts\` | 52 KB | |
| `api\` | 35 KB | |
| `migrations\` | 32 KB | |
| `sops\` | 20 KB | |

---

## Section 2 — What each subsystem actually is

This repo is **four loosely-connected projects sharing one folder**, not one project. Audit observations in §5 build on the boundaries below.

### 2.1 Main daily sourcing engine

**Where:** `app\`, `main.py`, `tests\`, `migrations\`, `scripts\`, `api\`, `requirements.txt`
**What it does:** Daily Notion+Supabase orchestrator. Reads operator decisions back from Notion, qualifies discovery rows via Anthropic, normalises intake rows into Lead models, scores and packages outreach drafts into Notion's Outreach Queue, and persists everything to Supabase. Operator-approval gate via the Outreach Queue.
**Entry points:**
- `python main.py` — full sourcing cycle (shadow / live)
- `python main.py --generate-outreach --limit N --icp X` — separate Opportunities-DB outreach path
- `python run_operator_console.py` — local web console at 127.0.0.1:8787
- `python run_integration_check.py` — wiring validation
- `python scripts\vibe_prospecting_scan.py` — Explorium → Lead Intake feeder
- `.\scripts\run_monthly_scan.ps1` — full monthly scan + live run

**Agents (18 in `app\agents\`):** AutonomousLane, CrmUpdater, DiscoverySourceCollector, EntityMapper, Execution, LeadDiscovery, LeadFeedback, LeadResearch, LeadScoring, Lifecycle, MessageWriter, NotionSync, OpportunitiesOutreach, OutreachReview, PipelineIntelligence, ProposalSupport, ResponseHandler, SolutionDesign.

**Notable file sizes:**
- `app\services\notion_service.py` — 104.7 KB (single biggest file in the repo)
- `app\web\operator_console.py` — 57.2 KB
- `app\services\discovery_source_service.py` — 54.9 KB
- `app\services\anthropic_service.py` — 26.7 KB
- `app\agents\proposal_support_agent.py` — 24.5 KB
- `app\agents\message_writer_agent.py` — 22.6 KB

**Tests:** 128 tests across 24 files. Last full run: 127 pass, 1 deselect (`test_queue_page_renders_outreach_rows` is a pre-existing failure unrelated to recent changes).

### 2.2 Per-lead research + email pipeline (`sales-engine\`)

**Where:** `sales-engine\` (standalone — its own README, requirements.txt, and venv per its README)
**What it does:** Takes a ranked leads CSV, calls Perplexity sonar-deep-research per company, then Claude Opus 4.7 to draft an outreach email per lead. Writes per-company `report.md`, `email.md`, `metadata.json`. Resumable.
**Entry point:** `python sales-engine\scripts\run_pipeline.py`
**Inputs:** CSVs in `sales-engine\csv\` — most recent is `uae_ksa_hr_finance_leaders_gk_20260427151757.csv`.
**Outputs:** `leads\<company-slug>\` — `report.md`, `email.md`, `metadata.json`. Run-level state in `leads\_manifest.json` and `leads\_run.log`.

**Relationship to the main engine:** Independent. Different inputs, different outputs, different model stack (Perplexity not Anthropic for research). Not invoked from `main.py`.

### 2.3 Dashboard project (`leads\leads\`)

**Where:** `leads\leads\` (189 MB, nested)
**What it appears to be:** A Lovable.dev TanStack Start (Vite/React) dashboard with its own FastAPI/uv-managed Python backend (`leads\leads\backend\`) and its own Supabase config (`leads\leads\supabase\`). Has its own `.git\`, `.claude\settings.local.json`, `.env`, `.gitignore`, `.prettierrc`, `package.json`, `bun.lockb`, `wrangler.jsonc` (Cloudflare Workers).
**Phase per its backend README:** "Phase 1A scaffold — adapters, pipeline, and workers land in later tasks."
**Tooling:** uv (Python), bun (JS), alembic (migrations), Cloudflare Workers (deploy), Lovable.dev cloud-auth.
**Relationship to root engine:** Reads from the same Supabase project (per its README — backend reads `.env` from repo-root). Otherwise structurally separate.

The root-level `api\` directory is **a different FastAPI app** — a Notion proxy specifically for serving the dashboard's read-only Notion views. Not the same as `leads\leads\backend\`.

### 2.4 Output artefacts (`leads\` — non-dashboard parts)

**`leads\_manifest.json`** — run history from `sales-engine` (68 KB). Contains `runs[]` with timestamps, leads_processed, Perplexity + Claude usage/cost per lead.
**`leads\_run.log`** — pipeline run log (30 KB).
**`leads\Archive\Dashboard\`** — historical dashboard artefacts.
**`leads\Reports\`** — exported reports.
**`leads\leads\` company-slug subfolders** — present in nested project root, not in `leads\` directly. The original lead folders that were once at `leads\<slug>\` were moved (deleted-then-recreated under `leads\leads\leads\`?) — git status earlier in this session showed many deletions.

### 2.5 Asset & doc directories

| Path | Contents |
|---|---|
| `templates\decks\` | One PowerPoint: `GlobalKinect_Sales_Deck.pptx` (336 KB) |
| `templates\emails\` | 9 files — `.ae` and `.co.uk` post-demo + proposal pairs (HTML + plain text) plus `GK_Email_Sequence.html` (largest, ~1.2 MB) |
| `templates\proposals\` | Empty |
| `sops\` | 3 markdown SOPs: Demo Preparation, Pipeline Management, Sales Outreach |
| `docs\` | 5 active markdown + `archive\` with 3 historical |
| `graphify-out\obsidian\` | 469 auto-generated markdown notes (one per function/symbol). Lots of `.__init__()_NN.md` clones |

---

## Section 3 — Configuration files and root-level docs

### 3.1 Root configuration

| File | Size | Purpose | Notes |
|---|---:|---|---|
| `.env` | 1.6 KB | Live secrets | Holds real Anthropic/Notion/Supabase/Explorium keys plus four Notion DB IDs that were rewired this April |
| `.env.example` | 1.5 KB | Template | Last edited 2026-04-12 — matches current settings.py keys |
| `.gitignore` | 58 B | Minimal | Misses `node_modules`, `dist`, `.next`, `.venv` (the dashboard's), `bun.lockb`, `*.lockb`, `.mypy_cache`, `.ruff_cache`, `.graphify_detect.json` |
| `pytest.ini` | 24 B | `pythonpath = .` | |
| `requirements.txt` | 158 B | Pinned: `httpx==0.28.1`, `anthropic>=0.52.0`, `pydantic==2.12.5`, `psycopg[binary]==3.2.10`, `pytest==9.0.2`, `python-dotenv==1.2.2`, `supabase==2.28.3`, `fastapi==0.115.5`, `uvicorn==0.32.1` | Anthropic is unpinned (>=) |
| `.graphify_detect.json` | 6.5 KB | Graphify config | |
| `.mv_test_cross` | 0 B | Unknown | Empty file dated 2026-04-11 |
| `.claude\settings.json` | 2.5 KB | Permissions and hooks | Permission whitelist references `globalkinect-engines` (old path) and `globalkinect-engines-sales` — current location is `globalkinect\sales` |

### 3.2 Environment variables consumed by `app\services\config.py`

```
ANTHROPIC_API_KEY, ANTHROPIC_MODEL, ANTHROPIC_DISCOVERY_MODEL, ANTHROPIC_LEAD_RESEARCH_MODEL
SALES_ENGINE_RUN_MODE (live|shadow), SALES_ENGINE_TRIGGERED_BY
OPERATOR_CONSOLE_HOST, OPERATOR_CONSOLE_PORT
DISCOVERY_SOURCES_FILE, DISCOVERY_SOURCE_MAX_ITEMS_PER_SOURCE
SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY, DATABASE_URL
NOTION_API_KEY, NOTION_DISCOVERY_DATABASE_ID, NOTION_INTAKE_DATABASE_ID,
  NOTION_OUTREACH_QUEUE_DATABASE_ID, NOTION_RUNS_DATABASE_ID,
  NOTION_LEADS_DATABASE_ID, NOTION_PIPELINE_DATABASE_ID,
  NOTION_SOLUTIONS_DATABASE_ID, NOTION_TASKS_DATABASE_ID,
  NOTION_DEAL_SUPPORT_DATABASE_ID, NOTION_ACCOUNTS_DATABASE_ID,
  NOTION_BUYERS_DATABASE_ID, NOTION_OPPORTUNITIES_DATABASE_ID
BRANDING_REPO_PATH
VIBE_PROSPECTING_API_KEY, VIBE_PROSPECTING_API_BASE_URL
```

The dashboard backend (`leads\leads\backend\`) per its README also expects: `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`, `VIBE_API_KEY`, `PERPLEXITY_API_KEY`, `ENV`, `LOG_LEVEL`, `PIPELINE_*` runtime knobs. **Note `VIBE_API_KEY` vs the engine's `VIBE_PROSPECTING_API_KEY` — two different names for the same Explorium key.**

### 3.3 Root-level markdown (21 files)

Active operating docs:
- `README.md` (22 KB) — repo overview
- `CLAUDE.md` (3.4 KB) — Claude instructions, last updated 2026-04-22
- `AGENT_REGISTRY.md` (4.9 KB) — agent-by-agent table
- `OPERATOR_GUIDE.md`, `RUNBOOK.md`, `DECISION_PLAYBOOK.md`
- `ICP_SOURCING_PLAYBOOK.md` (65 KB) — full ICP definitions
- `SOURCING_STRATEGY.md`, `SOURCING_AGENTS.md`, `SOURCING_LANES.md`
- `SYSTEM_ARCHITECTURE.md`, `PROJECT_PLAN.md`
- `NOTION_DISCOVERY_SCHEMA.md`, `NOTION_INTAKE_SCHEMA.md`
- `DATABASE_MIGRATIONS.md`

Testing-phase docs (mostly dated March 24, 2026):
- `TESTING_PHASE_PLAN.md`, `PIPELINE_GAPS.md`, `IMPLEMENTATION_BACKLOG.md`

Audit / one-off:
- `GLOBAL_KINECT_SOURCING_AUDIT.md` (32 KB, dated 2026-04-09)

### 3.4 Data / config files

- `discovery_sources.json` (33 KB) — 8 lanes, 21 active sources after this April's repair pass; covers Expansion / Saudi RHQ / Payroll Complexity / HRIS Maturity / European Multi-Country / Funding & Growth / Manual Strategic Accounts / Direct Outbound
- `discovery_sources.example.json` (9.3 KB)
- `strategic_account_entries.example.json` (4.4 KB)
- `supabase_schema_reference.sql` (4.5 KB) — parallel to `migrations\0001_initial_sales_schema.sql`

---

## Section 4 — Skipped directories

Per the audit brief, these were noted but not recursed:

| Path | Files | Size | Reason |
|---|---:|---:|---|
| `.git\` | 376 | 2.0 MB | Git internal |
| `.pytest_cache\` | 6 | <0.1 MB | Pytest cache |
| `__pycache__\` (root) | 3 | <0.1 MB | Python bytecode |
| `app\agents\__pycache__\` | 18 | 0.2 MB | Python bytecode |
| `app\models\__pycache__\` | 20 | <0.1 MB | Python bytecode |
| `app\services\__pycache__\` | 8 | 0.3 MB | Python bytecode |
| `app\web\__pycache__\` | 1 | 0.1 MB | Python bytecode |
| `tests\__pycache__\` | (counted in tests) | (counted in tests) | Python bytecode |
| `venv\` | (Python 3.13 site-packages) | **109 MB** | Project virtualenv |
| `leads\leads\.git\` | nested | 893 KB | **Embedded git repo inside parent — see §5.1** |
| `leads\leads\backend\` (recursed at one level only) | (uv-managed Python tree) | **186 MB** | Includes `.venv\`, `.mypy_cache\`, `.pytest_cache\`, `.ruff_cache\` |

No `node_modules\` was found at any depth. No `dist\`, `.next\`, or `build\` directories.

---

## Section 5 — Observations (not recommendations)

These are the things a fresh eye would call out. **No action proposed yet**, just facts.

### 5.1 Multiple projects share the directory

- The repo contains **the main daily sourcing engine** (`app\`, `main.py`, etc.), **a per-lead research pipeline** (`sales-engine\`), **a dashboard project** (`leads\leads\` — TanStack/Lovable), and **a Notion-proxy API** (`api\`). They are loosely coupled through shared Notion DBs and `.env` keys.
- `leads\leads\` is **a separate git repository nested inside the parent** (`leads\leads\.git\`) — neither a submodule nor checked-in source. The parent `.gitignore` does not exclude it, so it shows up in the parent's `git status` as untracked content.
- `leads\leads\backend\` has its own `pyproject.toml`, `uv.lock`, `alembic.ini`, `.venv\` and is described as "Phase 1A scaffold" in its README — implying a future replacement for the engine in `app\`.

### 5.2 Two parallel Python pipelines

- `app\agents\message_writer_agent.py` (in the daily engine) generates outreach using deterministic templates and writes "GlobalKinect" as one word throughout.
- `app\agents\opportunities_outreach_agent.py` (the more recently added Opportunities path) calls Anthropic and is configured to enforce **"Global Kinect" as two words**, per the brand rules in `C:\dev\globalkinect\branding\GLOBAL_KINECT_BRAND.md`.
- Both ship into the same Outreach Queue. `MessageWriterAgent` therefore violates the canonical brand rule on every run, while the newer agent enforces it.
- `sales-engine\` is yet a third copy generator (Perplexity research + Claude email). Its outputs are written to `leads\<slug>\email.md` and never feed back into the main engine.

### 5.3 Two FastAPI apps + three Supabase configs

- `api\app\main.py` — root-level FastAPI, Notion proxy for the dashboard.
- `leads\leads\backend\app\` — separate FastAPI/uv project, "Phase 1A scaffold".
- Supabase: root `.env` has `SUPABASE_URL` / `SUPABASE_PUBLISHABLE_KEY` / `DATABASE_URL`. `leads\leads\supabase\migrations\` has the dashboard's Lovable-managed Supabase schema. `leads\leads\backend\migrations\` has alembic migrations on the same database. `migrations\` (root) has the engine's own Supabase migrations.
- Three migration histories on (apparently) one Supabase project — coordination is via convention only.

### 5.4 Drift in the operator-console / dashboard story

- Per `README.md`, the operating UI is `python run_operator_console.py` — a **server-rendered local web app** at 127.0.0.1:8787 (single 57 KB file: `app\web\operator_console.py`).
- Per `leads\leads\backend\README.md`, the new direction is a **TanStack/React dashboard with a FastAPI backend** that calls Supabase via service-role keys.
- `api\` (root) appears to be the bridge — a Notion proxy specifically built for the React dashboard. Its router is single-file (~15 KB) and read-only.
- Both UIs depend on the same Notion databases. There is no documented migration plan from the local web app to the React dashboard.

### 5.5 Notion DB IDs were re-pointed earlier this month

- Earlier in April, four DB IDs in `.env` pointed to **archived** databases titled `LEGACY — …` (Lead Intake, Leads, Solution Recommendations, Deal Support). They have since been replaced with live IDs.
- Test failures for `test_main.py::test_main_*` fixtures expect a `FakeNotionService` that lacks `is_outreach_queue_configured()`. The new `ResponseHandlerAgent` defends with `getattr` to keep tests green; if anyone replaces the fake later with a stricter test double, the response handler will need a real method on it.

### 5.6 Test suite has one persistent failure

- `tests\test_operator_console.py::test_queue_page_renders_outreach_rows` has been failing on `main` for the duration of recent work; verified pre-existing by stashing changes. All recent test runs deselect it. The text the test is asserting (`"Status and text filters apply together."`) is no longer in the rendered HTML — likely a copy change that the test wasn't updated for.

### 5.7 Documentation overlap and dating

- 21 root-level markdown files plus `docs\` (5 + archive of 3) plus `sops\` (3) plus `graphify-out\obsidian\` (469 generated). Many root-level files cross-reference each other (`README.md` links to `OPERATOR_GUIDE.md`, `DECISION_PLAYBOOK.md`, etc.).
- Most playbook docs are dated **March 24, 2026** (testing phase) and don't reflect the April work (Opportunities database, Vibe scan, Response Handler, dashboard project). `CLAUDE.md` was last edited 2026-04-22.
- `GLOBAL_KINECT_SOURCING_AUDIT.md` (32 KB, April 9) is a previous one-off audit — different concern from this one.
- `docs\archive\BUILD_LOG.md`, `INTERACTION_POLISH_CHANGELOG.md`, `SALES_ENGINE_TASKLIST.md` — all moved to `archive\` per a `.claude/settings.json` permission entry.

### 5.8 Stale / orphan artefacts

- `.mv_test_cross` — empty 0-byte file dated 2026-04-11. Likely a leftover from a `mv` cross-device test.
- `app\prompts\` — empty directory.
- `templates\proposals\` — empty directory.
- `sales-engine\config\` — empty directory.
- `graphify-out\obsidian\` contains 41 files matching `.__init__()_<n>.md` (one per `__init__` method across the codebase), generated by the `/graphify` skill. Useful to Claude, low signal-to-noise for human readers.
- `leads\` — git status from earlier this session showed dozens of `D` (deleted) entries for `leads\<slug>\email.md`, `metadata.json`, `report.md`. The current directory contents (62 company-slug folders under `leads\leads\leads\` not `leads\` directly) suggest the lead artefacts were moved when the dashboard project was added — but the parent's git index still records them at the old paths.

### 5.9 `.claude\settings.json` paths are stale

- The permission allowlist references `globalkinect-engines\sales` and `globalkinect-engines-sales` and `c:\dev\globalkinect-engines\sales\*`. The actual path is `c:\dev\globalkinect\sales`. `additionalDirectories` lists three paths under `globalkinect-engines\` that no longer exist. Hooks block referenced earlier in the file still uses the old paths. This means hook-driven commands and Read permissions for the project memory are pointing at a non-existent directory.

### 5.10 `.gitignore` is too narrow for what's now in the tree

- Doesn't exclude: `.venv\` (used by `leads\leads\backend\`), `node_modules\` (would matter if the dashboard ever installs npm deps locally), `bun.lockb` is intentionally tracked but `dist\` / `.next\` / `build\` aren't excluded, `.mypy_cache\`, `.ruff_cache\` (both present in `leads\leads\backend\`), `.graphify_detect.json`, `graphify-out\` (currently tracked at 9 MB).
- Result: a fresh `git status` in this repo will show large amounts of untracked content the moment the dashboard's tooling runs.

### 5.11 File-type breakdown (excluding all skipped dirs)

| Extension | Files | Total size |
|---|---:|---:|
| `.md` | 1,249 | 3.17 MB (~470 of these are graphify-generated wiki notes) |
| `.json` | 169 | 4.40 MB (mostly `graphify-out\cache\`) |
| `.py` | 114 | 0.78 MB |
| `.tsx` | 71 | 0.21 MB (dashboard) |
| `.txt` | 36 | 0.01 MB |
| `.ts` | 10 | 0.06 MB (dashboard) |
| `.html` | 6 | 1.42 MB (`templates\emails\GK_Email_Sequence.html` dominates) |
| `.sql` | 5 | 0.03 MB |
| `.csv` | 4 | 0.09 MB (sales-engine inputs) |
| `.toml` | 3 | <0.01 MB |
| `.lockb` | 1 | 0.32 MB (`bun.lockb`) |
| `.lock` | 1 | 0.36 MB (`uv.lock` in dashboard backend) |
| `.pptx` | 1 | 0.33 MB (sales deck) |
| `.ps1` | 1 | <0.01 MB (`run_monthly_scan.ps1`) |
| `.css`, `.js`, `.jsonc`, `.mako`, `.ini`, `.example`, `.log` | small counts each | |

---

## Inputs that informed this audit

- Full directory walk to depth ≥ 3 with size + file-count per skipped dir
- File reads: every `.py` in `app\agents\`, `app\models\`, `app\services\` (sample), `api\`, `main.py`, `scripts\`, plus all root-level markdown excerpts already loaded earlier this session
- Live `git status` was not re-run for this audit; references to deleted lead folders come from a previous `git status` output earlier in the session
- Live API tests not re-run for this audit
