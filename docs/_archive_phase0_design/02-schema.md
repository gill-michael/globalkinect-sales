# Database Schema Specification

**Project:** Global Kinect Sales Intelligence
**Database:** PostgreSQL 16 on Google Cloud SQL (separate instance from platform)
**Migration tool:** Alembic
**Last updated:** April 2026

---

## Reading this document

This is the canonical schema. Every design decision has two parts: the DDL, and a commentary explaining *why* each column exists and which data capture requirement (from the vision doc) it satisfies. When Claude Code implements this, both parts matter — the commentary prevents "clean up" deletions of columns that look unused but exist to serve year-2 agent requirements.

Tables are grouped into five layers:

- **L1 — Lead domain** (what we prospect)
- **L2 — Generation provenance** (every AI artefact we produce)
- **L3 — Activity & outcomes** (what happens after we hand off to HubSpot)
- **L4 — Operations** (pipeline runs, suppression, team)
- **L5 — Agent layer** (reports, recommendations, feedback)

Every table includes `created_at`, `updated_at` (trigger-maintained), and a UUID primary key unless otherwise noted. Foreign keys are always `ON DELETE RESTRICT` unless soft-delete makes sense (noted where).

---

## Layer 1: Lead domain

### `segments`

The universe of ICP segments we run. Seeded from config but editable.

```sql
CREATE TABLE segments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,          -- 'cfo-mid-market', 'owner-smb-contractor'
    name            TEXT NOT NULL,                  -- human-readable
    description     TEXT,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    rubric_name     TEXT NOT NULL,                  -- 'cfo-first-v1', 'owner-first-v1'
    target_per_week INTEGER NOT NULL DEFAULT 0,     -- Michael adjusts via admin app
    vibe_filter     JSONB NOT NULL,                 -- the exact Vibe API filter blob
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX segments_active ON segments (is_active) WHERE is_active;
```

**Why each column:**
- `rubric_name` references code-side scoring implementations; allows rubric evolution without schema changes
- `target_per_week` is the concrete segment mix — sum across active segments should approximate 50 initially
- `vibe_filter` stored as JSONB so the pipeline reads it and passes directly to the Vibe adapter; versioning is by row history, not separate filter_versions table (KISS until we need otherwise)

**Initial rows:** seeded via migration with `cfo-mid-market` (rubric `cfo-first-v1`, target 30) and `owner-smb-contractor` (rubric `owner-first-v1`, target 20).

---

### `leads`

The core record. One row per prospect. Uniqueness by (email) OR (linkedin_url) OR (company_domain + full_name) — the composite rules are enforced in application code because Postgres can't express "any of these three" as a single UNIQUE constraint cleanly.

