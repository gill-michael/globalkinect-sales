# Operator Guide

## Purpose

This guide explains how to operate the GlobalKinect sales engine during testing phase.

The system is built to collect wide sourcing signals, qualify them into reviewable discovery, and only package outreach after a human operator has confidence in the commercial case.

## Daily Workflow

1. Run the engine in `shadow` mode.
2. Review `Lead Discovery`.
3. Review `Lead Intake`.
4. Review `Outreach Queue`.
5. Review `Sales Engine Runs`.
6. Adjust sources, manual lanes, or statuses based on what you learned.

## Start The Operator Console

```powershell
python run_operator_console.py
```

## Run A Shadow Cycle

```powershell
$env:SALES_ENGINE_RUN_MODE='shadow'
$env:SALES_ENGINE_TRIGGERED_BY='manual'
.\venv\Scripts\python.exe main.py
```

Use `shadow` mode for evaluation. It runs sourcing, qualification, scoring, and packaging logic without live Supabase persistence or live outreach-queue sync.

## What To Review

### `Lead Discovery`

This is the main operator work queue.

Review each row for:

- why this company
- why now
- likely buyer or buyer team
- product angle: `EOR`, `Payroll`, `HRIS`, or bundle
- whether the evidence is strong enough to move forward

Expected actions:

- keep in `Review` when interesting but not ready
- mark `Rejected` when weak or off-target
- allow `Promoted` only when the commercial case is credible

You may now also see discovery rows created by internal autonomous lanes such as:

- `Buyer Mapping`
- `Reactivation`

Treat these as internal follow-up work, not as raw external-source evidence.

### `Lead Intake`

This should contain only normalized leads that are ready for downstream packaging.

If a row is still weak, buyerless, or ambiguous, it should not stay in `ready`.

### `Outreach Queue`

This is not an automatic send queue. It is an operator approval queue.

Use it to:

- approve strong drafts
- hold weak but potentially valid rows
- regenerate drafts if the lead is sound but the copy is weak
- mark sent only after real execution

### `Sales Engine Runs`

Use this to verify:

- the run completed
- how many candidates were collected
- how many discovery rows were created
- how many were promoted, reviewed, or rejected
- whether any failures occurred

## What Good Looks Like

Good discovery output is:

- commercially intelligible
- tied to a target market
- tied to a plausible buyer
- useful enough that an operator can explain the lead quickly

Good outreach output is:

- specific
- relevant to the market and motion
- tied to a believable operational need

## What Bad Looks Like

Bad discovery output is:

- generic job noise
- no buyer
- no trigger event
- no clear product angle
- too vague to justify outreach

Bad outreach output is:

- generic copy
- no evidence-backed angle
- unknown contact and unknown role
- unclear module recommendation

## Current Working Rule

The current system is intentionally stricter than before.

Rows should stay in `review` unless:

- buyer readiness is credible
- the commercial trigger is real
- the lead is useful enough to act on

## Related Documents

- [SOURCING_STRATEGY.md](/c:/dev/globalkinect-engines/sales/SOURCING_STRATEGY.md)
- [SOURCING_AGENTS.md](/c:/dev/globalkinect-engines/sales/SOURCING_AGENTS.md)
- [SOURCING_LANES.md](/c:/dev/globalkinect-engines/sales/SOURCING_LANES.md)
- [TESTING_PHASE_PLAN.md](/c:/dev/globalkinect-engines/sales/TESTING_PHASE_PLAN.md)
