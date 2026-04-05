# Persistence Realignment Notes

## Purpose

This note records the likely persistence changes needed to store solution design data after the current review phase.

## Current State

The current Supabase persistence layer stores:

- `leads`
- `outreach_messages`
- `pipeline_records`
- `deal_support_packages`

This is sufficient for the current workflow, but it does not yet persist the new bundle-based platform recommendation layer.

## Likely Future Persistence Additions

The system will likely need a new persisted structure for solution recommendation data.

Suggested future fields:

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

## Likely Schema Direction

The cleanest next step will probably be a dedicated table such as:

- `solution_recommendations`

This keeps the bundle-design layer explicit and avoids overloading existing tables.

## Why This Is Not In Code Yet

- the platform realignment is still in a review phase
- existing persistence should remain stable while the new commercial model is inspected
- downstream agents are not yet fully refactored to consume persisted solution recommendations

## Recommended Next Persistence Step

After business review of the transition layer:

1. finalize canonical bundle fields
2. add Supabase table support for solution recommendations
3. extend `SupabaseService` with insert and fetch methods for that table
4. update downstream modules to read from the solution recommendation instead of inferring from `lead_type` alone
