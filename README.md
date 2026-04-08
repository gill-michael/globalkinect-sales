# GlobalKinect Sales Engine

## Overview

GlobalKinect Sales Engine is an internal commercial workflow engine for identifying, qualifying, shaping, and progressing revenue opportunities for one modular employment infrastructure platform. The primary commercial focus is the UAE, Saudi Arabia, and Egypt, while the wider supported payroll and employment footprint also includes the other Gulf states plus Lebanon and Jordan. HRIS-led opportunities can also be qualified outside those focus markets when the source evidence is strong.

The platform can be sold as:

- `EOR only`
- `Payroll only`
- `HRIS only`
- `EOR + Payroll`
- `Payroll + HRIS`
- `EOR + HRIS`
- `Full Platform`

The codebase is deterministic by design. It does not depend on UI, external CRM sync, or AI-driven decisioning for commercial logic. The commercial source of truth is `SolutionRecommendation`, which drives downstream pipeline, messaging, execution, and deal-support behavior.

## Current Workflow

The preferred execution flow is:

`Outreach Queue review sync -> Lead discovery -> qualification -> Lead Intake -> lead scoring -> solution design -> pipeline creation -> message drafting -> outreach packaging -> pipeline intelligence -> lifecycle evaluation -> execution tasks -> deal support -> Supabase persistence -> Notion operating sync -> run logging`

Current capabilities:

- mock lead generation for GCC expansion scenarios
- evidence-backed lead discovery promotion from a dedicated Notion discovery database
- real lead ingestion from a dedicated Notion intake database
- deterministic lead scoring and prioritization
- feedback-aware duplicate suppression and score adjustment from existing
  outreach and pipeline activity
- solution-led bundle and sales-motion recommendation
- solution-aligned pipeline record creation
- solution-led messaging generation
- send-ready outreach packaging into a dedicated Notion outreach queue
- live operator decisions in `Outreach Queue` syncing back into pipeline state
  on the next live run
- deterministic pipeline progression and stale-deal handling
- execution task generation
- solution-led proposal and deal-support package generation
- live-ready Supabase persistence when configured
- live-ready Notion operating sync when configured
- live-ready Notion run logging when configured

## Repository Structure

- `app/agents`: deterministic business workflow agents
- `app/models`: Pydantic domain models
- `app/services`: integration and configuration services
- `app/utils`: logging and shared utilities
- `docs`: operational handoff and integration reference material
- `tests`: mocked and deterministic test coverage

Primary agents and services now in code:

- `LeadResearchAgent`
- `LeadScoringAgent`
- `SolutionDesignAgent`
- `CRMUpdaterAgent`
- `MessageWriterAgent`
- `PipelineIntelligenceAgent`
- `LifecycleAgent`
- `ExecutionAgent`
- `ProposalSupportAgent`
- `NotionSyncAgent`
- `SupabaseService`
- `NotionService`

If you are using Notion AI to create or normalize the operational databases,
the exact prompts are collected in [docs/NOTION_AI_PROMPTS.md](/c:/dev/globalkinect-engines/sales/docs/NOTION_AI_PROMPTS.md).

## Environment Configuration

