# Pipeline Gaps

## Purpose

This document lists the major commercial and operational gaps that still exist in the GlobalKinect sales engine from a marketing and sales management perspective.

## Current Strengths

The pipeline now has:

- discovery lanes
- source collection
- qualification
- intake normalization
- deterministic scoring
- solution recommendation
- draft outreach generation
- operator review surfaces
- run logging

That is a solid internal workflow base.

## Major Missing Pieces

### 1. Ideal Customer Profile Framework

The system can classify signals, but it still does not hold a strong ICP model.

Missing:

- account size bands
- geography priority beyond target-country matching
- preferred company stage
- preferred operating complexity
- fit exclusions

Why it matters:

- without a stronger ICP, the system can still surface interesting rows that are not the best revenue opportunities

### 2. Buyer Mapping As A First-Class Stage

Buyer readiness is still too weak.

Missing:

- dedicated buyer-mapping lane
- named decision-maker enrichment
- stronger role-to-product mapping
- confidence scoring for buyer ownership

Why it matters:

- the usefulness of the pipeline depends on whether sales can identify who actually owns the problem

### 3. Account Enrichment

The pipeline still lacks broader company enrichment.

Missing:

- company size
- funding stage
- current footprint
- existing entity presence
- hiring scale
- operating model context

Why it matters:

- product fit and urgency are much easier to judge when the account is enriched

### 4. Campaign And Segment Strategy

The engine produces opportunities, but it does not yet organize them into clear campaigns.

Missing:

- segment-specific campaigns
- message families by motion
- country-specific outreach variants
- industry-neutral but persona-aware messaging tracks

Why it matters:

- sales and marketing need repeatable motion, not just isolated lead handling

### 5. Reactivation And Pipeline Mining

The config now has a reactivation lane, but the runtime does not yet mine historical data automatically.

Missing:

- stale-opportunity resurfacing logic
- prior no-response follow-up logic
- old approved-but-unsent queue resurfacing

Why it matters:

- reactivation is often one of the highest-efficiency sources of pipeline

### 6. Marketing Content Layer

The system can draft outreach, but it lacks a broader marketing asset layer.

Missing:

- proof points
- one-pagers
- country-specific value props
- objection handling by product line
- persona-specific collateral

Why it matters:

- good outreach depends on clear underlying positioning assets

### 7. Contact Verification And Channel Readiness

The system does not yet verify whether a contact route is usable.

Missing:

- verified email presence
- LinkedIn profile confidence
- fallback contact strategy
- buyer-team routing when a named contact is unavailable

Why it matters:

- a lead with no reachable path is not yet execution-ready

### 8. Revenue And Funnel Reporting

The pipeline logs operational output, but it does not yet report commercial performance deeply enough.

Missing:

- sourced accounts by lane
- reviewed vs promoted by lane
- outreach approved vs held
- meetings booked
- opportunity creation
- pipeline value by motion

Why it matters:

- management needs to know which lanes are commercially productive

### 9. SLA And Operating Cadence

The system has actions, but not enough management rhythm.

Missing:

- review SLA for discovery rows
- response SLA for queue items
- ownership for cleanup and enrichment
- weekly source pruning cadence

Why it matters:

- without cadence, the pipeline becomes a pile of rows rather than a managed commercial process

### 10. Clear Handoff Between Marketing And Sales

The pipeline is still mostly sales-ops driven.

Missing:

- clear MQL-to-SQL style definitions
- account-ready vs outreach-ready distinction
- lane ownership
- criteria for handing a lead to active selling

Why it matters:

- a good commercial pipeline needs role clarity, not just automation

## Recommended Priority Order

If acting as a sales and marketing manager, the next priorities should be:

1. buyer mapping
2. ICP definition
3. account enrichment
4. campaign/segment strategy
5. reactivation automation
6. reporting by lane
7. marketing asset layer

## Immediate Repo-Level Next Steps

1. Add a dedicated `Buyer Mapping` lane to `discovery_sources.json`
2. Add a simple account-enrichment model to discovery or intake records
3. Add lane-level reporting to `Sales Engine Runs`
4. Add campaign and persona guidance to messaging
5. Add a stricter distinction between `account hypothesis`, `qualified lead`, and `send-ready opportunity`