```sql
CREATE TABLE leads (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Provenance
    segment_id              UUID NOT NULL REFERENCES segments(id),
    pipeline_run_id         UUID NOT NULL REFERENCES pipeline_runs(id),
    vibe_prospect_id        TEXT,                       -- Explorium's ID, for future re-enrichment
    vibe_business_id        TEXT,
    vibe_dataset_id         TEXT,                       -- which Vibe dataset this came from
    control_stream          BOOLEAN NOT NULL DEFAULT FALSE,  -- the 20% segment-blind sample

    -- Identity
    full_name               TEXT NOT NULL,
    first_name              TEXT,
    last_name               TEXT,
    linkedin_url            TEXT,                       -- normalised: always starts with 'https://linkedin.com/in/'

    -- Role
    job_title_raw           TEXT NOT NULL,              -- exact string from Vibe
    job_title_normalised    TEXT,                       -- cleaned for rubric matching
    role_bucket             TEXT NOT NULL,              -- rubric output: 'CFO / Finance Director' etc
    role_score              INTEGER NOT NULL,

    -- Company
    company_name            TEXT NOT NULL,
    company_domain          TEXT,                       -- normalised: no 'www.', lowercased
    company_linkedin        TEXT,
    company_country         TEXT NOT NULL,              -- ISO Alpha-2 of HQ
    company_size_band       TEXT,                       -- '51-200' etc as reported by Vibe
    company_industry        TEXT,                       -- from Vibe NAICS

    -- Prospect location (may differ from company country — expat CFOs)
    prospect_country        TEXT,
    prospect_city           TEXT,

    -- Contact details
    email                   TEXT,
    email_status            TEXT,                       -- 'valid', 'catch-all', 'unverified'
    phone                   TEXT,                       -- E.164 format
    phone_type              TEXT,                       -- 'mobile', 'landline', 'unknown'

    -- Scoring
    rubric_version          TEXT NOT NULL,              -- 'cfo-first-v1' at time of scoring
    total_score             INTEGER NOT NULL,
    score_breakdown         JSONB NOT NULL,             -- full bucket-by-bucket detail

    -- Lifecycle
    status                  TEXT NOT NULL DEFAULT 'new',  -- 'new', 'pushed-to-hubspot', 'in-progress', 'closed', 'suppressed'
    hubspot_contact_id      TEXT,                       -- populated after push
    hubspot_deal_id         TEXT,                       -- populated after deal created

    -- Housekeeping
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX leads_email ON leads (LOWER(email)) WHERE email IS NOT NULL;
CREATE INDEX leads_linkedin ON leads (linkedin_url) WHERE linkedin_url IS NOT NULL;
CREATE INDEX leads_company_person ON leads (LOWER(company_domain), LOWER(full_name));
CREATE INDEX leads_segment ON leads (segment_id);
CREATE INDEX leads_status ON leads (status);
CREATE INDEX leads_score ON leads (total_score DESC);
CREATE INDEX leads_hubspot_contact ON leads (hubspot_contact_id) WHERE hubspot_contact_id IS NOT NULL;
CREATE INDEX leads_control ON leads (control_stream) WHERE control_stream;
```

**Why each column:**
- Denormalised on purpose — leads are the central query surface; normalising company into its own table adds joins for tiny benefit at 50 leads/week
- `control_stream` column exists from day one (per vision doc principle 3) even though it's not used until agents come online in month 3. Adding it later would require a backfill we can't do accurately
- `rubric_version` alongside `score_breakdown` JSONB means we can change rubric logic without losing the ability to interpret old scores
- `job_title_raw` vs `job_title_normalised` separation matters because the raw string is training data; the normalised is for matching
- `email_status` captures the Vibe enrichment signal even though Vibe's current CSV export drops it — we query it from the enrichment response directly

**Dedupe rule (enforced in Python, not SQL):**
On new lead insertion, reject if any of the following match an existing row:
1. `LOWER(email)` matches (when both have email)
2. `linkedin_url` matches exactly
3. `LOWER(company_domain) AND LOWER(full_name)` both match

Dedupe lookups query across the life of the database, not just current pipeline run.

---

## Layer 2: Generation provenance

This is where year-two training data is made or broken. Every AI-produced artefact lives here with full context.

### `prompt_versions`

Immutable record of every prompt template we've used. Never updated, never deleted.

```sql
CREATE TABLE prompt_versions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind            TEXT NOT NULL,                  -- 'research', 'email_sequence', 'phone_script', 'agent_strategist'
    version         TEXT NOT NULL,                  -- semver-ish: 'research-v1.2.0'
    template_hash   TEXT NOT NULL UNIQUE,           -- SHA256 of template text
    template_text   TEXT NOT NULL,                  -- the literal prompt template (with placeholders)
    model_name      TEXT NOT NULL,                  -- 'claude-opus-4-7', 'sonar-deep-research'
    model_params    JSONB NOT NULL DEFAULT '{}',    -- temperature, max_tokens, etc
    notes           TEXT,
    retired_at      TIMESTAMPTZ,                    -- set when we stop using this version (soft retirement)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX prompt_versions_kind_version ON prompt_versions (kind, version);
CREATE INDEX prompt_versions_active ON prompt_versions (kind) WHERE retired_at IS NULL;
```

