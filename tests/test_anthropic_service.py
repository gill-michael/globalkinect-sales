from app.models.lead_discovery_record import LeadDiscoveryRecord
from app.models.lead_intake_record import LeadIntakeRecord
from app.services.anthropic_service import AnthropicService


class _FakeToolUseBlock:
    def __init__(self, input_data):
        self.type = "tool_use"
        self.input = input_data


class _FakeMessagesResponse:
    def __init__(self, parsed):
        if parsed is None:
            self.content = []
        else:
            self.content = [_FakeToolUseBlock(parsed)]


class _FakeMessagesResource:
    def __init__(self, parsed):
        self._parsed = parsed
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeMessagesResponse(self._parsed)


class _FakeAnthropicClient:
    def __init__(self, parsed):
        self.messages = _FakeMessagesResource(parsed)


def test_normalize_lead_from_intake_uses_structured_response() -> None:
    parsed_payload = {
        "company_name": "Polaris Health",
        "contact_name": "Nadia Saleh",
        "contact_role": "People Director",
        "email": "nadia@polarishealth.com",
        "linkedin_url": "https://linkedin.com/in/nadia-saleh",
        "company_country": "Germany",
        "target_country": "KSA",
        "lead_type": "payroll",
        "fit_reason": "Payroll-led expansion into Saudi Arabia.",
    }
    client = _FakeAnthropicClient(parsed_payload)
    service = AnthropicService(client=client)
    intake_record = LeadIntakeRecord(
        page_id="page-1",
        company_name="Polaris Health",
        contact_name="Nadia Saleh",
        contact_role="People Director",
        company_country="Germany",
        target_country="Saudi Arabia",
        lead_type_hint="direct_payroll",
    )

    lead = service.normalize_lead_from_intake(
        intake_record,
        campaign="Saudi Arabia hiring campaign",
    )

    assert lead.company_name == "Polaris Health"
    assert lead.target_country == "Saudi Arabia"
    assert lead.lead_type == "direct_payroll"
    assert (
        client.messages.last_kwargs["model"]
        == service.model
    )
    assert client.messages.last_kwargs["tool_choice"] == {
        "type": "tool",
        "name": "normalize_lead",
    }


def test_build_lead_from_intake_fallback_preserves_raw_values() -> None:
    service = AnthropicService(client=_FakeAnthropicClient(parsed=None))
    intake_record = LeadIntakeRecord(
        page_id="page-2",
        company_name="Atlas Ops",
        contact_name=None,
        contact_role=None,
        company_country="United Kingdom",
        target_country="UAE",
        lead_type_hint="recruitment partner",
        notes="Recruiter placing into the UAE.",
    )

    lead = service.build_lead_from_intake_fallback(
        intake_record,
        campaign="UAE partner campaign",
    )

    assert lead.contact_name == "Unknown Contact"
    assert lead.contact_role == "Unknown Role"
    assert lead.target_country == "United Arab Emirates"
    assert lead.lead_type == "recruitment_partner"
    assert lead.fit_reason == "Recruiter placing into the UAE."


def test_normalize_lead_from_intake_treats_null_placeholders_as_missing() -> None:
    parsed_payload = {
        "company_name": "Guidepoint",
        "contact_name": "null",
        "contact_role": "null",
        "email": None,
        "linkedin_url": None,
        "company_country": None,
        "target_country": "UAE",
        "lead_type": "payroll",
        "fit_reason": "Payroll-led expansion into the UAE.",
    }
    client = _FakeAnthropicClient(parsed_payload)
    service = AnthropicService(client=client)
    intake_record = LeadIntakeRecord(
        page_id="page-null",
        company_name="Guidepoint",
        contact_name=None,
        contact_role=None,
        target_country="United Arab Emirates",
        lead_type_hint="direct_payroll",
    )

    lead = service.normalize_lead_from_intake(intake_record)

    assert lead.contact_name == "Unknown Contact"
    assert lead.contact_role == "Unknown Role"


