# GlobalKinect — Sales Discovery Engine Tasklist
# Location: C:\dev\globalkinect-engines\sales
# Last updated: 5 April 2026

---

## Status key
- [ ] Not started
- [~] In progress
- [x] Complete
- [!] Blocked / needs decision
- [M] Manual — you do this
- [CC] Claude Code task — run in VS Code
- [N] Notion AI — run inside Notion itself
- [→ PROMPT] Come back here to get the Claude Code prompt before starting this task

---

## BEFORE YOU START ANYTHING

Confirm these files exist in C:\dev\globalkinect-engines\sales\ root:
- [ ] GLOBALKINECT_BRAND.md
- [ ] GLOBALKINECT_ICP.md
- [ ] GLOBALKINECT_BRAND_TOKENS.json
- [ ] discovery_sources.json (8 lanes already built)
- [ ] .env (to be created)

Every Claude Code session must begin with:
"Read GLOBALKINECT_BRAND.md and GLOBALKINECT_ICP.md in the repo root before
writing any code. Every outreach draft the agents produce must pass the quality
checklist in GLOBALKINECT_BRAND.md and use the ICP-specific hooks and pain
language from GLOBALKINECT_ICP.md."

---

## SECTION 1 — PREREQUISITES
### Complete these before any code or Notion work

| # | Task | Type | Time | Notes |
|---|------|------|------|-------|
| 1.1 | Get Anthropic API key | [M] | 5 min | console.anthropic.com → API Keys → Create key. Same key as social engine. |
| 1.2 | Create Notion integration token | [M] | 5 min | notion.so/my-integrations → New integration → name: "GlobalKinect Sales Engine" → copy Internal Integration Token. Can reuse the same integration as social engine or create a separate one. |
| 1.3 | Create Supabase project | [M] | 10 min | Can be same project as social engine (different tables) or a separate project. Note URL and service role key. |
| 1.4 | Sign up for Apollo.io | [M] | 10 min | apollo.io → Basic plan (~£70/month). Needed for verified email extraction. Can start without it — discovery runs, emails come later. |
| 1.5 | Create .env file in sales repo root | [M] | 5 min | Create from scratch — no .env.example exists yet. Claude Code will produce the .env.example in Section 3. |
| 1.6 | Create private GitHub repo for scheduler | [M] | 5 min | github.com → New repo → "globalkinect-engine-scheduler" → private. Can be same repo as social engine scheduler. |

---

## SECTION 2 — NOTION SETUP FOR SALES PIPELINE
### Run these inside Notion using Notion AI before code runs

