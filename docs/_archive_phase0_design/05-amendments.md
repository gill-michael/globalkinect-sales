# Phase 0 Amendments

**Project:** Global Kinect Sales Intelligence
**Supersedes:** specific sections of docs 01-04 as noted per amendment
**Read order:** 01-vision → 02-schema → 03-hubspot-contract → 04-repo-and-tasks → THIS DOCUMENT
**Last updated:** April 2026

---

## How this document works

Docs 01-04 capture the design as originally drafted. This document records what we've learned since: a critical design review identified 14 weaknesses, HubSpot API research via Perplexity surfaced one showstopper + three clarifications, and a commercial decision on HubSpot tier was made. Rather than rewriting the four originals (which breaks version history and makes review harder), this amendments doc spells out exactly what changes.

Each amendment has:
- **Scope:** which document and which section it modifies
- **Status:** `accepted` / `deferred` / `rejected`, with reasoning where the decision isn't obvious
- **Rationale:** why the change
- **Concrete delta:** exact before/after or addition

Claude Code, when operating against this design, should treat this document's amendments as authoritative where they conflict with earlier docs.

---

## Decisions that set the context

Three decisions made before this amendments doc was written:

**D1. HubSpot tier: Sales Hub Professional, 2 seats at go-live.**
Rationale: UI extensions confirmed unavailable on Starter per HubSpot documentation. Sequences API enrollment also requires Professional. Cost commitment: ~$180/month + $1,500 one-time onboarding (negotiable). Scale seats as SDR hires land.

**D2. Perplexity research completed on six HubSpot API questions (see `research/03-hubspot-research.md` appendix).**
Three key findings:
- DRAFT is not a documented `hs_email_status` value; edited-content preservation is undocumented
- UI extensions available on Professional (GraphQL variants Enterprise-only)
- Sequences API supports enrollment only, not custom per-step content

**D3. Design review produced 14 weaknesses ranked must-fix / should-fix / nice-to-have.**
Full review retained at `docs/review.md`. This amendments doc implements the must-fix and should-fix items; nice-to-haves are recorded as deferred with rationale.

---

## Amendment group A — Draft lifecycle (CRITICAL)

This is the most important amendment. The original push flow in doc 03 pushed four pre-drafted emails into HubSpot as DRAFT engagements per lead. Two independent lines of evidence say this is wrong:

1. **Perplexity research (Q1 + Q4):** DRAFT is not documented as a valid `hs_email_status` value, and HubSpot does not document preservation of pre-edit body content. Our SDR-edit capture story cannot rely on undocumented behaviour.
2. **Design review (Weakness 1):** Four pre-drafts clutter the HubSpot contact record, become stale if the prospect replies warmly to touch 1, and cannot be attributed cleanly to individual send events.

Together these force a redesign: **drafts live in Postgres, HubSpot receives only sent engagements.**

### A1 — Replaces doc 03 §"Push flow: new leads into HubSpot", Step 5

**Status:** Accepted. Must land before Task 09.

**Rationale:** Per D2 and review Weakness 1. Drafts are not a reliable HubSpot primitive for our purposes.

**Delta:**

**REMOVE** (doc 03 Step 5):

```
5. Push drafted email sequence as engagements:
   For each email_draft in lead_email_drafts (sequence_position 1..4):
     POST /crm/v3/objects/emails with hs_email_status='DRAFT'
     Store response engagement_id back to lead_email_drafts.hubspot_engagement_id
```

**REPLACE WITH:**

```
5. (Pipeline push): no draft emails are pushed to HubSpot at pipeline time.

   Drafts 1-4 remain in Postgres only. The UI extension on the contact record
   renders them inline. SDRs act on them through an explicit send action
   (see Amendment A2).

6. Update local lead status → 'pushed-to-hubspot' (contact + deal created;
   drafts staged in Postgres awaiting SDR action)
```

### A2 — New section in doc 03: "Send-path"

**Status:** Accepted. Must land before Task 09.

**Rationale:** The send path is now an explicit workflow, not an implicit draft→sent transition. It must be designed deliberately.

**Addition to doc 03, new section after "Pull flow":**

