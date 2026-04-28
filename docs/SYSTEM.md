# Global Kinect Sales — System

**Last updated:** 2026-04-28
**Git SHA at writing:** `9dcdec2`
**Scope:** the entire repository at `c:\dev\globalkinect\sales`.
**Audience:** future Michael, future Claude Code sessions, anyone joining the project.
**Authority:** this document supersedes the eight Phase 0 design docs at `docs/_archive_phase0_design/` (which describe an aspirational build that diverged from what shipped). Where this doc and the code disagree, the code wins.

---

## 1. Overview

The repository runs the outbound sales motion for Global Kinect, a payroll bureau / HRIS / EOR platform covering 11 MENA countries via globalkinect.ae and 100+ countries via globalkinect.co.uk. The system pulls fresh prospects from Explorium ("Vibe Prospecting") once a month, scores and qualifies them, drafts outreach copy, and queues each draft for human approval. SDRs operate inside a local web console; the canonical record lives in Notion; an archival mirror lives in Supabase; a TanStack/Lovable dashboard reads from both.

**Barbell strategy in one diagram:**

```
                ┌────────────────────────────────────────────┐
                │  globalkinect.ae   /   globalkinect.co.uk  │   inbound websites (out of repo)
                └────────────────────────────────────────────┘
                              │
                              ▼
   ┌─────────────────────────────────────────────────────────────────────┐
   │                                                                     │
   │  founder-led demos     ◄────►   SDR + AI       ◄────►   future cold │
   │  (curated short-list)         (this engine)              (Layer 3,  │
   │   sales-engine/                                           not built)│
   │                                                                     │
   └─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────────┐
                │  app/  +  scripts/  +  api/     │   the engine
                │  Notion ◄──► Supabase           │
                └─────────────────────────────────┘
                              │
                              ▼
                ┌─────────────────────────────────┐
                │  leads/leads/  (Lovable React)  │   dashboard surface
                └─────────────────────────────────┘
```

The cold-blanket / "Layer 3" sender is **not built** today. SDRs copy approved drafts into their own email client and hit send manually.

---

## 2. The four subsystems

### 2.1 Daily engine — `app/`, `main.py`

**Purpose:** Take rows that landed in Notion's Lead Intake DB (from Vibe scan, manual entry, or autonomous lanes) and walk each one through scoring → solution design → outreach drafting → pipeline state → operator queue.
**Reads:** Notion Lead Discovery, Lead Intake, Outreach Queue (operator decisions), Pipeline (existing state); Anthropic API for normalisation/qualification/classification.
**Writes:** Notion Leads / Pipeline / Solutions / Tasks / Deal Support / Outreach Queue / Sales Engine Runs / Accounts / Buyers; Supabase mirror tables; never sends actual outreach.
**Cadence:** Manually invoked or via Windows Task Scheduler. `SALES_ENGINE_RUN_MODE=shadow` exercises the pipeline without writing to Supabase or Notion operating views; `live` writes everything.
**Operator:** Michael, sometimes via the run script bundled at `scripts/run_monthly_scan.ps1` after a Vibe scan completes.

### 2.2 Vibe prospecting + bulk_enrich — `scripts/vibe_prospecting_scan.py`

**Purpose:** Pull prospects from Explorium matching one of the seven ICPs (A1, A2, A3, B1, B2, B3, B4 — `recruitment_partner` discontinued, see §8), enrich plaintext emails via the bulk enrichment endpoint, and write each prospect into Notion's Lead Intake DB ready for the daily engine.
**Reads:** Explorium `/v1/businesses` (pre-query for events / number_of_locations filters), `/v1/prospects` (returns hashed email only), `/v1/prospects/contacts_information/bulk_enrich` (plaintext email).
**Writes:** Notion Lead Intake (one page per prospect, `Status="ready"`, `Lane Label="Direct Outbound Signals"`).
**Cadence:** Monthly batch via `scripts/run_monthly_scan.ps1` — 7 ICP × region calls totalling ~3,200 prospects/month at current limits.
**Operator:** Michael; must hold Explorium credits (~6,400 credits/month for email-only enrichment at 2 credits/prospect — see [EXPLORIUM_PROBE_RESULT.md](EXPLORIUM_PROBE_RESULT.md)).