**Why each column:**
- `template_hash` enables "have we seen exactly this prompt before" checks without string comparison
- `retired_at` rather than deletion — retired prompts stay as training context for historical events
- Every generation event references this table; without it, a month-9 audit can't reconstruct what the model was told

---

### `generation_events`

Every time we call an AI model to produce artefact, we log it here. This is the core feature→outcome table.

```sql
CREATE TABLE generation_events (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What was generated
    lead_id             UUID NOT NULL REFERENCES leads(id),
    kind                TEXT NOT NULL,                  -- 'research', 'email_draft', 'phone_script'
    sequence_position   INTEGER,                        -- for email_draft: 1 = first touch, 2 = day 3 follow-up, etc. NULL for research/script

    -- Prompt used
    prompt_version_id   UUID NOT NULL REFERENCES prompt_versions(id),
    prompt_rendered     TEXT NOT NULL,                  -- the template with variables filled in, exactly as sent to the model
    prompt_hash         TEXT NOT NULL,                  -- SHA256 of prompt_rendered for fast duplicate detection

    -- Response
    output_raw          TEXT NOT NULL,                  -- the model's unedited output
    output_tokens       INTEGER,
    input_tokens        INTEGER,
    latency_ms          INTEGER,
    api_cost_usd        NUMERIC(10, 6),                 -- computed at time of generation

    -- Source tracking
    pipeline_run_id     UUID NOT NULL REFERENCES pipeline_runs(id),

    -- Metadata
    error               TEXT,                           -- populated if generation failed; output_raw is then empty
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX gen_events_lead ON generation_events (lead_id);
CREATE INDEX gen_events_kind ON generation_events (kind);
CREATE INDEX gen_events_prompt_version ON generation_events (prompt_version_id);
CREATE INDEX gen_events_pipeline_run ON generation_events (pipeline_run_id);
CREATE INDEX gen_events_hash ON generation_events (prompt_hash);
```

**Why each column:**
- `prompt_rendered` stored in full — yes this bloats the table, but the whole point of this table is training provenance. Compression at the Postgres level handles the storage cost
- `sequence_position` because an email sequence of 4 produces 4 rows here, and we need to know which was which
- `api_cost_usd` computed at time of generation using Anthropic's and Perplexity's public pricing; updated if pricing changes via backfill migration
- `error` column so failed generations still have rows; NULL output with error text lets us analyse failure modes

**Relationship to artefact tables below:** `generation_events` is the *provenance* layer. The actual content served to SDRs lives in `lead_research`, `lead_email_drafts`, `lead_phone_scripts` — each of those references back to its generation_event. This split exists so that regeneration (e.g., a new prompt version produces a better email) creates a new generation_event AND a new artefact row, keeping both available for comparison.

---

### `lead_research`

Perplexity-produced research report. One per lead (rare regenerations create a new row, old remains).

```sql
CREATE TABLE lead_research (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id                 UUID NOT NULL REFERENCES leads(id),
    generation_event_id     UUID NOT NULL REFERENCES generation_events(id),
    is_current              BOOLEAN NOT NULL DEFAULT TRUE,      -- only one is_current=TRUE per lead

    -- Content
    report_markdown         TEXT NOT NULL,
    citations_count         INTEGER,                            -- extracted from Perplexity output
    thin_flag               BOOLEAN NOT NULL DEFAULT FALSE,     -- heuristic: <3k chars OR 0 citations

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX lead_research_current ON lead_research (lead_id) WHERE is_current;
CREATE INDEX lead_research_lead ON lead_research (lead_id);
```

**Why each column:**
- `is_current` partial unique index enforces "one active per lead" without blocking history
- `thin_flag` for quickly filtering weak reports in the admin view — we've seen this happen (Bin Harmal Group report had 0 citations in Run 1)
- Regeneration workflow: insert new row with `is_current=TRUE`, update old row to `is_current=FALSE` (atomically, in a transaction)

---

### `lead_email_drafts`

Email sequence artefacts. 4 rows per lead initially (touches 1-4), plus any regenerations.

