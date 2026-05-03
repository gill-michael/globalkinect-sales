-- schema_migrations is created automatically by runner.py; do not declare here.
-- pgcrypto loaded in 0001; gen_random_uuid() available.

CREATE TABLE companies (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name            text NOT NULL,
    domain          text,
    country         text,
    employee_count  int,
    industry        text,
    hubspot_id      text UNIQUE,
    notion_id       text,
    company_role    text CHECK (company_role IN ('end_buyer','eor_provider','partner','competitor','unknown')),
    firmographic    jsonb,
    created_at      timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at      timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE TABLE contacts (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id        uuid REFERENCES companies(id) ON DELETE RESTRICT,
    first_name        text,
    last_name         text,
    full_name         text,
    email             text,
    mobile            text,
    linkedin_url      text,
    job_title         text,
    seniority         text,
    authority_score   int,
    hubspot_id        text UNIQUE,
    notion_id         text,
    source            text,
    source_metadata   jsonb,
    status            text NOT NULL DEFAULT 'new' CHECK (status IN ('new','enriched','researched','in_sequence','replied','meeting_booked','closed','dropped')),
    owner_id          uuid REFERENCES users(id) ON DELETE SET NULL,
    assigned_at       timestamptz,
    created_at        timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at        timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE UNIQUE INDEX contacts_email_lower_idx ON contacts (lower(email)) WHERE email IS NOT NULL;
CREATE INDEX contacts_company_id_idx ON contacts (company_id);
CREATE INDEX contacts_linkedin_url_idx ON contacts (linkedin_url);
CREATE INDEX contacts_owner_status_idx ON contacts (owner_id, status);

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now() AT TIME ZONE 'utc';
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER companies_set_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER contacts_set_updated_at
    BEFORE UPDATE ON contacts
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
