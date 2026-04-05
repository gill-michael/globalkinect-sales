from app.agents.pipeline_intelligence_agent import PipelineIntelligenceAgent
from app.models.pipeline_record import PipelineRecord


def test_evaluate_pipeline_progresses_sent_record_to_contacted() -> None:
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
            stage="new",
            outreach_status="sent",
            next_action="wait_for_reply",
        )
    ]

    agent = PipelineIntelligenceAgent()
    evaluated_records = agent.evaluate_pipeline(records)

    assert evaluated_records[0].stage == "contacted"
    assert evaluated_records[0].next_action == "wait_for_reply"
    assert evaluated_records[0].bundle_label == "Payroll + HRIS"
    assert evaluated_records[0].primary_module == "Payroll"


def test_evaluate_pipeline_progresses_contacted_reply_to_replied() -> None:
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
            next_action="wait_for_reply",
            notes="Prospect replied and asked for details.",
        )
    ]

    agent = PipelineIntelligenceAgent()
    evaluated_records = agent.evaluate_pipeline(records)

    assert evaluated_records[0].stage == "replied"
    assert evaluated_records[0].next_action == "book_discovery_call"


def test_flag_high_value_deals_returns_high_priority_or_full_platform() -> None:
    records = [
        PipelineRecord(
            lead_reference="High Priority|A|the UAE|direct_eor",
            company_name="High Priority",
            contact_name="A",
            lead_type="direct_eor",
            target_country="United Arab Emirates",
            score=9,
            priority="high",
            sales_motion="direct_client",
            primary_module="EOR",
            bundle_label="EOR + Payroll",
            recommended_modules=["EOR", "Payroll"],
            stage="new",
            outreach_status="drafted",
            next_action="review_and_send_message",
        ),
        PipelineRecord(
            lead_reference="Full Platform|B|the UAE|direct_eor",
            company_name="Full Platform",
            contact_name="B",
            lead_type="direct_eor",
            target_country="United Arab Emirates",
            score=10,
            priority="medium",
            sales_motion="direct_client",
            primary_module="EOR",
            bundle_label="Full Platform",
            recommended_modules=["EOR", "Payroll", "HRIS"],
            stage="proposal",
            outreach_status="sent",
            next_action="follow_up_proposal",
        ),
        PipelineRecord(
            lead_reference="Standard|C|Egypt|direct_payroll",
            company_name="Standard",
            contact_name="C",
            lead_type="direct_payroll",
            target_country="Egypt",
            score=6,
            priority="low",
            sales_motion="direct_client",
            primary_module="Payroll",
            bundle_label="Payroll only",
            recommended_modules=["Payroll"],
            stage="new",
            outreach_status="drafted",
            next_action="review_and_send_message",
        ),
    ]

    agent = PipelineIntelligenceAgent()
    flagged_records = agent.flag_high_value_deals(records)

    assert len(flagged_records) == 2
    assert flagged_records[0].lead_reference == "High Priority|A|the UAE|direct_eor"
    assert flagged_records[1].lead_reference == "Full Platform|B|the UAE|direct_eor"
