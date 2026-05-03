# Audit Protocol

**Status:** Draft v1 — pending first use
**Owner:** Michael (sole technical founder, Global Kinect)
**Last updated:** 2026-05-03

---

## Purpose

An audit captures the **actual shape** of a system, not its intended shape. It is the ground-truth document that every subsequent architectural decision, specification, and Claude Code session reads first.

Audits exist because:

1. **Code drifts from intent.** Documentation lies, READMEs go stale, scripts get half-modified and never tested.
2. **AI tools amplify drift if unconstrained.** Claude Code without a baseline truth document will confidently produce code that contradicts what already exists, or duplicates it, or breaks it.
3. **Solo founders forget.** Six months from now, you won't remember why a script does what it does. The audit is the institutional memory.

An audit is **read-only work**. It records what is, not what should be. Recommendations and changes go into a separate document (a spec or an ADR), produced *after* the audit is reviewed and accepted.

---

## When to audit

| Trigger | Audit type |
|---|---|
| First time touching an existing system | **System audit** — the full repo / tool / data shape |
| Before integrating with a new external tool | **Integration audit** — the tool's API, data model, current state |
| When something behaves unexpectedly | **Behavioural audit** — the actual flow vs. the documented flow |
| Before a major refactor | **Refactor audit** — the dependencies, the assumptions, the test coverage |

---

## What every audit must capture

The fields below are mandatory. Missing fields are flagged in the audit document, not silently omitted.

### 1. Scope and boundaries
- What this audit covers (paths, files, services, accounts).
- What it explicitly excludes and why.
- The state of the world at the time of audit (date, git commit hash if applicable, account state).

### 2. Inventory
A complete listing of artefacts in scope. For a code audit:
- Every file by path and purpose.
- Every dependency (with version).
- Every config file and what it configures.
- Every external service touched.

For an external-tool audit:
- Every account, workspace, or tenant.
- Every API key, credential, or token (referenced by name only — never the value).
- Every active integration, webhook, or sync.

### 3. Behaviour vs. intent
For each significant artefact:
- **Intent:** what the file/service is supposed to do (per its documentation, comments, or naming).
- **Actual behaviour:** what it does when run, observed empirically.
- **Gap:** any divergence, with severity (critical / important / cosmetic).

### 4. Assumptions
Implicit assumptions baked into the system that aren't documented elsewhere. Examples:
- "This script assumes the CSV has these specific columns."
- "This API call assumes the rep is logged into HubSpot in the same browser session."
- "This prompt assumes Perplexity returns citations in this exact format."

These are gold. They are the things that will silently break when something upstream changes.

### 5. Fragility and risk
- What is most likely to break.
- What has known issues but is "working enough."
- What has no tests.
- What has no error handling.
- What has hardcoded values that should be config.
- What has secrets in plaintext (this is severity-critical).

### 6. State and credentials
- What credentials are required to run this system.
- Where those credentials are stored.
- Whether they're committed to git (if yes — severity-critical).
- Whether they're documented (in `.env.example` or similar).

### 7. Working / broken / stale
A simple three-bucket classification of every artefact:
- **Working:** runs, produces correct output, used recently.
- **Broken:** runs but produces wrong output, OR doesn't run at all.
- **Stale:** historical, no longer used, candidate for deletion.

Stale code is dangerous because it confuses future readers. Calling it out explicitly is the audit's job.

### 8. Findings and questions
- Things the auditor wants to flag for the human reviewer.
- Decisions that have been made implicitly that should probably be made explicitly.
- Things that don't make sense and may indicate a misunderstanding by the auditor.

This section is where the auditor's *judgement* lives. Everything else is observation.

---

## What an audit does NOT do

- **Does not propose changes.** Recommendations live in specs and ADRs. The audit captures what is.
- **Does not refactor.** Read-only. No edits, no commits, no fixes.
- **Does not assume correctness.** The auditor challenges every artefact: does this actually do what it claims?
- **Does not pad.** Brevity is a virtue. If a section is short because there's nothing to say, the section is short.
- **Does not invent context.** If the auditor doesn't know something, the audit says "unknown" — never guesses.

---

## How to run an audit (the protocol)

### Step 1: Define scope
Write the scope and boundaries section first, before any reading. This forces clarity about what's being audited.

### Step 2: Inventory mechanically
Use `tree`, `git ls-files`, or directory listing to produce a complete file inventory. No interpretation yet.

### Step 3: Classify each artefact
For each file: is it code, config, prompt, doc, data, or other? Apply the working/broken/stale classification.

### Step 4: Read everything
Yes, every file in scope. Speed-read where possible, but every file gets opened. Skipping files is how audits miss the important thing.

### Step 5: Run what can be run
Where possible, execute scripts (in dry-run mode if available) to observe actual behaviour. Note any errors verbatim.

### Step 6: Capture findings
Produce the audit document in the standard format (template below). Every section filled, even if briefly.

### Step 7: Human review
The audit is a draft until reviewed by the human. The reviewer's job is to challenge: is this finding correct? Is anything missing? Is the auditor wrong about anything?

### Step 8: Accept and freeze
Once accepted, the audit is the canonical baseline. Subsequent audits compare against it. The audit document is committed to the repo and never edited (a new audit supersedes it; the old one stays as history).

---

## Audit document structure

Every audit document follows this structure:

```markdown
# Audit NNNN — <descriptive name>

**Date:** YYYY-MM-DD
**Auditor:** <human or AI tool, with version if AI>
**Reviewer:** <human who accepted the audit>
**Status:** Draft / Accepted / Superseded by Audit MMMM
**Supersedes:** (previous audit number, if applicable)

---

## 1. Scope and boundaries
## 2. Inventory
## 3. Behaviour vs. intent
## 4. Assumptions
## 5. Fragility and risk
## 6. State and credentials
## 7. Working / broken / stale
## 8. Findings and questions

---

## Appendix A — raw observations
(Optional. Verbatim output from commands, error messages, any evidence
that supports findings above.)
```

Audits are numbered sequentially (`0001`, `0002`, ...) and named descriptively. They live in `docs/audits/` once that structure exists.

---

## Best-practice notes for AI-assisted audits

When the auditor is Claude Code (or any LLM tool):

1. **The audit prompt must specify "read-only — do not edit, do not commit."** LLMs default to fixing things they see as wrong. The audit must explicitly forbid this.

2. **The auditor must explicitly say when it's guessing.** A finding must be either evidence-based ("script X imports module Y on line Z") or explicitly marked as inference ("appears to assume X — verify").

3. **The auditor must not pad.** AI tools default to verbose output. The audit prompt must demand brevity and concrete evidence, not narrative prose.

4. **The auditor must list what it didn't read.** If the audit skipped a file, it says so. Silent omissions are worse than explicit ones.

5. **The human reviews adversarially.** The reviewer's working assumption is "this audit is wrong somewhere, find where." This is the same posture as reviewing any AI output.

---

## Versioning this protocol

This protocol document is versioned in git. Changes to the protocol go through the same review as code changes — proposed, reviewed, committed. The version at HEAD is the active protocol.

If the protocol changes mid-audit, the audit completes against the protocol that was active when it started. The next audit uses the new protocol.
