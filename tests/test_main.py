from app.models.deal_support_package import DealSupportPackage
from app.models.execution_task import ExecutionTask
from app.models.lead import Lead
from app.models.outreach_message import OutreachMessage
from app.models.pipeline_record import PipelineRecord
from app.models.solution_recommendation import SolutionRecommendation
import main as main_module
from main import _persist_generated_data


class FakeSupabaseService:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def is_configured(self) -> bool:
        return True

    def insert_leads(self, leads) -> None:
        self.calls.append("insert_leads")

    def insert_outreach_messages(self, messages) -> None:
        self.calls.append("insert_outreach_messages")

    def upsert_pipeline_records(self, records) -> None:
        self.calls.append("upsert_pipeline_records")

    def upsert_solution_recommendations(self, recommendations) -> None:
        self.calls.append("upsert_solution_recommendations")

    def insert_deal_support_packages(self, packages) -> None:
        self.calls.append("insert_deal_support_packages")

    def insert_execution_tasks(self, tasks) -> None:
        self.calls.append("insert_execution_tasks")


def test_persist_generated_data_uses_upserts_for_unique_entities() -> None:
    service = FakeSupabaseService()
    lead_reference = "Example Ltd|Jane Smith|Saudi Arabia|direct_payroll"

    leads = [
        Lead(
            company_name="Example Ltd",
            contact_name="Jane Smith",
            contact_role="Founder",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            score=8,
            priority="high",
        )
    ]
    messages = [
        OutreachMessage(
            lead_reference=lead_reference,
            company_name="Example Ltd",
            contact_name="Jane Smith",
            contact_role="Founder",
            lead_type="direct_payroll",
            target_country="Saudi Arabia",
            sales_motion="direct_client",
            primary_module="Payroll",
            bundle_label="Payroll + HRIS",
            linkedin_message="LinkedIn message",
            email_subject="Email subject",
            email_message="Email body",
            follow_up_message="Follow up",
        )
    ]
    records = [
        PipelineRecord(
            lead_reference=lead_reference,
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
    recommendations = [
        SolutionRecommendation(
            lead_reference=lead_reference,
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
    packages = [
        DealSupportPackage(
            lead_reference=lead_reference,
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
    ]
    tasks = [
        ExecutionTask(
            lead_reference=lead_reference,
            task_type="send_message",
            description="Review and send the drafted outreach.",
            priority="high",
            due_in_days=0,
        )
    ]

    _persist_generated_data(
        service,
        leads,
        messages,
        records,
        recommendations,
        packages,
        tasks,
    )

    assert service.calls == [
        "insert_leads",
        "insert_outreach_messages",
        "upsert_pipeline_records",
        "upsert_solution_recommendations",
        "insert_deal_support_packages",
        "insert_execution_tasks",
    ]


def _patch_main_dependencies(monkeypatch, *, run_mode: str, events: list[str]) -> None:
    class FakeOpenAIService:
        def is_configured(self) -> bool:
            return True

    class FakeSupabaseService:
        def is_configured(self) -> bool:
            return False

    class FakeNotionService:
        def is_run_logging_configured(self) -> bool:
            return False

    class FakeDiscoverySourceCollectorAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def is_configured(self) -> bool:
            return False

    class FakeLeadDiscoveryAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def is_configured(self) -> bool:
            return False

    class FakeAutonomousLaneAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def is_configured(self) -> bool:
            return False

    class FakeLeadFeedbackAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def collect_feedback_index(self, limit: int = 300):
            events.append("feedback")
            return {}

    class FakeReviewResult:
        reviewed_count = 1

        def summary(self) -> str:
            return "reviewed=1"

    class FakeOutreachReviewAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def is_configured(self) -> bool:
            return True

        def sync_queue_decisions(self, limit: int = 300):
            events.append("sync")
            return FakeReviewResult()

    class FakeLeadResearchAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def is_real_intake_configured(self) -> bool:
            return True

        def collect_leads(
            self,
            campaign: str,
            max_records: int = 25,
            mark_processed: bool = True,
        ) -> list[Lead]:
            return []

    class FakeNoOpAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class FakeNotionSyncAgent:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def is_configured(self) -> bool:
            return True

    monkeypatch.setattr(main_module, "OpenAIService", FakeOpenAIService)
    monkeypatch.setattr(main_module, "SupabaseService", FakeSupabaseService)
    monkeypatch.setattr(main_module, "NotionService", FakeNotionService)
    monkeypatch.setattr(
        main_module,
        "DiscoverySourceCollectorAgent",
        FakeDiscoverySourceCollectorAgent,
    )
    monkeypatch.setattr(main_module, "AutonomousLaneAgent", FakeAutonomousLaneAgent)
    monkeypatch.setattr(main_module, "LeadDiscoveryAgent", FakeLeadDiscoveryAgent)
    monkeypatch.setattr(main_module, "LeadFeedbackAgent", FakeLeadFeedbackAgent)
    monkeypatch.setattr(main_module, "OutreachReviewAgent", FakeOutreachReviewAgent)
    monkeypatch.setattr(main_module, "LeadResearchAgent", FakeLeadResearchAgent)
    monkeypatch.setattr(main_module, "LeadScoringAgent", FakeNoOpAgent)
    monkeypatch.setattr(main_module, "MessageWriterAgent", FakeNoOpAgent)
    monkeypatch.setattr(main_module, "CRMUpdaterAgent", FakeNoOpAgent)
    monkeypatch.setattr(main_module, "SolutionDesignAgent", FakeNoOpAgent)
    monkeypatch.setattr(main_module, "ProposalSupportAgent", FakeNoOpAgent)
    monkeypatch.setattr(main_module, "PipelineIntelligenceAgent", FakeNoOpAgent)
    monkeypatch.setattr(main_module, "LifecycleAgent", FakeNoOpAgent)
    monkeypatch.setattr(main_module, "ExecutionAgent", FakeNoOpAgent)
    monkeypatch.setattr(main_module, "NotionSyncAgent", FakeNotionSyncAgent)
    monkeypatch.setattr(
        main_module,
        "_sync_run_record",
        lambda notion_service, run_record: None,
    )
    monkeypatch.setattr(main_module.settings, "SALES_ENGINE_RUN_MODE", run_mode)
    monkeypatch.setattr(main_module.settings, "SALES_ENGINE_TRIGGERED_BY", "manual")


def test_main_shadow_mode_skips_outreach_review_sync(monkeypatch) -> None:
    events: list[str] = []
    _patch_main_dependencies(monkeypatch, run_mode="shadow", events=events)

    main_module.main()

    assert events == ["feedback"]


def test_main_live_mode_syncs_outreach_review_before_feedback_collection(
    monkeypatch,
) -> None:
    events: list[str] = []
    _patch_main_dependencies(monkeypatch, run_mode="live", events=events)

    main_module.main()

    assert events == ["sync", "feedback"]
