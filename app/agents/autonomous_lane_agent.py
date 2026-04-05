import hashlib
from dataclasses import dataclass
from dataclasses import field

from app.models.discovery_candidate import DiscoveryCandidate
from app.models.operator_console import OutreachQueueRecord
from app.services.notion_service import NotionService
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class AutonomousLaneSeedingResult:
    candidate_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    candidate_count_by_lane: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        base = (
            f"candidates={self.candidate_count}, created={self.created_count}, "
            f"updated={self.updated_count}, skipped={self.skipped_count}, "
            f"failed={self.failed_count}"
        )
        if not self.candidate_count_by_lane:
            return base
        lanes = ", ".join(
            f"{lane}={count}"
            for lane, count in sorted(self.candidate_count_by_lane.items())
        )
        return f"{base} | lanes={lanes}"


class AutonomousLaneAgent:
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

    def __init__(self, notion_service: NotionService | None = None) -> None:
        self.notion_service = notion_service or NotionService()

    def is_configured(self) -> bool:
        return self.notion_service.is_discovery_configured()

    def seed_internal_lanes(self, limit: int = 100) -> AutonomousLaneSeedingResult:
        result = AutonomousLaneSeedingResult()
        if not self.is_configured():
            return result

        candidates: list[DiscoveryCandidate] = []
        if self.notion_service.is_discovery_configured():
            candidates.extend(self._build_buyer_mapping_candidates_from_discovery(limit=limit))
        if self.notion_service.is_intake_configured():
            candidates.extend(self._build_buyer_mapping_candidates_from_intake(limit=limit))
        if self.notion_service.is_outreach_queue_configured():
            candidates.extend(self._build_reactivation_candidates(limit=limit))

        deduped: dict[str, DiscoveryCandidate] = {}
        for candidate in candidates:
            deduped[candidate.discovery_key or self._fallback_key(candidate)] = candidate
        final_candidates = list(deduped.values())

        result.candidate_count = len(final_candidates)
        for candidate in final_candidates:
            lane = candidate.lane_label or "Unlabeled"
            result.candidate_count_by_lane[lane] = (
                result.candidate_count_by_lane.get(lane, 0) + 1
            )
            try:
                sync_result = self.notion_service.sync_discovery_candidate_page(candidate)
            except Exception:
                logger.exception(
                    "Failed to sync autonomous lane candidate for %s.",
                    candidate.company_name,
                )
                result.failed_count += 1
                continue

            if sync_result == "created":
                result.created_count += 1
            elif sync_result == "updated":
                result.updated_count += 1
            else:
                result.skipped_count += 1

        if result.candidate_count:
            logger.info("Autonomous lane seeding completed with %s.", result.summary())
        return result

    def _build_buyer_mapping_candidates_from_discovery(self, limit: int) -> list[DiscoveryCandidate]:
        records = self.notion_service.list_lead_discovery_records(limit=limit)
        candidates: list[DiscoveryCandidate] = []
        for record in records:
            if (record.lane_label or "").strip().lower() == "buyer mapping":
                continue
            if not self._needs_buyer_mapping(
                contact_name=record.contact_name,
                contact_role=record.contact_role,
                buyer_confidence=record.buyer_confidence,
            ):
                continue
            if not record.target_country_hint:
                continue
            candidates.append(
                DiscoveryCandidate(
                    company_name=record.company_name,
                    agent_label="Buyer Mapping Agent",
                    lane_label="Buyer Mapping",
                    discovery_key=self._build_key(
                        record.company_name,
                        "buyer_mapping",
                        record.target_country_hint,
                        record.page_id,
                    ),
                    website_url=record.website_url,
                    source_url=record.source_url,
                    source_type="internal_buyer_mapping",
                    service_focus=record.service_focus,
                    evidence=(
                        f"Buyer mapping follow-up for {record.company_name} in "
                        f"{record.target_country_hint}. Existing discovery lacks a strong buyer."
                    ),
                    company_country=record.company_country,
                    target_country_hint=record.target_country_hint,
                    buyer_confidence=record.buyer_confidence,
                    account_fit_summary=record.account_fit_summary,
                    campaign=record.campaign,
                    notes=self._compose_internal_notes(
                        f"Source discovery page: {record.page_id}",
                        f"Origin lane: {record.lane_label}" if record.lane_label else None,
                        f"Origin source URL: {record.source_url}" if record.source_url else None,
                        record.notes,
                    ),
                    status="ready",
                )
            )
        return candidates

    def _build_buyer_mapping_candidates_from_intake(self, limit: int) -> list[DiscoveryCandidate]:
        records = self.notion_service.list_lead_intake_records(limit=limit)
        candidates: list[DiscoveryCandidate] = []
        for record in records:
            if (record.lane_label or "").strip().lower() == "buyer mapping":
                continue
            if not self._needs_buyer_mapping(
                contact_name=record.contact_name,
                contact_role=record.contact_role,
                buyer_confidence=record.buyer_confidence,
            ):
                continue
            if not record.target_country:
                continue
            candidates.append(
                DiscoveryCandidate(
                    company_name=record.company_name,
                    agent_label="Buyer Mapping Agent",
                    lane_label="Buyer Mapping",
                    discovery_key=self._build_key(
                        record.company_name,
                        "buyer_mapping",
                        record.target_country,
                        record.page_id,
                    ),
                    source_type="internal_buyer_mapping",
                    service_focus=record.lead_type_hint,
                    evidence=(
                        f"Buyer mapping follow-up for intake record {record.company_name} "
                        f"in {record.target_country}. Buyer confidence is still low."
                    ),
                    email=record.email,
                    linkedin_url=record.linkedin_url,
                    company_country=record.company_country,
                    target_country_hint=record.target_country,
                    buyer_confidence=record.buyer_confidence,
                    account_fit_summary=record.account_fit_summary,
                    campaign=record.campaign,
                    notes=self._compose_internal_notes(
                        f"Source intake page: {record.page_id}",
                        f"Origin lane: {record.lane_label}" if record.lane_label else None,
                        record.notes,
                    ),
                    status="ready",
                )
            )
        return candidates

    def _build_reactivation_candidates(self, limit: int) -> list[DiscoveryCandidate]:
        records = self.notion_service.list_outreach_queue_records(limit=limit)
        candidates: list[DiscoveryCandidate] = []
        for record in records:
            if self._normalize(record.status) != "hold":
                continue
            if not record.company_name or not record.target_country:
                continue
            candidates.append(
                DiscoveryCandidate(
                    company_name=record.company_name,
                    agent_label="Reactivation Agent",
                    lane_label="Reactivation",
                    discovery_key=self._build_key(
                        record.company_name,
                        "reactivation",
                        record.target_country,
                        record.lead_reference,
                    ),
                    source_type="internal_reactivation",
                    service_focus=self._normalize_service_focus(record.primary_module),
                    evidence=(
                        f"Reactivation follow-up for held queue item {record.lead_reference}. "
                        f"Review whether timing, buyer, or value prop should be revisited."
                    ),
                    contact_name=record.contact_name,
                    contact_role=record.contact_role,
                    target_country_hint=record.target_country,
                    campaign="Pipeline reactivation",
                    notes=self._compose_internal_notes(
                        f"Outreach queue status: {record.status}",
                        record.notes,
                    ),
                    status="ready",
                )
            )
        return candidates

    def _needs_buyer_mapping(
        self,
        *,
        contact_name: str | None,
        contact_role: str | None,
        buyer_confidence: int | None,
    ) -> bool:
        if buyer_confidence is not None and buyer_confidence >= 7:
            return False
        return not (
            self._has_known_value(contact_name)
            and self._has_known_value(contact_role)
        )

    def _has_known_value(self, value: str | None) -> bool:
        normalized = self._normalize(value)
        return bool(normalized) and normalized not in self.PLACEHOLDER_VALUES

    def _normalize(self, value: str | None) -> str:
        return (value or "").strip().lower()

    def _compose_internal_notes(self, *parts: str | None) -> str | None:
        values = [part.strip() for part in parts if part and part.strip()]
        if not values:
            return None
        return "\n".join(values)

    def _normalize_service_focus(self, primary_module: str | None) -> str | None:
        normalized = self._normalize(primary_module)
        if normalized == "eor":
            return "eor"
        if normalized == "payroll":
            return "payroll"
        if normalized == "hris":
            return "hris"
        return None

    def _build_key(
        self,
        company_name: str,
        lane_label: str,
        target_country: str | None,
        seed_value: str | None,
    ) -> str:
        seed = "|".join(
            [
                company_name.strip().lower(),
                lane_label.strip().lower(),
                (target_country or "").strip().lower(),
                (seed_value or "").strip().lower(),
            ]
        )
        return hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]

    def _fallback_key(self, candidate: DiscoveryCandidate) -> str:
        return "|".join(
            [
                candidate.company_name.strip().lower(),
                (candidate.lane_label or "").strip().lower(),
                (candidate.target_country_hint or "").strip().lower(),
            ]
        )