```sql
CREATE TABLE lead_email_drafts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id                 UUID NOT NULL REFERENCES leads(id),
    generation_event_id     UUID NOT NULL REFERENCES generation_events(id),
    sequence_position       INTEGER NOT NULL,                   -- 1, 2, 3, 4
    is_current              BOOLEAN NOT NULL DEFAULT TRUE,

    -- Content
    subject                 TEXT NOT NULL,
    body_markdown           TEXT NOT NULL,
    send_offset_days        INTEGER NOT NULL,                   -- 0 for first touch, 3 for day-3 follow-up, etc

    -- Push status to HubSpot
    hubspot_engagement_id   TEXT,                               -- set after we push as a draft engagement
    pushed_at               TIMESTAMPTZ,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX lead_email_drafts_current ON lead_email_drafts (lead_id, sequence_position) WHERE is_current;
CREATE INDEX lead_email_drafts_lead ON lead_email_drafts (lead_id);
CREATE INDEX lead_email_drafts_pushed ON lead_email_drafts (hubspot_engagement_id) WHERE hubspot_engagement_id IS NOT NULL;
```

**Why each column:**
- `sequence_position` + `is_current` composite ensures exactly one active version of touch-N per lead
- `send_offset_days` baked in at generation time (0, 3, 7, 14) — SDR can override when they send, but the suggested cadence lives here
- `hubspot_engagement_id` is the bridge between our storage and HubSpot's — when we push, we store HubSpot's returned ID so we can later correlate sent-content back to draft-content

---

### `lead_phone_scripts`

Phone outreach artefacts. One per lead (voicemail + opener typically bundled in same row).

```sql
CREATE TABLE lead_phone_scripts (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id                 UUID NOT NULL REFERENCES leads(id),
    generation_event_id     UUID NOT NULL REFERENCES generation_events(id),
    is_current              BOOLEAN NOT NULL DEFAULT TRUE,

    voicemail_markdown      TEXT,                   -- 30-second leave-a-message script
    opener_markdown         TEXT NOT NULL,          -- first 60 seconds to earn the meeting
    key_talking_points      JSONB NOT NULL DEFAULT '[]',   -- array of bullets; structured for UI display
    likely_objections       JSONB NOT NULL DEFAULT '[]',   -- array of {objection, response}

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX lead_phone_scripts_current ON lead_phone_scripts (lead_id) WHERE is_current;
CREATE INDEX lead_phone_scripts_lead ON lead_phone_scripts (lead_id);
```

**Why each column:**
- `voicemail_markdown` nullable because not all leads get a voicemail variant (e.g., if no phone number was enriched)
- `key_talking_points` and `likely_objections` as JSONB for structured UI rendering in the HubSpot extension — not just a blob of markdown

---

### `sdr_edits`

The capture of human modifications to AI-generated content. **This is gold dust for training.**

```sql
CREATE TABLE sdr_edits (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- What was edited
    artefact_kind           TEXT NOT NULL,                  -- 'email_draft', 'phone_script'
    artefact_id             UUID NOT NULL,                  -- FK into lead_email_drafts or lead_phone_scripts (polymorphic)
    lead_id                 UUID NOT NULL REFERENCES leads(id),

    -- Who
    sdr_user_id             UUID NOT NULL REFERENCES sales_users(id),

    -- What changed
    original_content        TEXT NOT NULL,                  -- the raw model output at time of edit
    edited_content          TEXT NOT NULL,                  -- what the SDR actually sent / saved
    edit_distance           INTEGER,                        -- Levenshtein distance, computed async
    change_summary          TEXT,                           -- optional: SDR's free-text note on why

    -- Outcome of their decision
    action                  TEXT NOT NULL,                  -- 'sent-as-is', 'edited-then-sent', 'discarded'
    edited_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX sdr_edits_lead ON sdr_edits (lead_id);
CREATE INDEX sdr_edits_artefact ON sdr_edits (artefact_kind, artefact_id);
CREATE INDEX sdr_edits_sdr ON sdr_edits (sdr_user_id);
CREATE INDEX sdr_edits_action ON sdr_edits (action);
```

