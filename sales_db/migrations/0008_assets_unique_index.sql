-- schema_migrations is created automatically by runner.py; do not declare here.
-- Idempotency guard for reports_backfill — prevents duplicate asset rows
-- when the script is re-run against the same leads/Reports/<slug>/ folders.

CREATE UNIQUE INDEX assets_contact_type_path_idx
    ON assets (contact_id, type, storage_path);
