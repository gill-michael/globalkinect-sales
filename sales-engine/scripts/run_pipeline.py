#!/usr/bin/env python3
"""
Global Kinect — Per-lead research + email generation pipeline.

Reads a ranked leads CSV (from Vibe Prospecting output).
For each lead:
  1. Checks if already processed (skip if so — resumable)
  2. Calls Perplexity sonar-deep-research with the research prompt
  3. Saves report.md
  4. Calls Claude with the report + email-drafting prompt
  5. Saves email.md
  6. Writes metadata.json per lead
  7. Updates the run manifest

Output:
  LEADS_ROOT/
    <company-slug>/
      report.md
      email.md
      metadata.json
    _manifest.json
    _run.log

Usage:
  python run_pipeline.py --csv leads/vibe_combined_top30.csv --limit 5
  python run_pipeline.py --csv leads/vibe_combined_top30.csv --force  # re-run everything
  python run_pipeline.py --csv leads/vibe_combined_top30.csv --only "legend holding"  # single lead
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

# ─────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────
load_dotenv()

PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
LEADS_ROOT = Path(os.getenv("LEADS_ROOT", r"C:\dev\globalkinect\sales\leads"))

PERPLEXITY_MODEL = os.getenv("PERPLEXITY_MODEL", "sonar-deep-research")
PERPLEXITY_URL = "https://api.perplexity.ai/chat/completions"

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-4-7")
CLAUDE_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_VERSION = "2023-06-01"

REQUEST_TIMEOUT_SECONDS = 300  # deep research can take a few minutes
INTER_REQUEST_DELAY_SECONDS = 2.0  # gentle pacing between Perplexity calls
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 15

SCRIPT_DIR = Path(__file__).resolve().parent
PROMPTS_DIR = SCRIPT_DIR.parent / "prompts"
CONFIG_DIR = SCRIPT_DIR.parent / "config"

# ─────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────
@dataclass
class Lead:
    rank: int
    score: int
    source: str
    full_name: str
    role: str
    company: str
    website: str
    professional_email: str
    personal_email: str
    best_email: str
    email_type: str
    linkedin_url: str
    prospect_country: str

    @classmethod
    def from_csv_row(cls, row: dict) -> "Lead":
        return cls(
            rank=int(row.get("Rank", 0) or 0),
            score=int(row.get("Score", 0) or 0),
            source=row.get("Source", "") or row.get("Src", ""),
            full_name=row.get("Full Name", ""),
            role=row.get("Role", ""),
            company=row.get("Company", ""),
            website=row.get("Website", ""),
            professional_email=row.get("Professional Email", ""),
            personal_email=row.get("Personal Email", ""),
            best_email=row.get("Best Email", "") or row.get("Professional Email", "") or row.get("Personal Email", ""),
            email_type=row.get("Email Type", ""),
            linkedin_url=row.get("LinkedIn URL", "") or row.get("LinkedIn", ""),
            prospect_country=row.get("Prospect Country", ""),
        )


def slugify(name: str) -> str:
    """Turn a company name into a safe folder slug."""
    s = (name or "unknown").lower().strip()
    s = re.sub(r"[®™©]", "", s)
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_-]+", "-", s)
    s = s.strip("-")
    return s or "unknown"


def log(message: str, file: Optional[Path] = None):
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    line = f"[{timestamp}] {message}"
    print(line, flush=True)
    if file:
        with open(file, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ─────────────────────────────────────────────────────────────
# Prompt loading
# ─────────────────────────────────────────────────────────────
def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(
            f"Prompt file missing: {path}\n"
            f"Expected directory: {PROMPTS_DIR}"
        )
    return path.read_text(encoding="utf-8")


def fill_research_prompt(template: str, lead: Lead) -> str:
    return (template
        .replace("{{FULL_NAME}}", lead.full_name)
        .replace("{{ROLE}}", lead.role)
        .replace("{{COMPANY}}", lead.company)
        .replace("{{WEBSITE}}", lead.website)
        .replace("{{EMAIL}}", lead.best_email or "(none on file)")
        .replace("{{LINKEDIN}}", lead.linkedin_url)
        .replace("{{PROSPECT_COUNTRY}}", lead.prospect_country))


def fill_email_prompt(template: str, lead: Lead, report: str) -> str:
    return (template
        .replace("{{FULL_NAME}}", lead.full_name)
        .replace("{{ROLE}}", lead.role)
        .replace("{{COMPANY}}", lead.company)
        .replace("{{EMAIL}}", lead.best_email or "")
        .replace("{{REPORT}}", report))


# ─────────────────────────────────────────────────────────────
# API callers
# ─────────────────────────────────────────────────────────────
def call_perplexity(prompt: str, log_file: Path) -> dict:
    """Call Perplexity deep-research API. Returns full response dict."""
    if not PERPLEXITY_API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY is not set in environment")

    headers = {
        "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
        "Content-Type": "application/json",
    }
    body = {
        "model": PERPLEXITY_MODEL,
        "messages": [
            {"role": "system", "content": "You are a senior B2B sales research analyst. Return thorough, accurate, citation-backed research in the exact structure requested."},
            {"role": "user", "content": prompt},
        ],
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = client.post(PERPLEXITY_URL, headers=headers, json=body)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                log(f"  Perplexity rate-limited (attempt {attempt}/{MAX_RETRIES}). Backing off {RETRY_BACKOFF_SECONDS * attempt}s.", log_file)
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            log(f"  Perplexity error {response.status_code}: {response.text[:500]}", log_file)
            response.raise_for_status()
        except httpx.TimeoutException:
            log(f"  Perplexity timeout (attempt {attempt}/{MAX_RETRIES})", log_file)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS)
        except httpx.HTTPError as e:
            log(f"  Perplexity HTTP error: {e}", log_file)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS)

    raise RuntimeError("Perplexity call failed after all retries")


def call_claude(prompt: str, log_file: Path) -> dict:
    """Call Anthropic Claude for email generation."""
    if not ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY is not set in environment")

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": CLAUDE_VERSION,
        "content-type": "application/json",
    }
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": 2000,
        "messages": [{"role": "user", "content": prompt}],
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(CLAUDE_URL, headers=headers, json=body)
            if response.status_code == 200:
                return response.json()
            if response.status_code == 429:
                log(f"  Claude rate-limited (attempt {attempt}/{MAX_RETRIES})", log_file)
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
                continue
            log(f"  Claude error {response.status_code}: {response.text[:500]}", log_file)
            response.raise_for_status()
        except httpx.HTTPError as e:
            log(f"  Claude HTTP error: {e}", log_file)
            if attempt == MAX_RETRIES:
                raise
            time.sleep(RETRY_BACKOFF_SECONDS)

    raise RuntimeError("Claude call failed after all retries")


def extract_perplexity_content(response: dict) -> tuple[str, list]:
    """Extract markdown text + citation list from Perplexity response."""
    choices = response.get("choices", [])
    content = choices[0]["message"]["content"] if choices else ""
    citations = response.get("citations", [])
    return content, citations


def extract_claude_content(response: dict) -> str:
    blocks = response.get("content", [])
    return "\n".join(b.get("text", "") for b in blocks if b.get("type") == "text")


def format_report(content: str, citations: list, lead: Lead) -> str:
    """Build the final report.md — content + citation appendix + metadata header."""
    header = f"""# Research Report — {lead.full_name}

