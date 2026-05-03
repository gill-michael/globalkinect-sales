-- schema_migrations is created automatically by runner.py; do not declare here.

CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- usually pre-enabled on Supabase; CREATE EXTENSION IF NOT EXISTS is safe either way

CREATE TABLE users (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email           text NOT NULL,
    full_name       text,
    role            text NOT NULL CHECK (role IN ('admin','sdr','manager','viewer')),
    active          boolean NOT NULL DEFAULT true,
    sso_subject     text,
    created_at      timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    last_login_at   timestamptz
);
CREATE UNIQUE INDEX users_email_lower_idx ON users (lower(email));
CREATE UNIQUE INDEX users_sso_subject_idx ON users (sso_subject) WHERE sso_subject IS NOT NULL;

CREATE TABLE pipelines (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    slug            text NOT NULL UNIQUE,
    stages          jsonb NOT NULL,
    active          boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
