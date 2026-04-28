# HubSpot Integration Contract

**Project:** Global Kinect Sales Intelligence
**Scope:** Data flows between `globalkinect/sales-intelligence` and HubSpot
**Assumed tier:** Sales Hub Professional or higher
**Auth model:** Private App with scoped API token
**Last updated:** April 2026

---

## The contract in one paragraph

HubSpot owns **contacts, deals, and activity** (emails sent, meetings, notes, deal stage). Our system owns **research reports, rubric scores, and drafted content** (email sequences, phone scripts). When the pipeline runs, we push enriched leads into HubSpot as Contacts with custom properties linking back to us. An hourly sync pulls HubSpot activity into our Postgres for agent analysis. SDRs work entirely inside HubSpot; our UI extension surfaces the AI briefing inline on the Contact record. We never modify HubSpot activity records; we only create new Contacts/Deals/Engagements and read activity.

---

## Direction of data flow

Two flows, explicitly one-directional at each boundary:

```
  PIPELINE WORKER ─────push──────►  HubSpot
                                      │
                                      │ (SDRs work here)
                                      │
  POSTGRES      ◄──────pull──────── HubSpot
                (hourly sync)
```

**We push to HubSpot:** new contacts, new deals, pre-drafted email engagements, custom property values
**We pull from HubSpot:** contacts we created (to check sync state), deal stage changes, email engagements (with sent content), meetings, notes, call logs, owner assignments

**We never:** update activity records HubSpot created, touch records for contacts we didn't originate, change deal stages from our side, modify emails that have been sent

This asymmetry is deliberate. HubSpot is SDR-operated. We are system-operated. Any rule that blurs that line invites conflicts where our pipeline overwrites an SDR's work. Hard separation.

---

## Authentication

**Mechanism:** HubSpot Private App with a scoped API token.

Scopes required:

| Scope | Why |
|-------|-----|
| `crm.objects.contacts.read` | Dedupe checks; sync lead state |
| `crm.objects.contacts.write` | Create new contacts from pipeline runs |
| `crm.objects.deals.read` | Sync deal stage progression |
| `crm.objects.deals.write` | Create deals linked to pushed contacts |
| `crm.schemas.contacts.read` | Read custom property definitions |
| `crm.schemas.contacts.write` | Create/update the `gk_*` custom properties at setup time |
| `sales-email-read` | Read email engagement bodies (critical for sent-content capture) |
| `crm.objects.owners.read` | Populate `sales_users` from HubSpot owners |
| `timeline` | Read timeline events (meetings, calls, notes) |

**Token storage:** Google Secret Manager. Never in `.env` files committed to the repo. Pipeline worker reads at startup, UI extension uses HubSpot's native auth flow.

**Rotation:** Annual rotation scheduled via admin app. Out-of-band rotation capability if a token leaks.

---

## Custom properties we create in HubSpot

One-time setup: the pipeline worker's bootstrap script creates these five contact properties and two deal properties if they don't exist. Idempotent — re-running is safe.

### Contact properties

| Property | Type | Field name | Purpose |
|----------|------|------------|---------|
| GK Lead ID | Single-line text | `gk_lead_id` | UUID foreign key back to `leads.id` in Postgres |
| GK Segment | Dropdown | `gk_segment` | `cfo-mid-market`, `owner-smb-contractor`, future values |
| GK Rubric Score | Number | `gk_rubric_score` | Total score from the scoring layer |
| GK Research URL | Single-line text | `gk_research_url` | Deep link to the AI briefing view (admin web app URL) |
| GK Pipeline Run ID | Single-line text | `gk_pipeline_run_id` | UUID back to `pipeline_runs.id`; enables "which weekly batch produced this" |

**Grouped under:** custom property group `Global Kinect AI` so they appear together in the Contact sidebar.

### Deal properties

| Property | Type | Field name | Purpose |
|----------|------|------------|---------|
| GK Lead ID | Single-line text | `gk_lead_id` | UUID foreign key back to `leads.id` — same as contact property, denormalised onto deal for easier analytics |
| GK Segment | Dropdown | `gk_segment` | Copy of contact segment at deal-creation time; locked even if contact is re-segmented later |

