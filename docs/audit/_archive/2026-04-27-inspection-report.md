> **SUPERSEDED on 2026-05-03** by `docs/audit/0001-existing-sales-engine.md`. Retained for audit trail; do not consult for current state.

# Engine Inspection Report

**Generated:** 2026-04-27
**Repository:** `C:\dev\globalkinect\sales`
**Scope:** Behaviour of the four working subsystems, written to inform Path A (existing engine stays as the source-of-truth backend; React dashboard at `leads\leads\` becomes its UI).
**Posture:** Read-only; no code modified. Where uncertain, "uncertain" is used explicitly.

---

## Section 1 — Vibe Prospecting flow

`scripts\vibe_prospecting_scan.py` (462 lines) is the only entry point that interacts with the Explorium / "Vibe Prospecting" API.

### 1.1 Endpoints called and sequence

The script runs a **two-step flow** when the ICP needs business-level filtering (locations or events), or a **single-step flow** when only company_size + job_department + country_code are needed.

The decision is in `build_business_filters` ([scripts\vibe_prospecting_scan.py:175-198](../scripts/vibe_prospecting_scan.py#L175-L198)):

1. `POST /v1/businesses` — request body via `build_business_filters`. Pages through results collecting `business_id`s up to `MAX_BUSINESS_IDS = 2000` ([line 162](../scripts/vibe_prospecting_scan.py#L162)). Mode is `preview`.
2. `POST /v1/prospects` — request body via `build_prospect_filters`. Mode is `full`. Pages until `--limit` results are collected. The `business_id` filter is populated from step 1 when applicable; otherwise `company_size` + `country_code` only.

Both endpoints share `explorium_post()` ([line 286-310](../scripts/vibe_prospecting_scan.py#L286-L310)):
- Auth header is `api_key: <raw key>` (not `Authorization: Bearer`)
- Content-Type and Accept both `application/json`
- Timeout 60 s
- A `print("DEBUG POST <path> request body: ...")` and a 4xx/5xx response-body dump are unconditionally emitted on every call. **This is debug instrumentation that was added when the 422 issue was being fixed and has not been gated behind a flag.**

### 1.2 Filter construction — hardcoded vs config

ICP filter sets are **hardcoded** at module level in `ICP_FILTERS` ([line 105-148](../scripts/vibe_prospecting_scan.py#L105-L148)). They are NOT read from `discovery_sources.json` or any other config file. The CLI parameterises only `--region`, `--icp`, `--limit`, `--dry-run`. Region → country-code mapping is also hardcoded in `REGION_COUNTRIES` ([line 53-59](../scripts/vibe_prospecting_scan.py#L53-L59)) and is independent of `app/utils/target_markets.py`.

### 1.3 ICP segments currently defined

Seven ICPs (A1, A2, A3, B1, B2, B3, B4 — no B5). Each is a dict with some subset of `company_size`, `departments`, `levels`, `number_of_locations`, `events`, `events_last_occurrence`. Quoting verbatim:

```python
ICP_FILTERS: dict[str, dict[str, Any]] = {
    "A1": {
        "company_size": company_size_range(51, 500),
        "departments": ["HR", "finance"],
        "levels": ["c-suite"],
        "number_of_locations": locations_range(2, 20),
    },
    "A2": {
        "company_size": company_size_range(11, 200),
        "departments": ["HR", "administration"],
        "levels": ["c-suite"],
        "number_of_locations": locations_range(0, 1),
    },
    "A3": {
        "company_size": company_size_range(201, 1000),
        "events": ["new_funding_round", "new_office", "increase_in_all_departments"],
        "events_last_occurrence": 90,
    },
    "B1": {
        "company_size": company_size_range(201, 5000),
        "departments": ["HR", "finance"],
        "number_of_locations": locations_range(6, 50),
    },
    "B2": {
        "company_size": company_size_range(11, 200),
        "departments": ["HR"],
        "levels": ["c-suite"],
        "number_of_locations": locations_range(0, 1),
    },
    "B3": {
        "company_size": company_size_range(51, 500),
        "events": ["new_office", "new_partnership"],
        "events_last_occurrence": 90,
    },
    "B4": {
        "company_size": company_size_range(201, 1000),
        "departments": ["HR", "finance"],
        "levels": ["c-suite"],
        "number_of_locations": locations_range(2, 20),
    },
}
```

`company_size_range(low, high)` ([line 71-83](../scripts/vibe_prospecting_scan.py#L71-L83)) and `locations_range(low, high)` ([line 86-95](../scripts/vibe_prospecting_scan.py#L86-L95)) translate integer ranges into the bucket strings Explorium accepts.

`JOB_DEPARTMENT_MAP` and `JOB_LEVEL_MAP` ([line 98-104](../scripts/vibe_prospecting_scan.py#L98-L104)) translate the brief's English labels into Explorium enums:

```python
JOB_DEPARTMENT_MAP = {
    "HR": "human resources",
    "finance": "finance",
    "administration": "operations",  # best guess — confirm against enum
}
JOB_LEVEL_MAP = {
    "c-suite": "c-suite",  # confirmed against Explorium /prospects docs
}
```

Both still carry comments flagging that "administration → operations" and the `c-suite` value were placeholders pending live confirmation; the c-suite value has since been verified in the docs but the administration mapping is unconfirmed.

### 1.4 What it writes to Notion

Target: `NOTION_INTAKE_DATABASE_ID` (the Lead Intake DB).

`write_intake_page()` ([line 379-429](../scripts/vibe_prospecting_scan.py#L379-L429)) builds property dicts via NotionService internal helpers (`_title`, `_text_property`, `_email_property`, `_url_property`, `_database_choice_or_text_property`, `_database_option_property`). The fields written are:

| Notion property | Source |
|---|---|
| `Company` (title) | `company_name` from result, fallback `"Unknown Company"` |
| `Contact` | `full_name` (or `first_name + last_name` concat) |
| `Role` | `job_title` (fallback `job_department_main`) |
| `Email` | `email` / `work_email` / `professional_email` if present — **plain text only**, never the hash |
| `LinkedIn URL` | First entry of `linkedin_url_array` |
| `Company Country` | `country_name` / `company_country_name` |
| `Target Country` | Region-specific: `"United Kingdom"` for `--region uk`; else `country_name` from result, falling back to `COUNTRY_CODE_TO_NAME[code.lower()]` |
| `Lane Label` | Hardcoded `"Direct Outbound Signals"` |
| `Lead Type Hint` | From `ICP_LEAD_TYPE_HINT[icp]` ([line 150-158](../scripts/vibe_prospecting_scan.py#L150-L158)): A1/A2/A3 → `direct_payroll`, B1/B2 → `hris`, B3/B4 → `direct_eor` |
| `Status` | Hardcoded `"ready"` |
| `Campaign` | `f"Vibe Scan {region} {icp} {YYYY-MM-DD}"` |
| `Notes` | `compose_notes()` — always includes `prospect_id` and `professional_email_hashed` (when no plain email is present) plus all other primitive raw fields not already mapped above |

### 1.5 Cadence

The scan is **not invoked from `main.py`**. It's invoked manually or through `scripts\run_monthly_scan.ps1` (see §9). `main.py` and `vibe_prospecting_scan.py` are independent processes.

### 1.6 Vibe → enriched contacts → Notion

It's **two API calls** but a **single Python invocation**: the `/businesses` step is internal to one scan run, not a separate "enrichment" step. A given lead is fetched as `(business_id, prospect_record)` in one pass.

There is no enrichment provider beyond Explorium. Contact emails are returned as `professional_email_hashed` (a hash) by default. The script attempts to read plaintext from `email` / `work_email` / `professional_email` fields if Explorium populates them in `mode: full`, but in the dry-run captured during the rebuild every result came back with `email_plain=(none)`. **Result:** unless Explorium starts surfacing plaintext addresses, the Notion `Email` property stays blank for every Vibe-sourced row.

### 1.7 Rate limiting / batching / credits

- Explorium docs say 200 qpm and `page_size` max 100. The script uses `MAX_PAGE_SIZE = 100` ([line 161](../scripts/vibe_prospecting_scan.py#L161)).
- No explicit throttle in the loop — calls are issued back-to-back within `fetch_business_ids()` and `fetch_prospects()`.
- **No credit tracking is implemented.** The original spec asked for it; the docs don't surface credit fields and the summary block at `run_scan()` no longer mentions them. Only `total_results` and `total_pages` are surfaced.

### 1.8 Duplicate handling

Two-tier dedupe in `load_existing_intake_keys()` ([line 359-374](../scripts/vibe_prospecting_scan.py#L359-L374)):

1. **Plaintext email** — if the result has a non-hashed email and that email already exists in Lead Intake (lower-cased), skip.
2. **Company + contact name pair** — `f"{company_name}|{contact_name}"` (lower-cased); if already present, skip.

The dedupe set is loaded once at the start of a scan via `notion_service.list_lead_intake_records(limit=500)`. Pre-existing rows beyond the most recent 500 are not visible to the dedupe.

Rows are also skipped if both `company_name` and `contact_name` are blank (`skipped_empty`).

---

## Section 2 — Scoring rubric

Source: [app\agents\lead_scoring_agent.py](../app/agents/lead_scoring_agent.py) (114 lines).

### 2.1 Inputs

`LeadScoringAgent.score_leads(leads: List[Lead], feedback_index: LeadFeedbackIndex | None = None)` ([line 15-26](../app/agents/lead_scoring_agent.py#L15-L26)).

Input is the in-memory `Lead` Pydantic model (see [app\models\lead.py](../app/models/lead.py)). Not Notion rows — the agent runs on already-normalised Lead objects produced earlier in the pipeline by `LeadResearchAgent` (which itself reads Notion intake and asks Anthropic to normalise into `Lead`).

The `feedback_index` is optional; when present the score is adjusted by `LeadFeedbackSignal.score_adjustment()` and a `feedback_summary` string is attached to the lead (see test below for the existing-sales-activity penalty in action).

### 2.2 Outputs

The agent returns a new list of `Lead` instances with `score`, `priority`, `recommended_angle`, and `feedback_summary` updated. **In-memory only — it does not write to Notion or Supabase directly.** Persistence happens later in `main.py`'s pipeline (`SupabaseService.insert_leads(scored_leads)` and `NotionService.upsert_lead_pages(scored_leads)`).

### 2.3 Universal vs segmented rubric

**Universal.** There is no per-segment branching. The same rubric applies whether the lead is `direct_eor`, `direct_payroll`, `recruitment_partner`, `hris`, or unknown. The differentiation by segment happens elsewhere — `lead_type` is one of the rubric inputs, but the function is not branched per ICP A1/A2/etc. (the engine has no concept of A1-B5 ICPs except in the Opportunities path, see §3).

### 2.4 Quality flags / penalties

There are **no explicit penalties** like "consultancy → -6 points" in the rubric. The only penalty mechanism is the feedback_index:

- `LeadFeedbackSignal.score_adjustment()` — undisclosed by reading the agent alone, but the test at [tests\test_lead_scoring_agent.py:113-139](../tests/test_lead_scoring_agent.py#L113-L139) asserts that an existing `Approved` queue + `proposal` pipeline + `sent` outreach produces `score <= 4`. So the adjustment is at least a -3 point penalty when sales activity already exists.

Quality control happens upstream (in `LeadDiscoveryAgent` qualification gates and the `_apply_operator_readiness_gate` that blocks promote when buyer is unknown) and downstream (in `OutreachReviewAgent` actionable-status gating). The scoring agent itself is purely additive on positive signals plus a single feedback-based adjustment.

### 2.5 Tests

[tests\test_lead_scoring_agent.py](../tests/test_lead_scoring_agent.py) has 4 test functions:

1. `test_score_leads_assigns_scores_priorities_and_angles` — asserts every lead gets a 1-10 score, a priority in `{high, medium, low}`, and a recommended_angle. Specifically: a UK/Founder/Saudi/direct_payroll lead becomes `priority == "high"`, a Netherlands/MD/UAE/recruitment_partner lead has score > a Coordinator with no target country.
2. `test_score_leads_rewards_top_target_markets_and_source_countries` — UAE > Egypt for the same lead profile.
3. `test_score_leads_supports_secondary_markets_without_treating_them_as_primary` — UAE > Qatar for same source country, both still scored.
4. `test_score_leads_applies_feedback_penalty_for_existing_sales_activity` — confirms feedback penalty caps at score ≤ 4.

### 2.6 Full rubric (verbatim)

```python
def _score_lead(self, lead, *, feedback_index=None) -> Lead:
    score = 0
    score += self._score_target_country(lead.target_country)   # via market_score()
    score += self._score_company_country(lead.company_country)
    score += self._score_lead_type(lead.lead_type)
    score += self._score_contact_role(lead.contact_role)
    if lead.email:
        score += 1
    if lead.linkedin_url:
        score += 1
    feedback_summary = None
    if feedback_index is not None:
        signal = self.lead_feedback_agent.signal_for_lead(feedback_index, lead)
        if signal is not None:
            score += signal.score_adjustment()
            feedback_summary = f"Existing sales activity detected: {signal.summary()}."
    final_score = max(1, min(score, 10))
    priority = self._priority_for_score(final_score)
    recommended_angle = self._recommended_angle_for_lead(lead)
    return lead.model_copy(update={
        "score": final_score,
        "priority": priority,
        "recommended_angle": recommended_angle,
        "feedback_summary": feedback_summary,
    })
```

**Per-component scoring:**

```python
def _score_target_country(self, target_country):
    return market_score(target_country)
    # market_score is defined in app/utils/target_markets.py.
    # Per the buckets used elsewhere it's roughly 3 for UAE/Saudi, 2 for
    # Qatar/Kuwait/Bahrain/Oman, 2 for Egypt, 1 for Lebanon/Jordan, 1 for
    # other supported markets, 0 for unsupported.

def _score_company_country(self, company_country):
    country_scores = {
        "United Kingdom": 2,
        "Germany": 2,
        "France": 1,
        "Netherlands": 1,
    }
    return country_scores.get(company_country or "", 0)

def _score_lead_type(self, lead_type):
    lead_type_scores = {
        "direct_eor": 3,
        "direct_payroll": 3,
        "recruitment_partner": 3,
        "hris": 2,
    }
    return lead_type_scores.get(lead_type or "", 0)

def _score_contact_role(self, contact_role):
    normalized_role = contact_role.lower()
    if "founder" in normalized_role:
        return 2
    if "head of people" in normalized_role or "people" in normalized_role:
        return 2
    if "director" in normalized_role:
        return 2
    return 1

def _priority_for_score(self, score):
    if score >= 8:
        return "high"
    if score >= 5:
        return "medium"
    return "low"
```

**Recommended angle** (string copy attached to the lead — used downstream by message_writer_agent):

```python
def _recommended_angle_for_lead(self, lead):
    target_country = normalize_target_country(lead.target_country)
    angle_by_type = {
        "direct_eor": "Position GlobalKinect around hiring into market without waiting for local entity setup.",
        "direct_payroll": (
            "Lead with payroll compliance, local processing confidence, and "
            "regional execution support."
            if target_country and market_score(target_country) < 3
            else "Lead with payroll compliance, local processing confidence, and GCC execution support."
        ),
        "recruitment_partner": "Position GlobalKinect as the employment and payroll partner behind recruiter-led placements.",
        "hris": "Lead with stronger HRIS control, employee visibility, and operational consistency across markets.",
    }
    return angle_by_type.get(lead.lead_type or "",
        "Lead with practical support across EOR, payroll, and people operations.")
```

**Score ceiling:** 10. **Score floor:** 1. **Theoretical max:** target_country (~3) + company_country (~2) + lead_type (~3) + contact_role (~2) + email (1) + linkedin (1) = **12 raw → clamped to 10**.

Note: the `recommended_angle` strings still write **"GlobalKinect" as one word**, contradicting the brand rule (see §3.3).

---

## Section 3 — Outreach generation (the two competing agents)

Three generators ship in this repo. Two are inside `app\agents\` and feed Notion's Outreach Queue. The third is `sales-engine\` and writes per-lead markdown files (see §4).

### 3.1 Which one runs when

| Agent | Runs in daily cycle (`main.py`)? | Runs on `--generate-outreach`? | Inputs |
|---|---|---|---|
| `MessageWriterAgent` ([app/agents/message_writer_agent.py](../app/agents/message_writer_agent.py)) | **Yes** — called as `message_writer_agent.generate_messages_with_solution(scored_leads, solution_recommendations)` at [main.py:200](../main.py#L200) | No | `Lead` (from intake) + `SolutionRecommendation` (from SolutionDesignAgent) |
| `OpportunitiesOutreachAgent` ([app/agents/opportunities_outreach_agent.py](../app/agents/opportunities_outreach_agent.py)) | **No** — only when `python main.py --generate-outreach` is passed; routes via `generate_opportunities_outreach()` at [main.py:524-562](../main.py#L524-L562) | **Yes** | Notion `Opportunities` DB rows (Vibe Prospecting imports) |

### 3.2 Prompts / templates

**MessageWriterAgent** is **fully deterministic — no Anthropic call**. Every message is composed from string templates keyed on `bundle_label`, `lead_type`, and `target_country`. Examples ([app/agents/message_writer_agent.py:267-313](../app/agents/message_writer_agent.py#L267-L313)):

```python
def _linkedin_value_line_with_solution(self, lead, solution_recommendation):
    country_label = self._country_label(lead.target_country)
    if solution_recommendation.sales_motion == "recruitment_partner":
        return (
            f"We support placements into {country_label} through an "
            f"{solution_recommendation.bundle_label} model that handles "
            "employment and payroll behind the scenes."
        )
    value_lines = {
        "EOR only": f"We help teams hire into {country_label} through a compliant EOR model.",
        "Payroll only": f"We help teams run compliant payroll in {country_label} without building a heavy local setup.",
        "HRIS only": f"We help teams add stronger HR visibility and control in {country_label}.",
        "EOR + Payroll": f"We help teams hire into {country_label} without an entity while covering payroll execution from day one.",
        "Payroll + HRIS": f"We help teams put compliant payroll in place in {country_label} and add stronger operating control.",
        "EOR + HRIS": f"We help teams enter {country_label} with compliant employment and clearer HR control.",
        "Full Platform": f"We help teams run hiring, payroll, and HR control in {country_label} through one operating platform.",
    }
    return value_lines[solution_recommendation.bundle_label]
```

The class also has `_role_hook`, `_email_context_line_with_solution`, `_email_value_line_with_solution`, `_strategy_line`, `_recommended_angle_line`, `_linkedin_close_with_solution`, `_email_close_with_solution`, `_build_follow_up_message_with_solution` — all deterministic dictionary-keyed copy.

The output is an `OutreachMessage` Pydantic model with `lead_reference`, `linkedin_message`, `email_subject`, `email_message`, `follow_up_message`.

**OpportunitiesOutreachAgent** is **Anthropic-backed**. After a recent edit (per the system reminder) it now picks one of three system prompts depending on the prospect's ICP:

```python
SYSTEM_PROMPT_MENA = (
    "You are a B2B outreach specialist for Global Kinect — a Payroll Bureau, "
    "HRIS, and EOR platform covering 11 MENA countries (Saudi Arabia, UAE, "
    "Qatar, Kuwait, Bahrain, Oman, Egypt, Morocco, Algeria, Lebanon, Jordan). "
    "You write direct, specific, human outreach messages. You never use generic "
    "openers. You never mention our partner network, third-party providers, or "
    "local bureaus. You never use the product names Insight, Orchestrate, or "
    "Control. You always write Global Kinect as two words. You follow the voice "
    "and hook patterns provided exactly."
)
SYSTEM_PROMPT_EUROPEAN = (... "covering 100+ countries" ...)
SYSTEM_PROMPT_DEFAULT = (... no country count ...)
```

(Quoted verbatim from the file modified at module top — see frontmatter of this conversation's recent system reminder for the file.)

The user prompt is constructed per-prospect in `_build_user_prompt` ([line 247-285](../app/agents/opportunities_outreach_agent.py)) — it embeds prospect details (Name, Role, Company, Country, Notes, ICP) plus the full text of the matching ICP hook file from `C:\dev\globalkinect\branding\outreach\icp-hooks\<file>.md` (or `partner-hooks\B5-…`). Loaded once at construction via `_load_hook_library` against `BRANDING_REPO_PATH`.

The model returns a single JSON object with `linkedin_message`, `email_subject`, `email_body`. Pulled out of the response by `_parse_json_response`.

After generation, every message goes through `_validate` ([line 309-350](../app/agents/opportunities_outreach_agent.py)) which checks:
- One-word `globalkinect` → reject
- Banned phrases (partner network / local bureau / "I hope this finds you well" etc) → reject
- Banned product names (Insight / Orchestrate / Control) as whole words in linkedin or email body → reject
- `30+ countries` → reject
- For `MENA_FOCUSED_ICPS` (A1-A3, B3): `100+ countries` → reject
- For `EUROPEAN_FOCUSED_ICPS` (B1, B2, B4): `11 MENA countries` → reject
- LinkedIn message > 5 non-empty lines → reject
- Email body > 6 non-empty lines → reject
- Bullet points (`-`, `*`, `•` line starts) → reject

Failed validations are written back into the source Opportunity page as `Outreach generation failed — <reason>` and counted in the result summary.

### 3.3 The "GlobalKinect vs Global Kinect" conflict

| Generator | What it writes |
|---|---|
| `MessageWriterAgent` | `"GlobalKinect"` — see [message_writer_agent.py:269-275](../app/agents/message_writer_agent.py#L269-L275): `f"We help companies hire into {country} without setting up an entity, …"` and many others. The string `"GlobalKinect"` appears throughout the file in deterministic copy and in `_strategy_line`. |
| `OpportunitiesOutreachAgent` | Enforces `"Global Kinect"` (two words) in the system prompt and in the validator. Any draft containing the literal `"globalkinect"` (lowercased) is rejected before it reaches Notion. |
| `LeadScoringAgent.recommended_angle` | Writes `"GlobalKinect"` (one word) in the `recommended_angle` string used downstream. |
| `SolutionDesignAgent` | I haven't quoted it directly here, but it produces `commercial_strategy` strings used by the message writer; these strings flow into one-word output. |
| `ProposalSupportAgent` | Multiple template strings here also use `"GlobalKinect"` (one word). |
| `sales-engine\prompts\email_prompt.md` | Enforces `"Global Kinect"` (two words) — line: `"Write Global Kinect as two words, never 'GlobalKinect'"`. |

**So the daily engine ships one-word brand drafts; the Opportunities path and the per-lead pipeline ship two-word.** Both run against the same Outreach Queue.

### 3.4 What each writes

`MessageWriterAgent.generate_messages_with_solution()` returns `OutreachMessage` instances **in memory**. Persistence happens in `main.py`:
- Supabase: `supabase_service.insert_outreach_messages(outreach_messages)` ([main.py:267](../main.py#L267))
- Notion: outreach is bundled into `OutreachQueueItem`s by `_build_outreach_queue_items()` ([main.py:454-481](../main.py#L454-L481)), then `notion_service.upsert_outreach_queue_pages(outreach_queue_items)` ([main.py:285-292](../main.py#L285-L292))

`OpportunitiesOutreachAgent._persist()` writes:
- `OutreachMessage` row to Supabase `outreach_messages` (if Supabase configured)
- `OutreachQueueItem` upsert into Notion Outreach Queue with `status="ready_to_send"`, `run_marker=f"OPPS_{timestamp}"`
- Updates the source Opportunity page (`Next Action = "Review outreach in dashboard"`, `Next Action Date = today`, appends an `---OUTREACH GENERATED---` block to its `Notes`)

### 3.5 Where drafts go for human review

The **Notion Outreach Queue** is the canonical surface. Both agents land there. The Operator Console (`app/web/operator_console.py`) reads from that DB to render the Queue page.

There is no second review surface — Supabase persistence is for archival/reporting, not for review.

### 3.6 Operator Console: edit drafts, or only approve/hold/regenerate?

**Approve / Hold / Regenerate / Mark Sent only.** No editing.

`OperatorConsoleApp._queue_card()` ([app/web/operator_console.py:1104-1129](../app/web/operator_console.py#L1104-L1129)) renders email subject as a flat read-only string and email body as a `<details>` collapsible block — both unedited HTML escapes. The action buttons are hardcoded in `_queue_action_button` ([line 1170-1193](../app/web/operator_console.py#L1170-L1193)) to four POST forms targeting `/queue/status` with status values `Approved`, `Hold`, `Regenerate`, `Sent`. There is no `<textarea>`, no PATCH route, no inline-edit handler.

If the operator wants to tweak copy before sending, they have to do it directly in Notion (or in their email client after copy/paste). The console does not write back edited copy.

### 3.7 How "send" actually works

**It doesn't.** No SMTP / Gmail API / SES / outbound handler exists in this repo. There is no module, class, or function that sends mail.

The flow is:
1. `MessageWriterAgent` (or `OpportunitiesOutreachAgent`) drafts the message into Notion Outreach Queue.
2. Operator opens the Notion page (or the local Operator Console at 127.0.0.1:8787).
3. Operator copies the subject + body, pastes into Gmail / Outlook / LinkedIn / their own client, sends it.
4. Operator returns to Notion and clicks **Mark Sent** — which only changes the Notion `Status` to `Sent`. Nothing leaves the system; this is purely a state update for tracking.

`OutreachReviewAgent.sync_queue_decisions()` then mirrors the `Sent` status into the Supabase `pipeline_records` and `Notion Pipeline` DBs on the next live run.

So "send" is operator-driven and out-of-band. The engine has no concept of an outbox.

---

## Section 4 — Per-lead research pipeline (`sales-engine/`)

Source: [sales-engine\scripts\run_pipeline.py](../sales-engine/scripts/run_pipeline.py) (548 lines), prompts in [sales-engine\prompts\](../sales-engine/prompts/).

### 4.1 CSV input format

Reads with `csv.DictReader` then `Lead.from_csv_row()` ([line 96-121](../sales-engine/scripts/run_pipeline.py#L96-L121)). The `Lead` dataclass tries multiple column-name fallbacks for each field — both Vibe-style snake_case (`prospect_full_name`, `prospect_company_name`, `contact_professions_email`) and human-readable PascalCase (`Full Name`, `Company`, `Professional Email`). Required fields per the dataclass: `rank`, `score`, `source`, `full_name`, `role`, `company`, `website`, `professional_email`, `personal_email`, `best_email`, `email_type`, `linkedin_url`, `prospect_country`, optional `mobile`. CSVs live in `sales-engine\csv\`; the most recent is `uae_ksa_hr_finance_leaders_gk_20260427151757.csv`.

### 4.2 Notion vs CSV

**Reads only from CSV. Never reads or writes Notion.**

The pipeline is orthogonal to the daily engine. It produces local markdown files only; no Notion DB ID is ever read or referenced. Outputs land at `LEADS_ROOT` which defaults to `C:\dev\globalkinect\sales\leads\Reports`.

### 4.3 Output → main engine?

**No feedback path.** Generated `report.md`, `email.md`, `mobile.txt`, `linkedin.txt`, `metadata.json` are local artefacts only. Nothing in `app\` reads from `leads\<slug>\`. The main engine has no awareness that this pipeline exists.

### 4.4 How it differs from main-engine outreach

| | Main engine `MessageWriterAgent` | Main engine `OpportunitiesOutreachAgent` | `sales-engine\` per-lead pipeline |
|---|---|---|---|
| Research model | None | None | **Perplexity sonar-deep-research** (live web search + citations) |
| Drafting model | None (deterministic) | Claude Sonnet 4 | **Claude Opus 4.7** |
| Input | Notion Lead Intake → normalised `Lead` | Notion Opportunities | CSV file |
| Output | Notion Outreach Queue | Notion Outreach Queue | Local `leads\<slug>\email.md` and `report.md` |
| Cadence | Daily (every `main.py` run) | On-demand `--generate-outreach` | On-demand `python run_pipeline.py --csv …` |
| Brand rule | "GlobalKinect" one word | "Global Kinect" two words (validated) | "Global Kinect" two words (prompt) |
| Banned strings | None enforced | partner network / local bureau / product names | "Entomo", "GlobalKinect" one word, partner network |
| Personalisation | Country/lead_type templates only | ICP hook library + Notion notes | Live web research → real signals |

The prompts ([sales-engine\prompts\research_prompt.md](../sales-engine/prompts/research_prompt.md), [email_prompt.md](../sales-engine/prompts/email_prompt.md)) are by far the most detailed in the repo. The research prompt expects 8 structured sections (company snapshot, MENA payroll footprint, payroll/HR pain signal, decision-maker context, buying unit map, suggested outreach angle, red flags, confidence rating). The email prompt expects 7-element body structure (subject, opening, bridge, value, proof point, ask, sign-off) and enforces British English, persona-matched language, no buzzword list, and a `[CAUTION: <red flag>]` pre-pend if the research flagged any.

### 4.5 Cost per lead

Logged in `leads\_manifest.json` per lead — sample from the file ([line 19-49](../leads/_manifest.json#L19-L49)) shows for `Kirtanlal Scaffolding`:

```json
"perplexity_usage": {
  "prompt_tokens": 1188,
  "completion_tokens": 4240,
  "total_tokens": 5428,
  "citation_tokens": 8014,
  "num_search_queries": 54,
  "reasoning_tokens": 92431,
  "cost": {
    "input_tokens_cost": 0.00238,
    "output_tokens_cost": 0.03392,
    "citation_tokens_cost": 0.01603,
    "reasoning_tokens_cost": 0.27729,
    "search_queries_cost": 0.27,
    "total_cost": 0.59962
  }
},
"claude_usage": { ... }
```

So **~$0.60 per lead for Perplexity research** in this sample, plus Claude Opus drafting cost (not summed per lead in the manifest — uncertain).

### 4.6 Active use vs superseded

**Active.** `leads\_run.log` (30 KB) is dated 2026-04-27 and `leads\_manifest.json` is 68 KB with multiple recent runs. The CSV `uae_ksa_hr_finance_leaders_gk_20260427151757.csv` is dated today (2026-04-27).

The pipeline is not superseded by the main engine's outreach agents — different workflows. The main engine is for high-volume scoring + first-touch templated emails; `sales-engine\` is for **deep-research, single-touch personalised emails on a curated short-list**. They serve different commercial intents. There's no documented connection between the two; they share branding and Anthropic credentials and not much else.

---

## Section 5 — Notion data model

Sources: [app\services\notion_service.py](../app/services/notion_service.py), [app\services\config.py](../app/services/config.py:23-37), [NOTION_DISCOVERY_SCHEMA.md](../NOTION_DISCOVERY_SCHEMA.md), [NOTION_INTAKE_SCHEMA.md](../NOTION_INTAKE_SCHEMA.md).

### 5.1 Databases the engine reads/writes

`NotionService` defines 11 logical database names ([notion_service.py:59-69](../app/services/notion_service.py#L59-L69)) plus the Opportunities DB added later:

| Logical key | Env var | Service constant | Purpose |
|---|---|---|---|
| Lead Discovery | `NOTION_DISCOVERY_DATABASE_ID` | `DATABASE_DISCOVERY` | Raw source-backed candidates from RSS/HTML/manual signals + autonomous lanes |
| Lead Intake | `NOTION_INTAKE_DATABASE_ID` | `DATABASE_INTAKE` | Normalised, processable leads ready for scoring |
| Outreach Queue | `NOTION_OUTREACH_QUEUE_DATABASE_ID` | `DATABASE_OUTREACH_QUEUE` | Drafted messages awaiting operator approve/hold/regenerate/send |
| Sales Engine Runs | `NOTION_RUNS_DATABASE_ID` | `DATABASE_RUNS` | Per-run health: status, counts, errors |
| Leads | `NOTION_LEADS_DATABASE_ID` | `DATABASE_LEADS` | Scored leads (post-scoring snapshot) |
| Pipeline | `NOTION_PIPELINE_DATABASE_ID` | `DATABASE_PIPELINE` | Live pipeline state per lead reference (stage, outreach_status, next_action) |
| Solution Recommendations | `NOTION_SOLUTIONS_DATABASE_ID` | `DATABASE_SOLUTIONS` | Per-lead bundle/module/strategy recommendation |
| Tasks | `NOTION_TASKS_DATABASE_ID` | `DATABASE_TASKS` | Operator action items (draft/send/wait/follow_up) |
| Deal Support | `NOTION_DEAL_SUPPORT_DATABASE_ID` | `DATABASE_DEAL_SUPPORT` | Call prep / proposal summary / objection responses |
| Accounts | `NOTION_ACCOUNTS_DATABASE_ID` | `DATABASE_ACCOUNTS` | Account-level rollup (one row per company) |
| Buyers | `NOTION_BUYERS_DATABASE_ID` | `DATABASE_BUYERS` | Buyer-level rollup (one row per contact) |
| **Opportunities** | `NOTION_OPPORTUNITIES_DATABASE_ID` | (no constant — direct fetch via `fetch_opportunity_pages`) | Vibe Prospecting imports waiting for outreach generation |

### 5.2 Per-database lifecycle

**Lead Discovery** — Title `Company`. Read by `LeadDiscoveryAgent.promote_discovery_records` (qualifies via Anthropic and either promotes/marks-review/marks-rejected). Written by `DiscoverySourceCollectorAgent.collect_into_discovery` (RSS/HTML feeds), `AutonomousLaneAgent.seed_internal_lanes` (Buyer Mapping + Reactivation), and the `mark_lead_discovery_record_processed` / `mark_lead_discovery_record_failed` updates after qualification. Status flow: `new`/`approved`/`ready` → `promoted`/`review`/`rejected`/`error`.

**Lead Intake** — Title `Company`. Read by `LeadResearchAgent.collect_leads`. Written by:
- `LeadDiscoveryAgent` via `upsert_intake_page_from_discovery` (promotion path)
- `scripts\vibe_prospecting_scan.py` directly (Explorium ingestion path)
- Manually by operators
Plus `mark_lead_intake_record_processed` / `mark_lead_intake_record_failed` after normalisation. Status flow: `new`/`approved`/`ready` → `ingested`/`archived`/`rejected`/`error`/`done`.

**Outreach Queue** — Title `Lead Reference`. Properties include `Email Subject`, `Email Message`, `LinkedIn Message`, `Follow-Up Message`, `Status`, `Reply` (added by ResponseHandlerAgent on first run via `ensure_outreach_queue_reply_property`), `Notes`. Written by `MessageWriterAgent` (via `upsert_outreach_queue_pages`), `OpportunitiesOutreachAgent` (same), and `ResponseHandlerAgent` (status changes after reply classification). Read by Operator Console, Notion Proxy API, and `OutreachReviewAgent` (which mirrors operator decisions back to Pipeline). Status flow: `ready_to_send` → `approved` / `hold` / `regenerate` / `sent` / `replied`. Operator-managed statuses (`approved`, `sent`, `hold`) are preserved by `_should_preserve_outreach_queue_page` so the next live run doesn't overwrite them.

**Sales Engine Runs** — Title `Run Marker`. Written by every `main.py` run (status `running` → `completed`/`failed`, plus counts and error_summary).

**Leads / Pipeline / Solutions / Tasks / Deal Support / Accounts / Buyers** — All written in the live-mode block of `main.py` ([main.py:268-289](../main.py#L268-L289)) via `NotionSyncAgent.sync_operating_views`. Read by Operator Console (Pipeline + Tasks views are uncertain — see §6) and the Lovable dashboard's Supabase mirror (separate schema, see §11).

**Opportunities** — Title `Company` (per the Vibe Prospecting context — uncertain about exact title property name; the NotionService fetches by `Company` via `_property_text(page, "Company")` in `_build_opportunity_record`). Read by `OpportunitiesOutreachAgent.generate_outreach`. Written **externally** by Vibe Prospecting (the import tool), not by the engine.

### 5.3 Lifecycle of a single lead

For a Vibe-sourced lead:

1. `scripts\vibe_prospecting_scan.py --region gcc --icp A1 --limit 1000` → creates a row in **Lead Intake** with `Status="ready"` and `Lane Label="Direct Outbound Signals"`.
2. Next `python main.py` run → `LeadResearchAgent.collect_leads` reads ready intake rows, normalises via Anthropic into `Lead` model, marks intake row `Status="ingested"`.
3. `LeadScoringAgent.score_leads` adds score/priority/recommended_angle (in-memory).
4. `EntityMapperAgent.build_accounts` / `build_buyers` produce Account and Buyer rollups.
5. `SolutionDesignAgent.create_solution_recommendations` produces a bundle/module recommendation per lead.
6. `CRMUpdaterAgent.create_pipeline_records_with_solution` makes pipeline records (`stage="new"`, `outreach_status="not_started"`).
7. `MessageWriterAgent.generate_messages_with_solution` drafts subject + email + LinkedIn + follow-up.
8. Pipeline records flipped to `outreach_status="drafted"`, then evaluated by `PipelineIntelligenceAgent` and `LifecycleAgent`.
9. `ExecutionAgent.generate_tasks` emits operator tasks per record.
10. `ProposalSupportAgent.create_deal_support_packages_with_solution` produces deal support package.
11. **Live mode only:** Supabase persistence (insert leads + outreach_messages + pipeline upsert + solutions upsert + deal_support insert + tasks insert) and Notion sync (upsert into Leads / Pipeline / Solutions / Tasks / Deal Support / Accounts / Buyers / Outreach Queue).
12. Outreach Queue page now has `Status="ready_to_send"`. Operator opens Console → approves / holds / regenerates → marks sent after copy-pasting the email.
13. Operator pastes prospect reply into the Outreach Queue page's `Reply` field and changes `Status="replied"` (manually, in Notion).
14. Next `main.py` run: `ResponseHandlerAgent.process_replies` (runs after `feedback_index`) classifies the reply via Anthropic, drafts next response, updates Pipeline record stage (`call_booked` / `contacted` / `closed` / `replied`), changes Queue status to `drafted` / `closed` / `hold`, creates a `send_reply` execution task.
15. `OutreachReviewAgent.sync_queue_decisions` mirrors any operator-led decisions (`approved` / `sent` / `hold`) into Pipeline state.

Sales-engine pipeline runs entirely outside this — see §4.

### 5.4 Obsolete or unused DBs

- **Solution Recommendations** — actively written by every live run, but the only consumers are NotionSyncAgent and (via Supabase) the dashboard. The `OpportunitiesOutreachAgent` uses Solution Recommendations from Supabase as a personalisation source for `request_for_info` replies via `ResponseHandlerAgent`. So used, but only as reference data. Not strictly obsolete.
- **Deal Support** — same shape: written every run, consumed only by the dashboard and by `ResponseHandlerAgent._draft_objection_response`. Useful but heavily under-used in operator flow today.
- **Tasks** — written every run, but no agent or human-facing surface I read uses them as a worklist. The Operator Console doesn't render a Tasks page. **Uncertain whether anyone consumes Tasks today.**
- **Accounts / Buyers** — populated by `EntityMapperAgent`, surfaced in Operator Console as the `/accounts` view (read-only aggregation, not the canonical Notion DB). Useful for navigating but not part of any decision loop.

---

## Section 6 — Operator Console capabilities

Source: [app\web\operator_console.py](../app/web/operator_console.py) (1356 lines, single WSGI file).

### 6.1 Routes

Defined in `OperatorConsoleApp.__call__()` ([line 22-91](../app/web/operator_console.py#L22-L91)):

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Dashboard (counts, latest run, focus cards) |
| GET | `/discovery` | Lead Discovery — filterable list of source-backed candidates |
| GET | `/intake` | Lead Intake — filterable list of normalised leads |
| GET | `/accounts` | Aggregated Accounts & Buyers view (computed from Discovery + Intake + Queue records, NOT from Accounts/Buyers Notion DBs) |
| GET | `/queue` | Outreach Queue — filterable list of drafts with action buttons |
| POST | `/queue/status` | Apply queue status change (approve/hold/regenerate/sent) — form POST, redirects to `/queue?flash=…` |
| GET | `/runs` | Sales Engine Runs — recent run history with status/counts/errors |
| GET | `/help` | Keyboard shortcuts cheatsheet |
| GET | `/health` | Plain-text "ok" |

Anything else returns 404.

### 6.2 Operator actions

Per `_queue_card()` button rendering ([line 1104-1129](../app/web/operator_console.py#L1104-L1129)):

| Action | Status set | Pipeline effect (next run) |
|---|---|---|
| Approve | `Approved` | `OutreachReviewAgent` flips outreach_status to `approved` |
| Hold | `Hold` | `OutreachReviewAgent` logs activity + sets `next_action="operator_hold"` |
| Regenerate | `Regenerate` | Next live run drops the existing draft and re-generates from `MessageWriterAgent` |
| Mark Sent | `Sent` | `OutreachReviewAgent` flips outreach_status to `sent`, sets `last_outreach_at`/`last_contacted` |

There is **no Edit, no Close-as-lost, no manual Re-score, no manual Promote, no manual Reject** in the console. Every other state change happens server-side during the next `main.py` run.

`/discovery`, `/intake`, `/accounts`, `/runs` are **read-only views**. No mutating routes exist for those databases.

### 6.3 Where data comes from

`OperatorConsoleApp` uses `OperatorConsoleService` ([app/services/operator_console_service.py](../app/services/operator_console_service.py:1-30 — short, ~30 lines). The service wraps `NotionService` directly. **Notion is the only source.** Supabase is not consulted. The console doesn't read leads/pipeline/solutions/tasks/deal_support DBs — only Discovery, Intake, Outreach Queue, Sales Engine Runs.

### 6.4 Writes back to Notion vs local-only

Writes back: only `_handle_queue_status` ([line 558-577](../app/web/operator_console.py#L558-L577)) — `service.update_outreach_queue_status(lead_reference, status)`. Everything else is read-only.

### 6.5 Daily SDR coverage assessment

**What it covers today:**
- See ready-to-send drafts and approve / hold / regenerate / mark-sent
- Browse discovery / intake backlogs and triage which look promising
- Aggregate view of accounts and buyers across discovery + intake + queue
- Run-health dashboard so the operator knows whether the engine ran cleanly

**What it doesn't cover (gaps):**
- **No "Today" view for an SDR.** The Dashboard shows aggregate counts, not "5 prospects waiting for your reply, 12 follow-ups due today, 3 hot replies".
- **No reply notifications or hot-reply surfacing.** Replies live in Notion. The operator has to navigate to the Queue and notice that some rows have status `replied` to know there's anything to act on.
- **No editing of drafts.** Approve-or-regenerate-or-walk-away is the only model. Operator has to edit in Notion directly.
- **No send-tracking.** "Mark Sent" is a manual click, not automatic from any inbox or LinkedIn signal.
- **No prioritisation / next-best-action.** The Queue sorts by status then priority then alpha; not by "this is the most urgent thing to do right now".
- **No view of Pipeline / Tasks / Deal Support DBs.** Those are written but never surfaced in this console. Operator has to open Notion to see them.
- **No view of `Reply` content** in the queue card — the replied-to text is in the Notion `Reply` property, but the queue card renders email subject / email body / linkedin / follow-up only. (Uncertain — would need to grep for `Reply` rendering; my read showed no Reply field on the queue card.)
- **Single user.** No auth, no team view, no per-SDR ownership/assignment, no capacity planning.

---

## Section 7 — The `api/` proxy and dashboard wiring

Sources: [api\app\main.py](../api/app/main.py) (31 lines), [api\app\routers\notion_proxy.py](../api/app/routers/notion_proxy.py) (259 lines).

### 7.1 Endpoints

`api\app\main.py` mounts one router under `/api/notion` plus a `/api/health` GET. Routes from `notion_proxy.py`:

| Method | Path | Action |
|---|---|---|
| GET | `/api/health` | `{"status":"ok"}` |
| GET | `/api/notion/discovery` | List discovery records (filter by `status`, `lane`, `limit`) |
| GET | `/api/notion/intake` | List intake records (filter by `status`, `limit`) |
| GET | `/api/notion/runs` | List recent runs with computed `duration_seconds` |
| GET | `/api/notion/outreach-queue` | List queue records (filter by `status`, `limit`) |
| PATCH | `/api/notion/outreach-queue/{record_id}/status` | Set arbitrary status (validated against `OUTREACH_STATUS_VALUES = {ready_to_send, approved, hold, sent, replied}`) |
| PATCH | `/api/notion/outreach-queue/{record_id}/approve` | Convenience: set status to `approved` |
| PATCH | `/api/notion/outreach-queue/{record_id}/hold` | Convenience: set status to `hold` |
| PATCH | `/api/notion/runs/{record_id}/note` | Append a note to a Sales Engine Runs page |
| PATCH | `/api/notion/intake/{record_id}/status` | Set intake status (validated against `INTAKE_STATUS_VALUES = {new, ready, ingested, rejected, error}`) |

Errors are swallowed into an empty array + `X-Notion-Proxy-Error: <context>: <error>` header rather than 500s — see `_safe_fetch` ([line 41-52](../api/app/routers/notion_proxy.py#L41-L52)).

### 7.2 Read-only or also writes

**Mostly read with limited writes.** The PATCH endpoints write back via NotionService methods like `update_outreach_queue_record_status`, `update_lead_intake_record_status`, `append_sales_engine_run_note`. **Uncertain whether those NotionService methods exist** — I didn't grep them in this pass. The PATCH endpoints will fail at runtime if they don't.

### 7.3 Auth

**None.** No API key check, no JWT verification, no header-based gating. Any caller that can reach the host can use these endpoints. Auth is "trust the caller" — viable only because the API is bound to localhost / a private network.

### 7.4 CORS

```python
app.add_middleware(CORSMiddleware,
    allow_origins=[DASHBOARD_ORIGIN],   # default http://localhost:5174
    allow_credentials=False,
    allow_methods=["GET", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Notion-Proxy-Error"],
)
```

`DASHBOARD_ORIGIN` from env, defaults to `http://localhost:5174` — the Vite dev server port for the dashboard at `leads\leads\`.

POST is **not** in the allowed methods. PATCH is. So any new write endpoint that uses POST would also need a CORS update.

### 7.5 Is the dashboard wired to call this api/?

**Uncertain.** I haven't grepped `leads\leads\src\` for fetch / axios / API URLs. The default CORS origin (`http://localhost:5174`) and the existence of these specific endpoint shapes suggest the dashboard was scaffolded to call this proxy for Notion data. But the dashboard also has its own Supabase client (`@supabase/supabase-js` in package.json) and its own backend (`leads\leads\backend\`) which has uv-managed FastAPI scaffolded.

So the answer depends on which path the dashboard is currently using. **Concrete next step to verify:** `grep -r "/api/notion" leads/leads/src/` and `grep -r "supabase" leads/leads/src/integrations/`.

### 7.6 Endpoints needed for SDR daily workflow

If the dashboard is to drive an SDR's day, the proxy needs at least:

- GET `/api/notion/today` — server-side compute of "what should this SDR do now": queue rows in `replied` (hot), pipeline records with `next_action ∈ {nudge_message, send_follow_up}` past their due date, queue rows in `ready_to_send` sorted by priority. Currently the only way to assemble this is for the dashboard to make multiple calls and sort client-side.
- PATCH `/api/notion/outreach-queue/{id}/edit` — accepts subject + body + linkedin + follow_up + reply text, writes back to Notion. **Currently absent** — only status PATCH exists.
- POST or PATCH `/api/notion/outreach-queue/{id}/regenerate` — currently the regenerate flow happens implicitly on the next `main.py` run; no dedicated endpoint.
- GET `/api/notion/pipeline` — pipeline records, filterable by stage, priority, owner. Not exposed today.
- GET `/api/notion/tasks` — execution tasks, filterable by priority/status. Not exposed today.
- GET `/api/notion/deal-support/{lead_reference}` — proposal summary, objection responses, recap subjects. Not exposed today.
- POST `/api/notion/manual-lead` — let an SDR add a lead by hand into Lead Intake. Not exposed today.
- POST `/api/notion/log-activity/{lead_reference}` — record a manual touch ("called and left voicemail"). Not exposed today.

Plus auth — even at minimum a shared-secret header check before any writes.

---

## Section 8 — Cold outbound: what's NOT there

**Direct, line-by-line:**

### 8.1 Cold-blanket / Layer 3 / Instantly-style functionality

**No.** Nothing in this repo opens a connection to send mail. No Instantly / Apollo / Mailshake / Smartlead / Lemlist / Reply.io / Smartreach integration. No Mailgun / SendGrid / Postmark / SES SDK. No SMTP client. The closest thing to a "send" action is `OutreachReviewAgent` recording the operator-clicked status `Sent` — which only changes a Notion field.

What's adjacent: the Outreach Queue is shaped like a queue you could plug a sender into. The drafted email_subject + email_message fields are fully formed plain-text emails ready to send. A future sender-shim could read `Status="approved"` rows, send via a sending provider, then flip status to `sent`. But that shim doesn't exist.

### 8.2 Sequence engine / multi-touch follow-ups

**Partially.** `MessageWriterAgent.generate_messages_with_solution` produces a `follow_up_message` field per draft ([app/agents/message_writer_agent.py:198-245](../app/agents/message_writer_agent.py#L198-L245)). So one canned follow-up exists per record — but:

- It's drafted alongside the first-touch and never re-evaluated based on the prospect's actual response or non-response.
- There's no second / third / fourth touch, no different cadence per persona, no escalation logic beyond `LifecycleAgent.evaluate_lifecycle()` setting `next_action = "send_follow_up"` when `last_outreach_at` is 3+ days ago with no reply.
- Sending the follow-up requires manual operator action — same copy-paste flow as the first-touch.

So: one pre-drafted follow-up exists per prospect, no real cadence engine. The lifecycle agent acts as the equivalent of "schedule next touch in N days" but it nudges human action, not autonomous send.

### 8.3 Reply ingestion from any inbox

**No.** No Gmail API client, no IMAP poller, no Microsoft Graph integration. `ResponseHandlerAgent` reads the `Reply` rich-text field from Notion Outreach Queue — meaning the operator must **manually paste** the prospect's reply into Notion. There is no automated link between an inbox and the engine.

The handler's docstring is honest about this: `"Operators paste prospect reply text here for the agent to pick up on the next run."` ([app/agents/response_handler_agent.py:10](../app/agents/response_handler_agent.py#L10) and per-prompt construction).

### 8.4 Classification of inbound replies

**Yes — but only after manual paste.** `ResponseHandlerAgent` exists and runs as part of the daily cycle (wired into `main.py` after `feedback_index`). It calls Anthropic with the system prompt:

> "You are a sales reply classifier for Global Kinect, a multi-country payroll bureau and EOR platform serving MENA and European markets."

…and asks for a JSON classification into `positive` / `objection` / `negative` / `out_of_office` / `neutral` / `request_for_info` plus a one-sentence summary plus a `key_concern` for objections. It then drafts a next message based on the classification (using Deal Support's `objection_response` for objections, Solution Recommendation's `commercial_strategy` for `request_for_info`) and writes the draft back into the Outreach Queue's Notes field with status `drafted` / `closed` / `hold`.

The flow is real and works. The bottleneck is the manual-paste step — which is the practical reverse of an inbox integration.

### 8.5 Suppression list / unsubscribe / bounce tracking

**No.** No suppression list lookup, no unsubscribe handler, no bounce ingestion. `LeadFeedbackAgent` provides a pass-through "if there's existing sales activity in queue/pipeline for this lead, downgrade the score" that prevents some duplicate outreach — but only across the engine's own DBs, not against an external DNC list.

A `ResponseHandlerAgent` `negative` classification sets the queue status to `closed` and the pipeline stage to `closed` with no further outreach drafted, but there's no global "never email this address again" list.

### 8.6 Deliverability infrastructure

**No.** No SPF / DKIM / DMARC awareness anywhere in the codebase — these are purely DNS / sending-domain concerns and the engine doesn't send. No domain-rotation logic. No warmup state machine. No bounce-rate / open-rate / reply-rate tracking. The engine is deliverability-agnostic by design — it stops at "drafted email in Notion".

The closest deliverability surface is in the per-lead pipeline (`sales-engine\`): it produces real subject lines + bodies, and the email_prompt enforces "no exclamation marks, no buzzwords, no caps lock, scannable in 15 seconds" — i.e. content-side hygiene. Sending-side hygiene is out of scope.

---

## Section 9 — Cadence and scheduling

### 9.1 Actual current cadence

**Manual / on-demand.** No cron, no Cloud Scheduler, no Windows Task Scheduler entry actually configured. References to scheduling exist only in docs and as a commented-out `schtasks` line at the bottom of `run_monthly_scan.ps1`.

The brief has the engine running daily; in practice the operator runs `python main.py` manually or schedules it through Task Scheduler at their discretion.

### 9.2 Monthly scan step-by-step

[scripts\run_monthly_scan.ps1](../scripts/run_monthly_scan.ps1) (27 lines). Verbatim:

```powershell
$ErrorActionPreference = "Stop"
$env:PYTHONPATH = "."

Write-Host "Starting monthly Vibe Prospecting scan at $(Get-Date -Format o)"

.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region gcc --icp A1 --limit 1000
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region gcc --icp A2 --limit 500
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region gcc --icp A3 --limit 200
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region mena --icp B3 --limit 400
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region mena --icp B4 --limit 300
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region uk --icp B2 --limit 400
.\venv\Scripts\python.exe scripts\vibe_prospecting_scan.py --region europe --icp B1 --limit 400

Write-Host "All Vibe scans complete. Running sourcing engine in live mode."

$env:SALES_ENGINE_RUN_MODE = "live"
$env:SALES_ENGINE_TRIGGERED_BY = "monthly_scan"
.\venv\Scripts\python.exe main.py

# To schedule this in Windows Task Scheduler to run on the 1st of every month at 07:00:
#
# schtasks /create /tn "GlobalKinect Monthly Scan" ...
```

So one monthly invocation:
1. Pulls up to **3,200 prospects** from Explorium across 7 ICP × region combos into Lead Intake.
2. Runs `main.py` once in `live` mode with `triggered_by="monthly_scan"`. That single run normalises every newly-inserted intake row, scores it, generates outreach drafts, and lands them in the Outreach Queue.

There is no equivalent weekly or daily script. The implication is **one batch ingestion per month, then the daily `main.py` run handles incremental discovery/intake/queue maintenance.**

### 9.3 Cron / Cloud Scheduler / Task Scheduler

**None configured.** The schtasks command is commented out — `run_monthly_scan.ps1` does not register itself. To actually schedule, the operator must run that schtasks command interactively.

The dashboard's `wrangler.jsonc` ([leads/leads/wrangler.jsonc](../leads/leads/wrangler.jsonc)) suggests Cloudflare Workers may be the eventual deployment target — but no cron triggers are configured in that file either.

### 9.4 Shadow vs live mode

`SALES_ENGINE_RUN_MODE` is read in [main.py:36](../main.py#L36) and normalised to `shadow` or `live` (default `live`).

**Live mode** runs everything: discovery → intake → scoring → solutions → outreach drafting → Supabase persistence → Notion operating-view sync → Outreach Queue sync → Sales Engine Runs.

**Shadow mode** ([main.py:103-105, 257-262, 282-288](../main.py)):
- **Skips** `OutreachReviewAgent.sync_queue_decisions` ([line 103](../main.py#L103)) — so operator-clicked statuses don't propagate back to Pipeline.
- **Skips** Supabase persistence (`_persist_generated_data` not called).
- **Skips** Notion operating-view sync (`_sync_operating_views`).
- **Skips** Outreach Queue sync (`_sync_outreach_queue`).
- **Still runs:** discovery source collection, autonomous lane seeding, lead discovery promotion (writes to Discovery and Intake Notion DBs), lead research / scoring / messaging in memory, run logging.
- **Lead intake** rows are read but **`mark_processed` is set to `False`** ([main.py:170](../main.py#L170)), so the same intake rows can be re-processed in the next shadow run. Plus shadow re-runs skip rows that already have processed markers (so historical rows aren't re-processed in shadow either).

`ResponseHandlerAgent` uses shadow mode to mean **classify and draft without writing** ([response_handler_agent.py:170-176](../app/agents/response_handler_agent.py#L170-L176)) — passes `shadow_mode=run_mode != "live"` from main.py.

So shadow mode is a "dry rehearsal" — discovery and intake do persist (because they're upstream queues operators populate), but no commercial state changes (Pipeline / Outreach Queue / Supabase) occur.

---

## Section 10 — Honest gaps for SDR daily use

### 10.1 What an SDR can do today

By opening Notion + the Operator Console at 127.0.0.1:8787:

1. See aggregate counts of pending discovery, intake, queue items
2. Browse Lead Discovery rows with filters (status / search) and follow source URLs / website URLs
3. Browse Lead Intake rows with filters
4. Browse Outreach Queue rows; click into a row to see subject / email body / linkedin / follow-up
5. Approve / Hold / Regenerate / Mark-Sent on any queue row
6. See an aggregated Accounts & Buyers view (computed across discovery + intake + queue)
7. See run history with status, counts, error summaries
8. Use keyboard shortcuts (g/d/i/a/q/r/?, Shift+A/H/S/G) for fast nav and queue actions

In the actual Notion workspace (separate UI):

9. Edit any field on any row by hand (change a draft, paste a reply, edit notes, etc.)
10. Add a manual lead to Lead Intake by creating a new row
11. View Pipeline / Tasks / Solutions / Deal Support DBs (none of which are surfaced in the Console)

### 10.2 What's MISSING from "Sara opens her laptop on Monday morning"

A direct list of holes against a typical SDR workflow:

1. **Today queue.** No "here are the 5-15 things you should do today, prioritised by urgency × value". The Console's Dashboard shows totals, not a worklist.
2. **Hot-reply notification.** No ping when a new `replied` arrives. SDR has to remember to check Notion. There's no badge count in the Console or anywhere else.
3. **Reply text visible in queue card.** The Console's queue card doesn't render the `Reply` field. SDR has to open Notion to see what the prospect actually wrote.
4. **Inline draft editing.** Operator can approve or regenerate but not adjust a single sentence before approving. Regen is an all-or-nothing reset.
5. **Send-tracking.** No automatic "this was sent at 09:14, Gmail confirmed delivery". Mark Sent is manual and trust-based.
6. **Open / click / reply analytics.** None.
7. **Inbox integration.** None — replies require manual paste.
8. **Manual lead capture.** No "Sara saw a relevant LinkedIn post and wants to add this person to today's queue" form. She has to go to Notion.
9. **Per-SDR ownership.** No `assigned_to` field, no team filter, no "my queue vs everyone's queue".
10. **Capacity awareness.** Nothing knows how many touches an SDR can handle per day; nothing throttles output to a meaningful per-person max.
11. **Explicit closer-of-loop on inbound.** When a reply lands and gets classified as `positive`, no calendar-booking link is emitted; SDR still has to handle the "what does your week look like" handoff manually.
12. **Multi-touch sequence beyond first + one canned follow-up.** No second follow-up, no "after no reply, send variant B in 7 days".
13. **Phone / LinkedIn DM tracking.** All channels other than email are off-system. No way to log "called and left voicemail" beyond editing Notion.
14. **Pipeline visibility.** Pipeline DB is written but not surfaced in the Console. SDR has no in-tool view of "what stage is each of my prospects at".
15. **Task list.** Execution Tasks DB is written but not surfaced. SDR has no in-tool view of "what's due today".

### 10.3 Filled by existing engine + Console + Notion if SDR is taught to use them

- Today queue → can be approximated by filtering Notion Outreach Queue by `Status=replied OR Status=ready_to_send`, sorted by priority. Workable but clunky.
- Manual lead capture → Notion's UI handles this; the engine processes new `Status=ready` intake rows on the next run.
- Pipeline visibility → Notion Pipeline DB exists; SDR opens it directly.
- Task list → Notion Tasks DB exists; SDR opens it directly.
- Reply text → manually paste into the Outreach Queue's `Reply` field, change `Status` to `replied`. Engine classifies on next run.
- Multi-channel logging → free-text in the Notion Notes field.

So a disciplined SDR with good Notion habits can use what's there. None of it is fast or pleasant.

### 10.4 Genuinely needs new code

- **Inbox ingestion** (Gmail API or IMAP). Without this, replies require manual paste forever.
- **Send tracking** (BCC to a logger / Gmail send confirmation / SMTP relay). Without this, "Mark Sent" is unreliable.
- **Today / next-best-action surface.** Not present in Console; would need either a new Console route or a dashboard view backed by a new API endpoint.
- **Inline draft editing.** Console has no edit form; new POST/PATCH route + textarea in queue card.
- **Multi-touch sequencer.** Beyond the canned follow-up, real cadence logic doesn't exist.
- **Calendar-link emission on positive replies.** Could be a small change inside `ResponseHandlerAgent._draft_response`.
- **Suppression list.** No infrastructure — would need a new table + check during outreach generation.

### 10.5 Gaps the React dashboard could close, and the api/ endpoints needed

The dashboard is well-positioned to close items 1, 2, 3, 4, 9, 10, 11, 14, 15 from §10.2 if the proxy gains a few endpoints:

| Dashboard feature | New API endpoint(s) needed |
|---|---|
| Today queue | `GET /api/notion/today?sdr=<id>` — server-computed prioritised worklist |
| Hot-reply badge / list | Could reuse `GET /api/notion/outreach-queue?status=replied` — present today |
| Reply text in card | Add `reply_text` field to the existing OutreachQueueRecord shape; already in Notion |
| Inline edit | `PATCH /api/notion/outreach-queue/{id}/draft` body `{subject, email, linkedin, follow_up}` |
| Per-SDR ownership | Requires a new Notion property + filter param on existing endpoints |
| Pipeline view | `GET /api/notion/pipeline?stage=<>&priority=<>` |
| Task list | `GET /api/notion/tasks?status=open&priority=<>` |
| Manual lead capture | `POST /api/notion/intake` body `{company, contact, role, email, …}` |
| Mark sent with metadata | Existing `PATCH /api/notion/outreach-queue/{id}/status` works; add `sent_via`, `sent_at` body fields |
| Log activity | `POST /api/notion/pipeline/{lead_reference}/activity` body `{note, channel}` |

All of these are thin wrappers around existing `NotionService` methods — except the Today endpoint and edit endpoint, which need new server logic. None require touching the engine's daily run loop.

---

## Section 11 — Compatibility with the Lovable dashboard

### 11.1 Read paths via existing api/ proxy

For viewing data the dashboard already has the major reads available: `discovery`, `intake`, `outreach-queue`, `runs`. The list above (§10.5) shows what's missing.

For writes the dashboard has: status PATCH (queue, intake), runs note PATCH. **It does not have:** edit drafts, log activity, create manual lead, set pipeline stage, mark task done.

So **for read-only dashboard browsing** + queue status changes + intake status changes + run notes, the existing api/ is sufficient. **For full SDR daily workflow** it isn't — see §10.5.

### 11.2 Schema match: dashboard Supabase vs engine writes

The dashboard's Supabase migrations live at [leads\leads\supabase\migrations\](../leads/leads/supabase/migrations/) — three files dated 2026-04-22:

```
20260422142231_<uuid>.sql   — profiles + has_role / get_my_role / is_admin_or_manager
20260422142250_<uuid>.sql   — uncertain (didn't read)
20260422171426_<uuid>.sql   — uncertain (didn't read)
```

The first migration introduces `public.profiles` with `app_role` enum (`admin` / `manager` / `sdr`), per-SDR fields like `preferred_segments`, `country_focus`, `capacity_per_week`, `on_leave_until`, plus row-level-security helper functions. **The engine has no concept of profiles, roles, or per-SDR ownership** — its Supabase schema in [migrations\0001_initial_sales_schema.sql](../migrations/0001_initial_sales_schema.sql) and [supabase_schema_reference.sql](../supabase_schema_reference.sql) defines `leads`, `outreach_messages`, `pipeline_records`, `solution_recommendations`, `deal_support_packages`, `execution_tasks`. There is no `profiles` table referenced anywhere in `app/`.

So **same Supabase project, different schemas, different responsibilities**. The engine writes the commercial domain tables; the dashboard adds a profiles + RLS layer on top. They're additive but not yet integrated.

The other two dashboard migrations are uncertain — they may add a leads/prospects table the dashboard reads, or extend the engine's tables, or add their own. **A grep for `create table` in those two files would resolve the question.**

### 11.3 Read-only mirror viability

If the engine continues to be Notion-primary and Supabase-archival, the dashboard can absolutely work off the Supabase mirror for read paths. The engine writes commercial tables every live run; the dashboard reads them. The dashboard's profiles/RLS layer adds auth without touching engine writes.

The challenge is **write paths**: status changes, draft edits, manual lead capture. The dashboard cannot write directly to Notion (no Notion client in the React frontend) — it has to go via the api/ proxy. So:
- **Reads:** can come from Supabase directly via the dashboard's existing `@supabase/supabase-js` client.
- **Writes that affect engine state (queue status, draft text, intake status, manual lead):** must route through api/.

This split is fine architecturally as long as the dashboard's reads don't lag behind Notion writes. The engine's live-mode persistence runs Notion-then-Supabase, and Supabase upserts are synchronous within `main.py`, so consistency is per-run not real-time. Operator clicks on the dashboard would need to either re-fetch through the proxy after a write, or trigger a Supabase update concurrently with the Notion update via a new server-side endpoint.

### 11.4 Smallest change set to wire dashboard to engine

In rough order of effort:

1. **Decide read source: api/ proxy or Supabase direct.** If Supabase: confirm the engine's tables match what the dashboard expects, add RLS that lets `sdr` role read commercial tables. If api/: dashboard hits api/ for all data, no Supabase reads at all.
2. **Add the missing GET endpoints** for the dashboard's main views: pipeline, tasks, today. ~150-200 LOC in api/.
3. **Add the missing PATCH/POST endpoints** for write actions: edit-draft, manual-lead, log-activity. ~150-300 LOC in api/.
4. **Add minimal auth** on the api/ — at least a shared-secret header. CORS already permits the dashboard's origin.
5. **Wire dashboard auth to Supabase profiles** — the dashboard already has Lovable.dev cloud-auth scaffolding; tie SDR identity to the api/ shared-secret or a per-SDR JWT.
6. **Optional: emit a "data updated" event** from `main.py` after each live run so the dashboard knows when to re-fetch.

The engine itself shouldn't need code changes for Path A. Everything is in the proxy and the dashboard.

---

## Section 12 — Things you noticed

These are observations a fresh reviewer would flag. Most are not bugs, but worth knowing.

### 12.1 Brand-rule contradiction across generators (already covered in §3.3)

`MessageWriterAgent` writes "GlobalKinect" (one word) into every draft going into Outreach Queue on every daily live run. `OpportunitiesOutreachAgent` and `sales-engine\` both enforce "Global Kinect" (two words) per the brand spec. Two streams of outbound copy with different brand spelling are landing in the same Outreach Queue. The brand spec says "Global Kinect" wins; the daily engine doesn't comply.

### 12.2 Debug print statements in `vibe_prospecting_scan.py`

`explorium_post()` unconditionally prints the full request body and any 4xx response body to stdout. For the monthly scan at full volume that's ~3,200 prospect requests + ~thousands of business pre-query pages = a lot of noisy stdout. Was added to fix the 422 issue and never gated.

### 12.3 `JOB_DEPARTMENT_MAP["administration"] = "operations"` is a guess

[scripts/vibe_prospecting_scan.py:101](../scripts/vibe_prospecting_scan.py#L101). Comment says `# best guess — confirm against enum`. The result is that ICPs A2 (which lists `administration`) will currently filter Explorium prospects on the `operations` job department, which may or may not match what was intended.

### 12.4 The Operator Console doesn't show the Reply field

The flow expects operators to paste replies into the Outreach Queue's `Reply` rich-text property, but the Console's queue card never renders that field. Operators have to remember to do this in the Notion UI, not the Console. Half the response loop runs through the Console; the other half doesn't.

### 12.5 `OutreachReviewAgent.sync_queue_decisions` is documented to handle `replied`, but doesn't

The agent's `ACTIONABLE_QUEUE_STATUSES = {"approved", "sent", "hold"}` ([app/agents/outreach_review_agent.py:32](../app/agents/outreach_review_agent.py#L32)). `replied` is **not** in that set. So when the SDR sets `Status=replied` in Notion, this agent ignores it. The pipeline state for that record stays at whatever it was last set to. Only `ResponseHandlerAgent` reacts to `replied` — and only if there's text in the `Reply` field. If the SDR sets status without text, the loop silently drops the signal.

### 12.6 The api/ proxy references NotionService methods that may not exist

[api/app/routers/notion_proxy.py](../api/app/routers/notion_proxy.py#L175) calls `service.update_outreach_queue_record_status(record_id, body.status)`. Earlier work this session added `update_outreach_queue_status_and_notes(page_id, status, notes)` to NotionService for `ResponseHandlerAgent`. **The proxy's function name doesn't match.** Same risk on `update_lead_intake_record_status` and `append_sales_engine_run_note` ([line 219](../api/app/routers/notion_proxy.py#L219), [line 237](../api/app/routers/notion_proxy.py#L237)) — uncertain whether these methods exist on `NotionService`. Would need a grep / runtime check. If they don't exist, the PATCH endpoints will fail at runtime even though the GET endpoints work.

### 12.7 `_render_accounts` aggregates from Discovery/Intake/Queue, not the Accounts DB

Operator Console's Accounts page ([app/web/operator_console.py:413-496](../app/web/operator_console.py#L413-L496)) computes accounts client-side by walking Discovery + Intake + Queue records — it does NOT read the canonical Notion `Accounts` DB written by `EntityMapperAgent`. So the Accounts view shows pipeline-active companies, not the full Accounts roster.

### 12.8 Discovery sources contain hardcoded `User-Agent`

[discovery_source_service.py:218](../app/services/discovery_source_service.py#L218) hardcodes `"User-Agent": "GlobalKinectSalesEngine/1.0"` (one word, no space). Cosmetic but inconsistent with brand.

### 12.9 `sales-engine\` and main engine share `ANTHROPIC_API_KEY` but use different models

Main engine: `claude-sonnet-4-20250514` (per `.env`/`config.py`).
`sales-engine\`: `claude-opus-4-7` (`CLAUDE_MODEL` default in run_pipeline.py:62).

Two different Claude models on the same API key on the same machine. Cost profiles diverge sharply — Opus is materially more expensive. Per-lead cost in the sales-engine manifest is ~$0.60 just for Perplexity research; the Opus drafting fee on top is uncertain but non-trivial.

### 12.10 `LEADS_ROOT` default in `sales-engine\` was changed

`sales-engine\scripts\run_pipeline.py:57` has `LEADS_ROOT = Path(os.getenv("LEADS_ROOT", r"C:\dev\globalkinect\sales\leads\Reports"))`. The actual lead artefacts in this repo live under `leads\leads\leads\<slug>\` (62 company subfolders), per the audit. So `LEADS_ROOT` either isn't being used by the actual pipeline runs, or someone overrode it via env, or the artefacts predate the current default. **Uncertain.**

### 12.11 `ResponseHandlerAgent` defends with `getattr` to keep tests green

[app/agents/response_handler_agent.py:113-120](../app/agents/response_handler_agent.py#L113-L120) uses `getattr(self.notion_service, "is_outreach_queue_configured", None)` because the test fakes for `main.py` don't have that method. This is a defensive workaround, not a bug — but it means if someone replaces `NotionService` with a stricter test double in the future, the agent silently degrades to "not configured" rather than failing cleanly.

### 12.12 No `pyproject.toml` at the repo root

The main engine uses `requirements.txt` only (no `pyproject.toml` / `setup.py` / `setup.cfg`). The dashboard backend uses `pyproject.toml` + uv. The `sales-engine\` standalone uses its own `requirements.txt`. Three different Python dependency stories within one repo.

### 12.13 No CI / GitHub Actions

I didn't see any `.github/`, `.circleci/`, `.gitlab-ci.yml`, or similar. Tests are run manually via `pytest`. The `.git/hooks/` are stock — no pre-commit.

### 12.14 `.gitignore` is too narrow

Six lines. Doesn't exclude `node_modules`, `.venv`, `dist`, `.next`, `bun.lockb`, `.mypy_cache`, `.ruff_cache`, `graphify-out`. With the dashboard project nested at `leads\leads\`, a fresh dev installing dependencies will see large amounts of untracked content the moment Bun and uv run.

### 12.15 The repo has two embedded git repositories

`leads\leads\.git\` (893 KB) is a separate git repo embedded inside the parent. It is not declared as a submodule. `git status` from the parent treats it as untracked content.

### 12.16 `.claude\settings.json` paths are stale

Permission whitelist references `globalkinect-engines\sales`, `c:\dev\globalkinect-engines\sales\*`. Actual path is `c:\dev\globalkinect\sales`. Hooks and Read permissions for project memory point at a non-existent directory. Already noted in `AUDIT.md`.

### 12.17 ICP definitions are split across at least three places

- `app\agents\opportunities_outreach_agent.py` — the Notion ICP property values (e.g. `"A1 - Frustrated GCC Operator"`) and the MENA/EUROPEAN sets
- `scripts\vibe_prospecting_scan.py` — the ICP filter blobs (A1-B4, no B5)
- `C:\dev\globalkinect\branding\GLOBAL_KINECT_ICP.md` — canonical ICP definitions
- `ICP_SOURCING_PLAYBOOK.md` (root) — sourcing-specific ICP guidance

If an ICP's definition shifts, four places need updating. None are auto-generated from a single source.

### 12.18 `ResponseHandlerAgent` writes the prospect's reply text into Notion Notes

The handler's `_update_queue_page` ([response_handler_agent.py:407-444](../app/agents/response_handler_agent.py#L407-L444)) appends the reply text + classification + drafted response into the queue page's Notes field. Notes can grow unboundedly across multiple replies. There's no truncation or rollup. **Long-running threads may overflow Notion's rich-text limits.** Uncertain if this has hit a limit yet.

### 12.19 The `prompts\` directory in `app\` is empty

[app\prompts\](../app/prompts/) is an empty directory. No prompts live there. The actual agent prompts live inline (in `_build_user_prompt`, `_build_lead_research_instructions`, etc.) inside the Python files. Suggests a planned refactor that didn't happen.

### 12.20 Many of the architectural choices push state toward Notion

The engine treats Notion as the operational source of truth: discovery rows are queried for `Status=ready`, intake rows are read by status, queue decisions are made in Notion, replies are pasted into Notion, run history lives in Notion. Supabase is used for archival/reporting but no agent makes decisions based on Supabase reads — except `ResponseHandlerAgent._fetch_deal_support` and `_fetch_solution_recommendation`, which were added recently.

This is fine while there's one operator and Notion's a comfortable UI. With multiple SDRs, Notion's lack of RLS, the absence of per-SDR ownership in the schema, and the API-rate limits will start to bite. The Lovable dashboard's `profiles` + `app_role` schema points at where this needs to evolve.

---

## Files inspected for this report

- `main.py` (562 lines) — full read
- `scripts\vibe_prospecting_scan.py` — full read
- `scripts\run_monthly_scan.ps1` — full read
- `app\services\config.py` — full read
- `app\services\notion_service.py` — skim (key methods identified; database table list confirmed)
- `app\services\discovery_source_service.py` — partial read (top + middle sections)
- `app\services\anthropic_service.py` — substantial prior read in this session
- `app\agents\lead_scoring_agent.py` — full read
- `app\agents\lead_discovery_agent.py` — full read
- `app\agents\lead_research_agent.py` — full read
- `app\agents\message_writer_agent.py` — full read
- `app\agents\opportunities_outreach_agent.py` — full read (incl. recent edit per system reminder)
- `app\agents\response_handler_agent.py` — full read
- `app\agents\outreach_review_agent.py` — full read
- `app\agents\lifecycle_agent.py` — full read
- `app\web\operator_console.py` — full read
- `api\app\main.py` — full read
- `api\app\routers\notion_proxy.py` — full read
- `requirements.txt`, `discovery_sources.json`, `.env.example`, `migrations\0001_initial_sales_schema.sql`, `supabase_schema_reference.sql` — full reads
- `sales-engine\scripts\run_pipeline.py` — full read
- `sales-engine\prompts\research_prompt.md`, `email_prompt.md` — full reads
- `tests\test_lead_scoring_agent.py` — full read
- `app\agents\` directory listing with mtimes
- `leads\leads\supabase\migrations\` — file list, first migration partial read

Files **NOT** read for this report:
- The two newer dashboard Supabase migrations (uncertain content) — flagged where it matters
- `leads\leads\src\` (React app source) — would be needed to definitively answer §7.5
- `leads\leads\backend\app\` (uv/FastAPI scaffold) — would be needed to assess Phase 1A scope
- The other 17 agent files beyond what was already covered earlier this session
- All `tests\` files except scoring-agent tests