### 2.3 Per-lead deep research — `sales-engine/`

**Purpose:** A different beast from the main engine. Takes a CSV of curated short-list prospects (often from the founder-led side of the barbell), calls Perplexity sonar-deep-research per lead for a multi-section briefing, then calls Claude Opus 4.7 for a personalised outreach email.
**Reads:** CSV file from `sales-engine/csv/`. **No Notion or Supabase.**
**Writes:** Per-lead artefacts under `leads/Reports/<company-slug>/` — `report.md`, `email.md`, `metadata.json`, `mobile.txt`, `linkedin.txt`. Plus run history in `leads/_manifest.json` and `leads/_run.log`. **`leads/Reports/` is the canonical store of researched leads — treated as SACRED across all sessions; never modified or deleted.**
**Cadence:** Manual, on-demand. Resumable — won't re-research a lead whose `report.md` already exists.
**Operator:** Michael directly. Does not feed back into the main engine.
**Cost:** ~$0.60/lead Perplexity + Claude Opus drafting (per `metadata.json` traces).

### 2.4 Operator Console + api/ proxy + Lovable dashboard

**Purpose:** Three surfaces, same goal — let operators see and act on what the engine has produced without bouncing into the Notion UI.

- **Operator Console** at `app/web/operator_console.py` — a self-contained WSGI app (1,300+ lines) at `127.0.0.1:8787`. Routes: `/`, `/discovery`, `/intake`, `/accounts`, `/queue`, `/pipeline`, `/tasks`, `/deal-support`, `/runs`, `/help`, `/health`. Reads Notion via `OperatorConsoleService`. Only writes Notion via the Outreach Queue status form (approve / hold / regenerate / mark-sent).
- **`api/` FastAPI proxy** at `api/app/` — read-only proxy plus a small set of PATCH endpoints (queue status, intake status, runs note). Used by the Lovable dashboard. CORS open only to the dashboard's origin. No auth — bound to localhost.
- **Lovable dashboard** at `leads/leads/` — TanStack Start (Vite/React/TypeScript), Cloudflare Workers deploy target, Lovable.dev cloud-auth. Lives in its own nested git repo. Talks to the `api/` proxy and to Supabase directly via `@supabase/supabase-js`. **The Phase 1A scaffold backend in this directory has been archived** at `leads/leads/_archived_phase1a_backend/` — superseded by `app/` in this repo.

---

## 3. The 18 agents

All under `app/agents/`. Each is a Python class with a small public surface plus a result dataclass. Wired together by `main.py`.

