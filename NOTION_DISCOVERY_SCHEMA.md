# Notion Discovery Schema

## Purpose

This database is the autonomous discovery queue for the sales engine.

`main.py` can now read ready discovery rows from `Lead Discovery`, qualify them
with Anthropic or deterministic fallback logic, and promote only stronger records
into `Lead Intake`.

## Required Properties

- `Company` -> `Title`

## Strongly Recommended Properties

- `Website URL` -> `URL`
- `Source URL` -> `URL`
- `Source Type` -> `Select` or `Text`
- `Agent Label` -> `Select` or `Text`
- `Lane Label` -> `Select` or `Text`
- `Evidence` -> `Text`
- `Contact` -> `Text`
- `Role` -> `Text`
- `Email` -> `Email`
- `LinkedIn URL` -> `URL`
- `Company Country` -> `Text`
- `Target Country Hint` -> `Select`
- `Campaign` -> `Text`
- `Notes` -> `Text`
- `Status` -> `Select` or `Status`

## Optional Tracking Properties

- `Confidence Score` -> `Number`
- `Buyer Confidence` -> `Number`
- `Account Fit Summary` -> `Text`
- `Qualification Summary` -> `Text`
- `Evidence Summary` -> `Text`
- `Lead Type` -> `Select`
- `Fit Reason` -> `Text`
- `Lead Reference` -> `Text`
- `Processed At` -> `Date`
- `Last Error` -> `Text`

## Supported Status Values

Rows are processed when `Status` is one of:

- `new`
- `approved`
- `ready`

Rows are skipped when `Status` is one of:

- `promoted`
- `review`
- `rejected`
- `error`
- `done`
- `archived`

If a row is marked as `error`, fix the source row and move it back to `ready`
when you want the engine to retry it.

## Qualification Outcomes

The engine classifies each discovery row into one of:

- `promote`
  The evidence is strong enough to auto-upsert the record into `Lead Intake`.
- `review`
  The evidence is interesting but not strong enough for automatic promotion.
- `reject`
  The evidence is too weak or off-target for the current sales motion.

If your Notion `Status` property uses human-readable capitalization such as
`Promoted` or `Ready`, the service maps those labels automatically.

## Recommended Operating Flow

1. Maintain the watched sources in `discovery_sources.json` when using the
   automated source collector.
2. Add any extra source-backed rows manually to `Lead Discovery` when needed.
3. Set `Status` to `ready` when a row can be qualified.
4. Run `python main.py`.
5. Review:
   - promoted rows in `Lead Discovery`
   - newly prepared rows in `Lead Intake`
   - send-ready drafts in `Outreach Queue`
   - run health in `Sales Engine Runs`

## Anthropic Behavior

When `ANTHROPIC_API_KEY` is configured, the engine uses the Anthropic Messages API to
qualify discovery evidence into:

- a normalized `Lead`
- an `evidence_summary`
- a `confidence_score`
- a `decision`

If Anthropic is unavailable or the qualification request fails, the engine falls
back to deterministic evidence scoring so the discovery layer still works.
