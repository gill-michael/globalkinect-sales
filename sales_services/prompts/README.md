# Sales Services — Prompts

Promoted from `sales-engine-v2/prompts/` on 2026-05-03 as part of the
pre-Week-1 cleanup (Spec 0001a). The standalone pipeline scripts that
consumed these prompts (`run_pipeline.py` in both `sales-engine/` and
`sales-engine-v2/`) are preserved only in git history under tag
`week-1-pre-verification`.

These prompts are intended to be called as services from the agent system.
Wiring happens in Week 2.

| Prompt | Purpose |
|---|---|
| `research_prompt.md` | Perplexity sonar-deep-research per Contact |
| `email_prompt.md` | Claude Opus first-touch outreach email |
| `sequence_prompt.md` | 5-touch multi-channel cadence |
| `call_prompt.md` | Bespoke cold call script + objection handling |
| `linkedin_prompt.md` | Connection note + DM + InMail kit |
