# Conventions

Lessons-learned and durable rules that aren't already encoded in the spec or
the architecture doc. Added to as we go; each entry is dated and cites the
incident or task that surfaced it.

---

## Concurrency and ordering

**Any code path that depends on a pre-existing row's absence (i.e., acts as a
dedup or insert-or-skip layer) must run on every input, not only the inputs
that survive an upstream filter. Place it as early in the flow as the data
shape allows.**

*Surfaced 2026-05-03 during Task 9 (Vibe Prospecting rewire). The
sales-Supabase write was initially placed inside the post-Notion-dedup branch
of the for-loop; on the dedup re-run, Notion's existing duplicate-detection
short-circuited every prospect and the sales-Supabase write was never even
attempted. Moving the call up — to run for every real prospect, before any
Notion-side filter — restored the intended independence between the two
write paths and made sales-Supabase's own dedup observable.*
