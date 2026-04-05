# Database Migrations

## Overview

This repository uses forward-only SQL migrations for Supabase Postgres.

The workflow is intentionally simple:

- SQL files live in `migrations/`
- `migrations/run_migrations.py` applies all pending migrations in filename order
- `migrations/create_migration.py` creates the next numbered SQL migration file

The migration runner reads the connection string only from `DATABASE_URL`.

## Environment

Set `DATABASE_URL` in `.env` to a direct Postgres connection string for your Supabase project.

Example shape only:

```text
DATABASE_URL=postgresql://user:password@host:5432/postgres
```

Do not commit real credentials.

## Commands

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run all pending migrations:

```powershell
python migrations/run_migrations.py
```

Create a future migration:

```powershell
python migrations/create_migration.py add_new_table
```

## Operational Notes

- applied migrations are tracked in the `schema_migrations` table
- each applied migration stores a checksum
- if a historical migration file is edited after application, the runner raises an error
- rollback is intentionally not automated; create a compensating forward migration instead
- `pipeline_records.lead_reference` is unique because the current engine treats pipeline as one active record per lead reference
- `solution_recommendations.lead_reference` is unique for the same reason: one current commercial recommendation per lead reference
- `deal_support_packages` and `execution_tasks` are not unique on `lead_reference` because those tables can legitimately hold multiple records over time

## Current Schema

The initial migration creates:

- `leads`
- `outreach_messages`
- `solution_recommendations`
- `pipeline_records`
- `deal_support_packages`
- `execution_tasks`

It also adds the indexes needed by the current sales-engine workflow.