Set these values in `.env` before attempting live integration:

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`
- `SALES_ENGINE_RUN_MODE`
- `SALES_ENGINE_TRIGGERED_BY`
- `OPERATOR_CONSOLE_HOST`
- `OPERATOR_CONSOLE_PORT`
- `DISCOVERY_SOURCES_FILE`
- `DISCOVERY_SOURCE_MAX_ITEMS_PER_SOURCE`
- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `DATABASE_URL`
- `NOTION_API_KEY`
- `NOTION_DISCOVERY_DATABASE_ID`
- `NOTION_INTAKE_DATABASE_ID`
- `NOTION_OUTREACH_QUEUE_DATABASE_ID`
- `NOTION_RUNS_DATABASE_ID`
- `NOTION_LEADS_DATABASE_ID`
- `NOTION_PIPELINE_DATABASE_ID`
- `NOTION_SOLUTIONS_DATABASE_ID`
- `NOTION_TASKS_DATABASE_ID`
- `NOTION_DEAL_SUPPORT_DATABASE_ID`

If Supabase or Notion are not configured, the application skips those integrations cleanly and continues the deterministic demo flow.

## Running The Project

1. Activate the local virtual environment:

```powershell
.\venv\Scripts\Activate.ps1
```

2. Run the main workflow:

```powershell
python main.py
```

3. Run the local operator console:

```powershell
python run_operator_console.py
```

The entry point:

- on live runs, syncs operator decisions from `Outreach Queue` back into live
  pipeline state before sourcing and packaging new work
- collects raw source evidence from configured feed sources into `Lead Discovery` when configured
- promotes qualified rows from the Notion `Lead Discovery` database into `Lead Intake` when configured
- prefers real leads from the Notion intake database when configured
- falls back to mock leads only when the intake database is not configured
- uses Anthropic structured qualification for discovery rows when configured
- uses Anthropic structured normalization for intake rows when configured
- packages send-ready outreach into the Notion `Outreach Queue` when configured
- writes daily run status into the Notion `Sales Engine Runs` database when configured
- persists records to Supabase when configured
- syncs operating views to Notion when configured
- prints concise demo output for review

The operator console:

- runs locally on `http://127.0.0.1:8787` by default
- reads `Lead Discovery`, `Lead Intake`, `Outreach Queue`, and `Sales Engine Runs`
- lets you mark outreach queue rows as `Approved`, `Hold`, `Regenerate`, or `Sent`
- does not create a second source of truth; it works directly on the existing Notion databases

## Lead Discovery

The repository now supports a discovery stage before intake so the daily run can
screen source-backed prospects and only promote stronger opportunities into the
real pipeline.

Required configuration for discovery:

- `NOTION_API_KEY`
- `NOTION_DISCOVERY_DATABASE_ID`

Recommended configuration for Anthropic-backed qualification:

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

Recommended configuration for automated source collection:

- `DISCOVERY_SOURCES_FILE`
- `DISCOVERY_SOURCE_MAX_ITEMS_PER_SOURCE`

The runtime behavior is:

- if a discovery sources file is configured and present, `main.py` pulls raw
  feed entries into `Lead Discovery` before qualification
- if the discovery database is configured, `main.py` reads ready discovery rows
  before processing intake
- each discovery row is qualified into one of `promote`, `review`, or `reject`
- if the same lead or company already has meaningful queue or pipeline activity,
  duplicate discovery promotions are downgraded to `review`
- `promote` rows are upserted into `Lead Intake` with `Status` set back to
  `ready`
- `review` and `reject` rows stay in `Lead Discovery` with confidence, evidence,
  fit reason, and processing fields updated
- if Anthropic is unavailable or the qualification request fails, the application
  falls back to deterministic evidence scoring

The discovery database schema is documented in [NOTION_DISCOVERY_SCHEMA.md](/c:/dev/globalkinect-engines/sales/NOTION_DISCOVERY_SCHEMA.md).

## Automated Source Collection

The repository now supports a config-driven source collector that reads RSS or
Atom feeds from a local sources file and writes only new or changed evidence
into `Lead Discovery`.

Use this when you want the daily run to discover leads automatically instead of
relying only on manually entered discovery rows.

Configuration:

- `SALES_ENGINE_RUN_MODE`
  Use `shadow` for evaluation runs or `live` for normal daily packaging.
- `SALES_ENGINE_TRIGGERED_BY`
  Use `manual` for terminal runs or `scheduler` for scheduled runs.
- `DISCOVERY_SOURCES_FILE`
  Defaults to `discovery_sources.json` in the repo root.
- `DISCOVERY_SOURCE_MAX_ITEMS_PER_SOURCE`
  Controls how many recent entries are checked per configured source.

The source file can be either a flat list of sources or a lane-grouped object with `lanes`.
An example is provided in [discovery_sources.example.json](/c:/dev/globalkinect-engines/sales/discovery_sources.example.json).
Use that file as the template for your real repo-local `discovery_sources.json`.

Supported source adapters currently include:

- RSS and Atom feeds
- JSON Feed endpoints
- Greenhouse public JSON boards
- Lever-style JSON boards
- Workable public jobs APIs
- generic HTML/newsroom pages via `webpage_html`
- XML sitemaps via `sitemap_xml`
- `manual_signals` entries defined directly in the source file

Recommended source strategy:

