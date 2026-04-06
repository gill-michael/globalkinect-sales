# Build Log

## Purpose

This log records what has been built in the repository and marks the current integration position of the system.

## Chronological Record

### 1. Project setup

- Initialized the repository as a Python application for an internal commercial sales engine
- Added `main.py`, environment scaffolding, logging, and pytest configuration

### 2. Foundation and lead workflow

- Built the base application structure under `app/`
- Implemented `Lead`
- Implemented `LeadResearchAgent`
- Implemented the initial service scaffolding

### 3. Deterministic scoring and messaging

- Implemented `LeadScoringAgent`
- Added priority and recommended-angle logic
- Implemented `MessageWriterAgent`
- Added structured `OutreachMessage`

### 4. Pipeline tracking and proposal support

- Implemented `PipelineRecord`
- Implemented `CRMUpdaterAgent`
- Implemented `DealSupportPackage`
- Implemented `ProposalSupportAgent`

### 5. Commercial realignment

- Added canonical platform terms
- Added `SolutionRecommendation`
- Implemented `SolutionDesignAgent`
- Moved the system toward bundle-led commercial logic

### 6. Pre-integration execution pass

- Added timestamped pipeline lifecycle handling
- Implemented `PipelineIntelligenceAgent`
- Implemented `LifecycleAgent`
- Implemented `ExecutionAgent`
- Added execution-task persistence support
- Updated documentation and mocked tests for the pre-integration state

### 7. Live integration readiness pass

- Refined `SupabaseService` with explicit table constants and execution-task fetch support
- Added `docs/SUPABASE_SCHEMA_REFERENCE.md`
- Added `supabase_schema_reference.sql` as a practical reference for expected tables
- Added Notion environment settings to configuration and `.env.example`
- Implemented `NotionService` with deterministic page upsert support for:
  - leads
  - pipeline records
  - solution recommendations
  - execution tasks
  - deal support packages
- Implemented `NotionSyncAgent` as the orchestration layer for Notion operating sync
- Integrated Notion sync into `main.py` after Supabase persistence
- Added mocked tests for `NotionService` and `NotionSyncAgent`
- Extended Supabase tests to cover execution-task fetch behavior
- Updated the repository documentation to reflect that Supabase persistence and Notion sync are implemented when configured

### 8. Live integration validation pass

- Added `app/orchestrators/integration_check.py` to run a small deterministic
  end-to-end validation flow with clearly marked `INTEGRATION_TEST` records
- Added `run_integration_check.py` so the validation can be run directly from
  the VS Code terminal
- Added environment validation reporting for Supabase, Notion, and
  `DATABASE_URL` presence without exposing secret values
- Added safe Supabase cleanup support that only targets integration-test rows
  containing the marker
- Updated `NotionSyncAgent` to return sync results so created or updated page ids
  can be reported during validation
- Added mocked tests for the integration validation workflow and updated the
  Notion sync tests for the new return shape
- Updated the README with integration-check run instructions, marker behavior,
  and cleanup guidance

### 9. Real lead ingestion pass

- Added `NOTION_INTAKE_DATABASE_ID` and `ANTHROPIC_LEAD_RESEARCH_MODEL`
  configuration support
- Added `LeadIntakeRecord` as the raw intake model
- Extended `NotionService` with lead-intake read and status-update support
- Extended `AnthropicService` with structured Messages API-based lead normalization
- Updated `LeadResearchAgent` to prefer real Notion intake rows and only fall
  back to mock leads when intake is not configured
- Updated `main.py` to use the real intake path
- Added mocked tests for:
  - real intake collection
  - Anthropic normalization
  - intake tracking updates in Notion
- Added `NOTION_INTAKE_SCHEMA.md` to document the real intake database
  contract

### 10. Daily packaging and run logging pass

- Added `NOTION_OUTREACH_QUEUE_DATABASE_ID` and `NOTION_RUNS_DATABASE_ID`
  configuration support
- Added `OutreachQueueItem` and `SalesEngineRun` models
- Extended `NotionService` with:
  - outreach queue sync support
  - sales engine run logging support
  - tolerant select-option mapping so internal values can map to human-readable
    Notion labels
- Updated `main.py` to:
  - create a run marker for each execution
  - package send-ready outreach into `Outreach Queue`
  - write run status and counts into `Sales Engine Runs`
  - record a completed run even when no intake rows are ready
- Added mocked tests for outreach queue sync and run-log sync
- Updated documentation so `python main.py` is now the supported daily run
  command for scheduled operation

