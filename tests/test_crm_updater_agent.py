from app.agents.crm_updater_agent import CRMUpdaterAgent
from app.agents.message_writer_agent import MessageWriterAgent
from app.models.lead import Lead
from app.models.solution_recommendation import SolutionRecommendation


def test_create_pipeline_records_sets_defaults() -> None:
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
            company_name="Nile Talent Partners",
            contact_name="Layla Fawzi",
            contact_role="Managing Director",
            target_country="United Arab Emirates",
            lead_type="recruitment_partner",
            score=8,
            priority="high",
            recommended_angle="Position GlobalKinect as the employment and payroll partner behind recruiter-led placements.",
        ),
    ]

    message_writer_agent = MessageWriterAgent()
    outreach_messages = message_writer_agent.generate_messages(leads)

    crm_updater_agent = CRMUpdaterAgent()
    records = crm_updater_agent.create_pipeline_records(leads, outreach_messages)

    assert len(records) == 2
    assert records[0].lead_reference == outreach_messages[0].lead_reference
    assert records[0].stage == "new"
    assert records[0].outreach_status == "drafted"
    assert records[0].next_action == "review_and_send_message"
    assert records[1].stage == "new"
    assert records[1].outreach_status == "drafted"
    assert records[1].next_action == "review_and_send_message"


def test_create_pipeline_records_without_messages_sets_not_started_defaults() -> None:
    leads = [
        Lead(
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            contact_role="Founder",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            score=9,
            priority="high",
        )
    ]

    crm_updater_agent = CRMUpdaterAgent()
    records = crm_updater_agent.create_pipeline_records(leads)

    assert len(records) == 1
    assert records[0].lead_reference == "ScaleBridge Health|Daniel Morris|Saudi Arabia|direct_payroll"
    assert records[0].stage == "new"
    assert records[0].outreach_status == "not_started"
    assert records[0].next_action == "draft_message"


def test_create_pipeline_records_with_solution_populates_bundle_fields() -> None:
    leads = [
        Lead(
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            contact_role="Founder",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            score=9,
            priority="high",
        )
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
        )
    ]

    crm_updater_agent = CRMUpdaterAgent()
    records = crm_updater_agent.create_pipeline_records_with_solution(
        leads,
        solution_recommendations,
    )

    assert len(records) == 1
    assert records[0].lead_reference == solution_recommendations[0].lead_reference
    assert records[0].sales_motion == "direct_client"
    assert records[0].primary_module == "Payroll"
    assert records[0].bundle_label == "Payroll + HRIS"
    assert records[0].recommended_modules == ["Payroll", "HRIS"]
    assert records[0].outreach_status == "not_started"
    assert records[0].created_at
    assert records[0].last_updated_at


def test_update_stage_and_activity_logging_work() -> None:
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
        )
    ]

    message_writer_agent = MessageWriterAgent()
    outreach_messages = message_writer_agent.generate_messages(leads)

    crm_updater_agent = CRMUpdaterAgent()
    record = crm_updater_agent.create_pipeline_records(leads, outreach_messages)[0]
    updated_record = crm_updater_agent.update_stage(record, "contacted")
    action_record = crm_updater_agent.set_next_action(updated_record, "send_follow_up_if_no_reply")
    noted_record = crm_updater_agent.log_activity(action_record, "Initial outreach drafted and queued for review.")

    assert updated_record.stage == "contacted"
    assert updated_record.next_action == "wait_for_reply"
    assert updated_record.outreach_status == "drafted"
    assert action_record.next_action == "send_follow_up_if_no_reply"
    assert action_record.stage == "contacted"
    assert noted_record.notes is not None
    assert "queued for review" in noted_record.notes
    assert noted_record.stage == "contacted"


def test_create_pipeline_records_raises_for_mismatched_counts() -> None:
    leads = [
        Lead(
            company_name="ScaleBridge Health",
            contact_name="Daniel Morris",
            contact_role="Founder",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            score=9,
            priority="high",
        )
    ]

    crm_updater_agent = CRMUpdaterAgent()

    try:
        crm_updater_agent.create_pipeline_records(leads, [])
    except ValueError as exc:
        assert "counts must match" in str(exc)
    else:
        raise AssertionError("Expected ValueError for mismatched lead and message counts.")


def test_update_outreach_status_updates_status_and_preserves_fields() -> None:
    leads = [
        Lead(
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            contact_role="Head of People",
            target_country="United Arab Emirates",
            lead_type="direct_eor",
            score=10,
            priority="high",
        )
    ]

    solution_recommendations = [
        SolutionRecommendation(
            lead_reference="Desert Peak Technologies|Amira Hassan|the UAE|direct_eor",
            company_name="Desert Peak Technologies",
            contact_name="Amira Hassan",
            target_country="United Arab Emirates",
            sales_motion="direct_client",
            recommended_modules=["EOR", "Payroll", "HRIS"],
            primary_module="EOR",
            bundle_label="Full Platform",
            commercial_strategy="Position GlobalKinect as a single operating platform for hiring, payroll, and HR control in the UAE.",
            rationale="The wider fit is a unified platform model.",
        )
    ]

    crm_updater_agent = CRMUpdaterAgent()
    record = crm_updater_agent.create_pipeline_records_with_solution(
        leads,
        solution_recommendations,
    )[0]
    updated_record = crm_updater_agent.update_outreach_status(record, "sent")

    assert updated_record.outreach_status == "sent"
    assert updated_record.lead_reference == record.lead_reference
    assert updated_record.stage == record.stage
    assert updated_record.score == record.score
    assert updated_record.priority == record.priority
    assert updated_record.sales_motion == "direct_client"
    assert updated_record.primary_module == "EOR"
    assert updated_record.bundle_label == "Full Platform"
    assert updated_record.recommended_modules == ["EOR", "Payroll", "HRIS"]
    assert updated_record.last_outreach_at is not None
    assert updated_record.next_action == "wait_for_reply"
