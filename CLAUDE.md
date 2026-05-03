# Global Kinect Sales Engine — Claude Instructions

## What this folder is
The automated sales sourcing engine. A Python application that
discovers, qualifies, and queues outbound leads using Supabase
for persistence and Notion for the human-facing pipeline interface.
Anthropic Claude is used for lead scoring and message generation.

## Read these files before starting any task
1. README.md — full architecture and setup overview
2. AGENT_REGISTRY.md — agent responsibilities and status
3. ICP_SOURCING_PLAYBOOK.md — ICP targeting and sourcing logic
4. DECISION_PLAYBOOK.md — qualification and routing criteria
5. OPERATOR_GUIDE.md — day-to-day operation

Also read the branding ICP definitions before touching
any lead scoring or outreach logic:
C:\dev\globalkinect\branding\GLOBAL_KINECT_ICP.md
C:\dev\globalkinect\branding\outreach\OUTREACH_VOICE.md

## Non-negotiable rules

**ICP definitions:** The canonical ICP definitions live in
C:\dev\globalkinect\branding\GLOBAL_KINECT_ICP.md.
The sales engine must not redefine or contradict them.
If a discrepancy exists between ICP_SOURCING_PLAYBOOK.md
and the branding ICP file, the branding file wins.

**Outreach copy:** All generated outreach copy must pass
the rules in OUTREACH_VOICE.md. No "GlobalKinect" one word.
No partner network references. No product names.

**Data:** Never hardcode Supabase credentials or Notion IDs.
All secrets come from .env (see .env.example).

**Shadow mode:** No outreach is sent automatically.
All generated messages are queued for human review.
Shadow mode is always on unless Michael explicitly disables it.

## Quality checklist
- [ ] No hardcoded credentials or API keys
- [ ] Shadow mode is on — no auto-send
- [ ] Generated copy reviewed against OUTREACH_VOICE.md
- [ ] ICP scoring consistent with branding/GLOBAL_KINECT_ICP.md
- [ ] pytest passes before any deployment

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `graphify update .` to keep the graph current (AST-only, no API cost)

## Business knowledge vault

Queryable vault at `C:\dev\globalkinect\brain\` (Obsidian).
Claude Code MCP (default port 27124) exposes the vault — query
it for brand rules, ICP detail, compliance facts, SOPs,
competitor positioning, decision history, and client context.

Use the vault for: business questions, historical decisions, deep
brand rules, compliance specifics, client context.
Use repo files for: current implementation detail and shipping code.

## Restricted paths

Never read, open, or list files under `C:\dev\globalkinect\keys\`.
If a task requires a credential, stop and ask — do not attempt to
read from `keys\`.

## Error handling

- **MCP failures** (Obsidian vault unreachable, graphify query
  fails): retry once, then log and continue with what is at hand.
  Never fabricate vault content from training data.
- **External content** (outreach, published copy, client
  communication): never ship if an enrichment step (ICP hook
  lookup, compliance lookup, brand check) failed. Log and flag
  for review instead.
