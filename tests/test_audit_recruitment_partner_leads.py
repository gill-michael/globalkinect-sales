"""Tests for scripts/audit_recruitment_partner_leads.py.

Unit-tests the filter and tally logic against a fake NotionService
with five fixture records:
- 3 active recruitment_partner pipeline rows (different statuses)
- 1 closed recruitment_partner pipeline row
- 1 direct_eor pipeline row that should NOT match
Plus a matching intake record so merge logic gets exercised.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.models.lead_intake_record import LeadIntakeRecord
from scripts.audit_recruitment_partner_leads import (
    RECRUITMENT_PARTNER,
    collect_recruitment_partner_records,
    render_markdown,
)


def _pipeline_record(
    *,
    company: str,
    contact: str,
    lead_type: str,
    outreach_status: str,
    priority: str = "medium",
    page_id: str | None = None,
) -> dict[str, Any]:
    """Build a Notion-shaped Pipeline record dict matching what
    `NotionService.list_pipeline_records` returns."""
    lead_reference = f"{company}|{contact}|United Arab Emirates|{lead_type}"
    pid = page_id or f"pipeline-{company.lower().replace(' ', '-')}"
    return {
        "page_id": pid,
        "page_url": f"https://notion.so/{pid.replace('-', '')}",
        "last_edited_time": "2026-04-15T09:00:00Z",
        "lead_reference": lead_reference,
        "lead_type": lead_type,
        "company_name": company,
        "contact_name": contact,
        "stage": "contacted",
        "outreach_status": outreach_status,
        "next_action": "review_and_send_message",
        "priority": priority,
        "sales_motion": "recruitment_partner" if lead_type == RECRUITMENT_PARTNER else "direct_client",
        "primary_module": "EOR",
        "bundle_label": "EOR + Payroll",
        "last_updated": "2026-04-15",
    }


class FakeNotionService:
    def __init__(
        self,
        pipeline_records: list[dict[str, Any]],
        intake_records: list[LeadIntakeRecord],
    ) -> None:
        self._pipeline_records = pipeline_records
        self._intake_records = intake_records

    def is_configured(self) -> bool:
        return True

    def list_pipeline_records(self, limit: int = 200) -> list[dict[str, Any]]:
        return list(self._pipeline_records[:limit])

    def list_lead_intake_records(self, limit: int = 100) -> list[LeadIntakeRecord]:
        return list(self._intake_records[:limit])


@pytest.fixture
def fixture_records():
    """3 active + 1 closed recruitment_partner + 1 direct_eor pipeline
    row, plus an intake row that matches one of the active partner rows."""
    pipeline = [
        _pipeline_record(
            company="Nile Talent",
            contact="Layla Fawzi",
            lead_type=RECRUITMENT_PARTNER,
            outreach_status="ready_to_send",
            priority="medium",
        ),
        _pipeline_record(
            company="Cairo Recruiters",
            contact="Omar Said",
            lead_type=RECRUITMENT_PARTNER,
            outreach_status="approved",
            priority="high",
        ),
        _pipeline_record(
            company="Riyadh Staffing",
            contact="Sara Khan",
            lead_type=RECRUITMENT_PARTNER,
            outreach_status="replied",
            priority="high",
        ),
        _pipeline_record(
            company="Dubai Closed Co",
            contact="Hassan Ali",
            lead_type=RECRUITMENT_PARTNER,
            outreach_status="closed",
            priority="low",
        ),
        _pipeline_record(
            company="Acme Corp",
            contact="John Doe",
            lead_type="direct_eor",
            outreach_status="ready_to_send",
            priority="high",
        ),
    ]
    intake = [
        # Matches the first pipeline record by lead_reference
        LeadIntakeRecord(
            page_id="intake-nile-talent",
            company_name="Nile Talent",
            contact_name="Layla Fawzi",
            contact_role="Managing Director",
            target_country="United Arab Emirates",
            lead_type_hint=RECRUITMENT_PARTNER,
            status="ingested",
            lead_reference=(
                "Nile Talent|Layla Fawzi|United Arab Emirates|recruitment_partner"
            ),
            processed_at="2026-04-12T10:00:00Z",
        ),
        # An intake-only recruitment_partner row not yet in pipeline
        LeadIntakeRecord(
            page_id="intake-orphan",
            company_name="Orphan Partners",
            contact_name="Mina Yusuf",
            target_country="Saudi Arabia",
            lead_type_hint=RECRUITMENT_PARTNER,
            status="ready",
            lead_reference=None,
        ),
        # A direct_eor intake — should NOT match the audit
        LeadIntakeRecord(
            page_id="intake-direct",
            company_name="Direct EOR Co",
            contact_name="Maria Santos",
            target_country="United Arab Emirates",
            lead_type_hint="direct_eor",
            status="ready",
        ),
    ]
    return pipeline, intake


def test_collect_filters_to_recruitment_partner_only(fixture_records) -> None:
    pipeline, intake = fixture_records
    fake = FakeNotionService(pipeline, intake)
    audit = collect_recruitment_partner_records(fake)

    # 4 pipeline rows match (3 active + 1 closed). 5th was direct_eor.
    assert len(audit["pipeline_matches"]) == 4
    assert all(
        record["lead_type"] == RECRUITMENT_PARTNER
        for record in audit["pipeline_matches"]
    )

    # 2 intake rows match. 3rd was direct_eor.
    assert len(audit["intake_matches"]) == 2
    assert all(
        record.lead_type_hint == RECRUITMENT_PARTNER
        for record in audit["intake_matches"]
    )


def test_collect_merges_pipeline_and_intake_by_lead_reference(fixture_records) -> None:
    pipeline, intake = fixture_records
    fake = FakeNotionService(pipeline, intake)
    audit = collect_recruitment_partner_records(fake)

    # 4 pipeline-recruitment rows + 1 intake-only orphan = 5 distinct keys
    assert audit["total"] == 5

    nile_key = "Nile Talent|Layla Fawzi|United Arab Emirates|recruitment_partner"
    nile_entry = audit["merged"][nile_key]
    assert nile_entry["pipeline"] is not None
    assert nile_entry["intake"] is not None
    assert nile_entry["intake"].company_name == "Nile Talent"


def test_collect_tallies_by_outreach_status(fixture_records) -> None:
    pipeline, intake = fixture_records
    fake = FakeNotionService(pipeline, intake)
    audit = collect_recruitment_partner_records(fake)

    # 3 distinct active statuses + 1 closed + 1 intake-only "unknown"
    by_status = audit["by_outreach_status"]
    assert by_status["ready_to_send"] == 1
    assert by_status["approved"] == 1
    assert by_status["replied"] == 1
    assert by_status["closed"] == 1
    assert by_status["unknown"] == 1  # intake-only row, no pipeline status
    assert audit["with_reply"] == 1   # only the "replied" pipeline row


def test_render_markdown_lists_each_record_and_summary(fixture_records) -> None:
    pipeline, intake = fixture_records
    fake = FakeNotionService(pipeline, intake)
    audit = collect_recruitment_partner_records(fake)
    markdown = render_markdown(audit, generated_at="2026-04-28T09:00:00Z")

    # Header + summary
    assert "# Recruitment-partner audit" in markdown
    assert "Total recruitment_partner leads: **5**" in markdown
    assert "With reply (outreach_status='replied'): **1**" in markdown

    # Each company appears in the rendered Records section
    for company in (
        "Nile Talent", "Cairo Recruiters", "Riyadh Staffing",
        "Dubai Closed Co", "Orphan Partners",
    ):
        assert company in markdown, f"missing {company} from markdown"

    # The non-matching company must NOT appear (direct_eor was filtered out)
    assert "Acme Corp" not in markdown
    assert "Direct EOR Co" not in markdown


def test_render_markdown_handles_empty_audit() -> None:
    fake = FakeNotionService([], [])
    audit = collect_recruitment_partner_records(fake)
    markdown = render_markdown(audit, generated_at="2026-04-28T09:00:00Z")

    assert "Total recruitment_partner leads: **0**" in markdown
    assert "_No recruitment_partner leads found in either database._" in markdown
