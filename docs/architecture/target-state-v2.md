# Sales Engine — Target-State Architecture

**Version:** v2
**Date:** 2026-05-03
**Status:** Draft for review
**Author:** Claude (with Michael)
**Supersedes:** v1 (2026-05-03)
**Changes from v1:**
- Open questions 1-7 resolved (see end of document)
- Multi-user from day one — auth, ownership, and assignment now first-class concepts (was: deferred to month 2)
- EOR partnership sequence designed in detail (was: flagged for separate spec)
- Notion's long-term role specified (was: deferred)
- Tiered AI cost confirmed
- Week-1 and week-4 plans updated to reflect multi-user from start

---

## 1. Why we're doing this

Global Kinect needs cashflow. The shortest path to cashflow is converting prospects into clients. The current sales infrastructure is functional in parts but has grown organically across a dozen sessions, multiple agents, and conflicting tools. The result is a system where the SDR can produce outreach but cannot reliably know who has been worked, what stage each Deal is in, what should happen today, and which channel is the right next touch. That has to change inside one month.

The strategic backdrop is the founder transition: Michael is moving from employed work toward full-time on Global Kinect. The sales engine is the runway-extending instrument. Every architectural decision in this document is weighted against that — speed to first paying client matters more than long-term theoretical purity.

The system being built must do four things end to end inside the next month:

1. **Ingest leads from multiple sources** — Vibe Prospecting (volume), curated CSVs (founder-led), HubSpot existing contacts, and identified EOR-provider targets — without losing track of which source said what.
2. **Enrich and qualify** — Perplexity for company research where it earns its cost, Claude for normalisation, scoring, and asset generation.
3. **Drive multi-channel outreach** — email through Instantly, LinkedIn touches manually-but-tracked, cold calls manually-but-tracked, all coordinated as a single sequence per Contact rather than parallel uncoordinated touches.
4. **Present the SDR with one screen** that shows what to do next, with the assets ready, dedup enforced, and progress visible.

The system is *not* trying to replace HubSpot, Notion, or Instantly. It's coordinating them. The canonical state lives in a Postgres database that the SDR's dashboard reads from and writes to. Every external tool is an integration — a service that does what it does best, with state synced back into Postgres as the source of truth.

---

## 2. Current state

The audit (`docs/audit/0001-existing-sales-engine.md`) and `SYSTEM.md` together describe what exists. This section is the architect's read of that material — what to keep, what to change, what to retire.

### What works and stays

- **The 18-agent system in `app/agents/`.** Most of the agents do real work and produce sensible outputs. The agent boundaries are good. They will be rewired to read/write Postgres instead of Notion-as-canonical, but the agent code itself largely survives.
- **The Vibe Prospecting ingestion (`scripts/vibe_prospecting_scan.py`).** Pulls 7-ICP × region prospects from Explorium with bulk_enrich. Works. Will be rewired to write to Postgres.
- **The per-lead deep-research pipeline (`sales-engine-v2/`).** Perplexity + Claude generating research/email/sequence/call/LinkedIn assets per lead. The v2 prompts are good. Will be promoted to canonical (replacing v1) and called as a service from the new architecture.
- **`leads/Reports/<slug>/`.** The SACRED folder of generated assets. Stays sacred. Becomes a regenerable cache, with references stored in Postgres but the markdown files themselves preserved.
- **HubSpot, Notion, Instantly, Perplexity, Anthropic, Vibe Prospecting accounts.** All live, all integrated where they're integrated, all paid. Don't churn the tool stack.
- **The Lovable dashboard at `leads/leads/`.** Stays as-is for now. Decision on its long-term role is deferred to month 2.

### What changes

- **Notion stops being canonical.** It becomes a review surface — operators can edit and decide in Notion, but the source of truth is Postgres. The `NotionSyncAgent` flips direction: it pushes from Postgres to Notion, not the other way around. The 12 Notion DBs become Postgres tables (with Notion as a synced view of a subset).
- **HubSpot becomes the CRM-of-record for Contacts and Companies.** The Contact / Company / Deal model is the conceptual unit. Postgres mirrors this exactly, syncs both ways. SDRs who prefer the HubSpot UI can work there; the dashboard shows the same data because it's the same data.
- **Instantly becomes the email-sending layer.** Approved drafts flow from Postgres into Instantly campaigns. Instantly's webhooks (sent, opened, replied, bounced) flow back into Postgres as Activity records. SDRs stop copying drafts into Gmail.
- **The Operator Console gets superseded.** Not yet — it stays running in parallel until the new SDR dashboard is the daily-driver, which is week 4 of the month. Then it retires.
- **`sales-engine/` (v1) retires.** v2 is promoted to take its place, callable as a service from the orchestration layer.
- **The SDR works in a new dashboard**, not in HubSpot, not in Notion, not in the Operator Console. One screen, purpose-built.

### What gets deleted

- The 51-deletion git status from the folder relocation gets committed. The legacy `leads/_manifest.json` and `leads/_run.log` go.
- `sales-engine.zip` once v2 is confirmed working.
- `.mv_test_cross` and other audit-flagged orphans.
- `SYSTEM_ARCHITECTURE.md` and `PROJECT_PLAN.md` move to `docs/archive/` with supersession headers.

