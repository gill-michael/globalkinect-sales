from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.crm_updater_agent import CRMUpdaterAgent
from app.agents.execution_agent import ExecutionAgent
from app.agents.lead_scoring_agent import LeadScoringAgent
from app.agents.lifecycle_agent import LifecycleAgent
from app.agents.message_writer_agent import MessageWriterAgent
from app.agents.notion_sync_agent import NotionSyncAgent
from app.agents.pipeline_intelligence_agent import PipelineIntelligenceAgent
from app.agents.proposal_support_agent import ProposalSupportAgent
from app.agents.solution_design_agent import SolutionDesignAgent
from app.models.deal_support_package import DealSupportPackage
from app.models.execution_task import ExecutionTask
from app.models.lead import Lead
from app.models.outreach_message import OutreachMessage
from app.models.pipeline_record import PipelineRecord
from app.models.solution_recommendation import SolutionRecommendation
from app.services.config import settings
from app.services.supabase_service import SupabaseService
from app.utils.logger import get_logger
from app.utils.time import utc_now

logger = get_logger(__name__)

INTEGRATION_TEST_PREFIX = "INTEGRATION_TEST"


@dataclass
class EnvironmentValidationResult:
    checks: dict[str, bool]

    @property
    def supabase_ready(self) -> bool:
        return self.checks["SUPABASE_URL"] and self.checks["SUPABASE_PUBLISHABLE_KEY"]

    @property
    def notion_ready(self) -> bool:
        required_keys = {
            "NOTION_API_KEY",
            "NOTION_LEADS_DATABASE_ID",
            "NOTION_PIPELINE_DATABASE_ID",
            "NOTION_SOLUTIONS_DATABASE_ID",
            "NOTION_TASKS_DATABASE_ID",
            "NOTION_DEAL_SUPPORT_DATABASE_ID",
        }
        return all(self.checks[key] for key in required_keys)

    @property
    def cleanup_ready(self) -> bool:
        return self.checks["DATABASE_URL"]

    def missing(self, keys: list[str]) -> list[str]:
        return [key for key in keys if not self.checks.get(key, False)]


@dataclass
class FlowArtifacts:
    leads: list[Lead]
    outreach_messages: list[OutreachMessage]
    pipeline_records: list[PipelineRecord]
    solution_recommendations: list[SolutionRecommendation]
    execution_tasks: list[ExecutionTask]
    deal_support_packages: list[DealSupportPackage]

    def counts(self) -> dict[str, int]:
        return {
            "leads": len(self.leads),
            "outreach_messages": len(self.outreach_messages),
            "pipeline_records": len(self.pipeline_records),
            "solution_recommendations": len(self.solution_recommendations),
            "execution_tasks": len(self.execution_tasks),
            "deal_support_packages": len(self.deal_support_packages),
        }

    def lead_references(self) -> list[str]:
        return [record.lead_reference for record in self.pipeline_records]


@dataclass
class SupabaseValidationResult:
    configured: bool
    insert_success: bool = False
    fetch_success: bool = False
    persisted_counts: dict[str, int] = field(default_factory=dict)
    fetched_counts: dict[str, int] = field(default_factory=dict)
    error: str | None = None


@dataclass
class NotionValidationResult:
    configured: bool
    sync_success: bool = False
    synced_counts: dict[str, int] = field(default_factory=dict)
    page_ids: dict[str, list[str]] = field(default_factory=dict)
    error: str | None = None


@dataclass
class CleanupResult:
    requested: bool
    marker: str
    success: bool = False
    deleted_counts: dict[str, int] = field(default_factory=dict)
    manual_notion_cleanup_required: bool = True
    error: str | None = None


@dataclass
class IntegrationCheckResult:
    run_marker: str
    environment: EnvironmentValidationResult
    generated_counts: dict[str, int] = field(default_factory=dict)
    lead_references: list[str] = field(default_factory=list)
    supabase: SupabaseValidationResult = field(
        default_factory=lambda: SupabaseValidationResult(configured=False)
    )
    notion: NotionValidationResult = field(
        default_factory=lambda: NotionValidationResult(configured=False)
    )
    failed_steps: list[str] = field(default_factory=list)

    @property
    def is_fully_integration_ready(self) -> bool:
        return (
            self.supabase.configured
            and self.supabase.insert_success
            and self.supabase.fetch_success
            and self.notion.configured
            and self.notion.sync_success
            and not self.failed_steps
        )


