from typing import Any, List

from app.models.account import Account
from app.models.buyer import Buyer
from app.models.deal_support_package import DealSupportPackage
from app.models.execution_task import ExecutionTask
from app.models.lead import Lead
from app.models.pipeline_record import PipelineRecord
from app.models.solution_recommendation import SolutionRecommendation
from app.services.notion_service import NotionService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class NotionSyncAgent:
    def __init__(self, notion_service: NotionService | None = None) -> None:
        self.notion_service = notion_service or NotionService()

    def is_configured(self) -> bool:
        return self.notion_service.is_configured()

    def sync_operating_views(
        self,
        leads: List[Lead],
        pipeline_records: List[PipelineRecord],
        solution_recommendations: List[SolutionRecommendation],
        execution_tasks: List[ExecutionTask],
        deal_support_packages: List[DealSupportPackage],
        accounts: List[Account] | None = None,
        buyers: List[Buyer] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        empty_result = {
            "accounts": [],
            "buyers": [],
            "leads": [],
            "pipeline_records": [],
            "solution_recommendations": [],
            "execution_tasks": [],
            "deal_support_packages": [],
        }
        if not self.notion_service.is_configured():
            logger.info("Notion is not configured. Skipping operating-view sync.")
            return empty_result

        account_list = accounts or []
        buyer_list = buyers or []
        logger.info("Syncing operating views to Notion.")
        sync_result = {
            "accounts": (
                self.notion_service.upsert_account_pages(account_list)
                if self.notion_service.is_accounts_configured()
                else []
            ),
            "buyers": (
                self.notion_service.upsert_buyer_pages(buyer_list)
                if self.notion_service.is_buyers_configured()
                else []
            ),
            "leads": self.notion_service.upsert_lead_pages(leads),
            "pipeline_records": self.notion_service.upsert_pipeline_pages(
                pipeline_records
            ),
            "solution_recommendations": self.notion_service.upsert_solution_pages(
                solution_recommendations
            ),
            "execution_tasks": self.notion_service.upsert_execution_task_pages(
                execution_tasks
            ),
            "deal_support_packages": self.notion_service.upsert_deal_support_pages(
                deal_support_packages
            ),
        }
        logger.info("Notion operating-view sync completed.")
        return sync_result
