# Decision Playbook

## Purpose

This playbook defines how to make operator decisions in `Lead Discovery`, `Lead Intake`, and `Outreach Queue`.

## Discovery Decisions

### Promote

Promote only when all or most of these are true:

- there is a believable commercial trigger
- the target country is relevant
- the likely buyer or buyer team is identifiable
- the product angle is clear
- the row would help a salesperson start a real conversation

### Review

Keep in `review` when:

- the account could be relevant but evidence is incomplete
- the buyer hypothesis is still weak
- the row is commercially interesting but not yet sendable
- the signal should be enriched before promotion

### Reject

Reject when:

- the row is generic hiring noise
- the market match is weak or incidental
- there is no product angle
- the row does not help drive sales

## Intake Decisions

### Keep Ready

Keep a row in `ready` only when it is genuinely processable.

That means:

- buyer context is usable
- target market is clear
- commercial fit is believable

### Archive Or Reject

Archive or reject when:

- the row is stale
- the row was promoted by mistake
- the row would only produce generic outreach

## Outreach Decisions

### Approve

Approve when:

- the lead is worth contacting
- the draft is specific enough
- the module recommendation makes sense

### Hold

Hold when:

- the account is potentially real but needs more research
- timing is unclear
- the draft is not ready yet

### Regenerate

Regenerate when:

- the lead is valid
- the commercial angle is valid
- the current message is just weak or generic

### Mark Sent

Only mark sent after real execution.

## Hard Stop Conditions

Do not treat a row as send-ready when:

- `Unknown Contact` and `Unknown Role` are both still present
- there is no believable trigger event
- the row came from weak source evidence without enrichment
- the lead exists only because of keyword matching

## Current Priority

At the current stage, bias toward `review` and `reject` over `approve`.

The system is still proving sourcing quality, not maximizing volume.