### What's deferred (out of scope for the one-month window)

- Inbound-from-website motion (Pipeline 3). The form-submission feed from globalkinect.ae/.co.uk into the system. Plumbed in month 2.
- Re-activation of stale leads as a deliberate motion. Possible later.
- The Lovable dashboard's long-term fate.
- Cold-blanket "Layer 3" sender (already deferred in SYSTEM.md).
- Mobile/phone enrichment at scale (still unverified per audit finding).

---

## 3. Target state

The architecture in one diagram:

```
┌─────────────────────── SOURCES ────────────────────────┐
│  Vibe Prospecting   Curated CSV   HubSpot import       │
│        │                │                │             │
└────────┼────────────────┼────────────────┼─────────────┘
         │                │                │
         ▼                ▼                ▼
    ┌────────────────────────────────────────────┐
    │   INGESTION LAYER (Python scripts)         │
    │   - dedupe against existing Contacts       │
    │   - normalise into Contact/Company shape   │
    │   - assign source, tag, motion             │
    └────────────────────────────────────────────┘
                          │
                          ▼
    ┌────────────────────────────────────────────┐
    │            POSTGRES (canonical)            │
    │                                            │
    │   contacts ─── companies ─── deals         │
    │      │             │            │          │
    │      ▼             ▼            ▼          │
    │  activities    accounts     pipelines      │
    │      │             │            │          │
    │      ▼             ▼            ▼          │
    │  sequences   sequence_steps  assets        │
    │                                            │
    └────────────────────────────────────────────┘
        ▲                  │                 ▲
        │                  │                 │
   ┌────┴─────┐    ┌───────▼────────┐  ┌────┴─────┐
   │ Agents + │    │   API LAYER    │  │ Webhook  │
   │ AI       │    │   (FastAPI)    │  │ receivers│
   └──────────┘    └───────┬────────┘  └──────────┘
        ▲                  │                 ▲
        │                  ▼                 │
        │         ┌────────────────┐         │
        │         │ SDR DASHBOARD  │         │
        │         │  (Next.js)     │         │
        │         └────────────────┘         │
        │                                    │
   ┌────┴────────────────────────────────────┴────┐
   │            EXTERNAL INTEGRATIONS              │
   │                                               │
   │   HubSpot (CRM)      Instantly (email send)   │
   │   Notion (review)    Perplexity (research)    │
   │   Anthropic (LLM)    Vibe (sourcing)          │
   └───────────────────────────────────────────────┘
```

### The component-by-component breakdown

**Postgres (canonical state).** Hosted on a new Cloud SQL Postgres instance, isolated from the platform database. Holds the conceptual model — Contacts, Companies, Deals, Activities, Sequences, Pipelines, Assets. This is the only system that "knows everything." Everything else reads from or writes to this.

**Ingestion layer.** A handful of Python scripts that take source-specific input (Vibe CSV, manual CSV, HubSpot pull) and write into the Postgres tables, applying dedup rules and assigning source/motion attributes. Each ingestion path is its own script under `ingestion/<source>/`. They share a common dedup library.

**Agents + AI services.** The existing `app/agents/` rewired to read/write Postgres. Plus the v2 sales-engine prompts repackaged as callable services — `research_service`, `email_service`, `sequence_service`, `call_service`, `linkedin_service` — each one taking a Contact ID and producing structured output stored in Postgres + asset markdown in `leads/Reports/`. Claude and Perplexity are called through these services, not directly by the dashboard.

**API layer.** A FastAPI service exposing REST endpoints over the Postgres state. The SDR dashboard's only data path. Implements business logic (e.g., "advance Deal to next stage and create the next-touch task"). Auth: shared-secret in the one-month window, JWT later.

**SDR dashboard.** Next.js app, single-screen-driven. Three primary views: Today (what to do now), Contact (everything about a person), Deals (pipeline). Talks to the API layer over JSON. Lives in `dashboard/` in the same repo.

**Integrations (sync layers).** Each external tool gets a sync adapter:
- **HubSpot adapter** — bidirectional sync of Contacts/Companies/Deals between Postgres and HubSpot, hourly poll plus webhooks for stage changes.
- **Instantly adapter** — pushes approved sequences to Instantly campaigns, receives webhook events back.
- **Notion adapter** — pushes from Postgres to Notion (one-way) for the operator-review surface. Notion stops being canonical.
- **Vibe Prospecting** — already a script; rewired to write Postgres.
- **Perplexity, Anthropic** — called through the AI services, no direct sync.

### What the SDR's day looks like in the target state

1. Open dashboard. See "Today" view: 30 due actions, ranked.
2. Click a Contact at the top. See research summary, asset previews, current stage, last activity. Decide action.
3. If action is "send email" — click "Approve and queue" — the email goes to Instantly, becomes part of that Contact's sequence.
4. If action is "make call" — click "Mark dialled" after the call, log disposition, automatic next-action created.
5. If action is "send LinkedIn DM" — copy the prepared message, send manually on LinkedIn, click "Mark sent" in dashboard.
6. Reply comes in via Instantly webhook → Activity logged → Deal advances to "engaged" → next-touch task auto-created → appears in tomorrow's Today view.