| # | Task | Type | Time | Notes |
|---|------|------|------|-------|
| 2.1 | Create GlobalKinect Sales Pipeline page in Notion | [N] | 3 min | Notion AI prompt: "Create a page called GlobalKinect Sales Pipeline. At the top add a short description: This is the operator-facing workspace for the GlobalKinect sales discovery engine. Add section headings: Pipeline Dashboard, Leads Database, Outreach Sequences, Discovery Feed, Setup Notes." |
| 2.2 | Create Leads database | [N] | 10 min | Notion AI prompt: "Inside the GlobalKinect Sales Pipeline page, create a full-page database called Leads. Create these properties exactly: Company Name (title), ICP Segment (select: A1 Frustrated GCC Operator / A2 GCC SME / A3 Scaling GCC Business / B1 European Multi-Country / B2 UK Domestic / B3 International GCC Expander / B4 European GCC Bridge), Country (select: UAE / Saudi Arabia / Qatar / Kuwait / Bahrain / Oman / Egypt / United Kingdom / Ireland / Sweden / Germany / France / Netherlands / Other), Trigger Event (rich text), Discovery Source (select: GCC Expansion / Saudi RHQ / Payroll Complexity / HRIS Maturity / European Multi-Country / Funding Signals / Manual Strategic / Direct Outbound), Contact Name (rich text), Contact Title (rich text), LinkedIn URL (URL), Company Website (URL), Company Email (email), Company Size (select: 10-50 / 50-200 / 200-500 / 500+), ICP Score (number, 0-100), Status (select: New / Researching / Draft Ready / Sent / Replied / Demo Booked / Disqualified), Discovery Date (date), Outreach Draft (rich text), Notes (rich text). Also add Created Time and Last Edited Time." |
| 2.3 | Create Outreach Sequences database | [N] | 10 min | Notion AI prompt: "Inside the GlobalKinect Sales Pipeline page, create a full-page database called Outreach Sequences. Create these properties exactly: Sequence Name (title), ICP Segment (select: A1 / A2 / A3 / B1 / B2 / B3 / B4), Channel (select: LinkedIn / Email / Both), Hook (rich text), Message 1 Connection Request (rich text), Message 2 Follow Up (rich text), Message 3 Demo Ask (rich text), Email Subject 1 (rich text), Email Body 1 (rich text), Email Subject 2 (rich text), Email Body 2 (rich text), Email Subject 3 (rich text), Email Body 3 (rich text), Status (select: Active / Draft / Paused), Last Updated (Last edited time)." |
| 2.4 | Create Pipeline Runs database | [N] | 5 min | Notion AI prompt: "Inside the GlobalKinect Sales Pipeline page, create a full-page database called Pipeline Runs. Create these properties: Run Date (date, title), Signals Found (number), Leads Qualified (number), Leads Added to Notion (number), Leads Deduplicated (number), Run Status (select: Success / Partial / Failed), Notes (rich text), Created Time." |
| 2.5 | Create Pipeline Dashboard view | [N] | 5 min | Notion AI prompt: "Inside the Pipeline Dashboard section of the GlobalKinect Sales Pipeline page, create a linked database view of the Leads database called Active Pipeline. Board view, grouped by Status. Show: Company Name, ICP Segment, Country, ICP Score, Discovery Date. Filter: Status is not Disqualified." |
| 2.6 | Create Daily Discovery Feed view | [N] | 3 min | Notion AI prompt: "Inside the Pipeline Dashboard section, create a linked database view of the Leads database called Daily Discovery Feed. Table view. Filter: Status is New. Sort: Discovery Date descending. Show: Company Name, ICP Segment, Country, Trigger Event, ICP Score, Discovery Source, Outreach Draft." |
| 2.7 | Create High Score view | [N] | 3 min | Notion AI prompt: "Inside the Pipeline Dashboard section, create a linked database view of the Leads database called Priority Leads. Table view. Filter: ICP Score is greater than or equal to 70 AND Status is Draft Ready. Sort: ICP Score descending. Show all properties." |
| 2.8 | Share all databases with the Notion integration | [M] | 5 min | Leads, Outreach Sequences, Pipeline Runs → Share → Invite the sales engine integration → Editor access |
| 2.9 | Copy database IDs to .env | [M] | 5 min | NOTION_LEADS_DB_ID, NOTION_SEQUENCES_DB_ID, NOTION_PIPELINE_RUNS_DB_ID |

---

## SECTION 3 — CLAUDE CODE: Scaffold the sales engine repo
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to scaffold the GlobalKinect sales discovery engine repo from scratch"

| # | Task | Type | Notes |
|---|------|------|-------|
| 3.1 | Create repo folder structure | [CC] | app/__init__.py, app/agents/__init__.py, app/services/__init__.py, app/models/__init__.py, app/orchestrators/__init__.py, app/utils/__init__.py, tests/__init__.py, main.py, requirements.txt, pytest.ini, .env.example, .gitignore |
| 3.2 | Create app/utils/logger.py | [CC] | Identical to social engine logger. BASE_LOGGER_NAME = "globalkinect_sales". |
| 3.3 | Create app/services/config.py | [CC] | Load from .env: ANTHROPIC_API_KEY, ANTHROPIC_MODEL, NOTION_API_KEY, NOTION_LEADS_DB_ID, NOTION_SEQUENCES_DB_ID, NOTION_PIPELINE_RUNS_DB_ID, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, APOLLO_API_KEY. is_anthropic_configured(), is_notion_configured(), is_supabase_configured(), is_apollo_configured(). |
| 3.4 | Create .env.example | [CC] | Document all env vars with comments explaining each one. |
| 3.5 | Create requirements.txt | [CC] | anthropic, pydantic, python-dotenv, supabase, notion-client, pytest, requests (for Apollo). |
| 3.6 | Create app/services/discovery_config.py | [CC] | Load and parse discovery_sources.json from repo root. get_all_lanes() returns list of lane configs. get_lane_queries(lane_name) returns search queries for a lane. |
| 3.7 | Write tests/test_setup.py | [CC] | Test config loads, discovery_sources.json is valid, all required lane structure is present. |

