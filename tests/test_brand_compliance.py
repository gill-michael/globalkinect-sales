"""Regression test: no draft entering the Outreach Queue may contain
the literal one-word "GlobalKinect". The canonical brand rule is
"Global Kinect" (two words).

This test feeds clean fixtures (no "GlobalKinect" anywhere in inputs)
through the deterministic generators that ship into the queue:
  - LeadScoringAgent.recommended_angle
  - SolutionDesignAgent.commercial_strategy / rationale
  - MessageWriterAgent.generate_messages_with_solution -> linkedin /
    email subject / email body / follow-up

If any of those emit "GlobalKinect" in the output, the brand rule
is being violated somewhere in the deterministic copy templates.
"""

from app.agents.lead_scoring_agent import LeadScoringAgent
from app.agents.message_writer_agent import MessageWriterAgent
from app.agents.solution_design_agent import SolutionDesignAgent
from app.models.lead import Lead


BANNED = "GlobalKinect"


def _build_clean_leads() -> list[Lead]:
    """Spread inputs across lead_type / target_country / role so the
    generators exercise their full template tables.

    `recruitment_partner` is excluded because the channel is formally
    discontinued — see docs/RECRUITMENT_PARTNER_DISCONTINUATION.md.
    Including it here would just produce a logged-and-skipped lead
    that contributes nothing to brand-rule coverage.
    """
    return [
        Lead(
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            contact_role="Head of People",
            email="amira@example.com",
            linkedin_url="https://linkedin.com/in/amira-hassan",
            company_country="United Kingdom",
            target_country="United Arab Emirates",
            lead_type="direct_eor",
        ),
        Lead(
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            contact_role="Founder",
            email="daniel@example.com",
            company_country="Germany",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
        ),
        Lead(
            company_name="Atlas People Ops",
            contact_name="Helen Price",
            contact_role="People Director",
            company_country="Netherlands",
            target_country="Egypt",
            lead_type="hris",
        ),
    ]


def test_recommended_angle_does_not_emit_one_word_brand() -> None:
    leads = _build_clean_leads()
    scored = LeadScoringAgent().score_leads(leads)
    for lead in scored:
        assert lead.recommended_angle, lead.company_name
        assert BANNED not in lead.recommended_angle, (
            f"recommended_angle for {lead.company_name} contains "
            f"'{BANNED}': {lead.recommended_angle!r}"
        )


def test_solution_recommendations_do_not_emit_one_word_brand() -> None:
    scored_leads = LeadScoringAgent().score_leads(_build_clean_leads())
    recommendations = SolutionDesignAgent().create_solution_recommendations(
        scored_leads
    )
    for recommendation in recommendations:
        for field_name in ("commercial_strategy", "rationale"):
            value = getattr(recommendation, field_name)
            assert BANNED not in value, (
                f"{field_name} for {recommendation.company_name} contains "
                f"'{BANNED}': {value!r}"
            )


def test_outreach_queue_drafts_do_not_emit_one_word_brand() -> None:
    scored_leads = LeadScoringAgent().score_leads(_build_clean_leads())
    recommendations = SolutionDesignAgent().create_solution_recommendations(
        scored_leads
    )
    messages = MessageWriterAgent().generate_messages_with_solution(
        scored_leads, recommendations
    )
    for message in messages:
        for field_name in (
            "linkedin_message",
            "email_subject",
            "email_message",
            "follow_up_message",
        ):
            value = getattr(message, field_name)
            assert BANNED not in value, (
                f"{field_name} for {message.lead_reference} contains "
                f"'{BANNED}': {value!r}"
            )
