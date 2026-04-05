from unittest.mock import MagicMock

from app.models.deal_support_package import DealSupportPackage
from app.models.execution_task import ExecutionTask
from app.models.lead import Lead
from app.models.outreach_message import OutreachMessage
from app.models.pipeline_record import PipelineRecord
from app.models.solution_recommendation import SolutionRecommendation
from app.services.supabase_service import SupabaseService


def test_ensure_configured_raises_when_service_is_not_configured() -> None:
    service = SupabaseService()
    service.client = None
    service._configuration_error = "Supabase credentials are missing. Persistence is disabled."

    try:
        service._ensure_configured()
    except RuntimeError as exc:
        assert "Persistence is disabled" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when Supabase is not configured.")


def test_model_list_to_dicts_serializes_models_cleanly() -> None:
    service = SupabaseService()
    lead = Lead(
        company_name="Example Ltd",
        contact_name="Jane Smith",
        contact_role="Founder",
        target_country="Saudi Arabia",
        lead_type="direct_payroll",
        score=8,
        priority="high",
    )

    payload = service._model_list_to_dicts("outreach_messages", [lead])

    assert payload == [lead.model_dump()]


def test_model_list_to_dicts_excludes_transient_lead_fields_for_leads_table() -> None:
    service = SupabaseService()
    lead = Lead(
        company_name="Example Ltd",
        contact_name="Jane Smith",
        contact_role="Founder",
        target_country="Saudi Arabia",
        lead_type="direct_payroll",
        score=8,
        priority="high",
        feedback_summary="Existing sales activity detected: queue=Approved.",
    )

    payload = service._model_list_to_dicts("leads", [lead])

    assert payload == [
        {
            "company_name": "Example Ltd",
            "contact_name": "Jane Smith",
            "contact_role": "Founder",
            "email": None,
            "linkedin_url": None,
            "company_country": None,
            "target_country": "Saudi Arabia",
            "lead_type": "direct_payroll",
            "fit_reason": None,
            "status": "new",
            "score": 8,
            "priority": "high",
            "recommended_angle": None,
        }
    ]