**Company:** {lead.company}
**Role:** {lead.role}
**Email:** {lead.best_email or "(none on file)"}
**LinkedIn:** {lead.linkedin_url}
**Website:** {lead.website}
**Generated:** {datetime.now(timezone.utc).isoformat(timespec="seconds")}
**Model:** {PERPLEXITY_MODEL}

---

"""
    citation_block = ""
    if citations:
        citation_block = "\n\n---\n\n## Citations\n\n"
        for i, url in enumerate(citations, 1):
            citation_block += f"{i}. {url}\n"
    return header + content + citation_block


def format_email(content: str, lead: Lead) -> str:
    header = f"""# Outreach Email — {lead.full_name}

**To:** {lead.best_email or "(no email on file — send via LinkedIn)"}
**From:** [YOUR NAME / sales@globalkinect.co.uk]
**Re:** {lead.company}
**Generated:** {datetime.now(timezone.utc).isoformat(timespec="seconds")}

---

"""
    return header + content


# ─────────────────────────────────────────────────────────────
# Core processing
# ─────────────────────────────────────────────────────────────
def process_lead(lead: Lead, research_prompt_template: str, email_prompt_template: str,
                 leads_root: Path, log_file: Path, force: bool = False) -> dict:
    slug = slugify(lead.company)
    lead_dir = leads_root / slug
    lead_dir.mkdir(parents=True, exist_ok=True)

    report_path = lead_dir / "report.md"
    email_path = lead_dir / "email.md"
    meta_path = lead_dir / "metadata.json"

    status = {"lead": lead.full_name, "company": lead.company, "slug": slug,
              "report_generated": False, "email_generated": False,
              "skipped_research": False, "skipped_email": False, "errors": []}

    # Step 1: Research report
    if report_path.exists() and not force:
        log(f"  ⏭  report.md exists — skipping research step", log_file)
        status["skipped_research"] = True
        report_content = report_path.read_text(encoding="utf-8")
    else:
        log(f"  🔎 Researching via Perplexity ({PERPLEXITY_MODEL})...", log_file)
        try:
            research_prompt = fill_research_prompt(research_prompt_template, lead)
            response = call_perplexity(research_prompt, log_file)
            content, citations = extract_perplexity_content(response)
            report_content = format_report(content, citations, lead)
            report_path.write_text(report_content, encoding="utf-8")
            status["report_generated"] = True
            status["perplexity_usage"] = response.get("usage", {})
            log(f"  ✓ Saved report.md ({len(report_content)} chars, {len(citations)} citations)", log_file)
        except Exception as e:
            error_msg = f"Research failed: {e}"
            log(f"  ✗ {error_msg}", log_file)
            status["errors"].append(error_msg)
            return status

    # Step 2: Email generation
    if email_path.exists() and not force:
        log(f"  ⏭  email.md exists — skipping email step", log_file)
        status["skipped_email"] = True
    else:
        log(f"  ✍  Drafting email via Claude ({CLAUDE_MODEL})...", log_file)
        try:
            email_prompt = fill_email_prompt(email_prompt_template, lead, report_content)
            response = call_claude(email_prompt, log_file)
            email_content = extract_claude_content(response)
            formatted = format_email(email_content, lead)
            email_path.write_text(formatted, encoding="utf-8")
            status["email_generated"] = True
            status["claude_usage"] = response.get("usage", {})
            log(f"  ✓ Saved email.md ({len(formatted)} chars)", log_file)
        except Exception as e:
            error_msg = f"Email generation failed: {e}"
            log(f"  ✗ {error_msg}", log_file)
            status["errors"].append(error_msg)

    # Step 3: Metadata
    metadata = {
        "lead": asdict(lead),
        "slug": slug,
        "processed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": status,
    }
    meta_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return status


def update_manifest(leads_root: Path, results: list[dict]):
    """Update the run manifest with results from this run."""
    manifest_path = leads_root / "_manifest.json"
    manifest = {"runs": []}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    manifest["runs"].append({
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "leads_processed": len(results),
        "reports_generated": sum(1 for r in results if r["report_generated"]),
        "emails_generated": sum(1 for r in results if r["email_generated"]),
        "errors": sum(len(r["errors"]) for r in results),
        "results": results,
    })
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Global Kinect per-lead research + email pipeline")
    parser.add_argument("--csv", required=True, help="Path to the ranked leads CSV")
    parser.add_argument("--leads-root", default=str(LEADS_ROOT),
                        help=f"Output folder root (default: {LEADS_ROOT})")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N leads")
    parser.add_argument("--only", default=None, help="Only process leads whose company name contains this substring (case-insensitive)")
    parser.add_argument("--force", action="store_true", help="Re-run even if outputs already exist")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be done, don't call APIs")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"ERROR: CSV not found: {csv_path}", file=sys.stderr)
        sys.exit(1)

    leads_root = Path(args.leads_root)
    leads_root.mkdir(parents=True, exist_ok=True)
    log_file = leads_root / "_run.log"

    log(f"=" * 70, log_file)
    log(f"Global Kinect lead pipeline starting", log_file)
    log(f"  CSV: {csv_path}", log_file)
    log(f"  Output root: {leads_root}", log_file)
    log(f"  Dry run: {args.dry_run}", log_file)
    log(f"=" * 70, log_file)

    # Load prompts
    try:
        research_prompt_template = load_prompt("research_prompt.md")
        email_prompt_template = load_prompt("email_prompt.md")
    except FileNotFoundError as e:
        log(f"ERROR: {e}", log_file)
        sys.exit(1)

    # Load leads
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        leads = [Lead.from_csv_row(row) for row in reader]

    # Apply filters
    if args.only:
        leads = [l for l in leads if args.only.lower() in l.company.lower()]
    if args.limit:
        leads = leads[:args.limit]

    log(f"Processing {len(leads)} leads", log_file)
    if not leads:
        log("No leads to process.", log_file)
        return

    if args.dry_run:
        for lead in leads:
            log(f"  [DRY RUN] Would process: {lead.full_name} / {lead.company} → {slugify(lead.company)}/", log_file)
        return

    # Check API keys early
    if not PERPLEXITY_API_KEY:
        log("ERROR: PERPLEXITY_API_KEY is not set. Copy .env.example to .env and fill in your keys.", log_file)
        sys.exit(1)
    if not ANTHROPIC_API_KEY:
        log("ERROR: ANTHROPIC_API_KEY is not set.", log_file)
        sys.exit(1)

    # Process each lead
    results = []
    for i, lead in enumerate(leads, 1):
        log(f"\n[{i}/{len(leads)}] {lead.full_name} — {lead.role} @ {lead.company}", log_file)
        try:
            status = process_lead(lead, research_prompt_template, email_prompt_template,
                                   leads_root, log_file, force=args.force)
            results.append(status)
        except KeyboardInterrupt:
            log("Interrupted by user.", log_file)
            break
        except Exception as e:
            log(f"  ✗ Unhandled error: {e}", log_file)
            results.append({"lead": lead.full_name, "company": lead.company,
                            "errors": [str(e)], "report_generated": False, "email_generated": False})

        # Gentle pacing between leads
        if i < len(leads):
            time.sleep(INTER_REQUEST_DELAY_SECONDS)

    update_manifest(leads_root, results)

    # Summary
    log(f"\n{'=' * 70}", log_file)
    log(f"Summary:", log_file)
    log(f"  Processed: {len(results)}", log_file)
    log(f"  Reports generated: {sum(1 for r in results if r['report_generated'])}", log_file)
    log(f"  Emails generated: {sum(1 for r in results if r['email_generated'])}", log_file)
    log(f"  Errors: {sum(len(r['errors']) for r in results)}", log_file)
    log(f"  Output: {leads_root}", log_file)


if __name__ == "__main__":
    main()
