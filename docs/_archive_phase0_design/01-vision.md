# Sales Intelligence System — Vision & Architecture

**Project:** Global Kinect Sales Intelligence
**Repository:** `globalkinect/sales-intelligence` (to be created)
**Status:** Phase 0 — Design
**Author:** Design produced with Claude (Anthropic); to be implemented by Claude Code
**Last updated:** April 2026

---

## Why this exists

Global Kinect's outbound sales today looks like this: Michael manually runs prospecting sweeps in Vibe Prospecting, scores leads with bespoke Python scripts, generates research reports and draft emails via a Claude Code pipeline, and hands artefacts to himself or his SDRs as files on disk. It works. It produces high-quality leads. But it is operator-dependent, does not learn from outcomes, and cannot scale past one operator without collapsing.

This project replaces the ad-hoc workflow with a durable system that:

1. **Runs autonomously on a weekly cadence** — pulling fresh leads from Vibe, enriching with emails and phones, scoring with segment-specific rubrics, generating research and outreach artefacts, and landing everything in a database owned by Global Kinect.

2. **Integrates with HubSpot as the operational workspace** — the SDR team lives in HubSpot; we do not fight that. HubSpot owns activity, deal pipeline, and sending. Our system owns the intelligence layer: lead scoring, research reports, drafted content, and analytics.

3. **Captures everything needed to train agents later** — every prompt, every draft, every human edit, every outcome is recorded with full context. The first year produces a **labelled training corpus**, not just a sales pipeline. The sales output is the byproduct.

4. **Graduates from observability to autonomy in stages** — agents are introduced as *advisors* once there is enough data to be worth advising from, then earn their way to narrow autonomous actions over 6-12 months. No agent acts on thin data.

---

## Product philosophy

Three principles that drive every downstream decision.

### 1. Data capture is the product in year one

Every artefact the system produces — a scored lead, a research report, an email draft — is **logged as a feature→outcome pair** with full provenance. The exact prompt used. The model version. The SDR who acted on it. Whether they edited it. Whether the recipient replied. What the deal became.

Getting this right early is non-negotiable. A system that captures the right things for 12 months produces a dataset that can fine-tune a model. A system that captures the wrong things produces noise. We will err toward **over-capturing** and prune later rather than realising in month 9 we lost the provenance we needed.

### 2. HubSpot is sacred ground

Our SDRs live in HubSpot. They know the keyboard shortcuts. They trust the deal view. They send from there. Disrupting this to save a few engineering hours would destroy adoption.

The rule: **HubSpot owns activity. We own intelligence.**

- HubSpot stores contacts, deals, emails sent, meetings, stage changes, notes
- We store AI-generated research reports, scored rubric breakdowns, drafted email sequences, phone scripts, agent reports
- Data flows: we push new leads into HubSpot as Contacts/Deals with metadata linking back to us; HubSpot activity syncs back to us hourly
- The SDR sees everything inside HubSpot (via a UI extension card showing our AI briefing) and never has to learn our system

### 3. Agents advise before they act

No agent makes autonomous decisions in the first 6 months. The pattern is:

- **Months 1-2:** Pure instrumentation. Data accumulates. No agents.
- **Month 3+:** Agent 1 (Weekly Strategist) comes online as an *advisor* — writes Michael a weekly markdown brief, takes no actions
- **Months 4-6:** Agent 2 (Quality Reviewer) comes online, also advisory. Agent 1's recommendations start being tracked against actual outcomes to measure its quality
- **Months 7-12:** Narrow autonomous actions become defensible — specific things like "auto-adjust next week's segment mix by ±10% within pre-agreed bounds"
- **Year 2+:** Broader autonomy unlocks as the training corpus matures and we fine-tune models on Global Kinect's own data

The trap to avoid is **acting on thin data**. An agent recommending a strategy shift based on 3 closed deals is worse than no agent at all — it will confidently point you at confounding factors and you will waste credits chasing hallucinated patterns.

---