| Agent | Triggered when | Reads | Writes |
|---|---|---|---|
| `DiscoverySourceCollectorAgent` | every `main.py` run if `discovery_sources.json` configured | RSS / HTML feeds | Notion Lead Discovery |
| `AutonomousLaneAgent` | every run, if Discovery DB configured | Notion Discovery + Intake + Outreach Queue | Notion Lead Discovery (Buyer Mapping + Reactivation lanes) |
| `LeadDiscoveryAgent` | every run | Notion Lead Discovery (`Status=ready`) | Notion Lead Intake (promoted), Notion Lead Discovery (status updates) |
| `LeadResearchAgent` | every run | Notion Lead Intake (`Status=ready`) | In-memory `Lead` objects (scored downstream); Notion intake processed markers |
| `LeadFeedbackAgent` | every run, before scoring | Notion Outreach Queue + Pipeline | In-memory `LeadFeedbackIndex` |
| `LeadScoringAgent` | every run | Lead objects + feedback index | Scored Lead objects in memory (1–10 score, priority bucket, recommended angle). recruitment_partner now scores 0 — see §8 |
| `EntityMapperAgent` | every run | Scored Lead objects | In-memory Account / Buyer rollups |
| `SolutionDesignAgent` | every run | Lead + optional PipelineRecord | In-memory `SolutionRecommendation`. **Skips `recruitment_partner`** — see §8 |
| `CRMUpdaterAgent` | every run | Lead + SolutionRecommendation | In-memory PipelineRecord (stage / outreach_status / next_action) |
| `MessageWriterAgent` | every run | Lead + SolutionRecommendation | In-memory OutreachMessage (deterministic templates — no Anthropic call here) |
| `PipelineIntelligenceAgent` | every run | PipelineRecords | Updated PipelineRecords (stage progression rules) |
| `LifecycleAgent` | every run | PipelineRecords | Updated PipelineRecords (stale-detection / next-action) |
| `ExecutionAgent` | every run | PipelineRecords | In-memory ExecutionTask objects (operator action items) |
| `ProposalSupportAgent` | every run | Lead + PipelineRecord + SolutionRecommendation | In-memory DealSupportPackage. **Skips `recruitment_partner`** — see §8 |
| `NotionSyncAgent` | live mode only | Account / Buyer / Lead / Pipeline / Solution / Task / DealSupport collections | Notion operating-view DBs (upserts) |
| `OutreachReviewAgent` | live mode only, **first** in the cycle | Notion Outreach Queue | Supabase Pipeline + Notion Pipeline (mirrors operator decisions: approved / sent / hold / replied) |
| `ResponseHandlerAgent` | every run, after feedback index | Notion Outreach Queue (`Reply` text) | Anthropic call → JSON classification (positive/objection/negative/out_of_office/neutral/request_for_info) → drafts next message → updates Pipeline + Outreach Queue + creates Execution Task |
| `OpportunitiesOutreachAgent` | only via `python main.py --generate-outreach` | Notion Opportunities DB (Vibe Prospecting imports) | Notion Outreach Queue + Supabase outreach_messages |

**Key dependencies:** `LeadScoringAgent` requires `LeadFeedbackAgent`'s index to apply duplicate-suppression penalties. `SolutionDesignAgent` is required before `CRMUpdaterAgent.create_pipeline_records_with_solution`, `MessageWriterAgent.generate_messages_with_solution`, and `ProposalSupportAgent.create_deal_support_packages_with_solution` (all use `_with_solution` suffix as the active path; the legacy paths still exist).

`OutreachReviewAgent` runs first in live mode (mirrors yesterday's operator clicks back into Pipeline state). Then `LeadFeedbackAgent` collects today's signal index. Then `ResponseHandlerAgent` classifies any new replies. Then the discovery → intake → scoring → packaging chain runs.

---

## 4. The Notion data model

12 logical Notion databases, each with an env var and a service constant in `app/services/notion_service.py:59-69`.

| Logical DB | Env var | Title property | Purpose |
|---|---|---|---|
| Lead Discovery | `NOTION_DISCOVERY_DATABASE_ID` | `Company` | Raw source-backed candidates from RSS / HTML / autonomous lanes. Status flow: `new`/`approved`/`ready` → `promoted`/`review`/`rejected`/`error` |
| Lead Intake | `NOTION_INTAKE_DATABASE_ID` | `Company` | Normalised, processable leads ready for scoring. Status: `ready` → `ingested` |
| Outreach Queue | `NOTION_OUTREACH_QUEUE_DATABASE_ID` | `Lead Reference` | Drafted messages awaiting operator decision. Status: `ready_to_send` / `approved` / `hold` / `regenerate` / `sent` / `replied`. The `Reply` rich-text property is where SDRs paste prospect responses for `ResponseHandlerAgent` to classify on the next run |
| Sales Engine Runs | `NOTION_RUNS_DATABASE_ID` | `Run Marker` | Per-run health: status, counts, error summary |
| Leads | `NOTION_LEADS_DATABASE_ID` | `Lead Reference` | Scored-lead snapshot per run |
| Pipeline | `NOTION_PIPELINE_DATABASE_ID` | `Lead Reference` | Live pipeline state per lead — stage, outreach_status, next_action. The Operator Console's `/pipeline` view reads from here |
| Solutions | `NOTION_SOLUTIONS_DATABASE_ID` | `Lead Reference` | Per-lead bundle/module/strategy recommendation |
| Tasks | `NOTION_TASKS_DATABASE_ID` | `Task` | Operator action items (draft / send / wait / follow_up / send_reply). The `/tasks` view reads from here |
| Deal Support | `NOTION_DEAL_SUPPORT_DATABASE_ID` | `Lead Reference` | Call prep, recap subject, proposal summary, next steps, objection responses. The `/deal-support` view reads from here |
| Accounts | `NOTION_ACCOUNTS_DATABASE_ID` | `Account` | Account-level rollup (one row per company) |
| Buyers | `NOTION_BUYERS_DATABASE_ID` | `Buyer` | Buyer-level rollup (one row per contact) |
| Opportunities | `NOTION_OPPORTUNITIES_DATABASE_ID` | `Company` | Vibe Prospecting imports awaiting outreach generation. Read by `OpportunitiesOutreachAgent` only |

**Note on field coverage:** the writers in `notion_service.py` write a slice of each Pydantic model, not the full thing. PipelineRecord has `last_response_at`, `last_contacted`, `last_outreach_at` Optional fields that are NOT persisted to Notion (they live only in Supabase). The Operator Console's Pipeline view shows `last_edited_time` (Notion's built-in) instead.