That's the target experience. No copy-paste between tools. No "where did I leave off." No double-touching the same Contact from a different motion.

---

## 4. Data model

Postgres schema. Tables, columns of note, relationships, what's intentionally JSONB for flexibility.

### Core entities

**`users`** — the people working the system (SDRs, founder, ops)
```
id              uuid PK
email           text UNIQUE NOT NULL
full_name       text
role            text NOT NULL          -- 'admin' | 'sdr' | 'manager' | 'viewer'
active          boolean DEFAULT true
sso_subject     text                   -- subject claim from SSO/JWT, populated on first login
created_at      timestamptz
last_login_at   timestamptz

INDEX on (lower(email))
```

Roles — the permissions model:
- **`admin`** — full read/write everything, can assign Contacts/Deals to any user, manage `users` table, manage pipelines/sequences. Michael is admin.
- **`sdr`** — read/write their own assigned Contacts/Deals/Activities, read all Contacts (so they can see who else is being worked, for coordination), cannot reassign across users.
- **`manager`** — read everything, write assignments, run reports. Doesn't action sequences themselves.
- **`viewer`** — read-only across the system. For ops or analyst roles.

**`companies`** — the organisation
```
id              uuid PK
name            text NOT NULL
domain          text                    -- canonical, lowercased
country         text                    -- ISO-3 or country name
employee_count  int
industry        text
hubspot_id      text UNIQUE             -- sync to HubSpot Company
notion_id       text                    -- review surface mirror
company_role    text                    -- 'end_buyer' | 'eor_provider' | 'partner' | 'competitor' | 'unknown'
firmographic    jsonb                   -- source-specific extra fields
created_at      timestamptz
updated_at      timestamptz
```

**`contacts`** — the person
```
id                uuid PK
company_id        uuid FK companies(id)
first_name        text
last_name         text
full_name         text                  -- application-populated; source may give first/last separately or as a single combined string
email             text
mobile            text
linkedin_url      text
job_title         text
seniority         text                  -- 'c_suite' | 'vp_director' | 'manager' | 'ic'
authority_score   int                   -- 0-10, role-based
hubspot_id        text UNIQUE
notion_id         text
source            text                  -- 'vibe' | 'curated_csv' | 'hubspot_import' | 'manual'
source_metadata   jsonb                 -- source-specific raw data
status            text                  -- 'new' | 'enriched' | 'researched' | 'in_sequence' | 'replied' | 'meeting_booked' | 'closed' | 'dropped'
owner_id          uuid FK users(id)     -- assigned SDR; null = unassigned pool
assigned_at       timestamptz           -- when ownership was last set
created_at        timestamptz
updated_at        timestamptz

UNIQUE INDEX on (lower(email))
INDEX on (company_id)
INDEX on (linkedin_url)
INDEX on (owner_id, status)            -- "my open contacts"
```

**`deals`** — the active buying conversation
```
id              uuid PK
contact_id      uuid NOT NULL FK contacts(id)
company_id      uuid FK companies(id)
pipeline_id     uuid NOT NULL FK pipelines(id)
stage           text                    -- references pipeline.stages JSON
motion_subtype  text                    -- 'volume' | 'curated' for end_buyer pipeline; null for eor
amount_estimate numeric                 -- estimated annual contract value, currency GBP
probability     int                     -- 0-100
expected_close  date
hubspot_id      text UNIQUE
owner_id        uuid FK users(id)       -- the SDR responsible for this Deal
created_at      timestamptz
updated_at      timestamptz
closed_at       timestamptz
won             boolean
loss_reason     text

INDEX on (owner_id, stage)             -- "my pipeline"
INDEX on (pipeline_id, stage)
```

**`pipelines`** — the motion shape
```
id              uuid PK
name            text                    -- 'End-buyer sales' | 'EOR Partnership'
slug            text UNIQUE
stages          jsonb                   -- [{id, name, order, default_probability, ...}]
active          boolean
```

Two pipelines seeded at install:
- `end_buyer_sales` — `new → contacted → engaged → meeting_booked → demo_held → proposal_sent → negotiation → won/lost/nurture`
- `eor_partnership` — `identified → mapped → initial_call → technical_eval → commercial → pilot_design → pilot_active → partnership_signed/lost/paused`

A third pipeline (`inbound`) gets added in month 2.

### Activity and sequencing

