from app.agents.entity_mapper_agent import EntityMapperAgent
from app.models.lead import Lead


def test_build_accounts_dedupes_by_canonical_and_merges_lane_context() -> None:
    agent = EntityMapperAgent()
    leads = [
        Lead(
            company_name="Blue Dune Technologies",
            lane_label="Expansion Signals",
            contact_name="Omar Rahman",
            contact_role="General Manager",
            target_country="Saudi Arabia",
            account_fit_summary="Expansion support into Saudi Arabia.",
        ),
        Lead(
            company_name="Blue Dune Technologies",
            lane_label="Buyer Mapping",
            contact_name="Mina Yusuf",
            contact_role="Head of People",
            target_country="Saudi Arabia",
        ),
    ]

    accounts = agent.build_accounts(leads)

    assert len(accounts) == 1
    assert accounts[0].account_canonical == "blue dune technologies"
    assert accounts[0].primary_target_country == "Saudi Arabia"
    assert accounts[0].lane_labels == ["Expansion Signals", "Buyer Mapping"]


def test_build_buyers_skips_unknown_contacts_and_sets_buyer_key() -> None:
    agent = EntityMapperAgent()
    leads = [
        Lead(
            company_name="Cedar Talent Partners",
            lane_label="Partner Channel",
            contact_name="Unknown Contact",
            contact_role="Unknown Role",
            target_country="the UAE",
        ),
        Lead(
            company_name="Cedar Talent Partners",
            lane_label="Partner Channel",
            contact_name="Layla Fawzi",
            contact_role="Managing Partner",
            target_country="the UAE",
            buyer_confidence=8,
        ),
    ]

    buyers = agent.build_buyers(leads)

    assert len(buyers) == 1
    assert buyers[0].buyer_key == "Layla Fawzi | Cedar Talent Partners"
    assert buyers[0].buyer_canonical == "layla fawzi"
    assert buyers[0].account_canonical == "cedar talent partners"
    assert buyers[0].buyer_confidence == 8
