-- schema_migrations is created automatically by runner.py; do not declare here.
-- pgcrypto loaded in 0001; gen_random_uuid() available.
-- No set_updated_at triggers on these tables this week (per spec Task 5);
-- sequences and assets are largely immutable, status changes via separate columns.

CREATE TABLE assets (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id      uuid NOT NULL REFERENCES contacts(id) ON DELETE RESTRICT,
    type            text NOT NULL CHECK (type IN (
        'research_report','email','sequence','call_script','linkedin_message'
    )),
    storage_path    text NOT NULL,
    content_summary text,
    generated_by    text,
    generated_at    timestamptz,
    metadata        jsonb
);

CREATE INDEX assets_contact_id_idx ON assets (contact_id);

CREATE TABLE sequences (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    contact_id   uuid NOT NULL REFERENCES contacts(id) ON DELETE RESTRICT,
    deal_id      uuid REFERENCES deals(id) ON DELETE SET NULL,
    template     text NOT NULL,
    status       text NOT NULL,
    started_at   timestamptz,
    paused_at    timestamptz,
    completed_at timestamptz
);

CREATE INDEX sequences_contact_id_idx ON sequences (contact_id);
CREATE INDEX sequences_deal_id_idx ON sequences (deal_id);

CREATE TABLE sequence_steps (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    sequence_id   uuid NOT NULL REFERENCES sequences(id) ON DELETE CASCADE,
    step_number   int NOT NULL,
    channel       text,
    scheduled_for timestamptz,
    status        text,
    asset_id      uuid REFERENCES assets(id) ON DELETE SET NULL,
    completed_at  timestamptz,
    activity_id   uuid REFERENCES activities(id) ON DELETE SET NULL,
    UNIQUE (sequence_id, step_number)
);