## High-level architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  SCHEDULER  —  Cloud Scheduler, weekly Monday 06:00 UTC          │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  PIPELINE WORKER  —  Cloud Run Job, Python                       │
│                                                                   │
│  1. Read active segment config                                   │
│  2. Vibe Prospecting → fetch N prospects                         │
│  3. Enrich → emails + phones                                     │
│  4. Score → segment-appropriate rubric                           │
│  5. Dedupe against existing DB records                           │
│  6. Perplexity → research report per lead                        │
│  7. Claude API → email sequence (4 touches) + phone script       │
│  8. Persist to Postgres                                          │
│  9. Push to HubSpot (Contact + Deal + custom properties)         │
│ 10. Log pipeline_run record with metrics                         │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                                ▼
┌──────────────────────────────────────────────────────────────────┐
│  POSTGRES  —  Google Cloud SQL, separate instance from platform │
│                                                                   │
│  Tables (high-level):                                             │
│    leads                     core record + score + status         │
│    lead_research             Perplexity output                    │
│    lead_email_drafts         versioned email drafts               │
│    lead_phone_scripts        phone call artefacts                 │
│    lead_activity             derived activity from HubSpot        │
│    lead_outcomes             deal stage progression               │
│    prompt_versions           every prompt we've ever run          │
│    generation_events         provenance of every AI output        │
│    sdr_edits                 captured diffs when SDRs modify      │
│    pipeline_runs             weekly job audit log                 │
│    segments                  segment definitions + config         │
│    agent_reports             weekly strategist output             │
│    suppression_list          opt-outs, bounces, blacklist         │
│    sales_users               team members (from HubSpot)          │
└─────┬──────────────────────────────────────────────┬─────────────┘
      │                                              │
      │ hourly sync                                  │ live reads
      ▼                                              ▼
┌──────────────────────────────┐       ┌────────────────────────────┐
│  HUBSPOT  (Sales Pro+)       │       │  ADMIN WEB APP (Michael)   │
│                              │       │                            │
│  Push (from us):             │       │  Routes:                   │
│    Contacts + Deals          │       │    /runs   pipeline audit  │
│    Custom properties:        │       │    /segments   config      │
│      gk_lead_id              │       │    /reports   agent briefs │
│      gk_segment              │       │    /suppressed             │
│      gk_rubric_score         │       │    /metrics   funnel       │
│      gk_research_url         │       │                            │
│      gk_pipeline_run_id      │       │  FastAPI + server-side     │
│                              │       │  rendered HTML (no React)  │
│  Pull (to us):               │       │  Auth: Google SSO + email  │
│    Emails sent/opened/clicked│       │  allowlist                 │
│    Meetings booked           │       └────────────────────────────┘
│    Deal stage changes        │
│    Notes                     │       ┌────────────────────────────┐
│                              │       │  HUBSPOT UI EXTENSION      │
│  UI Extension:               │◄──────│  (SDR-facing)              │
│    AI Briefing card on       │       │                            │
│    Contact records           │       │  TypeScript + HubSpot SDK  │
│                              │       │  Renders: segment, score,  │
│                              │       │  research summary, email   │
│                              │       │  drafts, phone script      │
└──────────────────────────────┘       └────────────────────────────┘
                │
                ▼
