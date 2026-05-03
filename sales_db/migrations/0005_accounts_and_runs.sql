-- schema_migrations is created automatically by runner.py; do not declare here.
-- pgcrypto loaded in 0001; gen_random_uuid() available.
-- No set_updated_at triggers on these tables this week (per spec Task 6);
-- accounts may need one later when ownership changes are tracked.

CREATE TABLE accounts (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id       uuid NOT NULL REFERENCES companies(id) ON DELETE RESTRICT,
    account_owner_id uuid REFERENCES users(id) ON DELETE SET NULL,
    strategic_value  text,
    notes            text
);

CREATE TABLE runs (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    type         text NOT NULL,
    started_at   timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    completed_at timestamptz,
    status       text NOT NULL CHECK (status IN ('running','success','failed','partial')),
    metrics      jsonb,
    errors       jsonb
);

CREATE INDEX runs_type_started_idx ON runs (type, started_at DESC);

CREATE INDEX accounts_company_id_idx ON accounts (company_id);
CREATE INDEX accounts_owner_idx ON accounts (account_owner_id);
