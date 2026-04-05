# Supabase Schema Reference

This document describes the expected table shapes for the current deterministic GlobalKinect sales engine. It is a practical reference for live Supabase hookup, not an auto-applied migration.

## `leads`

Expected fields:

- `company_name`
- `contact_name`
- `contact_role`
- `email`
- `linkedin_url`
- `company_country`
- `target_country`
- `lead_type`
- `fit_reason`
- `status`
- `score`
- `priority`
- `recommended_angle`

## `outreach_messages`

Expected fields:

- `lead_reference`
- `company_name`
- `contact_name`
- `contact_role`
- `lead_type`
- `target_country`
- `sales_motion`
- `primary_module`
- `bundle_label`
- `linkedin_message`
- `email_subject`
- `email_message`
- `follow_up_message`

## `pipeline_records`

Expected fields:

- `lead_reference`
- `company_name`
- `contact_name`
- `lead_type`
- `target_country`
- `score`
- `priority`
- `sales_motion`
- `primary_module`
- `bundle_label`
- `recommended_modules`
- `stage`
- `outreach_status`
- `created_at`
- `last_updated_at`
- `last_outreach_at`
- `last_response_at`
- `last_contacted`
- `next_action`
- `notes`

## `solution_recommendations`

Expected fields:

- `lead_reference`
- `company_name`
- `contact_name`
- `target_country`
- `sales_motion`
- `recommended_modules`
- `primary_module`
- `bundle_label`
- `commercial_strategy`
- `rationale`

## `deal_support_packages`

Expected fields:

- `lead_reference`
- `company_name`
- `contact_name`
- `lead_type`
- `target_country`
- `sales_motion`
- `primary_module`
- `bundle_label`
- `recommended_modules`
- `stage`
- `call_prep_summary`
- `recap_email_subject`
- `recap_email_body`
- `proposal_summary`
- `next_steps_message`
- `objection_response`

## `execution_tasks`

Expected fields:

- `lead_reference`
- `task_type`
- `description`
- `priority`
- `due_in_days`
- `status`
- `created_at`

## Practical Notes

- `pipeline_records.lead_reference` should be unique because updates and upserts use it as the stable key
- `solution_recommendations.lead_reference` and `deal_support_packages.lead_reference` should also be unique for clean write behavior
- `execution_tasks` can use a composite uniqueness rule across `lead_reference` and `task_type`
- `recommended_modules` is expected to persist as a text array in Postgres-backed Supabase
