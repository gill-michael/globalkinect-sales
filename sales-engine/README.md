# Global Kinect Sales Engine — Per-Lead Research + Email Pipeline

Turns a ranked leads CSV into a folder structure of per-lead research reports and cold outreach emails. Runs on your desktop. No browser automation, no manual copy-paste.

## What it does

For each lead in your CSV:

1. Calls **Perplexity sonar-deep-research** with a structured research prompt (company snapshot, payroll footprint, pain signals, decision-maker context, buying unit, red flags)
2. Saves the report to `LEADS_ROOT/<company-slug>/report.md`
3. Calls **Claude Opus 4.7** with the research report + an email-drafting prompt
4. Saves a ready-to-send cold email to `LEADS_ROOT/<company-slug>/email.md`
5. Writes `metadata.json` per lead with status, usage, any errors
6. Updates a `_manifest.json` at the leads root

**Resumable.** If a lead's `report.md` already exists, the research step is skipped. Same for `email.md`. Use `--force` to override.

## First-time setup

Assumes you have Python 3.10+ installed.

```powershell
# From the sales-engine folder
cd C:\dev\globalkinect\sales\sales-engine

# Create a virtualenv and install dependencies
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Copy env template and fill in your API keys
Copy-Item config\.env.example .env
notepad .env
```

Keys needed in `.env`:
- `PERPLEXITY_API_KEY` — from https://www.perplexity.ai/settings/api (Pro or Max subscribers get $5 monthly credits free)
- `ANTHROPIC_API_KEY` — from https://console.anthropic.com/settings/keys

## Running

```powershell
# Dry run — prints what would happen, makes no API calls
python scripts\run_pipeline.py --csv C:\dev\globalkinect\sales\csv\vibe_combined_top30.csv --dry-run

# Process first 3 leads only (cheap test)
python scripts\run_pipeline.py --csv C:\dev\globalkinect\sales\csv\vibe_combined_top30.csv --limit 3

# Process just one specific company
python scripts\run_pipeline.py --csv ..\csv\vibe_combined_top30.csv --only "legend holding"

# Process everything
python scripts\run_pipeline.py --csv ..\csv\vibe_combined_top30.csv

# Re-run everything from scratch (overwrites existing reports/emails)
python scripts\run_pipeline.py --csv ..\csv\vibe_combined_top30.csv --force
```

## Output structure

```
C:\dev\globalkinect\sales\leads\
├── _manifest.json                    # Run history, success/fail counts, token usage
├── _run.log                          # Timestamped log of all runs
├── legend-holding-group\
│   ├── report.md                     # Perplexity research output
│   ├── email.md                      # Claude-drafted cold email
│   └── metadata.json                 # Lead data + run status
├── eatx\
│   ├── report.md
│   ├── email.md
│   └── metadata.json
└── ...
```

## Expected costs per run of 30 leads

- **Perplexity sonar-deep-research:** roughly $0.10-$0.15 per lead = **$3-$5 total**
- **Claude Opus 4.7 email:** roughly $0.02-$0.05 per lead = **$0.60-$1.50 total**
- **Wall-clock time:** 15-30 minutes depending on Perplexity queue

## Editing the prompts

The prompts are externalised — edit them without touching code:

- `prompts/research_prompt.md` — what Perplexity researches and returns
- `prompts/email_prompt.md` — how Claude turns the report into an email (tone, structure, banned words)

Anything in `{{DOUBLE_BRACES}}` is a variable filled in at runtime. Keep the variable names as they are.

## CSV input format

The pipeline reads these columns (case-sensitive):

| Column | Required | Notes |
|---|---|---|
| Rank | Yes | Integer |
| Score | Yes | Integer |
| Source | No | R1 / R2 tag |
| Full Name | Yes | |
| Role | Yes | |
| Company | Yes | Used to generate folder slug |
| Website | Yes | |
| Professional Email | No | |
| Personal Email | No | |
| Best Email | No | Used in prompts if present |
| Email Type | No | |
| LinkedIn URL | Yes | Must be full URL |
| Prospect Country | No | |

If you use a different CSV format, the `Lead.from_csv_row` function in `run_pipeline.py` is where to adjust it.

## When things go wrong

**"PERPLEXITY_API_KEY is not set"** — you haven't copied `config/.env.example` to `.env` in the sales-engine root, or the file isn't being loaded. Confirm `.env` is in the same folder you're running the script from.

**"Perplexity error 429"** — rate-limited. The script retries automatically with exponential backoff. If it still fails, reduce pace by setting `INTER_REQUEST_DELAY_SECONDS` higher in the script.

**"Report looks generic / wrong"** — Perplexity couldn't find much on the company. Check the `citations` section at the bottom of the report — if few/weak, the company may be too small or too local for Perplexity's coverage. Flag as low-confidence and skip.

**"Email mentions Entomo / says GlobalKinect as one word"** — escape these via the email prompt (already in place). If it still happens, add more explicit exclusions in `prompts/email_prompt.md`.

## What's NOT in this pipeline (intentional scope)

- **Sending the emails.** The rep reviews and sends manually from their own mail client — this protects deliverability and lets them edit.
- **Notion sync.** Separate script needed to push the 30 folders into Notion Opportunity records. Next to build.
- **CRM enrichment.** You've got that at the Vibe Prospecting layer, upstream.

## Next iterations

- `push_to_notion.py` — create Opportunity records from the folders, attach the report as a child page
- `sync_status.py` — pull sent/replied/meeting-booked status from email provider back into metadata.json
- `extend_to_gcc.py` — run the Vibe Prospecting sweep + this pipeline for Kuwait, Bahrain, Qatar, Oman, Egypt
