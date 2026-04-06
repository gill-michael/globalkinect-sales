from app.agents.lead_feedback_agent import LeadFeedbackIndex
from app.agents.lead_feedback_agent import LeadFeedbackIndex
from app.agents.lead_discovery_agent import LeadDiscoveryAgent
from app.models.lead_feedback_signal import LeadFeedbackSignal
from app.models.lead_feedback_signal import LeadFeedbackSignal
from app.models.discovery_qualification import DiscoveryQualification
from app.models.lead import Lead
from app.models.lead_discovery_record import LeadDiscoveryRecord


class _FakeNotionService:
    def __init__(self, discovery_records=None, discovery_configured=True, intake_configured=True):
        self._discovery_records = discovery_records or []
        self._discovery_configured = discovery_configured
        self._intake_configured = intake_configured
        self.promoted = []
        self.processed = []
        self.failed = []

    def is_discovery_configured(self) -> bool:
        return self._discovery_configured

    def is_intake_configured(self) -> bool:
        return self._intake_configured

    def fetch_lead_discovery_records(self, limit: int = 20):
        return self._discovery_records[:limit]

    def upsert_intake_page_from_discovery(self, lead, discovery_record, qualification):
        self.promoted.append((lead, discovery_record, qualification))
        return {"id": f"intake-{discovery_record.page_id}"}

    def mark_lead_discovery_record_processed(self, discovery_record, qualification):
        self.processed.append((discovery_record, qualification))
        return {"id": discovery_record.page_id}

    def mark_lead_discovery_record_failed(self, discovery_record, error_message):
        self.failed.append((discovery_record, error_message))
        return {"id": discovery_record.page_id}


class _FakeAnthropicService:
    def __init__(self, qualifications=None, failing_page_ids=None, configured=True):
        self._qualifications = qualifications or {}
        self._failing_page_ids = set(failing_page_ids or [])
        self._configured = configured
        self.qualify_calls = []
        self.fallback_calls = []

    def is_configured(self) -> bool:
        return self._configured

    def qualify_discovery_record(self, discovery_record, campaign=None):
        self.qualify_calls.append((discovery_record, campaign))
        if discovery_record.page_id in self._failing_page_ids:
            raise RuntimeError("Anthropic qualification failed.")
        return self._qualifications[discovery_record.page_id]

    def build_discovery_qualification_fallback(self, discovery_record, campaign=None):
        self.fallback_calls.append((discovery_record, campaign))
        return DiscoveryQualification(
            lead=Lead(
                company_name=discovery_record.company_name,
                contact_name=discovery_record.contact_name or "Unknown Contact",
                contact_role=discovery_record.contact_role or "Unknown Role",
                target_country=discovery_record.target_country_hint or "Saudi Arabia",
                lead_type="direct_payroll",
                fit_reason=discovery_record.evidence or "Fallback qualification",
            ),
            evidence_summary=discovery_record.evidence or "Fallback qualification",
            confidence_score=7,
            decision="promote",
            qualification_notes="Fallback path",
        )


def _qualification(company_name: str, decision: str) -> DiscoveryQualification:
    return DiscoveryQualification(
        lead=Lead(
            company_name=company_name,
            contact_name="Nadia Saleh",
            contact_role="People Director",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            fit_reason="Evidence supports payroll-led GCC expansion.",
        ),
        evidence_summary=f"{company_name} shows GCC expansion evidence.",
        confidence_score=8,
        decision=decision,
    )


def test_promote_discovery_records_routes_decisions_correctly() -> None:
    discovery_records = [
        LeadDiscoveryRecord(page_id="page-promote", company_name="North Star Health"),
        LeadDiscoveryRecord(page_id="page-review", company_name="Blue Dune Tech"),
        LeadDiscoveryRecord(page_id="page-reject", company_name="Generic Vendor"),
    ]
    fake_notion = _FakeNotionService(discovery_records=discovery_records)
    fake_anthropic = _FakeAnthropicService(
        qualifications={
            "page-promote": _qualification("North Star Health", "promote"),
            "page-review": _qualification("Blue Dune Tech", "review"),
            "page-reject": _qualification("Generic Vendor", "reject"),
        }
    )
    agent = LeadDiscoveryAgent(
        notion_service=fake_notion,
        anthropic_service=fake_anthropic,
    )

    result = agent.promote_discovery_records("Saudi payroll campaign", max_records=10)

    assert result.fetched_count == 3
    assert result.promoted_count == 1
    assert result.review_count == 1
    assert result.rejected_count == 1
    assert result.failed_count == 0
    assert len(fake_notion.promoted) == 1
    assert len(fake_notion.processed) == 3
    assert fake_notion.failed == []


