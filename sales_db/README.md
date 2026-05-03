# sales_db

Schema migrations and connection helpers for the isolated sales Supabase
project — the canonical state for the new sales engine. Separate from the
existing platform / dashboard Supabase projects.

## Run migrations

From the repo root:

```powershell
python -m sales_db.runner
```

Reads `SALES_DATABASE_URL` from `.env`. Idempotent — re-running skips
already-applied migrations. The first run creates the `schema_migrations`
tracking table even if no migration files exist yet.

Migration files live in `sales_db/migrations/` and are named
`NNNN_description.sql` (four-digit sequence, lowercased description).
Files are applied in lexicographic order, each wrapped in its own
transaction.

The runner records the SHA-256 checksum of every applied migration in
`schema_migrations`. Editing an applied migration raises a checksum
mismatch error — create a new migration file instead.

## Connection helpers

`sales_db.connection`:

- `get_connection()` — psycopg v3 connection to `SALES_DATABASE_URL`,
  `autocommit=False`. Caller is responsible for committing or wrapping
  work in `with conn.transaction():`.
- `get_supabase_client()` — `supabase-py` client stub for future use,
  reads `SALES_SUPABASE_URL` and `SALES_SUPABASE_PUBLISHABLE_KEY`. Not
  exercised by week-1 code paths.
