# Implementation Backlog

## Purpose

This document is the practical backlog after the current repo improvements.

It separates work that is now implemented from work that still remains.

## Now Implemented

- operator guide set
- sourcing strategy and sourcing agents docs
- lane-based source configuration
- `manual_signals` source type
- manual strategic accounts lane
- market intelligence lane scaffold
- buyer mapping lane scaffold
- reactivation lane scaffold
- stricter buyer-readiness promotion gate
- discovery dedupe fix
- lane labels on discovery context
- lightweight enrichment fields:
  - `buyer_confidence`
  - `account_fit_summary`
- lane-level run summaries in run notes

## Still Remaining

### 1. Real Non-Job Fetch Adapters

The architecture now supports wider sourcing, but the only automated fetch adapters are still feed/job oriented.

Still needed:

- newsroom or press-release adapter
- generic RSS intelligence adapter for market-intel sources
- structured buyer-mapping adapter where possible

### 2. Automatic Reactivation Mining

The reactivation lane exists in config but is not yet automatically populated from historical pipeline or queue data.

### 3. Automatic Buyer Mapping

The buyer-mapping lane exists, but buyer discovery still depends on manual input or signal inference.

### 4. Richer Enrichment

The current enrichment is intentionally lightweight.

Still needed:

- account size hint
- company stage hint
- entity-presence hint
- urgency hint
- verified channel confidence

### 5. Lane-Level Dashboarding

Lane summaries are now written into run notes, but the operator console does not yet surface lane metrics explicitly.

### 6. Marketing Asset Layer

The pipeline still lacks reusable content assets such as:

- proof points
- country value props
- objection libraries
- persona-specific collateral

## Suggested Next Build Order

1. automatic reactivation mining
2. buyer-mapping enrichment
3. market-intelligence feed adapters
4. richer enrichment model
5. lane-level dashboard views
6. marketing asset layer
