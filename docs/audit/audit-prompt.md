# Audit Prompt — System Audit 0001

**This is the prompt to paste into Claude Code (or run as a slash command) to perform the first system audit of `C:\dev\globalkinect\sales`.**

The output of this prompt will be a single markdown document that captures the actual shape of the existing repo. Do not edit anything. Do not commit anything. Only read, classify, observe, and report.

---

## PROMPT BEGINS HERE — paste from this line down into Claude Code

You are performing **System Audit 0001** for the Global Kinect sales repo at `C:\dev\globalkinect\sales`. This is read-only work. Your job is to capture the actual shape of what exists, not to fix anything, not to suggest changes, not to refactor.

## ABSOLUTE RULES

1. **You will not edit any file.** Not even to fix obvious typos, broken imports, or stale documentation. If you find something wrong, you note it; you do not change it.
2. **You will not commit anything.** Not even to track your audit document.
3. **You will not run scripts that have side effects.** API calls, file writes, database changes — all forbidden. `--dry-run` modes and pure read commands are permitted.
4. **You will not invent context.** If you don't know something, write "unknown" or "could not determine." Never guess.
5. **You will explicitly list what you did not read.** Silent omissions are worse than explicit ones.
6. **You will be brief.** Concrete evidence, not narrative prose. If a section is short because there's nothing to say, the section is short.
7. **You will mark inferences explicitly.** A finding is either evidence-based (cite the file and line) or marked `[inferred]`.

## SCOPE

- **In scope:** Everything under `C:\dev\globalkinect\sales`, including all subfolders, all git repos, all uncommitted changes, all config files, all data files.
- **Out of scope:** External services (HubSpot, Instantly, Perplexity, Anthropic, Vibe Prospecting accounts) — those will be audited separately. Mention them only where the local code references them.

## STEPS

### Step 1: Inventory the filesystem
- Run `ls -la` (or PowerShell equivalent) on `C:\dev\globalkinect\sales`.
- For each top-level item, classify: directory / file / git repo.
- For each git repo found, capture: repo path, current branch, last commit hash and date, uncommitted changes (yes/no), untracked files count, remote (if any).
- Produce a complete tree of the folder, depth-limited to 3 levels for readability, but listing all files at any depth in a separate flat list.
- **Explicitly note anything that looks like duplicate content** (e.g., `sales-engine/` and `sales-engine-v2/` may have overlapping files — flag this).

