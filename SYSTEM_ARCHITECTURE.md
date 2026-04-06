# System Architecture

## Current State

GlobalKinect Sales Engine is a deterministic internal sales-operations engine
for discovering, qualifying, shaping, and progressing commercial opportunities
for a modular employment platform.

The current implementation is no longer a foundation-only prototype. It
supports a full discovery-first workflow with:

- source-backed lead discovery
- Notion-backed lead intake
- deterministic scoring and prioritization
- solution-led commercial design
- outreach packaging for operator review
- pipeline and execution-task generation
- Supabase persistence
- Notion operating sync
- local operator review through a lightweight console

`SolutionRecommendation` is the commercial source of truth for sales motion,
primary module, bundle label, and recommended modules.

## Application Structure

### `app/agents`

This package holds the workflow agents that transform commercial inputs into
reviewable outputs.

Current active agents include:

- `DiscoverySourceCollectorAgent`
- `LeadDiscoveryAgent`
- `LeadFeedbackAgent`
- `OutreachReviewAgent`
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

Design role:

- keep responsibilities bounded and testable
- emit structured outputs rather than free-form workflow state
- support a deterministic, auditable commercial path

### `app/services`

This package isolates external systems, configuration, and low-level operating
adapters.

Current services include:

- `config.py` for environment-backed settings
- `anthropic_service.py` for structured qualification and normalization helpers
- `notion_service.py` for intake, discovery, outreach queue, and operating-view
  sync
- `supabase_service.py` for persistence of core commercial entities
- `discovery_source_service.py` for local watchlist-driven source collection
- `operator_console_service.py` for the local operator-facing workflow surface

Design role:

- keep transport and persistence details out of agent logic
- make external dependencies replaceable
- keep business flow readable in orchestration code

### `app/models`

This package defines the shared domain contracts used across the workflow.

Key models include:

- `Lead`
- `LeadDiscoveryRecord`
- `LeadIntakeRecord`
- `LeadFeedbackSignal`
- `SolutionRecommendation`
- `OutreachMessage`
- `OutreachQueueItem`
- `PipelineRecord`
- `ExecutionTask`
- `DealSupportPackage`
- `SalesEngineRun`

Design role:

- standardize data exchanged across agents and services
- keep commercial assumptions explicit
- reduce hidden state and integration-specific coupling

### `app/orchestrators`

This package now contains cross-workflow validation logic.

Current state:

- `integration_check.py` runs a safe end-to-end validation flow for Supabase
  and Notion

Planned role:

- keep broader multi-step orchestration support outside individual agents
- centralize validation and future operational coordination flows

### `app/web`

This package contains the local operator console surface used to review the
Notion-backed workflow.

Current state:

- `operator_console.py` exposes the lightweight local review UI

### `app/utils`

This package contains shared support code such as:

- structured logging
- target-market helpers
- UTC time helpers

## Runtime Modes

The application supports two operating modes:

1. `shadow`
   Runs discovery, qualification, scoring, solution design, and outreach
   packaging without mutating live persistence or operator views.
2. `live`
   Runs the full workflow, including live queue reconciliation, Supabase
   persistence, Notion operating sync, and run logging when configured.

## Runtime Shape

The current entry point is `main.py`.

At runtime it:

1. initializes services and agents
2. records a run marker
3. syncs prior operator queue decisions back into live pipeline state on live
   runs
4. collects feedback from existing queue and pipeline activity
5. pulls watched-source evidence into `Lead Discovery` when configured
6. qualifies discovery rows and promotes stronger entries into `Lead Intake`
7. collects intake leads, preferring Notion-backed inputs over mock leads
8. scores leads deterministically
9. creates `SolutionRecommendation` records
10. creates pipeline records and outreach messages
11. evaluates pipeline intelligence and lifecycle state
12. generates execution tasks and deal-support packages
13. persists and syncs operating views on live runs
14. logs the run result and prints concise review output

## Control Principles

- human approval remains in place before outbound action
- business logic stays deterministic and testable
- `SolutionRecommendation` is the commercial source of truth
- external systems are accessed through `app/services`
- the system should be validated in `shadow` mode before scheduled live rollout

## Current Objective

As of March 23, 2026, the repository is in testing phase.

The immediate objective is to validate:

- discovery signal quality
- operator trust in promoted leads and packaged outreach
- integration stability across Notion and Supabase
- readiness for a narrow live rollout after a controlled shadow pilot