class IntegrationCheckRunner:
    def __init__(
        self,
        supabase_service: SupabaseService | None = None,
        notion_sync_agent: NotionSyncAgent | None = None,
        lead_scoring_agent: LeadScoringAgent | None = None,
        solution_design_agent: SolutionDesignAgent | None = None,
        crm_updater_agent: CRMUpdaterAgent | None = None,
        message_writer_agent: MessageWriterAgent | None = None,
        pipeline_intelligence_agent: PipelineIntelligenceAgent | None = None,
        lifecycle_agent: LifecycleAgent | None = None,
        execution_agent: ExecutionAgent | None = None,
        proposal_support_agent: ProposalSupportAgent | None = None,
        database_url: str | None = None,
    ) -> None:
        self.supabase_service = supabase_service or SupabaseService()
        self.notion_sync_agent = notion_sync_agent or NotionSyncAgent()
        self.lead_scoring_agent = lead_scoring_agent or LeadScoringAgent()
        self.solution_design_agent = solution_design_agent or SolutionDesignAgent()
        self.crm_updater_agent = crm_updater_agent or CRMUpdaterAgent()
        self.message_writer_agent = message_writer_agent or MessageWriterAgent()
        self.pipeline_intelligence_agent = (
            pipeline_intelligence_agent or PipelineIntelligenceAgent()
        )
        self.lifecycle_agent = lifecycle_agent or LifecycleAgent()
        self.execution_agent = execution_agent or ExecutionAgent()
        self.proposal_support_agent = (
            proposal_support_agent or ProposalSupportAgent()
        )
        self.database_url = (
            settings.DATABASE_URL.strip()
            if database_url is None
            else database_url.strip()
        )

    def validate_environment(self) -> EnvironmentValidationResult:
        checks = {
            "DATABASE_URL": bool(settings.DATABASE_URL.strip()),
            "SUPABASE_URL": bool(settings.SUPABASE_URL.strip()),
            "SUPABASE_PUBLISHABLE_KEY": bool(settings.SUPABASE_PUBLISHABLE_KEY.strip()),
            "NOTION_API_KEY": bool(settings.NOTION_API_KEY.strip()),
            "NOTION_LEADS_DATABASE_ID": bool(
                settings.NOTION_LEADS_DATABASE_ID.strip()
            ),
            "NOTION_PIPELINE_DATABASE_ID": bool(
                settings.NOTION_PIPELINE_DATABASE_ID.strip()
            ),
            "NOTION_SOLUTIONS_DATABASE_ID": bool(
                settings.NOTION_SOLUTIONS_DATABASE_ID.strip()
            ),
            "NOTION_TASKS_DATABASE_ID": bool(
                settings.NOTION_TASKS_DATABASE_ID.strip()
            ),
            "NOTION_DEAL_SUPPORT_DATABASE_ID": bool(
                settings.NOTION_DEAL_SUPPORT_DATABASE_ID.strip()
            ),
        }
        return EnvironmentValidationResult(checks=checks)

    def build_test_leads(self, run_marker: str) -> list[Lead]:
        safe_marker = self.normalize_run_marker(run_marker)
        return [
            Lead(
                company_name=f"{safe_marker}_Global Kinect_Payroll_Example",
                contact_name="Integration Jane",
                contact_role="Head of People",
                email="integration-jane@example.com",
                linkedin_url="https://www.linkedin.com/in/integration-jane",
                company_country="United Kingdom",
                target_country="Saudi Arabia",
                lead_type="direct_payroll",
                fit_reason="Deterministic integration validation lead for payroll flow.",
            ),
            Lead(
                company_name=f"{safe_marker}_Global Kinect_Partner_Example",
                contact_name="Integration Omar",
                contact_role="Managing Director",
                email="integration-omar@example.com",
                linkedin_url="https://www.linkedin.com/in/integration-omar",
                company_country="Germany",
                target_country="United Arab Emirates",
                lead_type="recruitment_partner",
                fit_reason="Deterministic integration validation lead for partner flow.",
            ),
        ]

    def run(self, run_marker: str | None = None) -> IntegrationCheckResult:
        effective_marker = self.normalize_run_marker(run_marker)
        environment = self.validate_environment()
        result = IntegrationCheckResult(
            run_marker=effective_marker,
            environment=environment,
            supabase=SupabaseValidationResult(
                configured=self.supabase_service.is_configured()
            ),
            notion=NotionValidationResult(
                configured=self.notion_sync_agent.is_configured()
            ),
        )

        try:
            artifacts = self._build_flow_artifacts(effective_marker)
        except Exception as exc:
            logger.exception("Integration check flow generation failed.")
            result.failed_steps.append("flow_generation")
            result.generated_counts = {}
            result.supabase.error = result.supabase.error or "Skipped because flow generation failed."
            result.notion.error = result.notion.error or "Skipped because flow generation failed."
            result.failed_steps.append(str(exc))
            return result

        result.generated_counts = artifacts.counts()
        result.lead_references = artifacts.lead_references()
        result.supabase = self._validate_supabase(artifacts, effective_marker)
        if result.supabase.error:
            result.failed_steps.append("supabase")
        result.notion = self._validate_notion(artifacts)
        if result.notion.error:
            result.failed_steps.append("notion")
        return result

    def cleanup(self, run_marker: str | None = None) -> CleanupResult:
        effective_marker = self.normalize_run_marker(
            run_marker,
            allow_prefix_only=True,
        )
        result = CleanupResult(requested=True, marker=effective_marker)

        if not self.database_url:
            result.error = (
                "DATABASE_URL is not configured. Cleanup requires a direct Postgres connection string."
            )
            return result

        try:
            import psycopg
        except ImportError:
            result.error = (
                "psycopg is not installed. Cleanup requires the migration database dependency."
            )
            return result

        pattern = f"%{effective_marker}%"
        delete_statements = [
            ("execution_tasks", "delete from execution_tasks where lead_reference like %s;"),
            (
                "deal_support_packages",
                "delete from deal_support_packages where lead_reference like %s;",
            ),
            (
                "pipeline_records",
                "delete from pipeline_records where lead_reference like %s;",
            ),
            (
                "solution_recommendations",
                "delete from solution_recommendations where lead_reference like %s;",
            ),
            (
                "outreach_messages",
                "delete from outreach_messages where lead_reference like %s;",
            ),
            ("leads", "delete from leads where company_name like %s;"),
        ]

        try:
            with psycopg.connect(self.database_url) as conn:
                with conn.cursor() as cursor:
                    for table_name, statement in delete_statements:
                        cursor.execute(statement, (pattern,))
                        result.deleted_counts[table_name] = cursor.rowcount
            result.success = True
            return result
        except Exception as exc:
            logger.exception("Integration cleanup failed.")
            result.error = f"Cleanup failed: {exc}"
            return result

    def normalize_run_marker(
        self,
        run_marker: str | None,
        allow_prefix_only: bool = False,
    ) -> str:
        if run_marker:
            cleaned = run_marker.strip().replace(" ", "_")
            if cleaned.startswith(INTEGRATION_TEST_PREFIX):
                return cleaned
            return f"{INTEGRATION_TEST_PREFIX}_{cleaned}"

        if allow_prefix_only:
            return INTEGRATION_TEST_PREFIX

        timestamp = utc_now().strftime("%Y%m%d%H%M%S")
        return f"{INTEGRATION_TEST_PREFIX}_{timestamp}"

    def _build_flow_artifacts(self, run_marker: str) -> FlowArtifacts:
        leads = self.build_test_leads(run_marker)
        scored_leads = self.lead_scoring_agent.score_leads(leads)
        solution_recommendations = (
            self.solution_design_agent.create_solution_recommendations(scored_leads)
        )
        pipeline_records = self.crm_updater_agent.create_pipeline_records_with_solution(
            scored_leads,
            solution_recommendations,
        )
        outreach_messages = self.message_writer_agent.generate_messages_with_solution(
            scored_leads,
            solution_recommendations,
        )
        sent_records = [
            self.crm_updater_agent.update_outreach_status(record, "sent")
            for record in pipeline_records
        ]
        evaluated_records = self.pipeline_intelligence_agent.evaluate_pipeline(
            sent_records
        )
        lifecycle_records = self.lifecycle_agent.evaluate_lifecycle(evaluated_records)
        execution_tasks = self.execution_agent.generate_tasks(lifecycle_records)
        deal_support_packages = (
            self.proposal_support_agent.create_deal_support_packages_with_solution(
                scored_leads,
                lifecycle_records,
                solution_recommendations,
            )
        )

        return FlowArtifacts(
            leads=scored_leads,
            outreach_messages=outreach_messages,
            pipeline_records=lifecycle_records,
            solution_recommendations=solution_recommendations,
            execution_tasks=execution_tasks,
            deal_support_packages=deal_support_packages,
        )

    def _validate_supabase(
        self,
        artifacts: FlowArtifacts,
        marker: str,
    ) -> SupabaseValidationResult:
        result = SupabaseValidationResult(
            configured=self.supabase_service.is_configured()
        )
        if not result.configured:
            result.error = "Supabase service is not configured."
            return result

        try:
            self.supabase_service.insert_leads(artifacts.leads)
            self.supabase_service.insert_outreach_messages(
                artifacts.outreach_messages
            )
            self.supabase_service.insert_pipeline_records(
                artifacts.pipeline_records
            )
            self.supabase_service.insert_solution_recommendations(
                artifacts.solution_recommendations
            )
            self.supabase_service.insert_deal_support_packages(
                artifacts.deal_support_packages
            )
            self.supabase_service.insert_execution_tasks(
                artifacts.execution_tasks
            )
            result.insert_success = True
            result.persisted_counts = artifacts.counts()
        except Exception as exc:
            logger.exception("Supabase insert validation failed.")
            result.error = f"Supabase insert validation failed: {exc}"
            return result

        try:
            result.fetched_counts = {
                "leads": self._fetch_supabase_marker_count(
                    self.supabase_service.TABLE_LEADS,
                    "company_name",
                    marker,
                ),
                "outreach_messages": self._fetch_supabase_marker_count(
                    self.supabase_service.TABLE_OUTREACH_MESSAGES,
                    "lead_reference",
                    marker,
                ),
                "pipeline_records": self._fetch_supabase_marker_count(
                    self.supabase_service.TABLE_PIPELINE_RECORDS,
                    "lead_reference",
                    marker,
                ),
                "solution_recommendations": self._fetch_supabase_marker_count(
                    self.supabase_service.TABLE_SOLUTION_RECOMMENDATIONS,
                    "lead_reference",
                    marker,
                ),
                "deal_support_packages": self._fetch_supabase_marker_count(
                    self.supabase_service.TABLE_DEAL_SUPPORT_PACKAGES,
                    "lead_reference",
                    marker,
                ),
                "execution_tasks": self._fetch_supabase_marker_count(
                    self.supabase_service.TABLE_EXECUTION_TASKS,
                    "lead_reference",
                    marker,
                ),
            }
            result.fetch_success = all(
                result.fetched_counts[key] >= artifacts.counts()[key]
                for key in artifacts.counts()
            )
            if not result.fetch_success:
                result.error = (
                    "Supabase fetch validation did not return the expected test rows."
                )
            return result
        except Exception as exc:
            logger.exception("Supabase fetch validation failed.")
            result.error = f"Supabase fetch validation failed: {exc}"
            return result

    def _validate_notion(
        self,
        artifacts: FlowArtifacts,
    ) -> NotionValidationResult:
        result = NotionValidationResult(
            configured=self.notion_sync_agent.is_configured()
        )
        if not result.configured:
            result.error = "Notion sync agent is not configured."
            return result

        try:
            sync_result = self.notion_sync_agent.sync_operating_views(
                leads=artifacts.leads,
                pipeline_records=artifacts.pipeline_records,
                solution_recommendations=artifacts.solution_recommendations,
                execution_tasks=artifacts.execution_tasks,
                deal_support_packages=artifacts.deal_support_packages,
            )
            result.sync_success = True
            result.synced_counts = {
                key: len(value)
                for key, value in sync_result.items()
            }
            result.page_ids = {
                key: [page["id"] for page in value if "id" in page]
                for key, value in sync_result.items()
            }
            return result
        except Exception as exc:
            logger.exception("Notion sync validation failed.")
            result.error = f"Notion sync validation failed: {exc}"
            return result

    def _fetch_supabase_marker_count(
        self,
        table_name: str,
        field_name: str,
        marker: str,
    ) -> int:
        response = (
            self.supabase_service.client.table(table_name)
            .select("*")
            .like(field_name, f"%{marker}%")
            .limit(20)
            .execute()
        )
        data = self._response_data(response)
        return len(data)

    def _response_data(self, response: Any) -> list[dict[str, Any]]:
        if isinstance(response, dict):
            data = response.get("data")
            return data if isinstance(data, list) else []

        data = getattr(response, "data", None)
        return data if isinstance(data, list) else []


