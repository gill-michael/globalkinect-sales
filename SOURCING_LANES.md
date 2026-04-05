# Sourcing Lanes

## Objective

The discovery system should use many sourcing lanes, not one narrow source pool.

Collection should be wide. Promotion should be strict.

The purpose of lanes is to separate different commercial hypotheses while still feeding one shared review process.

## Lane Model

Each lane answers a different sales question.

Examples:

- `Expansion Signals`
  Which companies appear to be entering or building in target markets?
- `Payroll Complexity`
  Which companies show signs of payroll scale, compliance burden, or in-country workforce operations?
- `HRIS Maturity`
  Which companies are maturing people systems and HR operating models?
- `Partner Channel`
  Which recruiters, staffing firms, or intermediaries could become referral or channel paths?
- `Manual Strategic Accounts`
  Which named accounts do we want to monitor even when public feed coverage is weak?
- `Buyer Mapping`
  Which sources help identify actual decision owners rather than only company signals?
- `Market Intelligence`
  Which public signals suggest urgency, growth, expansion, or operating change?
- `Reactivation`
  Which historical accounts should be re-reviewed based on prior activity or staleness?

## Config Format

The repository now supports a lane-based discovery source file.

The file can still be a flat list for backward compatibility, but the preferred format is:

```json
{
  "lanes": [
    {
      "lane_label": "Expansion Signals",
      "agent_label": "EOR Expansion Agent",
      "campaign": "Broad MENA employment infrastructure discovery",
      "sources": [
        {
          "company_name": "Example Co",
          "feed_url": "https://example.com/feed",
          "source_type": "careers_feed"
        }
      ]
    }
  ]
}
```

Lane-level defaults such as `lane_label`, `agent_label`, and `campaign` flow into each source unless a source overrides them.

## Manual Signals

The repository now supports `manual_signals` as a source type.

Use this for:

- strategic account notes
- operator research
- hand-entered expansion evidence
- named buyer hypotheses
- non-feed discoveries you still want in the same discovery queue

Example:

```json
{
  "company_name": "Atlas Ops",
  "source_type": "manual_signals",
  "service_focus": "eor",
  "entries": [
    {
      "title": "Atlas Ops planning UAE expansion",
      "summary": "Entity setup planning and regional launch work for the UAE.",
      "source_url": "https://atlas.example/uae-expansion",
      "target_country_hint": "United Arab Emirates",
      "contact_name": "Mina Yusuf",
      "contact_role": "COO",
      "notes": "Manual strategic account note entered by operator."
    }
  ]
}
```

This lets the same discovery pipeline process both feed-collected and manually curated opportunities.

A ready-to-edit set of starter entries is provided in [strategic_account_entries.example.json](/c:/dev/globalkinect-engines/sales/strategic_account_entries.example.json).
Use those entries as templates for the `entries` array inside the live `Manual Strategic Accounts` lane in [discovery_sources.json](/c:/dev/globalkinect-engines/sales/discovery_sources.json).

## Recommended Lane Portfolio

For this project, the source universe should be extremely wide. The lane portfolio should eventually include:

- company careers feeds
- recruiter and staffing feeds
- manual strategic account entries
- press releases and newsroom pages
- launch and expansion announcements
- funding and growth signals
- buyer and leadership mapping sources
- historical pipeline reactivation inputs

The current code supports feed adapters plus `manual_signals`. Additional non-job adapters should be added next rather than forcing everything through jobs logic.

The runtime now also seeds some internal autonomous lanes from existing system data:

- `Buyer Mapping`
  Generated from low-confidence discovery or intake rows that still need a real buyer.
- `Reactivation`
  Generated from held outreach queue rows so they can re-enter structured review.

## Operating Rule

Wide sourcing does not mean wide promotion.

The correct pattern is:

1. collect widely
2. annotate by lane and sourcing agent
3. qualify strictly
4. promote only when buyer readiness is credible
5. review manually before send
