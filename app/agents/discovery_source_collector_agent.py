from dataclasses import dataclass
from dataclasses import field

from app.services.discovery_source_service import DiscoverySourceService
from app.services.notion_service import NotionService
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DiscoverySourceCollectionResult:
    source_count: int = 0
    candidate_count: int = 0
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    candidate_count_by_lane: dict[str, int] = field(default_factory=dict)
    created_count_by_lane: dict[str, int] = field(default_factory=dict)
    updated_count_by_lane: dict[str, int] = field(default_factory=dict)

    def summary(self) -> str:
        base = (
            f"sources={self.source_count}, candidates={self.candidate_count}, "
            f"created={self.created_count}, updated={self.updated_count}, "
            f"skipped={self.skipped_count}, failed={self.failed_count}"
        )
        lane_bits: list[str] = []
        if self.candidate_count_by_lane:
            lane_bits.append(
                "candidate_lanes="
                + ", ".join(
                    f"{lane}={count}"
                    for lane, count in sorted(self.candidate_count_by_lane.items())
                )
            )
        if self.created_count_by_lane:
            lane_bits.append(
                "created_lanes="
                + ", ".join(
                    f"{lane}={count}"
                    for lane, count in sorted(self.created_count_by_lane.items())
                )
            )
        if self.updated_count_by_lane:
            lane_bits.append(
                "updated_lanes="
                + ", ".join(
                    f"{lane}={count}"
                    for lane, count in sorted(self.updated_count_by_lane.items())
                )
            )
        if not lane_bits:
            return base
        return base + " | " + " | ".join(lane_bits)


class DiscoverySourceCollectorAgent:
    def __init__(
        self,
        notion_service: NotionService | None = None,
        discovery_source_service: DiscoverySourceService | None = None,
    ) -> None:
        self.notion_service = notion_service or NotionService()
        self.discovery_source_service = (
            discovery_source_service or DiscoverySourceService()
        )

    def is_configured(self) -> bool:
        return (
            self.notion_service.is_discovery_configured()
            and self.discovery_source_service.is_configured()
        )

    def collect_into_discovery(
        self,
        campaign: str,
    ) -> DiscoverySourceCollectionResult:
        result = DiscoverySourceCollectionResult()

        if not self.notion_service.is_discovery_configured():
            logger.info(
                "Lead Discovery database is not configured. Skipping source collection."
            )
            return result

        if not self.discovery_source_service.is_configured():
            logger.info(
                "Discovery source collection is not configured. Skipping source collection."
            )
            return result

        sources, candidates = self.discovery_source_service.collect_candidates(
            campaign=campaign,
        )
        result.source_count = len(sources)
        result.candidate_count = len(candidates)
        for candidate in candidates:
            lane = candidate.lane_label or "Unlabeled"
            result.candidate_count_by_lane[lane] = (
                result.candidate_count_by_lane.get(lane, 0) + 1
            )

        for candidate in candidates:
            try:
                sync_result = self.notion_service.sync_discovery_candidate_page(candidate)
            except Exception:
                logger.exception(
                    "Failed to sync discovery candidate for %s.",
                    candidate.company_name,
                )
                result.failed_count += 1
                continue

            if sync_result == "created":
                result.created_count += 1
                lane = candidate.lane_label or "Unlabeled"
                result.created_count_by_lane[lane] = (
                    result.created_count_by_lane.get(lane, 0) + 1
                )
            elif sync_result == "updated":
                result.updated_count += 1
                lane = candidate.lane_label or "Unlabeled"
                result.updated_count_by_lane[lane] = (
                    result.updated_count_by_lane.get(lane, 0) + 1
                )
            else:
                result.skipped_count += 1

        logger.info(
            "Discovery source collection completed with %s.",
            result.summary(),
        )
        return result