---

## 5. The Supabase mirror

Tables defined in `migrations/0001_initial_sales_schema.sql`:

| Table | Written by | Read by |
|---|---|---|
| `leads` | `SupabaseService.insert_leads` (live mode) | dashboard reads (potentially) |
| `outreach_messages` | `insert_outreach_messages` (live mode) + `OpportunitiesOutreachAgent` | dashboard reads, `ResponseHandlerAgent._fetch_solution` indirectly |
| `pipeline_records` | `upsert_pipeline_records` (live mode) | `OutreachReviewAgent`, `ResponseHandlerAgent`, dashboard reads |
| `solution_recommendations` | `upsert_solution_recommendations` (live mode) | `ResponseHandlerAgent._fetch_solution` |
| `deal_support_packages` | `insert_deal_support_packages` (live mode) | `ResponseHandlerAgent._fetch_deal_support` |
| `execution_tasks` | `insert_execution_tasks` (live mode) | dashboard reads |

**Lovable dashboard** runs additional Supabase migrations under `leads/leads/supabase/migrations/` that add `profiles`, `app_role` enum, and RLS helper functions. Same Supabase project, different schemas — the dashboard layers auth on top of the engine's commercial tables.

The dashboard reads are **not yet wired** as of this writing — the `api/` proxy is functional but it's uncertain whether the dashboard's React code currently calls `/api/notion/*` versus reading Supabase directly. See [INSPECTION_REPORT.md](INSPECTION_REPORT.md) §7.5.

---

## 6. Operational cadences

| Cadence | What runs | Trigger |
|---|---|---|
| **Monthly** | `scripts/run_monthly_scan.ps1` — 7 Vibe scans (~3,200 prospects) + a single `python main.py` live cycle | Manual; documented schtasks command commented in the script for Windows Task Scheduler |
| **Daily** | `python main.py` engine cycle | Manually invoked, optionally Task-Scheduler driven |
| **Per-lead** | `python sales-engine/scripts/run_pipeline.py --csv <file>` | Manual, on-demand. Resumable. Costs Perplexity + Claude Opus per lead |
| **Per-reply** | Operator pastes prospect reply into Notion Outreach Queue's `Reply` field, sets `Status=replied` → next `main.py` run picks it up via `ResponseHandlerAgent` | Operator action |
| **One-off** | `scripts/audit_recruitment_partner_leads.py` (read-only); `scripts/explorium_email_probe.py` (~16 credits) | Manual |

**Future cadences not yet built:**
- Signal-driven cold (the "Layer 3" of the barbell). The `discovery_sources.json` lane infrastructure is in place; LLM classification of signals is not.

