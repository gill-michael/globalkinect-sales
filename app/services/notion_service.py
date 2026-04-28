import re
from typing import Any, Callable, Iterable

from app.models.account import Account
from app.models.buyer import Buyer
from app.models.deal_support_package import DealSupportPackage
from app.models.discovery_candidate import DiscoveryCandidate
from app.models.discovery_qualification import DiscoveryQualification
from app.models.execution_task import ExecutionTask
from app.models.lead import Lead
from app.models.lead_discovery_record import LeadDiscoveryRecord
from app.models.lead_feedback_signal import LeadFeedbackSignal
from app.models.lead_intake_record import LeadIntakeRecord
from app.models.operator_console import (
    OperatorDashboardSnapshot,
    OutreachQueueRecord,
    SalesEngineRunRecord,
)
from app.models.opportunity_record import OpportunityRecord
from app.models.outreach_queue_item import OutreachQueueItem
from app.models.pipeline_record import PipelineRecord
from app.models.sales_engine_run import SalesEngineRun
from app.models.solution_recommendation import SolutionRecommendation
from app.services.config import settings
from app.utils.identity import (
    company_name_from_lead_reference,
    contact_name_from_lead_reference,
    normalize_company_canonical,
)
from app.utils.time import utc_now_iso
from app.utils.logger import get_logger
from app.utils.target_markets import country_label

logger = get_logger(__name__)

try:
    import httpx
except ImportError:
    httpx = None


