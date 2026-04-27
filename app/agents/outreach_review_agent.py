from dataclasses import dataclass

from app.agents.crm_updater_agent import CRMUpdaterAgent
from app.agents.pipeline_intelligence_agent import PipelineIntelligenceAgent
from app.models.lead_feedback_signal import LeadFeedbackSignal
from app.models.pipeline_record import PipelineRecord
from app.services.notion_service import NotionService
from app.services.supabase_service import SupabaseService
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OutreachReviewSyncResult:
    reviewed_count: int = 0
    approved_count: int = 0
    sent_count: int = 0
    hold_count: int = 0
    replied_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0

    def summary(self) -> str:
        return (
            f"reviewed={self.reviewed_count}, approved={self.approved_count}, "
            f"sent={self.sent_count}, hold={self.hold_count}, "
            f"replied={self.replied_count}, skipped={self.skipped_count}, "
            f"failed={self.failed_count}"
        )


class OutreachReviewAgent:
    ACTIONABLE_QUEUE_STATUSES = {"approved", "sent", "hold", "replied"}
    POST_OUTREACH_STAGES = {"contacted", "replied", "callbooked", "proposal", "closed"}

    def __init__(
        self,
        notion_service: NotionService | None = None,
        supabase_service: SupabaseService | None = None,
        crm_updater_agent: CRMUpdaterAgent | None = None,
        pipeline_intelligence_agent: PipelineIntelligenceAgent | None = None,
    ) -> None:
        self.notion_service = notion_service or NotionService()
        self.supabase_service = supabase_service or SupabaseService()
        self.crm_updater_agent = crm_updater_agent or CRMUpdaterAgent()
        self.pipeline_intelligence_agent = (
            pipeline_intelligence_agent or PipelineIntelligenceAgent()
        )

    def is_configured(self) -> bool:
        return (
            self.notion_service.is_outreach_queue_configured()
            and self.supabase_service.is_configured()
        )

    def sync_queue_decisions(
        self,
        limit: int = 200,
    ) -> OutreachReviewSyncResult:
        result = OutreachReviewSyncResult()

        if not self.notion_service.is_outreach_queue_configured():
            logger.info("Outreach Queue is not configured. Skipping operator review sync.")
            return result

        if not self.supabase_service.is_configured():
            logger.info("Supabase is not configured. Skipping operator review sync.")
            return result

        signals = self.notion_service.fetch_outreach_queue_feedback_signals(limit=limit)
        actionable_signals = [
            signal
            for signal in signals
            if self._normalized_status(signal.queue_status)
            in self.ACTIONABLE_QUEUE_STATUSES
        ]
        result.reviewed_count = len(actionable_signals)
        if not actionable_signals:
            logger.info("No actionable outreach review decisions found.")
            return result

        for signal in actionable_signals:
            try:
                updated = self._apply_signal(signal)
            except Exception:
                logger.exception(
                    "Failed to apply outreach review signal for %s.",
                    signal.lead_reference or signal.company_name,
                )
                result.failed_count += 1
                continue

            if updated == "approved":
                result.approved_count += 1
            elif updated == "sent":
                result.sent_count += 1
            elif updated == "hold":
                result.hold_count += 1
            elif updated == "replied":
                result.replied_count += 1
            else:
                result.skipped_count += 1

        logger.info("Outreach review sync completed with %s.", result.summary())
        return result

    def _apply_signal(self, signal: LeadFeedbackSignal) -> str:
        if not signal.lead_reference:
            return "skipped"

        record = self.supabase_service.fetch_pipeline_record_by_lead_reference(
            signal.lead_reference
        )
        if record is None:
            return "skipped"

        normalized_status = self._normalized_status(signal.queue_status)
        if normalized_status == "approved":
            if self._should_skip_approved(record):
                return "skipped"
            updated_record = self.crm_updater_agent.update_outreach_status(
                record,
                "approved",
            )
            self._persist_pipeline_record(updated_record)
            return "approved"

        if normalized_status == "sent":
            if self._should_skip_sent(record):
                return "skipped"
            updated_record = self.crm_updater_agent.update_outreach_status(
                record,
                "sent",
            )
            updated_record = self.pipeline_intelligence_agent.evaluate_pipeline(
                [updated_record]
            )[0]
            self._persist_pipeline_record(updated_record)
            return "sent"

        if normalized_status == "hold":
            if self._should_skip_hold(record):
                return "skipped"
            updated_record = self.crm_updater_agent.log_activity(
                record,
                "Operator marked this outreach as Hold in Outreach Queue.",
            )
            updated_record = self.crm_updater_agent.set_next_action(
                updated_record,
                "operator_hold",
            )
            self._persist_pipeline_record(updated_record)
            return "hold"

        if normalized_status == "replied":
            # ResponseHandlerAgent runs later in the cycle and may also update
            # this record (with a more nuanced stage based on classification).
            # We only flip outreach_status + last_response_at here; the order
            # is irrelevant because both writes are idempotent on outreach_status
            # and ResponseHandlerAgent does its own stage logic.
            if self._should_skip_replied(record):
                return "skipped"
            updated_record = self.crm_updater_agent.update_outreach_status(
                record,
                "replied",
            )
            self._persist_pipeline_record(updated_record)
            return "replied"

        return "skipped"

    def _persist_pipeline_record(self, record: PipelineRecord) -> None:
        self.supabase_service.update_pipeline_record(record)
        if self.notion_service.is_configured():
            self.notion_service.upsert_pipeline_pages([record])

    def _should_skip_approved(self, record: PipelineRecord) -> bool:
        normalized_outreach_status = self._normalized_status(record.outreach_status)
        normalized_stage = self._normalized_status(record.stage)
        return (
            normalized_outreach_status in {"approved", "sent"}
            or normalized_stage in self.POST_OUTREACH_STAGES
        )

    def _should_skip_sent(self, record: PipelineRecord) -> bool:
        normalized_outreach_status = self._normalized_status(record.outreach_status)
        normalized_stage = self._normalized_status(record.stage)
        return (
            normalized_outreach_status == "sent"
            or normalized_stage in self.POST_OUTREACH_STAGES
        )

    def _should_skip_hold(self, record: PipelineRecord) -> bool:
        normalized_outreach_status = self._normalized_status(record.outreach_status)
        normalized_stage = self._normalized_status(record.stage)
        normalized_next_action = self._normalized_status(record.next_action)
        return (
            normalized_outreach_status == "sent"
            or normalized_stage in self.POST_OUTREACH_STAGES
            or normalized_next_action == "operatorhold"
        )

    def _should_skip_replied(self, record: PipelineRecord) -> bool:
        # Skip when the pipeline already reflects a reply (so re-running on
        # the same queue row, or running after ResponseHandlerAgent, is a
        # no-op) or when the deal has already been closed downstream.
        normalized_outreach_status = self._normalized_status(record.outreach_status)
        normalized_stage = self._normalized_status(record.stage)
        return (
            normalized_outreach_status == "replied"
            or normalized_stage == "closed"
        )

    def _normalized_status(self, value: str | None) -> str:
        if not value:
            return ""
        return "".join(character for character in value.lower() if character.isalnum())
