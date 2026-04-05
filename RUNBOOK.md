# Runbook

## Purpose

This runbook covers the practical operating commands and the most common situations during testing phase.

## Commands

### Run Shadow Mode

```powershell
$env:SALES_ENGINE_RUN_MODE='shadow'
$env:SALES_ENGINE_TRIGGERED_BY='manual'
.\venv\Scripts\python.exe main.py
```

### Start Operator Console

```powershell
python run_operator_console.py
```

### Run Tests

```powershell
pytest -q
```

## Common Situations

### No Discovery Candidates

Meaning:

- the active source set is too narrow
- the filters are too strict
- the manual lanes are empty

What to do:

- add entries to `Manual Strategic Accounts`
- add entries to `Market Intelligence`
- add entries to `Reactivation`
- review whether current feed sources are still useful

### Too Many Weak Candidates

Meaning:

- source set is too noisy
- watch keywords are too broad
- the lane is collecting activity that does not help sales

What to do:

- tighten watch keywords
- disable weak sources
- bias more rows into `review` or `reject`

### Same Lead Reappears

Meaning:

- there may be a stale `Lead Intake` row
- or a still-active discovery source is reproducing the same signal

What to do:

- archive or reject the stale intake row
- verify the source is still appropriate

### Discovery Rows Are Good But Outreach Is Weak

Meaning:

- sourcing is ahead of messaging quality

What to do:

- hold the queue item
- regenerate only after confirming the lead is valid
- refine the underlying commercial angle before approving

## Testing Phase Guidance

Use testing phase to answer:

- are the lanes producing useful discovery?
- are promoted rows credible?
- does the operator understand why each row exists?
- does the packaged output feel commercially usable?

Do not optimize for raw volume alone.
