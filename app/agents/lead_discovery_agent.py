from dataclasses import dataclass
from dataclasses import field

from app.agents.lead_feedback_agent import LeadFeedbackAgent, LeadFeedbackIndex
from app.models.discovery_qualification import DiscoveryQualification
from app.services.notion_service import NotionService
from app.services.anthropic_service import AnthropicService
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DiscoveryPromotionResult:
    fetched_count: int = 0
    promoted_count: int = 0
    review_count: int = 0
    rejected_count: int = 0
    failed_count: int = 0
    fetched_count_by_lane: dict[str, int] = field(default_factory=dict)
    promoted_count_by_lane: dict[str, int] = field(default_factory=dict)
    review_count_by_lane: dict[str, int] = field(default_factory=dict)
    rejected_count_by_lane: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        base = (
            f"fetched={self.fetched_count}, promoted={self.promoted_count}, "
            f"review={self.review_count}, rejected={self.rejected_count}, "
            f"failed={self.failed_count}"
        )
        lane_parts: list[str] = []
        if self.fetched_count_by_lane:
            lane_parts.append(
                "fetched_lanes="
                + ", ".join(
                    f"{lane}={count}"
                    for lane, count in sorted(self.fetched_count_by_lane.items())
                )
            )
        if self.promoted_count_by_lane:
            lane_parts.append(
                "promoted_lanes="
                + ", ".join(
                    f"{lane}={count}"
                    for lane, count in sorted(self.promoted_count_by_lane.items())
                )
            )
        if self.review_count_by_lane:
            lane_parts.append(
                "review_lanes="
                + ", ".join(
                    f"{lane}={count}"
                    for lane, count in sorted(self.review_count_by_lane.items())
                )
            )
        if self.rejected_count_by_lane:
            lane_parts.append(
                "rejected_lanes="
                + ", ".join(
                    f"{lane}={count}"
                    for lane, count in sorted(self.rejected_count_by_lane.items())
                )
            )
        if not lane_parts:
            return base
        return base + " | " + " | ".join(lane_parts)


