from app.agents.lead_research_agent import LeadResearchAgent
from app.models.lead import Lead
from app.models.lead_intake_record import LeadIntakeRecord


class _FakeNotionService:
    def __init__(self, intake_records=None, intake_configured=True):
        self._intake_records = intake_records or []
        self._intake_configured = intake_configured
        self.processed = []
        self.failed = []

    def is_intake_configured(self) -> bool:
        return self._intake_configured

    def fetch_lead_intake_records(self, limit: int = 20):
        return self._intake_records[:limit]

    def mark_lead_intake_record_processed(self, intake_record, lead):
        self.processed.append((intake_record, lead))
        return {"id": intake_record.page_id}

    def mark_lead_intake_record_failed(self, intake_record, error_message):
        self.failed.append((intake_record, error_message))
        return {"id": intake_record.page_id}


class _FakeAnthropicService:
    def __init__(self, normalized_leads=None, failing_page_ids=None, configured=True):
        self._normalized_leads = normalized_leads or {}
        self._failing_page_ids = set(failing_page_ids or [])
        self._configured = configured
        self.normalize_calls = []
        self.fallback_calls = []

    def is_configured(self) -> bool:
        return self._configured

    def normalize_lead_from_intake(self, intake_record, campaign=None):
        self.normalize_calls.append((intake_record, campaign))
        if intake_record.page_id in self._failing_page_ids:
            raise RuntimeError("Anthropic normalization failed.")
        return self._normalized_leads[intake_record.page_id]

    def build_lead_from_intake_fallback(self, intake_record, campaign=None):
        self.fallback_calls.append((intake_record, campaign))
        return Lead(
            company_name=intake_record.company_name,
            contact_name=intake_record.contact_name or "Unknown Contact",
            contact_role=intake_record.contact_role or "Unknown Role",
            email=intake_record.email,
            linkedin_url=intake_record.linkedin_url,
            company_country=intake_record.company_country,
            target_country=intake_record.target_country,
            lead_type=intake_record.lead_type_hint,
            fit_reason=intake_record.notes or f"Fallback for {campaign}",
        )


def test_generate_mock_leads() -> None:
    agent = LeadResearchAgent(
        notion_service=_FakeNotionService(intake_configured=False),
        anthropic_service=_FakeAnthropicService(configured=False),
    )
    leads = agent.generate_mock_leads("Test campaign")

    assert len(leads) == 3
    assert leads[0].company_name == "Desert Peak Technologies"
    assert leads[1].target_country == "Saudi Arabia"
    assert leads[2].lead_type == "recruitment_partner"


def test_collect_leads_falls_back_to_mock_when_intake_not_configured() -> None:
    agent = LeadResearchAgent(
        notion_service=_FakeNotionService(intake_configured=False),
        anthropic_service=_FakeAnthropicService(configured=False),
    )

    leads = agent.collect_leads("Test campaign")

    assert len(leads) == 3
    assert leads[0].company_name == "Desert Peak Technologies"


def test_collect_leads_uses_notion_intake_and_marks_processed() -> None:
    intake_record = LeadIntakeRecord(
        page_id="page-1",
        company_name="North Star Labs",
        contact_name="Mina Yusuf",
        contact_role="Head of People",
        email="mina@example.com",
        company_country="United Kingdom",
        target_country="Saudi Arabia",
        lead_type_hint="direct_payroll",
        notes="Hiring a first team in Saudi Arabia.",
    )
    normalized_lead = Lead(
        company_name="North Star Labs",
        contact_name="Mina Yusuf",
        contact_role="Head of People",
        email="mina@example.com",
        company_country="United Kingdom",
        target_country="Saudi Arabia",
        lead_type="direct_payroll",
        fit_reason="Hiring a first team in Saudi Arabia with likely payroll complexity.",
    )
    fake_notion = _FakeNotionService(intake_records=[intake_record])
    fake_anthropic = _FakeAnthropicService(normalized_leads={"page-1": normalized_lead})
    agent = LeadResearchAgent(
        notion_service=fake_notion,
        anthropic_service=fake_anthropic,
    )

    leads = agent.collect_leads("Saudi expansion", max_records=5)

    assert leads == [normalized_lead]
    assert fake_anthropic.normalize_calls[0][1] == "Saudi expansion"
    assert fake_notion.processed == [(intake_record, normalized_lead)]
    assert fake_notion.failed == []


def test_collect_leads_uses_fallback_mapping_when_anthropic_fails() -> None:
    intake_record = LeadIntakeRecord(
        page_id="page-2",
        company_name="Atlas Ops",
        contact_name="Rami Haddad",
        contact_role="Founder",
        target_country="United Arab Emirates",
        lead_type_hint="direct_eor",
        notes="Founder-led UAE market entry.",
    )
    fake_notion = _FakeNotionService(intake_records=[intake_record])
    fake_anthropic = _FakeAnthropicService(failing_page_ids={"page-2"})
    agent = LeadResearchAgent(
        notion_service=fake_notion,
        anthropic_service=fake_anthropic,
    )

    leads = agent.collect_leads("UAE expansion", max_records=5)

    assert len(leads) == 1
    assert leads[0].company_name == "Atlas Ops"
    assert leads[0].lead_type == "direct_eor"
    assert fake_anthropic.fallback_calls[0][1] == "UAE expansion"
    assert fake_notion.processed[0][0] == intake_record
    assert fake_notion.failed == []


def test_collect_leads_can_skip_marking_processed_for_shadow_mode() -> None:
    intake_record = LeadIntakeRecord(
        page_id="page-3",
        company_name="North Star Labs",
        contact_name="Mina Yusuf",
        contact_role="Head of People",
        target_country="Saudi Arabia",
        lead_type_hint="direct_payroll",
    )
    normalized_lead = Lead(
        company_name="North Star Labs",
        contact_name="Mina Yusuf",
        contact_role="Head of People",
        target_country="Saudi Arabia",
        lead_type="direct_payroll",
        fit_reason="Strong payroll-led expansion fit.",
    )
    fake_notion = _FakeNotionService(intake_records=[intake_record])
    fake_anthropic = _FakeAnthropicService(normalized_leads={"page-3": normalized_lead})
    agent = LeadResearchAgent(
        notion_service=fake_notion,
        anthropic_service=fake_anthropic,
    )

    leads = agent.collect_leads(
        "Saudi expansion",
        max_records=5,
        mark_processed=False,
    )

    assert leads == [normalized_lead]
    assert fake_notion.processed == []
    assert fake_notion.failed == []


def test_collect_leads_skips_shadow_replay_rows_with_prior_processing_markers() -> None:
    intake_record = LeadIntakeRecord(
        page_id="page-4",
        company_name="Atlas Ops",
        target_country="Saudi Arabia",
        lead_type_hint="direct_eor",
        lead_reference="Atlas Ops|Unknown Contact|Saudi Arabia|direct_eor",
        processed_at="2026-03-24T20:00:00Z",
    )
    fake_notion = _FakeNotionService(intake_records=[intake_record])
    fake_anthropic = _FakeAnthropicService(normalized_leads={})
    agent = LeadResearchAgent(
        notion_service=fake_notion,
        anthropic_service=fake_anthropic,
    )

    leads = agent.collect_leads(
        "Saudi expansion",
        max_records=5,
        mark_processed=False,
    )

    assert leads == []
    assert fake_anthropic.normalize_calls == []