def test_insert_methods_call_underlying_client_with_expected_payloads() -> None:
    service = SupabaseService()
    fake_client = MagicMock()
    fake_table = MagicMock()
    fake_table.insert.return_value = fake_table
    fake_table.execute.return_value = {"status": "ok"}
    fake_client.table.return_value = fake_table
    service.client = fake_client

    lead = Lead(
        company_name="Example Ltd",
        contact_name="Jane Smith",
        contact_role="Founder",
        target_country="Saudi Arabia",
        lead_type="direct_payroll",
        score=8,
        priority="high",
    )
    message = OutreachMessage(
        lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
        company_name="Example Ltd",
        contact_name="Jane Smith",
        contact_role="Founder",
        lead_type="direct_payroll",
        target_country="Saudi Arabia",
        linkedin_message="LinkedIn message",
        email_subject="Email subject",
        email_message="Email body",
        follow_up_message="Follow up",
    )
    record = PipelineRecord(
        lead_reference=message.lead_reference,
        company_name="Example Ltd",
        contact_name="Jane Smith",
        lead_type="direct_payroll",
        target_country="Saudi Arabia",
        score=8,
        priority="high",
        sales_motion="direct_client",
        primary_module="Payroll",
        bundle_label="Payroll + HRIS",
        recommended_modules=["Payroll", "HRIS"],
        stage="new",
        outreach_status="drafted",
        next_action="review_and_send_message",
    )
    package = DealSupportPackage(
        lead_reference=message.lead_reference,
        company_name="Example Ltd",
        contact_name="Jane Smith",
        lead_type="direct_payroll",
        target_country="Saudi Arabia",
        sales_motion="direct_client",
        primary_module="Payroll",
        bundle_label="Payroll + HRIS",
        recommended_modules=["Payroll", "HRIS"],
        stage="new",
        call_prep_summary="Prep summary",
        recap_email_subject="Recap subject",
        recap_email_body="Recap body",
        proposal_summary="Proposal summary",
        next_steps_message="Next steps",
        objection_response="Objection response",
    )
    recommendation = SolutionRecommendation(
        lead_reference=message.lead_reference,
        company_name="Example Ltd",
        contact_name="Jane Smith",
        target_country="Saudi Arabia",
        sales_motion="direct_client",
        recommended_modules=["Payroll", "HRIS"],
        primary_module="Payroll",
        bundle_label="Payroll + HRIS",
        commercial_strategy="Position a payroll-led platform entry point for Saudi Arabia with added operational visibility and control.",
        rationale="The current fit is payroll-led with stronger control.",
    )
    task = ExecutionTask(
        lead_reference=message.lead_reference,
        task_type="send_message",
        description="Review and send the drafted outreach.",
        priority="high",
        due_in_days=0,
    )

    service.insert_leads([lead])
    service.insert_outreach_messages([message])
    service.insert_pipeline_records([record])
    service.insert_solution_recommendations([recommendation])
    service.insert_deal_support_packages([package])
    service.insert_execution_tasks([task])

    assert fake_client.table.call_args_list[0].args[0] == "leads"
    assert fake_client.table.call_args_list[1].args[0] == "outreach_messages"
    assert fake_client.table.call_args_list[2].args[0] == "pipeline_records"
    assert fake_client.table.call_args_list[3].args[0] == "solution_recommendations"
    assert fake_client.table.call_args_list[4].args[0] == "deal_support_packages"
    assert fake_client.table.call_args_list[5].args[0] == "execution_tasks"
    assert fake_table.insert.call_args_list[0].args[0] == [
        {
            "company_name": "Example Ltd",
            "contact_name": "Jane Smith",
            "contact_role": "Founder",
            "email": None,
            "linkedin_url": None,
            "company_country": None,
            "target_country": "Saudi Arabia",
            "lead_type": "direct_payroll",
            "fit_reason": None,
            "status": "new",
            "score": 8,
            "priority": "high",
            "recommended_angle": None,
        }
    ]
    assert fake_table.insert.call_args_list[1].args[0] == [message.model_dump()]
    assert fake_table.insert.call_args_list[2].args[0] == [
        service._model_to_dict("pipeline_records", record)
    ]
    assert fake_table.insert.call_args_list[3].args[0] == [recommendation.model_dump()]
    assert fake_table.insert.call_args_list[4].args[0] == [package.model_dump()]
    assert fake_table.insert.call_args_list[5].args[0] == [
        service._model_to_dict("execution_tasks", task)
    ]


def test_fetch_methods_use_limit_and_return_response_data() -> None:
    service = SupabaseService()
    fake_client = MagicMock()
    fake_table = MagicMock()
    fake_select = MagicMock()
    fake_limit = MagicMock()
    fake_response = MagicMock()
    fake_response.data = [{"company_name": "Example Ltd"}]

    fake_client.table.return_value = fake_table
    fake_table.select.return_value = fake_select
    fake_select.limit.return_value = fake_limit
    fake_limit.execute.return_value = fake_response
    service.client = fake_client

    leads = service.fetch_leads(limit=5)
    records = service.fetch_pipeline_records(limit=3)
    tasks = service.fetch_execution_tasks(limit=7)

    assert leads == [{"company_name": "Example Ltd"}]
    assert records == [{"company_name": "Example Ltd"}]
    assert tasks == [{"company_name": "Example Ltd"}]
    assert fake_client.table.call_args_list[0].args[0] == "leads"
    assert fake_client.table.call_args_list[1].args[0] == "pipeline_records"
    assert fake_client.table.call_args_list[2].args[0] == "execution_tasks"
    assert fake_select.limit.call_args_list[0].args[0] == 5
    assert fake_select.limit.call_args_list[1].args[0] == 3
    assert fake_select.limit.call_args_list[2].args[0] == 7


def test_fetch_pipeline_record_by_lead_reference_returns_validated_model() -> None:
    service = SupabaseService()
    fake_client = MagicMock()
    fake_table = MagicMock()
    fake_select = MagicMock()
    fake_eq = MagicMock()
    fake_limit = MagicMock()
    record = PipelineRecord(
        lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
        company_name="Example Ltd",
        contact_name="Jane Smith",
        lead_type="direct_payroll",
        target_country="Saudi Arabia",
        score=8,
        priority="high",
        sales_motion="direct_client",
        primary_module="Payroll",
        bundle_label="Payroll + HRIS",
        recommended_modules=["Payroll", "HRIS"],
        stage="new",
        outreach_status="drafted",
        next_action="review_and_send_message",
    )
    fake_response = MagicMock()
    fake_response.data = [record.model_dump()]

    fake_client.table.return_value = fake_table
    fake_table.select.return_value = fake_select
    fake_select.eq.return_value = fake_eq
    fake_eq.limit.return_value = fake_limit
    fake_limit.execute.return_value = fake_response
    service.client = fake_client

    fetched = service.fetch_pipeline_record_by_lead_reference(record.lead_reference)

    assert fetched == record
    assert fake_client.table.call_args.args[0] == "pipeline_records"
    assert fake_table.select.call_args.args[0] == "*"
    assert fake_select.eq.call_args.args == ("lead_reference", record.lead_reference)
    assert fake_eq.limit.call_args.args[0] == 1


