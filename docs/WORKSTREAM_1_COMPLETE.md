# Workstream 1 — Fix the bleeding (complete)

**Date:** 2026-04-27
**Posture:** All 8 fixes committed and pushed. Six pre-existing pytest failures unrelated to this workstream remain.

---

## One-line summary per fix

| # | Fix | Commit | Files | Tests |
|---|---|---|---|---|
| 1 | Brand rule: `Global Kinect` (two words) | `b4f1b90` | 6 source files + 1 new test file | +3 tests, all pass |
| 2 | OutreachReviewAgent handles `replied` | `69b2b09` | 3 source files + 1 test file | +2 tests, all pass |
| 3 | Operator Console renders Reply field | `97bde74` | 3 source files + 1 test file | +2 tests, all pass |
| 4 | api/ proxy method-name mismatches | `ab84e08` | 1 new test file | +10 tests, all pass; no source changes (the inspection report was wrong — methods all exist) |
| 5 | Explorium plaintext-email investigation | `775fd41` | 1 doc + 1 probe script | n/a (investigation only) |
| 6 | Comprehensive `.gitignore` | `0c5aad7` | `.gitignore` + new `leads/Reports/.gitkeep` + removed `.mv_test_cross` | n/a |
| 7 | Archive Phase 1A backend scaffold | `a8ee688` (in `leads/leads/` nested repo) | 31 file rename + README header | n/a |
| 8 | `.claude/settings.json` paths | `634a431` | `.claude/settings.json` only | n/a |

---

## Test status

After all 8 fixes:
- **138 tests pass** (was 121 baseline; +17 new)
- **6 pre-existing failures** unrelated to this workstream:
  - `tests/test_crm_updater_agent.py::test_create_pipeline_records_sets_defaults`
  - `tests/test_integration_check.py::test_run_returns_success_summary_with_mocked_services`
  - `tests/test_message_writer_agent.py::test_generate_messages_legacy_method_still_returns_one_output_per_lead`
  - `tests/test_proposal_support_agent.py::test_create_deal_support_packages_with_solution_returns_one_package_per_record`
  - `tests/test_proposal_support_agent.py::test_deal_support_uses_bundle_label_over_lead_type_and_preserves_reference`
  - `tests/test_solution_design_agent.py::test_create_solution_recommendations_returns_one_per_pair`

  These all share a root cause: `SolutionDesignAgent.create_solution_recommendations` now skips `recruitment_partner` leads (logged as "recruitment_partner channel is discontinued — this lead should be reclassified") and the older tests pre-date this skip behaviour, asserting 1:1 mappings that no longer hold. The fix is to update the tests to match current agent behaviour, but the user instructed not to "fix forward" stale tests in this workstream. **Flagged for next session.**

- **1 test stays deselected**: `tests/test_operator_console.py::test_queue_page_renders_outreach_rows` — pre-existing brittle assertion against UI text that was removed earlier this April. Same advice — update or delete the assertion in a focused commit.

---

## Per-fix details

### Fix 1 — Brand rule

Hits found via `rg "GlobalKinect" app/ scripts/ api/`: 7 occurrences in scope. Five replaced with `Global Kinect` (two words). Two intentionally retained with comments:

- `app/services/discovery_source_service.py:222` — HTTP `User-Agent: GlobalKinectSalesEngine/1.0`. RFC 7231 disallows spaces in product tokens; this is wire-protocol identifier, not display copy.
- `app/agents/opportunities_outreach_agent.py:381` — diagnostic error string `"contains one-word 'GlobalKinect'"`. This is the validator's description of what it's rejecting; flipping it to two words breaks the meaning.

The four spec-named "broken" agents (`message_writer_agent`, `lead_scoring_agent`, `solution_design_agent`, `proposal_support_agent`) were already clean — `rg` showed zero hits. The inspection report and earlier audit overstated this.

New file `tests/test_brand_compliance.py` with three regression tests covering `LeadScoringAgent.recommended_angle`, `SolutionDesignAgent.commercial_strategy/rationale`, and `MessageWriterAgent` outputs.

### Fix 2 — `replied` status

Schema:
- `OutreachStatus` literal in `app/models/pipeline_record.py` extended with `"replied"`.
- `CRMUpdaterAgent.update_outreach_status` now special-cases `"replied"` → sets `last_response_at` + `last_contacted`.
- `_default_next_action_for_outreach_status` maps `"replied"` → `"review_and_send_reply"`.

