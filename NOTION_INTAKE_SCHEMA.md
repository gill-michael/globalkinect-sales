# Notion Intake Schema

## Purpose

This database is the real lead-ingestion entry point for the sales engine.

`main.py` now prefers this intake database over mock leads when
`NOTION_INTAKE_DATABASE_ID` is configured.

The engine reads a small batch of ready rows, normalizes them into the internal
`Lead` model, and then marks the intake rows as processed.

## Required Properties

- `Company` -> `Title`

## Strongly Recommended Properties

- `Contact` -> `Text`
- `Role` -> `Text`
- `Lane Label` -> `Select` or `Text`
- `Email` -> `Email`
- `LinkedIn URL` -> `URL`
- `Company Country` -> `Text`
- `Target Country` -> `Select`
- `Buyer Confidence` -> `Number`
- `Account Fit Summary` -> `Text`
- `Lead Type Hint` -> `Select`
- `Campaign` -> `Text`
- `Notes` -> `Text`
- `Status` -> `Select` or `Status`

## Optional Tracking Properties

- `Lead Reference` -> `Text`
- `Fit Reason` -> `Text`
- `Processed At` -> `Date`
- `Last Error` -> `Text`

## Supported Status Values

Rows are processed when `Status` is one of:

- `new`
- `approved`
- `ready`

Rows are skipped when `Status` is one of:

- `ingested`
- `archived`
- `rejected`
- `done`
- `error`

If a row is marked as `error`, fix the source row and move it back to `ready`
when you want the engine to retry it.

## Recommended Operating Flow

1. Add raw lead rows to the intake database.
2. Set `Status` to `ready` when a row can be processed.
3. Run `python main.py`.
4. Review the normalized output in the intake database tracking fields and the
operating databases already synced by the engine.

## OpenAI Behavior

When `OPENAI_API_KEY` is configured, the engine uses the OpenAI Responses API to
normalize the raw intake row into the internal `Lead` structure.

If OpenAI is unavailable or the normalization request fails, the engine falls
back to a direct deterministic mapping from the intake row so the pipeline can
still run.
