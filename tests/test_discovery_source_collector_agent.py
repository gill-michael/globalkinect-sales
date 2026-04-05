from app.agents.discovery_source_collector_agent import (
    DiscoverySourceCollectionResult,
    DiscoverySourceCollectorAgent,
)
from app.models.discovery_candidate import DiscoveryCandidate
from app.models.discovery_source import DiscoverySource


class _FakeNotionService:
    def __init__(self, discovery_configured=True, sync_results=None):
        self._discovery_configured = discovery_configured
        self._sync_results = list(sync_results or [])
        self.synced = []

    def is_discovery_configured(self) -> bool:
        return self._discovery_configured

    def sync_discovery_candidate_page(self, candidate):
        self.synced.append(candidate)
        return self._sync_results.pop(0)


class _FakeDiscoverySourceService:
    def __init__(self, configured=True, sources=None, candidates=None):
        self._configured = configured
        self._sources = sources or []
        self._candidates = candidates or []

    def is_configured(self) -> bool:
        return self._configured

    def collect_candidates(self, campaign=None):
        return self._sources, self._candidates


def test_collect_into_discovery_counts_created_updated_and_skipped() -> None:
    fake_notion = _FakeNotionService(
        sync_results=["created", "updated", "skipped"]
    )
    fake_service = _FakeDiscoverySourceService(
        sources=[
            DiscoverySource(company_name="North Star Health", feed_url="https://a"),
            DiscoverySource(company_name="Blue Dune Tech", feed_url="https://b"),
        ],
        candidates=[
            DiscoveryCandidate(
                company_name="North Star Health",
                source_url="https://a/1",
                evidence="Saudi payroll signal",
            ),
            DiscoveryCandidate(
                company_name="Blue Dune Tech",
                source_url="https://b/1",
                evidence="UAE entity setup signal",
            ),
            DiscoveryCandidate(
                company_name="Atlas Ops",
                source_url="https://c/1",
                evidence="Duplicate signal",
            ),
        ],
    )
    agent = DiscoverySourceCollectorAgent(
        notion_service=fake_notion,
        discovery_source_service=fake_service,
    )

    result = agent.collect_into_discovery("Daily sourcing run")

    assert result == DiscoverySourceCollectionResult(
        source_count=2,
        candidate_count=3,
        created_count=1,
        updated_count=1,
        skipped_count=1,
        failed_count=0,
        candidate_count_by_lane={"Unlabeled": 3},
        created_count_by_lane={"Unlabeled": 1},
        updated_count_by_lane={"Unlabeled": 1},
    )
    assert len(fake_notion.synced) == 3