- use careers feeds as one signal layer, not the primary sourcing model
- prioritize account signals, buyer signals, and expansion signals over isolated job posts
- spread the watchlist across `EOR`, `Payroll`, `HRIS`, and partner motions rather than treating everything as payroll
- treat UAE, Saudi Arabia, and Egypt as priority signals
- still accept credible signals from Qatar, Kuwait, Bahrain, Oman, Lebanon, and Jordan
- stay broad across industries, but strict on commercial relevance
- promote rows only when there is a plausible buyer and a believable sales case

The current sourcing thesis is documented in [SOURCING_STRATEGY.md](/c:/dev/globalkinect-engines/sales/SOURCING_STRATEGY.md). Use that document as the commercial source of truth when deciding whether discovery output is actually useful.
The current multi-agent sourcing structure is documented in [SOURCING_AGENTS.md](/c:/dev/globalkinect-engines/sales/SOURCING_AGENTS.md).
The lane-based sourcing architecture is documented in [SOURCING_LANES.md](/c:/dev/globalkinect-engines/sales/SOURCING_LANES.md).
Starter manual strategic-account entries are provided in [strategic_account_entries.example.json](/c:/dev/globalkinect-engines/sales/strategic_account_entries.example.json).

Recommended source fields:

- `agent_label`
  Use this to state which sourcing hypothesis owns the feed, such as `EOR Expansion Agent`, `Payroll Complexity Agent`, `HRIS Maturity Agent`, or `Partner Channel Agent`.
- `lane_label`
  Use this to group sources into broad sourcing lanes such as `Expansion Signals`, `Payroll Complexity`, `HRIS Maturity`, `Partner Channel`, or `Manual Strategic Accounts`.
- `source_priority`
  Higher values should be used for the sources you trust most to generate real commercial opportunities.
- `trust_score`
  Use this to reflect whether the source is an official company or recruiter endpoint versus a weaker public signal.
- `service_focus`
  Use values such as `payroll`, `eor`, `partner`, or `hris` so qualification can weight the signal correctly.
- `default_target_country`
  Use this when the source itself is country-specific even if each entry does not restate the market explicitly.
- `derive_company_name_from_title`
  Use this for broad market-intelligence feeds when the entry title contains the company name and the source is not tied to a single account.
- `entry_url_keywords`
  Use this to constrain `webpage_html` and `sitemap_xml` sources to likely article/news paths instead of scraping every link on a page.
- `fetch_detail_pages`
  Use this on `webpage_html` and `sitemap_xml` sources when list pages only contain headlines and the detail page text is needed for qualification.
- `active`
  Set false to keep a source in the file without collecting from it.

Idempotency behavior:

- if the same company already has the same `Source URL` and `Evidence` in
  `Lead Discovery`, the collector skips it
- if the evidence changes, the collector updates the row and requeues it as
  `ready`
- this prevents the same feed item from being reprocessed every day unless the
  signal actually changes

## Real Lead Intake

The repository now supports a real lead-ingestion path from a dedicated Notion
intake database.

Required configuration for real intake:

- `NOTION_API_KEY`
- `NOTION_INTAKE_DATABASE_ID`

Recommended configuration for daily operations:

- `NOTION_OUTREACH_QUEUE_DATABASE_ID`
- `NOTION_RUNS_DATABASE_ID`

Recommended configuration for Anthropic-backed normalization:

- `ANTHROPIC_API_KEY`
- `ANTHROPIC_MODEL`

The runtime behavior is:

- if the intake database is configured, `main.py` reads ready intake rows from
  Notion
- if matching queue or pipeline feedback already exists, scoring applies a small
  penalty and records a feedback summary for operator visibility
- if Anthropic is configured, each row is normalized into the internal `Lead`
  model with a structured tool-use API call
- if Anthropic is unavailable, the row is mapped directly into a `Lead`
- if the outreach queue database is configured, each run packages send-ready
  email and LinkedIn drafts into `Outreach Queue`
- repeat live runs preserve operator-managed queue rows already marked
  `Approved`, `Sent`, or `Hold`
- if a queue row is marked `Regenerate`, the next live run refreshes the draft
  and returns it to `Ready to send`
- on live runs, queue rows marked `Approved`, `Sent`, or `Hold` are also
  reconciled back into live pipeline state before the next sourcing cycle
- if the runs database is configured, each run writes a run marker, status,
  counts, and error summary into `Sales Engine Runs`
- processed rows can be marked back in Notion with tracking fields such as
  `Status`, `Lead Reference`, `Fit Reason`, and `Processed At`
- if the intake database is not configured, the application falls back to the
  existing mock leads for local demo use