Agent:
- `OutreachReviewAgent.ACTIONABLE_QUEUE_STATUSES` extended with `"replied"`.
- `_should_skip_replied(record)` skips when pipeline already shows `outreach_status="replied"` or stage `"closed"` — idempotent.
- `OutreachReviewSyncResult.replied_count` added; the sync loop counts it.

Order-independent with `ResponseHandlerAgent`: both agents tolerate either order (review sets the metadata; response handler sets the stage based on classification). Two new tests prove this.

### Fix 3 — Reply field rendering

- `OutreachQueueRecord` model gains `reply: str | None = None`.
- `NotionService._build_outreach_queue_record` extracts `reply=self._property_text(page, "Reply")`.
- `_queue_card` adds a `<details>` `Prospect reply` block above email subject. SDR opening a `replied` row sees the prospect's text first.
- Two tests cover present + absent.

### Fix 4 — api/ proxy

Investigation outcome: **all three NotionService methods exist** (`update_outreach_queue_record_status`, `update_lead_intake_record_status`, `append_sales_engine_run_note`). The inspection report was wrong. No source changes needed.

Added `tests/test_notion_proxy.py` (10 tests):
- Each PATCH endpoint hit via `TestClient`
- Recording-fake `NotionService` asserts exact method name and arguments
- Validation paths (unknown status, empty note) tested
- 500/error-header propagation tested

Note: the venv was missing FastAPI even though `requirements.txt` had it. Installed `fastapi` + `uvicorn` via `pip install`.

### Fix 5 — Explorium investigation (no implementation)

Diagnosis ([docs/EXPLORIUM_EMAIL_INVESTIGATION.md](EXPLORIUM_EMAIL_INVESTIGATION.md)):

`/v1/prospects` returns `professional_email_hashed` only — by design, not a bug in our request. Plaintext lives behind paid enrichment endpoints:

| Want | Endpoint | Cost/prospect |
|---|---|---|
| Email plaintext | `/v1/prospects/contacts_information/bulk_enrich` (`contact_types=["email"]`) | 2 credits |
| Email + mobile | same endpoint, default `contact_types` | 5 credits |
| LinkedIn URL | already free on `/v1/prospects` (`linkedin_url_array`) — already extracted today |
| Richer LinkedIn profile (experience, education, skills, company_linkedin) | `/v1/prospects/profiles/enrich` | unknown |

Cost projection at current monthly-scan limits (3,200 prospects):
- Email-only: **6,400 credits/month**
- Email + mobile: **16,000 credits/month**
- Profile enrichment: **3,200 calls/month at unknown cost**

Probe script `scripts/explorium_email_probe.py` (~16 credits per run) is written but **NOT RUN** — awaiting Michael's go-ahead.

### Fix 6 — `.gitignore`

Replaced 6-line ignore with comprehensive coverage. New ignores: `.venv/`, `.mypy_cache/`, `.ruff_cache/`, `*.egg-info/`, `node_modules/`, `.next/`, `.parcel-cache/`, `.vite/`, `.bun/`, `.env.local`, `.env.*.local`, `.DS_Store`, `Thumbs.db`, `.idea/`, `graphify-out/`, plus the orphan `.mv_test_cross` (removed from index via `git rm --cached`). Created `leads/Reports/.gitkeep` to keep that directory alive in fresh clones while ignoring its contents (the SACRED data zone).

Verified `git ls-files` showed no other previously-tracked files in any of the newly-ignored directories beyond `.mv_test_cross`. The earlier audit's claim of "graphify-out/ currently 9MB tracked" was wrong — nothing was tracked there.

### Fix 7 — Archive Phase 1A backend

`leads/leads/` is its own git repository (separate remote `gill-michael/globalkinect-leads.git`). The parent repo doesn't track its contents.

Performed `git mv backend _archived_phase1a_backend` **inside the nested repo**. Git correctly recognised it as a 100% rename across all 31 files. README at the new path was updated with an "ARCHIVED" header above the original quickstart content (preserved for reference).

Confirmed: nothing in the parent repo or the nested repo references `leads/leads/backend` after the rename (`rg leads/leads/backend` → no matches).

### Fix 8 — `.claude/settings.json`

Replaced four occurrences of `globalkinect-engines\sales` (and the project-cache key `c--dev-globalkinect-engines-sales`) with the actual `globalkinect\sales` path. Validated JSON. No new permissions or directories added (per the "minimal edit" instruction).