```
## Send-path: when the SDR sends a draft

When an SDR clicks "Send" on a draft in the UI extension (or pastes via
the copy-to-clipboard fallback and then we detect the send via hourly sync):

  1. UI extension POSTs to backend: /api/leads/{lead_id}/emails/send
     Body: {
       draft_id: UUID,
       final_subject: string,
       final_body: string,
       send_mode: 'direct' | 'via-hubspot-ui'  // 'direct' = we push; 'via-hubspot-ui' = we log after-the-fact
     }

  2. Backend (synchronous):
     a. Load the original draft from lead_email_drafts
     b. Compute diff: original vs final
     c. Insert sdr_edits row with:
        - action = 'sent-as-is' if byte-identical, else 'edited-then-sent'
        - original_content = draft.body_markdown (from DB at time of draft creation)
        - edited_content = final_body
     d. If send_mode='direct':
        POST /crm/v3/objects/emails to HubSpot
          properties: {
            hs_email_status: 'SENT',
            hs_timestamp: now(),
            hs_email_direction: 'EMAIL',
            hs_email_subject: final_subject,
            hs_email_text: final_body,
            hs_email_from_email: assigned_owner.email,
            hs_email_to_email: lead.email,
            hubspot_owner_id: assigned_owner.hubspot_owner_id
          }
          associations: [{ contact }, { deal }]
        Store returned engagement_id on both lead_email_drafts.sent_engagement_id
        and sdr_edits.hubspot_engagement_id
     e. If send_mode='via-hubspot-ui': no HubSpot API call — we wait for the
        hourly sync to ingest the engagement the SDR created themselves.
     f. Update lead_email_drafts.sent_at = now()
     g. Queue next-touch scheduling (see Amendment A3)

  3. Response to UI extension: {engagement_id, confirmation_url}

Error handling:
  - If HubSpot POST fails in step 2d, the sdr_edits row still persists
    (so we have the edit signal) but lead_email_drafts.sent_at stays NULL
    and the status is 'push-failed'. A retry job runs every 5 min for 1 hour,
    then alerts.
  - If sdr_edits write fails, the whole send is rejected (5xx to UI extension).
    We never want a silent send without an audit row.
```

### A3 — New section in doc 03: "Sequence advancement"

**Status:** Accepted. Must land before Task 10.

**Rationale:** Review Weakness 1 cont. — if we're not pushing touches 2-4 upfront, we need a mechanism to decide when (and whether) to push each subsequent touch.

**Addition to doc 03:**

```
## Sequence advancement

Touches 2-4 are generated at pipeline time but held in Postgres. A scheduled
job (the "sequence advancer") runs twice daily (09:00 and 14:00 UTC) and
decides whether to mark each follow-up as "ready to send".

Logic per unsent draft:

  1. Fetch drafts where sent_at IS NULL AND sequence_position > 1
     AND superseded_at IS NULL

  2. For each draft, determine prerequisites:
     a. The prior touch (sequence_position - 1) must have been sent
     b. Sufficient time must have elapsed:
        now() >= prior_touch.sent_at + draft.send_offset_days
     c. No reply has been received on any prior touch
        (check lead_activity for direction='INCOMING_EMAIL')
     d. Reply classification (if any) is not 'unsubscribe-request',
        'not-a-fit-ever', 'angry', or 'meeting-request'
        (meeting-request = stop sequence, different workflow takes over)

  3. If all prerequisites met:
     - Mark draft as ready_at = now()
     - Surface in UI extension as "ready to send"
     - SDR still has manual control; we do not auto-send

  4. If a reply has been received on any touch:
     - Mark remaining drafts as superseded_at = now() with
       superseded_reason = 'reply-received' | 'unsubscribe' | etc.
     - They remain in the table for training data but won't be sent

  5. If a draft has been ready for 7+ days with no action by the SDR:
     - Surface in admin /metrics as a "stalled draft" for awareness
     - Do not auto-send, do not discard
```

### A4 — Schema changes for draft lifecycle

**Status:** Accepted. Must land in Task 03 (initial migration).

**Rationale:** Amendments A1-A3 introduce new state that needs schema support.

**Changes to doc 02 §`lead_email_drafts`:**

Add columns:

```sql
ALTER TABLE lead_email_drafts ADD COLUMN sent_at              TIMESTAMPTZ;
ALTER TABLE lead_email_drafts ADD COLUMN sent_engagement_id   TEXT;
ALTER TABLE lead_email_drafts ADD COLUMN ready_at             TIMESTAMPTZ;
ALTER TABLE lead_email_drafts ADD COLUMN superseded_at        TIMESTAMPTZ;
ALTER TABLE lead_email_drafts ADD COLUMN superseded_reason    TEXT;
```