**Why duplicate `gk_lead_id` and `gk_segment` on the deal:** in HubSpot, reporting on deals is cleaner when the filter fields live on the deal object directly rather than joining through the associated contact. Pays for itself every time you build a funnel report.

### Properties we do NOT create

- **Don't create:** a custom deal stage pipeline. We use HubSpot's standard pipeline. Our segment routing is about which contacts enter, not how they progress.
- **Don't create:** a custom close-reason pick-list. If HubSpot has one, we read it; if not, free text. Unless Michael specifically wants a structured close-reason taxonomy (recommended but not in scope for Phase 1).

---

## Push flow: new leads into HubSpot

Executed at end of pipeline run, after Postgres inserts complete.

```
For each new lead with status='pushed-to-hubspot' pending:

  1. Check suppression: skip if email/domain in suppression_list

  2. Dedupe check (HubSpot side):
     GET /crm/v3/objects/contacts/search
       filterGroups: [{ filters: [{ propertyName: 'email', operator: 'EQ', value: lead.email }] }]
     If match exists: update our leads.hubspot_contact_id, don't create

  3. Create contact:
     POST /crm/v3/objects/contacts
       properties: {
         email: lead.email,
         firstname: lead.first_name,
         lastname: lead.last_name,
         phone: lead.phone,
         jobtitle: lead.job_title_raw,
         company: lead.company_name,
         website: lead.company_domain,
         linkedin_url: lead.linkedin_url,
         country: lead.company_country,
         gk_lead_id: lead.id,
         gk_segment: segment.slug,
         gk_rubric_score: lead.total_score,
         gk_research_url: f'https://sales-admin.globalkinect.co.uk/leads/{lead.id}',
         gk_pipeline_run_id: lead.pipeline_run_id
       }
     Store response hubspot_contact_id in leads row

  4. Create deal:
     POST /crm/v3/objects/deals
       properties: {
         dealname: f'{company} — {full_name}',
         pipeline: 'default',
         dealstage: 'appointmentscheduled',  -- first stage: 'New lead pushed'
         gk_lead_id: lead.id,
         gk_segment: segment.slug
       }
       associations: [{ to: { id: contact_id }, types: [{ associationCategory: 'HUBSPOT_DEFINED', associationTypeId: 3 }] }]
     Store hubspot_deal_id in leads row

  5. Push drafted email sequence as engagements:
     For each email_draft in lead_email_drafts (sequence_position 1..4):
       POST /crm/v3/objects/emails
         properties: {
           hs_timestamp: now(),
           hs_email_direction: 'EMAIL',
           hs_email_status: 'DRAFT',        -- critical: draft only, SDR sends
           hs_email_subject: draft.subject,
           hs_email_text: draft.body_markdown,
           hs_email_from_email: <assigned owner>,
           hs_email_to_email: lead.email,
           hubspot_owner_id: assigned_owner.hubspot_owner_id
         }
         associations: [{ to: contact }, { to: deal }]
       Store response engagement_id back to lead_email_drafts.hubspot_engagement_id

  6. Update local lead status → 'pushed-to-hubspot'
```

**Error handling:**
- 409 conflicts (contact already exists) handled by the dedupe check in step 2
- 429 rate limits: exponential backoff with jitter, max 5 retries
- 5xx errors: mark lead with `status='push-failed'`, log in `pipeline_runs.warnings`, do not fail entire run
- Network failures mid-step: idempotency keys on Postgres side allow retry without duplicate creation

**Owner assignment:**
For Phase 1, round-robin across active SDRs in `sales_users` where `role='sdr'`. Assignment recorded in `leads.assigned_owner_id` (add this column — flagging for schema update). Phase 2 can add smarter assignment (territory, segment specialisation, workload).

---

## Pull flow: HubSpot activity into Postgres

Executed hourly by a separate sync worker. Incremental based on last-sync timestamp.

