# Archived: Phase 0 design docs

**Read first:** `docs/SYSTEM.md`. That is the current source of truth.

These documents predate the audit of the actual system. They describe an
aspirational design that diverged from what was built — a clean-room
sales-intelligence platform with HubSpot integration, a separate Postgres
on Google Cloud SQL, and a 10-task Phase 1A scaffold. None of that is
what shipped. The actual system uses Notion as the operational store and
Supabase as a mirror, with no HubSpot integration. The "Phase 1A" backend
scaffold was archived in Workstream 1 Fix 7 — see
`leads/leads/_archived_phase1a_backend/`.

The seven docs are retained for historical reference:

| File | What it describes |
|---|---|
| `01-vision.md` | Original vision: weekly cadence, HubSpot as workspace, AI intelligence layer |
| `02-schema.md` | Canonical Postgres schema spec (5 layers, dozens of tables) |
| `03-hubspot-contract.md` | HubSpot integration data-flow contract |
| `04-repo-and-tasks.md` | Repository scaffold + 10 sequenced Claude Code tasks |
| `05-amendments.md` | Post-design-review amendments (14 weaknesses, 3 clarifications) |
| `06-phase1a-revised-plan.md` | The HubSpot-free 3-month build, replacing tasks 09-10 |
| `07-signal-detection-addendum.md` | MVP signal-ingestion plumbing (lane infrastructure) |

**The eighth doc** (`review.md`) referenced in some session briefs was
never written — only seven Phase 0 design docs ever existed.

**If you find yourself reading these for current behaviour, stop and
read `docs/SYSTEM.md` instead.** Where the docs here disagree with the
code, the code wins; SYSTEM.md captures what wins.
