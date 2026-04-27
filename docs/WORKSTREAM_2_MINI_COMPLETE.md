# Workstream 2 (mini) — Complete

**Date:** 2026-04-27
**Posture:** All 5 tasks committed and pushed. **158 passed, 0 failed, 1 deselected** (the still-out-of-scope `test_queue_page_renders_outreach_rows`).

---

## Probe results — headline

Plaintext emails confirmed flowing from `POST /v1/prospects/contacts_information/bulk_enrich` for our API key on a GCC × A1 sample. All 3 probed prospects returned `professions_email` with `professional_email_status: valid`. Mobile/phone fields came back **null** for every prospect — sample-specific or tier-gated, can't tell from `n=3`. Detail at [docs/EXPLORIUM_PROBE_RESULT.md](EXPLORIUM_PROBE_RESULT.md).

## Total Explorium credits consumed this session

**~16-20 credits** for the probe run only (3 prospects × 5 credits for email+phone + 1 profile enrichment). The number isn't surfaced by the API; check the Explorium dashboard for the exact figure.

No other live API calls in this session — the bulk_enrich integration was added with mocked HTTP throughout.

---

## Per-task summary

| # | Task | Commit | Files | Tests |
|---|---|---|---|---|
| 1 | Probe + report | `d2b4558` | `docs/EXPLORIUM_PROBE_RESULT.md` (new) | n/a |
| 2 | Wire bulk_enrich (email-only) | `e607547` | `scripts/vibe_prospecting_scan.py` (+187 lines) + `tests/test_vibe_prospecting_scan.py` (new, 396 lines) | +13 tests |
| 3 | Discontinue recruitment_partner | `a88fdde` | 7 files (4 test files, lead_scoring_agent, integration_check, new doc) | 6 failing tests fixed; +1 canonical skip test |
| 4 | Brand-compliance fixture comment | `78a51c6` | `tests/test_brand_compliance.py` (3 lines) | 0 new |
| 5 | Re-pin FastAPI | `2e2d09c` | `requirements.txt` (1 line) | 0 new |

### Task 1 detail
Probe ran against region=gcc, icp=A1, limit=3. Output captured in full to `docs/EXPLORIUM_PROBE_RESULT.md`. Critical finding: bulk_enrich response shape is `data[i].data.{professions_email, emails[], professional_email_status, mobile_phone, phone_numbers}` — note the **double `data` nesting** (response body → `data` array → each entry has `prospect_id` + nested `data` dict). This shape drives the implementation in Task 2.

### Task 2 detail
**Implementation in `scripts/vibe_prospecting_scan.py`**:
- New constants: `ENRICH_PATH`, `ENRICH_BATCH_SIZE = 50`, `CREDITS_PER_PROSPECT_EMAIL_ONLY = 2`.
- `EnrichmentResult` class with per-id email map, succeeded/failed counts, credits, and a `prospect_ids_in_failed_batches` set so per-row Notes can mark failure types distinctly from "no email on file".
- `_extract_email_from_enriched_record()` helper — prefers `professions_email`, falls back to first non-empty `emails[].address`.
- `enrich_prospect_emails()` — public API. Batches at `ENRICH_BATCH_SIZE`. Tolerates partial failures (logs warning, continues). Sends `contact_types=["email"]` for the cheaper 2-credit-per-prospect rate.
- `--skip-enrichment` CLI flag for development.
- `--dry-run` now also skips enrichment (no API call instead of skipping just the writes).
- `compose_notes()` surfaces `enrichment_credits` and `enrichment_failed: true` per row.
- `run_scan()` summary block split out enrichment counters.
- Notion intake-page write prefers enriched email > prospects-endpoint email > blank.

**Tests (13 new) in `tests/test_vibe_prospecting_scan.py`**:
- 4 unit tests for `_extract_email_from_enriched_record` (prefers professions_email, falls back to emails array, returns None on empty, defensive on malformed).
- 6 unit tests for `enrich_prospect_emails` (empty input, happy path, batches at max size, partial batch failure, full failure, succeeded-batch with no email returned).
- 3 integration tests for `run_scan()` with mocked Explorium + Notion: end-to-end Email property population, --skip-enrichment skips bulk_enrich, --dry-run skips enrichment AND Notion writes.

