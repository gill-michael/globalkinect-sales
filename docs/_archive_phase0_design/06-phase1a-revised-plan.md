# Phase 1A Revised Plan — HubSpot-Free Build

**Project:** Global Kinect Sales Intelligence
**Scope:** The first 3 months of build. No HubSpot integration.
**Supersedes:** doc 04 Tasks 09-10; parts of doc 03 and doc 05 that specify HubSpot behaviour
**Read order:** 01-vision → 02-schema → 03-hubspot-contract → 04-repo-and-tasks → 05-amendments → **THIS DOCUMENT** → (Phase 1B design, produced at month 3)
**Last updated:** April 2026

---

## What changed and why

Earlier design assumed a Sales Hub Professional upgrade and HubSpot integration built in Phase 1. On commercial grounds, the HubSpot upgrade is deferred at least 3 months. Rather than build integration code that won't be deployed, we split the work:

- **Phase 1A (months 1-3):** the full pipeline, scoring, generation, and storage. Michael + 1-2 SDRs use a minimal admin app to browse AI briefings and manually log send actions. No HubSpot integration code.
- **Phase 1B (month 4):** upgrade HubSpot, build Tasks 09-10 per the existing amendments, migrate from manual logging to sync.
- **Phase 1C (months 5-6):** build the HubSpot UI extension.

This is a better sequence than the original. The operational value (AI-generated leads and drafts delivered weekly) arrives in 6-8 weeks, not after the full 12-week HubSpot integration loop. The HubSpot constraints (DRAFT undocumented, sequences inflexible) no longer block progress, because we're not taking the dependency in 1A.

---

## The three-month story in plain terms

**Weeks 1-4: Build the pipeline core.**
Tasks 00-08 per doc 04. By end of week 4 you can push-button generate 50 scored leads with research + drafts per week. Data lives in Postgres. No user-facing UI beyond the scripts.

**Weeks 5-8: Build the admin app as SDR workspace.**
A new task (08.5 in this doc). By end of week 8, you and one SDR can log in, browse the week's leads, read the research, copy drafts to clipboard, send via your own email client, and click "log send" to record the action. Agent 0 (weekly descriptive brief) starts running.

**Weeks 9-12: Operate and learn.**
Run the weekly pipeline. Use the admin app. Generate manually-logged send data. Watch what works, what doesn't. Shape Phase 1B design based on real SDR workflow observations.

**End of month 3 checkpoint:** decide whether to upgrade HubSpot and proceed to Phase 1B, or adjust direction based on what 12 weeks of real use has taught us.

---

## What's in Phase 1A (the build list)

Carrying forward from doc 04 tasks, unchanged:

- **Task 00** Environment preflight — but without the HubSpot-specific steps (no upgrade, no private app, no sandbox portal). Still do Cloud SQL, Secret Manager, GitHub repo, DNS reservation.
- **Task 01** Project scaffold + CI
- **Task 02** Config, logging, DB engine
- **Task 03** Schema migration (all 16+ tables **including** HubSpot-related fields like `hubspot_contact_id`; they stay nullable and unused until Phase 1B)
- **Task 04** Vibe Prospecting adapter (with `ProspectSource` Protocol per Amendment I1)
- **Task 05** Scoring rubrics
- **Task 06** Dedupe + suppression (with job-change detection per Amendment G2)
- **Task 07** Lead persistence end-to-end
- **Task 08** Research + draft generation (4-touch email sequence stays in Postgres)

**NEW in Phase 1A:**

- **Task 04b** — Scrape source adapter (details pending your JSON file; placeholder for now)
- **Task 08.5** — Admin app Phase 1A: SDR-facing briefing browser with manual logging
- **Task 08.7** — Agent 0 (descriptive weekly brief), brought forward from Task 11

**REMOVED from Phase 1A** (returns in 1B):

- Task 09 HubSpot push
- Task 10 HubSpot sync
- Task 10.5 nightly hygiene sweep (simpler version in 1A, full sweep in 1B)
- Task 10.75 cost monitoring (simpler version in 1A)
- UI extension (Phase 1C)

---

## What the admin app looks like in Phase 1A

This is the central new thing. In the original design the admin app was Michael-only — a small thing for pipeline run inspection and segment config. In Phase 1A it becomes the **primary SDR workspace** because there's no HubSpot UI extension to do that job yet.

That makes it bigger than originally scoped, but not dramatically — it's still FastAPI + Jinja templates, not a React app. Deliberately utilitarian.

### Routes