---

## SECTION 4 — CLAUDE CODE: Build the data models
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to build the Pydantic data models for the GlobalKinect sales discovery engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 4.1 | Create app/models/discovery_signal.py | [CC] | DiscoverySignal: signal_reference (str), source_lane (str), raw_text (str), url (str | None), discovered_at (datetime), relevance_score (float 0-1), company_name_hint (str | None), country_hint (str | None), trigger_type (str | None). |
| 4.2 | Create app/models/lead.py | [CC] | Lead: lead_reference (str), company_name (str), icp_segment (Literal — all 8 ICPs), country (str), trigger_event (str), discovery_source (str), contact_name (str | None), contact_title (str | None), linkedin_url (str | None), company_website (str | None), contact_email (str | None), company_size_estimate (str | None), icp_score (int 0-100), status (Literal: new/researching/draft_ready/sent/replied/demo_booked/disqualified), discovery_date (datetime), outreach_draft (str | None), notes (str | None). |
| 4.3 | Create app/models/outreach_sequence.py | [CC] | OutreachSequence: sequence_name (str), icp_segment (str), channel (Literal: linkedin/email/both), hook (str), message_1 (str), message_2 (str | None), message_3 (str | None), email_subject_1 (str | None), email_body_1 (str | None), status (Literal: active/draft/paused). |
| 4.4 | Create app/models/pipeline_run.py | [CC] | PipelineRun: run_reference (str), run_date (datetime), signals_found (int), leads_qualified (int), leads_added (int), leads_deduplicated (int), run_status (Literal: success/partial/failed), notes (str). |
| 4.5 | Create app/models/__init__.py | [CC] | Export all models. |

---

## SECTION 5 — CLAUDE CODE: Build the Claude service with web search
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to build the Claude service with web search tool enabled for the sales discovery engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 5.1 | Create app/services/claude_service.py | [CC] | Claude Sonnet wrapper. CRITICAL: web_search tool must be enabled on every API call — this is what powers discovery. generate_text(prompt, system=None) and generate_structured_output(prompt, schema, system=None). Error classes: ClaudeConfigurationError, ClaudeResponseError. Load GLOBALKINECT_BRAND.md and GLOBALKINECT_ICP.md at init — pass as system context on every call. |
| 5.2 | Test Claude service with web search | [CC] | tests/test_claude_service.py — mock the Anthropic API, verify web_search tool is included in every request, verify brand context is in every system message. |

---

## SECTION 6 — CLAUDE CODE: Build the discovery agent
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to build the discovery agent for the GlobalKinect sales engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 6.1 | Create app/agents/discovery_agent.py | [CC] | For each lane in discovery_sources.json: build a targeted search query, call Claude with web search tool, parse the results, extract signals, score each for relevance. System prompt must include full GLOBALKINECT_ICP.md so Claude scores signals against all 8 ICP profiles accurately. Output: list of DiscoverySignal per lane. Failure on one lane does not stop other lanes. |
| 6.2 | Build ICP-aware search query construction | [CC] | Each lane from discovery_sources.json has search criteria. The agent builds queries that surface the right trigger signals — Saudi RHQ announcements, funding signals, HR Director job postings in GCC, multi-country payroll complexity signals, UK companies winning GCC contracts, etc. |
| 6.3 | Build signal relevance scorer | [CC] | After web search returns results, Claude scores each result 0-1 for relevance to GlobalKinect ICPs. Signals below 0.4 are discarded. Output includes company_name_hint and country_hint extracted from each signal. |
| 6.4 | Write tests/test_discovery_agent.py | [CC] | Mock Claude API and web search responses. Test each lane produces signals. Test low-relevance signals are filtered. |

---