```
For each sync run:

  1. Determine cursor: last successful sync time from sync_state table
     (add this table — flagging for schema update)

  2. Fetch engagements modified since cursor:
     GET /crm/v3/objects/emails/search
       filterGroups: [{ filters: [{ propertyName: 'hs_lastmodifieddate', operator: 'GTE', value: cursor }] }]
       properties: [hs_email_subject, hs_email_text, hs_email_status, hs_email_direction, hs_timestamp, hubspot_owner_id]
       associations: [contact, deal]
     Paginate through results

  3. For each email engagement:
     - Check: is this for a contact we created (has gk_lead_id)?
       If no: skip (respect boundary — not our contact)
     - Upsert into lead_activity table
     - If status transitioned from DRAFT to SENT: check if content matches our original draft
       If matches: log sdr_edits row with action='sent-as-is'
       If differs: log sdr_edits row with action='edited-then-sent' and store both versions
     - If hs_email_direction='INCOMING_EMAIL': this is a reply; queue for reply_classifications

  4. Repeat for:
     - Meetings: GET /crm/v3/objects/meetings/search
     - Calls: GET /crm/v3/objects/calls/search
     - Notes: GET /crm/v3/objects/notes/search

  5. Fetch deal stage changes:
     GET /crm/v3/objects/deals/search
       filterGroups: [{ filters: [
         { propertyName: 'hs_lastmodifieddate', operator: 'GTE', value: cursor },
         { propertyName: 'gk_lead_id', operator: 'HAS_PROPERTY' }
       ] }]
       properties: [dealstage, amount, closedate, closed_lost_reason]
     For each: insert new lead_outcomes row if stage differs from current; mark previous is_current=false

  6. Update sync_state cursor to start-of-run timestamp

  7. Dead-draft sweep (runs once per day, not hourly):
     Find lead_email_drafts rows where pushed_at > 14 days ago AND no corresponding
     lead_activity row with activity_type='email_sent'. Log sdr_edits with action='discarded'.
```

**Why hourly not real-time:**
- HubSpot rate limits favour periodic polling over webhook chaos
- Agent reasoning doesn't need sub-hour latency
- Adds operational simplicity: sync failures recover on next hour, no webhook endpoint to maintain
- Phase 2 can add webhook listeners for specific high-value events (deal stage changes) while keeping hourly polling as the safety net

**The critical verification item:**

> **Claim:** `hs_email_text` after status transition DRAFT→SENT contains the final sent body, including any edits the SDR made before sending.

If this is true: SDR edits are captured automatically, no extra work.
If this is false: we fall back to Plan B — subscribe to the `email.sent` webhook, fetch the sent version separately, diff against original.

**This must be tested within the first week of Phase 1 work.** Test procedure:
1. Create a test contact in HubSpot sandbox
2. POST a DRAFT email engagement with body "Test draft body"
3. Manually edit the email in HubSpot UI and send
4. GET the engagement by ID
5. Inspect: does `hs_email_text` show the edited content or the original?

If Plan B is needed, the data model doesn't change — only the sync logic does. We've designed for either outcome.

---

## UI Extension contract

**Location:** Extension card on the Contact object's sidebar.