class NotionService:
    API_BASE_URL = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"
    PLACEHOLDER_VALUES = {
        "",
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "unknown",
        "unknown contact",
        "unknown role",
        "not provided",
        "not available",
        "tbd",
    }

    DATABASE_LEADS = "leads"
    DATABASE_DISCOVERY = "discovery"
    DATABASE_INTAKE = "intake"
    DATABASE_OUTREACH_QUEUE = "outreach_queue"
    DATABASE_PIPELINE = "pipeline"
    DATABASE_RUNS = "runs"
    DATABASE_SOLUTIONS = "solutions"
    DATABASE_TASKS = "tasks"
    DATABASE_DEAL_SUPPORT = "deal_support"
    DATABASE_ACCOUNTS = "accounts"
    DATABASE_BUYERS = "buyers"
    OUTREACH_QUEUE_PRESERVE_STATUSES = {"approved", "sent", "hold"}
    OUTREACH_QUEUE_REGENERATE_STATUS = "regenerate"

    OPPORTUNITY_ICP_SHORT_CODE_MAP: dict[str, str | None] = {
        "a1": "A1 - Frustrated GCC Operator",
        "a2": "A2 - GCC SME",
        "a3": "A3 - Scaling GCC Business",
        "b1": None,
        "b2": "B2 - UK Domestic SME",
        "b3": "B3 - International MENA Expander",
        "b4": "B4 - European-MENA Bridge",
        "b5": None,
    }
    OPPORTUNITY_ICP_SELECT_VALUES: set[str] = {
        "A1 - Frustrated GCC Operator",
        "A2 - GCC SME",
        "A3 - Scaling GCC Business",
        "B2 - UK Domestic SME",
        "B3 - International MENA Expander",
        "B4 - European-MENA Bridge",
        "Unknown",
    }
    OPPORTUNITY_EXCLUDED_STATUSES: tuple[str, ...] = (
        "Closed Won",
        "Closed Lost",
        "On Hold",
    )

    def __init__(self, client: Any | None = None) -> None:
        self.api_key = settings.NOTION_API_KEY
        self.discovery_database_id = settings.NOTION_DISCOVERY_DATABASE_ID
        self.intake_database_id = settings.NOTION_INTAKE_DATABASE_ID
        self.outreach_queue_database_id = settings.NOTION_OUTREACH_QUEUE_DATABASE_ID
        self.opportunities_database_id = settings.NOTION_OPPORTUNITIES_DATABASE_ID
        self.runs_database_id = settings.NOTION_RUNS_DATABASE_ID
        self.accounts_database_id = settings.NOTION_ACCOUNTS_DATABASE_ID
        self.buyers_database_id = settings.NOTION_BUYERS_DATABASE_ID
        self.database_ids = {
            self.DATABASE_LEADS: settings.NOTION_LEADS_DATABASE_ID,
            self.DATABASE_PIPELINE: settings.NOTION_PIPELINE_DATABASE_ID,
            self.DATABASE_SOLUTIONS: settings.NOTION_SOLUTIONS_DATABASE_ID,
            self.DATABASE_TASKS: settings.NOTION_TASKS_DATABASE_ID,
            self.DATABASE_DEAL_SUPPORT: settings.NOTION_DEAL_SUPPORT_DATABASE_ID,
        }
        self.title_properties = {
            self.DATABASE_DISCOVERY: "Company",
            self.DATABASE_INTAKE: "Company",
            self.DATABASE_LEADS: "Lead Reference",
            self.DATABASE_OUTREACH_QUEUE: "Lead Reference",
            self.DATABASE_PIPELINE: "Lead Reference",
            self.DATABASE_RUNS: "Run Marker",
            self.DATABASE_SOLUTIONS: "Lead Reference",
            self.DATABASE_TASKS: "Task",
            self.DATABASE_DEAL_SUPPORT: "Lead Reference",
            self.DATABASE_ACCOUNTS: "Account",
            self.DATABASE_BUYERS: "Buyer",
        }
        self.client = None
        self._database_schema_cache: dict[str, dict[str, Any]] = {}
        self._configuration_error = "Notion service is not configured."

        if not self.api_key:
            self._configuration_error = (
                "Notion API key is missing. Operating sync is disabled."
            )
            logger.info(self._configuration_error)
            return

        missing_database_keys = [
            database_key
            for database_key, database_id in self.database_ids.items()
            if not database_id
        ]
        if missing_database_keys:
            missing_labels = ", ".join(sorted(missing_database_keys))
            self._configuration_error = (
                "Notion database IDs are missing for: "
                f"{missing_labels}. Operating sync is disabled."
            )
            logger.info(self._configuration_error)
            return

        if client is not None:
            self.client = client
            logger.info("Notion service configured.")
            return

        if httpx is None:
            self._configuration_error = (
                "httpx is not installed. Notion service is unavailable."
            )
            logger.warning(self._configuration_error)
            return

        self.client = httpx.Client(
            base_url=self.API_BASE_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Notion-Version": self.NOTION_VERSION,
            },
            timeout=30.0,
        )
        logger.info("Notion service configured.")

    def is_configured(self) -> bool:
        return self.client is not None

    def is_discovery_configured(self) -> bool:
        return self.is_configured() and bool(self.discovery_database_id)

    def is_intake_configured(self) -> bool:
        return self.is_configured() and bool(self.intake_database_id)

    def is_outreach_queue_configured(self) -> bool:
        return self.is_configured() and bool(self.outreach_queue_database_id)

    def is_opportunities_configured(self) -> bool:
        return self.is_configured() and bool(self.opportunities_database_id)

    def is_run_logging_configured(self) -> bool:
        return self.is_configured() and bool(self.runs_database_id)

    def is_accounts_configured(self) -> bool:
        return self.is_configured() and bool(self.accounts_database_id)

    def is_buyers_configured(self) -> bool:
        return self.is_configured() and bool(self.buyers_database_id)

    def fetch_lead_intake_records(self, limit: int = 20) -> list[LeadIntakeRecord]:
        self._ensure_intake_configured()

        response = self.client.post(
            f"/databases/{self.intake_database_id}/query",
            json={
                "page_size": min(max(limit * 3, 20), 100),
                "sorts": [
                    {
                        "timestamp": "last_edited_time",
                        "direction": "descending",
                    }
                ],
            },
        )
        payload = self._parse_response(response)

        records: list[LeadIntakeRecord] = []
        for page in payload.get("results", []):
            record = self._build_lead_intake_record(page)
            if record is None or not self._should_process_intake_status(record.status):
                continue
            records.append(record)
        records.sort(key=self._intake_priority_key)
        records = records[:limit]

        logger.info(f"Fetched {len(records)} lead intake records from Notion.")
        return records

    def fetch_lead_discovery_records(
        self,
        limit: int = 20,
    ) -> list[LeadDiscoveryRecord]:
        self._ensure_discovery_configured()

        response = self.client.post(
            f"/databases/{self.discovery_database_id}/query",
            json={
                "page_size": min(max(limit * 3, 20), 100),
                "sorts": [
                    {
                        "timestamp": "last_edited_time",
                        "direction": "descending",
                    }
                ],
            },
        )
        payload = self._parse_response(response)

        records: list[LeadDiscoveryRecord] = []
        for page in payload.get("results", []):
            record = self._build_lead_discovery_record(page)
            if record is None or not self._should_process_discovery_status(record.status):
                continue
            records.append(record)
        records.sort(key=self._discovery_priority_key)
        records = records[:limit]

        logger.info(f"Fetched {len(records)} lead discovery records from Notion.")
        return records

    def fetch_outreach_queue_feedback_signals(
        self,
        limit: int = 200,
    ) -> list[LeadFeedbackSignal]:
        self._ensure_outreach_queue_configured()
        response = self.client.post(
            f"/databases/{self.outreach_queue_database_id}/query",
            json={
                "page_size": min(max(limit, 20), 100),
                "sorts": [
                    {
                        "timestamp": "last_edited_time",
                        "direction": "descending",
                    }
                ],
            },
        )
        payload = self._parse_response(response)
        signals: list[LeadFeedbackSignal] = []
        for page in payload.get("results", []):
            signal = LeadFeedbackSignal(
                lead_reference=self._property_text(page, "Lead Reference"),
                company_name=self._property_text(page, "Company"),
                queue_status=self._property_option(page, "Status"),
            )
            if signal.lead_reference or signal.company_name:
                signals.append(signal)
            if len(signals) >= limit:
                break

        logger.info(f"Fetched {len(signals)} outreach queue feedback signals from Notion.")
        return signals

    def fetch_outreach_queue_replied_records(
        self,
        limit: int = 50,
    ) -> list[tuple[OutreachQueueRecord, str]]:
        """Return queue records currently in the 'replied' status along with
        the text of the operator-pasted `Reply` property. Records with empty
        Reply are skipped."""
        self._ensure_outreach_queue_configured()
        response = self.client.post(
            f"/databases/{self.outreach_queue_database_id}/query",
            json={
                "page_size": min(max(limit, 20), 100),
                "filter": {
                    "property": "Status",
                    "select": {"equals": "replied"},
                },
                "sorts": [
                    {
                        "timestamp": "last_edited_time",
                        "direction": "descending",
                    }
                ],
            },
        )
        payload = self._parse_response(response)
        out: list[tuple[OutreachQueueRecord, str]] = []
        for page in payload.get("results", []):
            record = self._build_outreach_queue_record(page)
            if record is None:
                continue
            reply_text = self._property_text(page, "Reply")
            if not reply_text:
                continue
            out.append((record, reply_text))
            if len(out) >= limit:
                break
        logger.info("Fetched %s replied outreach queue records from Notion.", len(out))
        return out

    def ensure_outreach_queue_reply_property(self) -> bool:
        """Add a `Reply` rich_text property to the Outreach Queue database if
        it isn't already present. Returns True if the property now exists."""
        self._ensure_outreach_queue_configured()
        schema = self._get_database_schema(self.outreach_queue_database_id)
        if "Reply" in schema:
            return True
        response = self.client.patch(
            f"/databases/{self.outreach_queue_database_id}",
            json={"properties": {"Reply": {"rich_text": {}}}},
        )
        self._parse_response(response)
        self._database_schema_cache.pop(self.outreach_queue_database_id, None)
        logger.info("Added Reply property to Outreach Queue database.")
        return True

    def update_outreach_queue_status_and_notes(
        self,
        page_id: str,
        status: str,
        notes: str | None,
    ) -> dict[str, Any]:
        """Lightweight update used by the response handler agent."""
        self._ensure_outreach_queue_configured()
        database_id = self.outreach_queue_database_id
        properties: dict[str, Any] = {}
        status_property = self._database_option_property(database_id, "Status", status)
        if status_property is not None:
            properties["Status"] = status_property
        if notes is not None:
            properties["Notes"] = self._rich_text(notes)
        if not properties:
            return {}
        return self._update_page(page_id, properties)

    def fetch_pipeline_feedback_signals(
        self,
        limit: int = 200,
    ) -> list[LeadFeedbackSignal]:
        self._ensure_configured()
        response = self.client.post(
            f"/databases/{self.database_ids[self.DATABASE_PIPELINE]}/query",
            json={
                "page_size": min(max(limit, 20), 100),
                "sorts": [
                    {
                        "timestamp": "last_edited_time",
                        "direction": "descending",
                    }
                ],
            },
        )
        payload = self._parse_response(response)
        signals: list[LeadFeedbackSignal] = []
        for page in payload.get("results", []):
            signal = LeadFeedbackSignal(
                lead_reference=self._property_text(page, "Lead Reference"),
                company_name=self._property_text(page, "Company"),
                pipeline_stage=self._property_option(page, "Stage"),
                outreach_status=self._property_option(page, "Outreach Status"),
            )
            if signal.lead_reference or signal.company_name:
                signals.append(signal)
            if len(signals) >= limit:
                break

        logger.info(f"Fetched {len(signals)} pipeline feedback signals from Notion.")
        return signals

    def list_lead_discovery_records(
        self,
        limit: int = 100,
    ) -> list[LeadDiscoveryRecord]:
        self._ensure_discovery_configured()
        payload = self._query_database(
            self.discovery_database_id,
            limit=limit,
            sort_direction="descending",
        )
        records: list[LeadDiscoveryRecord] = []
        for page in payload.get("results", []):
            record = self._build_lead_discovery_record(page)
            if record is not None:
                records.append(record)
        return records

    def list_lead_intake_records(
        self,
        limit: int = 100,
    ) -> list[LeadIntakeRecord]:
        self._ensure_intake_configured()
        payload = self._query_database(
            self.intake_database_id,
            limit=limit,
            sort_direction="descending",
        )
        records: list[LeadIntakeRecord] = []
        for page in payload.get("results", []):
            record = self._build_lead_intake_record(page)
            if record is not None:
                records.append(record)
        return records

    def list_execution_tasks(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return Execution Tasks rows as plain dicts shaped for the
        operator console's Tasks view. Status is one of `open`,
        `completed`, `cancelled`; due_in_days is a number; the title
        property is `Task` (built from task_type + lead_reference)."""
        self._ensure_configured()
        payload = self._query_database(
            self.database_ids[self.DATABASE_TASKS],
            limit=limit,
            sort_direction="descending",
        )
        records: list[dict[str, Any]] = []
        for page in payload.get("results", []):
            records.append({
                "page_id": page["id"],
                "page_url": f"https://notion.so/{page['id'].replace('-', '')}",
                "last_edited_time": page.get("last_edited_time"),
                "task_title": self._property_text(page, "Task"),
                "lead_reference": self._property_text(page, "Lead Reference"),
                "company_name": self._property_text(page, "Company"),
                "task_type": self._property_option(page, "Task Type"),
                "description": self._property_text(page, "Description"),
                "priority": self._property_option(page, "Priority"),
                "due_in_days": self._property_number(page, "Due In Days"),
                "status": self._property_option(page, "Status"),
            })
        return records

    def list_pipeline_records(self, limit: int = 200) -> list[dict[str, Any]]:
        """Return Pipeline rows as plain dicts shaped for audit/console use.

        Not every `PipelineRecord` model field is written to Notion (the
        timestamps live in Supabase only), so this method intentionally
        returns dicts with the subset the Notion DB actually carries plus
        the page's `last_edited_time` as a "last touched" signal.

        `lead_type` is parsed from the lead_reference title suffix
        (`Company|Contact|Country|lead_type`).
        """
        self._ensure_configured()
        payload = self._query_database(
            self.database_ids[self.DATABASE_PIPELINE],
            limit=limit,
            sort_direction="descending",
        )
        records: list[dict[str, Any]] = []
        for page in payload.get("results", []):
            lead_reference = self._property_text(page, "Lead Reference")
            if not lead_reference:
                continue
            lead_type: str | None = None
            parts = lead_reference.split("|")
            if len(parts) >= 4:
                lead_type = parts[-1].strip() or None
            records.append({
                "page_id": page["id"],
                "page_url": f"https://notion.so/{page['id'].replace('-', '')}",
                "last_edited_time": page.get("last_edited_time"),
                "lead_reference": lead_reference,
                "lead_type": lead_type,
                "company_name": self._property_text(page, "Company"),
                "contact_name": (
                    parts[1].strip() if len(parts) >= 2 else None
                ),
                "stage": self._property_option(page, "Stage"),
                "outreach_status": self._property_option(page, "Outreach Status"),
                "next_action": self._property_text(page, "Next Action"),
                "priority": self._property_option(page, "Priority"),
                "sales_motion": self._property_option(page, "Sales Motion"),
                "primary_module": self._property_option(page, "Primary Module"),
                "bundle_label": self._property_option(page, "Bundle Label"),
                "last_updated": self._property_date(page, "Last Updated"),
            })
        return records

    def list_outreach_queue_records(
        self,
        limit: int = 100,
    ) -> list[OutreachQueueRecord]:
        self._ensure_outreach_queue_configured()
        payload = self._query_database(
            self.outreach_queue_database_id,
            limit=limit,
            sort_direction="descending",
        )
        records: list[OutreachQueueRecord] = []
        for page in payload.get("results", []):
            record = self._build_outreach_queue_record(page)
            if record is not None:
                records.append(record)
        return records

    def update_outreach_queue_record_status(
        self,
        page_id: str,
        status: str,
    ) -> dict[str, Any]:
        """Set the Status field on a single Outreach Queue record."""
        self._ensure_outreach_queue_configured()
        status_property = self._database_option_property(
            self.outreach_queue_database_id, "Status", status
        )
        if status_property is None:
            raise RuntimeError(
                f"Could not set Outreach Queue status to '{status}'"
            )
        return self._update_page(page_id, {"Status": status_property})

    def update_lead_intake_record_status(
        self,
        page_id: str,
        status: str,
    ) -> dict[str, Any]:
        """Set the Status field on a single Lead Intake record."""
        self._ensure_intake_configured()
        status_property = self._database_option_property(
            self.intake_database_id, "Status", status
        )
        if status_property is None:
            raise RuntimeError(
                f"Could not set Lead Intake status to '{status}'"
            )
        return self._update_page(page_id, {"Status": status_property})

    def append_sales_engine_run_note(
        self,
        page_id: str,
        note: str,
    ) -> dict[str, Any]:
        """Append text to the Notes field on a Sales Engine Run record."""
        self._ensure_run_logging_configured()
        if not note or not note.strip():
            raise RuntimeError("Note text is required")
        response = self.client.get(f"/pages/{page_id}")
        payload = self._parse_response(response)
        existing = self._property_text(payload, "Notes") or ""
        combined = f"{existing}\n{note}" if existing else note
        return self._update_page(page_id, {"Notes": self._rich_text(combined)})

    def list_sales_engine_runs(
        self,
        limit: int = 50,
    ) -> list[SalesEngineRunRecord]:
        self._ensure_run_logging_configured()
        payload = self._query_database(
            self.runs_database_id,
            limit=limit,
            sort_direction="descending",
        )
        records: list[SalesEngineRunRecord] = []
        for page in payload.get("results", []):
            record = self._build_sales_engine_run_record(page)
            if record is not None:
                records.append(record)
        return records

    def update_outreach_queue_status(
        self,
        lead_reference: str,
        status: str,
    ) -> dict[str, Any]:
        self._ensure_outreach_queue_configured()
        existing_page = self._find_page_by_title(
            database_id=self.outreach_queue_database_id,
            title_property=self.title_properties[self.DATABASE_OUTREACH_QUEUE],
            title_value=lead_reference,
        )
        if existing_page is None:
            raise ValueError(f"Outreach Queue row not found for {lead_reference}.")

        properties = self._compact_properties(
            {
                "Status": self._database_option_property(
                    self.outreach_queue_database_id,
                    "Status",
                    status,
                ),
            }
        )
        return self._update_page(existing_page["id"], properties)

    def get_operator_dashboard_snapshot(
        self,
        *,
        discovery_limit: int = 50,
        intake_limit: int = 50,
        outreach_limit: int = 50,
        runs_limit: int = 25,
    ) -> OperatorDashboardSnapshot:
        snapshot = OperatorDashboardSnapshot()
        if not self.is_configured():
            return snapshot

        if self.is_discovery_configured():
            snapshot.discovery_records = self.list_lead_discovery_records(
                limit=discovery_limit,
            )
        if self.is_intake_configured():
            snapshot.intake_records = self.list_lead_intake_records(
                limit=intake_limit,
            )
        if self.is_outreach_queue_configured():
            snapshot.outreach_queue_records = self.list_outreach_queue_records(
                limit=outreach_limit,
            )
        if self.is_run_logging_configured():
            snapshot.run_records = self.list_sales_engine_runs(limit=runs_limit)

        return snapshot

    def sync_discovery_candidate_page(
        self,
        candidate: DiscoveryCandidate,
    ) -> str:
        self._ensure_discovery_configured()
        existing_page = self._find_discovery_page(candidate)
        if existing_page is not None and self._same_discovery_signal(existing_page, candidate):
            return "skipped"

        properties = self._build_discovery_candidate_properties(candidate)
        if existing_page is None:
            self._create_page(self.discovery_database_id, properties)
            return "created"

        self._update_page(existing_page["id"], properties)
        return "updated"

    def mark_lead_intake_record_processed(
        self,
        intake_record: LeadIntakeRecord,
        lead: Lead,
    ) -> dict[str, Any]:
        self._ensure_intake_configured()
        properties = self._build_intake_processed_properties(lead)
        if not properties:
            logger.info(
                "No compatible intake tracking properties found. Skipping intake success update."
            )
            return {}
        return self._update_page(intake_record.page_id, properties)

    def mark_lead_intake_record_failed(
        self,
        intake_record: LeadIntakeRecord,
        error_message: str,
    ) -> dict[str, Any]:
        self._ensure_intake_configured()
        properties = self._build_intake_failed_properties(error_message)
        if not properties:
            logger.info(
                "No compatible intake tracking properties found. Skipping intake failure update."
            )
            return {}
        return self._update_page(intake_record.page_id, properties)

    def upsert_intake_page_from_discovery(
        self,
        lead: Lead,
        discovery_record: LeadDiscoveryRecord,
        qualification: DiscoveryQualification,
    ) -> dict[str, Any]:
        self._ensure_intake_configured()

        properties = self._build_intake_page_properties(
            lead,
            discovery_record,
            qualification,
        )
        existing_page = self._find_page_by_title(
            database_id=self.intake_database_id,
            title_property=self.title_properties[self.DATABASE_INTAKE],
            title_value=lead.company_name,
        )
        if existing_page is None:
            return self._create_page(self.intake_database_id, properties)
        return self._update_page(existing_page["id"], properties)

    def mark_lead_discovery_record_processed(
        self,
        discovery_record: LeadDiscoveryRecord,
        qualification: DiscoveryQualification,
    ) -> dict[str, Any]:
        self._ensure_discovery_configured()
        properties = self._build_discovery_processed_properties(qualification)
        if not properties:
            logger.info(
                "No compatible discovery tracking properties found. Skipping discovery success update."
            )
            return {}
        return self._update_page(discovery_record.page_id, properties)

    def mark_lead_discovery_record_failed(
        self,
        discovery_record: LeadDiscoveryRecord,
        error_message: str,
    ) -> dict[str, Any]:
        self._ensure_discovery_configured()
        properties = self._build_discovery_failed_properties(error_message)
        if not properties:
            logger.info(
                "No compatible discovery tracking properties found. Skipping discovery failure update."
            )
            return {}
        return self._update_page(discovery_record.page_id, properties)

    def upsert_lead_pages(self, leads: list[Lead]) -> list[dict[str, Any]]:
        return self._upsert_pages(
            items=leads,
            database_key=self.DATABASE_LEADS,
            title_builder=self._build_lead_reference,
            properties_builder=self._build_lead_properties,
            entity_label="lead pages",
        )

    def fetch_opportunity_pages(
        self,
        limit: int = 50,
        icp_filter: str | None = None,
    ) -> list[OpportunityRecord]:
        self._ensure_opportunities_configured()

        resolved_icp = self._resolve_opportunity_icp_filter(icp_filter)
        if icp_filter and resolved_icp is None:
            logger.info(
                "ICP filter '%s' has no matching select option in the Opportunities "
                "database. Returning an empty result set.",
                icp_filter,
            )
            return []

        query: dict[str, Any] = {
            "page_size": min(max(limit * 3, 20), 100),
            "sorts": [
                {
                    "timestamp": "last_edited_time",
                    "direction": "descending",
                }
            ],
            "filter": self._build_opportunity_filter(resolved_icp),
        }

        response = self.client.post(
            f"/databases/{self.opportunities_database_id}/query",
            json=query,
        )
        payload = self._parse_response(response)

        records: list[OpportunityRecord] = []
        for page in payload.get("results", []):
            record = self._build_opportunity_record(page)
            if record is None:
                continue
            if not self._is_opportunity_eligible(record):
                continue
            records.append(record)
            if len(records) >= limit:
                break

        logger.info(
            "Fetched %s eligible opportunity records from Notion "
            "(icp filter=%s, resolved=%s).",
            len(records),
            icp_filter or "all",
            resolved_icp or "none",
        )
        return records

    def _resolve_opportunity_icp_filter(
        self,
        icp_filter: str | None,
    ) -> str | None:
        if not icp_filter:
            return None
        cleaned = icp_filter.strip()
        if not cleaned:
            return None
        if cleaned in self.OPPORTUNITY_ICP_SELECT_VALUES:
            return cleaned
        short_key = cleaned.lower()
        if short_key in self.OPPORTUNITY_ICP_SHORT_CODE_MAP:
            return self.OPPORTUNITY_ICP_SHORT_CODE_MAP[short_key]
        return None

    def _build_opportunity_filter(
        self,
        resolved_icp: str | None,
    ) -> dict[str, Any]:
        status_exclusions = [
            {
                "property": "Status",
                "select": {"does_not_equal": status_value},
            }
            for status_value in self.OPPORTUNITY_EXCLUDED_STATUSES
        ]
        conditions: list[dict[str, Any]] = []
        if resolved_icp:
            conditions.append(
                {
                    "property": "ICP",
                    "select": {"equals": resolved_icp},
                }
            )
        conditions.extend(status_exclusions)
        if len(conditions) == 1:
            return conditions[0]
        return {"and": conditions}

    def update_opportunity_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        self._ensure_opportunities_configured()
        return self._update_page(page_id, properties)

    def _build_opportunity_record(
        self,
        page: dict[str, Any],
    ) -> OpportunityRecord | None:
        company_name = self._property_text(page, "Company")
        if not company_name:
            return None

        notes = self._property_text(page, "Notes")
        linkedin_url = self._extract_linkedin_url(notes)

        return OpportunityRecord(
            page_id=page["id"],
            company_name=company_name,
            contact_name=self._property_text(page, "Contact Name"),
            contact_role=self._property_text(page, "Contact Role"),
            contact_email=self._property_value(page, "Contact Email"),
            linkedin_url=linkedin_url,
            countries=self._property_multi_select(page, "Countries"),
            icp=self._property_option(page, "ICP"),
            source=self._property_option(page, "Source")
            or self._property_text(page, "Source"),
            headcount=self._property_option(page, "Headcount")
            or self._property_text(page, "Headcount")
            or self._stringify_number(self._property_number(page, "Headcount")),
            notes=notes,
            status=self._property_option(page, "Status"),
            next_action=self._property_option(page, "Next Action")
            or self._property_text(page, "Next Action"),
            next_action_date=self._property_date(page, "Next Action Date"),
            fit_score=self._property_number(page, "Fit Score"),
            modules_interested_in=self._property_multi_select(
                page, "Modules Interested In"
            ),
            operating_model_preference=self._property_option(
                page, "Operating Model Preference"
            )
            or self._property_text(page, "Operating Model Preference"),
            current_setup=self._property_text(page, "Current Setup"),
            main_problem=self._property_text(page, "Main Problem"),
            expanding_to=self._property_multi_select(page, "Expanding To"),
            estimated_headcount_at_start=self._property_number(
                page, "Estimated Headcount at Start"
            ),
            demo_date=self._property_date(page, "Demo Date"),
        )

    def _is_opportunity_eligible(self, record: OpportunityRecord) -> bool:
        status = (record.status or "").strip().lower()
        if status in {"closed won", "closed lost", "on hold"}:
            return False

        next_action = (record.next_action or "").strip().lower()
        if next_action and "generate outreach" not in next_action:
            return False

        has_email = bool((record.contact_email or "").strip())
        has_linkedin = bool((record.linkedin_url or "").strip())
        if not (has_email or has_linkedin):
            return False

        return True

    def _extract_linkedin_url(self, notes: str | None) -> str | None:
        if not notes:
            return None
        for line in notes.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            lower = stripped.lower()
            if lower.startswith("linkedin:"):
                value = stripped.split(":", 1)[1].strip()
                if value:
                    return value
        match = re.search(
            r"(?:https?://)?(?:[a-z]{2,3}\.)?linkedin\.com/[^\s\])]+",
            notes,
            re.IGNORECASE,
        )
        if not match:
            return None
        return match.group(0).rstrip(".,);]")

    def _stringify_number(self, value: int | None) -> str | None:
        if value is None:
            return None
        return str(value)

    def _property_multi_select(
        self,
        page: dict[str, Any],
        property_name: str,
    ) -> list[str]:
        property_value = page.get("properties", {}).get(property_name)
        if not property_value or property_value.get("type") != "multi_select":
            return []
        options = property_value.get("multi_select", []) or []
        return [option.get("name", "") for option in options if option.get("name")]

    def upsert_outreach_queue_pages(
        self,
        items: list[OutreachQueueItem],
    ) -> list[dict[str, Any]]:
        self._ensure_outreach_queue_configured()
        item_list = list(items)
        if not item_list:
            logger.info("No outreach queue pages to sync.")
            return []

        logger.info(f"Syncing {len(item_list)} outreach queue pages to Notion.")

        responses: list[dict[str, Any]] = []
        for item in item_list:
            existing_page = self._find_page_by_title(
                database_id=self.outreach_queue_database_id,
                title_property=self.title_properties[self.DATABASE_OUTREACH_QUEUE],
                title_value=item.lead_reference,
            )
            if existing_page is None:
                properties = self._build_outreach_queue_properties(item)
                responses.append(
                    self._create_page(self.outreach_queue_database_id, properties)
                )
                continue

            if self._should_preserve_outreach_queue_page(existing_page):
                logger.info(
                    "Preserving operator-managed outreach queue page for %s.",
                    item.lead_reference,
                )
                responses.append(existing_page)
                continue

            properties = self._build_outreach_queue_properties(item)
            responses.append(self._update_page(existing_page["id"], properties))

        return responses

    def upsert_pipeline_pages(
        self,
        records: list[PipelineRecord],
    ) -> list[dict[str, Any]]:
        return self._upsert_pages(
            items=records,
            database_key=self.DATABASE_PIPELINE,
            title_builder=lambda record: record.lead_reference,
            properties_builder=self._build_pipeline_properties,
            entity_label="pipeline pages",
        )

    def upsert_solution_pages(
        self,
        recommendations: list[SolutionRecommendation],
    ) -> list[dict[str, Any]]:
        return self._upsert_pages(
            items=recommendations,
            database_key=self.DATABASE_SOLUTIONS,
            title_builder=lambda recommendation: recommendation.lead_reference,
            properties_builder=self._build_solution_properties,
            entity_label="solution pages",
        )

    def upsert_execution_task_pages(
        self,
        tasks: list[ExecutionTask],
    ) -> list[dict[str, Any]]:
        return self._upsert_pages(
            items=tasks,
            database_key=self.DATABASE_TASKS,
            title_builder=self._build_task_title,
            properties_builder=self._build_execution_task_properties,
            entity_label="execution task pages",
        )

    def upsert_deal_support_pages(
        self,
        packages: list[DealSupportPackage],
    ) -> list[dict[str, Any]]:
        return self._upsert_pages(
            items=packages,
            database_key=self.DATABASE_DEAL_SUPPORT,
            title_builder=lambda package: package.lead_reference,
            properties_builder=self._build_deal_support_properties,
            entity_label="deal support pages",
        )

    def upsert_account_pages(
        self,
        accounts: list[Account],
    ) -> list[dict[str, Any]]:
        self._ensure_accounts_configured()
        title_property = self._resolve_title_property(
            self.accounts_database_id,
            self.title_properties[self.DATABASE_ACCOUNTS],
        )

        responses: list[dict[str, Any]] = []
        for account in accounts:
            properties = self._build_account_properties(account, title_property)
            existing_page = self._find_account_page(account.account_canonical)
            if existing_page is None:
                existing_page = self._find_page_by_title(
                    database_id=self.accounts_database_id,
                    title_property=title_property,
                    title_value=account.account_name,
                )
            if existing_page is None:
                responses.append(self._create_page(self.accounts_database_id, properties))
            else:
                responses.append(self._update_page(existing_page["id"], properties))
        return responses

    def upsert_buyer_pages(
        self,
        buyers: list[Buyer],
    ) -> list[dict[str, Any]]:
        self._ensure_buyers_configured()
        title_property = self._resolve_title_property(
            self.buyers_database_id,
            self.title_properties[self.DATABASE_BUYERS],
        )

        responses: list[dict[str, Any]] = []
        for buyer in buyers:
            properties = self._build_buyer_properties(buyer, title_property)
            existing_page = self._find_buyer_page(
                buyer_name=buyer.buyer_name,
                company_name=buyer.account_name,
            )
            if existing_page is None:
                responses.append(self._create_page(self.buyers_database_id, properties))
            else:
                responses.append(self._update_page(existing_page["id"], properties))
        return responses

    def upsert_sales_engine_run_page(
        self,
        run: SalesEngineRun,
    ) -> dict[str, Any]:
        self._ensure_run_logging_configured()
        responses = self._upsert_custom_pages(
            items=[run],
            database_id=self.runs_database_id,
            title_property=self.title_properties[self.DATABASE_RUNS],
            title_builder=lambda item: item.run_marker,
            properties_builder=self._build_sales_engine_run_properties,
            entity_label="sales engine run pages",
        )
        return responses[0]

    def _upsert_pages(
        self,
        items: Iterable[Any],
        database_key: str,
        title_builder: Callable[[Any], str],
        properties_builder: Callable[[Any], dict[str, Any]],
        entity_label: str,
    ) -> list[dict[str, Any]]:
        self._ensure_configured()

        item_list = list(items)
        if not item_list:
            logger.info(f"No {entity_label} to sync.")
            return []

        database_id = self.database_ids[database_key]
        title_property = self.title_properties[database_key]
        logger.info(f"Syncing {len(item_list)} {entity_label} to Notion.")

        responses: list[dict[str, Any]] = []
        for item in item_list:
            title_value = title_builder(item)
            properties = properties_builder(item)
            existing_page = self._find_page_by_title(
                database_id=database_id,
                title_property=title_property,
                title_value=title_value,
            )
            if existing_page is None:
                responses.append(self._create_page(database_id, properties))
            else:
                responses.append(self._update_page(existing_page["id"], properties))

        return responses

    def _upsert_custom_pages(
        self,
        items: Iterable[Any],
        database_id: str,
        title_property: str,
        title_builder: Callable[[Any], str],
        properties_builder: Callable[[Any], dict[str, Any]],
        entity_label: str,
    ) -> list[dict[str, Any]]:
        self._ensure_configured()

        item_list = list(items)
        if not item_list:
            logger.info(f"No {entity_label} to sync.")
            return []

        logger.info(f"Syncing {len(item_list)} {entity_label} to Notion.")

        responses: list[dict[str, Any]] = []
        for item in item_list:
            title_value = title_builder(item)
            properties = properties_builder(item)
            existing_page = self._find_page_by_title(
                database_id=database_id,
                title_property=title_property,
                title_value=title_value,
            )
            if existing_page is None:
                responses.append(self._create_page(database_id, properties))
            else:
                responses.append(self._update_page(existing_page["id"], properties))

        return responses

    def _query_database(
        self,
        database_id: str,
        *,
        limit: int,
        sort_direction: str = "descending",
    ) -> dict[str, Any]:
        response = self.client.post(
            f"/databases/{database_id}/query",
            json={
                "page_size": min(max(limit, 20), 100),
                "sorts": [
                    {
                        "timestamp": "last_edited_time",
                        "direction": sort_direction,
                    }
                ],
            },
        )
        return self._parse_response(response)

    def _find_page_by_title(
        self,
        database_id: str,
        title_property: str,
        title_value: str,
    ) -> dict[str, Any] | None:
        response = self.client.post(
            f"/databases/{database_id}/query",
            json={
                "filter": {
                    "property": title_property,
                    "title": {
                        "equals": title_value,
                    },
                }
            },
        )
        payload = self._parse_response(response)
        results = payload.get("results", [])
        if not results:
            return None
        return results[0]

    def _find_discovery_page(
        self,
        candidate: DiscoveryCandidate,
    ) -> dict[str, Any] | None:
        schema = self._get_database_schema(self.discovery_database_id)

        if candidate.discovery_key and "Discovery Key" in schema:
            existing_page = self._find_page_by_property_value(
                database_id=self.discovery_database_id,
                property_name="Discovery Key",
                value=candidate.discovery_key,
            )
            if existing_page is not None:
                return existing_page

        if candidate.source_url and "Source URL" in schema:
            existing_page = self._find_page_by_property_value(
                database_id=self.discovery_database_id,
                property_name="Source URL",
                value=candidate.source_url,
            )
            if existing_page is not None:
                return existing_page

        return None

    def _find_page_by_property_value(
        self,
        database_id: str,
        property_name: str,
        value: str,
    ) -> dict[str, Any] | None:
        schema = self._get_database_schema(database_id)
        property_definition = schema.get(property_name)
        if not property_definition:
            return None

        property_type = property_definition.get("type")
        filter_payload = self._property_filter(property_name, property_type, value)
        if filter_payload is None:
            return None

        response = self.client.post(
            f"/databases/{database_id}/query",
            json={"filter": filter_payload},
        )
        payload = self._parse_response(response)
        results = payload.get("results", [])
        if not results:
            return None
        return results[0]

    def _find_account_page(self, account_canonical: str | None) -> dict[str, Any] | None:
        if not self.is_accounts_configured() or not account_canonical:
            return None
        return self._find_page_by_property_value(
            database_id=self.accounts_database_id,
            property_name="Account Canonical",
            value=account_canonical,
        )

    def _find_buyer_page(
        self,
        buyer_name: str | None,
        company_name: str | None,
    ) -> dict[str, Any] | None:
        if not self.is_buyers_configured() or not buyer_name:
            return None
        title_property = self._resolve_title_property(
            self.buyers_database_id,
            self.title_properties[self.DATABASE_BUYERS],
        )
        results = self._find_pages_by_title(
            database_id=self.buyers_database_id,
            title_property=title_property,
            title_value=buyer_name,
        )
        if not results:
            return None

        account_text_property = self._first_property_name(
            self.buyers_database_id,
            "Account (text)",
        )
        if not company_name or not account_text_property:
            return results[0]

        for page in results:
            if self._property_text(page, account_text_property) == company_name:
                return page
        return results[0]

    def _find_pages_by_title(
        self,
        database_id: str,
        title_property: str,
        title_value: str,
    ) -> list[dict[str, Any]]:
        response = self.client.post(
            f"/databases/{database_id}/query",
            json={
                "filter": {
                    "property": title_property,
                    "title": {
                        "equals": title_value,
                    },
                }
            },
        )
        payload = self._parse_response(response)
        return payload.get("results", [])

    def _resolve_title_property(
        self,
        database_id: str,
        preferred_name: str,
    ) -> str:
        schema = self._get_database_schema(database_id)
        if preferred_name in schema:
            return preferred_name
        for property_name, definition in schema.items():
            if definition.get("type") == "title":
                return property_name
        return preferred_name

    def _first_property_name(
        self,
        database_id: str,
        *names: str,
    ) -> str | None:
        schema = self._get_database_schema(database_id)
        for name in names:
            if name in schema:
                return name
        return None

    def _property_filter(
        self,
        property_name: str,
        property_type: str | None,
        value: str,
    ) -> dict[str, Any] | None:
        if property_type == "title":
            return {
                "property": property_name,
                "title": {"equals": value},
            }
        if property_type == "rich_text":
            return {
                "property": property_name,
                "rich_text": {"equals": value},
            }
        if property_type == "url":
            return {
                "property": property_name,
                "url": {"equals": value},
            }
        return None

    def _create_page(
        self,
        database_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.client.post(
            "/pages",
            json={
                "parent": {
                    "database_id": database_id,
                },
                "properties": properties,
            },
        )
        return self._parse_response(response)

    def _update_page(
        self,
        page_id: str,
        properties: dict[str, Any],
    ) -> dict[str, Any]:
        response = self.client.patch(
            f"/pages/{page_id}",
            json={
                "properties": properties,
            },
        )
        return self._parse_response(response)

    def _ensure_intake_configured(self) -> None:
        self._ensure_configured()
        if not self.intake_database_id:
            raise RuntimeError("Notion intake database is not configured.")

    def _ensure_discovery_configured(self) -> None:
        self._ensure_configured()
        if not self.discovery_database_id:
            raise RuntimeError("Notion discovery database is not configured.")

    def _ensure_outreach_queue_configured(self) -> None:
        self._ensure_configured()
        if not self.outreach_queue_database_id:
            raise RuntimeError("Notion outreach queue database is not configured.")

    def _ensure_opportunities_configured(self) -> None:
        self._ensure_configured()
        if not self.opportunities_database_id:
            raise RuntimeError("Notion opportunities database is not configured.")

    def _ensure_run_logging_configured(self) -> None:
        self._ensure_configured()
        if not self.runs_database_id:
            raise RuntimeError("Notion runs database is not configured.")

    def _ensure_accounts_configured(self) -> None:
        self._ensure_configured()
        if not self.accounts_database_id:
            raise RuntimeError("Notion accounts database is not configured.")

    def _ensure_buyers_configured(self) -> None:
        self._ensure_configured()
        if not self.buyers_database_id:
            raise RuntimeError("Notion buyers database is not configured.")

    def _get_database_schema(self, database_id: str) -> dict[str, Any]:
        if database_id in self._database_schema_cache:
            return self._database_schema_cache[database_id]

        response = self.client.get(f"/databases/{database_id}")
        payload = self._parse_response(response)
        properties = payload.get("properties", {})
        self._database_schema_cache[database_id] = properties
        return properties

    def _get_database_property_types(self, database_id: str) -> dict[str, str]:
        properties = self._get_database_schema(database_id)
        return {
            name: definition.get("type", "")
            for name, definition in properties.items()
        }

    def _parse_response(self, response: Any) -> dict[str, Any]:
        if hasattr(response, "raise_for_status"):
            response.raise_for_status()
        if hasattr(response, "json"):
            return response.json()
        return response

    def _ensure_configured(self) -> None:
        if not self.is_configured():
            raise RuntimeError(self._configuration_error)

    def _build_lead_intake_record(
        self,
        page: dict[str, Any],
    ) -> LeadIntakeRecord | None:
        company_name = self._property_text(page, "Company")
        if not company_name:
            logger.info(
                "Skipping intake page without a Company title property value."
            )
            return None

        return LeadIntakeRecord(
            page_id=page["id"],
            company_name=company_name,
            company_canonical=self._property_text(page, "Company Canonical"),
            lane_label=(
                self._property_option(page, "Lane Label")
                or self._property_text(page, "Lane Label")
                or self._lane_label_from_summary(
                    self._property_text(page, "Account Fit Summary")
                )
            ),
            contact_name=self._property_text(page, "Contact"),
            contact_role=self._property_text(page, "Role"),
            email=self._property_value(page, "Email"),
            linkedin_url=self._property_value(page, "LinkedIn URL"),
            company_country=self._property_text(page, "Company Country"),
            target_country=self._property_option(page, "Target Country"),
            buyer_confidence=self._property_number(page, "Buyer Confidence"),
            account_fit_summary=self._property_text(page, "Account Fit Summary"),
            lead_type_hint=self._property_option(page, "Lead Type Hint"),
            campaign=self._property_text(page, "Campaign"),
            notes=self._property_text(page, "Notes"),
            status=self._property_option(page, "Status"),
            lead_reference=self._property_text(page, "Lead Reference"),
            processed_at=self._property_date(page, "Processed At"),
        )

    def _build_lead_discovery_record(
        self,
        page: dict[str, Any],
    ) -> LeadDiscoveryRecord | None:
        company_name = self._property_text(page, "Company")
        if not company_name:
            logger.info(
                "Skipping discovery page without a Company title property value."
            )
            return None

        return LeadDiscoveryRecord(
            page_id=page["id"],
            company_name=company_name,
            company_canonical=self._property_text(page, "Company Canonical"),
            agent_label=self._property_option(page, "Agent Label")
            or self._property_text(page, "Agent Label"),
            lane_label=(
                self._property_option(page, "Lane Label")
                or self._property_text(page, "Lane Label")
                or self._lane_label_from_summary(
                    self._property_text(page, "Account Fit Summary")
                )
            ),
            discovery_key=self._property_text(page, "Discovery Key"),
            website_url=self._property_value(page, "Website URL"),
            source_url=self._property_value(page, "Source URL"),
            source_type=self._property_option(page, "Source Type"),
            published_at=self._property_date(page, "Published At"),
            source_priority=self._property_number(page, "Source Priority"),
            source_trust_score=self._property_number(page, "Source Trust Score"),
            service_focus=self._property_option(page, "Service Focus"),
            evidence=self._property_text(page, "Evidence"),
            contact_name=self._property_text(page, "Contact"),
            contact_role=self._property_text(page, "Role"),
            email=self._property_value(page, "Email"),
            linkedin_url=self._property_value(page, "LinkedIn URL"),
            company_country=self._property_text(page, "Company Country"),
            target_country_hint=self._property_option(page, "Target Country Hint"),
            buyer_confidence=self._property_number(page, "Buyer Confidence"),
            account_fit_summary=self._property_text(page, "Account Fit Summary"),
            campaign=self._property_text(page, "Campaign"),
            notes=self._property_text(page, "Notes"),
            status=self._property_option(page, "Status"),
        )

    def _build_outreach_queue_record(
        self,
        page: dict[str, Any],
    ) -> OutreachQueueRecord | None:
        lead_reference = self._property_text(page, "Lead Reference")
        if not lead_reference:
            logger.info(
                "Skipping outreach queue page without a Lead Reference title property value."
            )
            return None

        return OutreachQueueRecord(
            page_id=page["id"],
            lead_reference=lead_reference,
            company_name=self._property_text(page, "Company"),
            company_canonical=self._property_text(page, "Company Canonical"),
            contact_name=self._property_text(page, "Contact"),
            contact_role=self._property_text(page, "Role"),
            priority=self._property_option(page, "Priority"),
            target_country=self._property_option(page, "Target Country")
            or self._property_text(page, "Target Country"),
            sales_motion=self._property_option(page, "Sales Motion")
            or self._property_text(page, "Sales Motion"),
            primary_module=self._property_option(page, "Primary Module")
            or self._property_text(page, "Primary Module"),
            bundle_label=self._property_option(page, "Bundle Label")
            or self._property_text(page, "Bundle Label"),
            email_subject=self._property_text(page, "Email Subject"),
            email_message=self._property_text(page, "Email Message"),
            linkedin_message=self._property_text(page, "LinkedIn Message"),
            follow_up_message=self._property_text(page, "Follow-Up Message"),
            reply=self._property_text(page, "Reply"),
            status=self._property_option(page, "Status"),
            generated_at=self._property_date(page, "Generated At"),
            run_marker=self._property_text(page, "Run Marker"),
            notes=self._property_text(page, "Notes"),
        )

    def _build_sales_engine_run_record(
        self,
        page: dict[str, Any],
    ) -> SalesEngineRunRecord | None:
        run_marker = self._property_text(page, "Run Marker")
        status = self._property_option(page, "Status")
        started_at = self._property_date(page, "Started At")
        if not run_marker or not status or not started_at:
            logger.info("Skipping sales engine run page missing key properties.")
            return None

        return SalesEngineRunRecord(
            page_id=page["id"],
            run_marker=run_marker,
            status=status,
            started_at=started_at,
            run_mode=self._property_option(page, "Run Mode")
            or self._property_text(page, "Run Mode"),
            completed_at=self._property_date(page, "Completed At"),
            lead_count=self._property_number(page, "Lead Count") or 0,
            outreach_count=self._property_number(page, "Outreach Count") or 0,
            pipeline_count=self._property_number(page, "Pipeline Count") or 0,
            task_count=self._property_number(page, "Task Count") or 0,
            error_summary=self._property_text(page, "Error Summary"),
            triggered_by=self._property_option(page, "Triggered By")
            or self._property_text(page, "Triggered By"),
            notes=self._property_text(page, "Notes"),
        )

    def _same_discovery_signal(
        self,
        existing_page: dict[str, Any],
        candidate: DiscoveryCandidate,
    ) -> bool:
        existing_discovery_key = self._property_text(existing_page, "Discovery Key")
        existing_source_url = self._property_value(existing_page, "Source URL")
        existing_evidence = self._property_text(existing_page, "Evidence")
        existing_status = self._property_option(existing_page, "Status")

        same_discovery_key = (
            (existing_discovery_key or None) == (candidate.discovery_key or None)
        )
        same_source_url = (existing_source_url or None) == (candidate.source_url or None)
        same_evidence = (existing_evidence or "").strip() == (candidate.evidence or "").strip()
        normalized_status = (existing_status or "").strip().lower()

        return (
            (same_discovery_key or same_source_url)
            and same_evidence
            and normalized_status not in {"", "error"}
        )

    def _should_process_discovery_status(self, status: str | None) -> bool:
        if not status:
            return True

        normalized = status.strip().lower()
        if normalized in {
            "promoted",
            "review",
            "rejected",
            "error",
            "done",
            "archived",
        }:
            return False
        return normalized in {"new", "approved", "ready"}

    def _should_process_intake_status(self, status: str | None) -> bool:
        if not status:
            return True

        normalized = status.strip().lower()
        if normalized in {"ingested", "archived", "rejected", "done"}:
            return False
        return normalized in {"new", "approved", "ready"}

    def _build_intake_processed_properties(self, lead: Lead) -> dict[str, Any]:
        property_types = self._get_database_property_types(self.intake_database_id)
        lead_reference = self._build_lead_reference(lead)
        properties: dict[str, Any] = {}
        company_canonical_property = self._text_property(
            property_types.get("Company Canonical"),
            self._company_canonical(lead.company_canonical, lead.company_name),
        )
        if company_canonical_property is not None:
            properties["Company Canonical"] = company_canonical_property

        status_property = self._database_option_property(
            self.intake_database_id,
            "Status",
            "ingested",
        )
        if status_property is not None:
            properties["Status"] = status_property

        lead_reference_property = self._text_property(
            property_types.get("Lead Reference"),
            lead_reference,
        )
        if lead_reference_property is not None:
            properties["Lead Reference"] = lead_reference_property

        fit_reason_property = self._text_property(
            property_types.get("Fit Reason"),
            lead.fit_reason,
        )
        if fit_reason_property is not None:
            properties["Fit Reason"] = fit_reason_property

        processed_at_property = self._date_property(
            property_types.get("Processed At"),
            utc_now_iso(),
        )
        if processed_at_property is not None:
            properties["Processed At"] = processed_at_property

        last_error_property = self._text_property(
            property_types.get("Last Error"),
            "",
        )
        if last_error_property is not None:
            properties["Last Error"] = last_error_property

        return properties

    def _build_intake_failed_properties(self, error_message: str) -> dict[str, Any]:
        property_types = self._get_database_property_types(self.intake_database_id)
        properties: dict[str, Any] = {}

        status_property = self._database_option_property(
            self.intake_database_id,
            "Status",
            "error",
        )
        if status_property is not None:
            properties["Status"] = status_property

        last_error_property = self._text_property(
            property_types.get("Last Error"),
            error_message,
        )
        if last_error_property is not None:
            properties["Last Error"] = last_error_property

        processed_at_property = self._date_property(
            property_types.get("Processed At"),
            utc_now_iso(),
        )
        if processed_at_property is not None:
            properties["Processed At"] = processed_at_property

        return properties

    def _build_discovery_candidate_properties(
        self,
        candidate: DiscoveryCandidate,
    ) -> dict[str, Any]:
        property_types = self._get_database_property_types(self.discovery_database_id)
        return self._compact_properties(
            {
                "Company": self._text_property(
                    property_types.get("Company"),
                    candidate.company_name,
                ),
                "Company Canonical": self._text_property(
                    property_types.get("Company Canonical"),
                    self._company_canonical(
                        candidate.company_canonical,
                        candidate.company_name,
                    ),
                ),
                "Discovery Key": self._text_property(
                    property_types.get("Discovery Key"),
                    candidate.discovery_key,
                ),
                "Agent Label": self._database_choice_or_text_property(
                    self.discovery_database_id,
                    "Agent Label",
                    candidate.agent_label,
                ),
                "Lane Label": self._database_choice_or_text_property(
                    self.discovery_database_id,
                    "Lane Label",
                    candidate.lane_label,
                ),
                "Website URL": self._url_property(
                    property_types.get("Website URL"),
                    candidate.website_url,
                ),
                "Source URL": self._url_property(
                    property_types.get("Source URL"),
                    candidate.source_url,
                ),
                "Source Type": self._database_choice_or_text_property(
                    self.discovery_database_id,
                    "Source Type",
                    candidate.source_type,
                ),
                "Published At": self._date_property(
                    property_types.get("Published At"),
                    candidate.published_at,
                ),
                "Source Priority": self._number_property(
                    property_types.get("Source Priority"),
                    candidate.source_priority,
                ),
                "Source Trust Score": self._number_property(
                    property_types.get("Source Trust Score"),
                    candidate.source_trust_score,
                ),
                "Service Focus": self._database_choice_or_text_property(
                    self.discovery_database_id,
                    "Service Focus",
                    candidate.service_focus,
                ),
                "Evidence": self._text_property(
                    property_types.get("Evidence"),
                    candidate.evidence,
                ),
                "Contact": self._text_property(
                    property_types.get("Contact"),
                    candidate.contact_name,
                ),
                "Role": self._text_property(
                    property_types.get("Role"),
                    candidate.contact_role,
                ),
                "Email": self._email_property(
                    property_types.get("Email"),
                    candidate.email,
                ),
                "LinkedIn URL": self._url_property(
                    property_types.get("LinkedIn URL"),
                    candidate.linkedin_url,
                ),
                "Company Country": self._text_property(
                    property_types.get("Company Country"),
                    candidate.company_country,
                ),
                "Target Country Hint": self._database_choice_or_text_property(
                    self.discovery_database_id,
                    "Target Country Hint",
                    candidate.target_country_hint,
                ),
                "Buyer Confidence": self._number_property(
                    property_types.get("Buyer Confidence"),
                    candidate.buyer_confidence,
                ),
                "Account Fit Summary": self._text_property(
                    property_types.get("Account Fit Summary"),
                    candidate.account_fit_summary,
                ),
                "Campaign": self._text_property(
                    property_types.get("Campaign"),
                    candidate.campaign,
                ),
                "Notes": self._text_property(
                    property_types.get("Notes"),
                    candidate.notes,
                ),
                "Status": self._database_choice_or_text_property(
                    self.discovery_database_id,
                    "Status",
                    candidate.status,
                ),
                "Confidence Score": self._number_property(
                    property_types.get("Confidence Score"),
                    None,
                ),
                "Qualification Summary": self._text_property(
                    property_types.get("Qualification Summary"),
                    "",
                ),
                "Evidence Summary": self._text_property(
                    property_types.get("Evidence Summary"),
                    "",
                ),
                "Lead Type": self._database_choice_or_text_property(
                    self.discovery_database_id,
                    "Lead Type",
                    None,
                ),
                "Fit Reason": self._text_property(
                    property_types.get("Fit Reason"),
                    "",
                ),
                "Lead Reference": self._text_property(
                    property_types.get("Lead Reference"),
                    "",
                ),
                "Processed At": self._date_property(
                    property_types.get("Processed At"),
                    None,
                ),
                "Last Error": self._text_property(
                    property_types.get("Last Error"),
                    "",
                ),
            }
        )

    def _build_intake_page_properties(
        self,
        lead: Lead,
        discovery_record: LeadDiscoveryRecord,
        qualification: DiscoveryQualification,
    ) -> dict[str, Any]:
        property_types = self._get_database_property_types(self.intake_database_id)
        notes = self._compose_notes(
            qualification.evidence_summary,
            discovery_record.notes,
            f"Service focus: {discovery_record.service_focus}"
            if discovery_record.service_focus
            else None,
            f"Source priority: {discovery_record.source_priority}"
            if discovery_record.source_priority is not None
            else None,
            f"Source trust score: {discovery_record.source_trust_score}"
            if discovery_record.source_trust_score is not None
            else None,
            f"Source type: {discovery_record.source_type}"
            if discovery_record.source_type
            else None,
            f"Source URL: {discovery_record.source_url}"
            if discovery_record.source_url
            else None,
        )
        lead_reference = self._build_lead_reference(lead)

        return self._compact_properties(
            {
                "Company": self._text_property(
                    property_types.get("Company"),
                    lead.company_name,
                ),
                "Company Canonical": self._text_property(
                    property_types.get("Company Canonical"),
                    self._company_canonical(
                        lead.company_canonical,
                        lead.company_name,
                    ),
                ),
                "Lane Label": self._database_choice_or_text_property(
                    self.intake_database_id,
                    "Lane Label",
                    lead.lane_label or discovery_record.lane_label,
                ),
                "Contact": self._text_property(
                    property_types.get("Contact"),
                    lead.contact_name,
                ),
                "Role": self._text_property(
                    property_types.get("Role"),
                    lead.contact_role,
                ),
                "Email": self._email_property(
                    property_types.get("Email"),
                    lead.email,
                ),
                "LinkedIn URL": self._url_property(
                    property_types.get("LinkedIn URL"),
                    lead.linkedin_url,
                ),
                "Company Country": self._text_property(
                    property_types.get("Company Country"),
                    lead.company_country,
                ),
                "Target Country": self._database_choice_or_text_property(
                    self.intake_database_id,
                    "Target Country",
                    lead.target_country,
                ),
                "Buyer Confidence": self._number_property(
                    property_types.get("Buyer Confidence"),
                    lead.buyer_confidence or discovery_record.buyer_confidence,
                ),
                "Account Fit Summary": self._text_property(
                    property_types.get("Account Fit Summary"),
                    lead.account_fit_summary or discovery_record.account_fit_summary,
                ),
                "Lead Type Hint": self._database_choice_or_text_property(
                    self.intake_database_id,
                    "Lead Type Hint",
                    lead.lead_type,
                ),
                "Campaign": self._text_property(
                    property_types.get("Campaign"),
                    discovery_record.campaign,
                ),
                "Notes": self._text_property(
                    property_types.get("Notes"),
                    notes,
                ),
                "Status": self._database_option_property(
                    self.intake_database_id,
                    "Status",
                    "ready",
                ),
                "Lead Reference": self._text_property(
                    property_types.get("Lead Reference"),
                    lead_reference,
                ),
                "Fit Reason": self._text_property(
                    property_types.get("Fit Reason"),
                    lead.fit_reason,
                ),
                "Processed At": self._date_property(
                    property_types.get("Processed At"),
                    None,
                ),
                "Last Error": self._text_property(
                    property_types.get("Last Error"),
                    "",
                ),
            }
        )

    def _build_discovery_processed_properties(
        self,
        qualification: DiscoveryQualification,
    ) -> dict[str, Any]:
        property_types = self._get_database_property_types(self.discovery_database_id)
        lead_reference = self._build_lead_reference(qualification.lead)
        status_value = self._discovery_status_from_decision(qualification.decision)

        return self._compact_properties(
            {
                "Status": self._database_option_property(
                    self.discovery_database_id,
                    "Status",
                    status_value,
                ),
                "Company Canonical": self._text_property(
                    property_types.get("Company Canonical"),
                    self._company_canonical(
                        qualification.lead.company_canonical,
                        qualification.lead.company_name,
                    ),
                ),
                "Contact": self._text_property(
                    property_types.get("Contact"),
                    qualification.lead.contact_name,
                ),
                "Role": self._text_property(
                    property_types.get("Role"),
                    qualification.lead.contact_role,
                ),
                "Email": self._email_property(
                    property_types.get("Email"),
                    qualification.lead.email,
                ),
                "LinkedIn URL": self._url_property(
                    property_types.get("LinkedIn URL"),
                    qualification.lead.linkedin_url,
                ),
                "Company Country": self._text_property(
                    property_types.get("Company Country"),
                    qualification.lead.company_country,
                ),
                "Target Country Hint": self._database_choice_or_text_property(
                    self.discovery_database_id,
                    "Target Country Hint",
                    qualification.lead.target_country,
                ),
                "Lead Type": self._database_choice_or_text_property(
                    self.discovery_database_id,
                    "Lead Type",
                    qualification.lead.lead_type,
                ),
                "Confidence Score": self._number_property(
                    property_types.get("Confidence Score"),
                    qualification.confidence_score,
                ),
                "Qualification Summary": self._text_property(
                    property_types.get("Qualification Summary"),
                    qualification.evidence_summary,
                ),
                "Evidence Summary": self._text_property(
                    property_types.get("Evidence Summary"),
                    qualification.evidence_summary,
                ),
                "Fit Reason": self._text_property(
                    property_types.get("Fit Reason"),
                    qualification.lead.fit_reason,
                ),
                "Lead Reference": self._text_property(
                    property_types.get("Lead Reference"),
                    lead_reference,
                ),
                "Processed At": self._date_property(
                    property_types.get("Processed At"),
                    utc_now_iso(),
                ),
                "Last Error": self._text_property(
                    property_types.get("Last Error"),
                    "",
                ),
            }
        )

    def _build_discovery_failed_properties(
        self,
        error_message: str,
    ) -> dict[str, Any]:
        property_types = self._get_database_property_types(self.discovery_database_id)
        return self._compact_properties(
            {
                "Status": self._database_option_property(
                    self.discovery_database_id,
                    "Status",
                    "error",
                ),
                "Last Error": self._text_property(
                    property_types.get("Last Error"),
                    error_message,
                ),
                "Processed At": self._date_property(
                    property_types.get("Processed At"),
                    utc_now_iso(),
                ),
            }
        )

    def _build_lead_reference(self, lead: Lead) -> str:
        parts = [
            lead.company_name,
            lead.contact_name,
            self._country_label(lead.target_country),
            lead.lead_type or "unknown",
        ]
        return "|".join(parts)

    def _build_task_title(self, task: ExecutionTask) -> str:
        return f"{task.lead_reference} | {task.task_type}"

    def _build_lead_properties(self, lead: Lead) -> dict[str, Any]:
        property_types = self._get_database_property_types(
            self.database_ids[self.DATABASE_LEADS]
        )
        return self._compact_properties({
            "Lead Reference": self._title(self._build_lead_reference(lead)),
            "Company": self._rich_text(lead.company_name),
            "Company Canonical": self._text_property(
                property_types.get("Company Canonical"),
                self._company_canonical(lead.company_canonical, lead.company_name),
            ),
            "Contact": self._rich_text(lead.contact_name),
            "Role": self._rich_text(lead.contact_role),
            "Country": self._rich_text(lead.target_country),
            "Lead Type": self._select(lead.lead_type),
            "Score": self._number(lead.score),
            "Priority": self._select(lead.priority),
        })

    def _build_outreach_queue_properties(
        self,
        item: OutreachQueueItem,
    ) -> dict[str, Any]:
        database_id = self.outreach_queue_database_id
        property_types = self._get_database_property_types(database_id)
        company_canonical = self._company_canonical(
            item.company_canonical,
            item.company_name,
        )
        return self._compact_properties({
            "Lead Reference": self._title(item.lead_reference),
            "Company": self._rich_text(item.company_name),
            "Company Canonical": self._text_property(
                property_types.get("Company Canonical"),
                company_canonical,
            ),
            "Account": self._account_relation_property(
                property_types.get("Account"),
                company_canonical,
            ),
            "Buyer": self._buyer_relation_property(
                property_types.get("Buyer"),
                item.contact_name,
                item.company_name,
            ),
            "Contact": self._rich_text(item.contact_name),
            "Role": self._rich_text(item.contact_role),
            "Priority": self._database_option_property(
                database_id,
                "Priority",
                item.priority,
            ),
            "Target Country": self._database_option_property(
                database_id,
                "Target Country",
                item.target_country,
            ),
            "Sales Motion": self._database_option_property(
                database_id,
                "Sales Motion",
                item.sales_motion,
            ),
            "Primary Module": self._database_option_property(
                database_id,
                "Primary Module",
                item.primary_module,
            ),
            "Bundle Label": self._database_option_property(
                database_id,
                "Bundle Label",
                item.bundle_label,
            ),
            "Email Subject": self._rich_text(item.email_subject),
            "Email Message": self._rich_text(item.email_message),
            "LinkedIn Message": self._rich_text(item.linkedin_message),
            "Follow-Up Message": self._rich_text(item.follow_up_message),
            "Status": self._database_option_property(
                database_id,
                "Status",
                item.status,
            ),
            "Generated At": self._date(item.generated_at),
            "Run Marker": self._rich_text(item.run_marker),
            "Notes": self._rich_text(item.notes),
        })

    def _should_preserve_outreach_queue_page(
        self,
        existing_page: dict[str, Any],
    ) -> bool:
        existing_status = self._property_option(existing_page, "Status")
        normalized_status = self._normalize_option_name(existing_status)
        if not normalized_status:
            return False
        if normalized_status == self.OUTREACH_QUEUE_REGENERATE_STATUS:
            return False
        return normalized_status in self.OUTREACH_QUEUE_PRESERVE_STATUSES

    def _build_pipeline_properties(
        self,
        record: PipelineRecord,
    ) -> dict[str, Any]:
        property_types = self._get_database_property_types(
            self.database_ids[self.DATABASE_PIPELINE]
        )
        company_canonical = self._company_canonical(
            record.company_canonical,
            record.company_name,
        )
        return self._compact_properties({
            "Lead Reference": self._title(record.lead_reference),
            "Company": self._rich_text(record.company_name),
            "Company Canonical": self._text_property(
                property_types.get("Company Canonical"),
                company_canonical,
            ),
            "Account": self._account_relation_property(
                property_types.get("Account"),
                company_canonical,
            ),
            "Buyer": self._buyer_relation_property(
                property_types.get("Buyer"),
                record.contact_name,
                record.company_name,
            ),
            "Stage": self._select(record.stage),
            "Outreach Status": self._select(record.outreach_status),
            "Next Action": self._rich_text(record.next_action),
            "Priority": self._select(record.priority),
            "Sales Motion": self._select(record.sales_motion),
            "Primary Module": self._select(record.primary_module),
            "Bundle Label": self._select(record.bundle_label),
            "High Value": self._checkbox(self._is_high_value(record)),
            "Last Updated": self._date(record.last_updated_at),
        })

    def _build_solution_properties(
        self,
        recommendation: SolutionRecommendation,
    ) -> dict[str, Any]:
        return {
            "Lead Reference": self._title(recommendation.lead_reference),
            "Company": self._rich_text(recommendation.company_name),
            "Sales Motion": self._select(recommendation.sales_motion),
            "Primary Module": self._select(recommendation.primary_module),
            "Bundle Label": self._select(recommendation.bundle_label),
            "Recommended Modules": self._multi_select(
                recommendation.recommended_modules
            ),
            "Commercial Strategy": self._rich_text(
                recommendation.commercial_strategy
            ),
            "Rationale": self._rich_text(recommendation.rationale),
        }

    def _build_execution_task_properties(
        self,
        task: ExecutionTask,
    ) -> dict[str, Any]:
        property_types = self._get_database_property_types(
            self.database_ids[self.DATABASE_TASKS]
        )
        company_name = task.company_name or company_name_from_lead_reference(
            task.lead_reference
        )
        company_canonical = self._company_canonical(task.company_canonical, company_name)
        contact_name = contact_name_from_lead_reference(task.lead_reference)
        return self._compact_properties({
            "Task": self._title(self._build_task_title(task)),
            "Lead Reference": self._rich_text(task.lead_reference),
            "Company": self._text_property(
                property_types.get("Company"),
                company_name,
            ),
            "Company Canonical": self._text_property(
                property_types.get("Company Canonical"),
                company_canonical,
            ),
            "Account": self._account_relation_property(
                property_types.get("Account"),
                company_canonical,
            ),
            "Buyer": self._buyer_relation_property(
                property_types.get("Buyer"),
                contact_name,
                company_name,
            ),
            "Task Type": self._select(task.task_type),
            "Description": self._rich_text(task.description),
            "Priority": self._select(task.priority),
            "Due In Days": self._number(task.due_in_days),
            "Status": self._select(task.status),
        })

    def _build_account_properties(
        self,
        account: Account,
        title_property: str,
    ) -> dict[str, Any]:
        property_types = self._get_database_property_types(self.accounts_database_id)
        country_property = self._first_property_name(
            self.accounts_database_id,
            "Primary Target Country",
            "Country / Region",
        )
        lane_property = self._first_property_name(
            self.accounts_database_id,
            "Lane Labels",
            "Tags",
        )
        fit_summary_property = self._first_property_name(
            self.accounts_database_id,
            "Account Fit Summary",
            "ICP Notes",
        )
        notes_or_fit = self._compose_notes(
            account.account_fit_summary,
            account.notes,
        )
        source_property = self._first_property_name(
            self.accounts_database_id,
            "Source",
        )
        return self._compact_properties({
            title_property: self._title(account.account_name),
            "Account Canonical": self._text_property(
                property_types.get("Account Canonical"),
                account.account_canonical,
            ),
            **(
                {
                    country_property: self._database_choice_or_text_property(
                        self.accounts_database_id,
                        country_property,
                        account.primary_target_country,
                    )
                }
                if country_property
                else {}
            ),
            **(
                {
                    lane_property: self._multi_select_property(
                        property_types.get(lane_property),
                        account.lane_labels,
                    )
                }
                if lane_property
                else {}
            ),
            **(
                {
                    fit_summary_property: self._text_property(
                        property_types.get(fit_summary_property),
                        notes_or_fit,
                    )
                }
                if fit_summary_property
                else {}
            ),
            **(
                {
                    source_property: self._database_choice_or_text_property(
                        self.accounts_database_id,
                        source_property,
                        "Sales Engine",
                    )
                }
                if source_property
                else {}
            ),
        })

    def _build_buyer_properties(
        self,
        buyer: Buyer,
        title_property: str,
    ) -> dict[str, Any]:
        property_types = self._get_database_property_types(self.buyers_database_id)
        role_property = self._first_property_name(
            self.buyers_database_id,
            "Contact Role",
            "Role / Persona",
        )
        linkedin_property = self._first_property_name(
            self.buyers_database_id,
            "LinkedIn URL",
            "LinkedIn",
        )
        account_text_property = self._first_property_name(
            self.buyers_database_id,
            "Account (text)",
        )
        notes = self._compose_notes(
            buyer.notes,
            f"Buyer key: {buyer.buyer_key}",
            (
                f"Buyer confidence: {buyer.buyer_confidence}"
                if buyer.buyer_confidence is not None
                else None
            ),
            (
                f"Lanes: {', '.join(buyer.lane_labels)}"
                if buyer.lane_labels
                else None
            ),
            (
                f"Target country: {buyer.target_country}"
                if buyer.target_country
                else None
            ),
        )
        return self._compact_properties({
            title_property: self._title(buyer.buyer_name),
            "Buyer Key": self._text_property(
                property_types.get("Buyer Key"),
                buyer.buyer_key,
            ),
            "Buyer Name": self._text_property(
                property_types.get("Buyer Name"),
                buyer.buyer_name,
            ),
            "Buyer Canonical": self._text_property(
                property_types.get("Buyer Canonical"),
                buyer.buyer_canonical,
            ),
            "Account Canonical": self._text_property(
                property_types.get("Account Canonical"),
                buyer.account_canonical,
            ),
            **(
                {
                    role_property: self._text_property(
                        property_types.get(role_property),
                        buyer.contact_role,
                    )
                }
                if role_property
                else {}
            ),
            "Email": self._email_property(
                property_types.get("Email"),
                buyer.email,
            ),
            **(
                {
                    linkedin_property: self._url_property(
                        property_types.get(linkedin_property),
                        buyer.linkedin_url,
                    )
                }
                if linkedin_property
                else {}
            ),
            "Target Country": self._database_choice_or_text_property(
                self.buyers_database_id,
                "Target Country",
                buyer.target_country,
            ),
            "Buyer Confidence": self._number_property(
                property_types.get("Buyer Confidence"),
                buyer.buyer_confidence,
            ),
            "Lane Labels": self._multi_select_property(
                property_types.get("Lane Labels"),
                buyer.lane_labels,
            ),
            **(
                {
                    account_text_property: self._text_property(
                        property_types.get(account_text_property),
                        buyer.account_name,
                    )
                }
                if account_text_property
                else {}
            ),
            "Account": self._account_relation_property(
                property_types.get("Account"),
                buyer.account_canonical,
            ),
            "Notes": self._text_property(
                property_types.get("Notes"),
                notes,
            ),
        })

    def _build_deal_support_properties(
        self,
        package: DealSupportPackage,
    ) -> dict[str, Any]:
        return {
            "Lead Reference": self._title(package.lead_reference),
            "Company": self._rich_text(package.company_name),
            "Stage": self._select(package.stage),
            "Recap Subject": self._rich_text(package.recap_email_subject),
            "Proposal Summary": self._rich_text(package.proposal_summary),
            "Next Steps": self._rich_text(package.next_steps_message),
            "Objection Response": self._rich_text(package.objection_response),
        }

    def _build_sales_engine_run_properties(
        self,
        run: SalesEngineRun,
    ) -> dict[str, Any]:
        database_id = self.runs_database_id
        property_types = self._get_database_property_types(database_id)
        return self._compact_properties({
            "Run Marker": self._title(run.run_marker),
            "Status": self._database_option_property(
                database_id,
                "Status",
                run.status,
            ),
            "Run Mode": self._database_choice_or_text_property(
                database_id,
                "Run Mode",
                run.run_mode,
            ),
            "Started At": self._date(run.started_at),
            "Completed At": self._date(run.completed_at),
            "Lead Count": self._number(run.lead_count),
            "Outreach Count": self._number(run.outreach_count),
            "Pipeline Count": self._number(run.pipeline_count),
            "Task Count": self._number(run.task_count),
            "Error Summary": self._rich_text(run.error_summary),
            "Triggered By": self._database_option_property(
                database_id,
                "Triggered By",
                run.triggered_by,
            ),
            "Notes": self._text_property(
                property_types.get("Notes"),
                run.notes,
            ),
        })

    def _is_high_value(self, record: PipelineRecord) -> bool:
        return record.priority == "high" or record.bundle_label == "Full Platform"

    def _title(self, value: str) -> dict[str, Any]:
        return {
            "title": [
                {
                    "text": {
                        "content": self._truncate_text(value),
                    }
                }
            ]
        }

    def _rich_text(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {"rich_text": []}
        return {
            "rich_text": [
                {
                    "text": {
                        "content": self._truncate_text(value),
                    }
                }
            ]
        }

    def _number(self, value: int | None) -> dict[str, Any]:
        return {"number": value}

    def _select(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {"select": None}
        return {
            "select": {
                "name": value,
            }
        }

    def _multi_select(self, values: list[str] | None) -> dict[str, Any]:
        return {
            "multi_select": [
                {
                    "name": value,
                }
                for value in values or []
            ]
        }

    def _multi_select_property(
        self,
        property_type: str | None,
        values: list[str] | None,
    ) -> dict[str, Any] | None:
        if property_type != "multi_select":
            return None
        return self._multi_select(values)

    def _checkbox(self, value: bool) -> dict[str, Any]:
        return {"checkbox": value}

    def _date(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {"date": None}
        return {
            "date": {
                "start": value,
            }
        }

    def _truncate_text(self, value: str, limit: int = 2000) -> str:
        if len(value) <= limit:
            return value
        return value[: limit - 3].rstrip() + "..."

    def _company_canonical(
        self,
        value: str | None,
        company_name: str | None,
    ) -> str | None:
        return normalize_company_canonical(value or company_name)

    def _buyer_key(
        self,
        buyer_name: str | None,
        company_name: str | None,
    ) -> str | None:
        if not self._has_known_value(buyer_name) or not company_name:
            return None
        return f"{buyer_name.strip()} | {company_name}"

    def _relation_property(
        self,
        property_type: str | None,
        page_ids: list[str] | None,
    ) -> dict[str, Any] | None:
        if property_type != "relation" or not page_ids:
            return None
        return {
            "relation": [{"id": page_id} for page_id in page_ids],
        }

    def _account_relation_property(
        self,
        property_type: str | None,
        account_canonical: str | None,
    ) -> dict[str, Any] | None:
        if property_type != "relation":
            return None
        account_page = self._find_account_page(account_canonical)
        if account_page is None:
            return None
        return self._relation_property(property_type, [account_page["id"]])

    def _buyer_relation_property(
        self,
        property_type: str | None,
        buyer_name: str | None,
        company_name: str | None,
    ) -> dict[str, Any] | None:
        if property_type != "relation":
            return None
        buyer_page = self._find_buyer_page(buyer_name, company_name)
        if buyer_page is None:
            return None
        return self._relation_property(property_type, [buyer_page["id"]])

    def _compact_properties(self, properties: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in properties.items()
            if value is not None
        }

    def _text_property(
        self,
        property_type: str | None,
        value: str | None,
    ) -> dict[str, Any] | None:
        if not property_type:
            return None
        if property_type == "title":
            return self._title(value or "")
        if property_type == "rich_text":
            return self._rich_text(value)
        return None

    def _status_or_select_property(
        self,
        property_type: str | None,
        value: str | None,
    ) -> dict[str, Any] | None:
        if not property_type:
            return None
        if property_type == "status":
            if not value:
                return {"status": None}
            return {"status": {"name": value}}
        if property_type == "select":
            if not value:
                return {"select": None}
            return {"select": {"name": value}}
        return None

    def _database_option_property(
        self,
        database_id: str,
        property_name: str,
        value: str | None,
    ) -> dict[str, Any] | None:
        properties = self._get_database_schema(database_id)
        property_definition = properties.get(property_name)
        if not property_definition:
            return None

        property_type = property_definition.get("type")
        resolved_value = self._resolve_database_option_name(
            database_id,
            property_name,
            value,
        )
        return self._status_or_select_property(property_type, resolved_value)

    def _database_choice_or_text_property(
        self,
        database_id: str,
        property_name: str,
        value: str | None,
    ) -> dict[str, Any] | None:
        properties = self._get_database_schema(database_id)
        property_definition = properties.get(property_name)
        if not property_definition:
            return None

        property_type = property_definition.get("type")
        if property_type in {"select", "status"}:
            resolved_value = self._resolve_database_option_name(
                database_id,
                property_name,
                value,
            )
            return self._status_or_select_property(property_type, resolved_value)

        return self._text_property(property_type, value)

    def _resolve_database_option_name(
        self,
        database_id: str,
        property_name: str,
        value: str | None,
    ) -> str | None:
        if not value:
            return None

        properties = self._get_database_schema(database_id)
        property_definition = properties.get(property_name, {})
        property_type = property_definition.get("type")
        if property_type not in {"select", "status"}:
            return value

        property_settings = property_definition.get(property_type, {})
        options = property_settings.get("options", [])
        normalized_value = self._normalize_option_name(value)

        for option in options:
            option_name = option.get("name")
            if self._normalize_option_name(option_name) == normalized_value:
                return option_name

        return value

    def _normalize_option_name(self, value: str | None) -> str:
        if not value:
            return ""
        return "".join(character for character in value.lower() if character.isalnum())

    def _discovery_priority_key(
        self,
        record: LeadDiscoveryRecord,
    ) -> tuple[int, int, int, int, int, str]:
        return (
            -(record.buyer_confidence or 0),
            -int(self._has_known_value(record.contact_role)),
            -int(self._has_known_value(record.contact_name)),
            -(record.source_trust_score or 0),
            -(record.source_priority or 0),
            record.page_id,
        )

    def _intake_priority_key(
        self,
        record: LeadIntakeRecord,
    ) -> tuple[int, int, str]:
        return (
            -(record.buyer_confidence or 0),
            -int(self._has_known_value(record.contact_role)),
            record.page_id,
        )

    def _has_known_value(self, value: str | None) -> bool:
        cleaned = (value or "").strip().lower()
        return bool(cleaned) and cleaned not in self.PLACEHOLDER_VALUES

    def _lane_label_from_summary(self, summary: str | None) -> str | None:
        if not summary:
            return None
        match = re.search(r"\blane=([^;]+)", summary, flags=re.IGNORECASE)
        if not match:
            return None
        return match.group(1).strip()

    def _date_property(
        self,
        property_type: str | None,
        value: str | None,
    ) -> dict[str, Any] | None:
        if property_type != "date":
            return None
        return self._date(value)

    def _number_property(
        self,
        property_type: str | None,
        value: int | None,
    ) -> dict[str, Any] | None:
        if property_type != "number":
            return None
        return self._number(value)

    def _email_property(
        self,
        property_type: str | None,
        value: str | None,
    ) -> dict[str, Any] | None:
        if property_type != "email":
            return None
        return {"email": value or None}

    def _url_property(
        self,
        property_type: str | None,
        value: str | None,
    ) -> dict[str, Any] | None:
        if property_type != "url":
            return None
        return {"url": value or None}

    def _property_value(
        self,
        page: dict[str, Any],
        property_name: str,
    ) -> str | None:
        property_value = page.get("properties", {}).get(property_name)
        if not property_value:
            return None

        property_type = property_value.get("type")
        if property_type == "email":
            return self._clean_placeholder_value(property_value.get("email"))
        if property_type == "url":
            return self._clean_placeholder_value(property_value.get("url"))
        if property_type in {"rich_text", "title"}:
            return self._compose_rich_text(property_value.get(property_type, []))
        return None

    def _property_text(
        self,
        page: dict[str, Any],
        property_name: str,
    ) -> str | None:
        property_value = page.get("properties", {}).get(property_name)
        if not property_value:
            return None

        property_type = property_value.get("type")
        if property_type not in {"rich_text", "title"}:
            return None
        return self._compose_rich_text(property_value.get(property_type, []))

    def _property_option(
        self,
        page: dict[str, Any],
        property_name: str,
    ) -> str | None:
        property_value = page.get("properties", {}).get(property_name)
        if not property_value:
            return None

        property_type = property_value.get("type")
        if property_type == "select":
            selected = property_value.get("select")
            return selected.get("name") if selected else None
        if property_type == "status":
            status = property_value.get("status")
            return status.get("name") if status else None
        if property_type in {"rich_text", "title"}:
            return self._compose_rich_text(property_value.get(property_type, []))
        return None

    def _property_number(
        self,
        page: dict[str, Any],
        property_name: str,
    ) -> int | None:
        property_value = page.get("properties", {}).get(property_name)
        if not property_value or property_value.get("type") != "number":
            return None
        return property_value.get("number")

    def _property_date(
        self,
        page: dict[str, Any],
        property_name: str,
    ) -> str | None:
        property_value = page.get("properties", {}).get(property_name)
        if not property_value or property_value.get("type") != "date":
            return None
        date_value = property_value.get("date")
        if not date_value:
            return None
        return date_value.get("start")

    def _compose_rich_text(self, text_items: list[dict[str, Any]]) -> str | None:
        content = "".join(item.get("plain_text", "") for item in text_items).strip()
        return self._clean_placeholder_value(content)

    def _clean_placeholder_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.lower() in self.PLACEHOLDER_VALUES:
            return None
        return cleaned

    def _compose_notes(self, *parts: str | None) -> str | None:
        unique_parts: list[str] = []
        seen: set[str] = set()
        for part in parts:
            if not part or not part.strip():
                continue
            normalized = part.strip()
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_parts.append(normalized)
        if not unique_parts:
            return None
        return "\n".join(unique_parts)

    def _discovery_status_from_decision(self, decision: str | None) -> str:
        normalized = (decision or "").strip().lower()
        if normalized == "promote":
            return "promoted"
        if normalized == "reject":
            return "rejected"
        return "review"

    def _country_label(self, target_country: str | None) -> str:
        return country_label(target_country)