def test_update_pipeline_record_calls_update_by_lead_reference() -> None:
    service = SupabaseService()
    fake_client = MagicMock()
    fake_table = MagicMock()
    fake_update = MagicMock()
    fake_eq = MagicMock()

    fake_client.table.return_value = fake_table
    fake_table.update.return_value = fake_update
    fake_update.eq.return_value = fake_eq
    fake_eq.execute.return_value = {"status": "ok"}
    service.client = fake_client

    record = PipelineRecord(
        lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
        company_name="Example Ltd",
        contact_name="Jane Smith",
        lead_type="direct_payroll",
        target_country="Saudi Arabia",
        score=8,
        priority="high",
        sales_motion="direct_client",
        primary_module="Payroll",
        bundle_label="Payroll + HRIS",
        recommended_modules=["Payroll", "HRIS"],
        stage="proposal",
        outreach_status="sent",
        next_action="follow_up_proposal",
    )

    service.update_pipeline_record(record)

    assert fake_client.table.call_args.args[0] == "pipeline_records"
    assert fake_table.update.call_args.args[0] == service._model_to_dict(
        "pipeline_records", record
    )
    assert fake_update.eq.call_args.args == ("lead_reference", record.lead_reference)


def test_upsert_pipeline_records_calls_underlying_client() -> None:
    service = SupabaseService()
    fake_client = MagicMock()
    fake_table = MagicMock()
    fake_upsert = MagicMock()

    fake_client.table.return_value = fake_table
    fake_table.upsert.return_value = fake_upsert
    fake_upsert.execute.return_value = {"status": "ok"}
    service.client = fake_client

    records = [
        PipelineRecord(
            lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
            company_name="Example Ltd",
            contact_name="Jane Smith",
            lead_type="direct_payroll",
            target_country="Saudi Arabia",
            score=8,
            priority="high",
            sales_motion="direct_client",
            primary_module="Payroll",
            bundle_label="Payroll + HRIS",
            recommended_modules=["Payroll", "HRIS"],
            stage="new",
            outreach_status="drafted",
            next_action="review_and_send_message",
        )
    ]

    service.upsert_pipeline_records(records)

    assert fake_client.table.call_args.args[0] == "pipeline_records"
    assert fake_table.upsert.call_args.args[0] == [
        service._model_to_dict("pipeline_records", records[0])
    ]
    assert fake_table.upsert.call_args.kwargs["on_conflict"] == "lead_reference"


def test_upsert_solution_recommendations_calls_underlying_client() -> None:
    service = SupabaseService()
    fake_client = MagicMock()
    fake_table = MagicMock()
    fake_upsert = MagicMock()

    fake_client.table.return_value = fake_table
    fake_table.upsert.return_value = fake_upsert
    fake_upsert.execute.return_value = {"status": "ok"}
    service.client = fake_client

    recommendations = [
        SolutionRecommendation(
            lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
            company_name="Example Ltd",
            contact_name="Jane Smith",
            target_country="Saudi Arabia",
            sales_motion="direct_client",
            recommended_modules=["Payroll", "HRIS"],
            primary_module="Payroll",
            bundle_label="Payroll + HRIS",
            commercial_strategy="Position a payroll-led platform entry point.",
            rationale="Payroll is the strongest commercial entry point.",
        )
    ]

    service.upsert_solution_recommendations(recommendations)

    assert fake_client.table.call_args.args[0] == "solution_recommendations"
    assert fake_table.upsert.call_args.args[0] == [recommendations[0].model_dump()]
    assert fake_table.upsert.call_args.kwargs["on_conflict"] == "lead_reference"
