# Project Plan

## Program Intent

This document tracks the GlobalKinect Sales Engine roadmap by operational phase.

## Current Program Phase

- Phase: Testing And Pilot Rollout
- Status: in progress
- Phase start: March 23, 2026
- Primary goal: validate the discovery-first operating model in `shadow` mode
  before scheduled live rollout

## Completed Delivery Phases

### Phase 1: Foundation

- Objective: establish the project structure, core models, services, logging,
  and test harness
- Status: complete

### Phase 2: Lead Pipeline

- Objective: support structured lead intake, normalized lead records, and
  reviewable pipeline inputs
- Status: complete

### Phase 3: Scoring

- Objective: rank opportunities across direct-client and recruitment-partner
  motions
- Status: complete

### Phase 4: Messaging

- Objective: generate commercially realistic outbound messaging from
  deterministic business rules
- Status: complete

### Phase 5: CRM And Persistence Layer

- Objective: persist internal pipeline state and supporting commercial records
  into the system of record
- Status: complete at the code and mocked-test level

### Phase 6: Proposal And Deal Support

- Objective: support call preparation, recap generation, proposal framing, and
  objection handling
- Status: complete

### Phase 7: Live Persistence And Operating Layer

- Objective: connect the deterministic engine into live persistence and live
  operational views
- Status: complete at the code and mocked-test level; live environment
  validation remains part of testing phase

## Active Phase: Testing And Pilot Rollout

- Objective: prove that the current workflow produces useful, low-noise,
  operator-reviewable commercial outputs
- Components:
  - documentation alignment around the current implementation
  - environment validation and integration check execution
  - curated high-trust discovery source setup
  - 5-7 day `shadow` pilot
  - daily operator review loop across discovery, intake, queue, and run logs
  - go/no-go decision for narrow live rollout
- Status: in progress

## Next Phase: Automation, Scheduling, And Reporting

- Objective: operationalize repeatable execution once the pilot proves the
  workflow is useful
- Components:
  - scheduled runs
  - sync monitoring
  - exception handling
  - execution reporting
  - operational dashboards
- Status: next

## Later Phase: External CRM Sync

- Objective: extend the internal operating model into an external CRM once the
  internal workflow is stable in live use
- Components:
  - external CRM mapping
  - sync policy
  - reconciliation rules
  - operator controls
- Status: planned

## Delivery Notes

- `SolutionDesignAgent` remains the commercial source of truth
- the immediate focus is testing quality and operator usability, not adding new
  features
- live rollout should follow a documented shadow pilot rather than a direct
  cutover
- the next major product step after a successful pilot is scheduled execution
  and monitoring