## SECTION 7 — CLAUDE CODE: Build the enrichment agent
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to build the enrichment agent for the GlobalKinect sales engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 7.1 | Create app/agents/enrichment_agent.py | [CC] | Takes a DiscoverySignal. Calls Claude with web search to build a company profile: what they do, estimated headcount, countries of operation, industry, likely payroll setup (signs of fragmentation, spreadsheet use, multiple bureaus), growth signals, any named HR or Finance leaders. Returns enriched Lead model with all fields populated where discoverable. |
| 7.2 | Add LinkedIn profile extraction | [CC] | As part of enrichment: search for the most relevant contact at the company — HR Director, Finance Director, CPO, COO — and extract their LinkedIn profile URL if publicly findable. |
| 7.3 | Write tests/test_enrichment_agent.py | [CC] | Mock Claude API. Test that enrichment produces a valid Lead model. Test graceful handling when company info is limited. |

---

## SECTION 8 — CLAUDE CODE: Build the ICP scoring agent
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to build the ICP scoring agent for the GlobalKinect sales engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 8.1 | Create app/agents/icp_scoring_agent.py | [CC] | Takes an enriched Lead. Reads all 8 ICP profiles from GLOBALKINECT_ICP.md. Scores the lead 0-100 against the best-matching ICP profile. Scoring criteria: company size match (20 pts), country match (20 pts), pain signals present — fragmentation, spreadsheets, manual process (25 pts), trigger event quality — Saudi RHQ, funding, GCC expansion, new contract (20 pts), contact title match — HR Director/CFO/CPO/COO (15 pts). Assigns icp_segment. Threshold: score ≥ 60 = qualified lead. Score < 60 = disqualified. |
| 8.2 | Add scoring rationale to lead notes | [CC] | Append a brief scoring rationale to lead.notes so you can see why each lead was scored the way it was when reviewing in Notion. |
| 8.3 | Write tests/test_icp_scoring_agent.py | [CC] | Test scoring against representative lead profiles. A GCC HR Director at a 200-person multi-country company should score ≥ 80 as A1. A UK company with a Saudi RHQ announcement should score ≥ 70 as B3. |

---

## SECTION 9 — CLAUDE CODE: Build the deduplication agent
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to build the deduplication agent for the GlobalKinect sales engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 9.1 | Create app/agents/deduplication_agent.py | [CC] | Before saving a lead, check Supabase leads table for existing entry by company_name + country combination. If exists and status is not disqualified, skip. If exists and status is disqualified, also skip. Return: is_duplicate (bool), existing_lead_reference (str | None). |
| 9.2 | Add fuzzy company name matching | [CC] | "Accenture Middle East" and "Accenture UAE" should match. Use simple string normalisation — lowercase, strip legal suffixes (Ltd, LLC, Inc, DMCC), compare. Not ML — just clean string logic. |
| 9.3 | Write tests/test_deduplication_agent.py | [CC] | Test that exact duplicates are caught. Test that fuzzy matches are caught. Test that different companies with similar names are not incorrectly deduplicated. |

---

## SECTION 10 — CLAUDE CODE: Build the outreach draft agent
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to build the outreach draft agent for the GlobalKinect sales engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 10.1 | Create app/agents/outreach_draft_agent.py | [CC] | Takes a qualified Lead + icp_segment. Reads the matching ICP profile from GLOBALKINECT_ICP.md — extracts: who they are, pain in their words, what they need to hear, hook, entry CTA. Drafts a personalised first message. Two output formats: LinkedIn connection request note (max 300 chars) and LinkedIn follow-up message (max 400 words). Brand rules enforced from GLOBALKINECT_BRAND.md. |
| 10.2 | Build ICP-aware personalisation | [CC] | The draft must reference the specific trigger event found during discovery. Saudi RHQ announcement → reference it. Funding round → reference it. Multi-country job posting → reference it. Generic drafts are not acceptable — every draft must be specific to why this company, why now. |
| 10.3 | Add brand quality enforcement to draft | [CC] | After generating: check zero instances of "partner network", "Global Kinect" with space, "30+ countries", EOR-first positioning, "Get a Quote". If any found: regenerate or flag as needs_review. |
| 10.4 | Add cold email draft output | [CC] | Second output format: email subject + email body (max 150 words). For B-segment leads where email is more appropriate than LinkedIn. Same ICP personalisation and brand rules. |
| 10.5 | Write tests/test_outreach_draft_agent.py | [CC] | Mock Claude API. Test A1 draft uses GCC fragmentation pain language. Test B3 draft references Saudi RHQ. Test brand quality checks catch violations. Test LinkedIn note is within 300 chars. |