---

## 7. Lead lifecycle

The single most important section. One Vibe-sourced lead, end to end:

1. **Vibe scan** (monthly). `scripts/vibe_prospecting_scan.py` calls `/v1/businesses` (pre-query) → `/v1/prospects` (returns hashed email) → `/v1/prospects/contacts_information/bulk_enrich` (plaintext email). Creates Notion Lead Intake row with `Status=ready`, `Lane Label=Direct Outbound Signals`, the plaintext email if available, and a Notes block including the prospect_id and any enrichment metadata.

2. **Daily engine — intake** (`main.py`). `LeadResearchAgent.collect_leads` reads ready intake rows, normalises each via Anthropic into a `Lead` Pydantic model, marks the intake row `Status=ingested`.

3. **Scoring**. `LeadScoringAgent.score_leads` adds score (1–10), priority bucket (low/medium/high), and `recommended_angle` string. Feedback-index downgrades duplicates.

4. **Entity mapping**. `EntityMapperAgent.build_accounts` / `build_buyers` produces account-level + buyer-level rollups.

5. **Solution design**. `SolutionDesignAgent.create_solution_recommendations` produces a `SolutionRecommendation` per lead — sales motion, recommended modules (e.g., `["EOR", "Payroll", "HRIS"]`), primary module, bundle label, commercial strategy, rationale.

6. **Pipeline records**. `CRMUpdaterAgent.create_pipeline_records_with_solution` makes a `PipelineRecord` per lead with `stage="new"`, `outreach_status="not_started"`.

7. **Drafting**. `MessageWriterAgent.generate_messages_with_solution` produces an `OutreachMessage` per lead — LinkedIn message, email subject, email message, follow-up message. **Deterministic** — no Anthropic call.

8. **Stage transitions**. Pipeline records flipped to `outreach_status="drafted"`, then `PipelineIntelligenceAgent.evaluate_pipeline` and `LifecycleAgent.evaluate_lifecycle` apply progression and staleness rules.

9. **Tasks + deal support**. `ExecutionAgent.generate_tasks` emits operator action items. `ProposalSupportAgent.create_deal_support_packages_with_solution` produces call prep / recap / proposal / objection content.

10. **Live persistence**. Supabase: `insert_leads`, `insert_outreach_messages`, `upsert_pipeline_records`, `upsert_solution_recommendations`, `insert_deal_support_packages`, `insert_execution_tasks`. Notion: upsert into Leads / Pipeline / Solutions / Tasks / Deal Support / Accounts / Buyers / Outreach Queue. Outreach Queue row lands with `Status=ready_to_send`.

11. **Operator decision** (Operator Console or Notion UI). SDR reviews the queue card and clicks **Approve**, **Hold**, **Regenerate**, or **Mark Sent**. Approval and hold are decision states; regenerate flags the row for redraft on next run; sent means the SDR copied the email body into their email client and clicked send manually. **No outbox in this engine.**

12. **Send (out of repo)**. SDR uses Gmail / Outlook / LinkedIn directly. Engine doesn't touch SMTP.

13. **Reply ingestion** (manual). When the prospect replies, the SDR pastes the reply text into the Outreach Queue page's `Reply` rich-text property and sets `Status=replied`.

14. **Next `main.py` run.** `OutreachReviewAgent.sync_queue_decisions` mirrors the `replied` status into the Pipeline record (sets `outreach_status="replied"`, `last_response_at=now`). Then `ResponseHandlerAgent.process_replies` reads the `Reply` text, classifies via Anthropic into `{positive, objection, negative, out_of_office, neutral, request_for_info}`, drafts the next response, updates the Pipeline stage based on classification, appends classification + drafted reply to the queue page's Notes field, and creates an Execution Task with `task_type="send_reply"`.

