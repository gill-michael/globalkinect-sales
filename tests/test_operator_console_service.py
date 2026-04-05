from app.models.lead_discovery_record import LeadDiscoveryRecord
from app.models.lead_intake_record import LeadIntakeRecord
from app.models.operator_console import (
    OperatorDashboardSnapshot,
    OutreachQueueRecord,
    SalesEngineRunRecord,
)
from app.services.operator_console_service import OperatorConsoleService


class FakeNotionService:
    def __init__(self) -> None:
        self.updated: list[tuple[str, str]] = []

    def is_configured(self) -> bool:
        return True

    def is_discovery_configured(self) -> bool:
        return True

    def is_intake_configured(self) -> bool:
        return True

    def is_outreach_queue_configured(self) -> bool:
        return True

    def is_run_logging_configured(self) -> bool:
        return True

    def get_operator_dashboard_snapshot(self) -> OperatorDashboardSnapshot:
        return OperatorDashboardSnapshot(
            discovery_records=[
                LeadDiscoveryRecord(page_id="d1", company_name="North Star Labs", status="Ready")
            ],
            intake_records=[
                LeadIntakeRecord(page_id="i1", company_name="North Star Labs", status="Ready")
            ],
            outreach_queue_records=[
                OutreachQueueRecord(
                    page_id="q1",
                    lead_reference="North Star Labs|Mina Yusuf|Saudi Arabia|direct_payroll",
                    status="Ready to send",
                )
            ],
            run_records=[
                SalesEngineRunRecord(
                    page_id="r1",
                    run_marker="RUN_1",
                    status="Completed",
                    started_at="2026-03-23T09:00:00+00:00",
                )
            ],
        )

    def list_lead_discovery_records(self, limit: int = 100):
        return self.get_operator_dashboard_snapshot().discovery_records

    def list_lead_intake_records(self, limit: int = 100):
        return self.get_operator_dashboard_snapshot().intake_records

    def list_outreach_queue_records(self, limit: int = 100):
        return self.get_operator_dashboard_snapshot().outreach_queue_records

    def list_sales_engine_runs(self, limit: int = 50):
        return self.get_operator_dashboard_snapshot().run_records

    def update_outreach_queue_status(self, lead_reference: str, status: str) -> None:
        self.updated.append((lead_reference, status))


def test_dashboard_snapshot_proxies_notion_snapshot() -> None:
    service = OperatorConsoleService(notion_service=FakeNotionService())

    snapshot = service.dashboard_snapshot()

    assert len(snapshot.discovery_records) == 1
    assert len(snapshot.intake_records) == 1
    assert len(snapshot.outreach_queue_records) == 1
    assert len(snapshot.run_records) == 1


def test_update_outreach_queue_status_delegates_to_notion_service() -> None:
    notion_service = FakeNotionService()
    service = OperatorConsoleService(notion_service=notion_service)

    service.update_outreach_queue_status(
        "North Star Labs|Mina Yusuf|Saudi Arabia|direct_payroll",
        "Approved",
    )

    assert notion_service.updated == [
        ("North Star Labs|Mina Yusuf|Saudi Arabia|direct_payroll", "Approved")
    ]
