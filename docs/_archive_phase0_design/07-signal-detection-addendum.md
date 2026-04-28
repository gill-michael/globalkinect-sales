# Phase 1A Signal Detection Addendum

**Project:** Global Kinect Sales Intelligence
**Scope:** MVP signal ingestion layer alongside the Vibe-only prospect pipeline in Phase 1A
**Supersedes:** doc 06 §"The scrape source (placeholder)" — now specified
**Extends:** doc 02 schema with signal-layer tables
**Read order:** 01-vision → 02-schema → 03-hubspot-contract → 04-repo-and-tasks → 05-amendments → 06-phase1a-revised-plan → **THIS DOCUMENT**
**Last updated:** April 2026

---

## The decision this doc implements

Option Z from the architectural fork: **MVP signals in Phase 1A, full signals in Phase 1B.** Build the plumbing to ingest signals during the first 3 months, attach them to leads as metadata, learn which lanes earn their keep. Full upgrade (LLM classification, signal-aware generation prompts, webpage scrapers, multi-source dedupe) lands in Phase 1B once we have data.

The input to this work is `discovery_sources.json` — 8 lanes, 30+ sources, a genuinely sophisticated intent-detection taxonomy for the Global Kinect sales motion.

---

## What "MVP" means here

MVP signals in Phase 1A is deliberately small. The goal is:

1. Prove the plumbing works end-to-end: fetch → filter → store → attach → display
2. Generate enough data (signals + attached leads + outcomes) to learn which lanes convert
3. Avoid over-investing in sources that will turn out to be noise

**In scope for Phase 1A:**

- Seed the `signal_lanes` and `signal_sources` tables from the JSON file
- Fetch all `active: true` sources with `source_type: "rss"` on a daily cadence
- Match each entry against the source's `watch_keywords` (simple substring match in title + description)
- Store matched entries as `signal_events` rows
- Extract company names from titles using a conservative heuristic (titlecase tokens of 2+ words before " — " / " - " / " | " / verbs like "announces", "launches", "acquires")
- Canonical company resolution: against the `leads.company_name` and `leads.company_domain` in our DB, best-effort fuzzy match (Levenshtein or trigram)
- Attach matched signals to existing leads via `lead_signals`
- Surface attached signals on the lead's admin-app briefing page
- Track per-source fetch success/failure and entry yield in `signal_source_health`

**Explicitly out of scope for Phase 1A (moves to Phase 1B):**

