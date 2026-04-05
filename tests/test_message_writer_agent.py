from app.agents.message_writer_agent import MessageWriterAgent
from app.models.lead import Lead
from app.models.solution_recommendation import SolutionRecommendation


def test_generate_messages_legacy_method_still_returns_one_output_per_lead() -> None:
    leads = [
        Lead(
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            contact_role="Head of People",
            target_country="United Arab Emirates",
            lead_type="direct_eor",
            recommended_angle="Position GlobalKinect as the fastest compliant EOR entry path for market expansion.",
        ),
        Lead(
            company_name="Nile Talent Partners",
            contact_name="Layla Fawzi",
            contact_role="Managing Director",
            target_country="United Arab Emirates",
            lead_type="recruitment_partner",
            recommended_angle="Position GlobalKinect as the execution partner for employing and paying placed talent compliantly.",
        ),
    ]

    agent = MessageWriterAgent()
    messages = agent.generate_messages(leads)

    assert len(messages) == 2
    for message in messages:
        assert message.lead_reference
        assert message.linkedin_message
        assert len(message.linkedin_message) <= 300
        assert message.email_subject
        assert message.email_message
        assert message.follow_up_message


def test_generate_messages_with_solution_returns_one_output_per_recommendation() -> None:
    leads = [
        Lead(
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            contact_role="Head of People",
            target_country="United Arab Emirates",
            lead_type="direct_payroll",
            recommended_angle="Lead with payroll compliance, local processing reliability, and reduced operational overhead.",
        ),
        Lead(
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            contact_role="Founder",
            target_country="Saudi Arabia",
            lead_type="direct_eor",
            recommended_angle="Position GlobalKinect around hiring into market without waiting for local entity setup.",
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
            commercial_strategy="Position GlobalKinect as a single operating platform for hiring, payroll, and HR control in the UAE.",
            rationale="The wider fit is a unified platform model.",
        ),
        SolutionRecommendation(
            lead_reference="ScaleBridge Health|Daniel Morris|Saudi Arabia|direct_eor",
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
    ]

    agent = MessageWriterAgent()
    messages = agent.generate_messages_with_solution(leads, solution_recommendations)

    assert len(messages) == 2
    for message, solution_recommendation in zip(messages, solution_recommendations):
        assert message.lead_reference == solution_recommendation.lead_reference
        assert message.sales_motion == solution_recommendation.sales_motion
        assert message.primary_module == solution_recommendation.primary_module
        assert message.bundle_label == solution_recommendation.bundle_label
        assert message.linkedin_message
        assert len(message.linkedin_message) <= 300
        assert message.email_subject
        assert message.email_message
        assert message.follow_up_message


def test_generate_messages_with_solution_uses_bundle_label_over_lead_type() -> None:
    leads = [
        Lead(
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            contact_role="Head of People",
            target_country="United Arab Emirates",
            lead_type="direct_payroll",
            recommended_angle="Lead with payroll compliance, local processing reliability, and reduced operational overhead.",
        ),
        Lead(
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            contact_role="Founder",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            recommended_angle="Lead with payroll compliance, local processing reliability, and reduced operational overhead.",
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
            commercial_strategy="Position GlobalKinect as a single operating platform for hiring, payroll, and HR control in the UAE.",
            rationale="The wider fit is a unified platform model.",
        ),
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
    ]

    agent = MessageWriterAgent()
    messages = agent.generate_messages_with_solution(leads, solution_recommendations)

    assert "full platform support" in messages[0].email_subject.lower()
    assert "full platform" in messages[0].email_message.lower()
    assert "hiring, payroll, and hr control" in messages[0].linkedin_message.lower()
    assert "payroll + hris support" in messages[1].email_subject.lower()
    assert "payroll + hris" in messages[1].email_message.lower()
    assert "payroll + hris" in messages[1].follow_up_message.lower()
    assert messages[0].linkedin_message != messages[1].linkedin_message
    assert messages[0].email_subject != messages[1].email_subject