def test_promote_discovery_records_uses_fallback_when_anthropic_fails() -> None:
    discovery_record = LeadDiscoveryRecord(
        page_id="page-fallback",
        company_name="Atlas Ops",
        contact_name="Mina Yusuf",
        contact_role="Head of People",
        target_country_hint="Saudi Arabia",
        evidence="Hiring a payroll lead in Riyadh.",
    )
    fake_notion = _FakeNotionService(discovery_records=[discovery_record])
    fake_anthropic = _FakeAnthropicService(
        qualifications={},
        failing_page_ids={"page-fallback"},
    )
    agent = LeadDiscoveryAgent(
        notion_service=fake_notion,
        anthropic_service=fake_anthropic,
    )

    result = agent.promote_discovery_records("Saudi payroll campaign", max_records=10)

    assert result.promoted_count == 1
    assert result.failed_count == 0
    assert len(fake_anthropic.fallback_calls) == 1
    assert len(fake_notion.promoted) == 1


def test_promote_discovery_records_downgrades_duplicate_activity_to_review() -> None:
    discovery_record = LeadDiscoveryRecord(
        page_id="page-duplicate",
        company_name="Guidepoint",
        target_country_hint="United Arab Emirates",
        evidence="Hiring payroll operations support in Dubai.",
    )
    fake_notion = _FakeNotionService(discovery_records=[discovery_record])
    fake_anthropic = _FakeAnthropicService(
        qualifications={
            "page-duplicate": DiscoveryQualification(
                lead=Lead(
                    company_name="Guidepoint",
                    contact_name="Unknown Contact",
                    contact_role="Unknown Role",
                    target_country="United Arab Emirates",
                    lead_type="direct_payroll",
                    fit_reason="Evidence supports UAE payroll expansion.",
                ),
                evidence_summary="Guidepoint shows UAE payroll expansion evidence.",
                confidence_score=8,
                decision="promote",
            )
        }
    )
    agent = LeadDiscoveryAgent(
        notion_service=fake_notion,
        anthropic_service=fake_anthropic,
    )
    feedback_index = LeadFeedbackIndex(
        by_reference={
            "guidepoint|unknown contact|the uae|direct_payroll": LeadFeedbackSignal(
                lead_reference="Guidepoint|Unknown Contact|the UAE|direct_payroll",
                company_name="Guidepoint",
                queue_status="Approved",
            )
        }
    )

    result = agent.promote_discovery_records(
        "UAE payroll campaign",
        max_records=10,
        feedback_index=feedback_index,
    )

    assert result.promoted_count == 0
    assert result.review_count == 1
    assert len(fake_notion.promoted) == 0
    assert "Existing sales activity detected" in fake_notion.processed[0][1].qualification_notes


def test_promote_discovery_records_blocks_unknown_buyer_auto_promotion() -> None:
    discovery_record = LeadDiscoveryRecord(
        page_id="page-unknown-buyer",
        company_name="Thunes",
        target_country_hint="United Arab Emirates",
        evidence="Regional payroll operations support in the UAE.",
    )
    fake_notion = _FakeNotionService(discovery_records=[discovery_record])
    fake_anthropic = _FakeAnthropicService(
        qualifications={
            "page-unknown-buyer": DiscoveryQualification(
                lead=Lead(
                    company_name="Thunes",
                    contact_name="Unknown Contact",
                    contact_role="Unknown Role",
                    target_country="United Arab Emirates",
                    lead_type="direct_payroll",
                    fit_reason="Evidence supports UAE payroll expansion support.",
                ),
                evidence_summary="Thunes shows UAE payroll expansion evidence.",
                confidence_score=8,
                decision="promote",
            )
        }
    )
    agent = LeadDiscoveryAgent(
        notion_service=fake_notion,
        anthropic_service=fake_anthropic,
    )
    result = agent.promote_discovery_records("UAE payroll campaign", max_records=10)

    assert result.promoted_count == 0
    assert result.review_count == 1
    assert len(fake_notion.promoted) == 0
    assert (
        "Auto-promotion blocked because buyer identity is still unknown."
        in fake_notion.processed[0][1].qualification_notes
    )


def test_promote_discovery_records_allows_known_buyer_role_auto_promotion() -> None:
    discovery_record = LeadDiscoveryRecord(
        page_id="page-known-role",
        company_name="Atlas Ops",
        target_country_hint="Saudi Arabia",
        evidence="Regional payroll operations support in Saudi Arabia.",
    )
    fake_notion = _FakeNotionService(discovery_records=[discovery_record])
    fake_anthropic = _FakeAnthropicService(
        qualifications={
            "page-known-role": DiscoveryQualification(
                lead=Lead(
                    company_name="Atlas Ops",
                    contact_name="Unknown Contact",
                    contact_role="Payroll Manager",
                    target_country="Saudi Arabia",
                    lead_type="direct_payroll",
                    fit_reason="Evidence supports Saudi payroll expansion support.",
                ),
                evidence_summary="Atlas Ops shows Saudi payroll expansion evidence.",
                confidence_score=8,
                decision="promote",
            )
        }
    )
    agent = LeadDiscoveryAgent(
        notion_service=fake_notion,
        anthropic_service=fake_anthropic,
    )

    result = agent.promote_discovery_records("Saudi payroll campaign", max_records=10)

    assert result.promoted_count == 1
    assert result.review_count == 0
    assert len(fake_notion.promoted) == 1