- `source_type: "webpage_html"` scrapers (LinkedIn Jobs, GulfTalent) — need bespoke parsers, TOS-sensitive, high build cost
- `fetch_detail_pages: true` — the two-stage pattern where we fetch the linked article for deeper context. RSS summaries are enough for MVP filtering.
- LLM classifier on each entry ("is this really a signal or just filler?"). MVP uses keywords. LLM upgrade in 1B.
- Triggering Vibe lookups *from* a signal (when we detect "Acme Corp expansion" and Acme isn't in our leads DB yet, looking up Acme's CFO via Vibe). This is the high-ROI action but adds complexity. Deferred.
- Signal-aware prompt generation — our email drafts in Phase 1A don't yet reference attached signals as the hook. Drafts stay generic, signals are just visible metadata on the briefing page.
- Multi-signal scoring (does having 3 signals in 30 days boost the lead's rubric score?)
- The `Manual Strategic Accounts` lane — inline entries rather than feed scraping, different ingestion path, easy to add but distinct from the main flow. Skip for 1A.

**What "MVP signals in 1A" delivers to the SDR:**

When an SDR opens a lead in the admin app in week 10, they see:

```
Lead: Kashish Kohli (Group CFO @ The Sanad Group)
Score: 80

🚨 Recent signals attached to this company:
  • "Sanad Group announces Saudi expansion plans"
    — Saudi Gazette Business, 2 days ago
  • "Sanad Group finance hiring ramp"
    — Gulf News, 8 days ago

📄 Research (unchanged — Perplexity output)
✉️ Email sequence (unchanged — drafts don't yet reference signals)
📞 Phone script (on demand)
```

The SDR sees the signals. The AI drafts don't yet weave them in. That happens in Phase 1B.

---

## Schema additions

Four new tables + one column on `leads`. All additive — no changes to existing tables beyond that one column.

### `signal_lanes`

One row per lane. Config, seeded from JSON.

```sql
CREATE TABLE signal_lanes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug            TEXT NOT NULL UNIQUE,       -- 'expansion-signals', 'saudi-rhq', etc
    label           TEXT NOT NULL,              -- 'Expansion Signals'
    agent_label     TEXT NOT NULL,              -- 'EOR Expansion Agent'
    campaign        TEXT NOT NULL,              -- the campaign description from JSON
    service_focus   TEXT NOT NULL,              -- 'eor', 'hris', 'payroll' (most common focus in the lane)
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    priority        INTEGER NOT NULL DEFAULT 5,  -- affects display ordering; 10 = highest
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX signal_lanes_active ON signal_lanes (is_active) WHERE is_active;
```

**Seed data (8 rows):** Expansion Signals, Saudi RHQ Signals, Payroll Complexity, HRIS Maturity, European Multi-Country, Funding and Growth Signals, Manual Strategic Accounts, Direct Outbound Signals.

### `signal_sources`

One row per source (30+ rows seeded from JSON).

```sql
CREATE TABLE signal_sources (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lane_id                 UUID NOT NULL REFERENCES signal_lanes(id),

    -- Identity
    name                    TEXT NOT NULL,                  -- 'Tahawul Tech', 'Saudi Gazette Business'
    source_type             TEXT NOT NULL,                  -- 'rss', 'webpage_html', 'manual_signals'
    feed_url                TEXT,
    website_url             TEXT NOT NULL,

    -- Country scope
    source_country          TEXT,                           -- ISO-2 of the source itself, nullable
    target_countries        TEXT[] NOT NULL DEFAULT '{}',   -- ISO-2 list; signals flagged as relevant to these countries

    -- Hints
    lead_type_hint          TEXT,                           -- 'direct_eor', 'direct_payroll', etc
    service_focus           TEXT,                           -- 'eor', 'hris', 'payroll', 'bundle'

    -- Matching config
    watch_keywords          TEXT[] NOT NULL DEFAULT '{}',
    entry_url_keywords      TEXT[] NOT NULL DEFAULT '{}',   -- unused in 1A, for 1B detail-page fetching
    derive_company_name_from_title BOOLEAN NOT NULL DEFAULT TRUE,
    fetch_detail_pages      BOOLEAN NOT NULL DEFAULT FALSE, -- unused in 1A

    -- Operator control
    source_priority         INTEGER NOT NULL DEFAULT 5,     -- ordering within lane
    trust_score             INTEGER NOT NULL DEFAULT 5,     -- 1-10; feeds signal scoring
    is_active               BOOLEAN NOT NULL DEFAULT TRUE,

    -- Operational
    last_fetched_at         TIMESTAMPTZ,
    last_success_at         TIMESTAMPTZ,
    consecutive_failures    INTEGER NOT NULL DEFAULT 0,
    disabled_reason         TEXT,                           -- if auto-disabled due to repeated failures

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX signal_sources_lane ON signal_sources (lane_id);
CREATE INDEX signal_sources_active ON signal_sources (is_active) WHERE is_active;
CREATE INDEX signal_sources_type ON signal_sources (source_type);
```

**Why this structure:**

- `lane_id` is a hard reference — every source belongs to exactly one lane. No orphans.
- `watch_keywords` stored as `TEXT[]` for fast GIN indexing if matching becomes slow later
- `consecutive_failures` supports auto-disable after N failures (with manual re-enable via admin)
- `trust_score` from JSON — MVP uses it for display ordering only; 1B may weight signal scores by this
- `fetch_detail_pages`, `entry_url_keywords` stored but unused in 1A so the schema is 1B-ready

### `signal_events`

One row per matched RSS entry. The raw signal stream.

```sql
CREATE TABLE signal_events (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id               UUID NOT NULL REFERENCES signal_sources(id),

    -- Entry identity (from RSS)
    entry_guid              TEXT,                           -- RSS <guid> or equivalent; nullable
    entry_url               TEXT,                           -- canonical URL of the article
    entry_hash              TEXT NOT NULL,                  -- SHA256 of (source_id + entry_url + title) for dedupe

    -- Content
    title                   TEXT NOT NULL,
    summary                 TEXT,
    published_at            TIMESTAMPTZ,                    -- from RSS <pubDate>; may be null
    fetched_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Matching
    matched_keywords        TEXT[] NOT NULL,                -- which keywords from source.watch_keywords hit
    match_score             INTEGER NOT NULL,               -- simple: count of matched keywords; 1B will upgrade to LLM confidence

    -- Company extraction
    extracted_company_name  TEXT,                           -- heuristic extraction from title; may be NULL
    extraction_confidence   REAL NOT NULL DEFAULT 0.0,      -- 0.0-1.0
    extraction_method       TEXT NOT NULL DEFAULT 'heuristic', -- '1B will add 'llm'

    -- Operational
    is_discarded            BOOLEAN NOT NULL DEFAULT FALSE, -- operator flag: false positive, filler, etc
    discarded_reason        TEXT,
    discarded_by            UUID REFERENCES sales_users(id),
    discarded_at            TIMESTAMPTZ,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX signal_events_hash ON signal_events (entry_hash);
CREATE INDEX signal_events_source ON signal_events (source_id, published_at DESC);
CREATE INDEX signal_events_company ON signal_events (LOWER(extracted_company_name)) WHERE extracted_company_name IS NOT NULL;
CREATE INDEX signal_events_active ON signal_events (published_at DESC) WHERE NOT is_discarded;
```

**Why this structure:**

- `entry_hash` prevents double-ingesting the same RSS entry if the feed re-serves it
- `extracted_company_name` stored even when low-confidence — operator can correct; correction becomes training signal
- `is_discarded` lets operators reject false positives without deleting the row (keeps training corpus honest — "things our system thought were signals but weren't")
- `extraction_method = 'heuristic'` in 1A, `'llm'` in 1B — so we can analyse how much better LLM extraction is when it lands

### `lead_signals`

The many-to-many join. A lead can have multiple signals; a signal can attach to multiple leads.

```sql
CREATE TABLE lead_signals (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id                 UUID NOT NULL REFERENCES leads(id),
    signal_event_id         UUID NOT NULL REFERENCES signal_events(id),

    -- How this attachment was made
    attachment_method       TEXT NOT NULL,          -- 'auto-domain-match', 'auto-name-match', 'operator-manual'
    attachment_confidence   REAL NOT NULL DEFAULT 0.0,   -- 0.0-1.0

    -- Operator feedback (trains the matcher over time)
    is_confirmed            BOOLEAN,                -- NULL = not reviewed, TRUE = "yes, real match", FALSE = "no, mismatched"
    confirmed_by            UUID REFERENCES sales_users(id),
    confirmed_at            TIMESTAMPTZ,

    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (lead_id, signal_event_id)
);

CREATE INDEX lead_signals_lead ON lead_signals (lead_id, created_at DESC);
CREATE INDEX lead_signals_signal ON lead_signals (signal_event_id);
CREATE INDEX lead_signals_unreviewed ON lead_signals (created_at DESC) WHERE is_confirmed IS NULL;
```

**Why this structure:**

- `is_confirmed` = NULL means the operator hasn't reviewed. This is the cue for the admin app to surface "review this attachment" tasks.
- Operator corrections feed the training corpus: which attachment methods produce real matches vs false positives
- `attachment_confidence` lets us threshold what to display — high-confidence auto-attached shown prominently, low-confidence shown behind a "possible signals" expand

### `signal_source_health`

Operational history per source. Lightweight observability.

```sql
CREATE TABLE signal_source_health (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id               UUID NOT NULL REFERENCES signal_sources(id),

    fetched_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    status                  TEXT NOT NULL,              -- 'success', 'http-error', 'parse-error', 'timeout', 'empty-feed'
    http_status_code        INTEGER,
    entries_fetched         INTEGER NOT NULL DEFAULT 0,
    entries_matched         INTEGER NOT NULL DEFAULT 0,
    fetch_duration_ms       INTEGER,
    error_message           TEXT
);

CREATE INDEX signal_source_health_source ON signal_source_health (source_id, fetched_at DESC);
```

**Why this structure:**

- Answers "which sources are worth keeping" with data — if source X hasn't produced a matched entry in 30 days, it's a candidate for deactivation
- Helps debug auto-disabled sources (consecutive_failures triggered by what?)
- Informs Agent 0's weekly brief: "Source FOO had 40 entries but 0 matches this week — keywords may be mistuned"

### Column on `leads`

```sql
ALTER TABLE leads ADD COLUMN latest_signal_at TIMESTAMPTZ;
```

**Why:** denormalised for fast "show me leads with recent signals" queries in the admin app inbox. Updated by trigger or by the signal-attachment job. Without it, the inbox would need a JOIN against `lead_signals` + `signal_events` to rank leads by recency of signal, which is fine now but gets slow at year-2 volumes.

---

## Pipeline additions

Two new workers. Neither runs inside the weekly Vibe pipeline — they run on their own cadences.

### Signal ingestion worker

**Cadence:** daily, 04:00 UTC (before the weekly Vibe run on Mondays, but independent)

**Module:** `src/gk_sales/signals/ingest.py`

**Logic:**

```
For each active source where source_type='rss':

  1. Fetch feed URL with httpx + 30s timeout
     If HTTP error: log to signal_source_health, increment consecutive_failures
     If 5+ consecutive failures: auto-disable source with reason='repeated-failures'

  2. Parse feed (feedparser library handles RSS + Atom)

  3. For each entry:
     a. Compute entry_hash
     b. Skip if entry_hash already exists in signal_events
     c. Match title + summary against source.watch_keywords (case-insensitive substring)
     d. If any keyword matches:
        - Extract company name via heuristic (see below)
        - Insert signal_events row with matched_keywords, match_score, extraction info

  4. Log signal_source_health row

  5. Update source.last_fetched_at, last_success_at, consecutive_failures
```

**Company name extraction heuristic:**

Conservative. Better to extract nothing than to extract noise.

```
Given a title like "Acme Corp announces Saudi expansion":

  1. Split on common separators: " - ", " — ", " | ", " announces ", " launches ",
     " acquires ", " wins ", " raises ", " opens "
  2. Take the LEFT side (typically the subject)
  3. Strip common prefixes: "BREAKING:", "NEWS:", "UPDATE:"
  4. Require: 2-6 words, all Title Case or ALL CAPS, no trailing punctuation
  5. If matches criteria → extracted_company_name, confidence 0.7
  6. If no split matched → try first 2-5 Title Case words
     → confidence 0.4
  7. If nothing plausible → NULL, confidence 0.0
```

This will miss many real company names and misidentify some ("Saudi Arabia" as a company). That's expected. LLM extraction in 1B fixes this. MVP priority: don't produce garbage.

### Signal attachment worker

**Cadence:** hourly (light job)

**Module:** `src/gk_sales/signals/attach.py`

**Logic:**

```
For each signal_events row where no lead_signals attachment exists yet
AND extracted_company_name IS NOT NULL
AND NOT is_discarded:

  1. Normalise extracted_company_name (lowercase, strip " group", " ltd", " llc", etc)

  2. Try exact match against leads.company_name (normalised):
     - If 1 match: insert lead_signals with method='auto-name-match', confidence 0.8
     - If >1 match: create lead_signals for each, confidence 0.5 (ambiguous)

  3. Try domain match if extraction yielded a URL:
     - If signal_events.entry_url contains a company domain,
       and that domain matches leads.company_domain: attach with 0.9 confidence

  4. Update leads.latest_signal_at for each attached lead

  5. Leave signal_events without matches untouched. Future leads from Vibe may
     match them retrospectively (signal_events rows are timeless — they live on).
```

**What 1A does NOT do:** trigger a Vibe lookup when a signal has no matching lead. That would be high-ROI ("we just saw Acme Corp expansion — find Acme's CFO") but it's the kind of thing that compounds cost quickly if the signal stream is noisy. Defer to 1B once we know the noise floor.

---

## Admin app additions

Three new surfaces in the admin app for Phase 1A:

### 1. Signal feed (Michael only)

**Route:** `GET /signals`

Shows the last 100 signals ingested, sortable by source, lane, company, date. Each row has:
- Date + source
- Title + summary snippet
- Extracted company (with confidence indicator)
- Attached to: [list of lead names] or "not attached"
- Actions: [Discard as false positive] [Attach manually to lead...]

Lets Michael sanity-check the signal stream and correct false positives. Corrections train the heuristic.

### 2. Signal lane admin (Michael only)

**Route:** `GET /signals/lanes`, `GET /signals/sources`

Toggle `is_active` on lanes and sources. View health metrics (entries fetched, matched, consecutive failures). Edit `watch_keywords`.

### 3. Signal attachment panel on lead briefing

**Route modification:** `GET /leads/{id}`

Adds a prominent section above the research:

```
🚨 Recent signals attached to this company (3)

  ▸ "Sanad Group announces Saudi expansion plans"
    — Saudi Gazette Business · 2 days ago · Expansion Signals lane
    [View article] [Not a match] [Confirm match]

  ▸ "Sanad Group finance hiring ramp"
    — Gulf News · 8 days ago · HRIS Maturity lane
    [View article] [Not a match] [Confirm match]

  ▸ (1 older signal — show all)
```

When the SDR clicks "Not a match", the `lead_signals.is_confirmed` is set to FALSE. When they click "Confirm match", set TRUE. Both corrections are training data.

### 4. Agent 0's weekly brief gains a signal section

Already planned to run week 5+. With signals in play, the brief includes:

- Total signals ingested this week, per lane
- Sources with zero matches this week (suggest review)
- Top companies by signal count
- Leads that gained signals this week

---

## New task list entries for Phase 1A

Adds three tasks to doc 06's sequence. These land after Task 08 (generation) but can run in parallel with Task 08.5 (admin app) if you have bandwidth.

### Task 04b — Signal source seed migration and `ProspectSource` extension

**Goal:** Load `discovery_sources.json` into the database; define the signal-source abstraction.

**Inputs:** Task 03 merged (schema has signal_lanes, signal_sources, etc).

**Outputs:**
- `migrations/versions/0002_seed_signal_lanes_sources.py` — reads `config/discovery_sources.json` at migration time, inserts lanes and sources
- `src/gk_sales/signals/models.py` — Pydantic models matching the JSON shape (validation at load time)
- Unit tests verifying: 8 lanes inserted, 25+ active RSS sources inserted, malformed source entries rejected with clear error
- `config/discovery_sources.json` committed to the repo (source of truth)

**Acceptance:**
- Running migration inserts exact expected counts
- Re-running migration is idempotent (UPSERT on slug / name)
- Pydantic validation catches malformed entries (unknown source_type, missing required fields)

**Estimated effort:** Small. 1-2 hours.

### Task 09a — Signal ingestion worker (Phase 1A)

**Goal:** Build the daily RSS fetch and match worker.

**Inputs:** Tasks 03, 04b merged.

**Outputs:**
- `src/gk_sales/signals/ingest.py` — the daily worker
- `src/gk_sales/signals/rss.py` — feedparser wrapper with retry, timeout, caching
- `src/gk_sales/signals/extract.py` — company name heuristic
- `src/gk_sales/signals/match.py` — keyword matcher
- `scripts/run_signal_ingest_once.py` — manual trigger for testing
- Integration tests with mocked feeds covering: happy path, HTTP error, malformed XML, empty feed, no matches, all-entries-match, duplicate entry_hash
- A `@pytest.mark.live` test that fetches 2-3 real RSS sources (Menabytes, Gulf News) to verify the pipeline works against real data

**Acceptance:**
- `python scripts/run_signal_ingest_once.py --source menabytes` fetches, matches, inserts without error
- Running twice doesn't duplicate signal_events (entry_hash uniqueness)
- Failing source (bad URL) logs to health table, increments consecutive_failures, doesn't break other sources
- After 5 failures, source is auto-disabled with `disabled_reason='repeated-failures'`

**Estimated effort:** Medium. 3-5 hours.

### Task 09b — Signal attachment worker (Phase 1A)

**Goal:** Hourly worker that attaches signals to existing leads.

**Inputs:** Task 09a merged, some real signal_events in the DB.

**Outputs:**
- `src/gk_sales/signals/attach.py` — the hourly worker
- Name normalisation logic (strip group, ltd, llc; lowercase; handle Arabic transliteration variants with a small lookup table seeded with common cases)
- Unit tests covering: exact match, fuzzy match, ambiguous match, no match, already-attached skip
- Integration test: 10 signals + 10 leads, verify correct attachments

**Acceptance:**
- Signals with extracted_company_name matching a lead's company_name get attached with method='auto-name-match'
- Domain match beats name match if both available
- Re-running doesn't create duplicate lead_signals rows (UNIQUE constraint)
- `leads.latest_signal_at` updated for every affected lead

**Estimated effort:** Small-medium. 2-3 hours.

### Task 08.5 amendment — signal display on lead page

**Addition to Task 08.5:** the `/leads/{id}` template gains the signal section described above. Signal feed routes (`/signals`, `/signals/lanes`, `/signals/sources`) added to admin-only section.

**Estimated additional effort:** 2-3 hours on top of Task 08.5's base.

---

## Cloud Scheduler entries

Two new jobs to configure in Task 00 preflight (or as part of 09a/09b):

```
signal-ingest:  daily at 04:00 UTC  →  POST /jobs/signal-ingest
signal-attach:  hourly              →  POST /jobs/signal-attach
```

Both are authenticated internal endpoints on the admin app (not publicly exposed).

---

## Revised Phase 1A cost estimate

Adding to the earlier ~$1,000 estimate:

- **RSS fetching:** negligible, maybe 250 feed fetches/day × 30-day month = 7,500 requests. No AI cost yet (no LLM classification in 1A). Network cost ≈ $0.
- **Cloud Scheduler:** 2 additional schedules, free tier covers this easily
- **Postgres storage:** signal_events could accumulate 1-5k rows/week. Trivial.

**Signal ingestion in Phase 1A adds ~$0/month.** The cost lands in 1B when we add LLM classification (probably ~$30/month at the observed volume).

---

## Honest risks and open questions

**1. The MISA RSS feed (trust score 10) may not exist.**
My pre-build check suggests the `misa.gov.sa/rss` URL is aspirational — couldn't confirm the feed actually publishes RHQ registrations as RSS. The ingestion worker's health tracking will surface this within the first week. If it doesn't work, we either find an alternative RHQ-registration source (MEED sometimes covers these) or accept the lane is weaker than hoped.

**2. The heuristic company name extraction will be noisy.**
Expect 40-60% false positive extraction rate initially. The admin signal feed view exists specifically so you can mark false positives; those corrections inform the 1B LLM classifier prompt.

**3. Signals and leads may not overlap much for the first 4-6 weeks.**
Vibe pulls prospects; signals detect companies in the news. For the first batch of Vibe leads there may be very few signal matches. As the database grows, overlap increases. Don't judge the system's value from week 2 signal-attachment rates — give it 6-8 weeks.

**4. Some feeds are almost certainly dead or low-value.**
Of the 30+ sources, I'd estimate 5-8 will produce zero usable signals in the first month. That's fine — the health tracking tells you which to cut. Don't pre-trim; let data decide.

**5. No LLM classification means we'll match false-positive entries.**
An article titled "Hiring Manager at Construction Firm Shares Tips" would match the Payroll Complexity lane's `hiring` keyword but isn't a real signal. MVP accepts this noise. Operator discards train the 1B classifier.

---

## What this means for the Phase 1A timeline

Original Phase 1A estimate (from doc 06): ~40-60 hours of Claude Code work across 4-6 weeks.

Signal additions: +6-10 hours across 3 new tasks (04b + 09a + 09b + small 08.5 amendment).

**Revised total:** 50-70 hours, 5-7 weeks of elapsed build time.

Signals should land by week 6-7, operating on real data through weeks 8-12 before the Phase 1B decision point.

---

## Phase 1B signal upgrades (preview)

When HubSpot upgrade commits in month 4, the signal layer gets these upgrades:

1. **LLM classification.** Replace keyword match with Claude Haiku assessing each entry against the lane's campaign thesis. Expected signal precision lifts 40% → 80%.
2. **Detail page fetching.** For high-match-score entries, fetch the linked article for fuller context. Enables better company extraction and lets signals inform prompt hooks.
3. **Webpage_html scrapers.** LinkedIn Jobs, GulfTalent — bespoke parsers with proxy rotation. TOS-sensitive work, timing matters.
4. **Signal-aware prompt generation.** Email drafts reference attached signals as specific hooks. This is where the conversion lift happens.
5. **Signal-triggered Vibe lookups.** Detected signal at Acme Corp, no lead yet → trigger Vibe enrichment on Acme to find CFO. High-ROI, high-complexity.
6. **Multi-signal scoring.** Leads with 3+ signals in 30 days get a rubric bonus.
7. **Manual Strategic Accounts lane** implementation — operator uploads curated accounts, they receive highest-priority treatment.

Each is a discrete Phase 1B task. None of them block Phase 1A operation.

---

## Review checklist before Claude Code starts signal work

- [ ] Agreed to MVP scope (RSS-only, keyword match, heuristic extraction)
- [ ] Comfortable that some sources will turn out dead/noisy — data decides which to cut
- [ ] Understand signal attachments will be manually reviewable (false positives expected)
- [ ] Signals attach to leads but drafts don't yet use them (that's 1B)
- [ ] 4 new tables is acceptable schema expansion
- [ ] Agree to not trigger Vibe lookups from signals in 1A (deferred to 1B)
- [ ] The `Manual Strategic Accounts` lane is explicitly deferred to 1B

Once ticked, the signal tasks are ready for Claude Code execution after the foundational Tasks 01-08 land.