### 11. Discovery-first autonomous sourcing pass

- Added `NOTION_DISCOVERY_DATABASE_ID` and `ANTHROPIC_DISCOVERY_MODEL`
  configuration support
- Added `LeadDiscoveryRecord` and `DiscoveryQualification` models
- Extended `AnthropicService` with structured discovery qualification and
  deterministic fallback scoring
- Extended `NotionService` with:
  - discovery queue fetch support
  - discovery status updates for promoted, review, rejected, and error outcomes
  - intake upsert support from qualified discovery rows
- Added `LeadDiscoveryAgent` to:
  - qualify source-backed discovery records
  - auto-promote strong records into `Lead Intake`
  - keep weaker records in `Lead Discovery` with tracking metadata
- Updated `main.py` so the scheduled daily run now executes:
  - discovery qualification
  - intake normalization
  - downstream scoring, messaging, packaging, sync, and run logging
- Added mocked tests for discovery qualification, discovery promotion, and
  discovery Notion schema handling
- Added `NOTION_DISCOVERY_SCHEMA.md` to document the autonomous discovery
  database contract

### 12. Feed-driven source collection pass

- Added `DISCOVERY_SOURCES_FILE` and `DISCOVERY_SOURCE_MAX_ITEMS_PER_SOURCE`
  configuration support
- Added `DiscoverySource` and `DiscoveryCandidate` models
- Implemented `DiscoverySourceService` to:
  - load a local JSON watchlist of RSS or Atom feeds
  - parse recent entries from configured company or partner sources
  - detect UAE, Saudi Arabia, and Egypt evidence in source text
  - build source-backed discovery candidates
- Implemented `DiscoverySourceCollectorAgent` to sync only new or changed
  evidence into `Lead Discovery`
- Extended `NotionService` with idempotent discovery candidate upsert logic so
  unchanged source signals are skipped rather than requeued every day
- Updated `main.py` so the daily run now executes:
  - source collection into `Lead Discovery`
  - discovery qualification into `Lead Intake`
  - downstream scoring, packaging, sync, and run logging
- Added `discovery_sources.example.json` as a working config template for
  watched source feeds
- Added mocked tests for feed parsing, source collection, and discovery
  candidate idempotency

### 13. Source-quality and shadow-mode rollout pass

- Added `SALES_ENGINE_RUN_MODE` and `SALES_ENGINE_TRIGGERED_BY` configuration
  support so the engine can be run safely in `shadow` or `live` mode
- Added shared target-market priority handling so the primary focus remains
  UAE, Saudi Arabia, and Egypt while still supporting the wider Gulf states,
  Lebanon, and Jordan
- Added source metadata across discovery models and source configs, including:
  - `service_focus`
  - `source_priority`
  - `trust_score`
  - `active`
  - `discovery_key`
  - `published_at`
- Extended `DiscoverySourceService` to:
  - de-duplicate candidates per run
  - rank candidates by source priority and trust score
  - parse Workable public jobs APIs in addition to the existing feed adapters
  - allow explicit HRIS-led discovery outside the payroll focus markets
- Extended `NotionService` to:
  - sync and read richer discovery metadata when the database includes the
    matching optional properties
  - look up discovery rows by `Discovery Key` and `Source URL` before falling
    back to company title
- Extended `AnthropicService` deterministic fallback qualification to consider:
  - source trust score
  - source priority
  - service focus
  - HRIS-anywhere handling
- Updated `LeadResearchAgent` so shadow runs can collect intake rows without
  marking them processed
- Updated `main.py` so shadow mode:
  - still runs source collection, discovery, intake normalization, scoring, and
    message packaging logic
  - skips Supabase persistence, Outreach Queue sync, and operating-view sync
- Updated the default and example discovery source files to use richer source
  metadata and a payroll-first operating posture
- Added mocked tests for:
  - Workable parsing
  - candidate de-duplication
  - shadow-mode intake behavior
  - richer discovery metadata sync
  - HRIS-anywhere qualification
- Updated the README with the shadow-to-live rollout sequence

### 14. Live rerun persistence hardening

- Updated `SupabaseService` with a shared upsert helper that uses
  `lead_reference` conflict handling for unique commercial entities
- Switched live persistence in `main.py` to upsert:
  - `pipeline_records`
  - `solution_recommendations`
- Added regression coverage to ensure the persistence path uses upserts for
  unique tables during repeat live runs

### 15. Outreach queue operator-state preservation