class LeadDiscoveryAgent:
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

    def __init__(
        self,
        notion_service: NotionService | None = None,
        anthropic_service: AnthropicService | None = None,
        lead_feedback_agent: LeadFeedbackAgent | None = None,
    ) -> None:
        self.notion_service = notion_service or NotionService()
        self.anthropic_service = anthropic_service or AnthropicService()
        self.lead_feedback_agent = lead_feedback_agent or LeadFeedbackAgent(
            notion_service=self.notion_service,
        )

    def is_configured(self) -> bool:
        return (
            self.notion_service.is_discovery_configured()
            and self.notion_service.is_intake_configured()
        )

    def promote_discovery_records(
        self,
        campaign: str,
        max_records: int = 20,
        feedback_index: LeadFeedbackIndex | None = None,
    ) -> DiscoveryPromotionResult:
        result = DiscoveryPromotionResult()

        if not self.notion_service.is_discovery_configured():
            logger.info(
                "Lead Discovery database is not configured. Skipping discovery promotion."
            )
            return result

        if not self.notion_service.is_intake_configured():
            logger.info(
                "Lead Intake database is not configured. Skipping discovery promotion."
            )
            return result

        discovery_records = self.notion_service.fetch_lead_discovery_records(
            limit=max_records
        )
        result.fetched_count = len(discovery_records)
        for record in discovery_records:
            lane = record.lane_label or "Unlabeled"
            result.fetched_count_by_lane[lane] = (
                result.fetched_count_by_lane.get(lane, 0) + 1
            )
        if not discovery_records:
            logger.info("No ready discovery records found in Notion.")
            return result

        for discovery_record in discovery_records:
            try:
                qualification = self._qualify_discovery_record(
                    discovery_record,
                    campaign=campaign,
                )
                qualification = self._apply_feedback(
                    discovery_record,
                    qualification,
                    feedback_index,
                )
                qualification = self._apply_operator_readiness_gate(qualification)
                self._apply_qualification(discovery_record, qualification, result)
            except Exception as exc:
                logger.exception(
                    "Discovery qualification failed for page %s.",
                    discovery_record.page_id,
                )
                result.failed_count += 1
                self._mark_failed(discovery_record, str(exc))

        logger.info(
            "Lead discovery promotion completed with %s.",
            result.summary(),
        )
        return result

    def _qualify_discovery_record(
        self,
        discovery_record,
        campaign: str,
    ) -> DiscoveryQualification:
        if self.anthropic_service.is_configured():
            try:
                return self.anthropic_service.qualify_discovery_record(
                    discovery_record,
                    campaign=campaign,
                )
            except Exception:
                logger.warning(
                    "Anthropic discovery qualification failed for page %s. Falling back to deterministic qualification.",
                    discovery_record.page_id,
                )

        return self.anthropic_service.build_discovery_qualification_fallback(
            discovery_record,
            campaign=campaign,
        )

    def _apply_feedback(
        self,
        discovery_record,
        qualification: DiscoveryQualification,
        feedback_index: LeadFeedbackIndex | None,
    ) -> DiscoveryQualification:
        if feedback_index is None:
            return qualification

        lead_reference = self.lead_feedback_agent.build_lead_reference(qualification.lead)
        signal = self.lead_feedback_agent.signal_for_reference(
            feedback_index,
            lead_reference=lead_reference,
            company_name=qualification.lead.company_name or discovery_record.company_name,
        )
        if signal is None or not signal.blocks_duplicate_outreach():
            return qualification

        qualification_notes = self._merge_notes(
            qualification.qualification_notes,
            f"Existing sales activity detected: {signal.summary()}.",
        )
        return qualification.model_copy(
            update={
                "decision": "review",
                "qualification_notes": qualification_notes,
            }
        )

    def _apply_operator_readiness_gate(
        self,
        qualification: DiscoveryQualification,
    ) -> DiscoveryQualification:
        if qualification.decision != "promote":
            return qualification

        has_contact = self._has_known_buyer_value(qualification.lead.contact_name)
        has_role = self._has_known_buyer_value(qualification.lead.contact_role)
        if has_contact or has_role:
            return qualification

        qualification_notes = self._merge_notes(
            qualification.qualification_notes,
            "Auto-promotion blocked because buyer identity is still unknown.",
        )
        return qualification.model_copy(
            update={
                "decision": "review",
                "qualification_notes": qualification_notes,
            }
        )

    def _has_known_buyer_value(self, value: str | None) -> bool:
        if value is None:
            return False
        cleaned = value.strip().lower()
        return bool(cleaned) and cleaned not in self.PLACEHOLDER_VALUES

    def _merge_notes(self, *parts: str | None) -> str | None:
        values = [part.strip() for part in parts if part and part.strip()]
        if not values:
            return None
        return " ".join(values)

    def _apply_qualification(
        self,
        discovery_record,
        qualification: DiscoveryQualification,
        result: DiscoveryPromotionResult,
    ) -> None:
        lane = discovery_record.lane_label or "Unlabeled"
        if qualification.decision == "promote":
            self.notion_service.upsert_intake_page_from_discovery(
                qualification.lead,
                discovery_record,
                qualification,
            )
            result.promoted_count += 1
            result.promoted_count_by_lane[lane] = (
                result.promoted_count_by_lane.get(lane, 0) + 1
            )
        elif qualification.decision == "reject":
            result.rejected_count += 1
            result.rejected_count_by_lane[lane] = (
                result.rejected_count_by_lane.get(lane, 0) + 1
            )
        else:
            result.review_count += 1
            result.review_count_by_lane[lane] = (
                result.review_count_by_lane.get(lane, 0) + 1
            )

        self._mark_processed(discovery_record, qualification)

    def _mark_processed(
        self,
        discovery_record,
        qualification: DiscoveryQualification,
    ) -> None:
        try:
            self.notion_service.mark_lead_discovery_record_processed(
                discovery_record,
                qualification,
            )
        except Exception:
            logger.warning(
                "Failed to update discovery page %s after qualification.",
                discovery_record.page_id,
            )

    def _mark_failed(self, discovery_record, error_message: str) -> None:
        try:
            self.notion_service.mark_lead_discovery_record_failed(
                discovery_record,
                error_message,
            )
        except Exception:
            logger.warning(
                "Failed to update discovery page %s after error.",
                discovery_record.page_id,
            )