**Why each column:**
- `original_content` captured at time of edit, not pulled from artefact table at query time. This protects against later regeneration making the comparison wrong
- `edit_distance` populated async (nightly job) because we don't want to block sends on Levenshtein computation for long texts
- `change_summary` is optional. We **will not** force SDRs to explain every edit — friction kills adoption. But we provide a field so a thoughtful SDR can say "changed opening because the reference to their recent hire was too specific and felt stalky"
- Action enum is critical for training: `discarded` is just as valuable a signal as `sent-as-is`

**Capture strategy:**
- `sent-as-is`: when HubSpot tells us via engagement API that the sent content matches the draft content we pushed
- `edited-then-sent`: when HubSpot engagement content differs from draft. We insert an sdr_edits row with both versions
- `discarded`: when the HubSpot draft engagement is deleted or never sent within 14 days. Background job sweeps for these

This row is inserted by a background sync job, not inline with SDR action. The SDR never sees this table or does anything to populate it. **Invisible instrumentation** is the goal.

---

## Layer 3: Activity & outcomes

HubSpot is source of truth. This layer is a local mirror for agent reasoning.

### `lead_activity`

Individual engagement events synced from HubSpot hourly.

```sql
CREATE TABLE lead_activity (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id                 UUID NOT NULL REFERENCES leads(id),

    -- What happened
    hubspot_engagement_id   TEXT NOT NULL UNIQUE,
    activity_type           TEXT NOT NULL,                  -- 'email_sent', 'email_opened', 'email_clicked', 'email_replied', 'meeting', 'call', 'note'
    direction               TEXT,                           -- 'outbound', 'inbound', NULL for non-communicative

    -- When
    occurred_at             TIMESTAMPTZ NOT NULL,           -- event time from HubSpot, NOT sync time

    -- Context (flexible)
    content_text            TEXT,                           -- email body, call notes, meeting notes — full content where available
    content_summary         TEXT,                           -- truncated for list views
    metadata                JSONB NOT NULL DEFAULT '{}',    -- subject, duration, recording URL (when compliant), etc

    -- Attribution
    sdr_user_id             UUID REFERENCES sales_users(id),
    related_draft_id        UUID REFERENCES lead_email_drafts(id),  -- if this email_sent corresponds to one of our drafts

    synced_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX lead_activity_lead ON lead_activity (lead_id);
CREATE INDEX lead_activity_occurred ON lead_activity (occurred_at DESC);
CREATE INDEX lead_activity_type ON lead_activity (activity_type);
CREATE INDEX lead_activity_draft ON lead_activity (related_draft_id) WHERE related_draft_id IS NOT NULL;
```

**Why each column:**
- `occurred_at` vs `synced_at` separation: if we run the sync job late, we still know when the event actually happened. Critical for time-to-reply analysis
- `related_draft_id` is populated by a matcher: find the most recent email_draft we pushed for this lead, same subject, sent within ±2 hours. This link powers the training feature→outcome join
- `content_text` captured in full when HubSpot permits — for replies, this is the most valuable training signal

---

### `lead_outcomes`

Deal stage transitions and final outcomes. One row per stage change (append-only log).

```sql
CREATE TABLE lead_outcomes (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id                 UUID NOT NULL REFERENCES leads(id),
    hubspot_deal_id         TEXT NOT NULL,

    -- State
    stage                   TEXT NOT NULL,                  -- HubSpot stage: 'New', 'Qualified', 'Demo Booked', etc
    stage_changed_at        TIMESTAMPTZ NOT NULL,
    is_current              BOOLEAN NOT NULL DEFAULT TRUE,  -- only latest is TRUE

    -- Closure data (populated when stage is closed-won or closed-lost)
    is_closed               BOOLEAN NOT NULL DEFAULT FALSE,
    is_won                  BOOLEAN NOT NULL DEFAULT FALSE,
    close_reason            TEXT,                           -- structured HubSpot close reason
    deal_amount_usd         NUMERIC(12, 2),

    synced_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX lead_outcomes_lead ON lead_outcomes (lead_id);
CREATE INDEX lead_outcomes_current ON lead_outcomes (lead_id) WHERE is_current;
CREATE INDEX lead_outcomes_closed ON lead_outcomes (is_closed, is_won) WHERE is_closed;
CREATE INDEX lead_outcomes_stage ON lead_outcomes (stage);
```

