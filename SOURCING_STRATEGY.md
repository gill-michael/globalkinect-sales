# Sourcing Strategy

## Objective

The purpose of sourcing in this project is to produce sellable commercial opportunities for GlobalKinect's employment platform, not to collect interesting hiring activity.

The engine should help operators answer four practical questions:

1. Which companies are showing signs that they may need `EOR`, `Payroll`, `HRIS`, or a bundle?
2. Why does that need plausibly exist now?
3. Who is the most likely buyer or buying team?
4. Is there enough evidence to justify outreach?

If the system cannot answer those questions, it has not produced a useful lead.

## Core Principle

Do not confuse a market signal with a buyer.

A job posting, expansion note, funding round, or country launch can be useful evidence. None of those are the lead by themselves. The useful lead is the combination of:

- an account with plausible need
- a trigger event
- a target geography
- a likely buyer or buying team
- a reasoned commercial angle

The sourcing system should therefore prioritize `account and buyer discovery`, not `job discovery`.

## Commercial Scope

The platform can serve companies across industries. Industry should not be the main filter.

The main qualifying dimensions are:

- geography
- workforce pattern
- expansion stage
- employment infrastructure complexity
- buyer plausibility
- urgency

This means sourcing should stay broad across sectors while remaining strict on commercial relevance.

## What Counts As A Useful Lead

A useful lead usually has all or most of the following:

- a company operating in or expanding into UAE, Saudi Arabia, Egypt, or wider GCC/MENA
- evidence of in-country hiring, distributed hiring, market entry, or workforce scaling
- a plausible reason they need employer infrastructure, payroll support, or people systems
- a likely buyer or buyer team
- enough context to write a credible first message

Useful leads do not require perfect contact enrichment on day one, but they do require a believable commercial case.

## What Counts As Noise

The following are usually noise unless additional evidence changes the picture:

- isolated engineering roles with no people, payroll, compliance, mobility, or expansion signal
- generic sales or business development hiring with no workforce-operations relevance
- single-country roles outside target markets without expansion implications
- job posts that mention a target market only incidentally
- rows with no plausible buyer and no clear trigger event

## Buyer Personas

The engine should preferentially look for these buyers or buying teams:

- `Head of People`
- `VP People`
- `People Operations Lead`
- `HR Director`
- `Payroll Manager`
- `Global Mobility Lead`
- `Finance Director`
- `CFO`
- `COO`
- `Operations Director`
- `Regional General Manager`
- founder or CEO for smaller firms entering a new market

Different products map to different buyer patterns:

- `EOR`
  Usually expansion, market-entry, hiring-before-entity, or fast-hire scenarios.
- `Payroll`
  Usually active in-country employment, growing headcount, compliance burden, or fragmented payroll operations.
- `HRIS`
  Usually scaling people operations, cross-country standardization, reporting, or process maturity.

## Signal Framework

Treat sources as evidence layers, not as the lead itself.

### Tier 1: Account Signals

These are the strongest inputs for finding companies worth targeting:

- expansion into UAE, Saudi Arabia, Egypt, or nearby markets
- opening an office, entity, branch, or local team
- remote hiring across multiple countries
- funding rounds followed by international hiring
- local market launch announcements
- partner ecosystem announcements with regional execution implications
- explicit hiring for payroll, people operations, HR, mobility, compliance, or finance operations

### Tier 2: Buyer Signals

These help identify who to approach:

- named leaders in People, HR, Finance, Operations, or Mobility
- public team pages
- leadership announcements
- LinkedIn or company pages showing regional people or finance ownership
- decision-maker roles appearing in hiring plans

### Tier 3: Fit Signals

These help choose the right commercial angle:

- first hires in a new market
- multiple hires in one target country
- cross-border or distributed hiring language
- payroll or compliance references
- entity setup or local registration references
- people ops or HR stack standardization references

## Source Types

The source mix should be broader than career boards.

### Primary Sources

These should drive the sourcing strategy:

- company announcements and newsroom pages
- expansion and launch announcements
- funding and growth signals
- company team and leadership pages
- public employee and leadership profiles
- regional business directories
- founder, finance, HR, and operations pages that help identify buyers

### Secondary Sources

These can still be useful, but should not be the main engine:

- Greenhouse boards
- Lever boards
- other public jobs feeds

Use jobs data as supporting evidence of expansion or workforce complexity, not as the default source of leads.

## Qualification Standard

The sourcing system should only promote a lead when it can reasonably state:

- `why now`
- `why this company`
- `why this buyer`
- `why this product angle`

Every promoted lead should ideally carry:

- company name
- target country
- evidence summary
- trigger event
- buyer or buyer team hypothesis
- recommended motion: `EOR`, `Payroll`, `HRIS`, or bundle
- notes explaining the commercial logic

## Practical Outreach Standard

If a human operator cannot answer these questions in under a minute, the lead is not ready:

- What happened?
- Why does it matter commercially?
- Who should we approach?
- What are we actually offering?

The outreach queue should contain only leads that pass that standard.

## Implications For This Codebase

The current discovery implementation is useful as an early signal collector, but it is not yet sufficient as the primary sourcing model because it overweights job-feed evidence.

The next iteration should move the system toward:

1. broader source coverage across account, buyer, and fit signals
2. multiple valid discovery rows per company when the triggers are distinct
3. explicit buyer-persona mapping
4. better explanation fields in discovery and intake
5. clear rejection of raw hiring activity that lacks a sales case

## Immediate Operating Guidance

During testing phase, use this rule:

- keep job-board sourcing as a signal layer
- do not treat job-board hits as send-ready leads
- require a buyer hypothesis before promotion to meaningful outreach
- reject any row that does not help an operator sell

## Success Criteria

Sourcing is working when:

- discovery rows are commercially intelligible
- operators can explain the sales case quickly
- promoted leads have plausible buyers
- outreach drafts feel specific rather than generic
- the queue contains fewer rows, but materially better ones