┌──────────────────────────────────────────────────────────────────┐
│  AGENTS (advisory, month 3+)                                     │
│                                                                   │
│  Agent 1: Weekly Strategist                                       │
│    Reads: pipeline_runs + lead_outcomes (last 90d)                │
│    Output: agent_reports row (markdown brief)                     │
│    Cadence: Sunday 22:00 UTC                                      │
│    Authority: advisory only                                       │
│                                                                   │
│  Agent 2: Quality Reviewer                                        │
│    Reads: last batch's leads + rubric scores                      │
│    Output: flagged leads + rubric drift observations              │
│    Cadence: after each pipeline_run                               │
│    Authority: advisory only                                       │
└──────────────────────────────────────────────────────────────────┘
```

---

## Key design decisions and why

### Separate Cloud SQL instance from the platform database

Not the same schema, not the same instance. Hard isolation. Reasons:
- **Blast radius:** a sales-tool bug must not risk platform payroll data under any circumstances
- **Access control:** platform data is customer-protected; sales data is Global Kinect internal. Different authorisation models
- **Backup and retention:** sales data has different retention requirements (PDPL-driven) than payroll data
- **Scaling:** sales workload is spiky (weekly batches); platform workload is steady. No reason to share tuning

### HubSpot-native over custom dashboard

Originally considered building a full React dashboard for the SDRs. Rejected after weighing options. Reasoning:
- SDRs already live in HubSpot; asking them to check a second tool loses adoption
- A HubSpot UI extension puts AI briefings *inside* the Contact record they're already viewing — zero context switch
- An admin web app stays for Michael (pipeline runs, agent reports, config) because HubSpot isn't the right surface for operational admin
- Net: one small TypeScript HubSpot extension + one small Python admin app, instead of a full frontend

**Requirement:** HubSpot Sales Hub **Professional** tier or higher. UI extensions are not available on Starter.

### Python for backend, TypeScript only for HubSpot UI

Rationale:
- Global Kinect platform is FastAPI + SQLAlchemy + Postgres. Staying Python keeps patterns familiar
- HubSpot UI extensions require TypeScript (their SDK). Accept this, isolate it to one small package
- Agents will be Python (Anthropic SDK, same ergonomics as the existing `sales-engine` pipeline)
- All shared contracts defined in OpenAPI/JSON Schema so Python and TypeScript both consume them

### Draft-only on email, let HubSpot send

Considered auto-sending from our system. Rejected. Reasoning:
- Building SMTP with bounce handling, deliverability monitoring, domain warming, unsubscribe management is 6 months of engineering we don't need
- HubSpot already does all of this well
- The critical data capture (did they send, what did they edit, what was the final version) is available via HubSpot's Engagement API
- Net: our system writes drafts into HubSpot as `emails` engagement objects attached to the contact. SDRs review, edit if needed, and send from HubSpot. We observe.

**Verification item for Phase 0 discovery:** confirm that HubSpot's API exposes the final sent-content after SDR edits, not just the pre-scheduled version. If it doesn't, we need a different capture strategy (webhook on send, diffing).

### Phase 1 scope: call metadata only, not recordings

MENA call recording laws (UAE Federal Decree-Law 34/2021, KSA PDPL 2023) require verbal consent and treat voice data as personal data. Rather than design the compliance story in this phase, we defer recording. Phase 1 captures:
- Call outcome (from HubSpot: completed, no-answer, voicemail, meeting-booked)
- Call duration
- Post-call notes SDR writes in HubSpot
- Timestamp

Phase 2 (after legal consult) may add transcripts with proper consent flow.

---

## Data capture philosophy

This is the single most important section of this document.

### The non-negotiable capture list

Every item in this list is captured from week 1. Missing any of them means retraining from scratch later. In order of importance:

**Per generation event (research, email draft, phone script):**
1. Prompt fingerprint (hash of exact prompt + model + params + context)
2. Model name and version (e.g. `claude-opus-4-7`, Perplexity `sonar-deep-research`)
3. Raw output — before any human editing
4. Tokens consumed and latency
5. Timestamp and generating pipeline_run_id
6. Link to source lead

**Per SDR interaction:**
7. Send decision: sent-as-is / edited-then-sent / discarded
8. Full edited version (when edited) — we store the diff implicitly by comparing raw to sent
9. SDR identifier
10. Time between draft-created and action-taken

**Per recipient outcome:**
11. Delivery: delivered / bounced / deferred / marked-spam (from HubSpot engagement API)
12. Engagement: opened / clicked / replied
13. Reply content — full text, for later classification
14. Reply classification: interested / not-interested / polite-defer / confused / out-of-office / auto-responder
15. Time-to-reply

**Per deal trajectory:**
16. HubSpot stage: New → Qualified → Demo Booked → Proposal → Closed Won/Lost
17. Time in each stage
18. Win/loss reason (structured HubSpot property, not free text)
19. Final deal value (when closed-won)

This 19-point spec drives the schema. Every field traces back to one of these requirements.

### What we deliberately do NOT capture (yet)

- Call recordings and transcripts (pending legal review — see above)
- Personal information beyond work context (no home addresses, no personal phones unless publicly listed as business contact)
- SDR screen activity / keystroke-level data (privacy-invasive, low ROI)
- Email content from recipients that wasn't replying to us (respect for inbound communication we didn't solicit)

### The control stream

To prevent self-referential agent contamination, **20% of weekly leads** come from a deliberately segment-blind rule (e.g. "highest-scoring prospect in a random eligible segment, regardless of current strategy"). This provides an uncontaminated baseline when agents eventually shape the other 80%.

This is cheap (it's just a different SQL query each week) and pays for itself ten times over in year 2 when we need to answer "is Agent 1 actually helping, or just confirming its own bias?"

---

## Success criteria

### Phase 1 done when:
- Weekly scheduled job runs without manual intervention
- 50 leads/week land in Postgres and HubSpot with full briefings
- Michael can open a Contact in HubSpot and see an AI Briefing card with segment, score, research summary, and email drafts
- Admin web app shows run history and allows pausing/resuming
- Every 19-point capture requirement above is being recorded

### Phase 2 done when:
- Agent 1 runs every Sunday, produces a weekly strategic brief
- Michael reviews and approves segment mix for the week
- Pipeline run honours the approved mix

### Phase 3 done when:
- Agent 2 flags suspicious leads per batch
- Rubric drift dashboard exists
- 20+ closed deals exist for outcome analysis

### Year-one success looks like:
- A clean, labelled dataset of 2,000+ lead→outcome pairs
- Demonstrable correlation between rubric score and conversion rate (hypothesis: higher-scoring leads convert more; if not, rubric needs revising)
- Agent 1 recommendations tracking within ±15% of actual outcomes it predicted
- Sales team retained and actually using the system (adoption is the hardest KPI)
- **Optionality to begin narrow autonomous agent actions in Q4**

---

## What this is NOT

Being explicit about scope to prevent drift:

- **Not a CRM.** HubSpot is the CRM. This is an intelligence layer.
- **Not an email sender.** HubSpot sends. We draft.
- **Not an autonomous agent today.** Agents are advisory for ~6 months minimum.
- **Not a replacement for SDR judgement.** SDRs edit, discard, override. Their judgement is the training signal.
- **Not a B2B contact database.** We buy prospects from Vibe; we don't build a directory ourselves.
- **Not an outcome prediction system.** We observe outcomes, we don't predict them in v1. Prediction is a year-2 problem.

---

## Risks and how we address them

| Risk | Mitigation |
|------|------------|
| HubSpot API rate limits disrupt hourly sync | Exponential backoff, batch where possible, alerting on sustained failures |
| Vibe Prospecting upstream instability (seen in Run 3) | Retry with backoff; if fail persists, pipeline skips that week with clear alert. Better to miss a week than corrupt data |
| Training data contamination from agent recommendations | 20% control stream from day one |
| SDRs bypass HubSpot UI extension, system loses capture signal | Design UI extension so that viewing the AI briefing is *faster* than skipping it; measure adoption weekly |
| PDPL-related complaint about stored contact data | Suppression list in schema from day one; clear retention policy (12 months unengaged → soft delete); legal review before launch |
| Schema migration pain as requirements evolve | Alembic migrations from day one, every change reviewed, no ad-hoc DDL |
| Claude Code producing code that passes tests but has subtle bugs | Every task has acceptance criteria including edge cases; Michael reviews PRs; incremental deployment |
| Lead quality regresses silently over time | Agent 2 (Quality Reviewer) flags anomalies; weekly metric review |

---

## What happens next

This document is the first of four Phase 0 artefacts. The others:

1. **Schema specification** (`02-schema.md`) — complete Postgres DDL with commentary on every table and column. **← next deliverable**
2. **HubSpot integration contract** (`03-hubspot-contract.md`) — custom properties, push/pull spec, UI extension contract
3. **Repository scaffold + first 10 Claude Code tasks** (`04-repo-and-tasks.md`) — directory layout, stub files, prioritised implementation roadmap

Each document will be delivered separately so you can review and push back before the next one is produced.

The design is opinionated. Every opinion here is challengeable. If you disagree with a design decision — the HubSpot-native choice, the Python/TS split, the agent-as-advisor stance — flag it before we move to the schema, because the schema bakes these choices into tables.