**Why each column:**
- Append-only log means we can reconstruct the deal journey: time in each stage, direction of movement, revivals from dead
- `is_current` partial index gives fast "what stage is each lead in right now"
- `close_reason` structured, not free text — we'll map to HubSpot's close-reason pick-list, editable via admin

---

### `reply_classifications`

Asynchronous enrichment of inbound email replies. Populated by a background job, not inline with sync.

```sql
CREATE TABLE reply_classifications (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    activity_id             UUID NOT NULL UNIQUE REFERENCES lead_activity(id),

    classification          TEXT NOT NULL,                  -- 'interested', 'not-interested', 'polite-defer', 'confused', 'angry', 'out-of-office', 'auto-responder'
    confidence              NUMERIC(3, 2),                  -- 0.00-1.00 from classifier model
    classifier_model        TEXT NOT NULL,                  -- which model classified (e.g. 'claude-haiku-4-5')
    classifier_version      TEXT NOT NULL,
    classified_at           TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- For active learning loop later
    human_override          TEXT,                           -- SDR can correct misclassification
    human_override_at       TIMESTAMPTZ,
    human_override_by       UUID REFERENCES sales_users(id)
);

CREATE INDEX reply_class_classification ON reply_classifications (classification);
```

**Why each column:**
- Cheap classifier (Haiku or similar) runs async to keep sync job fast
- `human_override` captures corrections without losing the original classification — this is the training data for fine-tuning a custom classifier in year 2
- Confidence score matters for agent reasoning: a 0.55-confidence "interested" vs a 0.98-confidence "interested" deserve different weights

---

## Layer 4: Operations

### `pipeline_runs`

Every execution of the weekly job. The audit trail.

```sql
CREATE TABLE pipeline_runs (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Timing
    started_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at             TIMESTAMPTZ,
    status                  TEXT NOT NULL DEFAULT 'running',  -- 'running', 'success', 'partial', 'failed'

    -- Config at time of run (captured for reproducibility)
    config_snapshot         JSONB NOT NULL,                 -- full segment mix, filters, target counts

    -- Results
    segments_run            JSONB NOT NULL DEFAULT '[]',    -- per-segment: planned, fetched, scored, pushed
    total_leads_added       INTEGER NOT NULL DEFAULT 0,
    total_leads_skipped     INTEGER NOT NULL DEFAULT 0,     -- duplicates, suppressions
    total_api_cost_usd      NUMERIC(10, 4),
    total_vibe_credits      INTEGER,

    -- Errors
    error_summary           TEXT,
    warnings                JSONB NOT NULL DEFAULT '[]',    -- array of structured warning objects

    -- Agent context
    strategist_report_id    UUID REFERENCES agent_reports(id)  -- which weekly brief informed this run's config
);

CREATE INDEX pipeline_runs_started ON pipeline_runs (started_at DESC);
CREATE INDEX pipeline_runs_status ON pipeline_runs (status);
```

**Why each column:**
- `config_snapshot` captures the *effective* config — Michael might have edited a segment mid-week; the run records what was true at start
- `strategist_report_id` creates the closed loop: in month 3+, Agent 1 writes a report, Michael approves a config, pipeline runs with that config. We can later audit "did Agent 1's recommendations lead to better outcomes?"
- `total_api_cost_usd` for budget monitoring

---

### `suppression_list`

Global do-not-contact list. Check before every insert.

