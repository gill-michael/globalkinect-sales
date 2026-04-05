# Sourcing Agents

## Purpose

The sales engine should not rely on one generic discovery lens. It should use a small set of sourcing agents, each with a specific commercial hypothesis.

All sourcing agents still feed the same `Lead Discovery` queue and the same promotion standard, but they should search for different kinds of useful sales evidence.

## Shared Rule

A sourcing agent is useful only if it helps answer:

- why this company
- why now
- who likely owns the problem
- what GlobalKinect would plausibly sell

If an agent mostly returns interesting hiring activity without a sales case, it should be pruned or tightened.

## Active Agent Types

### `EOR Expansion Agent`

Focus:

- market entry
- first hires in-country
- launch into UAE, Saudi Arabia, Egypt, or wider GCC/MENA
- regional management buildout
- mobility, entity, and compliance setup signals

Good evidence:

- `country manager`
- `general manager`
- `market entry`
- `new market`
- `entity`
- `entity setup`
- `global mobility`
- `mobility`
- `compliance`

Likely buyers:

- `Head of People`
- `COO`
- `Regional GM`
- `Country Manager`

### `Payroll Complexity Agent`

Focus:

- in-country employment scale-up
- payroll operations complexity
- finance and payroll ownership
- compliance-heavy workforce operations

Good evidence:

- `payroll`
- `payroll manager`
- `payroll operations`
- `global payroll`
- `finance director`
- `people operations`
- `compliance`

Likely buyers:

- `Payroll Manager`
- `Finance Director`
- `People Operations Lead`
- `HR Director`

### `HRIS Maturity Agent`

Focus:

- people systems growth
- HR process standardization
- cross-country HR operating model maturity
- systems ownership

Good evidence:

- `hris`
- `people systems`
- `hr systems`
- `people operations`
- `human resources`
- `hr director`

Likely buyers:

- `People Operations Lead`
- `HR Director`
- `HRIS owner`

### `Partner Channel Agent`

Focus:

- recruiters
- staffing firms
- placement partners
- referral-capable intermediaries

Good evidence:

- `recruitment`
- `staffing`
- `placements`
- `talent acquisition`

Likely buyers:

- agency owner
- recruiting lead
- staffing operations lead

## Configuration

Each source in `discovery_sources.json` can now declare an `agent_label`.

That label should describe the sourcing hypothesis, for example:

- `EOR Expansion Agent`
- `Payroll Complexity Agent`
- `HRIS Maturity Agent`
- `Partner Channel Agent`

The label is written into discovery context so operators can see which agent produced the row.

## Operating Guidance

Use multiple sourcing agents when you want more breadth, but do not relax the review standard.

More agents should produce:

- more diverse account signals
- better coverage of `EOR`, `Payroll`, and `HRIS`
- clearer buyer hypotheses

More agents should not produce:

- more generic jobs noise
- more unknown-contact promotions
- more queue volume without better commercial logic

## Current Recommendation

For the current testing phase:

1. keep only agents and sources that repeatedly produce review-worthy rows
2. disable weak feeds quickly
3. let good rows accumulate in `Lead Discovery`
4. promote only when buyer readiness is credible
5. judge the system by operator usefulness, not candidate count alone
