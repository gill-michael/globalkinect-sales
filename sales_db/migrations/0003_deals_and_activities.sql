-- schema_migrations is created automatically by runner.py; do not declare here.
-- pgcrypto loaded in 0001; gen_random_uuid() available.
-- set_updated_at() function loaded in 0002; reused for the deals trigger here.

CREATE TABLE deals (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id      uuid NOT NULL REFERENCES contacts(id) ON DELETE RESTRICT,
    company_id      uuid REFERENCES companies(id) ON DELETE RESTRICT,
    pipeline_id     uuid NOT NULL REFERENCES pipelines(id) ON DELETE RESTRICT,
    stage           text NOT NULL,
    motion_subtype  text CHECK (motion_subtype IS NULL OR motion_subtype IN ('volume','curated')),
    amount_estimate numeric,
    probability     int,
    expected_close  date,
    hubspot_id      text UNIQUE,
    owner_id        uuid REFERENCES users(id) ON DELETE SET NULL,
    created_at      timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at      timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    closed_at       timestamptz,
    won             boolean NOT NULL DEFAULT false,
    loss_reason     text
);

CREATE INDEX deals_owner_stage_idx ON deals (owner_id, stage);
CREATE INDEX deals_pipeline_stage_idx ON deals (pipeline_id, stage);

CREATE TABLE activities (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id          uuid NOT NULL REFERENCES contacts(id) ON DELETE RESTRICT,
    deal_id             uuid REFERENCES deals(id) ON DELETE SET NULL,
    type                text NOT NULL CHECK (type IN (
        'email_sent','email_opened','email_replied','email_bounced',
        'call_made','call_connected','call_voicemail',
        'linkedin_sent','linkedin_replied',
        'meeting_booked','note','stage_change','assignment_change'
    )),
    direction           text,
    channel             text,
    payload             jsonb,
    performed_by        uuid REFERENCES users(id) ON DELETE SET NULL,
    performed_by_system text,
    external_id         text,
    occurred_at         timestamptz,
    created_at          timestamptz NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE INDEX activities_contact_occurred_idx ON activities (contact_id, occurred_at DESC);
CREATE INDEX activities_deal_occurred_idx ON activities (deal_id, occurred_at DESC);
CREATE INDEX activities_performed_by_occurred_idx ON activities (performed_by, occurred_at DESC);

CREATE TRIGGER deals_set_updated_at
    BEFORE UPDATE ON deals
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