```sql
CREATE TABLE suppression_list (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Suppression identifiers (any non-null is checked)
    email                   TEXT,
    email_domain            TEXT,                           -- suppresses @example.com entirely
    linkedin_url            TEXT,
    company_domain          TEXT,                           -- suppresses all contacts at a company

    -- Why
    reason                  TEXT NOT NULL,                  -- 'unsubscribe', 'bounce-hard', 'complaint', 'manual-block', 'pdpl-request'
    source                  TEXT NOT NULL,                  -- 'hubspot-unsubscribe', 'ses-bounce', 'sdr-manual', 'self-service-form'
    notes                   TEXT,

    suppressed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    suppressed_by           UUID REFERENCES sales_users(id), -- NULL for system-generated

    -- Time-bound suppressions (some are permanent, some for N days)
    expires_at              TIMESTAMPTZ                     -- NULL = permanent
);

CREATE INDEX suppression_email ON suppression_list (LOWER(email)) WHERE email IS NOT NULL;
CREATE INDEX suppression_email_domain ON suppression_list (LOWER(email_domain)) WHERE email_domain IS NOT NULL;
CREATE INDEX suppression_linkedin ON suppression_list (linkedin_url) WHERE linkedin_url IS NOT NULL;
CREATE INDEX suppression_company_domain ON suppression_list (LOWER(company_domain)) WHERE company_domain IS NOT NULL;
CREATE INDEX suppression_active ON suppression_list (expires_at) WHERE expires_at IS NULL OR expires_at > now();
```

**Why each column:**
- Four suppression levels (email, email_domain, linkedin, company_domain) cover different scenarios: one person vs a whole company vs a whole email provider
- `pdpl-request` as a reason so we can report on deletion compliance
- `expires_at` for soft suppression (e.g. "no contact for 90 days") vs permanent — GDPR/PDPL deletion requests are permanent

---

### `sales_users`

Your team. Synced from HubSpot owners.

```sql
CREATE TABLE sales_users (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    email                   TEXT NOT NULL UNIQUE,
    full_name               TEXT NOT NULL,
    hubspot_owner_id        TEXT UNIQUE,                    -- populated on first sync

    -- Role
    role                    TEXT NOT NULL DEFAULT 'sdr',    -- 'admin', 'manager', 'sdr'
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,

    -- Admin web app auth
    sso_provider            TEXT,                           -- 'google'
    sso_subject             TEXT,                           -- Google sub claim

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX sales_users_active ON sales_users (is_active) WHERE is_active;
CREATE INDEX sales_users_sso ON sales_users (sso_provider, sso_subject);
```

**Why each column:**
- Bridge between HubSpot's ownership concept and our authenticated sessions
- `role` drives admin web app access but not HubSpot access (which HubSpot manages)

---

## Layer 5: Agent layer

### `agent_reports`

Weekly briefs from Agent 1 (Strategist). Also catches Agent 2 (Quality Reviewer) output.

```sql
CREATE TABLE agent_reports (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    agent_name              TEXT NOT NULL,                  -- 'strategist-v1', 'quality-reviewer-v1'
    prompt_version_id       UUID NOT NULL REFERENCES prompt_versions(id),

    -- Time window analysed
    analysis_start          TIMESTAMPTZ NOT NULL,
    analysis_end            TIMESTAMPTZ NOT NULL,

    -- Output
    report_markdown         TEXT NOT NULL,                  -- the brief Michael reads
    recommendations         JSONB NOT NULL DEFAULT '[]',    -- structured: [{type: 'segment_mix', suggested_change: {...}, rationale: ...}]

    -- Human review
    reviewed_at             TIMESTAMPTZ,
    reviewed_by             UUID REFERENCES sales_users(id),
    decision                TEXT,                           -- 'accepted', 'rejected', 'modified'
    decision_notes          TEXT,

    -- Cost
    generation_event_id     UUID REFERENCES generation_events(id),

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX agent_reports_agent ON agent_reports (agent_name);
CREATE INDEX agent_reports_pending_review ON agent_reports (created_at DESC) WHERE reviewed_at IS NULL;
```

