-- schema_migrations is created automatically by runner.py; do not declare here.
-- pgcrypto loaded in 0001; gen_random_uuid() available.

CREATE TABLE contact_suppressions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    hubspot_id      text UNIQUE,
    email           text,
    reason          text NOT NULL,
    suppressed_at   timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    suppressed_by   uuid REFERENCES users(id) ON DELETE SET NULL
);
CREATE INDEX contact_suppressions_email_lower_idx
    ON contact_suppressions (lower(email)) WHERE email IS NOT NULL;
