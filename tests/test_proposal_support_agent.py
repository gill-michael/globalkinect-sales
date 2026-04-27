from app.agents.proposal_support_agent import ProposalSupportAgent
from app.models.lead import Lead
from app.models.pipeline_record import PipelineRecord
from app.models.solution_recommendation import SolutionRecommendation


def test_create_deal_support_packages_with_solution_returns_one_package_per_record() -> None:
    leads = [
        Lead(
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            contact_role="Founder",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            score=9,
            priority="high",
            recommended_angle="Lead with payroll compliance, local processing confidence, and GCC execution support.",
        ),
        Lead(
            # Was a recruitment_partner; channel discontinued
            # (see docs/RECRUITMENT_PARTNER_DISCONTINUATION.md). Replaced
            # with an HRIS lead so the test still exercises a different
            # bundle and motion.
            company_name="Atlas People Ops",
            contact_name="Helen Price",
            contact_role="People Director",
            target_country="United Arab Emirates",
            lead_type="hris",
            score=8,
            priority="high",
            recommended_angle="Lead with stronger HRIS control, employee visibility, and operational consistency across markets.",
        ),
    ]
    solution_recommendations = [
        SolutionRecommendation(
            lead_reference="ScaleBridge Health|Daniel Morris|Saudi Arabia|direct_payroll",
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            target_country="Saudi Arabia",
            sales_motion="direct_client",
            recommended_modules=["Payroll", "HRIS"],
            primary_module="Payroll",
            bundle_label="Payroll + HRIS",
            commercial_strategy="Position a payroll-led platform entry point for Saudi Arabia with added operational visibility and control.",
            rationale="The current fit is payroll-led with stronger control.",
        ),
        SolutionRecommendation(
            lead_reference="Atlas People Ops|Helen Price|the UAE|hris",
            company_name="Atlas People Ops",
            contact_name="Helen Price",
            target_country="United Arab Emirates",
            sales_motion="direct_client",
            recommended_modules=["Payroll", "HRIS"],
            primary_module="HRIS",
            bundle_label="Payroll + HRIS",
            commercial_strategy="Position a payroll-led platform entry point for the UAE with added operational visibility and control.",
            rationale="The wider fit is HRIS-led with operational visibility.",
        ),
    ]
    pipeline_records = [
        PipelineRecord(
            lead_reference="ScaleBridge Health|Daniel Morris|Saudi Arabia|direct_payroll",
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            lead_type="direct_payroll",
            target_country="Saudi Arabia",
            score=9,
            priority="high",
            stage="replied",
            outreach_status="sent",
            next_action="book_discovery_call",
        ),
        PipelineRecord(
            lead_reference="Atlas People Ops|Helen Price|the UAE|hris",
            company_name="Atlas People Ops",
            contact_name="Helen Price",
            lead_type="hris",
            target_country="United Arab Emirates",
            score=8,
            priority="high",
            stage="proposal",
            outreach_status="sent",
            next_action="follow_up_proposal",
        ),
    ]

    agent = ProposalSupportAgent()
    packages = agent.create_deal_support_packages_with_solution(
        leads,
        pipeline_records,
        solution_recommendations,
    )

    assert len(packages) == 2
    for package in packages:
        assert package.lead_reference
        assert package.stage
        assert package.call_prep_summary
        assert package.recap_email_subject
        assert package.recap_email_body
        assert package.proposal_summary
        assert package.next_steps_message
        assert package.objection_response


def test_deal_support_uses_bundle_label_over_lead_type_and_preserves_reference() -> None:
    leads = [
        Lead(
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            contact_role="Head of People",
            target_country="United Arab Emirates",
            lead_type="direct_payroll",
            score=10,
            priority="high",
            recommended_angle="Lead with payroll compliance, local processing confidence, and GCC execution support.",
        ),
        Lead(
            # Was a recruitment_partner; channel discontinued
            # (see docs/RECRUITMENT_PARTNER_DISCONTINUATION.md). Replaced
            # with a direct_eor lead which still gives a different bundle
            # from the direct_payroll above so the assertions below
            # continue to test bundle-label preservation across types.
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            contact_role="Founder",
            target_country="United Arab Emirates",
            lead_type="direct_eor",
            score=9,
            priority="high",
            recommended_angle="Position Global Kinect around hiring into market without waiting for local entity setup.",
        ),
    ]
    solution_recommendations = [
        SolutionRecommendation(
            lead_reference="Desert Peak Technologies|Amira Hassan|the UAE|direct_payroll",
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            target_country="United Arab Emirates",
            sales_motion="direct_client",
            recommended_modules=["EOR", "Payroll", "HRIS"],
            primary_module="EOR",
            bundle_label="Full Platform",
            commercial_strategy="Position Global Kinect as a single operating platform for hiring, payroll, and HR control in the UAE.",
            rationale="The wider fit is a unified platform model.",
        ),
        SolutionRecommendation(
            lead_reference="ScaleBridge Health|Daniel Morris|the UAE|direct_eor",
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            target_country="United Arab Emirates",
            sales_motion="direct_client",
            recommended_modules=["EOR", "Payroll"],
            primary_module="EOR",
            bundle_label="EOR + Payroll",
            commercial_strategy="Position a fast market-entry bundle for the UAE that combines compliant employment with payroll execution.",
            rationale="The current fit is an EOR-led bundle.",
        ),
    ]
    pipeline_records = [
        PipelineRecord(
            lead_reference="Desert Peak Technologies|Amira Hassan|the UAE|direct_payroll",
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            lead_type="direct_payroll",
            target_country="United Arab Emirates",
            score=10,
            priority="high",
            stage="call_booked",
            outreach_status="sent",
            next_action="prepare_for_call",
        ),
        PipelineRecord(
            lead_reference="ScaleBridge Health|Daniel Morris|the UAE|direct_eor",
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            lead_type="direct_eor",
            target_country="United Arab Emirates",
            score=9,
            priority="high",
            stage="proposal",
            outreach_status="sent",
            next_action="follow_up_proposal",
        ),
    ]

    agent = ProposalSupportAgent()
    packages = agent.create_deal_support_packages_with_solution(
        leads,
        pipeline_records,
        solution_recommendations,
    )

    assert packages[0].lead_reference == pipeline_records[0].lead_reference
    assert packages[0].stage == pipeline_records[0].stage
    assert packages[0].bundle_label == "Full Platform"
    assert packages[0].primary_module == "EOR"
    assert packages[0].recommended_modules == ["EOR", "Payroll", "HRIS"]
    assert "full platform" in packages[0].proposal_summary.lower()
    assert "eor, payroll, hris" in packages[0].proposal_summary.lower()
    # Was an assertion about the recruitment_partner copy ("partner-ready
    # EOR + Payroll offer"); channel discontinued — the second fixture is
    # now a direct_eor lead with EOR + Payroll bundle, so we assert the
    # corresponding direct-client copy instead.
    assert "eor + payroll" in packages[1].call_prep_summary.lower()
    assert "fast market-entry" in packages[1].call_prep_summary.lower()
    assert (
        "entity" in packages[1].objection_response.lower()
        or "speed" in packages[1].objection_response.lower()
    )
    assert packages[0].proposal_summary != packages[1].proposal_summary
    assert packages[0].objection_response != packages[1].objection_response