def test_qualify_discovery_record_uses_structured_response() -> None:
    parsed_payload = {
        "company_name": "North Star Health",
        "contact_name": "Nadia Saleh",
        "contact_role": "People Director",
        "email": "nadia@northstarhealth.com",
        "linkedin_url": "https://linkedin.com/in/nadia-saleh",
        "company_country": "Germany",
        "target_country": "KSA",
        "lead_type": "payroll",
        "fit_reason": "Evidence points to payroll-led Saudi expansion.",
        "evidence_summary": "Hiring payroll operations in Saudi Arabia from Germany.",
        "confidence_score": 9,
        "decision": "approved",
        "qualification_notes": "Two clear hiring signals.",
    }
    client = _FakeAnthropicClient(parsed_payload)
    service = AnthropicService(client=client)
    discovery_record = LeadDiscoveryRecord(
        page_id="page-3",
        company_name="North Star Health",
        source_url="https://example.com/saudi-jobs",
        evidence="Hiring payroll operations manager in Riyadh.",
        target_country_hint="Saudi Arabia",
    )

    qualification = service.qualify_discovery_record(
        discovery_record,
        campaign="Saudi Arabia discovery campaign",
    )

    assert qualification.lead.target_country == "Saudi Arabia"
    assert qualification.lead.lead_type == "direct_payroll"
    assert qualification.decision == "promote"
    assert qualification.confidence_score == 9
    assert client.messages.last_kwargs["model"] == service.discovery_model


def test_build_discovery_qualification_fallback_scores_evidence() -> None:
    service = AnthropicService(client=_FakeAnthropicClient(parsed=None))
    discovery_record = LeadDiscoveryRecord(
        page_id="page-4",
        company_name="Cedar Talent Partners",
        source_url="https://example.com/recruitment-uae",
        source_type="staffing partner",
        evidence="Recruitment firm placing talent into the UAE and needing EOR support.",
        contact_name="Layla Mansour",
        contact_role="Head of People Partnerships",
        target_country_hint="UAE",
        notes=(
            "Buyer hypothesis: Recruitment leader or operations director. "
            "Commercial trigger: regional recruitment partner placing into the UAE."
        ),
    )

    qualification = service.build_discovery_qualification_fallback(
        discovery_record,
        campaign="UAE partner discovery campaign",
    )

    assert qualification.lead.target_country == "United Arab Emirates"
    assert qualification.lead.lead_type == "recruitment_partner"
    assert qualification.decision == "promote"
    assert qualification.confidence_score >= 7


def test_build_lead_from_intake_fallback_normalizes_secondary_markets() -> None:
    service = AnthropicService(client=_FakeAnthropicClient(parsed=None))
    intake_record = LeadIntakeRecord(
        page_id="page-5",
        company_name="Atlas Ops",
        contact_name="Maya Khoury",
        contact_role="Payroll Manager",
        company_country="United Kingdom",
        target_country="Amman",
        lead_type_hint="payroll",
        notes="Regional payroll expansion into Jordan.",
    )

    lead = service.build_lead_from_intake_fallback(
        intake_record,
        campaign="Regional payroll expansion",
    )

    assert lead.target_country == "Jordan"
    assert lead.lead_type == "direct_payroll"


def test_build_discovery_qualification_fallback_can_promote_hris_without_target_country() -> None:
    service = AnthropicService(client=_FakeAnthropicClient(parsed=None))
    discovery_record = LeadDiscoveryRecord(
        page_id="page-6",
        company_name="People Systems Group",
        source_url="https://example.com/hris-role",
        source_type="careers_feed",
        evidence="Senior HRIS Manager role focused on global people systems operations.",
        contact_name="Rania Aziz",
        contact_role="People Systems Director",
        notes=(
            "Buyer hypothesis: People Operations Lead or HRIS owner. "
            "Commercial trigger: HRIS standardization and people systems expansion."
        ),
    )

    qualification = service.build_discovery_qualification_fallback(
        discovery_record,
        campaign="Global HRIS expansion",
    )

    assert qualification.lead.lead_type == "hris"
    assert qualification.decision == "promote"
    assert qualification.lead.target_country is None


def test_build_lead_from_intake_fallback_treats_null_placeholders_as_missing() -> None:
    service = AnthropicService(client=_FakeAnthropicClient(parsed=None))
    intake_record = LeadIntakeRecord(
        page_id="page-7",
        company_name="Guidepoint",
        contact_name="null",
        contact_role="N/A",
        target_country="UAE",
        lead_type_hint="payroll",
    )

    lead = service.build_lead_from_intake_fallback(intake_record)

    assert lead.contact_name == "Unknown Contact"
    assert lead.contact_role == "Unknown Role"


def test_discovery_qualification_input_includes_commercial_standard() -> None:
    service = AnthropicService(client=_FakeAnthropicClient(parsed=None))
    discovery_record = LeadDiscoveryRecord(
        page_id="page-8",
        company_name="Atlas Ops",
        evidence="Regional payroll operations hiring in Saudi Arabia.",
    )

    payload = service._build_discovery_qualification_input(
        discovery_record,
        campaign="Saudi payroll expansion",
    )

    assert "Qualification standard:" in payload
    assert "buyer hypothesis" in payload.lower()