- if `SALES_ENGINE_RUN_MODE=shadow`, the engine still collects discovery,
  promotes intake, scores leads, and builds packaging previews, but it skips
  Supabase persistence, Outreach Queue sync, and operating-view sync

The intake database schema is documented in [NOTION_INTAKE_SCHEMA.md](/c:/dev/globalkinect-engines/sales/NOTION_INTAKE_SCHEMA.md).

## Daily Use

For the daily operating loop:

1. maintain the watched source list in `discovery_sources.json`
2. add or approve any extra hand-curated rows in `Lead Discovery`
3. optionally add hand-curated rows directly in `Lead Intake`
4. run in shadow mode first for 5-7 days:

```powershell
$env:SALES_ENGINE_RUN_MODE='shadow'
$env:SALES_ENGINE_TRIGGERED_BY='scheduler'
python main.py
```

5. review promoted and processed rows in `Lead Discovery` and `Lead Intake`
6. review run status in `Sales Engine Runs`
7. once the discovery quality is stable, switch to live mode:

```powershell
$env:SALES_ENGINE_RUN_MODE='live'
$env:SALES_ENGINE_TRIGGERED_BY='scheduler'
python main.py
```

8. open the local operator console:

```powershell
python run_operator_console.py
```

9. review send-ready drafts in `Outreach Queue`
10. approve the rows you want to send, hold the rest, and mark rows sent after execution
11. send the approved outreach manually

Once the environment is stable, `python main.py` is the command to schedule in
Windows Task Scheduler for once-daily execution.

## Shadow To Live Rollout

Use this sequence for safer production rollout:

1. curate `discovery_sources.json` around official high-trust feeds only
2. run daily in `shadow` mode for 5-7 days
3. review `Lead Discovery`, `Lead Intake`, and `Sales Engine Runs`
4. tune trust scores, source priority, and watch keywords
5. switch to `live` mode once the promoted leads are consistently useful

## Testing Phase

As of March 23, 2026, the repository is in controlled testing phase.

The immediate goal is to validate discovery quality, operator usability, and
integration stability in `shadow` mode before scheduled live rollout.

The current testing playbook is documented in [TESTING_PHASE_PLAN.md](/c:/dev/globalkinect-engines/sales/TESTING_PHASE_PLAN.md).
The active sourcing thesis is documented in [SOURCING_STRATEGY.md](/c:/dev/globalkinect-engines/sales/SOURCING_STRATEGY.md).
Operator guidance is documented in [OPERATOR_GUIDE.md](/c:/dev/globalkinect-engines/sales/OPERATOR_GUIDE.md), [DECISION_PLAYBOOK.md](/c:/dev/globalkinect-engines/sales/DECISION_PLAYBOOK.md), and [RUNBOOK.md](/c:/dev/globalkinect-engines/sales/RUNBOOK.md).
The current commercial gap assessment is documented in [PIPELINE_GAPS.md](/c:/dev/globalkinect-engines/sales/PIPELINE_GAPS.md).
The current implementation backlog is documented in [IMPLEMENTATION_BACKLOG.md](/c:/dev/globalkinect-engines/sales/IMPLEMENTATION_BACKLOG.md).

Use [run_integration_check.py](/c:/dev/globalkinect-engines/sales/run_integration_check.py)
to validate environment wiring, then run the daily engine in `shadow` mode and
review outputs in `Lead Discovery`, `Lead Intake`, `Outreach Queue`, and
`Sales Engine Runs`.

For current rollout guidance, prefer this README, [SYSTEM_ARCHITECTURE.md](/c:/dev/globalkinect-engines/sales/SYSTEM_ARCHITECTURE.md), and [PROJECT_PLAN.md](/c:/dev/globalkinect-engines/sales/PROJECT_PLAN.md). Some older transition notes under `docs/` are preserved for historical context rather than as the active operating plan.

## Discovery-First Operating Model

Use the databases with clear roles:

1. `Lead Discovery`
   Store raw source-backed evidence such as job postings, recruiter pages,
   partner referrals, or expansion notes.
2. `Lead Intake`
   Hold only normalized, processable leads that are ready for scoring and
   packaging.
3. `Outreach Queue`
   Hold the send-ready subject lines and messages for operator review.
4. `Sales Engine Runs`
   Track whether the autonomous run completed, found leads, or failed.

This gives you a practical daily automation path:

`Lead Discovery -> qualification -> Lead Intake -> outreach packaging`

while still keeping a human approval step before messages are sent.

## Operator Console

The repository now includes a lightweight local operator console for the existing
Notion-backed workflow.

Views:

1. `Dashboard`
   Summary counts for ready discovery, intake, queue, and recent run health.
2. `Lead Discovery`
   Review source-backed candidates and their qualification status.
3. `Lead Intake`
   Review normalized leads that are waiting for or recently completed packaging.
4. `Outreach Queue`
   Approve, hold, regenerate, or mark drafts sent.
5. `Run Monitor`
   Inspect recent run records and failures.

Run it locally:

```powershell
python run_operator_console.py
```

## Running Tests

```powershell
pytest -v
```

The test suite currently covers:

- lead generation, discovery qualification, and intake promotion
- solution recommendation logic
- CRM and pipeline updates
- solution-led messaging
- pipeline intelligence and lifecycle evaluation
- execution task generation
- solution-led proposal support
- Supabase service methods through mocks
- Notion service, discovery handling, outreach queue sync, and run logging through mocks

## Database Migrations

The repository uses forward-only SQL migrations for the Supabase Postgres schema.

- migration files live in `migrations/`
- `DATABASE_URL` is required for migration execution
- the migration runner applies pending files in order and records checksums in `schema_migrations`

Core commands:

```powershell
pip install -r requirements.txt
python migrations/run_migrations.py
python migrations/create_migration.py add_new_change
```

Detailed migration notes are in `DATABASE_MIGRATIONS.md`.

## Integration Check

Use the integration check to validate that the deterministic workflow, Supabase
persistence layer, and Notion operating sync are connected correctly for a
small marker-tagged test run.

Required environment variables for full validation:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `NOTION_API_KEY`
- `NOTION_LEADS_DATABASE_ID`
- `NOTION_PIPELINE_DATABASE_ID`
- `NOTION_SOLUTIONS_DATABASE_ID`
- `NOTION_TASKS_DATABASE_ID`
- `NOTION_DEAL_SUPPORT_DATABASE_ID`

Optional but recommended:

- `DATABASE_URL`
  - used by migrations
  - used by the optional cleanup command for safe deletion of integration-test
    rows in Supabase only

Run the integration check:

```powershell
python run_integration_check.py
```

Optional commands:

```powershell
python run_integration_check.py --run-marker validation_run
python run_integration_check.py --cleanup
python run_integration_check.py --cleanup --run-marker validation_run
```

The integration runner:

- generates 2 deterministic test leads only
- prefixes every test record with an `INTEGRATION_TEST` marker
- runs scoring, solution design, pipeline creation, messaging, pipeline
  intelligence, lifecycle evaluation, execution tasks, and deal support
- attempts Supabase inserts and filtered fetch validation when configured
- attempts Notion sync and reports created or updated page ids when configured
- prints a structured summary without exposing secret values

Successful output includes:

- environment presence checks
- generated record counts
- Supabase configured / insert / fetch results
- Notion configured / sync results
- the run marker and sample lead reference for traceability
- an overall `fully integration-ready: yes` or `no` result

Cleanup notes:

- `--cleanup` only targets Supabase rows whose `company_name` or
  `lead_reference` contains the integration-test marker
- Notion cleanup is intentionally manual to avoid risky broad deletion
- If no run marker is supplied with cleanup, the script targets
  `INTEGRATION_TEST` records only

## Integration Status

The project is now in an integration-ready state.

- Supabase: service methods, schema references, inserts, fetches, updates, and upserts are implemented
- Notion: service layer, field mappings, page upsert behavior, and sync orchestration are implemented
- Source collection: feed-driven discovery candidate collection into `Lead Discovery` is implemented
- Discovery: source-backed lead qualification and auto-promotion into `Lead Intake` are implemented
- Real lead intake: Notion intake ingestion and Anthropic-backed lead normalization are implemented
- Daily packaging: Outreach Queue and Sales Engine Runs integration are implemented

The remaining next-phase work is operational rather than architectural:

1. operate the real source watchlist, discovery, intake, and outreach-review process
2. move into scheduled execution in Windows Task Scheduler
3. add monitoring refinements, richer source coverage, and later external CRM sync

Out of scope in the current repository state:

- external CRM integration
- UI
- async orchestration
- Anthropic-driven commercial decisioning