**Technology:** HubSpot UI Extensions SDK (React + TypeScript, HubSpot's sandboxed runtime). Separate small repo or subdirectory: `globalkinect/sales-intelligence/extensions/hubspot-briefing-card/`.

**What it renders:**

```
┌──────────────────────────────────────────────┐
│  🧠  Global Kinect AI Briefing               │
├──────────────────────────────────────────────┤
│                                              │
│  Segment: CFO Mid-Market    Score: 78        │
│                                              │
│  📄  Research Report  [expand]                │
│     3-sentence summary pulled from report… │
│                                              │
│  ✉️  Email Sequence  (4 drafts)               │
│     ▸ Touch 1 (ready)                        │
│       Subject: "Payroll for your Riyadh…"    │
│       [Preview] [Open draft in Emails]       │
│     ▸ Touch 2 (Day +3 follow-up)             │
│     ▸ Touch 3 (Day +7)                       │
│     ▸ Touch 4 (Day +14)                      │
│                                              │
│  📞  Phone Script                             │
│     [Voicemail] [Opener] [Objections]        │
│                                              │
│  ⚠️  Not a fit? [Flag lead]                   │
└──────────────────────────────────────────────┘
```

**Data source:** HubSpot serverless function (included in the extension package) fetches from our admin app's internal API using the `gk_lead_id` contact property. API authenticated via a shared secret (Google Secret Manager).

**What it does NOT do:**
- Does NOT send emails from within the extension (HubSpot's native email UI does this; we push drafts, they send)
- Does NOT modify HubSpot data beyond the [Flag lead] action (which writes to our side, not HubSpot's)
- Does NOT surface analytics; that's admin-app territory

**Performance budget:** initial render < 500ms, lazy-load long content (full research report markdown) behind an expand interaction. Users will close the card if it's slow.

**Failure mode:** if our API is down or the `gk_lead_id` property is missing (e.g., contact created manually, not via pipeline), show a graceful "No AI briefing available for this contact" state. Never show an error that scares the SDR.

---

## Admin web app — the non-HubSpot surface

Separate small FastAPI + server-rendered HTML tool for Michael (not SDRs). Lives at `sales-admin.globalkinect.co.uk` (subdomain of existing Global Kinect platform).

**Routes:**

| Route | Purpose |
|-------|---------|
| `GET /runs` | Pipeline run history with status, cost, lead count per segment |
| `GET /runs/{id}` | Detailed view of one run: leads created, errors, warnings, agent input |
| `GET /leads/{id}` | The full AI briefing view (also deep-linked from HubSpot UI extension) — research, email drafts, phone script, edit history |
| `GET /segments` | Current segment config; toggle is_active, adjust target_per_week |
| `POST /segments/{id}` | Update segment config (audited, changes logged) |
| `GET /reports` | Agent reports (weekly strategist briefs) with accept/reject actions |
| `POST /reports/{id}/decision` | Record Michael's decision on a recommendation |
| `GET /suppression` | Manage suppression list: add manual blocks, review auto-added entries |
| `POST /suppression` | Add a suppression entry |
| `GET /metrics` | Simple funnel: leads → sent → replied → meeting → closed, sliced by segment |
| `GET /health` | Admin health check: last pipeline run, last sync, alert status |

**Auth:** Google SSO with email allowlist, stored in `sales_users.sso_subject`. Only Michael and managers get access initially; SDRs do NOT need admin app access (they work in HubSpot).

**Tech choice justification:** server-rendered HTML (Jinja2) over React because:
- 1-3 users, not 1000 — no SPA performance payoff
- Admin UI changes rarely; Jinja templates are easy to modify
- Less JavaScript = less attack surface for an internal tool touching sensitive data
- Consistent with staying Python-native

---

## Contact and deal stage naming

HubSpot comes with a default sales pipeline. We use it. The stages (as of this writing, subject to HubSpot defaults):

| Stage | Internal name | Our interpretation |
|-------|---------------|-------------------|
| Appointment scheduled | `appointmentscheduled` | New lead just pushed — awaiting first outreach |
| Qualified to buy | `qualifiedtobuy` | Had a conversation, looks real |
| Presentation scheduled | `presentationscheduled` | Demo booked |
| Decision maker bought-in | `decisionmakerboughtin` | Proposal sent |
| Contract sent | `contractsent` | Final terms under review |
| Closed won | `closedwon` | Won |
| Closed lost | `closedlost` | Lost |

Our pipeline *reads* these but does not *enforce* them. SDRs manage progression. Agent analysis treats stage transitions as the outcome signal.

**One rename we will make during setup:** rename `appointmentscheduled` label to "New lead (AI)" in HubSpot UI to distinguish from manually-created leads. The internal name (`appointmentscheduled`) stays unchanged to avoid API breakage.

---

## Rate limits and quotas

HubSpot API rate limits (Pro tier at time of writing):

- 110 requests per 10 seconds per private app
- 250,000 requests per day

Our expected usage:
- Pipeline run push: ~5-10 API calls per lead × 50 leads/week = 250-500 calls/week (nothing)
- Hourly sync: ~5-50 calls per hour depending on activity volume
- UI extension: ~1-3 calls per card render; light

**Headroom is enormous.** We won't hit limits in year 1 unless something is looping incorrectly. Monitor anyway — set up an alert at 50% daily quota consumption.

---

## Error scenarios and handling

| Scenario | Detection | Response |
|----------|-----------|----------|
| Token expired / invalid | 401 response | Alert to Michael, pause pipeline, manual re-auth |
| Rate limit hit | 429 response | Exponential backoff; resume within 60s |
| Contact creation conflict (duplicate email, not caught by dedupe) | 409 response | Log warning, re-run dedupe logic, link to existing contact |
| Custom property missing | 400 with specific error | Bootstrap script didn't run or was reverted; re-run bootstrap, alert |
| Owner ID invalid (SDR deactivated in HubSpot) | 400 | Re-fetch owners, reassign from active pool, log |
| HubSpot API unavailable | 5xx or timeout | Retry 5x with backoff; if still failing, mark run as `partial`, complete on next run |
| Sync lag > 6 hours | Alert rule on `sync_state.last_success_at` | Page Michael; likely token or network issue |

**Never:** silently skip a lead because a push failed. Always surface in `pipeline_runs.warnings` and in the admin `/runs/{id}` view.

---

## Schema additions this document implies

Two tables I realised while writing this contract that weren't in `02-schema.md` and need adding:

### `sync_state`

Tracks the sync cursor for HubSpot pull jobs.

```sql
CREATE TABLE sync_state (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sync_name           TEXT NOT NULL UNIQUE,           -- 'hubspot-engagements', 'hubspot-deals', etc
    last_success_at     TIMESTAMPTZ NOT NULL,
    last_attempt_at     TIMESTAMPTZ NOT NULL,
    last_error          TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### Columns to add to `leads`

```sql
ALTER TABLE leads ADD COLUMN assigned_owner_id UUID REFERENCES sales_users(id);
ALTER TABLE leads ADD COLUMN pushed_to_hubspot_at TIMESTAMPTZ;
ALTER TABLE leads ADD COLUMN push_attempts INTEGER NOT NULL DEFAULT 0;
ALTER TABLE leads ADD COLUMN last_push_error TEXT;
```

These will be folded into `02-schema.md` as an addendum section when we finalise Phase 0.

---

## Verification items for Phase 0 discovery

Before Claude Code starts serious implementation work on sync, these need answering:

1. **Does `hs_email_text` reflect final sent content after SDR edits?** (See verification procedure above. Critical for `sdr_edits` capture.)

2. **What HubSpot tier is Global Kinect actually on?** Starter (blocker), Professional, or Enterprise? Determines UI extension availability.

3. **Does the current HubSpot instance have an existing custom properties group we should use, or do we create `Global Kinect AI` fresh?** Check before bootstrap script runs.

4. **Are there existing contacts for any of the Vibe-sourced leads?** A pre-sync dedupe report against HubSpot's current contact base would prevent accidental duplicates — a one-off audit before first pipeline run.

5. **Do SDRs currently use HubSpot Sequences?** If yes, we should investigate pushing our 4-touch sequence as a HubSpot Sequence rather than 4 separate draft emails — cleaner UX. If no, draft emails are fine.

6. **Meeting booking mechanism?** Does the team use HubSpot Meetings (calendly-style links) or book manually? Affects the `activity_type='meeting'` sync semantics.

Michael, if you can answer these six before we move to document 04 (repo and tasks), the build becomes much smoother. None are blockers — they're refinements.

---

## What this document does NOT cover

- Actual Python client code (that's Phase 1 implementation)
- Webhook configuration (Phase 2 if needed)
- Historical HubSpot data backfill (separate migration exercise if relevant)
- Multi-workspace HubSpot support (we have one workspace — sufficient)

---

## Review checklist for Michael

- [ ] Data flow direction (asymmetric push/pull) makes sense
- [ ] Custom property names (`gk_lead_id` etc) are acceptable — these are hard to change later
- [ ] Owner assignment as round-robin is acceptable for Phase 1
- [ ] Deal-stage naming leaves HubSpot's defaults alone
- [ ] Admin web app scope is sufficient (no "dashboard for SDRs" — HubSpot UI extension does that)
- [ ] Hourly sync cadence (not real-time webhooks) is acceptable for Phase 1
- [ ] 6 verification items will be answered before deep implementation

If all checked, we proceed to `04-repo-and-tasks.md` — the scaffold + Claude Code task list.
