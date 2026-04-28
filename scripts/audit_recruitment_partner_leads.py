"""Recruitment-partner audit — read-only.

Surfaces every recruitment_partner lead currently in Notion (Pipeline
DB and Lead Intake DB) so an operator can decide what to do with each
before the next monthly run. The channel is formally discontinued
(see docs/RECRUITMENT_PARTNER_DISCONTINUATION.md); the lead-type score
dropped from 3 to 0, which means active recruitment_partner leads
will silently de-prioritise on the next live run.

What this script does:
- Reads Notion Pipeline + Lead Intake DBs via the existing NotionService.
- Filters each side to records where lead_type == "recruitment_partner".
- Merges by lead_reference where both sides match.
- Prints to stdout (markdown) and dumps the same content to
  docs/RECRUITMENT_PARTNER_AUDIT_<UTC-timestamp>.md for the permanent
  record.

What this script does NOT do:
- No Notion writes. No Supabase writes. No outreach generation.
- No Explorium calls. No credit cost.

Usage:
    python scripts/audit_recruitment_partner_leads.py
    python scripts/audit_recruitment_partner_leads.py --dry-run

The --dry-run flag is informational only — there's nothing to write
in either mode. Default is dry-run-ON to make the read-only intent
explicit for operators reading the script later.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.notion_service import NotionService  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


RECRUITMENT_PARTNER = "recruitment_partner"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="audit-recruitment-partner-leads",
        description="Read-only audit of recruitment_partner leads in Notion.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="(Default ON) Document the read-only intent. The script never "
             "writes regardless of this flag.",
    )
    return parser.parse_args()


def collect_recruitment_partner_records(
    notion_service: NotionService,
) -> dict[str, Any]:
    """Pull both DBs and filter to recruitment_partner. Returns a dict
    with `pipeline`, `intake`, `merged`, and tally fields."""
    pipeline_records = notion_service.list_pipeline_records(limit=500)
    intake_records = notion_service.list_lead_intake_records(limit=500)

    pipeline_matches = [
        record for record in pipeline_records
        if (record.get("lead_type") or "").lower() == RECRUITMENT_PARTNER
    ]
    intake_matches = [
        record for record in intake_records
        if (record.lead_type_hint or "").lower() == RECRUITMENT_PARTNER
    ]

    by_lead_reference: dict[str, dict[str, Any]] = {}
    for record in pipeline_matches:
        lead_reference = record.get("lead_reference") or record.get("page_id")
        by_lead_reference[lead_reference] = {"pipeline": record, "intake": None}
    for record in intake_matches:
        key = record.lead_reference or f"intake:{record.page_id}"
        existing = by_lead_reference.get(key)
        if existing:
            existing["intake"] = record
        else:
            by_lead_reference[key] = {"pipeline": None, "intake": record}

    by_outreach_status: dict[str, int] = {}
    with_reply = 0
    for entry in by_lead_reference.values():
        pipeline = entry["pipeline"] or {}
        outreach_status = (pipeline.get("outreach_status") or "unknown").lower()
        by_outreach_status[outreach_status] = (
            by_outreach_status.get(outreach_status, 0) + 1
        )
        if outreach_status == "replied":
            with_reply += 1

    return {
        "pipeline_matches": pipeline_matches,
        "intake_matches": intake_matches,
        "merged": by_lead_reference,
        "total": len(by_lead_reference),
        "by_outreach_status": by_outreach_status,
        "with_reply": with_reply,
    }


def render_markdown(audit: dict[str, Any], generated_at: str) -> str:
    """Format the audit as markdown. Used for both stdout and file."""
    lines: list[str] = [
        "# Recruitment-partner audit",
        "",
        f"**Generated (UTC):** {generated_at}",
        "**Source:** Notion Pipeline DB + Lead Intake DB",
        "**Channel status:** discontinued — see "
        "`docs/RECRUITMENT_PARTNER_DISCONTINUATION.md`",
        "",
        "## Summary",
        "",
        f"- Total recruitment_partner leads: **{audit['total']}**",
        f"- With reply (outreach_status='replied'): **{audit['with_reply']}**",
    ]
    if audit["by_outreach_status"]:
        lines.append("")
        lines.append("### By outreach_status")
        lines.append("")
        for status, count in sorted(audit["by_outreach_status"].items()):
            lines.append(f"- `{status}`: {count}")
    lines.append("")
    lines.append(
        "Pipeline matches: "
        f"{len(audit['pipeline_matches'])}; "
        f"Intake matches: {len(audit['intake_matches'])}."
    )

    if not audit["merged"]:
        lines.extend([
            "",
            "## Records",
            "",
            "_No recruitment_partner leads found in either database._",
        ])
        return "\n".join(lines) + "\n"

    lines.extend(["", "## Records", ""])
    sorted_keys = sorted(audit["merged"].keys())
    for key in sorted_keys:
        entry = audit["merged"][key]
        pipeline = entry.get("pipeline") or {}
        intake = entry.get("intake")
        company = (
            pipeline.get("company_name")
            or (intake.company_name if intake else None)
            or "(unknown company)"
        )
        contact = (
            pipeline.get("contact_name")
            or (intake.contact_name if intake else None)
            or "(unknown contact)"
        )
        page_url = pipeline.get("page_url") or (
            f"https://notion.so/{intake.page_id.replace('-', '')}"
            if intake else "(no URL)"
        )
        outreach_status = pipeline.get("outreach_status") or "(no pipeline row)"
        priority = pipeline.get("priority") or "(no pipeline row)"
        next_action = pipeline.get("next_action") or "(no pipeline row)"
        last_updated = pipeline.get("last_updated") or pipeline.get(
            "last_edited_time"
        ) or "(unknown)"

        lines.extend([
            f"### {company} — {contact}",
            "",
            f"- **Notion:** [{page_url}]({page_url})",
            f"- **Lead reference:** `{key}`",
            f"- **Outreach status:** `{outreach_status}`",
            f"- **Priority:** `{priority}`",
            f"- **Next action:** {next_action}",
            f"- **Last updated:** {last_updated}",
        ])
        if intake is not None:
            lines.extend([
                f"- **Intake status:** `{intake.status or 'unknown'}`",
                f"- **Intake processed_at:** "
                f"{intake.processed_at or '(not processed)'}",
            ])
        lines.append("")

    return "\n".join(lines) + "\n"


def write_audit_doc(markdown: str, generated_at: str) -> Path:
    safe_timestamp = generated_at.replace(":", "").replace("-", "").replace("T", "_")
    target = REPO_ROOT / "docs" / f"RECRUITMENT_PARTNER_AUDIT_{safe_timestamp}.md"
    target.write_text(markdown, encoding="utf-8")
    return target


def main() -> int:
    args = parse_args()
    notion_service = NotionService()
    if not notion_service.is_configured():
        print(
            "Notion is not configured. Set NOTION_API_KEY and the relevant "
            "DB IDs in .env before running the audit."
        )
        return 1

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.info("Recruitment-partner audit starting (UTC %s).", generated_at)

    audit = collect_recruitment_partner_records(notion_service)
    markdown = render_markdown(audit, generated_at=generated_at)

    print(markdown)
    target = write_audit_doc(markdown, generated_at=generated_at)
    print(f"\nAudit written to: {target}")

    if args.dry_run:
        logger.info("Dry-run flag is set (read-only by design).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