15. **Operator handles the next touch.** Same pattern: review the drafted reply in the queue card, edit if needed (in Notion — the Console doesn't edit copy), copy into email client, mark sent.

16. **Loop until close.** Stage advances through `contacted` → `replied` → `call_booked` → `proposal` → `closed` per `PipelineIntelligenceAgent` rules. Negative classifications and `out_of_office` short-circuit appropriately.

---

## 8. Decisions and policies

- **Brand rule: "Global Kinect" two words, never "GlobalKinect" one word.** Enforced in:
  - `tests/test_brand_compliance.py` regression checks against `LeadScoringAgent` / `SolutionDesignAgent` / `MessageWriterAgent` outputs
  - `OpportunitiesOutreachAgent._validate` — rejects any draft containing `globalkinect` (case-insensitive)
  - Two intentional one-word retentions, both with explanatory comments: HTTP `User-Agent: GlobalKinectSalesEngine/1.0` (RFC 7231 disallows spaces in product tokens), and the validator's diagnostic error message itself.

- **Recruitment-partner channel discontinued.** See [RECRUITMENT_PARTNER_DISCONTINUATION.md](RECRUITMENT_PARTNER_DISCONTINUATION.md). `SolutionDesignAgent` and `ProposalSupportAgent` skip these leads with a logged warning. `LeadScoringAgent._score_lead_type` scores `recruitment_partner` at 0 (was 3). The latest live audit ([RECRUITMENT_PARTNER_AUDIT_20260428_075641Z.md](RECRUITMENT_PARTNER_AUDIT_20260428_075641Z.md)) found 5 recruitment_partner leads still in Notion (3 of which are integration-test artefacts, 2 are real partner accounts). None had replies.

- **Email-only enrichment from Explorium.** `bulk_enrich` is called with `contact_types=["email"]` (2 credits/prospect) — see [EXPLORIUM_EMAIL_INVESTIGATION.md](EXPLORIUM_EMAIL_INVESTIGATION.md) and [EXPLORIUM_PROBE_RESULT.md](EXPLORIUM_PROBE_RESULT.md). Mobile and richer LinkedIn-profile enrichment are out of scope until a larger probe confirms cost / availability.

- **`leads/Reports/` is sacred.** The per-lead pipeline at `sales-engine/` writes researched leads, drafted emails, mobile numbers, and LinkedIn URLs to `leads/Reports/<company-slug>/`. This is the only copy. Never modified, moved, or deleted by automation.

- **Service tier expectations.** Notion API: standard rate-limited (no quotas explicitly hit). Anthropic: Sonnet 4 for normalisation/classification (model pinned via `ANTHROPIC_MODEL` env). Explorium: pay-per-call, no surfaced credit balance in responses. Supabase: free tier sufficient at current volumes.

- **Shadow vs live mode** (`SALES_ENGINE_RUN_MODE`). Shadow runs everything in memory and writes Discovery / Intake but skips Supabase persistence, Notion operating-view sync, and the Outreach Queue write — so a shadow run can be repeated without state-pollution. Live writes everything.

---

## 9. Known limitations and open questions

1. **No outbound sender.** Approved drafts sit in Notion until an SDR copy-pastes. No SMTP, no Gmail API, no Mailgun. The "send" button is operator-driven.

2. **No reply-inbox integration.** Replies land in the SDR's inbox; they paste into Notion manually. Half the loop is a copy-paste step.

3. **Mobile / phone enrichment is unverified at scale.** The single probe run returned `mobile_phone: null` for all 3 sampled prospects. Sample-specific or tier-gated; not investigated further.

4. **PipelineRecord timestamps don't round-trip.** `last_response_at`, `last_contacted`, `last_outreach_at` exist on the Pydantic model and Supabase schema but are not written to Notion. Notion shows `last_edited_time` as a proxy.

5. **`api/` proxy has no auth.** Bound to localhost; CORS open only to the Lovable dashboard's origin. Acceptable for local use; production deploy will need shared-secret or JWT.

6. **`SolutionDesignAgent.create_solution_recommendation` (singular)** still maps `recruitment_partner` to a motion + bundle, even though the plural wrapper skips it. Building-block code retained for cheap reactivation.

7. **`graphify-out/` is gitignored** as of Workstream 1 Fix 6. Local copies linger; future `/graphify` runs regenerate.

8. **Two FastAPI projects.** `api/app/main.py` is the live Notion proxy. `leads/leads/_archived_phase1a_backend/app/` is the Phase 1A scaffold, archived but still on disk.

9. **`integration_check.py` has not been re-run since the recruitment_partner discontinuation.** Worth running once before the next live monthly cycle.

10. **`graphify` post-commit hook re-runs on every commit.** Adds ~10 seconds of overhead per commit and rewrites `graphify-out/` (which is gitignored, so no diff noise).

---

## 10. Pointers to other docs

- [README.md](../README.md) — project root quickstart (currently description-heavy; SYSTEM.md supersedes)
- [AGENT_REGISTRY.md](../AGENT_REGISTRY.md) — agent-by-agent table
- [OPERATOR_GUIDE.md](../OPERATOR_GUIDE.md) — day-to-day operating
- [RUNBOOK.md](../RUNBOOK.md) — common situations
- [DECISION_PLAYBOOK.md](../DECISION_PLAYBOOK.md) — operator decisions
- [ICP_SOURCING_PLAYBOOK.md](../ICP_SOURCING_PLAYBOOK.md) — full ICP definitions (canonical lives in `c:\dev\globalkinect\branding\GLOBAL_KINECT_ICP.md`)
- [SOURCING_STRATEGY.md](../SOURCING_STRATEGY.md), [SOURCING_AGENTS.md](../SOURCING_AGENTS.md), [SOURCING_LANES.md](../SOURCING_LANES.md) — discovery layer
- [NOTION_DISCOVERY_SCHEMA.md](../NOTION_DISCOVERY_SCHEMA.md), [NOTION_INTAKE_SCHEMA.md](../NOTION_INTAKE_SCHEMA.md) — Notion DB property reference
- [DATABASE_MIGRATIONS.md](../DATABASE_MIGRATIONS.md) — Supabase migration runner
- [SYSTEM_ARCHITECTURE.md](../SYSTEM_ARCHITECTURE.md), [PROJECT_PLAN.md](../PROJECT_PLAN.md) — older orientation docs

### docs/

- [INSPECTION_REPORT.md](INSPECTION_REPORT.md) — full read-only inspection of behaviour, sourced from code
- [EXPLORIUM_EMAIL_INVESTIGATION.md](EXPLORIUM_EMAIL_INVESTIGATION.md) — diagnosis of why Vibe-sourced rows had blank emails
- [EXPLORIUM_PROBE_RESULT.md](EXPLORIUM_PROBE_RESULT.md) — actual probe output confirming bulk_enrich works
- [RECRUITMENT_PARTNER_DISCONTINUATION.md](RECRUITMENT_PARTNER_DISCONTINUATION.md) — channel-cutoff decision + reactivation recipe
- [RECRUITMENT_PARTNER_AUDIT_*.md](.) — timestamped read-only audits
- [WORKSTREAM_1_COMPLETE.md](WORKSTREAM_1_COMPLETE.md), [WORKSTREAM_2_MINI_COMPLETE.md](WORKSTREAM_2_MINI_COMPLETE.md) — session summaries
- [_archive_phase0_design/](_archive_phase0_design/) — the seven Phase 0 design docs that this doc supersedes

### Operational

- `discovery_sources.json` — feed/source watchlist (24 sources across 8 lanes after Workstream 1 Fix 5)
- `.env.example` — env var template
- `requirements.txt` — Python deps (FastAPI 0.136.1, Anthropic, Supabase, httpx, Pydantic, etc.)
- `tests/` — 176 tests; one full pytest run takes ~7s

### Out of repo

- `c:\dev\globalkinect\branding\` — canonical brand + ICP definitions. SACRED for brand decisions.
- `c:\dev\globalkinect\brain\` — Obsidian vault of business knowledge (per `CLAUDE.md`).
