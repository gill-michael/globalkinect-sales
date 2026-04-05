# Notion Integration Ready Checklist

## Code Coverage

- `NotionService` exists and is environment-backed
- `NotionService` supports deterministic upsert methods for:
  - leads
  - pipeline records
  - solution recommendations
  - execution tasks
  - deal support packages
- `NotionSyncAgent` coordinates operating-view sync cleanly
- `main.py` triggers Notion sync after Supabase persistence

## Environment

- `NOTION_API_KEY` present in `.env`
- `NOTION_LEADS_DATABASE_ID` present in `.env`
- `NOTION_PIPELINE_DATABASE_ID` present in `.env`
- `NOTION_SOLUTIONS_DATABASE_ID` present in `.env`
- `NOTION_TASKS_DATABASE_ID` present in `.env`
- `NOTION_DEAL_SUPPORT_DATABASE_ID` present in `.env`

## Expected Operating Views

- leads intake / review
- pipeline board
- solution recommendations
- execution task queue
- deal support / proposal prep

## Mapping Readiness

- leads view uses a deterministic lead reference as the page title
- pipeline board includes stage, outreach status, next action, priority, sales motion, module, bundle, high-value flag, and last updated
- solution pages carry sales motion, primary module, bundle label, recommended modules, commercial strategy, and rationale
- execution task pages carry task type, description, priority, due timing, and status
- deal support pages carry stage, recap subject, proposal summary, next steps, and objection handling

## Safety And Validation

- service logs and skips cleanly when Notion is not configured
- page sync uses upsert-style query-then-create-or-update behavior
- tests use mocks only and do not require a live Notion workspace

## Remaining Live Step

- connect the real Notion integration and validate the target databases and property names
