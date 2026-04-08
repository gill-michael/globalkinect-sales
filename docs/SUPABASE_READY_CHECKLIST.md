# Supabase Ready Checklist

## Code Coverage

- `SupabaseService` implements inserts for:
  - `leads`
  - `outreach_messages`
  - `pipeline_records`
  - `solution_recommendations`
  - `deal_support_packages`
  - `execution_tasks`
- `SupabaseService` implements:
  - `update_pipeline_record(...)`
  - `upsert_pipeline_records(...)`
  - `fetch_leads(...)`
  - `fetch_pipeline_records(...)`
  - `fetch_execution_tasks(...)`

## Environment

- `SUPABASE_URL` present in `.env`
- `SUPABASE_PUBLISHABLE_KEY` present in `.env`

## Table Readiness

- expected table reference documented in `docs/SUPABASE_SCHEMA_REFERENCE.md`
- practical SQL reference available in `supabase_schema_reference.sql`
- pipeline records include solution-aligned commercial fields
- execution tasks persist cleanly with status and creation timestamp

## Safety And Validation

- service raises clear `RuntimeError` when not configured
- empty payloads are skipped safely
- serialization uses `model_dump()` consistently
- tests use mocks only and do not require a live Supabase instance

## Remaining Live Step

- connect real Supabase credentials and validate the referenced tables in the target project
