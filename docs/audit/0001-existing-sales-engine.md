# Audit 0001 — Sales Repo System Audit

**Date:** 2026-05-03
**Auditor:** Claude Code (model: Claude Opus 4.7 [1m] — `claude-opus-4-7`)
**Reviewer:** Michael Gill, 2026-05-03
**Status:** Accepted
**Repo path:** `C:\dev\globalkinect\sales`
**Git HEAD at audit start:** `462dcc4` on branch `main`
**Remote:** `https://github.com/gill-michael/globalkinect-sales.git`

---

## 1. Scope and boundaries

**In scope:** every file and subfolder under `C:\dev\globalkinect\sales`, including uncommitted work, untracked files, the nested `leads/leads/` git repo, all `.env` files, all configs, all generated lead artefacts.

**Out of scope:** external service state (Notion DBs, Supabase tables, Explorium account credits, Anthropic billing, Lovable.dev hosting, Cloudflare Workers, Perplexity account). Credentials are referenced by env-var name only — values were never read.

**Restricted (per project `CLAUDE.md`):** `C:\dev\globalkinect\keys\` — not opened.

**State at audit time:** Working tree is dirty. `git status` shows `M .claude/settings.json`, `M CLAUDE.md`, 51 deletions of `leads/<slug>/` artefacts (now relocated under `leads/Reports/<slug>/`), `M leads/_manifest.json`, `M leads/_run.log`, `M sales-engine/csv/vibe_combined_top30.csv`, `M sales-engine/scripts/run_pipeline.py`. Untracked: `.graphify_detect.json`, `AUDIT.md`, `docs/INSPECTION_REPORT.md`, `docs/README.md`, `docs/audit/`, `leads/leads/`, `sales-engine-v2/`, `sales-engine.zip`, `sales-engine/.claude/`, three new CSV files in `sales-engine/csv/`.

**Two pre-existing audit-style documents informed this audit:**

- [AUDIT.md](AUDIT.md) — 2026-04-27, 25.7 KB, untracked. A previous read-only inventory by Claude Code. Substantially overlaps Sections 2–4 here. Where its findings remain accurate, this audit cites it; where they have shifted (notably the gitignore rewrite, the operator console maturing, the dashboard-backend archival, and the May-3 creation of `sales-engine-v2/`), this audit notes the delta.
- [docs/SYSTEM.md](docs/SYSTEM.md) — 2026-04-28, the human-authored "source of truth" referenced from `README.md`. It is intent-shaped (what each subsystem is *for*), not behaviour-shaped. This audit treats it as a source of stated intent against which observed behaviour is checked.

This audit does NOT supersede either; it is a fresh observation as of 2026-05-03.

---

## 2. Inventory

### 2.1 Top-level structure (depth 3, noise excluded)

```
C:\dev\globalkinect\sales
├── .claude\                          Claude Code permissions + hooks
├── .git\                             Main repo .git (skipped)
├── .pytest_cache\                    Skipped
├── .env                              Live secrets (1.6 KB)
├── .env.example                      Template (1.5 KB)
├── .gitignore                        2.0 KB — comprehensive (rewritten since AUDIT.md noted it was 58 B)
├── .graphify_detect.json             Graphify config (untracked)
├── .mv_test_cross                    Empty 0-byte orphan (still present from 2026-04-11)
├── 20 root *.md files                README, CLAUDE, AGENT_REGISTRY, etc. — see §3.2
├── AUDIT.md                          Untracked prior audit (2026-04-27, 25.7 KB)
├── api\
│   ├── __init__.py
│   └── app\
│       ├── __init__.py
│       ├── main.py                   FastAPI proxy
│       └── routers\
│           ├── __init__.py
│           └── notion_proxy.py
├── app\
│   ├── __init__.py
│   ├── agents\                       18 agent .py + __init__
│   ├── models\                       18 model .py + __init__
│   ├── orchestrators\
│   │   └── integration_check.py
│   ├── services\                     6 service .py + __init__
│   ├── utils\                        4 util .py + __init__
│   └── web\
│       └── operator_console.py
├── docs\
│   ├── 15 *.md files (incl. SYSTEM.md, INSPECTION_REPORT.md, audit-prompt/protocol)
│   ├── _archive_phase0_design\       8 historical phase-0 design docs
│   ├── archive\                      3 historical changelogs/build-logs
│   └── audit\
│       ├── audit-prompt.md           The prompt this audit ran
│       └── audit-protocol.md         The framework that defines what an audit must capture
├── graphify-out\                     Knowledge-graph output (gitignored)
├── leads\
│   ├── _manifest.json                Run-history of sales-engine pipeline (modified, untracked content)
│   ├── _run.log                      Pipeline run log (modified)
│   ├── Reports\                      62 company-slug subfolders + .gitkeep + own _manifest.json + _run.log
│   └── leads\                        Nested git repo (TanStack/React dashboard) — see §2.3
├── main.py                           Daily engine entry (23 KB)
├── migrations\
│   ├── 0001_initial_sales_schema.sql
│   ├── create_migration.py
│   └── run_migrations.py
├── pytest.ini
├── requirements.txt
├── run_integration_check.py
├── run_operator_console.py
├── sales-engine\                     Per-lead Perplexity+Claude pipeline (the "v1")
│   ├── .claude\settings.json         Untracked
│   ├── .env                          3 keys (untracked)
│   ├── .gitignore
│   ├── .venv\                        Skipped
│   ├── README.md
│   ├── config\.env.example           Template (only env-bearing file ever committed besides root .env.example)
│   ├── csv\                          4 CSV inputs (1 tracked, 3 untracked)
│   ├── prompts\                      research_prompt.md, email_prompt.md (2 files)
│   ├── requirements.txt
│   └── scripts\run_pipeline.py       548 lines (modified vs HEAD)
├── sales-engine-v2\                  NEW (created 2026-05-03 — entirely untracked)
│   ├── README.md
│   ├── prompts\                      5 prompts: research/email/sequence/call/linkedin
│   └── scripts\run_pipeline.py       696 lines
├── sales-engine.zip                  6.0 MB zip of `sales-engine/` snapshot (incl. .venv) — created 2026-05-03 08:14
├── scripts\
│   ├── audit_recruitment_partner_leads.py
│   ├── explorium_email_probe.py
│   ├── run_monthly_scan.ps1
│   └── vibe_prospecting_scan.py
├── sops\                             3 SOPs (Demo Prep, Pipeline Mgmt, Sales Outreach)
├── strategic_account_entries.example.json
├── supabase_schema_reference.sql
├── templates\
│   ├── decks\GlobalKinect_Sales_Deck.pptx
│   └── emails\                       9 HTML/txt + GK_Email_Sequence.html
├── tests\                            29 test_*.py (AUDIT.md said 24 — five added since)
├── venv\                             Python 3.13 — skipped
├── discovery_sources.json            33 KB, primary feed config
└── discovery_sources.example.json    Template
```

### 2.2 Git repositories found

| Path | Branch | Last commit | Uncommitted | Untracked | Remote |
|---|---|---|---|---|---|
| `C:\dev\globalkinect\sales\.git` | `main` | `462dcc4` "docs: Workstream 3 complete summary" | yes (see §2.1) | yes (10 paths) | `origin → github.com/gill-michael/globalkinect-sales.git` |
| `C:\dev\globalkinect\sales\leads\leads\.git` | `main` | `f312f95` "Archive Phase 0 design docs" | `M .gitignore` | `Book1.xlsx` | `origin → github.com/gill-michael/globalkinect-leads.git` |

Notes:
- `sales-engine/` and `sales-engine-v2/` are **not** git repos (no nested `.git`).
- The nested `leads/leads/` repo is gitignored at the parent level (per `.gitignore` line covering `node_modules/`, `.venv/`, etc., and indirectly via the new `.env` rule), but the directory itself is **not** explicitly ignored — it shows up as `??` untracked content in the parent.
- Total tracked files in main repo: **228**. (Heavy generated/dependency content correctly gitignored.)

### 2.3 Nested dashboard repo (`leads/leads/`)

A standalone TanStack Start (React 19 + Vite + TypeScript) front-end with its own git remote. Notable contents:

- 13 routes in `src/routes/` (file-based router): `index`, `login`, `_app.inbox`, `_app.leads.$leadId`, `_app.metrics`, `_app.reports`, `_app.runs`, `_app.segments`, `_app.settings.profile`, `_app.signals`, `_app.suppression`, `_app.tsx`, `__root.tsx`.
- 3 Supabase migrations under `supabase/migrations/` (Lovable-generated, dated 2026-04-22).
- `_archived_phase1a_backend/` — formerly the Python backend scaffold; explicitly archived per its own README ("Do not build into this directory. New backend work should be added to the existing engine.") with the read-only Notion proxy at `api/app/main.py` named as the bridge instead.
- Untracked `Book1.xlsx` (47 KB) at repo root.
- Deploy targets per files: `wrangler.jsonc` (Cloudflare Workers), `bun.lockb` (Bun), Lovable.dev cloud-auth (per [INSPECTION_REPORT.md] §7.5 — not re-verified here).

### 2.4 File-type counts (excluding venvs, .git, __pycache__, graphify-out, leads/Reports/)

| Type | Approx count | Notes |
|---|---:|---|
| `.py` (main repo, app + scripts + tests) | ~85 | Python code |
| `.tsx` (dashboard) | ~71 [from AUDIT.md, not re-counted] | React components |
| `.md` (root + docs + sops + sales-engine[+v2] + leads/leads/docs) | ~50 [excluding generated graphify wiki] | |
| `.json` (configs / data) | ~10 | discovery_sources, strategic_account, package.json, etc. |
| `.sql` | 5 | Engine + dashboard migrations |
| `.csv` | 4 | All under `sales-engine/csv/` |
| `.html` / `.txt` (templates) | 9+1 | |
| `.pptx` | 1 | Sales deck |
| `.ps1` | 1 | `run_monthly_scan.ps1` |
| `.zip` | 1 | `sales-engine.zip` (6.0 MB) |

`leads/Reports/` contains 62 company-slug folders × 3 files (`report.md`, `email.md`, `metadata.json`) = 186 generated files. Gitignored as "SACRED" per `.gitignore`.

`graphify-out/` is gitignored (regenerable). Not enumerated.

---

## 3. Artefact classification

### 3.1 Code files (Python, in main repo)

The full per-file purpose breakdown was captured in [AUDIT.md §2.1](AUDIT.md) and [docs/SYSTEM.md §3](docs/SYSTEM.md) (agent table); both remain accurate as of HEAD `462dcc4`. Summary, with status delta from those documents:

| Cluster | Files | Status |
|---|---|---|
| `main.py` | 1 | Working — orchestrates 18 agents per `SYSTEM.md` §3 |
| `app/agents/*.py` | 18 | Working — `OutreachReviewAgent` runs first (live mode), `ResponseHandlerAgent` after feedback index |
| `app/models/*.py` | 18 | Working — Pydantic models |
| `app/services/*.py` | 6 | Working — `notion_service.py` (~105 KB), `discovery_source_service.py` (~55 KB), `anthropic_service.py` (~27 KB), plus supabase, operator_console, config |
| `app/orchestrators/integration_check.py` | 1 | Per SYSTEM.md §9 item 9: **not re-run since recruitment_partner discontinuation** — status not freshly verified |
| `app/utils/*.py` | 4 | Working — logger, time, identity, target_markets |
| `app/web/operator_console.py` | 1 | Working — single-file 57 KB WSGI app on `127.0.0.1:8787`. Test `test_queue_page_renders_outreach_rows` flagged as a persistent failure in AUDIT.md was fixed by commit `3d212b4` ("tests: fix or delete deselected queue page assertion") on 2026-04-27 |
| `api/app/main.py` + `api/app/routers/notion_proxy.py` | 2 | Working — read-only Notion proxy + small set of PATCH endpoints, CORS bound to dashboard origin, no auth (per SYSTEM.md §9.5 — accepted for local-only) |
| `migrations/*.py`, `migrations/0001_initial_sales_schema.sql` | 3 | Working — forward-only runner, applied schema |
| `scripts/audit_recruitment_partner_leads.py` | 1 | Working — read-only audit (last output: `docs/RECRUITMENT_PARTNER_AUDIT_20260428_075641Z.md`) |
| `scripts/explorium_email_probe.py` | 1 | Working — investigative tool, ~16 credits per run |
| `scripts/run_monthly_scan.ps1` | 1 | Working per SYSTEM.md §6; not freshly executed |
| `scripts/vibe_prospecting_scan.py` | 1 | Working — Vibe → Notion Lead Intake. Bulk-enrich step added in commit `e607547` |
| `tests/test_*.py` | 29 | AUDIT.md reported 24 — 5 added since (likely incl. `test_audit_recruitment_partner_leads.py`, `test_brand_compliance.py` updates, `test_vibe_prospecting_scan.py`). Not freshly executed in this audit |

### 3.2 Documentation files (Markdown)

20 root-level `.md` + 15 in `docs/` + 3 archive subfolders.

| Path | Last edited | Role |
|---|---|---|
| `README.md` | 2026-04-28 | Now defers to `docs/SYSTEM.md` ("where they disagree, SYSTEM.md wins") — historical project description retained below the header |
| `CLAUDE.md` | 2026-04-27 | Project Claude instructions (includes branding paths, restricted-paths rule, error handling) |
| `docs/SYSTEM.md` | 2026-04-28 | **Source of truth** — declared as such by README and by Phase 0 archive README |
| `docs/INSPECTION_REPORT.md` | 2026-04-27 | 79 KB read-only behaviour inspection (untracked) |
| `docs/audit/audit-prompt.md` | 2026-05-03 | The prompt that produced this audit |
| `docs/audit/audit-protocol.md` | 2026-05-03 | The audit framework (Draft v1 — pending first use) |
| `AUDIT.md` (root) | 2026-04-27 | Prior repo-shape audit (untracked) |
| `AGENT_REGISTRY.md`, `OPERATOR_GUIDE.md`, `RUNBOOK.md`, `DECISION_PLAYBOOK.md`, `ICP_SOURCING_PLAYBOOK.md`, `SOURCING_*.md`, `NOTION_*.md`, `DATABASE_MIGRATIONS.md`, `SYSTEM_ARCHITECTURE.md`, `PROJECT_PLAN.md`, `PIPELINE_GAPS.md`, `IMPLEMENTATION_BACKLOG.md`, `TESTING_PHASE_PLAN.md`, `GLOBAL_KINECT_SOURCING_AUDIT.md` | 2026-03-21 → 2026-04-12 | Historic playbooks. SYSTEM.md is now canonical; these are not re-pointed at it. [inferred] some are stale |
| `docs/EXPLORIUM_*.md`, `docs/RECRUITMENT_PARTNER_*.md`, `docs/WORKSTREAM_*_COMPLETE.md` | 2026-04-27 → 2026-04-28 | Recent workstream output; aligned with SYSTEM.md |
| `docs/_archive_phase0_design/` | 2026-04-28 | 7 phase-0 design docs + README — explicitly superseded by SYSTEM.md |
| `docs/archive/` | (3 files) | `BUILD_LOG.md`, `INTERACTION_POLISH_CHANGELOG.md`, `SALES_ENGINE_TASKLIST.md` — pre-pivot history |
| `sops/SOP_*.md` | 2026-03-24 | 3 standard operating procedures, not refreshed since SYSTEM.md |

### 3.3 Prompt files (LLM prompts in `prompts/` folders)

| Path | Lines / size | Purpose | Notes |
|---|---|---|---|
| `sales-engine/prompts/research_prompt.md` | 4.9 KB (Apr 18) | Perplexity sonar-deep-research briefing prompt | **Lacks `<think>`-suppression rule** — see §7 |
| `sales-engine/prompts/email_prompt.md` | 3.4 KB (Apr 18) | Claude email-drafting prompt | Excludes "Entomo" and one-word "GlobalKinect" per the `sales-engine/README.md` "When things go wrong" section |
| `sales-engine-v2/prompts/research_prompt.md` | 7.5 KB (May 3) | Same role, **adds CRITICAL OUTPUT RULES** including "Do NOT output any internal reasoning, planning, deliberation, or `<think>` blocks" |
| `sales-engine-v2/prompts/email_prompt.md` | 4.2 KB (May 3) | Same role, expanded |
| `sales-engine-v2/prompts/sequence_prompt.md` | 5.7 KB | NEW — 5-touch cadence over 3 weeks |
| `sales-engine-v2/prompts/call_prompt.md` | 7.6 KB | NEW — call script + objection handling |
| `sales-engine-v2/prompts/linkedin_prompt.md` | 4.6 KB | NEW — connection note + DM + InMail kit |

`docs/NOTION_AI_PROMPTS.md` (12.5 KB, root-level docs) is a doc *about* prompts (Notion AI), not an executed prompt — classified as documentation.

`app/prompts/` was reported empty in AUDIT.md §5.8; inspection here finds it absent from the current `app/` listing — [inferred] it has been removed since (or AUDIT.md was wrong). Did not verify in git history.

### 3.4 Config files

| Path | Type | Purpose | Notes |
|---|---|---|---|
| `.env` | dotenv (untracked) | Live secrets for engine | Has 23 keys including `SUPABASE_SOCIAL_*` (two extra Supabase keys not in `.env.example`) |
| `.env.example` | dotenv (tracked) | Template | **Drift:** missing `NOTION_ACCOUNTS_DATABASE_ID`, `NOTION_BUYERS_DATABASE_ID`, `NOTION_OPPORTUNITIES_DATABASE_ID`, `SUPABASE_SOCIAL_*`, `ANTHROPIC_DISCOVERY_MODEL`, `ANTHROPIC_LEAD_RESEARCH_MODEL` (all of which AUDIT.md §3.2 listed as consumed by `app/services/config.py`). [inferred] needs refresh |
| `sales-engine/.env` | dotenv (untracked) | Per-lead pipeline secrets | 3 keys: `ANTHROPIC_API_KEY`, `LEADS_ROOT`, `PERPLEXITY_API_KEY` |
| `sales-engine/config/.env.example` | dotenv (tracked) | Template | Matches `sales-engine/.env` |
| `sales-engine-v2/.env` | does not exist | **Gap** — README says copy `config\.env.example`, but v2 has no `config/` subfolder. [inferred] v2 expects to inherit from `sales-engine/.env` if run from there, or this is a gap |
| `leads/leads/.env` | dotenv (untracked, in nested repo) | Dashboard env | 5 keys: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_PROJECT_ID`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_URL` |
| `leads/leads/.env.example` | dotenv (tracked in nested) | Dashboard template | 9 keys including `SUPABASE_SERVICE_ROLE_KEY`, `VIBE_API_KEY` (note: parent engine uses `VIBE_PROSPECTING_API_KEY` — same Explorium key, two names — flagged in AUDIT.md §3.2 and unchanged) |
| `.gitignore` (root) | gitignore | | **Greatly expanded since AUDIT.md** — now covers `.venv/`, `node_modules/`, `bun.lockb` (intentionally tracked), `.bun/`, `.env*`, `leads/Reports/*`, `graphify-out/`, `.mv_test_cross`, etc. Confirms `leads/Reports/*` is gitignored, with `.gitkeep` sentinel kept |
| `leads/leads/.gitignore` | gitignore | Dashboard ignore rules | More comprehensive (handles `*.pem`, `service-account.json`, etc.) |
| `pytest.ini` | ini | `pythonpath = .` | unchanged |
| `requirements.txt` | requirements | | 9 deps, FastAPI pinned to `0.115.5` (AUDIT.md noted earlier `0.136.1` mismatch — fix landed in commit `2e2d09c`) |
| `sales-engine/requirements.txt` | requirements | | Independent dep list (per the README, includes `httpx`, `anthropic`, `python-dotenv`) |
| `discovery_sources.json` | json (tracked) | 21+ active feed sources, 8 lanes | 33 KB |
| `discovery_sources.example.json` | json (tracked) | Template | 9.3 KB |
| `strategic_account_entries.example.json` | json (tracked) | Curated-account template | 4.4 KB |
| `.graphify_detect.json` | json (untracked) | Graphify config | Untracked but on disk; gitignored under `graphify-out/` rule? — no: gitignore covers `graphify-out/`, not this file. Currently shows as `??` |
| `.claude/settings.json` | json (tracked, modified) | Claude Code permissions + hooks | Paths now correctly point at `c:/dev/globalkinect/sales` (fixed in commit `634a431`); permission allowlist has grown to ~50 entries |

### 3.5 Data files

| Path | Size | Purpose | Notes |
|---|---|---|---|
| `sales-engine/csv/vibe_combined_top30.csv` | tracked, modified | 30-lead Vibe export | Modified vs HEAD |
| `sales-engine/csv/gk_vibe_run4_top75.csv` | untracked | 75-lead Vibe export | 2026-04-27 |
| `sales-engine/csv/uae_ksa_hr_finance_leaders_gk_20260427151757.csv` | untracked | UAE/KSA-specific export | 2026-04-27 |
| `sales-engine/csv/gk antiquated systems.csv` | untracked | Special-thesis CSV (filename has space) | 2026-04-27 |
| `supabase_schema_reference.sql` | 4.5 KB | Reference DDL | Parallel to `migrations/0001_initial_sales_schema.sql` |
| `migrations/0001_initial_sales_schema.sql` | 6 KB [inferred] | Engine schema | Not re-read in this audit |
| `leads/leads/Book1.xlsx` | 48 KB (untracked) | Spreadsheet in nested repo | Unknown purpose |
| `leads/leads/supabase/migrations/2026-04-22*.sql` | 3 files | Lovable-managed dashboard schema | `profiles`, `app_role` enum, RLS helpers per SYSTEM.md §5 |
| `templates/decks/GlobalKinect_Sales_Deck.pptx` | 336 KB | Sales deck | Filename uses one-word "GlobalKinect" — see §7 |
| `templates/emails/*.html` / `*.txt` | 10 files | Post-demo + proposal templates (.ae and .co.uk pairs) + GK_Email_Sequence.html | Not re-read for brand-compliance in this audit |

### 3.6 Output / generated files

| Path | Count / size | Notes |
|---|---|---|
| `leads/Reports/<slug>/report.md` | **62 files** | Gitignored. **All 62 contain a `<think>` block at the top** — see §7 |
| `leads/Reports/<slug>/email.md` | 62 files | Gitignored. Brand check: 0 emails contain one-word "GlobalKinect" outside the `globalkinect.ae` / `globalkinect.co.uk` domain references |
| `leads/Reports/<slug>/metadata.json` | 62 files | Per-lead status + Perplexity/Claude usage + cost (sample: $0.61 Perplexity for one report) |
| `leads/Reports/_manifest.json` | 1 | Run-history (in addition to one at `leads/_manifest.json`) |
| `leads/Reports/_run.log` | 1 | Run log (additional copy at `leads/_run.log`) |
| `leads/_manifest.json` | 1, modified | The legacy location of run history (per AUDIT.md §2.4) |
| `leads/_run.log` | 1, modified | Legacy run log |
| `graphify-out/` | gitignored | Knowledge-graph wiki + cache. Regenerable |

### 3.7 Unknown / unclassified

- `.mv_test_cross` — empty 0-byte file at root, dated 2026-04-11. Carried over from before AUDIT.md (which also flagged it). [inferred] leftover from a `mv` cross-device test.
- `sales-engine.zip` — 6.0 MB Zip archive of the entire `sales-engine/` directory **including its `.venv/`** (5+ MB of `site-packages`), created 2026-05-03 08:14, just hours before `sales-engine-v2/` was created. [inferred] a backup snapshot taken before forking v2. Not gitignored explicitly — would be committed if `git add .` ran.
- `leads/leads/Book1.xlsx` — 48 KB Excel spreadsheet in dashboard repo, untracked, dated 2026-05-02. Purpose unknown.
- `sales-engine/.claude/settings.json` (untracked) — Claude permissions for the sub-pipeline. Purpose: per-folder hooks/perms when working on the per-lead pipeline.

---

## 4. Duplicates and overlaps

### 4.1 `sales-engine/` ↔ `sales-engine-v2/` — TWO PARALLEL VERSIONS

| | v1 (`sales-engine/`) | v2 (`sales-engine-v2/`) |
|---|---|---|
| Created | 2026-04-18 | 2026-05-03 (today) |
| Tracked? | Yes (most files) | No — entirely untracked |
| Outputs per lead | `report.md`, `email.md`, `metadata.json` | `report.md`, `email.md`, `sequence.md`, `call.md`, `linkedin.md`, `metadata.json` |
| `run_pipeline.py` size | 548 lines | 696 lines |
| Prompts | research, email | research, email, **sequence, call, linkedin** |
| `<think>` block fix | **Not present** — output reports leak it | Promised in v2: prompt-level "CRITICAL OUTPUT RULES" + script-level strip function (per v2 README) |
| Brand-rule explicit prompt rule | Per v1 `email_prompt.md` (not re-read here) | "Never write 'GlobalKinect' — it is 'Global Kinect' (two words)" baked into v2 research prompt |
| Resumability | Per-pair (report, email) | Per-asset (5 independent steps) |
| Standalone `.env` | Yes (3 keys) | No `.env` and no `config/` directory |
| `LEADS_ROOT` default | `leads/<slug>/` per its README, but actual current behaviour writes to `leads/Reports/<slug>/` per the manifest evidence | `leads/Reports/<slug>/` per v2 README |

**Key question for the reviewer:** is v2 the new canonical pipeline (and v1 + the zip should be retired), or is v2 still experimental?

### 4.2 `sales-engine.zip` ↔ live `sales-engine/`

- `.zip` is a copy of `sales-engine/` (incl. `.venv/`) snapped on 2026-05-03 08:14, ~13 minutes before `sales-engine-v2/` was created.
- 6.0 MB. Untracked. Will pollute the repo if a future `git add .` is run.
- **Question:** safe to delete once v2 is confirmed canonical?

### 4.3 `app/agents/message_writer_agent.py` ↔ `app/agents/opportunities_outreach_agent.py`

Both write into the same Outreach Queue. Per AUDIT.md §5.2, the older `MessageWriterAgent` produced one-word "GlobalKinect" while the newer `OpportunitiesOutreachAgent` enforced two words. AUDIT.md flagged this as a brand violation. Commit `b4f1b90` ("Fix brand rule: 'Global Kinect' (two words) in all production drafts") landed since. **Not re-verified** by reading the agent code in this audit; flagged for the reviewer to confirm.

### 4.4 Two FastAPI projects (one archived)

- `api/app/main.py` — live Notion proxy for the Lovable dashboard.
- `leads/leads/_archived_phase1a_backend/app/` — formerly a parallel scaffold; now explicitly archived per its own README ("Do not build into this directory"). AUDIT.md §5.3 noted both as live; SYSTEM.md §9 item 8 acknowledges the archive. **Status now: only one live FastAPI project.**

### 4.5 Three Supabase migration histories (per AUDIT.md §5.3)

- `migrations/` (root, engine) — `0001_initial_sales_schema.sql`
- `leads/leads/supabase/migrations/` — 3 dashboard migrations from Lovable
- `leads/leads/_archived_phase1a_backend/migrations/` — alembic migrations of the archived backend

All three apply to (apparently) the same Supabase project. The archived backend's migrations are now historical.

### 4.6 `leads/_manifest.json` ↔ `leads/Reports/_manifest.json` (and same for `_run.log`)

Two pairs of run-history files at two depths. The current pipeline (`sales-engine/`) writes to `leads/Reports/` per the v1 README and v2 README. The legacy `leads/_manifest.json` is being updated (`M` in git status) but its purpose vs the `Reports/` copy is unclear. **Question:** which one is canonical?

### 4.7 Documentation: `README.md` ↔ `docs/SYSTEM.md`

`README.md` explicitly defers to `SYSTEM.md` ("where they disagree, SYSTEM.md wins"). The other 19 root-level `.md` files are not re-pointed at SYSTEM.md and may contain stale guidance — not re-checked in this audit. AUDIT.md §5.7 flagged this.

---

## 5. External dependencies

| Service | Files calling it | Purpose | Direction |
|---|---|---|---|
| **Anthropic** (Claude) | `app/services/anthropic_service.py`, `app/agents/lead_discovery_agent.py`, `app/agents/lead_research_agent.py`, `app/agents/response_handler_agent.py`, `app/agents/opportunities_outreach_agent.py`, `sales-engine/scripts/run_pipeline.py`, `sales-engine-v2/scripts/run_pipeline.py` | Lead normalisation, qualification, reply classification, outreach drafting | Push (request/response) |
| **Notion** | `app/services/notion_service.py`, `app/agents/notion_sync_agent.py`, `app/agents/lead_discovery_agent.py`, `app/agents/lead_research_agent.py`, `app/agents/lead_feedback_agent.py`, `app/agents/outreach_review_agent.py`, `app/agents/opportunities_outreach_agent.py`, `app/web/operator_console.py`, `api/app/routers/notion_proxy.py`, `scripts/vibe_prospecting_scan.py` | 12 logical Notion DBs (per SYSTEM.md §4) | Two-way (read + write/upsert; operator decisions read back next run) |
| **Supabase** | `app/services/supabase_service.py`, all `*_with_solution` writers in agents | Mirror of leads / outreach / pipeline / solutions / deal_support / execution_tasks | Two-way — engine writes; dashboard reads (some routes) |
| **Explorium** ("Vibe Prospecting") | `scripts/vibe_prospecting_scan.py`, `scripts/explorium_email_probe.py` | Pre-query → prospect lookup → bulk plaintext-email enrichment | Push (read) |
| **Perplexity** (sonar-deep-research) | `sales-engine/scripts/run_pipeline.py`, `sales-engine-v2/scripts/run_pipeline.py` | Per-lead deep research | Push |
| **Lovable.dev** (cloud-auth + hosting) | `leads/leads/` (dashboard) | Auth provider + dashboard hosting | Out of scope |
| **Cloudflare Workers** | `leads/leads/wrangler.jsonc` | Dashboard deploy target | Out of scope |
| **GitHub** | both repos' `origin` | Source hosting | Push/pull |
| **External feed sources** (RSS / HTML / JSON Feed / Greenhouse / Lever / Workable / sitemap_xml / webpage_html) | `app/services/discovery_source_service.py`, configured in `discovery_sources.json` | Lead Discovery raw input (24 sources / 8 lanes per AUDIT.md / SYSTEM.md) | Pull |

---

## 6. State and credentials

### 6.1 Credentials expected at runtime

**Main engine `.env`** (per `app/services/config.py` and observed `.env`):
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` (+ `ANTHROPIC_DISCOVERY_MODEL`, `ANTHROPIC_LEAD_RESEARCH_MODEL` per AUDIT.md §3.2 — not in current `.env.example`)
- `NOTION_API_KEY` and 12 DB IDs: `NOTION_DISCOVERY_DATABASE_ID`, `NOTION_INTAKE_DATABASE_ID`, `NOTION_OUTREACH_QUEUE_DATABASE_ID`, `NOTION_RUNS_DATABASE_ID`, `NOTION_LEADS_DATABASE_ID`, `NOTION_PIPELINE_DATABASE_ID`, `NOTION_SOLUTIONS_DATABASE_ID`, `NOTION_TASKS_DATABASE_ID`, `NOTION_DEAL_SUPPORT_DATABASE_ID`, `NOTION_ACCOUNTS_DATABASE_ID`, `NOTION_BUYERS_DATABASE_ID`, `NOTION_OPPORTUNITIES_DATABASE_ID`
- `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `DATABASE_URL`
- `SUPABASE_SOCIAL_URL`, `SUPABASE_SOCIAL_PUBLISHABLE_KEY` — **observed in `.env`, not documented in `.env.example`** — purpose unclear; [inferred] for an unrelated/secondary Supabase project (perhaps social-auth)
- `VIBE_PROSPECTING_API_KEY`, `VIBE_PROSPECTING_API_BASE_URL`
- `BRANDING_REPO_PATH`
- `SALES_ENGINE_RUN_MODE`, `SALES_ENGINE_TRIGGERED_BY` (per `.env.example`, not currently in `.env` — implied to default in code)
- `OPERATOR_CONSOLE_HOST`, `OPERATOR_CONSOLE_PORT` (per `.env.example`)
- `DISCOVERY_SOURCES_FILE`, `DISCOVERY_SOURCE_MAX_ITEMS_PER_SOURCE` (per `.env.example`)

**`sales-engine/.env`** (per the per-lead pipeline): `ANTHROPIC_API_KEY`, `LEADS_ROOT`, `PERPLEXITY_API_KEY`.

**`sales-engine-v2/`** has no `.env` and no `config/` template — see §3.4 gap.

**`leads/leads/.env`** (dashboard runtime): `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_PROJECT_ID`, `VITE_SUPABASE_PUBLISHABLE_KEY`, `VITE_SUPABASE_URL`. The dashboard's `.env.example` documents 4 additional keys (`ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `VIBE_API_KEY`) that the running `.env` doesn't carry — [inferred] dashboard does not currently invoke the AI/Vibe paths from inside its repo, only reads Supabase.

### 6.2 Secrets check (git history)

- Tracked env-bearing files: `.env.example` (root), `sales-engine/config/.env.example`, `leads/leads/.env.example`. All are templates with placeholder/comment values, not real secrets.
- `git log --all -p -S 'sk-ant'` returned **only the diff that introduced `sales-engine/config/.env.example` (commit `a286c4b` "First Lead Pack")**. The diff shows the template line `# Copy this file to .env in the same directory and fill in your keys` — **not** a real key.
- `git log --all -p -S 'NOTION_API_KEY=secret'` returned no matches.
- `git log --all -- '*.env'` (wildcard) returned no matches in the main repo's tracked history — i.e., real `.env` files have not been committed.

**Conclusion: clean.** Tracked history contains no real credentials.

The nested `leads/leads/.git` repo was not searched for committed secrets in this audit. Its `.gitignore` is comprehensive (covers `.env`, `*.pem`, `*-service-account*.json`, `secrets.json`, `.aws/`, `.gcp/`) so the surface area is small but unverified.

### 6.3 Where credentials are stored

- Live secrets are in dotfiles (`.env`, `sales-engine/.env`, `leads/leads/.env`) that are explicitly gitignored.
- The repo also references `C:\dev\globalkinect\keys\` (per project `CLAUDE.md`'s "Restricted paths" rule) — that directory was **not opened** during this audit per the rule.
- `BRANDING_REPO_PATH` env var points to a sibling repo (`C:\dev\globalkinect\branding\`) for ICP/voice rules — out of scope here.

---

## 7. Behaviour vs. intent

### 7.1 `<think>` block leak in 100% of `sales-engine/` reports — **important**

**Intent (per `sales-engine-v2/README.md`):** "v1: `report.md` (with `<think>` block leak)" → "v2: `report.md` (think block stripped + research prompt fixed)" — confirms v1 has a known leak.

**Observation:** `grep -l '<think>'` against all 62 `leads/Reports/<slug>/report.md` files returns **62/62 matches**. Sample (`almanea/report.md`): the `<think>` block begins on line 13 directly after the front-matter and runs for many lines of Perplexity's internal reasoning before the actual briefing.

**Severity:** **important** for v1 (the historical store of "researched leads" treated as SACRED per the SYSTEM.md and `.gitignore` is full of internal model reasoning, not the polished briefings the SDR is meant to read).

**Status:** v2 promises fix. v1 is the version that produced these 62 reports. No backfill or strip-pass observed in either README. **Question:** should the existing 62 reports be re-stripped, or left as-is?

### 7.2 `sales-engine/` README path drift

**Intent (per its README):** outputs land at `LEADS_ROOT/<slug>/report.md`, with the example showing `C:\dev\globalkinect\sales\leads\<slug>\`.

**Observation:** Current artefacts are at `C:\dev\globalkinect\sales\leads\Reports\<slug>\` (with a `Reports/` segment). The git status shows 51 deletions of paths like `leads/<slug>/email.md` matched by re-creation under `leads/Reports/<slug>/` — i.e., files were moved between commits. The v1 README has not been updated to reflect the new path.

**Severity:** cosmetic but confusing. **Question:** confirm `leads/Reports/` is the new canonical, and update v1 README (or retire v1 entirely)?

### 7.3 Double `_manifest.json` / `_run.log` (the "manifest at two depths" anomaly)

**Intent (per `sales-engine/README.md`):** one `_manifest.json` and one `_run.log` at the leads root.

**Observation:** there is one pair at `leads/_manifest.json` + `leads/_run.log` (modified vs HEAD) **and** another pair at `leads/Reports/_manifest.json` + `leads/Reports/_run.log`. The legacy pair is being touched on each run (per the `M` status), but the v2 README only mentions the `Reports/` copy.

**Severity:** important. Two histories of the same runs are diverging.

### 7.4 `.env.example` lags `.env` and `app/services/config.py`

**Intent:** `.env.example` should document every env var the engine reads, so a new operator can boot the system from scratch.

**Observation:** `.env` in use today carries `NOTION_ACCOUNTS_DATABASE_ID`, `NOTION_BUYERS_DATABASE_ID`, `NOTION_OPPORTUNITIES_DATABASE_ID`, `SUPABASE_SOCIAL_URL`, `SUPABASE_SOCIAL_PUBLISHABLE_KEY` — none of which are in `.env.example`. AUDIT.md §3.2 also lists `ANTHROPIC_DISCOVERY_MODEL`, `ANTHROPIC_LEAD_RESEARCH_MODEL` as referenced by `config.py` but not in `.env.example`.

**Severity:** important — fresh-clone setup is undocumented for these.

### 7.5 `sales-engine-v2/` lacks env scaffolding

**Intent (per v2 `README.md`):** "Copy `Copy-Item config\.env.example .env`".

**Observation:** there is no `config/` directory in `sales-engine-v2/`, and no `.env` or `.env.example` of its own. Setup commands in v2 README will fail as written. [inferred] v2 was authored against the assumption that the operator has `sales-engine/.env` already and runs v2 from inside that directory, or this is unfinished.

**Severity:** cosmetic if v2 inherits v1's env file by chance, important if it doesn't. **Question for reviewer.**

### 7.6 `requirements.txt` FastAPI version

**Intent (per AUDIT.md §3.1):** `0.115.5`. AUDIT.md §3.1 also reports `0.136.1` at one point.

**Observation:** current `requirements.txt` (158 B) — not freshly opened in this audit, but commit `2e2d09c` "requirements: align FastAPI pin with venv" landed since AUDIT.md, suggesting the discrepancy was resolved.

**Severity:** cosmetic / possibly resolved.

### 7.7 `templates/decks/GlobalKinect_Sales_Deck.pptx` filename

**Intent (per `OUTREACH_VOICE.md` rule cited in `CLAUDE.md`):** "No 'GlobalKinect' one word."

**Observation:** the deck filename uses one-word `GlobalKinect`. The contents of the .pptx were not opened.

**Severity:** cosmetic (filename, not user-facing copy). Note for consistency.

### 7.8 `integration_check.py` not re-run since `recruitment_partner` discontinuation

**Intent (per SYSTEM.md §9 item 9):** worth re-running before the next live monthly cycle.

**Observation:** no fresh run was attempted in this audit (would be a side-effect — the script writes Supabase + Notion test rows). Status: **stale, not exercised since policy change**.

**Severity:** important *if* the next live cycle is imminent.

### 7.9 `MessageWriterAgent` brand-rule fix

**Intent:** Both message writers must produce two-word "Global Kinect".

**Observation:** AUDIT.md §5.2 flagged the v1 `MessageWriterAgent` as still producing one word. Commit `b4f1b90` "Fix brand rule: 'Global Kinect' (two words) in all production drafts" has landed since. The agent code was **not re-read** in this audit; flagged for the reviewer.

**Severity:** unverified (likely fixed).

### 7.10 Test status (one historical failure)

**Intent (per AUDIT.md §5.6):** `test_queue_page_renders_outreach_rows` was a known persistent failure.

**Observation:** commit `3d212b4` "tests: fix or delete deselected queue page assertion" has landed. Pytest was **not re-run in this audit** (read-only posture). Status: [inferred] resolved. Reviewer to confirm.

---

## 8. Working / broken / stale classification

### 8.1 Working (per code path, not freshly executed)

- `main.py` daily engine + 18 `app/agents/*` + 6 `app/services/*`
- `api/app/` Notion proxy (active)
- `app/web/operator_console.py` (active local UI, port 8787)
- `migrations/` runner + initial schema
- `scripts/vibe_prospecting_scan.py` (Explorium → Notion Lead Intake; bulk_enrich step landed in `e607547`)
- `scripts/audit_recruitment_partner_leads.py` (read-only)
- `scripts/explorium_email_probe.py`
- `scripts/run_monthly_scan.ps1`
- `sales-engine/scripts/run_pipeline.py` (v1) — produces output but with `<think>` leak (see §7.1)
- `tests/` — 29 test files, presumed green per the recent commit history; not re-run
- `leads/leads/` dashboard — TanStack Start app with 13 routes, builds via Bun/Vite [inferred — not built in this audit]

### 8.2 Broken / behaviourally divergent

- `sales-engine/` v1 pipeline — produces `report.md` files with leaked `<think>` blocks (62/62 affected). v2 promises fix, not yet validated against an end-to-end run.
- `sales-engine-v2/` — `.env`/`config/` scaffolding missing per its own README's setup commands (§7.5).
- `.env.example` — does not document all the keys actually read by `config.py` (§7.4).
- Two `_manifest.json` / `_run.log` pairs at different depths, diverging (§7.3).

### 8.3 Stale candidates for retirement (no recommendation; candidate list only)

- `.mv_test_cross` — empty file from 2026-04-11.
- `sales-engine.zip` — 6 MB snapshot of v1 (incl. its venv) created today before v2 was forked.
- `sales-engine/` — entire folder, pending review of whether v2 fully replaces it.
- `leads/_manifest.json`, `leads/_run.log` — pending which copy is canonical (§4.6).
- `leads/leads/_archived_phase1a_backend/` — explicitly archived per its README; current SYSTEM.md says retained "for reference only".
- `docs/_archive_phase0_design/` — explicitly superseded by SYSTEM.md.
- `docs/archive/` — pre-pivot history (3 files).
- 19 of 20 root `.md` files — not re-pointed at SYSTEM.md; may contain stale guidance.
- `sops/SOP_*.md` — last edited 2026-03-24, predate SYSTEM.md and recent workstream changes.
- `app/prompts/` — flagged as empty by AUDIT.md §5.8; appears absent now [inferred — removed since].
- Root `templates/proposals/` and `sales-engine/config/` empty directories — flagged in AUDIT.md.

---

## 9. Findings and questions for the reviewer

Each finding is numbered, with: observation → evidence → severity → question.

1. **`<think>` block in every researched lead report.** All 62 `leads/Reports/<slug>/report.md` files contain a Perplexity `<think>` block at the top. v2 promises a fix; no backfill is in evidence. Severity: important. **Q:** should the 62 existing reports be re-stripped (or re-generated), or left as historical artefact?

2. **`sales-engine-v2/` is brand new today and entirely untracked.** Created 2026-05-03 (after `sales-engine.zip` was snapped at 08:14). `git status` shows it as `??`. v2 expands outputs from `{report, email}` to `{report, email, sequence, call, linkedin}`; `run_pipeline.py` grew from 548 → 696 lines. Severity: not a defect, but a major architectural decision in flight. **Q:** is v2 the new canonical pipeline (and v1 + the zip should retire), or experimental? If canonical, does it need to be committed and the v1 dir retired in the same step?

3. **`sales-engine-v2/` lacks `.env` scaffolding.** v2's README points operators at `Copy-Item config\.env.example .env`, but no `config/` directory or `.env.example` exists in v2. Severity: important if a fresh operator runs v2; cosmetic if everyone runs from `sales-engine/` with shared env. **Q:** should v2 ship its own env scaffold?

4. **Two pairs of `_manifest.json` / `_run.log` exist** — at `leads/` and at `leads/Reports/`. Both touched recently. Severity: important — two divergent run histories. **Q:** which is canonical, and can the other pair be removed?

5. **`.env.example` lags actual `.env` and `config.py`.** Missing at minimum: `NOTION_ACCOUNTS_DATABASE_ID`, `NOTION_BUYERS_DATABASE_ID`, `NOTION_OPPORTUNITIES_DATABASE_ID`, `SUPABASE_SOCIAL_URL`, `SUPABASE_SOCIAL_PUBLISHABLE_KEY`, `ANTHROPIC_DISCOVERY_MODEL`, `ANTHROPIC_LEAD_RESEARCH_MODEL`. Severity: important. **Q:** what are `SUPABASE_SOCIAL_*` for, and should they be documented?

6. **`sales-engine.zip` (6 MB) at root, untracked.** Includes the v1 `.venv/`. Created today, hours before v2 was created. Severity: cosmetic. **Q:** delete after v2 is confirmed canonical?

7. **`leads/leads/Book1.xlsx` (48 KB) untracked in dashboard repo.** Modified 2026-05-02. Severity: cosmetic. **Q:** what is this — interim spreadsheet, or staging data?

8. **`templates/decks/GlobalKinect_Sales_Deck.pptx` filename uses one-word brand.** Inconsistent with `CLAUDE.md` and `OUTREACH_VOICE.md` rules. Severity: cosmetic (filename only). **Q:** rename for consistency?

9. **`.mv_test_cross` (0-byte) at root.** Carried over from 2026-04-11. Severity: cosmetic. **Q:** safe to delete?

10. **`integration_check.py` not exercised since `recruitment_partner` discontinuation.** Per SYSTEM.md §9 item 9. Severity: important if next live cycle is imminent. **Q:** run before next live monthly?

11. **19 of 20 root `.md` docs not re-pointed at SYSTEM.md.** Many predate the SYSTEM.md authority statement and may contain stale guidance (e.g., `TESTING_PHASE_PLAN.md`, `IMPLEMENTATION_BACKLOG.md`, `PIPELINE_GAPS.md`, `SYSTEM_ARCHITECTURE.md`, `SOURCING_*.md`). Severity: important for newcomers / future Claude sessions. **Q:** archive the superseded docs to `docs/archive/`, or leave with header annotations?

12. **The nested `leads/leads/.git` repo's history was not scanned for accidentally committed secrets in this audit.** Its `.gitignore` is comprehensive, but unverified. Severity: low (because gitignore looks safe). **Q:** want me to run the secret scan against the nested repo as a follow-up?

13. **The prior `AUDIT.md` (untracked) has substantially overlapping content.** This audit ran fresh and converged on most of the same observations, plus net-new ones (sales-engine-v2 didn't exist then, gitignore was much smaller, dashboard backend was not yet archived). Severity: not a defect. **Q:** does the prior `AUDIT.md` get retired (renamed/archived) once this `AUDIT-0001-DRAFT.md` is accepted?

14. **`leads/leads/` is gitignored implicitly (because of `.env` rules and `.venv/`/`node_modules/` rules) but not as a directory.** Result: `git status` continually shows `?? leads/leads/` as untracked content even though the nested `.git` is the actual home of those files. Severity: cosmetic noise. **Q:** add `leads/leads/` to root `.gitignore` to silence the noise?

15. **`a286c4b "First Lead Pack"` introduced `sales-engine/config/.env.example` containing only template comments.** No real secrets in any tracked path. Severity: clean. **Q:** none — this is a positive finding, recorded for completeness.

---

## 10. Did not read

The following files / directories were **not opened** during this audit. Reasons given.

### 10.1 Skipped by sandbox / out-of-scope

- `C:\dev\globalkinect\keys\` — restricted by project `CLAUDE.md`.
- `C:\dev\globalkinect\branding\` — out of scope.
- `C:\dev\globalkinect\brain\` (Obsidian vault) — out of scope.
- All external service state (Notion DBs, Supabase rows, Explorium account, Anthropic billing, Lovable, Cloudflare, Perplexity, GitHub remotes) — out of scope per Audit Protocol §1.

### 10.2 Skipped because they are vendored / generated / regenerable

- `venv/`, `sales-engine/.venv/`, `leads/leads/_archived_phase1a_backend/.venv/` (Python site-packages).
- `__pycache__/` (everywhere).
- `.git/` internal objects.
- `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`.
- `node_modules/` (none observed at any depth).
- `graphify-out/` (gitignored regenerable knowledge graph).
- `package-lock.json`, `bun.lockb`, `uv.lock` — lockfiles.

### 10.3 Skipped because of size / low information density (sampled instead of fully read)

- `app/services/notion_service.py` (~105 KB) — not full-read; relied on AUDIT.md §2.1 + SYSTEM.md §3 / §4 for purpose.
- `app/services/discovery_source_service.py` (~55 KB) — not full-read.
- `app/web/operator_console.py` (~57 KB) — not full-read.
- `main.py` — read first 100 of 23 KB lines only; relied on import surface for the rest.
- `tests/test_*.py` (29 files) — not full-read.
- `app/agents/*.py` (18 files) — not full-read; relied on SYSTEM.md §3 agent table.
- `app/models/*.py` (18 files) — not full-read; class names taken from filename.
- `app/orchestrators/integration_check.py` — not opened.
- `app/utils/*.py` (4 files) — not opened.
- `api/app/main.py`, `api/app/routers/notion_proxy.py` — not opened.
- `migrations/0001_initial_sales_schema.sql`, `supabase_schema_reference.sql`, `migrations/run_migrations.py`, `migrations/create_migration.py` — not opened.
- `scripts/audit_recruitment_partner_leads.py`, `scripts/explorium_email_probe.py`, `scripts/run_monthly_scan.ps1`, `scripts/vibe_prospecting_scan.py` — not opened.
- All 4 CSVs in `sales-engine/csv/` — not opened.
- 9 `templates/emails/*.html`/`*.txt` files and `GK_Email_Sequence.html` — not opened (no brand-compliance scan beyond the `.pptx` filename).
- `templates/decks/GlobalKinect_Sales_Deck.pptx` — not opened (binary).
- `sops/SOP_*.md` (3 files) — not opened.
- Most root `.md` docs (read only `README.md`, `CLAUDE.md`, `AUDIT.md`; not opened: `AGENT_REGISTRY.md`, `OPERATOR_GUIDE.md`, `RUNBOOK.md`, `DECISION_PLAYBOOK.md`, `ICP_SOURCING_PLAYBOOK.md`, `SOURCING_*.md` ×3, `NOTION_*.md` ×2, `SYSTEM_ARCHITECTURE.md`, `PROJECT_PLAN.md`, `PIPELINE_GAPS.md`, `IMPLEMENTATION_BACKLOG.md`, `TESTING_PHASE_PLAN.md`, `GLOBAL_KINECT_SOURCING_AUDIT.md`, `DATABASE_MIGRATIONS.md`).
- `docs/INSPECTION_REPORT.md` (79 KB) — not opened; cited via SYSTEM.md.
- `docs/EXPLORIUM_EMAIL_INVESTIGATION.md`, `docs/EXPLORIUM_PROBE_RESULT.md`, `docs/RECRUITMENT_PARTNER_*.md`, `docs/WORKSTREAM_*_COMPLETE.md`, `docs/INTERACTION_POLISH.md`, `docs/NOTION_AI_PROMPTS.md`, `docs/NOTION_INTEGRATION_READY_CHECKLIST.md`, `docs/SUPABASE_*.md` — not opened; flagged by name only.
- `docs/_archive_phase0_design/*` (8 files) — not opened (explicitly superseded).
- `docs/archive/*` (3 files) — not opened.
- `discovery_sources.json`, `discovery_sources.example.json`, `strategic_account_entries.example.json` — not opened beyond AUDIT.md §3.4 description.
- All 62 `leads/Reports/<slug>/report.md` files except `almanea/report.md` (sampled). Behavioural finding §7.1 was based on grep of all 62.
- All 62 `leads/Reports/<slug>/email.md` except `almanea/email.md` (sampled). Brand-compliance check §3.6 was a grep across all 62.
- All 62 `leads/Reports/<slug>/metadata.json` except `almanea/metadata.json` (sampled).
- `leads/_manifest.json`, `leads/_run.log`, `leads/Reports/_manifest.json`, `leads/Reports/_run.log` — not opened (only stat'd).
- `leads/leads/src/**/*.tsx` (~71 files) — not opened beyond route filenames.
- `leads/leads/_archived_phase1a_backend/app/**` (Python backend) — README only; no source files opened.
- `leads/leads/supabase/migrations/*.sql` (3 files) — not opened.
- `leads/leads/docs/CLAUDE-CODE-ORIENTATION.md`, `leads/leads/docs/HANDOFF.md` — not opened.
- `leads/leads/Book1.xlsx`, `sales-engine.zip` contents beyond the listing — not extracted.
- All `sales-engine-v2/prompts/*.md` — read first 30 lines of `research_prompt.md` only; the four other prompts were not opened.
- `sales-engine/prompts/email_prompt.md` — first 20 lines of `research_prompt.md` only.
- `sales-engine/scripts/run_pipeline.py` and `sales-engine-v2/scripts/run_pipeline.py` — diff of the first ~100 lines only; bodies not read.

### 10.4 Side effects forbidden

- `pytest` was not run (would import code; arguably no side effect for unit tests, but conservative posture per Audit Protocol §3 / Audit Prompt rule 3).
- `python main.py` — not invoked (would write to Notion / Supabase even in shadow mode for some paths).
- `python run_integration_check.py` — not invoked (writes test rows).
- `python sales-engine/scripts/run_pipeline.py --dry-run` — not invoked.
- `python scripts/vibe_prospecting_scan.py --dry-run` — not invoked.

---

## Appendix A — raw observations

### A.1 `git status` summary at audit start

Branch `main`, ahead/behind not checked. Working-tree changes (selection):

```
 M .claude/settings.json
 M CLAUDE.md
 D leads/Leads.zip
 M leads/_manifest.json
 M leads/_run.log
 D leads/<51 individual slug folders>/{email,metadata,report}
 M sales-engine/csv/vibe_combined_top30.csv
 M sales-engine/scripts/run_pipeline.py
?? .graphify_detect.json
?? AUDIT.md
?? docs/INSPECTION_REPORT.md
?? docs/README.md
?? docs/audit/
?? leads/leads/
?? sales-engine-v2/
?? sales-engine.zip
?? sales-engine/.claude/
?? sales-engine/csv/gk antiquated systems.csv
?? sales-engine/csv/gk_vibe_run4_top75.csv
?? sales-engine/csv/uae_ksa_hr_finance_leaders_gk_20260427151757.csv
```

### A.2 Recent commit history (since 2026-04-25)

```
462dcc4 docs: Workstream 3 complete summary
dc651f3 docs: update root README to point at SYSTEM.md
78bf7c9 docs: archive Phase 0 design history
e885c02 docs: SYSTEM.md as new source of truth
9dcdec2 Operator Console: Deal Support view
141647e Operator Console: Tasks view
c230d38 Operator Console: Pipeline view
740580a scripts: recruitment-partner audit (read-only)
3d212b4 tests: fix or delete deselected queue page assertion
41e31bb docs: Workstream 2 (mini) complete summary
2e2d09c requirements: align FastAPI pin with venv
78a51c6 tests: clarify brand-compliance fixture excludes discontinued recruitment_partner
a88fdde Discontinue recruitment_partner channel: update tests, scoring, and docs
e607547 vibe_prospecting_scan: add bulk_enrich step for email plaintext
d2b4558 docs: Explorium probe results
98e43a8 docs: Workstream 1 complete summary
634a431 .claude/settings.json: fix stale globalkinect-engines paths
0c5aad7 gitignore: comprehensive coverage for current repo layout
775fd41 docs: Explorium plaintext-email investigation
ab84e08 api/: integration tests confirm proxy method-name compatibility
97bde74 Operator Console: render Reply field in queue card
69b2b09 Pipeline: respond to 'replied' queue status in OutreachReviewAgent
b4f1b90 Fix brand rule: 'Global Kinect' (two words) in all production drafts
```

### A.3 `<think>`-block grep evidence

```
$ grep -l '<think>' leads/Reports/*/report.md | wc -l
62
$ ls leads/Reports/*/report.md | wc -l
62
```

### A.4 Brand-compliance grep on emails

```
$ grep -lE 'GlobalKinect[^\.]' leads/Reports/*/email.md
(no matches)
```

### A.5 Secret-scan output

```
$ git -C c:/dev/globalkinect/sales log --all -p -S 'sk-ant' --oneline
a286c4b First Lead Pack
diff --git a/sales-engine/config/.env.example b/sales-engine/config/.env.example
+# Copy this file to `.env` in the same directory and fill in your keys.
+# NEVER commit .env to git.

$ git -C c:/dev/globalkinect/sales log --all --oneline -- '*.env'
(no output)

$ git -C c:/dev/globalkinect/sales ls-files | grep -iE '\.env|secret|credential|key'
.env.example
sales-engine/config/.env.example
```

### A.6 Diff fingerprint, `sales-engine/scripts/run_pipeline.py` ↔ `sales-engine-v2/scripts/run_pipeline.py`

```
v1: 548 lines, dated 2026-04-27 (modified vs HEAD)
v2: 696 lines, dated 2026-05-03

Key v2 additions visible in first 100 lines of diff:
+ CLAUDE_MAX_TOKENS = {"email": 2000, "sequence": 4000, "call": 4000, "linkedin": 2000}
+ normalise_linkedin() helper
+ per-asset resumability for sequence.md / call.md / linkedin.md
+ --skip-{sequence,call,linkedin} flags
```

### A.7 Audit-protocol cross-check

This audit follows the structure dictated by the audit prompt (`docs/audit/audit-prompt.md`), which itself extends the Section-1-through-8 spec in `docs/audit/audit-protocol.md`. The prompt's structure (10 sections incl. "Did not read" + Appendix) is a strict superset of the protocol's 8 sections. This document conforms to the prompt's structure.
