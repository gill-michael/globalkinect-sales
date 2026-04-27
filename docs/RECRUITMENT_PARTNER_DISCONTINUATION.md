# Recruitment-partner channel — formally discontinued

**Decision date:** 2026-04-12 (commit `92fbc4e` "Sweeping Alignments").
**Decision owner:** Michael (operator-level call).
**Status:** Discontinued. Not paused.

---

## What was discontinued

The `recruitment_partner` lead type — leads where Global Kinect would
sit behind a recruiter and provide compliant employment + payroll for
their placements. Historically scored equivalently to `direct_eor` and
`direct_payroll` (3 points apiece) in the lead-scoring rubric and
treated as a first-class sales motion (`sales_motion =
"recruitment_partner"`) by `SolutionDesignAgent`.

## What the system does today

1. **`SolutionDesignAgent.create_solution_recommendations` skips
   recruitment_partner leads** with the warning:
   `"recruitment_partner channel is discontinued — this lead should be
   reclassified. Skipping outreach generation."`
   Skip applied in both the with-pipeline and without-pipeline branches.
   No `SolutionRecommendation` is produced for these leads, so they
   drop out of the 1:1 zip that downstream agents assume.

2. **`ProposalSupportAgent.create_deal_support_packages_with_solution`
   skips recruitment_partner leads** with the same warning. No deal
   support package is produced. (Same skip in the legacy
   `create_deal_support_packages` path.)

3. **`LeadScoringAgent._score_lead_type` scores recruitment_partner
   at 0** (was 3). Even if such a lead slips through upstream
   classification, it cannot rise above `low` priority on its lead-type
   contribution alone.

4. **`LeadScoringAgent._recommended_angle_for_lead` keeps a mapping
   for recruitment_partner** as a safety net, but no outreach is
   drafted for these leads downstream so the angle string is purely
   informational for operators inspecting raw leads.

5. **`build_test_leads` in `app/orchestrators/integration_check.py`
   no longer includes a recruitment_partner test lead.** The
   integration validation exercises `direct_payroll` + `direct_eor`
   only.

## What downstream sees

- No queue rows. No outreach drafts. No deal support. No execution
  tasks. The pipeline stops at solution design for these leads.
- A run-level warning per skipped lead in the log so operators see
  the count.

## How to reactivate the channel

If the operator decision is reversed:

1. Remove the `if lead.lead_type == "recruitment_partner": skip`
   guards in `app/agents/solution_design_agent.py` (both branches of
   `create_solution_recommendations`) and
   `app/agents/proposal_support_agent.py` (both branches of
   `create_deal_support_packages_with_solution` and the legacy
   `create_deal_support_packages` path).
2. Restore `recruitment_partner: 3` in
   `app/agents/lead_scoring_agent.py::_score_lead_type`.
3. Re-add a recruitment_partner test lead to `build_test_leads` in
   `app/orchestrators/integration_check.py`.
4. Update or remove
   `tests/test_solution_design_agent.py::test_create_solution_recommendations_skips_recruitment_partner_leads`
   so the canonical assertion of the skip is no longer authoritative.
5. Restore recruitment_partner fixtures in the six tests that were
   updated when the discontinuation landed:
   - `tests/test_crm_updater_agent.py`
   - `tests/test_message_writer_agent.py`
   - `tests/test_proposal_support_agent.py` (×2)
   - `tests/test_solution_design_agent.py::test_create_solution_recommendations_returns_one_per_pair`
   - `tests/test_integration_check.py::test_run_returns_success_summary_with_mocked_services`
6. Delete this document.

## Related building blocks (kept intact)

`SolutionDesignAgent.create_solution_recommendation` (singular,
internal) still maps `recruitment_partner` to its `sales_motion`,
`recommended_modules`, `primary_module`, `bundle_label`,
`commercial_strategy`, and `rationale`. The
`tests/test_solution_design_agent.py::test_recruitment_partner_maps_to_partner_motion_and_bundle`
test exercises this. Reactivation does not require restoring this
behaviour — it has been preserved throughout.

The same is true of the deterministic copy templates in
`MessageWriterAgent` and `ProposalSupportAgent` for the
`recruitment_partner` and `EOR + Payroll` partner-bundle paths.
Those are still in the source code, just not reachable through the
operational entry points.