### Task 3 detail
Discontinuation traced to commit `92fbc4e` (2026-04-12, "Sweeping Alignments"). The skip lives in both `SolutionDesignAgent.create_solution_recommendations` and `ProposalSupportAgent.create_deal_support_packages_with_solution`. Source-side changes:
- `LeadScoringAgent._score_lead_type`: `recruitment_partner` 3 → 0.
- `LeadScoringAgent._recommended_angle_for_lead`: kept the mapping with a safety-net comment.
- `app/orchestrators/integration_check.py::build_test_leads`: replaced the recruitment_partner test lead with a direct_eor lead so the integration check exercises two distinct active types.
- New canonical test `test_create_solution_recommendations_skips_recruitment_partner_leads` in `tests/test_solution_design_agent.py` that asserts skip behaviour with a 3-lead fixture.
- Existing `test_recruitment_partner_maps_to_partner_motion_and_bundle` preserved as building-block coverage with a docstring.
- All 6 previously failing tests now pass.
- Decision documented in `docs/RECRUITMENT_PARTNER_DISCONTINUATION.md` with full reactivation procedure.

### Task 4 detail
Comment in `tests/test_brand_compliance.py` rewritten from "workaround for the skip behaviour" framing to "the channel is formally discontinued, see the doc". 3-line edit.

### Task 5 detail
`requirements.txt`: `fastapi==0.115.5` → `fastapi==0.136.1` (the version actually installed mid-Workstream-1). Pytest passes. Other transitive deps (`starlette`, `annotated-doc`) are fastapi's own; not pinned in requirements.txt. If reproducibility tightens further later, adding starlette/annotated-doc pins would be a follow-up.

---

## Tests added in total

| File | Tests added |
|---|---|
| `tests/test_vibe_prospecting_scan.py` (new) | 13 |
| `tests/test_solution_design_agent.py` | 1 (new canonical skip test) |
| **Total** | **14** |

Final test count: **158 pass, 0 fail, 1 deselected** (`test_queue_page_renders_outreach_rows` — pre-existing brittle UI-text assertion, still out of scope).

---

## What was harder than expected

- **The bulk_enrich response shape has `data[i].data.{...}`** — double-nested under "data". Easy to miss when reading the spec. The probe surfaced this clearly; tests assert against the doubly-nested shape.
- **`ProposalSupportAgent` has the same recruitment_partner skip as `SolutionDesignAgent`.** I'd assumed it was only the latter. Caught when fixing test_proposal_support_agent.py — both proposal tests had to drop their recruitment_partner fixtures, not just construct different SolutionRecommendation inputs.
- **The integration_check failure had a different root cause** than I expected. It wasn't a test-fixture issue — it was that `build_test_leads` in production code creates a recruitment_partner lead, and downstream `crm_updater_agent.create_pipeline_records_with_solution` enforces a strict 1:1 `len(leads) == len(solution_recommendations)` zip. With the recruitment_partner skipped, lengths mismatched and the integration check raised. Fix was a production-code change (replace the test lead) rather than a test edit.
- **One assertion in `test_proposal_support_agent.py` referenced "partner-ready EOR + Payroll offer"** — copy that came specifically from the recruitment_partner template path. Replaced with assertions against the equivalent direct_eor copy. The test is now slightly weaker (no more recruitment-specific text-coverage) but the bundle-label / motion / reference assertions still cover the test's intent.

---

## What's new for next session

1. **The deselected `test_queue_page_renders_outreach_rows` is still pre-existing.** Not in scope this session, not in the 6 fixed by Task 3. Worth a focused commit to either fix the brittle assertion or delete it.

2. **Mobile/phone enrichment is unverified.** The probe sent `contact_types=["email", "phone"]` but every prospect returned `mobile_phone: null` and `phone_numbers: null`. Could be sample-specific (n=3 GCC-finance leaders) or tier-gated. If Michael wants mobile in Notion, the next step is a larger-sample probe (10-30 prospects across regions) to determine whether phone data ever flows. **Cost ~50-150 credits** for that.

3. **Profile enrichment is also unverified beyond a single sample.** The probe called `/v1/prospects/profiles/enrich` once and got rich experience/education data. Cost per call is undocumented. If Michael wants profile data on every prospect, next step is a 5-10 prospect probe to gauge cost, then a wiring decision.

4. **`bun.lockb` is now in the dashboard project's lockfile but `requirements.txt` for the parent's Python world is incomplete.** `starlette` and `annotated-doc` (transitive fastapi deps) aren't pinned. If reproducibility starts to bite, a fuller `pip freeze > requirements.lock` would help.

5. **The `_score_lead_type` change to recruitment_partner=0** means historical leads of that type now arrive at lower priority on re-run. If any historical recruitment_partner leads had high scores in the engine's Supabase / Notion tables, those scores will drift on the next live run. Consider an audit query on existing pipeline_records before the next monthly run.

6. **The brand-compliance test is now the only place asserting "Global Kinect" on outputs.** It runs on `LeadScoringAgent`, `SolutionDesignAgent`, and `MessageWriterAgent` outputs. It does not cover `ProposalSupportAgent` or `OpportunitiesOutreachAgent` outputs. Worth extending if either of those drifts back to "GlobalKinect" in future edits.