Note: I had to reset and reapply this commit once because session-accumulated permission entries were polluting the staged diff. The committed diff is now path-renames only.

---

## What was harder than expected

- **Fix 7's nested git repo.** The parent's `git status` showed `leads/leads/` as a single `??` entry — the rename had to happen and commit inside the nested repo, with its own remote (`globalkinect-leads.git`). I pushed both repos at the end so neither stays divergent.
- **Fix 8's permission accumulation.** Claude auto-adds permission entries to `.claude/settings.json` as new commands are run, so `git diff` between sessions shows growth that has nothing to do with the user's intended edit. I reset the file and re-applied only the path-rename edits to keep the commit minimal.
- **Fix 1's brand-compliance test fixture.** First version included a `recruitment_partner` lead, which `SolutionDesignAgent` now silently skips — caused a list-length mismatch downstream in `MessageWriterAgent`. Removed that lead-type from the fixture. The discontinued-channel behaviour is upstream of this workstream.

## Tests added in total

| File | Tests added |
|---|---|
| `tests/test_brand_compliance.py` (new) | 3 |
| `tests/test_outreach_review_agent.py` | 2 |
| `tests/test_operator_console.py` | 2 |
| `tests/test_notion_proxy.py` (new) | 10 |
| **Total** | **17** |

## For Fix 5 — Michael's next step

> **Single question for Michael:** does your Explorium account have credits enabled for the contact-enrichment endpoint, and which level of enrichment do you want — email-only (2 credits/prospect ≈ 6,400/month), email + mobile (5 credits/prospect ≈ 16,000/month), or also richer LinkedIn profile data (cost unknown until probed)?
>
> Once you've answered:
> 1. Run `python scripts/explorium_email_probe.py --region gcc --icp A1` once (~16 credits) to confirm plaintext flows for our actual API key.
> 2. I'll wire `bulk_enrich` (and optionally `/profiles/enrich`) into `vibe_prospecting_scan.py` as a third step. About 60-90 LOC depending on how much profile data you want surfaced.

---

## New technical debt this session created

1. **FastAPI was added as a venv dependency mid-session** to enable Fix 4's tests. The venv now has `fastapi==0.136.1` (not the `0.115.5` pinned in `requirements.txt`). The tests pass with either, but you'll see pip warn next time you sync. Easy fix: `pip install -r requirements.txt --upgrade` to re-pin, or update `requirements.txt` to allow `>=0.115`.
2. **`tests/test_brand_compliance.py` excludes `recruitment_partner`** from the fixture because `SolutionDesignAgent` now skips it. If recruitment_partner is ever reactivated, the test should add it back.
3. **`leads/Reports/.gitkeep` is the file that pinned the rename** detection during Fix 6's commit — git interpreted `.mv_test_cross` removal + `.gitkeep` creation as a rename because both are 0-byte. Functionally fine, but the commit log reads "rename .mv_test_cross → leads/Reports/.gitkeep" which is misleading. Worth a sentence in the commit message if it confuses anyone in `git log`.

## For next session

1. **Address the 6 pre-existing pytest failures** (recruitment_partner skip + 1:1 list assumption mismatch). Decide whether to re-enable recruitment_partner or update the tests.
2. **Address the 1 deselected test** (`test_queue_page_renders_outreach_rows`) — fix or delete the brittle string assertion.
3. **Decide on Fix 5 recommendation** above and act on it. The probe script is ready to run.
4. **Operator Console doesn't show the Pipeline / Tasks / Deal Support DBs.** This is a documented gap from the inspection report (§6). Either surface them in the existing local console or leave them for the React dashboard. Worth a workstream of its own.
5. **`MessageWriterAgent` produces deterministic `commercial_strategy` strings via `SolutionDesignAgent`** that include "Position GlobalKinect …" patterns. The `_strategy_line` method in `message_writer_agent.py` (line ~462 from my earlier read) handles this — it strips the prefix and reformats. Worth confirming it doesn't reintroduce the one-word brand by accident on edge cases not covered by Fix 1's regression test. Consider extending the brand-compliance test with adversarial inputs.
6. **`graphify-out/` is now gitignored.** Existing local copies will linger; future `/graphify` runs will keep regenerating it. Worth deciding whether to track it for navigability or rely on local regeneration only.