---

## SECTION 11 — CLAUDE CODE: Build the orchestrator
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to build the discovery orchestrator for the GlobalKinect sales engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 11.1 | Create app/orchestrators/discovery_orchestrator.py | [CC] | run_daily_discovery() method. Flow: load lanes from discovery_config → for each lane: run discovery_agent → enrich each signal via enrichment_agent → score via icp_scoring_agent → deduplicate via deduplication_agent → if qualified and not duplicate: draft outreach via outreach_draft_agent → save to Supabase → sync to Notion. Item-level failures do not crash the run — log and continue. Return PipelineRun summary. |
| 11.2 | Add run summary and logging | [CC] | Log: X lanes searched, Y signals found, Z leads qualified, W deduplicated, V added to Notion. Save PipelineRun to Supabase and Notion Pipeline Runs database. |
| 11.3 | Create main.py | [CC] | Entry point. Instantiate config, check is_anthropic_configured(). Run discovery_orchestrator.run_daily_discovery(). Print PipelineRun summary. Graceful exit on config errors. |
| 11.4 | Write tests/test_discovery_orchestrator.py | [CC] | Mock all agents. Test full pipeline flow. Test that failures in one lane do not stop the run. Test that PipelineRun is correctly populated. |

---

## SECTION 12 — CLAUDE CODE: Wire Supabase persistence
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to wire Supabase persistence for the GlobalKinect sales engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 12.1 | Create Supabase migration file | [CC] | supabase/migrations/20260406000000_sales_pipeline_init.sql. Tables: leads (all Lead model fields, lead_reference as primary key), discovery_signals (all DiscoverySignal fields), pipeline_runs (all PipelineRun fields). Indexes: leads by company_name + country (for deduplication), leads by icp_segment, leads by status, leads by discovery_date desc. RLS enabled. |
| 12.2 | Run migration in Supabase | [M] | Supabase dashboard → SQL Editor → paste migration → Run. Verify tables created. |
| 12.3 | Create app/services/supabase_service.py | [CC] | Supabase Python client wrapper. upsert(table, data), select(table, filters, order), delete(table, filters). Graceful error handling. |
| 12.4 | Create app/services/lead_store.py | [CC] | save_lead(lead), save_signal(signal), save_pipeline_run(run), get_existing_lead(company_name, country) for deduplication, load_qualified_leads(status_filter). |
| 12.5 | Wire lead_store into orchestrator | [CC] | Replace any in-memory storage with lead_store calls in discovery_orchestrator.py. |
| 12.6 | Test persistence | [CC] | Run python main.py with Supabase configured. Verify leads, signals, and pipeline run appear in Supabase dashboard. |

---

## SECTION 13 — CLAUDE CODE: Wire Notion sync
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to wire Notion sync for the GlobalKinect sales engine"

| # | Task | Type | Notes |
|---|------|------|-------|
| 13.1 | Create app/services/notion_service.py | [CC] | Notion client wrapper. create_lead_page(lead), update_lead_status(lead_reference, status), query_leads(filters), create_pipeline_run_page(run). Property names must match exactly what Notion AI created in Section 2 — especially the ICP Segment select options and Status select options. |
| 13.2 | Wire notion sync into orchestrator | [CC] | After save_lead() to Supabase: call notion_service.create_lead_page(). After pipeline run: call notion_service.create_pipeline_run_page(). |
| 13.3 | Test Notion sync | [CC] | Run python main.py. Verify lead pages appear in Notion Leads database with correct properties. Verify pipeline run appears in Pipeline Runs database. |

---

## SECTION 14 — CLAUDE CODE: Apollo integration for verified emails
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to add Apollo.io email enrichment to the GlobalKinect sales engine"
### NOTE: Only needed when outreach is going live. Can skip initially.