### Step 2: Classify every artefact
For each file in the scope, classify into one of:
- **Code** (.py, .ts, .js, .sh, .ps1, etc.)
- **Prompt** (.md inside a `prompts/` folder, or any file whose content is an LLM prompt)
- **Config** (.env, .env.example, .toml, .yaml, .json that's clearly config)
- **Documentation** (.md README, .md docs)
- **Data** (.csv, .xlsx, .json that's clearly data)
- **Output** (anything in a `leads/`, `outputs/`, `reports/` folder that looks like generated content)
- **Unknown** (everything else — list each one explicitly)

### Step 3: Read every code file and every prompt file
Read each one. For each, capture in 2-4 lines:
- **Path:** `relative/path/from/sales/root.py`
- **Purpose:** what it appears to do (1 sentence)
- **Key dependencies:** which APIs / packages / files it depends on
- **Known assumptions:** anything implicit (e.g., "assumes CSV has column X")
- **Status:** Working / Broken / Stale / Unknown

You may speed-read but every file is opened. If you skip a file, list it in the "Did not read" section with reason.

### Step 4: Identify duplicate or overlapping artefacts
- If two files appear to do the same thing (e.g., two versions of the same script), note both paths and the differences.
- If two prompt files have substantially overlapping content, note both.
- Specifically check: is `sales-engine/` and `sales-engine-v2/` the same code, or different versions? Document the relationship.

### Step 5: Identify state and credentials
- Find every `.env`, `.env.example`, or any config file that holds or describes credentials.
- For each: list what credentials it expects (key names only, never values).
- Check whether any actual secrets appear committed to git history. Use `git log -p` or similar. If any are found: severity-CRITICAL, flag clearly.
- Note where secrets are expected to be stored at runtime.

### Step 6: Map external dependencies
List every external service or API the code talks to. For each:
- Service name (HubSpot, Perplexity, Anthropic, Instantly, Vibe Prospecting, etc.)
- Which file(s) make calls to it
- What it's used for in this codebase
- Whether the integration is one-way (push) or two-way (sync with webhooks/polling)

### Step 7: Identify behavioural gaps
For any script that has been demonstrably run (evidence: output files exist, log files exist), check:
- Does the output match what the code says it should produce?
- Are there any mismatches between intent (per docstrings/comments) and observed output?

For example: if a script says "outputs report.md without `<think>` block" but a sample `report.md` in the leads folder *does* contain a `<think>` block — that's a behavioural gap.

### Step 8: Identify untracked or stale artefacts
- Files that haven't been touched in over 60 days AND are not referenced by any active code path.
- Folders that look like prior experiments (`sales-engine-old/`, `archive/`, etc.).
- Any TODO / FIXME / XXX comments in code, with their location.

### Step 9: Capture findings and open questions
For things you noticed that don't fit the rubric above, write them in a "Findings and questions" section. Examples:
- "Two prompt files exist with conflicting brand guidance — `prompts/email_prompt.md` mentions Insight/Control/Orchestrate; the README explicitly forbids these names. Which is canonical?"
- "The `LEADS_ROOT` config defaults to a Windows path — is this intended, or should it be config-driven?"

End each finding with a question for the human reviewer to answer.

## OUTPUT FORMAT

Write the audit as a single markdown document with this exact structure. Save it to `C:\dev\globalkinect\sales\AUDIT-0001-DRAFT.md` (uppercase, root-level, so it's impossible to miss). It is a draft until the human reviews and accepts it.

```markdown
# Audit 0001 — Sales Repo System Audit

**Date:** <today's date>
**Auditor:** Claude Code (model: <model name from your environment>)
**Reviewer:** <leave blank — Michael will fill in>
**Status:** Draft — pending human review
**Repo path:** C:\dev\globalkinect\sales

---

## 1. Scope and boundaries

<scope as defined above, plus anything you discovered during audit that's worth calling out about scope>

## 2. Inventory

### 2.1 Top-level structure
<tree, depth 3>

### 2.2 Git repositories found
<table: path | branch | last commit | uncommitted | untracked | remote>

### 2.3 Full file listing (flat)
<flat list of all files, with size and last-modified date>

## 3. Artefact classification

### 3.1 Code files
<table or list: path | purpose | dependencies | assumptions | status>

### 3.2 Prompt files
<same format>

### 3.3 Config files
<same format>

### 3.4 Data files
<same format>

### 3.5 Output / generated files
<summary — counts, locations, sampled content quality>

### 3.6 Unknown / unclassified
<explicit list>

## 4. Duplicates and overlaps

<each duplicate cluster with paths, differences, and a recommendation question for the reviewer>

## 5. External dependencies

<table: service | files calling it | purpose | direction>

## 6. State and credentials

### 6.1 Credentials expected at runtime
<list>

### 6.2 Secrets check (git history)
<finding: clean / contaminated, with details if contaminated>

### 6.3 Where credentials are stored
<observation>

## 7. Behaviour vs. intent

<each significant artefact where intent ≠ observed behaviour, with severity>

## 8. Working / broken / stale classification

### 8.1 Working
<list of artefacts believed to be operational>

### 8.2 Broken
<list of artefacts that don't run, run wrong, or produce wrong output>

### 8.3 Stale
<list of candidates for deletion>

## 9. Findings and questions for the reviewer

<numbered list of findings, each with: observation, evidence, severity, question for human>

## 10. Did not read

<explicit list of files skipped, with reason>

---

## Appendix A — raw observations

<verbatim output from commands run, error messages encountered, any evidence supporting findings above>
```

## REMINDERS BEFORE YOU START

- **Read-only.** Do not edit any file. Do not commit. Do not run scripts with side effects.
- **Be brief.** Concrete evidence, not prose. Tables and bullets where they fit.
- **Mark inferences.** `[inferred]` where you're not 100% certain.
- **List what you didn't read.** Section 10 is mandatory.
- **End with questions.** The reviewer needs to know what to challenge you on.

When you have produced the audit document, stop. Do not propose what to build next. Do not refactor anything. Wait for the human to review.

## PROMPT ENDS HERE