def format_integration_check_report(result: IntegrationCheckResult) -> str:
    lines = [
        "Integration Check Summary",
        f"Run marker: {result.run_marker}",
        "",
        "Environment",
    ]
    for key, present in result.environment.checks.items():
        lines.append(f"- {key}: {'present' if present else 'missing'}")

    lines.extend(
        [
            "",
            "Generated Records",
        ]
    )
    for key, count in result.generated_counts.items():
        lines.append(f"- {key}: {count}")

    if result.lead_references:
        lines.append(f"- sample lead reference: {result.lead_references[0]}")

    lines.extend(
        [
            "",
            "Supabase",
            f"- configured: {'yes' if result.supabase.configured else 'no'}",
            f"- insert success: {'yes' if result.supabase.insert_success else 'no'}",
            f"- fetch success: {'yes' if result.supabase.fetch_success else 'no'}",
        ]
    )
    for key, count in result.supabase.persisted_counts.items():
        lines.append(f"- persisted {key}: {count}")
    for key, count in result.supabase.fetched_counts.items():
        lines.append(f"- fetched {key}: {count}")
    if result.supabase.error:
        lines.append(f"- error: {result.supabase.error}")

    lines.extend(
        [
            "",
            "Notion",
            f"- configured: {'yes' if result.notion.configured else 'no'}",
            f"- sync success: {'yes' if result.notion.sync_success else 'no'}",
        ]
    )
    for key, count in result.notion.synced_counts.items():
        lines.append(f"- synced {key}: {count}")
    for key, page_ids in result.notion.page_ids.items():
        if page_ids:
            lines.append(f"- {key} page ids: {', '.join(page_ids)}")
    if result.notion.error:
        lines.append(f"- error: {result.notion.error}")

    lines.extend(
        [
            "",
            "Overall",
            (
                "- fully integration-ready: yes"
                if result.is_fully_integration_ready
                else "- fully integration-ready: no"
            ),
        ]
    )
    if result.failed_steps:
        lines.append(f"- failed steps: {', '.join(result.failed_steps)}")

    return "\n".join(lines)


def format_cleanup_report(result: CleanupResult) -> str:
    lines = [
        "Integration Cleanup Summary",
        f"Marker: {result.marker}",
        f"- cleanup success: {'yes' if result.success else 'no'}",
    ]
    for key, count in result.deleted_counts.items():
        lines.append(f"- deleted {key}: {count}")
    if result.error:
        lines.append(f"- error: {result.error}")
    if result.manual_notion_cleanup_required:
        lines.append(
            "- notion cleanup: manual only. Remove pages whose titles contain the integration marker."
        )
    return "\n".join(lines)
