from datetime import timedelta

from app.agents.lifecycle_agent import LifecycleAgent
from app.models.pipeline_record import PipelineRecord
from app.utils.time import utc_now


def test_evaluate_lifecycle_marks_sent_record_for_follow_up_after_three_days() -> None:
    reference_time = utc_now()
    sent_at = (reference_time - timedelta(days=3, hours=1)).isoformat()
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
            outreach_status="sent",
            last_outreach_at=sent_at,
            last_contacted=sent_at,
            next_action="wait_for_reply",
        )
    ]

    agent = LifecycleAgent()
    evaluated_records = agent.evaluate_lifecycle(records, reference_time=reference_time)

    assert evaluated_records[0].next_action == "send_follow_up"


def test_evaluate_lifecycle_marks_contacted_record_for_nudge_after_two_days() -> None:
    reference_time = utc_now()
    contacted_at = (reference_time - timedelta(days=2, hours=2)).isoformat()
    records = [
        PipelineRecord(
            lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
            company_name="Example Ltd",
            contact_name="Jane Smith",
            lead_type="direct_payroll",
            target_country="Saudi Arabia",
            score=8,
            priority="medium",
            sales_motion="direct_client",
            primary_module="Payroll",
            bundle_label="Payroll + HRIS",
            recommended_modules=["Payroll", "HRIS"],
            stage="contacted",
            outreach_status="sent",
            last_outreach_at=contacted_at,
            last_contacted=contacted_at,
            next_action="wait_for_reply",
        )
    ]

    agent = LifecycleAgent()
    evaluated_records = agent.evaluate_lifecycle(records, reference_time=reference_time)

    assert evaluated_records[0].next_action == "nudge_message"


def test_evaluate_lifecycle_marks_stale_proposal_for_escalation() -> None:
    reference_time = utc_now()
    updated_at = (reference_time - timedelta(days=6)).isoformat()
    records = [
        PipelineRecord(
            lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
            company_name="Example Ltd",
            contact_name="Jane Smith",
            lead_type="direct_payroll",
            target_country="Saudi Arabia",
            score=8,
            priority="medium",
            sales_motion="direct_client",
            primary_module="Payroll",
            bundle_label="Payroll + HRIS",
            recommended_modules=["Payroll", "HRIS"],
            stage="proposal",
            outreach_status="sent",
            last_updated_at=updated_at,
            next_action="follow_up_proposal",
        )
    ]

    agent = LifecycleAgent()
    evaluated_records = agent.evaluate_lifecycle(records, reference_time=reference_time)

    assert evaluated_records[0].next_action == "escalate_follow_up"