| # | Task | Type | Notes |
|---|------|------|-------|
| 14.1 | Create app/services/apollo_service.py | [CC] | Apollo.io API wrapper. search_people(name, company, title) returns people results. get_email(linkedin_url) returns verified email if available. enrich_company(domain) returns company data. Handle rate limits and 429 responses with exponential backoff. |
| 14.2 | Add Apollo enrichment to enrichment_agent.py | [CC] | After basic enrichment: if contact_name and company_website known, call apollo_service to get verified email. Add to lead.contact_email. Only if is_apollo_configured(). |
| 14.3 | Test Apollo integration | [CC] | With valid Apollo API key: test search_people returns results. Test graceful failure when email not found. |

---

## SECTION 15 — MANUAL: Write outreach sequences
### Do these yourself. Claude can help draft — ask "Help me write a LinkedIn outreach sequence for ICP A1 using GLOBALKINECT_ICP.md"

| # | Task | Type | Time | Notes |
|---|------|------|------|-------|
| 15.1 | Write sequence for ICP A1 — Frustrated GCC Operator | [M] | 30 min | 3-message LinkedIn sequence. Hook: "Still sending spreadsheets to separate bureaus in each country?" Message 1 (connection note, 300 chars): recognition of their pain. Message 2 (follow-up after connect): specific to their country mix, platform capability. Message 3 (demo ask): direct, specific, no slides. Ask here for a draft prompt. |
| 15.2 | Write sequence for ICP A3 — Scaling GCC Business | [M] | 30 min | Hook: "You're scaling fast. Your payroll setup isn't." Focus on speed, Saudization compliance, HRIS. Ask here for a draft prompt. |
| 15.3 | Write sequence for ICP B1 — European Multi-Country | [M] | 30 min | Hook: "Replace your fragmented country-by-country payroll setup with one clean platform." Focus on consolidation ROI, no country-specific complexity. Ask here for a draft prompt. |
| 15.4 | Write sequence for ICP B3 — International GCC Expander | [M] | 30 min | Hook: "Your global platform doesn't know the GCC like we do." Saudi RHQ trigger version and standard version. Ask here for a draft prompt. |
| 15.5 | Write cold email sequence for ICP B3 | [M] | 30 min | 3-email sequence. Email 1: trigger-aware opener referencing GCC expansion or Saudi RHQ. Email 2: compliance depth proof point. Email 3: direct demo ask. Max 150 words each. Ask here for a draft prompt. |
| 15.6 | Write cold email sequence for ICP B1 | [M] | 30 min | 3-email sequence. Focus on fragmentation cost and consolidation. Ask here for a draft prompt. |
| 15.7 | Enter all sequences into Notion Outreach Sequences database | [M] | 20 min | Manually create a page per sequence in Notion. |
| 15.8 | Wire sequences to outreach_draft_agent | [CC] | — | → PROMPT: "Give me the Claude Code prompt to load outreach sequences from Notion into the outreach draft agent as personalisation templates" |

---

## SECTION 16 — CLAUDE CODE: GitHub Actions scheduler
### → PROMPT: Come back here before starting. Ask: "Give me the Claude Code prompt to set up GitHub Actions for the sales discovery engine daily run"

| # | Task | Type | Notes |
|---|------|------|-------|
| 16.1 | Create .github/workflows/daily_discovery.yml | [CC] | Cron: "0 7 * * 1-5" (07:00 UTC Mon-Fri). Steps: checkout sales engine repo, Python 3.11 setup, pip install requirements, python main.py. Secrets: ANTHROPIC_API_KEY, NOTION_API_KEY, NOTION_LEADS_DB_ID, NOTION_SEQUENCES_DB_ID, NOTION_PIPELINE_RUNS_DB_ID, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, APOLLO_API_KEY. |
| 16.2 | Add secrets to GitHub repo | [M] | Repo → Settings → Secrets and variables → Actions → New repository secret. Add every secret listed in 16.1. |
| 16.3 | Test workflow manually | [M] | GitHub → Actions → daily_discovery → Run workflow. Watch run complete. Verify leads appear in Notion Daily Discovery Feed. |

---

## SECTION 17 — SHADOW MODE: Review and quality control
### Run this phase for 5 days before considering any outreach

