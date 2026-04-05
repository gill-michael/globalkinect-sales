from app.agents.lead_feedback_agent import LeadFeedbackIndex
from app.agents.lead_scoring_agent import LeadScoringAgent
from app.models.lead import Lead
from app.models.lead_feedback_signal import LeadFeedbackSignal


def test_score_leads_assigns_scores_priorities_and_angles() -> None:
    leads = [
        Lead(
            company_name="Example Expansion Co",
            contact_name="Amina Noor",
            contact_role="Founder",
            email="amina@example.com",
            linkedin_url="https://linkedin.com/in/amina-noor",
            company_country="United Kingdom",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
        ),
        Lead(
            company_name="Channel Bridge",
            contact_name="Lars Meijer",
            contact_role="Managing Director",
            email="lars@channelbridge.com",
            company_country="Netherlands",
            target_country="United Arab Emirates",
            lead_type="recruitment_partner",
        ),
        Lead(
            company_name="Partner Recruiters",
            contact_name="Omar Said",
            contact_role="Coordinator",
            target_country="Unknown",
            lead_type="recruitment_partner",
        ),
    ]

    agent = LeadScoringAgent()
    scored_leads = agent.score_leads(leads)

    assert len(scored_leads) == 3

    for lead in scored_leads:
        assert lead.score is not None
        assert 1 <= lead.score <= 10
        assert lead.priority in {"high", "medium", "low"}
        assert lead.recommended_angle

    assert scored_leads[0].priority == "high"
    assert "payroll" in scored_leads[0].recommended_angle.lower()
    assert scored_leads[1].score > scored_leads[2].score
    assert scored_leads[1].priority in {"medium", "high"}
    assert "partner" in scored_leads[1].recommended_angle.lower()
    assert scored_leads[2].priority == "low"


def test_score_leads_rewards_top_target_markets_and_source_countries() -> None:
    leads = [
        Lead(
            company_name="UK Expansion Ltd",
            contact_name="Helen Price",
            contact_role="Head of People",
            company_country="United Kingdom",
            target_country="United Arab Emirates",
            lead_type="direct_eor",
        ),
        Lead(
            company_name="Local Ops Co",
            contact_name="Samir Adel",
            contact_role="Coordinator",
            company_country="Unknown",
            target_country="Egypt",
            lead_type="hris",
        ),
    ]

    agent = LeadScoringAgent()
    scored_leads = agent.score_leads(leads)

    assert scored_leads[0].score > scored_leads[1].score
    assert scored_leads[0].priority in {"medium", "high"}
    assert scored_leads[1].score >= 1


def test_score_leads_supports_secondary_markets_without_treating_them_as_primary() -> None:
    leads = [
        Lead(
            company_name="Primary Market Co",
            contact_name="Helen Price",
            contact_role="Head of People",
            company_country="United Kingdom",
            target_country="United Arab Emirates",
            lead_type="direct_payroll",
        ),
        Lead(
            company_name="Secondary Market Co",
            contact_name="Rami Haddad",
            contact_role="People Director",
            company_country="United Kingdom",
            target_country="Qatar",
            lead_type="direct_payroll",
        ),
    ]

    agent = LeadScoringAgent()
    scored_leads = agent.score_leads(leads)

    assert scored_leads[1].score is not None
    assert scored_leads[1].score >= 1
    assert scored_leads[0].score > scored_leads[1].score
    assert "payroll" in scored_leads[1].recommended_angle.lower()


def test_score_leads_applies_feedback_penalty_for_existing_sales_activity() -> None:
    lead = Lead(
        company_name="Guidepoint",
        contact_name="Unknown Contact",
        contact_role="Unknown Role",
        target_country="United Arab Emirates",
        lead_type="direct_payroll",
    )
    feedback_index = LeadFeedbackIndex(
        by_reference={
            "guidepoint|unknown contact|the uae|direct_payroll": LeadFeedbackSignal(
                lead_reference="Guidepoint|Unknown Contact|the UAE|direct_payroll",
                company_name="Guidepoint",
                queue_status="Approved",
                pipeline_stage="proposal",
                outreach_status="sent",
            )
        }
    )

    agent = LeadScoringAgent()
    scored_lead = agent.score_leads([lead], feedback_index=feedback_index)[0]

    assert scored_lead.score is not None
    assert scored_lead.score <= 4
    assert scored_lead.feedback_summary is not None
    assert "Existing sales activity detected" in scored_lead.feedback_summary