```
Public:
  GET  /login                 Google SSO initiate
  GET  /auth/callback         SSO callback

Authenticated (all routes require an active session):

  SDR routes — Michael + assigned SDRs can access
  GET  /inbox                 Leads assigned to me, sorted by score desc
  GET  /leads/{id}            Full AI briefing: research, drafts, phone script
  POST /leads/{id}/draft-action   Manual send-logging; see below
  POST /leads/{id}/flag       Not-a-fit, regenerate-research, etc
  POST /leads/{id}/rate/{kind}/{artefact_id}   Thumbs up/down rating
  POST /leads/{id}/generate-phone-script       On-demand phone script
  POST /leads/{id}/manual-activity   Log a meeting booked, call made, etc

  Admin routes — Michael only
  GET  /runs                  Pipeline run history
  GET  /runs/{id}             Detailed view of one run
  GET  /segments              Segment config
  POST /segments/{id}         Update segment config
  GET  /reports               Agent 0 weekly briefs
  GET  /suppression           Manage suppression list
  POST /suppression           Add entry
  GET  /metrics               Funnel + cost per lead
  GET  /users                 Manage SDRs (add, deactivate, set capacity)
  POST /users                 Add user
  GET  /health                Ops health
```

### The `/leads/{id}` page — the thing SDRs will stare at

This replaces what would have been the HubSpot UI extension card. It needs to be good. Visually:

```
┌────────────────────────────────────────────────────────────────┐
│  Lead: Kashish Kohli                           Score: 80 / 86  │
│  Group CFO + SVP Leasing @ The Sanad Group (UAE)               │
│  kashish.kohli@sanadgroup.com   +971 ••• •••• •••              │
│                                                                 │
│  Segment: CFO Mid-Market                                        │
│  Top score drivers: Group Finance Lead · UAE · Group holding   │
│                                                                 │
│  [Flag: not a fit] [Regenerate research]                        │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📄 Research  (read in full →)                                  │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ 3-sentence auto-summary                                   │ │
│  │ • Recent UAE real-estate consolidation play               │ │
│  │ • Headcount ~250 across 3 subsidiaries                    │ │
│  │ • Group-level payroll via external bureau (per LinkedIn)  │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ✉️ Email sequence                                              │
│  ▸ Touch 1 — Ready now                           👍 👎          │
│    Subject: Payroll consolidation across your 3 entities       │
│    [Copy to clipboard] [Log as sent ▾]                         │
│                                                                 │
│  ▸ Touch 2 — Ready after Touch 1 sent + 3 days                 │
│    [Preview] [Generate fresh version]                          │
│                                                                 │
│  ▸ Touch 3 — Ready after Touch 2 sent + 4 days                 │
│  ▸ Touch 4 — Ready after Touch 3 sent + 7 days                 │
│                                                                 │
│  📞 Phone script  [Generate on demand]                          │
│                                                                 │
│  🗓️ Activity                                                    │
│    (empty — log a send or meeting to begin tracking)           │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

### The "Log as sent" flow — the critical capture moment

When the SDR clicks `[Log as sent ▾]` on a draft, a small form appears:

```
How did you send this?
  ○ As-is (no edits)
  ○ I edited it before sending
  ○ Actually, I decided not to send this one

(If edited)
  Final subject:   [ pre-filled with draft subject, editable    ]
  Final body:      [ pre-filled with draft body, editable       ]

Sent at: [ now() — or adjust if you sent it earlier ]

(If not sending)
  Reason: [ optional free text ]

[Cancel] [Save]
```

**On submit, the backend does in one transaction:**

1. Create `sdr_edits` row:
   - `action`: `sent-as-is` | `edited-then-sent` | `discarded`
   - `original_content`: draft body at time of log
   - `edited_content`: the final body the SDR pasted (or identical if sent as-is)
   - `sdr_user_id`: the logged-in user
2. Update `lead_email_drafts`:
   - Set `sent_at` to the timestamp (unless discarded)
   - Set `superseded_at` + `superseded_reason` if discarded
3. Insert a `lead_activity` row with `activity_type='email_sent'`, `direction='outbound'`, and `content_text` = the final body
4. If this was touch 1, mark the lead as `status='in-progress'`
5. Return success to UI

**The friction is ~15 seconds per send.** For a SDR sending 10 leads/day, that's 2.5 minutes/day of overhead. Acceptable.

### The "Log a reply" flow

SDRs also need to log replies so we can capture outcome signal. A separate action on the lead page:

```
📥 Log a reply from the prospect

Reply content: [ multi-line text area ]
Received at:    [ now() — adjustable ]

