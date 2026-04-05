# Testing Phase Plan

## Status

- Phase start: March 23, 2026
- Operating mode: `shadow` first
- Phase objective: prove that the current workflow produces useful,
  operator-reviewable outputs before scheduled live rollout

## What This Phase Is For

This phase is not for adding broad new capability. It is for validating that
the implemented workflow is commercially usable:

- source collection produces relevant candidates
- discovery qualification promotes the right leads into intake
- scoring and solution design produce sensible commercial outputs
- outreach drafts are good enough for operator review
- Notion and Supabase integrations behave predictably

## In Scope

- discovery source collection
- discovery qualification and intake promotion
- lead normalization and scoring
- solution recommendation generation
- outreach packaging and queue review
- run logging
- integration validation
- operator feedback and tuning

## Out Of Scope

- external CRM sync
- autonomous sending
- broad source expansion before the pilot is stable
- major feature work unless it fixes a blocker found during testing

## Preconditions

Before day 1 of the pilot:

1. Confirm the environment matches [.env.example](/c:/dev/globalkinect-engines/sales/.env.example).
2. Confirm the Notion databases match the schema docs used by the workflow.
3. Confirm the Supabase tables exist for the expected entities.
4. Run:

```powershell
pytest -q
python run_integration_check.py --run-marker testing_phase_baseline
```

5. Start with a narrow, high-trust source list based on
   [discovery_sources.example.json](/c:/dev/globalkinect-engines/sales/discovery_sources.example.json).

## Daily Testing Loop

Run this cycle for 5-7 days before any live cutover.

1. Set the engine to `shadow` mode:

```powershell
$env:SALES_ENGINE_RUN_MODE='shadow'
$env:SALES_ENGINE_TRIGGERED_BY='manual'
```

2. Execute the daily engine:

```powershell
python main.py
```

3. Open the operator console when needed:

```powershell
python run_operator_console.py
```

4. Review four operating surfaces:
   - `Lead Discovery`
   - `Lead Intake`
   - `Outreach Queue`
   - `Sales Engine Runs`
5. Capture counts, false positives, and operator comments for the run.
6. Tune only:
   - watched sources
   - `trust_score`
   - `source_priority`
   - qualification thresholds and evidence handling

## Metrics To Track

- discovery candidates collected
- discovery rows promoted to intake
- rows kept in `review`
- rows rejected
- duplicate suppressions from existing activity
- leads scored and packaged
- queue items considered send-worthy
- operator approval, hold, and regenerate patterns
- obvious false positives
- runs with sync or processing failures

## Go/No-Go Criteria

Move from `shadow` to `live` only if all of these are true:

- the pilot produces consistent useful leads across multiple days
- duplicate and low-signal promotions are at an acceptable level
- operators trust the outreach drafts with limited rewriting
- no unresolved integration or run-log failures remain
- the integration check succeeds for the active environment

If those conditions are not met, keep the engine in `shadow` mode and continue
tuning the source list and qualification rules.

## Issue Handling

Classify pilot issues into these buckets:

- `blocker`
- `integration`
- `data-quality`
- `messaging-quality`
- `documentation`
- `operator-workflow`

Treat blockers and integration failures as same-day work. Treat data-quality and
messaging issues as tuning work unless they create unsafe output.

## Exit Deliverables

At the end of testing phase, produce:

1. a short shadow-pilot summary
2. an updated source strategy
3. a go/no-go decision for narrow live rollout
4. a follow-up plan for scheduling and monitoring if live rollout is approved