**`activities`** — every touch, every event
```
id              uuid PK
contact_id      uuid NOT NULL FK contacts(id)
deal_id         uuid FK deals(id)       -- nullable: pre-deal activities exist; ON DELETE SET NULL preserves activity history under contact when deal deleted
type            text                    -- 'email_sent' | 'email_opened' | 'email_replied' | 'email_bounced' | 'call_made' | 'call_connected' | 'call_voicemail' | 'linkedin_sent' | 'linkedin_replied' | 'meeting_booked' | 'note' | 'stage_change' | 'assignment_change'
direction       text                    -- 'outbound' | 'inbound' | 'internal' (free text, validated in application layer — no DB CHECK)
channel         text                    -- 'email' | 'linkedin' | 'phone' | 'meeting' | 'system' (free text, validated in application layer — no DB CHECK)
payload         jsonb                   -- channel-specific (email subject, call duration, etc.)
performed_by    uuid FK users(id)       -- nullable for system-generated (Instantly webhook, scheduled job)
performed_by_system text                 -- 'instantly' | 'claude' | 'scheduler' | etc. — populated when performed_by is null
external_id     text                    -- e.g., Instantly message ID, HubSpot activity ID
occurred_at     timestamptz             -- nullable; real-world event time, distinct from created_at (row-insert time) — may be backfilled in past
created_at      timestamptz

INDEX on (contact_id, occurred_at DESC)
INDEX on (deal_id, occurred_at DESC)
INDEX on (performed_by, occurred_at DESC)
```

**`sequences`** — the planned cadence per Contact
```
id              uuid PK
contact_id      uuid FK contacts(id)
deal_id         uuid FK deals(id)
template        text                    -- 'direct_outbound_5touch' | 'eor_partnership_long' | etc.
status          text                    -- 'planned' | 'active' | 'paused' | 'completed' | 'cancelled'
started_at      timestamptz
paused_at       timestamptz
completed_at    timestamptz
```
No `created_at` column — lifecycle timestamps (`started_at`/`paused_at`/`completed_at`) carry the semantic meaning.

**`sequence_steps`** — each individual touch within a sequence
```
id              uuid PK
sequence_id     uuid FK sequences(id) ON DELETE CASCADE  -- steps are owned by sequence
step_number     int                     -- 1, 2, 3...
channel         text                    -- 'email' | 'linkedin' | 'call'
scheduled_for   timestamptz             -- when the SDR should action this
status          text                    -- 'pending' | 'ready' | 'completed' | 'skipped'
asset_id        uuid FK assets(id)      -- the asset that powers this touch
completed_at    timestamptz
activity_id     uuid FK activities(id)  -- the activity that fulfilled this step

UNIQUE (sequence_id, step_number)
```
No `created_at` column — `step_number` plus `scheduled_for`/`completed_at` carry the ordering and lifecycle.

### Assets

**`assets`** — the AI-generated outputs
```
id              uuid PK
contact_id      uuid FK contacts(id)
type            text                    -- 'research_report' | 'email' | 'sequence' | 'call_script' | 'linkedin_message'
storage_path    text                    -- e.g., 'leads/Reports/<slug>/email.md'
content_summary text                    -- brief excerpt for dashboard preview
generated_by    text                    -- 'perplexity' | 'claude_opus_4_7' | etc.
generated_at    timestamptz
metadata        jsonb                   -- model used, tokens, cost, citations
```

Markdown content lives on disk in `leads/Reports/<slug>/`. Postgres holds the reference + summary, not the body. Keeps Postgres slim, keeps the SACRED folder intact.

No `created_at` column on `assets` — `generated_at` carries the semantic meaning (when the AI produced the content).

### Supporting

**`pipelines`** seeded as above.

**`accounts`** — for the EOR-provider channel specifically, where multiple Contacts at one EOR provider need account-level rollup
```
id              uuid PK
company_id      uuid NOT NULL FK companies(id) ON DELETE RESTRICT  -- INDEX (Postgres doesn't auto-index FKs); company-rollup queries
account_owner_id uuid FK users(id) ON DELETE SET NULL              -- INDEX; "my accounts" owner-based views
strategic_value text                    -- 'tier_1' | 'tier_2' | 'tier_3' (free text, validated in application layer)
notes           text
```

Most direct-outbound deals don't need an Account row. EOR partnerships always do.

**`runs`** — a record of every batch operation (Vibe scans, agent runs, sync runs)
```
id              uuid PK
type            text                    -- 'vibe_scan' | 'agent_cycle' | 'hubspot_sync' | 'instantly_push' | etc.
started_at      timestamptz
completed_at    timestamptz
status          text                    -- 'running' | 'success' | 'failed' | 'partial'
metrics         jsonb                   -- counts, durations, costs
errors          jsonb
```

### Indexes and constraints worth calling out