**Why each column:**
- `recommendations` JSONB structure means the admin app can render each recommendation with an accept/reject button. Machine-actionable, not just prose
- `decision` + `decision_notes` is the training data for "would the agent's recommendations have worked" — cross-reference with outcomes 30/60/90 days later
- Generation event reference so we can analyse the agent's own cost over time

---

### `agent_recommendation_outcomes`

The long-term tracking of whether agent advice was sound. Populated by a periodic backfill job.

```sql
CREATE TABLE agent_recommendation_outcomes (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id               UUID NOT NULL REFERENCES agent_reports(id),
    recommendation_index    INTEGER NOT NULL,               -- which recommendation in the report's JSONB array

    -- Measurement
    evaluated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    days_after_report       INTEGER NOT NULL,
    measured_outcome        JSONB NOT NULL,                 -- e.g. {reply_rate: 0.12, vs_baseline: 0.08}
    verdict                 TEXT,                           -- 'correct', 'incorrect', 'inconclusive'

    evaluator_notes         TEXT,

    UNIQUE (report_id, recommendation_index, days_after_report)
);
```

**Why each column:**
- Evaluated at multiple horizons (e.g. 30, 60, 90 days) with separate rows
- `vs_baseline` baked into measured_outcome — the 20% control stream is what baseline is computed from
- This is the table that eventually earns Agent 1 the right to act autonomously — when its verdicts are consistently `correct`, Michael can promote it

---

## Migrations strategy

- Alembic, no exceptions. Every schema change is a migration file in git.
- Migration files are **never edited after merge**; always new migrations forward-apply.
- Destructive migrations (DROP, ALTER removing columns) require a two-step pattern: mark deprecated in version N, remove in version N+1 after verifying no code reads the column.
- A migration that needs a backfill (e.g., new required column on existing table) splits into three migrations: add nullable, backfill, make NOT NULL.

---

## What this schema does NOT yet handle

Intentional omissions, to be addressed when we encounter them:

- **Multi-tenancy:** there's only one Global Kinect. No `tenant_id` column anywhere. If Global Kinect ever licenses this system to others, that's a year-2 concern.
- **Localisation:** all content is English. If segments expand to Arabic outreach, we'll add a `language` column to relevant artefact tables then.
- **Call recordings:** tables exist to accept a `recording_url` eventually, but no dedicated table yet. Added post-legal review.
- **Campaign grouping:** leads aren't yet grouped into campaigns. If we run a "pre-Ramadan burst" campaign distinct from regular weekly flow, we'd add a `campaigns` table and FK from leads.
- **Cross-segment deduplication escalation:** the three-way dedupe rule (email OR linkedin OR company+name) is enforced in application code. If it becomes a performance bottleneck, we convert to a materialised view with indexes.

---

## Total table count

**14 tables:**
L1: segments, leads
L2: prompt_versions, generation_events, lead_research, lead_email_drafts, lead_phone_scripts, sdr_edits
L3: lead_activity, lead_outcomes, reply_classifications
L4: pipeline_runs, suppression_list, sales_users
L5: agent_reports, agent_recommendation_outcomes

(Count is 16 with L5; the grouping above is for reading ease.)

Sizing at 50 leads/week with full sequence generation: approximately 5,000 leads/year → 20k generation events → 25k activity rows → very small by Postgres standards. No partitioning needed in year 1.

---

## Review checklist for Michael before we move to HubSpot contract

- [ ] Agreed to schema layering and naming
- [ ] Comfortable with denormalisation choices (especially on `leads`)
- [ ] Agreed that `control_stream` column exists from day one even though unused until agents arrive
- [ ] Agreed to store full prompt + full model output (cost: ~50MB/year additional storage, benefit: training data)
- [ ] Agreed that `sdr_edits` table exists even though we haven't confirmed HubSpot engagement API lets us detect edits
- [ ] Agreed that 16 tables is not too many (it's not; it's the right number for the requirements)

Any "no" on this list we resolve now, before I write the HubSpot contract document which bakes these decisions deeper.
