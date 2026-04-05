from app.agents.execution_agent import ExecutionAgent
from app.models.pipeline_record import PipelineRecord


def test_generate_tasks_creates_send_message_for_drafted_records() -> None:
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

    agent = ExecutionAgent()
    tasks = agent.generate_tasks(records)

    assert len(tasks) == 1
    assert tasks[0].task_type == "send_message"
    assert tasks[0].priority == "high"
    assert tasks[0].due_in_days == 0
    assert tasks[0].status == "open"
    assert "send the drafted outreach" in tasks[0].description.lower()


def test_generate_tasks_creates_book_call_for_replied_stage() -> None:
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
            stage="replied",
            outreach_status="sent",
            next_action="book_discovery_call",
        )
    ]

    agent = ExecutionAgent()
    tasks = agent.generate_tasks(records)

    assert len(tasks) == 1
    assert tasks[0].task_type == "book_call"
    assert tasks[0].due_in_days == 1
    assert "discovery call" in tasks[0].description.lower()


def test_generate_tasks_creates_follow_up_for_proposal_stage() -> None:
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
            next_action="follow_up_proposal",
        )
    ]

    agent = ExecutionAgent()
    tasks = agent.generate_tasks(records)

    assert len(tasks) == 1
    assert tasks[0].task_type == "follow_up"
    assert tasks[0].due_in_days == 2
    assert "proposal" in tasks[0].description.lower()


def test_generate_tasks_creates_nudge_message_when_next_action_requires_it() -> None:
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
            next_action="nudge_message",
        )
    ]

    agent = ExecutionAgent()
    tasks = agent.generate_tasks(records)

    assert len(tasks) == 1
    assert tasks[0].task_type == "nudge_message"
    assert tasks[0].due_in_days == 0


def test_generate_tasks_creates_escalation_task_when_required() -> None:
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
            next_action="escalate_follow_up",
        )
    ]

    agent = ExecutionAgent()
    tasks = agent.generate_tasks(records)

    assert len(tasks) == 1
    assert tasks[0].task_type == "escalate_follow_up"
    assert tasks[0].priority == "high"
    assert tasks[0].due_in_days == 0