(On submit, the backend immediately classifies via Claude Haiku)
Detected intent: meeting-request
Is this right? [Yes, save] [No — override to: dropdown]
```

This uses Amendment D1-D2's classification logic but triggered by the SDR paste rather than hourly sync. When Phase 1B lands, this manual flow is replaced by sync, but the same classifier logic is reused.

### The "Log a meeting / call / note" flow

Also manual for Phase 1A. Just a form that inserts into `lead_activity` with the right type. Keeps outcome tracking functional without HubSpot.

---

## The scrape source (placeholder — awaiting your JSON)

You mentioned a JSON file you'll upload for a scraping source. Until I see it, I'm reserving this structure:

### Task 04b — Scrape source adapter

**Goal:** Ingest prospects from [scrape source TBD based on JSON] in addition to Vibe.

**Inputs:** Your JSON file, placed at `config/scrape_source.json` in the repo.

**Outputs:**
- `src/gk_sales/adapters/scrape/` — adapter module implementing `ProspectSource` Protocol
- Whatever the JSON describes — this could be: a list of target companies to research individually, a website scrape config, a seed list to feed Vibe with more refined filters
- Integration into the pipeline so scrape-sourced prospects are scored with the same rubrics and land in the same `leads` table, tagged with `source_run` like `SCRAPE-2026-W17`

**Design principle:** whatever this source is, it is fed through the `ProspectSource` interface so the pipeline treats it identically to Vibe downstream. Adapter-level differences only.

When you upload the JSON I'll specify this task concretely — type of source, parsing logic, rate limits, error handling, and whether it complements Vibe (run both) or substitutes for it (pick one per week).

Until then, the schema and pipeline are designed to accept a second source without schema changes. The `leads.pipeline_run_id` + `leads.source_run` pattern already supports multi-source provenance.

---

## What stays true from earlier docs

Everything HubSpot-independent. The schema is almost unchanged (see §schema notes below). The Vibe pipeline is unchanged. The scoring, dedupe, generation, prompt versioning — all unchanged.

The agent timeline is slightly adjusted:
- **Agent 0** — brought forward from Task 11 to Phase 1A week 5 onward. Its input sources are pipeline runs, leads, and manually-logged activity. It learns to describe what's happening based on whatever data exists — which in 1A is smaller but still meaningful.
- **Agent 1** (Strategist) — still month 3+, but its "analyse 90 days of activity" premise now includes manually-logged sends/replies rather than HubSpot sync. Same logic, different data source.
- **Agent 2** (Quality Reviewer) — unchanged.

---

## Schema notes for Phase 1A

Almost no schema changes vs what's specified in docs 02 + 05. Specifically:

**Keep the HubSpot-related columns in the schema from day one** (`leads.hubspot_contact_id`, `leads.hubspot_deal_id`, `lead_email_drafts.sent_engagement_id`, `sdr_edits.hubspot_engagement_id`, `lead_activity.hubspot_engagement_id`). They stay nullable. Phase 1B populates them.

**Add one column** to `leads`:

```sql
ALTER TABLE leads ADD COLUMN source_run TEXT;
-- e.g. 'vibe-2026-W17', 'scrape-2026-W17', to distinguish origin within a pipeline run
-- Already partially redundant with pipeline_run_id + vibe_dataset_id but useful for quick filtering
```

**No new tables needed.** The `lead_activity` table already accepts manually-created rows — we just populate them via the admin app rather than HubSpot sync.

---

## The Phase 1A → 1B transition plan (month 3 checkpoint)

At the end of month 3, before committing to the HubSpot upgrade:

### Decision checklist

- [ ] Is the system producing leads we'd actually work? (Check by sampling 20 random leads from last month)
- [ ] Are SDRs actually using the admin app, or bypassing it? (Check logging rates)
- [ ] Is the draft quality good enough that `sent-as-is` rate > 30%? (If <30%, the drafts are wrong, not the HubSpot integration)
- [ ] Have we closed at least 2-3 deals from Phase 1A leads, or seen demo-booking rates at ≥5%? (If not, investigate before adding integration complexity)
- [ ] Are the costs tracking to expectations (~£30/week)?
- [ ] Do SDRs want HubSpot integration, or would they prefer we invest those engineering weeks elsewhere? (This question is worth asking openly.)

If most of the boxes tick, upgrade HubSpot and proceed to Phase 1B. If they don't, we have a harder conversation about what the system should become.

### Backdated data import at transition

When HubSpot Professional goes live in month 4:

1. Export all contact history from HubSpot Starter (manual UI export, one-time).
2. Ingest the export via a one-off migration script: for each email engagement in the export, find the matching lead in our Postgres (by email + approximate timestamp), insert a `lead_activity` row retrospectively.
3. Contacts in the HubSpot export that don't match any lead in our DB — skip. These are older than our pipeline; they don't meaningfully inform training.
4. After import, disable manual logging flows. All future capture happens via sync.

The backdated data has the honest caveat stated earlier: it's good for validating the system and seeding early Agent 0 reports, but it lacks the AI-draft → SDR-edit lineage that makes post-month-4 data much higher quality. That's fine — the value of month 4+ data compounds, and 3 months of backdated data is a reasonable cold-start.

---

## Cost during Phase 1A

With no HubSpot integration and no UI extension:

- **Vibe Prospecting:** 300 credits/week ≈ $60/week ≈ $780 over 3 months
- **Perplexity research:** 50 leads/week × $0.15 = $7.50/week ≈ $100 over 3 months
- **Claude drafting + classification:** 50 leads/week × $0.04 = $2/week ≈ $25 over 3 months
- **Cloud Run + Cloud SQL (dev tier):** ≈ $30/month ≈ $90 over 3 months
- **Google Secret Manager, Cloud Scheduler, logging:** negligible
- **HubSpot Starter:** whatever you're already paying (unchanged)

**Total Phase 1A spend: ~$1,000 over 3 months.** Substantially cheaper than the HubSpot-integrated path, and we learn whether the pipeline creates real value before committing to the £4,400/year HubSpot expansion.

---

## What this defers (and why that's fine)

Things that are explicitly deferred and the honest justification for each:

**Automatic email send and tracking.** SDRs send from their own tools in Phase 1A. Slight workflow friction (paste drafts, log manually), but avoids 6 weeks of integration work that would be rebuilt when HubSpot arrives.

**Real-time activity sync.** Manual logging instead. Lossy if SDRs forget to log, but cheap and sufficient for small team.

**UI extension inline with HubSpot.** Admin app is the UI for now. Less polished than a HubSpot card but more than adequate for 2 users.

**A/B testing live operation.** Schema is present, not wired up. Defer until there's enough volume to test against.

**HubSpot Sequences for control stream.** Deferred with HubSpot itself. The 20% control stream still exists at the segment-selection layer; it just isn't sent through Sequences yet.

**Auto-discarded-after-14-days logic.** Replaced by manual "I decided not to send this" in the log form.

---

## Updated task list for Phase 1A

Full sequenced list. Tasks 00-08 are per doc 04 (with amendments per doc 05). 04b, 08.5, 08.7 are new. 09-10 and UI extension are Phase 1B/1C.

| # | Task | Effort | Status |
|---|------|--------|--------|
| 00 | Environment preflight (no HubSpot parts) | 2-3h (Michael) | New behaviour |
| 01 | Project scaffold + CI | Small | Unchanged |
| 02 | Config, logging, DB engine | Small-medium | Unchanged |
| 03 | Schema migration (all tables + amendments) | Medium-large | Unchanged |
| 04 | Vibe Prospecting adapter | Medium | Unchanged |
| 04b | Scrape source adapter | TBD on JSON | **New** |
| 05 | Scoring rubrics | Small-medium | Unchanged |
| 06 | Dedupe + suppression | Small | Unchanged |
| 07 | Lead persistence end-to-end | Medium | Unchanged |
| 08 | Research + draft generation | Large | Unchanged |
| 08.5 | Admin app Phase 1A | Medium-large (5-8h) | **New** |
| 08.7 | Agent 0 descriptive brief | Small-medium (2-3h) | Brought forward |
| -- | **Phase 1A GO-LIVE** | | |
| -- | Operate for ~8 weeks, learn | | |
| -- | Month 3 checkpoint decision | | |
| -- | **IF GO:** upgrade HubSpot | | |
| 09 | HubSpot push flow | Medium-large | Phase 1B |
| 10 | HubSpot sync flow | Large | Phase 1B |
| 10.5 | Nightly hygiene sweep | Small-medium | Phase 1B |
| 10.75 | Cost monitoring | Small | Phase 1B |
| -- | Migrate manual logging → sync | Small | Phase 1B |
| -- | Backdated export import | Small | Phase 1B |
| -- | **Phase 1B complete** | | |
| 11+ | UI extension (separate repo) | Medium | Phase 1C |
| 12+ | Agent 1 Strategist | Medium | Month 3+ |

Total Phase 1A engineering time (rough estimate): 40-60 hours of Claude Code work across 4-6 weeks of elapsed time.

---

## Task 08.5 specification

Because this is the biggest new task, here's the full spec.

### Task 08.5 — Admin app Phase 1A: SDR briefing browser + manual logging

**Goal:** Deliver a web app that Michael and 1-2 SDRs use to browse AI-generated lead briefings, copy drafts, and log send actions.

**Inputs:** Tasks 01-08 merged. Lead content flowing into Postgres weekly.

**Outputs:**

- `src/gk_sales/admin/main.py` — FastAPI app factory with middleware, session config, error handlers
- `src/gk_sales/admin/auth.py` — Google SSO via Authlib; email allowlist from `ADMIN_ALLOWED_EMAILS` env
- `src/gk_sales/admin/routes/` — all routes listed in the §Routes section above
- `src/gk_sales/admin/templates/` — Jinja2 templates: `layout.html`, `login.html`, `inbox.html`, `lead_detail.html`, `log_send_form.html`, `runs.html`, `metrics.html`, etc
- `src/gk_sales/admin/static/style.css` — utilitarian CSS, ~300 lines, Global Kinect brand colours (navy/teal)
- Integration tests for critical flows: login, view lead, log a send, log a reply
- E2E test using Playwright (one happy-path scenario, SDR logs in → sees inbox → opens lead → logs a send)

**Acceptance:**

- Michael and an allowlisted SDR email can log in via Google SSO
- Non-allowlisted emails are rejected with a clear message
- `/inbox` shows the logged-in user's assigned leads, sorted by score
- `/leads/{id}` renders research, 4 drafts (with ready/locked state per Amendment A3), optional phone script section
- "Copy to clipboard" button on draft populates clipboard via JS
- "Log as sent" form validates inputs, writes sdr_edits + lead_email_drafts + lead_activity in one transaction
- "Log a reply" form invokes Claude Haiku classifier synchronously and shows detected intent with override option
- Admin-only routes (`/runs`, `/segments`, `/users`) reject non-admin users
- Flash messages on success/failure, no silent fails
- Mobile-friendly (SDRs may check from phones — use semantic HTML + simple responsive CSS, no framework)
- Deployed to Cloud Run with Cloud SQL connection via Cloud SQL proxy

**Estimated effort:** 5-8 hours of Claude Code work. Likely split across 2 sessions (routes + templates first, then auth + polish).

**Notes for Claude Code:**

- Use `fastapi.templating.Jinja2Templates` throughout; server-render, no SPA
- Htmx for interactive bits (the log-send form, the classification override) — avoid React
- Sessions stored signed in cookies (via `itsdangerous` or Starlette's `SessionMiddleware`); session secret from env
- All DB writes through `session_scope()` context manager; transaction per request
- Don't try to make it pretty — make it fast, clear, and reliable. SDRs will use it because it works, not because it looks nice

---

## Review checklist for Michael before Claude Code starts

- [ ] Phase 1A / 1B split makes sense
- [ ] Admin app as primary SDR surface (not just Michael admin) is acceptable
- [ ] Manual logging friction (~15 seconds per send) is acceptable for 3 months
- [ ] Scrape source JSON will be provided before Task 04b starts
- [ ] Month 3 checkpoint review will happen before HubSpot upgrade commits
- [ ] £1,000 estimated 3-month spend is within budget
- [ ] Understand that 3 months of manual-logged data is smaller/weaker than post-HubSpot sync data, but still useful
- [ ] Happy with Agent 0 coming online week 5-6 rather than waiting for integration

Once these tick, Task 00 preflight (simplified — no HubSpot bits) can begin.

---

## What this doc does NOT change

- The schema. It's already HubSpot-agnostic.
- The generation pipeline (Tasks 01-08).
- The agent philosophy (advisor for 6+ months).
- The overall project identity — still a sales intelligence system, not a CRM.
- The year-one training data thesis — just with a weaker first 3 months of data, stronger month 4+.

---

## Phase 0 document count

After this doc, we have:

```
docs/
├── 01-vision.md                 The why (original)
├── 02-schema.md                 The schema (original)
├── 03-hubspot-contract.md       The integration (deferred to Phase 1B)
├── 04-repo-and-tasks.md         The task roadmap (original)
├── 05-amendments.md             Review + Perplexity findings
├── 06-phase1a-revised-plan.md   THIS DOCUMENT — the HubSpot-free Phase 1
└── review.md                    The critical review
```

When Phase 1A nears completion, I'll produce `07-phase1b-plan.md` folding HubSpot integration back in based on what we've learned from 3 months of real use.

For now, this doc is the operational build plan. Read it in sequence after the originals; amendments land on top of it when they conflict.
