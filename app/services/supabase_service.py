from typing import Any, Iterable, List

from app.models.deal_support_package import DealSupportPackage
from app.models.execution_task import ExecutionTask
from app.models.lead import Lead
from app.models.outreach_message import OutreachMessage
from app.models.pipeline_record import PipelineRecord
from app.models.solution_recommendation import SolutionRecommendation
from app.services.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

try:
    from supabase import Client, create_client
except ImportError:
    Client = None
    create_client = None


class SupabaseService:
    TABLE_LEADS = "leads"
    TABLE_OUTREACH_MESSAGES = "outreach_messages"
    TABLE_PIPELINE_RECORDS = "pipeline_records"
    TABLE_SOLUTION_RECOMMENDATIONS = "solution_recommendations"
    TABLE_DEAL_SUPPORT_PACKAGES = "deal_support_packages"
    TABLE_EXECUTION_TASKS = "execution_tasks"
    TABLE_RESPONSE_EVENTS = "response_events"
    TABLE_FIELD_EXCLUSIONS: dict[str, set[str]] = {
        TABLE_LEADS: {
            "feedback_summary",
            "lane_label",
            "buyer_confidence",
            "account_fit_summary",
            "company_canonical",
        },
        TABLE_PIPELINE_RECORDS: {
            "company_canonical",
        },
        TABLE_EXECUTION_TASKS: {
            "company_name",
            "company_canonical",
        },
    }

    def __init__(self) -> None:
        self.url = settings.SUPABASE_URL
        self.key = settings.SUPABASE_PUBLISHABLE_KEY
        self.client = None
        self._configuration_error = "Supabase service is not configured."

        if create_client is None:
            self._configuration_error = (
                "Supabase package is not installed. Supabase service is unavailable."
            )
            logger.warning(self._configuration_error)
            return

        if not self.url or not self.key:
            self._configuration_error = (
                "Supabase credentials are missing. Persistence is disabled."
            )
            logger.info(self._configuration_error)
            return

        self.client = create_client(self.url, self.key)
        logger.info("Supabase service configured.")

    def is_configured(self) -> bool:
        return self.client is not None

    def insert_leads(self, leads: list[Lead]) -> Any:
        return self._insert_models(self.TABLE_LEADS, leads)

    def insert_outreach_messages(self, messages: list[OutreachMessage]) -> Any:
        return self._insert_models(self.TABLE_OUTREACH_MESSAGES, messages)

    def insert_pipeline_records(self, records: list[PipelineRecord]) -> Any:
        logger.info("Preparing pipeline records for insert with solution-aligned fields when present.")
        return self._insert_models(self.TABLE_PIPELINE_RECORDS, records)

    def update_pipeline_record(self, record: PipelineRecord) -> Any:
        self._ensure_configured()
        payload = self._model_to_dict(self.TABLE_PIPELINE_RECORDS, record)
        logger.info(f"Updating pipeline record for {record.lead_reference}.")
        return (
            self.client.table(self.TABLE_PIPELINE_RECORDS)
            .update(payload)
            .eq("lead_reference", record.lead_reference)
            .execute()
        )

    def upsert_pipeline_records(self, records: list[PipelineRecord]) -> Any:
        return self._upsert_models(
            self.TABLE_PIPELINE_RECORDS,
            records,
            on_conflict="lead_reference",
        )

    def insert_solution_recommendations(
        self,
        recommendations: list[SolutionRecommendation],
    ) -> Any:
        return self._insert_models(self.TABLE_SOLUTION_RECOMMENDATIONS, recommendations)

    def upsert_solution_recommendations(
        self,
        recommendations: list[SolutionRecommendation],
    ) -> Any:
        return self._upsert_models(
            self.TABLE_SOLUTION_RECOMMENDATIONS,
            recommendations,
            on_conflict="lead_reference",
        )

    def insert_deal_support_packages(
        self,
        packages: list[DealSupportPackage],
    ) -> Any:
        return self._insert_models(self.TABLE_DEAL_SUPPORT_PACKAGES, packages)

    def insert_execution_tasks(
        self,
        tasks: list[ExecutionTask],
    ) -> Any:
        return self._insert_models(self.TABLE_EXECUTION_TASKS, tasks)

    def insert_response_events(self, events: list[dict]) -> None:
        if not events:
            logger.info(f"No records to insert into {self.TABLE_RESPONSE_EVENTS}.")
            return
        self._ensure_configured()
        logger.info(
            f"Inserting {len(events)} records into {self.TABLE_RESPONSE_EVENTS}."
        )
        self.client.table(self.TABLE_RESPONSE_EVENTS).insert(events).execute()

    def fetch_leads(self, limit: int = 20) -> Any:
        return self._fetch_rows(self.TABLE_LEADS, limit)

    def fetch_pipeline_records(self, limit: int = 20) -> Any:
        return self._fetch_rows(self.TABLE_PIPELINE_RECORDS, limit)

    def fetch_pipeline_record_by_lead_reference(
        self,
        lead_reference: str,
    ) -> PipelineRecord | None:
        self._ensure_configured()
        logger.info("Fetching pipeline record for %s.", lead_reference)
        response = (
            self.client.table(self.TABLE_PIPELINE_RECORDS)
            .select("*")
            .eq("lead_reference", lead_reference)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", response) or []
        if not rows:
            return None
        return PipelineRecord.model_validate(rows[0])

    def fetch_execution_tasks(self, limit: int = 20) -> Any:
        return self._fetch_rows(self.TABLE_EXECUTION_TASKS, limit)

    def fetch_deal_support_package_by_lead_reference(
        self,
        lead_reference: str,
    ) -> DealSupportPackage | None:
        self._ensure_configured()
        response = (
            self.client.table(self.TABLE_DEAL_SUPPORT_PACKAGES)
            .select("*")
            .eq("lead_reference", lead_reference)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", response) or []
        if not rows:
            return None
        return DealSupportPackage.model_validate(rows[0])

    def fetch_solution_recommendation_by_lead_reference(
        self,
        lead_reference: str,
    ) -> SolutionRecommendation | None:
        self._ensure_configured()
        response = (
            self.client.table(self.TABLE_SOLUTION_RECOMMENDATIONS)
            .select("*")
            .eq("lead_reference", lead_reference)
            .limit(1)
            .execute()
        )
        rows = getattr(response, "data", response) or []
        if not rows:
            return None
        return SolutionRecommendation.model_validate(rows[0])

    def _fetch_rows(self, table_name: str, limit: int) -> Any:
        self._ensure_configured()
        logger.info(f"Fetching up to {limit} rows from {table_name}.")
        response = self.client.table(table_name).select("*").limit(limit).execute()
        return getattr(response, "data", response)

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise RuntimeError(self._configuration_error)

    def _model_to_dict(self, table_name: str, model: Any) -> dict[str, Any]:
        excluded_fields = self.TABLE_FIELD_EXCLUSIONS.get(table_name, set())
        if not excluded_fields:
            return model.model_dump()
        return model.model_dump(exclude=excluded_fields)

    def _model_list_to_dicts(
        self,
        table_name: str,
        models: Iterable[Any],
    ) -> List[dict[str, Any]]:
        return [self._model_to_dict(table_name, model) for model in models]

    def _insert_models(self, table_name: str, models: Iterable[Any]) -> Any:
        self._ensure_configured()

        payload = self._model_list_to_dicts(table_name, models)
        if not payload:
            logger.info(f"No records to insert into {table_name}.")
            return []

        logger.info(f"Inserting {len(payload)} records into {table_name}.")
        return self.client.table(table_name).insert(payload).execute()

    def _upsert_models(
        self,
        table_name: str,
        models: Iterable[Any],
        *,
        on_conflict: str,
    ) -> Any:
        self._ensure_configured()

        payload = self._model_list_to_dicts(table_name, models)
        if not payload:
            logger.info(f"No records to upsert into {table_name}.")
            return []

        logger.info(
            "Upserting %s records into %s on conflict %s.",
            len(payload),
            table_name,
            on_conflict,
        )
        return (
            self.client.table(table_name)
            .upsert(payload, on_conflict=on_conflict)
            .execute()
        )