- Updated `NotionService` so repeat live runs no longer overwrite manually
  reviewed `Outreach Queue` rows in these statuses:
  - `Approved`
  - `Sent`
  - `Hold`
- Added regenerate handling so rows marked `Regenerate` are refreshed on the
  next run and returned to `Ready to send`
- Added mocked tests for the outreach queue preservation and regenerate paths

### 16. Outcome feedback loop for discovery and scoring

- Added `LeadFeedbackSignal` and `LeadFeedbackAgent`
- Added Notion feedback reads from:
  - `Outreach Queue`
  - `Pipeline`
- Updated `LeadDiscoveryAgent` so duplicate leads with existing operator or
  pipeline activity are downgraded from `promote` to `review`
- Updated `LeadScoringAgent` so existing activity can apply a small scoring
  penalty and surface a feedback summary to operators
- Updated `main.py` so the daily run collects feedback before discovery
  promotion and scoring
- Added mocked tests for:
  - feedback index merging
  - discovery suppression from existing activity
  - scoring penalties from existing activity
  - Notion feedback signal parsing

### 17. Outreach review sync back into pipeline state

- Added `OutreachReviewAgent` to reconcile manual `Outreach Queue` decisions
  into live pipeline state before each live run
- Updated `main.py` so live runs now:
  - sync `Approved` rows back into pipeline with `outreach_status=approved`
  - sync `Sent` rows back into pipeline with `outreach_status=sent` and
    advance them through pipeline intelligence
  - sync `Hold` rows back into pipeline with `next_action=operator_hold`
- Hardened the sync logic so stale queue statuses do not downgrade a more
  advanced pipeline record
- Added regression coverage for:
  - approved queue sync
  - sent queue sync
  - hold queue sync
  - stale queue status suppression
  - live-only review sync ordering in `main.py`

### 18. Schema-safe Supabase lead persistence

- Updated `SupabaseService` to exclude transient operator-only lead fields from
  Supabase payloads
- Prevented `feedback_summary` from being sent to the `leads` table, avoiding
  runtime schema-cache errors during live runs
- Added regression coverage for table-aware lead serialization

### 19. Local operator console frontend

- Added a lightweight local operator console over the existing Notion-backed
  workflow
- Added `OperatorConsoleService` plus structured console models for:
  - dashboard snapshot
  - outreach queue rows
  - sales engine run rows
- Extended `NotionService` with list and update methods for:
  - `Lead Discovery`
  - `Lead Intake`
  - `Outreach Queue`
  - `Sales Engine Runs`
- Added `run_operator_console.py` so the console can be launched directly from
  the repo
- Added regression coverage for:
  - console service delegation
  - WSGI console rendering
  - queue status updates through the console
  - Notion dashboard snapshot reads

### 20. Testing phase kickoff

- Updated the architecture and roadmap documents so they reflect the implemented
  end-to-end workflow rather than the earlier foundation state
- Added `TESTING_PHASE_PLAN.md` as the active shadow-pilot playbook
- Marked older transition notes as historical references so they do not compete
  with the current rollout guidance

## Current Build Position

- The deterministic commercial workflow is implemented end to end
- Supabase persistence is code-complete and mock-tested
- Notion operating sync is code-complete and mock-tested
- Lead discovery qualification and intake promotion are code-complete and
  mock-tested
- Feed-driven source collection into `Lead Discovery` is code-complete and
  mock-tested
- Real lead ingestion from Notion is code-complete and mock-tested
- Daily outreach packaging and run logging are code-complete and mock-tested
- Source-quality scoring, Workable support, and shadow-to-live run mode are now
  implemented and mock-tested
- Live reruns no longer fail on duplicate `pipeline_records` or
  `solution_recommendations` keyed by `lead_reference`
- Live reruns now preserve operator decisions in `Outreach Queue`
- Existing queue and pipeline outcomes now feed back into discovery promotion
  and lead scoring
- Manual `Outreach Queue` decisions now also sync back into live pipeline state
  on the next live run
- Lead persistence now strips transient operator-only fields before writing to
  Supabase
- The repo now includes a lightweight local operator frontend over the Notion
  operating workflow
- The repository now includes a runnable integration validation workflow for
  live Supabase and Notion environments
- The project has now entered controlled testing phase with a shadow-pilot
  playbook and documentation aligned to the implemented runtime
- The next major phase after a successful pilot should be scheduled execution,
  monitoring, operational automation, and later external CRM sync
