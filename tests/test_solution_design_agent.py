from app.agents.solution_design_agent import SolutionDesignAgent
from app.models.lead import Lead
from app.models.pipeline_record import PipelineRecord


def test_create_solution_recommendations_returns_one_per_pair() -> None:
    leads = [
        Lead(
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            contact_role="Head of People",
            target_country="United Arab Emirates",
            lead_type="direct_eor",
            score=10,
            priority="high",
            recommended_angle="Position GlobalKinect around hiring into market without waiting for local entity setup.",
        ),
        Lead(
            company_name="Nile Talent Partners",
            contact_name="Layla Fawzi",
            contact_role="Managing Director",
            target_country="Saudi Arabia",
            lead_type="recruitment_partner",
            score=8,
            priority="high",
            recommended_angle="Position GlobalKinect as the employment and payroll partner behind recruiter-led placements.",
        ),
    ]

    agent = SolutionDesignAgent()
    recommendations = agent.create_solution_recommendations(leads)

    assert len(recommendations) == 2
    for recommendation in recommendations:
        assert recommendation.lead_reference
        assert recommendation.sales_motion
        assert recommendation.recommended_modules
        assert recommendation.primary_module
        assert recommendation.bundle_label
        assert recommendation.commercial_strategy
        assert recommendation.rationale
    assert recommendations[0].lead_reference == "Desert Peak Technologies|Amira Hassan|the UAE|direct_eor"
    assert recommendations[1].lead_reference == "Nile Talent Partners|Layla Fawzi|Saudi Arabia|recruitment_partner"


def test_recruitment_partner_maps_to_partner_motion_and_bundle() -> None:
    lead = Lead(
        company_name="Nile Talent Partners",
        contact_name="Layla Fawzi",
        contact_role="Managing Director",
        target_country="Saudi Arabia",
        lead_type="recruitment_partner",
        recommended_angle="Position GlobalKinect as the employment and payroll partner behind recruiter-led placements.",
    )
    pipeline_record = PipelineRecord(
        lead_reference="Nile Talent Partners|Layla Fawzi|Saudi Arabia|recruitment_partner",
        company_name="Nile Talent Partners",
        contact_name="Layla Fawzi",
        lead_type="recruitment_partner",
        target_country="Saudi Arabia",
        score=8,
        priority="high",
        stage="proposal",
        outreach_status="sent",
        next_action="follow_up_proposal",
    )

    agent = SolutionDesignAgent()
    recommendation = agent.create_solution_recommendation(lead, pipeline_record)

    assert recommendation.lead_reference == pipeline_record.lead_reference
    assert recommendation.sales_motion == "recruitment_partner"
    assert recommendation.recommended_modules == ["EOR", "Payroll"]
    assert recommendation.primary_module == "EOR"
    assert recommendation.bundle_label == "EOR + Payroll"


def test_direct_client_contexts_map_to_meaningfully_different_bundles() -> None:
    leads = [
        Lead(
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            contact_role="Head of People",
            target_country="United Arab Emirates",
            lead_type="direct_eor",
            recommended_angle="Position GlobalKinect around hiring into market without waiting for local entity setup.",
        ),
        Lead(
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            contact_role="Founder",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            recommended_angle="Lead with payroll compliance, local processing confidence, and GCC execution support.",
        ),
    ]
    pipeline_records = [
        PipelineRecord(
            lead_reference="Desert Peak Technologies|Amira Hassan|the UAE|direct_eor",
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            lead_type="direct_eor",
            target_country="United Arab Emirates",
            score=10,
            priority="high",
            stage="call_booked",
            outreach_status="sent",
            next_action="prepare_for_call",
        ),
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
    ]

    agent = SolutionDesignAgent()
    recommendations = agent.create_solution_recommendations(leads, pipeline_records)

    assert recommendations[0].sales_motion == "direct_client"
    assert recommendations[1].sales_motion == "direct_client"
    assert recommendations[0].bundle_label == "Full Platform"
    assert recommendations[1].bundle_label == "Payroll + HRIS"
    assert recommendations[0].recommended_modules != recommendations[1].recommended_modules
    assert recommendations[0].primary_module == "EOR"
    assert recommendations[1].primary_module == "Payroll"


def test_secondary_markets_do_not_get_primary_market_bundle_uplift() -> None:
    lead = Lead(
        company_name="Desert Route Logistics",
        contact_name="Noura Ali",
        contact_role="Head of People",
        target_country="Qatar",
        lead_type="direct_payroll",
        score=10,
        priority="high",
        recommended_angle="Lead with payroll compliance, local processing confidence, and regional execution support.",
    )

    agent = SolutionDesignAgent()
    recommendation = agent.create_solution_recommendation(lead)

    assert recommendation.bundle_label == "Payroll only"
    assert recommendation.primary_module == "Payroll"