Add index:

```sql
CREATE INDEX lead_email_drafts_advancement
  ON lead_email_drafts (lead_id, sequence_position)
  WHERE sent_at IS NULL AND superseded_at IS NULL;
```

These columns are populated by the send-path (A2) and sequence-advancer (A3).

---

## Amendment group B — Lead hygiene & closure

### B1 — Closure columns on leads table

**Status:** Accepted. Must land in Task 03.

**Rationale:** Review Weakness 3. Without closure semantics, the DB rots at ~2,600 leads/year.

**Changes to doc 02 §`leads`:**

Add columns:

```sql
ALTER TABLE leads ADD COLUMN closure_reason TEXT;
-- Enum-like values: 'completed-no-reply', 'bounced-hard', 'unsubscribe',
-- 'company-dead', 'pdpl-retention', 'manual-close', 'meeting-booked',
-- 'closed-won', 'closed-lost', 'not-a-fit'
ALTER TABLE leads ADD COLUMN closed_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN closure_notes TEXT;
```

Add index:

```sql
CREATE INDEX leads_closed ON leads (closed_at DESC) WHERE closed_at IS NOT NULL;
CREATE INDEX leads_active ON leads (created_at DESC) WHERE closed_at IS NULL;
```

Update the `status` enum description to note that `status='closed'` ALWAYS implies `closed_at IS NOT NULL` and a valid `closure_reason`. Application-level constraint (Postgres can't easily enforce this trigram).

### B2 — Nightly hygiene sweep job

**Status:** Accepted. Becomes Task 10.5 in the roadmap.

**Rationale:** Review Weakness 3.

**Addition to doc 04:**

```
### Task 10.5 — Nightly hygiene sweep

Goal: Auto-close leads that meet closure criteria; suppress unsubscribes;
flag company-dead signals.

Schedule: 02:00 UTC daily via Cloud Scheduler.

Output module: src/gk_sales/sync/hygiene.py

Behaviour:

  1. Close leads where touch 4 was sent > 14 days ago with no reply:
     UPDATE leads SET status='closed', closed_at=now(),
       closure_reason='completed-no-reply'
     WHERE id IN (
       SELECT lead_id FROM lead_email_drafts
       WHERE sequence_position = 4 AND sent_at < now() - INTERVAL '14 days'
         AND lead_id NOT IN (
           SELECT lead_id FROM lead_activity
           WHERE activity_type = 'email_replied'
             AND direction = 'inbound'
         )
     ) AND closed_at IS NULL

  2. Process new HubSpot unsubscribes (via lead_activity scan):
     - Auto-close lead with closure_reason='unsubscribe'
     - Add to suppression_list (email + email_domain level, permanent)

  3. Check company-domain liveness for leads with no activity in 30+ days:
     - Simple HTTP GET on https://{domain} with 5s timeout
     - If 404/500/DNS-fail for 3 consecutive checks (7 days apart):
       mark closure_reason='company-dead', keep status='closed'
     - This check is rate-limited to 100 domains/day to avoid hammering

  4. PDPL retention: leads with closed_at > 12 months ago AND no closed-won:
     - Soft-delete (clear PII: email, phone, full_name) but retain
       aggregate fields (segment, score, closure_reason) for training stats
     - Record the redaction in a new audit_log table (add as part of this task)

Acceptance:
  - Unit tests for each rule with fixture data
  - Dry-run mode: job logs what it would do, writes nothing
  - Idempotent: running twice same day has no additional effect
```

### B3 — Audit log table for closures and redactions

**Status:** Accepted. Must land in Task 03.

**Rationale:** B2 introduces automated state changes; PDPL compliance requires an audit trail.

**New table for doc 02:**

```sql
CREATE TABLE audit_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type      TEXT NOT NULL,                  -- 'lead_closed', 'lead_redacted', 'suppression_added', etc
    entity_type     TEXT NOT NULL,                  -- 'lead', 'sales_user', etc
    entity_id       UUID NOT NULL,
    actor           TEXT NOT NULL,                  -- 'system:hygiene-sweep', 'user:michael@...', etc
    details         JSONB NOT NULL DEFAULT '{}',    -- structured before/after
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX audit_log_entity ON audit_log (entity_type, entity_id);
CREATE INDEX audit_log_type ON audit_log (event_type, created_at DESC);
```

---

## Amendment group C — SDR UI actions

### C1 — Required UI extension actions

**Status:** Accepted. Feature spec for the `hubspot-briefing-card` repo (Phase 2).

**Rationale:** Review Weakness 4. Without these, the UI extension is read-only and loses adoption.

**Replaces doc 03 §"UI Extension contract" subsection "What it renders":**

The extension card must include four explicit SDR actions, each backed by an API endpoint:

| Action | Endpoint | Side effect |
|--------|----------|-------------|
| 👎 Not a fit | `POST /api/leads/{id}/flag` body `{reason, notes}` | Sets `leads.status='not-fit'`, `closure_reason='not-a-fit'`, `closed_at=now()`; inserts audit_log |
| ♻ Regenerate research | `POST /api/leads/{id}/regenerate` body `{kind: 'research'}` | Marks current `lead_research.is_current=false`; enqueues background job to regenerate |
| 👍 / 👎 rate draft | `POST /api/artefacts/{kind}/{id}/rate` body `{rating: -1\|0\|1, note}` | Inserts `artefact_ratings` row (see C2) |
| 📤 Send this draft | `POST /api/leads/{id}/emails/send` (see Amendment A2) | Logs edit, pushes SENT engagement to HubSpot |

Additionally, the card's header must display a **headline reason line** auto-generated from the top 3 scoring buckets: e.g. "Top score drivers: CFO at 201-500 KSA contracting firm with group entity". This is computed at render time from `leads.score_breakdown`, not stored.

### C2 — artefact_ratings table

**Status:** Accepted. Must land in Task 03.

**Rationale:** Review Weakness 4. SDR sentiment on AI output is high-signal training data.

**New table for doc 02:**

```sql
CREATE TABLE artefact_ratings (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id         UUID NOT NULL REFERENCES leads(id),
    artefact_kind   TEXT NOT NULL,                  -- 'research', 'email_draft', 'phone_script'
    artefact_id     UUID NOT NULL,                  -- polymorphic; app-enforced
    rater_id        UUID NOT NULL REFERENCES sales_users(id),
    rating          SMALLINT NOT NULL,              -- -1, 0, 1
    note            TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX artefact_ratings_artefact ON artefact_ratings (artefact_kind, artefact_id);
CREATE INDEX artefact_ratings_lead ON artefact_ratings (lead_id);
CREATE INDEX artefact_ratings_rater ON artefact_ratings (rater_id, created_at DESC);
```

---

## Amendment group D — Reply classification (synchronous, broader labels)

### D1 — Synchronous inline classification

**Status:** Accepted. Shifts classification from post-hoc to inline within the hourly sync.

**Rationale:** Review Weakness 5. Async nightly classification delivers zero operational value to the SDR; inline with hourly sync delivers hot-reply awareness within an hour of receipt.

**Delta to doc 02 §`reply_classifications`:** no schema change, population path changes.

**Delta to doc 04 Task 10 acceptance criteria:** add:

> When the hourly sync ingests a new inbound email engagement (direction='INCOMING_EMAIL'), the same sync worker calls Claude Haiku to classify and writes the `reply_classifications` row before completing the sync cycle. No separate nightly classifier job.

### D2 — Extended label set

**Status:** Accepted.

**Rationale:** Review Weakness 5. Operationally-significant replies need their own labels.

**Delta to doc 02 §`reply_classifications.classification` enum:**

Replace the 6-value set with 12 values:

```
'meeting-request',      -- priority-1; stop sequence, SDR follow up within 4 hours
'pricing-question',     -- often Michael-handoff
'positive-general',     -- engaged but not yet specific
'polite-defer',         -- "not right now" / "circle back in Q2"
'not-a-fit-now',        -- wrong timing
'not-a-fit-ever',       -- explicit permanent no
'referral-redirect',    -- "talk to my colleague X"
'unsubscribe-request',  -- MUST suppress
'confused',             -- didn't understand the email
'angry',                -- escalate, consider suppression
'out-of-office',        -- auto-reply, low value
'auto-responder'        -- system auto-reply, ignore
```

### D3 — Write classification back to HubSpot

**Status:** Accepted.

**Rationale:** Review Weakness 5. The SDR lives in HubSpot; classification must be visible there.

**New custom contact property (adds to doc 03 §"Custom properties"):**

| Property | Type | Field name | Purpose |
|----------|------|------------|---------|
| GK Reply Sentiment | Dropdown | `gk_reply_sentiment` | Latest classification from our side; populated by hourly sync |
| GK Reply Sentiment Updated | Date | `gk_reply_sentiment_at` | Timestamp of last classification |

Values match the enum in D2. The bootstrap script creates these alongside the existing 5 `gk_*` contact properties.

When the sync writes a `reply_classifications` row, it also PATCHes the HubSpot contact to update these two properties. SDRs can filter their HubSpot contact list by `gk_reply_sentiment = 'meeting-request'` to see hot replies instantly.

---

## Amendment group E — Agent timeline tweak

### E1 — Agent 0: weekly descriptive brief

**Status:** Accepted. New task in roadmap.

**Rationale:** Review Weakness 6. Advisory agents in month 3+ are correct, but month 1-2 needs *some* periodic insight to build the reading-the-brief habit.

**Addition to doc 04 and doc 01:**

```
### Task 11 — Agent 0: Pipeline Describer

Goal: Every Friday 16:00 UTC, produce a one-page descriptive brief of the
week's pipeline activity. Descriptive only, no recommendations.

Not an agent in the "agentic reasoning" sense — it's a templated summary
generated via Claude Sonnet with deterministic structure. Called "Agent 0"
for consistency with later Agent 1 (Strategist) and Agent 2 (Reviewer).

Content:
  - Pipeline runs this week: count, leads produced, failures
  - Score distribution across produced leads
  - SDR activity: leads touched, emails sent, replies received
  - Any warnings from pipeline_runs.warnings
  - Upcoming: what's queued for next Monday's run

Output: agent_reports row with agent_name='describer-v1', decision=NULL.

Cost: negligible (~$0.05/week on Sonnet).

Dependencies: Task 03 (schema), Task 09 (HubSpot push), Task 10 (sync)
must be working so there is data to describe.

Can be built independently of Agents 1 and 2 and is a good exercise in the
agent framework before those later tasks.
```

**Update to doc 01 §"Agents advise before they act":**

Add to the timeline:

```
- Month 1+:   Agent 0 (Describer) runs Fridays — descriptive brief,
              no recommendations
- Months 1-2: No analytical agents; Agent 0 only
- Month 3+:   Agent 1 (Strategist) advisory
(rest unchanged)
```

---

## Amendment group F — Phone script on-demand

### F1 — Defer phone script generation from pipeline to on-demand

**Status:** Accepted.

**Rationale:** Review Weakness 9. Pipeline-time phone scripts go stale; on-demand scripts use fresher research and only spend tokens on leads actually called.

**Delta to doc 04 Task 08:**

Replace the phone script portion:

```
- Claude API → phone script per lead (generated at pipeline time)
```

With:

```
- Phone script generation is NOT triggered at pipeline time.
  Phone scripts are generated on-demand when the SDR clicks "Generate phone
  script" in the UI extension. The endpoint:
    POST /api/leads/{id}/generate-phone-script
  runs a single Claude Sonnet call (cost ~$0.03) using the lead's current
  research + latest activity, and inserts a fresh lead_phone_scripts row.
```

**Delta to doc 02 §`lead_phone_scripts`:** no schema change.

**Delta to doc 04 Task 08 acceptance:** remove "3 phone scripts per run" from the end-to-end test expectation. Phone scripts are only generated when triggered.

---

## Amendment group G — Dedupe, owner assignment, cost controls

### G1 — Owner assignment pluggable strategy

**Status:** Accepted. Schema support now; smarter strategy deferred to Phase 1.5.

**Rationale:** Review Weakness 2. Round-robin as MVP is fine, but the columns need to exist so we don't migrate later.

**Additions to doc 02 §`sales_users`:**

```sql
ALTER TABLE sales_users ADD COLUMN preferred_segments TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE sales_users ADD COLUMN country_focus TEXT[] NOT NULL DEFAULT '{}';  -- ISO-2
ALTER TABLE sales_users ADD COLUMN capacity_per_week INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sales_users ADD COLUMN on_leave_until DATE;
```

**Delta to doc 03 §"Owner assignment":**

```
For Phase 1, a RoundRobinAssigner strategy. Strategy is pluggable via
env var ASSIGNER_STRATEGY. A WeightedAssigner strategy, respecting
preferred_segments, country_focus, capacity_per_week, and on_leave_until,
can be added in Phase 1.5 without schema changes.

Assignment recorded on leads.assigned_owner_id (already flagged as addition).
```

### G2 — Dedupe extension: job-change detection

**Status:** Accepted. Implementation in Task 06.

**Rationale:** Review Weakness 10.

**Delta to doc 02 §`leads`:**

```sql
ALTER TABLE leads ADD COLUMN prior_contact_id UUID REFERENCES leads(id);
CREATE INDEX leads_prior_contact ON leads (prior_contact_id) WHERE prior_contact_id IS NOT NULL;
```

**Delta to doc 02 §"Dedupe rule":**

Replace the 3-point rule with:

```
Dedupe rule (enforced in Python, not SQL):

1. Same LOWER(email) → treat as dupe (reject insert, return existing id)
2. Same canonical_linkedin_url (strip query params, trailing slash,
   vanity suffix normalised) → dupe
3. Same (LOWER(company_domain), LOWER(first_name), LOWER(last_name))
   when both first+last names are non-null AND the LinkedIn URLs don't
   actively contradict (neither is set, or they match) → dupe
4. Job-change detection (NOT a dupe, but link to history):
   If the incoming prospect matches an existing lead on
   (first_name, last_name, canonical_linkedin_url)
   but differs on (email, company_domain), treat as a NEW lead and
   set prior_contact_id to the existing lead's id.

Canonical LinkedIn URL normalisation:
  - Lowercase
  - Strip protocol, 'www.', trailing slash, query string, fragment
  - Strip '-{numeric_id}' suffix if present
  - Result should be 'linkedin.com/in/john-smith'
```

### G3 — Cost brake env var and daily cost check

**Status:** Accepted. Implementation split across tasks.

**Rationale:** Review Weakness 8.

**Delta to doc 04 §".env.example":**

Add:

```
# === Cost controls ===
PIPELINE_COST_CEILING_PER_RUN_USD=50      # Hard brake per single pipeline run
GENERATION_COST_CEILING_PER_LEAD_USD=0.50 # Alert threshold per-lead; >2x median triggers alert
```

**Delta to doc 04 Task 08:**

Add to acceptance:

> If `pipeline_runs.total_api_cost_usd` would exceed `PIPELINE_COST_CEILING_PER_RUN_USD` mid-run, the worker halts gracefully: remaining leads are skipped, `pipeline_runs.status='cost-capped'`, and an alert is raised. Leads already generated stay complete.

**New task Task 10.75 — Cost monitoring:**

```
### Task 10.75 — Cost monitoring job

Goal: Daily check for cost drift. Alert when per-lead generation cost
strays >2× the 30-day rolling median.

Schedule: 03:00 UTC daily via Cloud Scheduler.

Module: src/gk_sales/sync/cost_check.py

Behaviour:
  - Compute per-lead cost for last 30 days from generation_events
  - Compute median and current run's mean
  - If mean > 2 × median: write to agent_reports with
    agent_name='cost-monitor-v1', include diagnosis (which prompts drifted,
    which leads were most expensive)
  - Admin /metrics page renders a cost-per-lead trend line (14d window)

Acceptance:
  - Unit tests with fixture data
  - Dry-run mode prints what it would alert
  - Does not block pipeline; purely observational
```

---

## Amendment group H — A/B testing infrastructure

### H1 — prompt_experiments table and experiment_group column

**Status:** Accepted as schema-only. Operational A/B testing deferred to Phase 2.

**Rationale:** Review Weakness 7. Schema cost is low; having the columns means we don't need a migration when Michael wants to run a subject-line test in month 6.

**Delta to doc 02 §`prompt_versions`:**

```sql
ALTER TABLE prompt_versions ADD COLUMN experiment_group TEXT;
```

**New table:**

```sql
CREATE TABLE prompt_experiments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,
    kind            TEXT NOT NULL,                  -- matches prompt_versions.kind
    started_at      TIMESTAMPTZ NOT NULL,
    ended_at        TIMESTAMPTZ,
    allocation      JSONB NOT NULL,                 -- {'exp-A': 50, 'exp-B': 50}
    hypothesis      TEXT NOT NULL,
    result_summary  TEXT,                           -- written at ended_at
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX prompt_experiments_active ON prompt_experiments (kind) WHERE ended_at IS NULL;
```

No task to build A/B logic yet — deferred. Schema is in place when needed.

---

## Amendment group I — Prospect source portability

### I1 — ProspectSource Protocol

**Status:** Accepted.

**Rationale:** Review Weakness 13. Single-vendor risk on Vibe. Cheap to design away.

**Delta to doc 04 §"Task 04" (Vibe adapter):**

Add to outputs:

> - `src/gk_sales/adapters/base.py` defining `ProspectSource` Protocol with typed methods: `fetch_prospects`, `enrich_emails`, `enrich_phones`, `export_to_csv`. Vibe adapter implements this protocol. No other implementations yet.

Add to acceptance:

> - mypy strict verifies `VibeClient` satisfies the `ProspectSource` protocol.
> - An architectural note is added to `docs/adr/0001-vibe-as-primary-source.md` documenting why Vibe and what alternatives exist (Apollo, ZoomInfo, Cognism, Lusha) and estimated effort to swap (~2-3 eng days).

### I2 — ADR directory from day one

**Status:** Accepted.

**Rationale:** A `docs/adr/` directory is part of the scaffold spec. The first ADR should exist.

**Delta to doc 04 Task 01:**

Add to outputs:

> - `docs/adr/0001-vibe-as-primary-source.md` — stub. Full content written as part of Task 04.
> - `docs/adr/README.md` — brief explanation of the ADR pattern, template location.

---

## Amendment group J — Agent evaluation (deferred but stubbed)

### J1 — Stub doc for agent evaluation

**Status:** Accepted as stub-only. Full design deferred to month 2.

**Rationale:** Review Weakness 14. Agents need a judgement framework before they go live.

**Delta:** add a new file `docs/05-agent-evaluation.md` with a stub:

```markdown
# Agent Evaluation Framework (stub)

**Status:** Stub — to be completed before Agent 1 goes live (month 2-3).

This document will define:
  - Metrics we judge agents on
  - Minimum sample size for statistical significance per metric
  - Attribution model linking agent recommendations to outcomes
  - Human arbitration process when agent and operator disagree
  - Evaluation cadence and reporting

## Open questions to resolve before month 2

1. What does "correct recommendation" mean in our context?
2. How do we attribute outcome changes to agent recommendations
   given the 20% control stream?
3. At what sample size does a verdict become defensible?
4. Who arbitrates when Agent 1 says "shift to contractors" and
   Michael's intuition says "stick with CFOs"?
5. What happens when an agent recommendation is never implemented
   (rejected by operator) — is that a data point or an absence?

## Placeholder until fully designed

For now, agent_recommendation_outcomes.verdict values are set manually
by Michael after 90-day observation windows.
```

---

## Amendment group K — Campaigns (deferred with explicit placeholder)

### K1 — Campaigns deferred; tracking note added

**Status:** Deferred. Confirmation that this is known.

**Rationale:** Review Weakness 11. Phase 1 steady-state flow doesn't need campaigns. Ramadan / Expo / fiscal-year-end bursts will.

**Delta to doc 02 §"What this schema does NOT yet handle":**

No change — this is already explicitly listed. Adding a note that the backlog item has an owner (Michael) and a rough trigger (before Q4 planning).

---

## Amendment group L — Phase 0 setup (explicit scaffolding task)

### L1 — Task 00: environment preflight

**Status:** Accepted. New task before Task 01.

**Rationale:** Review Weakness 12. Claude Code wastes cycles if these aren't set up.

**New task in doc 04:**

```
### Task 00 — Environment preflight (before Task 01)

Goal: Provision external resources that Tasks 01+ depend on. This is a
checklist for Michael, not a Claude Code task per se, but it must be
complete before Task 01 starts.

Checklist:
  □ GitHub: create private repo globalkinect/sales-intelligence
  □ Google Cloud: create project gk-sales-intelligence-prod (and -dev)
  □ Google Cloud SQL: provision Postgres 16 instance (dev tier to start:
    db-f1-micro or similar; upgrade before prod go-live)
  □ Google Secret Manager: create secrets for:
      - VIBE_API_KEY
      - PERPLEXITY_API_KEY
      - ANTHROPIC_API_KEY
      - HUBSPOT_PRIVATE_APP_TOKEN
      - ADMIN_SESSION_SECRET (generate fresh)
      - ADMIN_GOOGLE_CLIENT_ID, _SECRET
  □ HubSpot: upgrade to Sales Hub Professional (2 seats initially)
  □ HubSpot: create sandbox / test portal
  □ HubSpot: create a Private App with the scopes listed in doc 03
    §"Authentication", capture the token into Secret Manager
  □ Domain: reserve sales-admin.globalkinect.co.uk DNS (Cloudflare or similar);
    TLS cert via Google-managed cert when Cloud Run deployed

Deliverable: a docs/runbook.md initial entry listing all resource IDs,
project names, DNS entries, so onboarding a future developer is possible.

Estimated time: 2-3 hours of Michael's time, spread over a few days waiting
on DNS propagation etc.
```

---

## Amendments NOT taken

For completeness — amendments considered and rejected or deferred indefinitely.

### Not taken: reopening the HubSpot-native UI decision

Some readers might ask "given how much friction HubSpot creates (DRAFT undocumented, custom content not in Sequences), should we reconsider building a fuller native dashboard instead?" Answer: no. SDRs' workflow lives in HubSpot; we adapt. The friction is real but survivable; the cost of a fully native SDR-facing app is not worth the friction savings.

### Not taken: call recording infrastructure

Covered in doc 01 as deferred pending legal consultation. No change.

### Not taken: real-time webhook sync

Hourly polling is sufficient for Phase 1. Webhooks are a Phase 2 optimisation for specific high-value events (deal stage change, meeting booked) if hourly latency becomes operationally painful.

### Not taken: multi-currency deal amount handling

Deal amounts stored as `NUMERIC(12,2)` with an assumed USD/GBP semantic. If PEPM pricing becomes multi-currency in Phase 2, revisit.

---

## Summary: what's landed vs deferred

**Must-fix before Task 01:**
- A1-A4: Draft lifecycle redesign (drafts in Postgres, send-path explicit)
- B1, B3: Closure columns, audit_log table
- C2: artefact_ratings table
- G1, G2: sales_users extensions, leads.prior_contact_id
- G3 (env vars only): cost brake env vars defined
- H1: prompt_experiments schema
- I2: ADR directory
- L1: Task 00 preflight

**Must-fix before Task 09:**
- A1-A3: push-flow rewrite, send-path design
- D1-D3: synchronous reply classification + HubSpot write-back
- C1: UI extension action spec (for Phase 2 Implementation)

**Must-fix before Task 10:**
- B2: nightly hygiene sweep (Task 10.5)
- G3 (job only): cost monitoring (Task 10.75)

**Deferred with placeholder:**
- E1: Agent 0 (month 1+ — Task 11)
- F1: on-demand phone script
- J1: agent evaluation framework (stub only)

**Deferred indefinitely:**
- Campaigns (Weakness 11)
- Call recording (vision doc)

---

## Review checklist for Michael before Claude Code starts

- [ ] Amendments A1-A4 understood — drafts live in Postgres, send-path is explicit
- [ ] Amendment B1-B3 — closure semantics and audit_log accepted
- [ ] Amendment C1-C2 — UI extension actions and artefact_ratings accepted
- [ ] Amendment D1-D3 — synchronous reply classification with HubSpot write-back accepted
- [ ] Amendment E1 — Agent 0 to start in month 1 accepted
- [ ] Amendment F1 — phone script on-demand accepted
- [ ] Amendment G1-G3 — owner assignment strategy, dedupe extension, cost brakes accepted
- [ ] Amendment H1 — prompt experiment schema accepted
- [ ] Amendment I1-I2 — ProspectSource protocol and ADR directory accepted
- [ ] Amendment J1 — agent evaluation stub accepted
- [ ] Amendment L1 — Task 00 preflight understood and owned by Michael
- [ ] HubSpot Sales Hub Professional upgrade in motion; private app token capability confirmed

Once these are ticked, Phase 0 is closed and Task 01 can begin.
