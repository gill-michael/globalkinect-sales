from app.models.operator_console import OperatorDashboardSnapshot
from app.services.notion_service import NotionService


class OperatorConsoleService:
    def __init__(self, notion_service: NotionService | None = None) -> None:
        self.notion_service = notion_service or NotionService()

    def is_configured(self) -> bool:
        return self.notion_service.is_configured()

    def configuration_error(self) -> str:
        return getattr(
            self.notion_service,
            "_configuration_error",
            "Notion service is not configured.",
        )

    def dashboard_snapshot(self) -> OperatorDashboardSnapshot:
        return self.notion_service.get_operator_dashboard_snapshot()

    def list_discovery_records(self, limit: int = 100):
        if not self.notion_service.is_discovery_configured():
            return []
        return self.notion_service.list_lead_discovery_records(limit=limit)

    def list_intake_records(self, limit: int = 100):
        if not self.notion_service.is_intake_configured():
            return []
        return self.notion_service.list_lead_intake_records(limit=limit)

    def list_outreach_queue_records(self, limit: int = 100):
        if not self.notion_service.is_outreach_queue_configured():
            return []
        return self.notion_service.list_outreach_queue_records(limit=limit)

    def list_sales_engine_runs(self, limit: int = 50):
        if not self.notion_service.is_run_logging_configured():
            return []
        return self.notion_service.list_sales_engine_runs(limit=limit)

    def list_pipeline_records(self, limit: int = 200):
        if not self.notion_service.is_configured():
            return []
        return self.notion_service.list_pipeline_records(limit=limit)

    def update_outreach_queue_status(
        self,
        lead_reference: str,
        status: str,
    ) -> None:
        self.notion_service.update_outreach_queue_status(lead_reference, status)
