from app.agents.autonomous_lane_agent import (
    AutonomousLaneAgent,
    AutonomousLaneSeedingResult,
)
from app.models.lead_discovery_record import LeadDiscoveryRecord
from app.models.lead_intake_record import LeadIntakeRecord
from app.models.operator_console import OutreachQueueRecord


class _FakeNotionService:
    def __init__(
        self,
        *,
        discovery_records=None,
        intake_records=None,
        outreach_records=None,
        sync_results=None,
    ) -> None:
        self._discovery_records = discovery_records or []
        self._intake_records = intake_records or []
        self._outreach_records = outreach_records or []
        self._sync_results = list(sync_results or [])
        self.synced = []

    def is_discovery_configured(self) -> bool:
        return True

    def is_intake_configured(self) -> bool:
        return True

    def is_outreach_queue_configured(self) -> bool:
        return True

    def list_lead_discovery_records(self, limit: int = 100):
        return self._discovery_records[:limit]

    def list_lead_intake_records(self, limit: int = 100):
        return self._intake_records[:limit]

    def list_outreach_queue_records(self, limit: int = 100):
        return self._outreach_records[:limit]

    def sync_discovery_candidate_page(self, candidate):
        self.synced.append(candidate)
        return self._sync_results.pop(0)


def test_seed_internal_lanes_creates_buyer_mapping_and_reactivation_candidates() -> None:
    fake_notion = _FakeNotionService(
        discovery_records=[
            LeadDiscoveryRecord(
                page_id="disc-1",
                company_name="Atlas Ops",
                lane_label="Expansion Signals",
                target_country_hint="Saudi Arabia",
                buyer_confidence=4,
                contact_name="Unknown Contact",
                contact_role="Unknown Role",
                notes="Weak buyer mapping",
            )
        ],
        intake_records=[
            LeadIntakeRecord(
                page_id="intake-1",
                company_name="Blue Dune Tech",
                lane_label="Payroll Complexity",
                target_country="United Arab Emirates",
                buyer_confidence=5,
                contact_name=None,
                contact_role="Unknown Role",
                notes="Needs buyer mapping",
            )
        ],
        outreach_records=[
            OutreachQueueRecord(
                page_id="queue-1",
                lead_reference="North Star|Jane|Saudi Arabia|direct_eor",
                company_name="North Star",
                contact_name="Jane",
                contact_role="Head of People",
                target_country="Saudi Arabia",
                status="Hold",
                primary_module="EOR",
                notes="Paused due to timing",
            )
        ],
        sync_results=["created", "created", "created"],
    )
    agent = AutonomousLaneAgent(notion_service=fake_notion)

    result = agent.seed_internal_lanes(limit=10)

    assert result == AutonomousLaneSeedingResult(
        candidate_count=3,
        created_count=3,
        updated_count=0,
        skipped_count=0,
        failed_count=0,
        candidate_count_by_lane={"Buyer Mapping": 2, "Reactivation": 1},
    )
    lane_labels = [candidate.lane_label for candidate in fake_notion.synced]
    assert lane_labels.count("Buyer Mapping") == 2
    assert lane_labels.count("Reactivation") == 1


def test_seed_internal_lanes_skips_records_with_strong_buyer_ready_context() -> None:
    fake_notion = _FakeNotionService(
        discovery_records=[
            LeadDiscoveryRecord(
                page_id="disc-1",
                company_name="Atlas Ops",
                lane_label="Expansion Signals",
                target_country_hint="Saudi Arabia",
                buyer_confidence=9,
                contact_name="Mina Yusuf",
                contact_role="COO",
            )
        ],
        sync_results=[],
    )
    agent = AutonomousLaneAgent(notion_service=fake_notion)

    result = agent.seed_internal_lanes(limit=10)

    assert result.candidate_count == 0
    assert fake_notion.synced == []


def test_seed_internal_lanes_uses_origin_page_ids_for_buyer_mapping_keys() -> None:
    fake_notion = _FakeNotionService(
        intake_records=[
            LeadIntakeRecord(
                page_id="intake-1",
                company_name="Atlas Ops",
                lane_label="Expansion Signals",
                target_country="Saudi Arabia",
                buyer_confidence=4,
                contact_name="Unknown Contact",
                contact_role="Unknown Role",
            ),
            LeadIntakeRecord(
                page_id="intake-2",
                company_name="Atlas Ops",
                lane_label="Expansion Signals",
                target_country="Saudi Arabia",
                buyer_confidence=4,
                contact_name="Unknown Contact",
                contact_role="Unknown Role",
            ),
        ],
        sync_results=["created", "created"],
    )
    agent = AutonomousLaneAgent(notion_service=fake_notion)

    result = agent.seed_internal_lanes(limit=10)

    assert result.candidate_count == 2
    assert len({candidate.discovery_key for candidate in fake_notion.synced}) == 2