- `contacts.email` — unique, lowercased — primary dedup key
- `contacts.linkedin_url` — secondary dedup key
- `(contacts.first_name, contacts.last_name, contacts.company_id)` — tertiary dedup key for cases where email/LinkedIn missing
- Foreign keys all ON DELETE RESTRICT (don't auto-cascade — make deletions deliberate)
- All `_at` timestamps default `now() at time zone 'utc'`

### What I am explicitly not designing yet

- **Notification system.** Email/Slack reminders to the SDR. Defer to week 4 if there's time.
- **Scoring config storage.** Rules live in code for the one-month window. Migrate to a `scoring_rules` table later if rules need to change without code deploys.
- **Granular per-Contact ACLs.** All SDRs can read all Contacts (for cross-rep coordination); writes are restricted to owner. If GDPR/PII restrictions need finer-grained read access later, that's a separate spec.

---

## 5. Integration contracts

For each external tool, what flows in, what flows out, who owns the connector.

### HubSpot

**Direction:** bidirectional.
**Postgres → HubSpot:** new Contacts/Companies/Deals created in Postgres are pushed to HubSpot via Hourly batch sync. Deal stage changes pushed in near-real-time.
**HubSpot → Postgres:** if an SDR edits a Contact or advances a Deal in HubSpot UI, the change webhooks back to Postgres. Hourly poll catches anything missed.
**Conflict resolution:** Postgres wins on data conflicts unless the HubSpot record has a newer `updated_at`. Logged when conflicts occur.
**Owner:** `integrations/hubspot/sync.py` and `integrations/hubspot/webhook_receiver.py`.
**Mapping:** documented in `integrations/hubspot/mapping.md` — explicit field-by-field.

### Instantly

**Direction:** outbound (Postgres → Instantly) for sending; inbound (Instantly → Postgres) for engagement events.
**Postgres → Instantly:** when a `sequence_step` of channel='email' becomes status='ready' and the SDR clicks "Approve and queue," the email + Contact get pushed to an Instantly campaign as a per-Contact custom field set.
**Instantly → Postgres:** webhooks for `sent`, `opened`, `clicked`, `replied`, `bounced` create `activities` rows. The `replied` event also moves the `sequence` to status='paused' until the SDR processes the reply.
**Auth:** API key stored in `.env`.
**Owner:** `integrations/instantly/push.py` and `integrations/instantly/webhook_receiver.py`.

### Notion

**Direction:** one-way (Postgres → Notion). Notion stops being canonical.
**Postgres → Notion:** subset of data synced for review. Contacts and Deals primarily. Sync triggered on `updated_at` change, hourly batch.
**Operators editing in Notion:** changes are *not* synced back to Postgres state. Notion is read-only for canonical state. Notes-and-context fields (free-text-only) on a Contact or Deal can be edited in Notion and synced back as `activities` rows of type `note`, but no canonical state changes.
**Long-term role:** Notion stays as the **read-and-comment surface** indefinitely. It's where Michael reads briefings, leaves comments, and shares context with non-technical collaborators. The dashboard is the *action* surface; Notion is the *thinking and sharing* surface. This division is durable — Notion is genuinely good at the second job and the dashboard is genuinely good at the first.
**Owner:** `integrations/notion/push.py`, refactored from existing `NotionSyncAgent`.

### Vibe Prospecting (Explorium)

**Direction:** inbound only (Vibe → Postgres).
**Flow:** existing `scripts/vibe_prospecting_scan.py` rewired to write Postgres `contacts` and `companies` rows directly, with `source='vibe'` and the full Explorium response in `source_metadata` JSONB. Dedup library checks existing Contacts before insert.
**Cadence:** monthly, manual trigger.
**Owner:** existing script, modified.

### Perplexity

**Direction:** outbound only (request/response). No webhooks.
**Used by:** `services/research_service.py`. Called per-Contact when a research report is requested (either eagerly on a high-priority lead, or lazily when an SDR clicks "Generate research").
**Output:** markdown file in `leads/Reports/<slug>/report.md` plus `assets` row in Postgres referencing it.

### Anthropic (Claude)

**Direction:** outbound only.
**Used by:**
- `services/normalisation_service.py` — Lead intake normalisation (existing `LeadResearchAgent` work).
- `services/scoring_service.py` — qualification scoring (existing `LeadScoringAgent`).
- `services/email_service.py` — first-touch email generation (v2 prompt).
- `services/sequence_service.py` — multi-touch sequence (v2 prompt).
- `services/call_service.py` — call script (v2 prompt).
- `services/linkedin_service.py` — LinkedIn message kit (v2 prompt).
- `services/reply_classifier_service.py` — incoming reply classification (existing `ResponseHandlerAgent`).

Each service has its own prompt file in `services/prompts/<name>.md`. Prompts are version-controlled.

### Sequence templates

Two sequence templates exist at the data-model level (`sequences.template`), each a different cadence shape. Both are stored as data so they can be edited without a code deploy.

**`direct_outbound_5touch`** — for end-buyer sales (volume + curated). Already designed in `sales-engine-v2/prompts/sequence_prompt.md`. Five touches over 16 days:

| # | Day | Channel | Purpose |
|---|---|---|---|
| 1 | 0 (Mon) | Email | Initial value-led outreach |
| 2 | 2 (Wed) | LinkedIn connection request | Parallel social touch |
| 3 | 5 (next Mon) | Cold call | Direct dial, voicemail if no answer |
| 4 | 9 (Fri) | Email | Different angle — case-based or question-based |
| 5 | 16 (next Mon) | LinkedIn InMail / email break-up | Final close-the-loop |

**`eor_partnership_long`** — for EOR-provider partnerships. Designed here for the first time. Eight touches over approximately 12 weeks. The shape is fundamentally different from direct outbound: EOR providers are not "convert in 16 days" prospects — they're strategic conversations that take months. The sequence is more about *orchestrating multiple stakeholder contacts* than driving one Contact to a meeting.

| # | Day | Channel | Purpose |
|---|---|---|---|
| 1 | 0 | LinkedIn engagement | Engage publicly with a recent post by the primary Contact (Head of Operations / Country Expansion / Partnerships). No DM yet — visibility-building only. |
| 2 | 3 | LinkedIn connection request + personalised note | Reference the engagement in Touch 1. Note positions Global Kinect as MENA-coverage *infrastructure*, not as a competitor. |
| 3 | 10 | Email (post-acceptance) | Long-form, thoughtful. Frame: "you've got X clients, Y of them have or want MENA presence — here's the wholesale model that gives you 11-country coverage without building it yourself." Include link to the proposition page on globalkinect.co.uk. No meeting ask yet. |
| 4 | 21 | LinkedIn DM | Follow-up referencing the email. Soft ask: "happy to walk through the technical fit on a call next week — or send the partner brief if that's more useful at this stage." Two paths offered. |
| 5 | 35 | Map a second Contact at the same company | Identify the *technical* counterpart (Head of Product / VP Engineering / Country Operations Lead) — different person, different angle. Run a parallel mini-sequence (LinkedIn engage → connect → DM) on the second Contact. |
| 6 | 50 | Reply or escalate | If primary Contact has engaged: book a 30-min discovery. If silent: send a polished one-pager (PDF) on the partnership model to both Contacts simultaneously, framed as "thought you'd find this useful given X recent news at your company." |
| 7 | 70 | Founder-to-founder outreach | Michael directly to the EOR provider's founder/CEO via warm intro if findable, else a personal LinkedIn DM. The founder-led escalation path — only triggered if SDR-driven steps 1-6 haven't produced a meeting. |
| 8 | 84 | Pause-or-continue decision | Either: meeting booked → sequence ends, Deal moves to `initial_call`. Or: no engagement after eight touches over twelve weeks → Deal moves to `paused`, Account flagged for re-attempt in 6 months. |

The EOR sequence is **dual-Contact by design** — a single EOR provider gets two Contacts in active sequence at the same time, deliberately, because the buying decision involves both the commercial side (touch 1-4) and the operational/technical side (touch 5+). The data model supports this via the existing Contact-Deal-Sequence relationships; the orchestration layer runs two concurrent `sequences` rows pointed at the same Account.

A separate spec (`docs/specs/0003-eor-sequence-prompts.md`, week 3) will detail the actual prompts that generate per-touch copy. The EOR sequence prompts cannot reuse `sales-engine-v2/prompts/sequence_prompt.md` — the tone, length, and ask-shape are too different. New prompt set.

### What I'm not integrating in month 1

- **Lovable dashboard's Supabase reads.** The Lovable dashboard at `leads/leads/` keeps reading the existing Supabase. Migration of that layer is a month-3+ decision.
- **Operator Console.** Stays running, reading Notion. Decommissioned at the end of month 1 once the new dashboard is the daily-driver.
- **Cloudflare Workers, Lovable.dev hosting.** No change.

---

## 6. Migration path

Four weeks. Each week ends with something demonstrably working that the previous week didn't have.

### Week 1 — Postgres foundation + ingestion + auth scaffold

**Goal:** Postgres exists, one ingestion path works, dedup works, multi-user auth scaffold in place.

- Stand up new Cloud SQL Postgres instance (small tier, ~$30/month). Isolated from platform.
- Schema migrations: all tables in section 4 — including `users`. Run via existing migration runner pattern.
- Seed pipelines (`end_buyer_sales`, `eor_partnership`).
- Seed initial users: Michael as `admin`, plus placeholder rows for the SDRs joining (their actual login provisions on first SSO/JWT login).
- Build dedup library: `services/dedup.py` — given a candidate Contact, returns existing match (by email, then LinkedIn, then name+company) or None.
- Rewire `scripts/vibe_prospecting_scan.py` to write Postgres (in addition to current Notion writes — dual-write for safety in week 1).
- Backfill: load current HubSpot Contacts + Companies into Postgres via one-shot import. This is the starting state.
- Backfill: walk `leads/Reports/<slug>/` folders, create `contacts` + `assets` rows for each (linking to the existing markdown).
- **Auth scaffold:** decide and document JWT/SSO approach. Two viable paths:
  - **Path A — Auth0/Clerk/WorkOS managed identity provider** (~$25-50/month tier). Quick to set up, production-grade from day one, social/SSO out of the box.
  - **Path B — Self-hosted (e.g., Supabase Auth, since you have Supabase already, or FastAPI-Users).** No new vendor cost; more setup time.
  - Recommended: **Path A with Clerk or WorkOS** — the time saved in week 1 is worth more than the monthly fee. Decision to confirm before week 1 starts.

**Success criteria:**
- Run a Vibe scan and see new rows appear in Postgres `contacts` and `companies` with correct dedup.
- Pull all current HubSpot Contacts into Postgres, count matches expected.
- Existing folder-based research reports show up as `assets` rows pointing at the right files.
- A test user can authenticate against the chosen provider and the FastAPI layer can validate their JWT.

### Week 2 — HubSpot bidirectional sync + Instantly push

**Goal:** Contacts, Companies, Deals stay in lockstep between Postgres and HubSpot. Instantly receives campaigns from Postgres.

- Build `integrations/hubspot/sync.py` — Postgres → HubSpot for Contacts, Companies, Deals.
- Build `integrations/hubspot/webhook_receiver.py` — HubSpot → Postgres for stage changes, edits.
- Build `integrations/instantly/push.py` — push approved email touches to Instantly as campaign sends.
- Build `integrations/instantly/webhook_receiver.py` — receive `sent/opened/replied/bounced` events into `activities`.
- Migrate the existing 18 agents to read/write Postgres. Heavy refactor — this is the bulk of the week.
- Notion sync flips: `NotionSyncAgent` becomes `notion_push.py`, one-way.

**Success criteria:**
- Create a Deal in HubSpot UI, see it in Postgres within 5 minutes.
- Update a Deal stage in Postgres, see it in HubSpot within 5 minutes.
- Approve an email in Postgres, see it in Instantly campaign.
- Receive a test reply in Instantly, see the corresponding `activities` row in Postgres.

### Week 3 — AI services + asset generation pipeline

**Goal:** Per-Contact research and outreach assets generated on demand, all five asset types working.

- Repackage v2 prompts as services (`research_service`, `email_service`, `sequence_service`, `call_service`, `linkedin_service`).
- Each service: takes Contact ID, generates asset, writes file, creates `assets` row.
- Wire trigger: when a Contact moves to status='enriched', auto-trigger research_service. When SDR requests outreach, trigger email/sequence/call/linkedin services.
- Retire `sales-engine/` (v1). Promote `sales-engine-v2/` content into the new services structure.
- Tear down the dual-write — Postgres becomes sole canonical at end of week 3.
- Wire reply classifier: Instantly reply webhook → `reply_classifier_service` → updates Deal stage + creates next-action task.

**Success criteria:**
- Pick any Contact in Postgres, click "Generate full kit," all five asset types appear in `leads/Reports/<slug>/`.
- Reply received via Instantly is classified, Deal stage advances, next-action task is created — all automatic.
- Vibe scan output is in Postgres only (Notion no longer dual-written).

### Week 4 — SDR dashboard + retire Operator Console

**Goal:** SDRs work the day from the new dashboard, with proper login and per-user views. Operator Console retires.

- FastAPI backend layer over Postgres — the dashboard's data path. **JWT validation middleware** on every endpoint, using the auth scaffold built in week 1.
- Next.js dashboard with login flow (Clerk/WorkOS SDK or equivalent), then four primary views:
  - **Today** — list of *the logged-in user's* due actions, ranked, filterable by motion. One-click into Contact view.
  - **Contact** — research, asset previews, sequence state, activity history, action buttons. Read-all (any SDR can see any Contact for cross-rep coordination), write-restricted-to-owner.
  - **Deals** — pipeline view, filterable by owner ("my deals" / "all deals" toggle), drag-to-advance, motion-filterable.
  - **Assignments** (admin/manager only) — bulk assignment of unassigned Contacts to SDRs.
- Per-user permissions enforced server-side: SDRs cannot reassign Contacts they don't own; viewers cannot write anything; managers can reassign across users.
- SDR runs through full day: ingest → enrich → research → sequence → approve → send → reply → next action — all in dashboard, all attributable to the logged-in user.
- Operator Console marked deprecated, port reused by FastAPI.

**Success criteria:**
- A new lead from Vibe ingestion appears in the *assignment pool* within 1 hour, fully enriched, with assets ready, and an admin/manager can assign it to a specific SDR.
- The assigned SDR sees it in their Today view immediately after assignment.
- SDR completes a full action (e.g., approve email → push to Instantly → mark sent) without leaving the dashboard, and the activity is correctly attributed to them in `activities`.
- A reply to a sent email appears in the *original sender's* Today view as a new task within 5 minutes of receipt.
- A second SDR logging in sees their own Today view, not the first SDR's.

### What "usable" means at end of month 1

- All three motions in scope (direct volume, direct curated, EOR partnership) ingest into the same Postgres, are visible in the dashboard, and have working asset generation and outreach push.
- **Multiple SDRs can log in, see their own assigned work, and act on it without stepping on each other.**
- The SDR's full day happens in the dashboard.
- HubSpot stays in sync as the CRM-of-record.
- Instantly handles email sending end-to-end.
- The 62 existing research reports are accessible through the new system without modification.
- Notion still exists as the read-and-comment surface.

### What's explicitly not done at end of month 1

- The Lovable dashboard at `leads/leads/`. Untouched, parallel.
- Inbound from globalkinect.ae/.co.uk. Month 2.
- Re-activation of stale leads as a deliberate motion. Month 2 or later.
- Cold-blanket "Layer 3" sender. Already deferred in SYSTEM.md, stays deferred.
- Granular per-Contact ACLs (e.g. PII restrictions where some users can see fewer fields). All SDRs read-all-Contacts, write-own-only is the model.

---

## 7. Decisions registered

These are the binding architectural decisions made by this document. Each gets a corresponding ADR file in `docs/decisions/` once we set up the ADR scaffolding. They cannot be changed without a new ADR.

| # | Decision | Why |
|---|---|---|
| 1 | Postgres is canonical state, hosted on a new isolated Cloud SQL instance | Multi-source, multi-channel, custom-dashboard architecture demands a real database. Isolation from platform protects blast radius. |
| 2 | HubSpot Contact/Company/Deal model is adopted verbatim | Well-understood shape, makes HubSpot integration trivial, reps already think in this model. |
| 3 | Two pipelines for the one-month window: end-buyer sales and EOR partnership | Three motions selected by Michael; volume and curated share enough structure to share a pipeline; EOR is structurally different. |
| 4 | Notion stops being canonical; becomes one-way read-and-comment surface — durable role, not transitional | Notion's API and rate limits can't support a custom dashboard; canonical state needs SQL. Notion stays as the thinking/sharing surface, indefinitely. |
| 5 | Instantly is the email-sending layer | Existing tool, deliverability handled, webhook-rich. No SMTP-from-scratch. |
| 6 | The `leads/Reports/` folder remains SACRED | Existing policy in SYSTEM.md, no reason to change. Becomes regenerable cache with Postgres pointers. |
| 7 | `sales-engine/` (v1) retires; `sales-engine-v2/` content is promoted into services structure | v2 has correct prompts, multi-asset output, brand-rule alignment. v1 has the `<think>` leak and outdated positioning. |
| 8 | Lovable dashboard at `leads/leads/` is untouched in month 1 | Out of scope for one-month window. Decision on its long-term role deferred. |
| 9 | Operator Console retires at end of month 1 | Superseded by new SDR dashboard. |
| 10 | Audit-first, spec-first, challenge-before-accept is the working practice | Established earlier in conversation; codified here. Every non-trivial change has a spec; every Claude Code output is reviewed adversarially. |
| 11 | Multi-user from day one; no "solo first, multi later" deferral | The system will be used by multiple SDRs; bolting auth/ownership on later is more painful than building it in from week 1. JWT/SSO via managed identity provider (Clerk or WorkOS recommended). |
| 12 | EOR partnership sequence is dual-Contact and 12 weeks long | EOR providers buy strategically with multi-stakeholder committees. The sequence orchestrates two parallel Contacts (commercial + technical) over 8 touches across 3 months, with founder-led escalation as touch 7. |
| 13 | AI cost model is tiered (eager generation for top-decile leads, lazy for the rest) | ~$50-80/month at current Vibe volumes vs ~$500/month for eager-everything. Confirmed by Michael. |

---

## What this document is, and isn't

This is a **target-state architecture**. It says where we're going and what shape we're building. It does **not** specify:

- Per-table SQL DDL (that's the migration spec, week 1)
- API endpoint shapes (that's the API spec, week 2-3)
- Dashboard component design (that's the dashboard spec, week 4)
- Per-script implementation details (those are individual specs as work begins)

Each of those gets its own document under `docs/specs/`, written immediately before the work starts, reviewed before code is generated.

---

## Questions resolved (from v1)

| # | v1 question | v2 answer |
|---|---|---|
| 1 | Cloud SQL Postgres tier | Smallest tier confirmed, ~$30/month |
| 2 | Two HubSpot pipelines | Confirmed: end-buyer sales + EOR partnership |
| 3 | EOR sequence design | Designed in section 5 above (8 touches over 12 weeks, dual-Contact) |
| 4 | Notion's long-term role | Permanent read-and-comment surface; durable, not transitional |
| 5 | Authentication | Multi-user from day one. Managed identity provider (Clerk or WorkOS recommended) — Path A in week-1 plan |
| 6 | Backup and recovery | Cloud SQL defaults acceptable for now |
| 7 | AI cost ceiling | Tiered approach confirmed (~$50-80/month) |

## One open question for week 1 to confirm before kickoff

**Auth provider choice — Clerk, WorkOS, or alternative?**

Both Clerk and WorkOS are good fits. Quick comparison:

- **Clerk** — developer-friendly, fast to integrate (Next.js SDK is excellent), pricing starts free up to ~10,000 monthly active users. Best for fast-moving teams.
- **WorkOS** — enterprise-leaning, stronger SSO/SAML support out of the box, used by sales tooling like Apollo and Intercom. Pricing is per-feature.
- **Auth0** — mature option, broadest feature set, more expensive.

For a multi-SDR setup at the size you're operating, **Clerk** is probably the right call: lowest friction, strongest Next.js integration, free tier covers you indefinitely. WorkOS makes sense if you anticipate enterprise SSO requirements early (e.g., a partner asks to log in with their corporate Google).

This is the only choice still open. Make it before week 1 kicks off.

---

**End of document.**