| # | Task | Type | Time | Notes |
|---|------|------|------|-------|
| 17.1 | Run first discovery manually | [M] | 30 min | python main.py — watch output. Confirm leads appear in Notion. Review ICP scoring accuracy. |
| 17.2 | Review ICP scoring quality in Notion | [M] | 30 min | Open Daily Discovery Feed. For each new lead: does the ICP segment make sense? Is this actually an A1 (GCC operator with fragmentation pain) or was it misclassified? Is the score reasonable? |
| 17.3 | Review outreach draft quality | [M] | 30 min | For each draft: does it reference the specific trigger event? Does it use the right ICP hook and pain language? Does it sound human? Does it pass the brand checklist below? |
| 17.4 | Note systematic scoring or draft issues | [M] | 10 min | If multiple leads are misclassified → the scoring prompt needs tightening. If drafts are too generic → the draft agent needs more specific trigger event extraction. |
| 17.5 | Fix scoring or draft issues | [CC] | Per issue | → PROMPT: "The sales engine is [specific problem]. Fix the relevant agent to address this." |
| 17.6 | Run for 5 days in shadow mode | [M] | 15 min/day | Review the Notion Daily Discovery Feed each morning. Build a backlog of approved drafts. Do not send anything. |
| 17.7 | Decision: move to live outreach | [M] | — | Send outreach only when: you have left current employment, outreach drafts consistently pass quality review, LinkedIn company page is live, you have reviewed and approved each message personally before it goes out |

---

## SECTION 18 — MANUAL: Morning routine once live

Once the engine is running and you are no longer employed elsewhere, this is the daily operating rhythm:

| Time | Task | Time needed |
|------|------|-------------|
| 08:00 | Open Notion Daily Discovery Feed | 5 min |
| 08:05 | Review new leads from overnight run | 15 min |
| 08:20 | Approve or edit outreach drafts for qualified leads | 20 min |
| 08:40 | Send approved LinkedIn messages manually (never auto-send) | 10 min |
| 08:50 | Update status of any leads that replied | 5 min |
| 09:00 | Done — back to platform work | — |

Total: 45 minutes per day to maintain a live, actively working outreach pipeline.

---

## OUTREACH DRAFT QUALITY CHECKLIST
### Every draft must pass before you send it

- [ ] References the specific trigger event — not generic
- [ ] Uses the ICP hook from GLOBALKINECT_ICP.md verbatim or close
- [ ] Pain recognition before any product mention
- [ ] Platform language — not services firm language
- [ ] "Book a Demo" is the CTA — not "Get a Quote" or "Learn More"
- [ ] Links to globalkinect.co.uk/contact?intent=demo if a link is included
- [ ] Zero mention of partner network or delivery infrastructure
- [ ] Zero "Global Kinect" with a space
- [ ] Zero EOR-first positioning as headline
- [ ] LinkedIn note: under 300 characters
- [ ] LinkedIn message: under 400 words
- [ ] Email: under 150 words
- [ ] Reads like a senior operator talking to a peer — not a marketer
- [ ] Reviewed and approved by you personally before sending

---

## CURRENT STATUS SUMMARY

| Section | Status | Blocked by |
|---------|--------|------------|
| 1. Prerequisites | [ ] | Nothing |
| 2. Notion setup | [ ] | Section 1 |
| 3. Scaffold repo | [ ] | Section 1 |
| 4. Data models | [ ] | Section 3 |
| 5. Claude service | [ ] | Sections 1, 3 |
| 6. Discovery agent | [ ] | Section 5 |
| 7. Enrichment agent | [ ] | Section 6 |
| 8. ICP scoring agent | [ ] | Sections 4, 7 |
| 9. Deduplication agent | [ ] | Section 4 |
| 10. Outreach draft agent | [ ] | Sections 4, 5 |
| 11. Orchestrator | [ ] | Sections 6-10 |
| 12. Supabase persistence | [ ] | Sections 2, 11 |
| 13. Notion sync | [ ] | Sections 2, 12 |
| 14. Apollo integration | [ ] | Section 1 (Apollo account) |
| 15. Outreach sequences | [ ] | Nothing (do manually) |
| 16. GitHub Actions | [ ] | Sections 11-13 |
| 17. Shadow mode | [ ] | Sections 11-13 |
| 18. Live outreach | [ ] | Post-employment + shadow mode |
