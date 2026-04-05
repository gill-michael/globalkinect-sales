from unittest.mock import MagicMock

from app.models.account import Account
from app.models.buyer import Buyer
from app.models.deal_support_package import DealSupportPackage
from app.models.discovery_candidate import DiscoveryCandidate
from app.models.discovery_qualification import DiscoveryQualification
from app.models.execution_task import ExecutionTask
from app.models.lead import Lead
from app.models.lead_discovery_record import LeadDiscoveryRecord
from app.models.lead_intake_record import LeadIntakeRecord
from app.models.operator_console import OperatorDashboardSnapshot
from app.models.outreach_queue_item import OutreachQueueItem
from app.models.pipeline_record import PipelineRecord
from app.models.sales_engine_run import SalesEngineRun
from app.models.solution_recommendation import SolutionRecommendation
from app.services.config import settings
from app.services.notion_service import NotionService


def _configure_notion_settings(monkeypatch) -> None:
    monkeypatch.setattr(settings, "NOTION_API_KEY", "test-notion-key")
    monkeypatch.setattr(settings, "NOTION_DISCOVERY_DATABASE_ID", "discovery-db")
    monkeypatch.setattr(settings, "NOTION_INTAKE_DATABASE_ID", "intake-db")
    monkeypatch.setattr(settings, "NOTION_OUTREACH_QUEUE_DATABASE_ID", "outreach-db")
    monkeypatch.setattr(settings, "NOTION_RUNS_DATABASE_ID", "runs-db")
    monkeypatch.setattr(settings, "NOTION_LEADS_DATABASE_ID", "leads-db")
    monkeypatch.setattr(settings, "NOTION_PIPELINE_DATABASE_ID", "pipeline-db")
    monkeypatch.setattr(settings, "NOTION_SOLUTIONS_DATABASE_ID", "solutions-db")
    monkeypatch.setattr(settings, "NOTION_TASKS_DATABASE_ID", "tasks-db")
    monkeypatch.setattr(
        settings,
        "NOTION_DEAL_SUPPORT_DATABASE_ID",
        "deal-support-db",
    )
    monkeypatch.setattr(settings, "NOTION_ACCOUNTS_DATABASE_ID", "accounts-db")
    monkeypatch.setattr(settings, "NOTION_BUYERS_DATABASE_ID", "buyers-db")


def _mock_response(payload):
    response = MagicMock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def _mock_schema_response(properties):
    return _mock_response({"properties": properties})


def test_ensure_configured_raises_when_service_is_not_configured() -> None:
    service = NotionService()
    service.client = None
    service._configuration_error = "Notion is disabled."

    try:
        service._ensure_configured()
    except RuntimeError as exc:
        assert "Notion is disabled" in str(exc)
    else:
        raise AssertionError("Expected RuntimeError when Notion is not configured.")


def test_upsert_lead_pages_creates_page_when_missing(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_schema_response(
        {"Company Canonical": {"type": "rich_text"}}
    )
    fake_client.post.side_effect = [
        _mock_response({"results": []}),
        _mock_response({"id": "page-created"}),
    ]
    service = NotionService(client=fake_client)

    lead = Lead(
        company_name="Example Ltd",
        contact_name="Jane Smith",
        contact_role="Founder",
        target_country="Saudi Arabia",
        lead_type="direct_payroll",
        score=8,
        priority="high",
    )

    responses = service.upsert_lead_pages([lead])

    assert responses == [{"id": "page-created"}]
    assert fake_client.post.call_args_list[0].args[0] == "/databases/leads-db/query"
    assert fake_client.post.call_args_list[1].args[0] == "/pages"
    create_payload = fake_client.post.call_args_list[1].kwargs["json"]
    assert create_payload["parent"]["database_id"] == "leads-db"
    assert (
        create_payload["properties"]["Lead Reference"]["title"][0]["text"]["content"]
        == "Example Ltd|Jane Smith|Saudi Arabia|direct_payroll"
    )
    assert (
        create_payload["properties"]["Company Canonical"]["rich_text"][0]["text"]["content"]
        == "example ltd"
    )


def test_upsert_pipeline_pages_updates_existing_page(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_schema_response(
        {"Company Canonical": {"type": "rich_text"}}
    )
    fake_client.post.return_value = _mock_response({"results": [{"id": "page-123"}]})
    fake_client.patch.return_value = _mock_response({"id": "page-123"})
    service = NotionService(client=fake_client)

    record = PipelineRecord(
        lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
        company_name="Example Ltd",
        contact_name="Jane Smith",
        lead_type="direct_payroll",
        target_country="Saudi Arabia",
        score=8,
        priority="high",
        sales_motion="direct_client",
        primary_module="Payroll",
        bundle_label="Payroll + HRIS",
        recommended_modules=["Payroll", "HRIS"],
        stage="proposal",
        outreach_status="sent",
        next_action="follow_up_proposal",
    )

    responses = service.upsert_pipeline_pages([record])

    assert responses == [{"id": "page-123"}]
    assert fake_client.post.call_args.args[0] == "/databases/pipeline-db/query"
    assert fake_client.patch.call_args.args[0] == "/pages/page-123"
    patch_payload = fake_client.patch.call_args.kwargs["json"]
    assert patch_payload["properties"]["Stage"]["select"]["name"] == "proposal"
    assert patch_payload["properties"]["High Value"]["checkbox"] is True
    assert (
        patch_payload["properties"]["Company Canonical"]["rich_text"][0]["text"]["content"]
        == "example ltd"
    )


def test_upsert_account_pages_creates_account_row(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_schema_response(
        {
            "Account": {"type": "title"},
            "Account Canonical": {"type": "rich_text"},
            "Primary Target Country": {
                "type": "select",
                "select": {"options": [{"name": "Saudi Arabia"}]},
            },
            "Notes": {"type": "rich_text"},
        }
    )
    fake_client.post.side_effect = [
        _mock_response({"results": []}),
        _mock_response({"results": []}),
        _mock_response({"id": "account-page"}),
    ]
    service = NotionService(client=fake_client)
    account = Account(
        account_name="Blue Dune Technologies",
        account_canonical="blue dune technologies",
        primary_target_country="Saudi Arabia",
        notes="Derived from active sales-engine lead output.",
    )

    responses = service.upsert_account_pages([account])

    assert responses == [{"id": "account-page"}]
    create_payload = fake_client.post.call_args_list[2].kwargs["json"]["properties"]
    assert create_payload["Account"]["title"][0]["text"]["content"] == "Blue Dune Technologies"
    assert (
        create_payload["Account Canonical"]["rich_text"][0]["text"]["content"]
        == "blue dune technologies"
    )


def test_upsert_pipeline_pages_sets_account_and_buyer_relations_when_available(
    monkeypatch,
) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.side_effect = [
        _mock_schema_response(
            {
                "Company Canonical": {"type": "rich_text"},
                "Account": {"type": "relation"},
                "Buyer": {"type": "relation"},
            }
        ),
        _mock_schema_response(
            {
                "Account Canonical": {"type": "rich_text"},
            }
        ),
        _mock_schema_response(
            {
                "Buyer": {"type": "title"},
                "Account (text)": {"type": "rich_text"},
            }
        ),
    ]
    fake_client.post.side_effect = [
        _mock_response({"results": [{"id": "account-page"}]}),
        _mock_response(
            {
                "results": [
                    {
                        "id": "buyer-page",
                        "properties": {
                            "Buyer": {
                                "type": "title",
                                "title": [{"plain_text": "Omar Rahman"}],
                            },
                            "Account (text)": {
                                "type": "rich_text",
                                "rich_text": [{"plain_text": "Blue Dune Technologies"}],
                            },
                        },
                    }
                ]
            }
        ),
        _mock_response({"results": []}),
        _mock_response({"id": "pipeline-page"}),
    ]
    service = NotionService(client=fake_client)

    record = PipelineRecord(
        lead_reference="Blue Dune Technologies|Omar Rahman|Saudi Arabia|direct_eor",
        company_name="Blue Dune Technologies",
        contact_name="Omar Rahman",
        lead_type="direct_eor",
        target_country="Saudi Arabia",
        score=8,
        priority="high",
        stage="new",
        outreach_status="drafted",
    )

    responses = service.upsert_pipeline_pages([record])

    assert responses == [{"id": "pipeline-page"}]
    create_payload = fake_client.post.call_args_list[3].kwargs["json"]["properties"]
    assert create_payload["Account"]["relation"] == [{"id": "account-page"}]
    assert create_payload["Buyer"]["relation"] == [{"id": "buyer-page"}]


def test_upsert_buyer_pages_uses_live_buyer_schema(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.side_effect = [
        _mock_schema_response(
            {
                "Buyer": {"type": "title"},
                "Account": {"type": "relation"},
                "Account (text)": {"type": "rich_text"},
                "Email": {"type": "email"},
                "LinkedIn": {"type": "url"},
                "Notes": {"type": "rich_text"},
                "Role / Persona": {"type": "rich_text"},
            }
        ),
        _mock_schema_response(
            {
                "Account Canonical": {"type": "rich_text"},
            }
        ),
    ]
    fake_client.post.side_effect = [
        _mock_response({"results": []}),
        _mock_response({"results": []}),
        _mock_response({"id": "buyer-page"}),
    ]
    service = NotionService(client=fake_client)
    buyer = Buyer(
        buyer_key="Omar Rahman | Blue Dune Technologies",
        buyer_name="Omar Rahman",
        buyer_canonical="omar rahman",
        account_name="Blue Dune Technologies",
        account_canonical="blue dune technologies",
        contact_role="General Manager",
        email="omar@example.com",
        linkedin_url="https://linkedin.com/in/omar",
        target_country="Saudi Arabia",
        buyer_confidence=8,
        lane_labels=["Buyer Mapping"],
    )

    responses = service.upsert_buyer_pages([buyer])

    assert responses == [{"id": "buyer-page"}]
    create_payload = fake_client.post.call_args_list[2].kwargs["json"]["properties"]
    assert create_payload["Buyer"]["title"][0]["text"]["content"] == "Omar Rahman"
    assert (
        create_payload["Account (text)"]["rich_text"][0]["text"]["content"]
        == "Blue Dune Technologies"
    )
    assert create_payload["Role / Persona"]["rich_text"][0]["text"]["content"] == "General Manager"


def test_upsert_solution_task_and_deal_support_pages_create_expected_payloads(
    monkeypatch,
) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_schema_response(
        {
            "Company": {"type": "rich_text"},
            "Company Canonical": {"type": "rich_text"},
        }
    )
    fake_client.post.side_effect = [
        _mock_response({"results": []}),
        _mock_response({"id": "solution-page"}),
        _mock_response({"results": []}),
        _mock_response({"id": "task-page"}),
        _mock_response({"results": []}),
        _mock_response({"id": "deal-page"}),
    ]
    service = NotionService(client=fake_client)

    recommendation = SolutionRecommendation(
        lead_reference="Example Ltd|Jane Smith|Saudi Arabia|direct_payroll",
        company_name="Example Ltd",
        contact_name="Jane Smith",
        target_country="Saudi Arabia",
        sales_motion="direct_client",
        recommended_modules=["Payroll", "HRIS"],
        primary_module="Payroll",
        bundle_label="Payroll + HRIS",
        commercial_strategy="Position a payroll-led platform entry point for Saudi Arabia with added operational visibility and control.",
        rationale="The current fit is payroll-led with stronger control.",
    )
    task = ExecutionTask(
        lead_reference=recommendation.lead_reference,
        task_type="send_message",
        description="Review and send the drafted outreach.",
        priority="high",
        due_in_days=0,
    )
    package = DealSupportPackage(
        lead_reference=recommendation.lead_reference,
        company_name="Example Ltd",
        contact_name="Jane Smith",
        lead_type="direct_payroll",
        target_country="Saudi Arabia",
        sales_motion="direct_client",
        primary_module="Payroll",
        bundle_label="Payroll + HRIS",
        recommended_modules=["Payroll", "HRIS"],
        stage="proposal",
        call_prep_summary="Prep summary",
        recap_email_subject="Recap subject",
        recap_email_body="Recap body",
        proposal_summary="Proposal summary",
        next_steps_message="Next steps",
        objection_response="Objection response",
    )

    solution_responses = service.upsert_solution_pages([recommendation])
    task_responses = service.upsert_execution_task_pages([task])
    deal_support_responses = service.upsert_deal_support_pages([package])

    assert solution_responses == [{"id": "solution-page"}]
    assert task_responses == [{"id": "task-page"}]
    assert deal_support_responses == [{"id": "deal-page"}]
    solution_create_payload = fake_client.post.call_args_list[1].kwargs["json"]
    task_create_payload = fake_client.post.call_args_list[3].kwargs["json"]
    deal_create_payload = fake_client.post.call_args_list[5].kwargs["json"]
    assert (
        solution_create_payload["properties"]["Recommended Modules"]["multi_select"][0]["name"]
        == "Payroll"
    )
    assert (
        task_create_payload["properties"]["Task"]["title"][0]["text"]["content"]
        == "Example Ltd|Jane Smith|Saudi Arabia|direct_payroll | send_message"
    )
    assert (
        task_create_payload["properties"]["Company"]["rich_text"][0]["text"]["content"]
        == "Example Ltd"
    )
    assert (
        task_create_payload["properties"]["Company Canonical"]["rich_text"][0]["text"]["content"]
        == "example ltd"
    )
    assert (
        deal_create_payload["properties"]["Proposal Summary"]["rich_text"][0]["text"]["content"]
        == "Proposal summary"
    )


def test_fetch_lead_intake_records_filters_completed_rows(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.post.return_value = _mock_response(
        {
            "results": [
                {
                    "id": "page-ready",
                    "properties": {
                        "Company": {
                            "type": "title",
                            "title": [{"plain_text": "North Star Labs"}],
                        },
                        "Contact": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "Mina Yusuf"}],
                        },
                        "Role": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "Head of People"}],
                        },
                        "Email": {"type": "email", "email": "mina@example.com"},
                        "Target Country": {
                            "type": "select",
                            "select": {"name": "Saudi Arabia"},
                        },
                        "Lead Type Hint": {
                            "type": "select",
                            "select": {"name": "direct_payroll"},
                        },
                        "Status": {
                            "type": "select",
                            "select": {"name": "ready"},
                        },
                    },
                },
                {
                    "id": "page-done",
                    "properties": {
                        "Company": {
                            "type": "title",
                            "title": [{"plain_text": "Archived Co"}],
                        },
                        "Status": {
                            "type": "select",
                            "select": {"name": "ingested"},
                        },
                    },
                },
            ]
        }
    )
    service = NotionService(client=fake_client)

    records = service.fetch_lead_intake_records(limit=10)

    assert records == [
        LeadIntakeRecord(
            page_id="page-ready",
            company_name="North Star Labs",
            contact_name="Mina Yusuf",
            contact_role="Head of People",
            email="mina@example.com",
            target_country="Saudi Arabia",
            lead_type_hint="direct_payroll",
            status="ready",
        )
    ]
    assert fake_client.post.call_args.args[0] == "/databases/intake-db/query"
    query_payload = fake_client.post.call_args.kwargs["json"]
    assert query_payload["sorts"][0]["timestamp"] == "last_edited_time"
    assert query_payload["sorts"][0]["direction"] == "descending"


def test_fetch_lead_intake_records_treats_null_placeholder_strings_as_missing(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.post.return_value = _mock_response(
        {
            "results": [
                {
                    "id": "page-null",
                    "properties": {
                        "Company": {
                            "type": "title",
                            "title": [{"plain_text": "Guidepoint"}],
                        },
                        "Contact": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "null"}],
                        },
                        "Role": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "N/A"}],
                        },
                        "Status": {
                            "type": "select",
                            "select": {"name": "ready"},
                        },
                    },
                }
            ]
        }
    )
    service = NotionService(client=fake_client)

    records = service.fetch_lead_intake_records(limit=10)

    assert records[0].contact_name is None
    assert records[0].contact_role is None


def test_fetch_lead_discovery_records_filters_completed_rows(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.post.return_value = _mock_response(
        {
            "results": [
                {
                    "id": "page-ready",
                    "properties": {
                        "Company": {
                            "type": "title",
                            "title": [{"plain_text": "Atlas Ops"}],
                        },
                        "Source URL": {
                            "type": "url",
                            "url": "https://example.com/jobs/atlas-ksa",
                        },
                        "Evidence": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "Hiring first payroll lead in KSA"}],
                        },
                        "Target Country Hint": {
                            "type": "select",
                            "select": {"name": "Saudi Arabia"},
                        },
                        "Status": {
                            "type": "select",
                            "select": {"name": "ready"},
                        },
                    },
                },
                {
                    "id": "page-done",
                    "properties": {
                        "Company": {
                            "type": "title",
                            "title": [{"plain_text": "Archived Co"}],
                        },
                        "Status": {
                            "type": "select",
                            "select": {"name": "promoted"},
                        },
                    },
                },
            ]
        }
    )
    service = NotionService(client=fake_client)

    records = service.fetch_lead_discovery_records(limit=10)

    assert records == [
        LeadDiscoveryRecord(
            page_id="page-ready",
            company_name="Atlas Ops",
            source_url="https://example.com/jobs/atlas-ksa",
            evidence="Hiring first payroll lead in KSA",
            target_country_hint="Saudi Arabia",
            status="ready",
        )
    ]
    assert fake_client.post.call_args.args[0] == "/databases/discovery-db/query"
    query_payload = fake_client.post.call_args.kwargs["json"]
    assert query_payload["sorts"][0]["timestamp"] == "last_edited_time"
    assert query_payload["sorts"][0]["direction"] == "descending"


def test_fetch_lead_discovery_records_prioritizes_stronger_buyer_context(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.post.return_value = _mock_response(
        {
            "results": [
                {
                    "id": "page-weak",
                    "properties": {
                        "Company": {
                            "type": "title",
                            "title": [{"plain_text": "Weak Co"}],
                        },
                        "Buyer Confidence": {"type": "number", "number": 3},
                        "Status": {"type": "select", "select": {"name": "ready"}},
                    },
                },
                {
                    "id": "page-strong",
                    "properties": {
                        "Company": {
                            "type": "title",
                            "title": [{"plain_text": "Strong Co"}],
                        },
                        "Role": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "Head of People"}],
                        },
                        "Buyer Confidence": {"type": "number", "number": 8},
                        "Status": {"type": "select", "select": {"name": "ready"}},
                    },
                },
            ]
        }
    )
    service = NotionService(client=fake_client)

    records = service.fetch_lead_discovery_records(limit=1)

    assert len(records) == 1
    assert records[0].company_name == "Strong Co"


def test_build_lead_discovery_record_recovers_lane_label_from_account_fit_summary(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    service = NotionService(client=MagicMock())

    record = service._build_lead_discovery_record(
        {
            "id": "page-1",
            "properties": {
                "Company": {
                    "type": "title",
                    "title": [{"plain_text": "Radar Co"}],
                },
                "Account Fit Summary": {
                    "type": "rich_text",
                    "rich_text": [{"plain_text": "Radar Co: lane=Market Intelligence; market=Saudi Arabia"}],
                },
                "Status": {
                    "type": "select",
                    "select": {"name": "ready"},
                },
            },
        }
    )

    assert record is not None
    assert record.lane_label == "Market Intelligence"


def test_sync_discovery_candidate_page_creates_ready_discovery_row(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Company": {"type": "title"},
                "Company Canonical": {"type": "rich_text"},
                "Discovery Key": {"type": "rich_text"},
                "Agent Label": {
                    "type": "select",
                    "select": {"options": [{"name": "Payroll Complexity Agent"}]},
                },
                "Website URL": {"type": "url"},
                "Source URL": {"type": "url"},
                "Source Type": {
                    "type": "select",
                    "select": {"options": [{"name": "careers_feed"}]},
                },
                "Published At": {"type": "date"},
                "Source Priority": {"type": "number"},
                "Source Trust Score": {"type": "number"},
                "Service Focus": {
                    "type": "select",
                    "select": {"options": [{"name": "payroll"}]},
                },
                "Evidence": {"type": "rich_text"},
                "Target Country Hint": {
                    "type": "select",
                    "select": {"options": [{"name": "Saudi Arabia"}]},
                },
                "Campaign": {"type": "rich_text"},
                "Notes": {"type": "rich_text"},
                "Status": {
                    "type": "select",
                    "select": {"options": [{"name": "Ready"}]},
                },
                "Last Error": {"type": "rich_text"},
            }
        }
    )
    fake_client.post.side_effect = [
        _mock_response({"results": []}),
        _mock_response({"results": []}),
        _mock_response({"id": "discovery-page"}),
    ]
    service = NotionService(client=fake_client)
    candidate = DiscoveryCandidate(
        company_name="North Star Health",
        agent_label="Payroll Complexity Agent",
        discovery_key="abc123",
        website_url="https://northstar.example",
        source_url="https://northstar.example/jobs/saudi-payroll",
        source_type="careers_feed",
        published_at="2026-03-22T08:00:00Z",
        source_priority=8,
        source_trust_score=9,
        service_focus="payroll",
        evidence="Payroll Operations Manager - Riyadh. Matched target market: Saudi Arabia.",
        company_country="Germany",
        target_country_hint="Saudi Arabia",
        campaign="Saudi payroll expansion",
        notes="Lead type hint: direct_payroll",
    )

    result = service.sync_discovery_candidate_page(candidate)

    assert result == "created"
    create_payload = fake_client.post.call_args_list[2].kwargs["json"]["properties"]
    assert create_payload["Company"]["title"][0]["text"]["content"] == "North Star Health"
    assert (
        create_payload["Company Canonical"]["rich_text"][0]["text"]["content"]
        == "north star health"
    )
    assert create_payload["Discovery Key"]["rich_text"][0]["text"]["content"] == "abc123"
    assert create_payload["Agent Label"]["select"]["name"] == "Payroll Complexity Agent"
    assert create_payload["Status"]["select"]["name"] == "Ready"
    assert create_payload["Published At"]["date"]["start"] == "2026-03-22T08:00:00Z"
    assert create_payload["Source Priority"]["number"] == 8
    assert create_payload["Source Trust Score"]["number"] == 9
    assert create_payload["Service Focus"]["select"]["name"] == "payroll"
    assert create_payload["Target Country Hint"]["select"]["name"] == "Saudi Arabia"


def test_sync_discovery_candidate_page_skips_unchanged_processed_signal(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Company": {"type": "title"},
                "Source URL": {"type": "url"},
                "Status": {
                    "type": "select",
                    "select": {"options": [{"name": "Promoted"}]},
                },
                "Evidence": {"type": "rich_text"},
            }
        }
    )
    fake_client.post.return_value = _mock_response(
        {
            "results": [
                {
                    "id": "existing-page",
                    "properties": {
                        "Company": {
                            "type": "title",
                            "title": [{"plain_text": "North Star Health"}],
                        },
                        "Source URL": {
                            "type": "url",
                            "url": "https://northstar.example/jobs/saudi-payroll",
                        },
                        "Evidence": {
                            "type": "rich_text",
                            "rich_text": [
                                {
                                    "plain_text": "Payroll Operations Manager - Riyadh. Matched target market: Saudi Arabia."
                                }
                            ],
                        },
                        "Status": {
                            "type": "select",
                            "select": {"name": "Promoted"},
                        },
                    },
                }
            ]
        }
    )
    service = NotionService(client=fake_client)
    candidate = DiscoveryCandidate(
        company_name="North Star Health",
        source_url="https://northstar.example/jobs/saudi-payroll",
        evidence="Payroll Operations Manager - Riyadh. Matched target market: Saudi Arabia.",
    )

    result = service.sync_discovery_candidate_page(candidate)

    assert result == "skipped"
    fake_client.patch.assert_not_called()


def test_sync_discovery_candidate_page_does_not_dedupe_by_company_title_alone(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Company": {"type": "title"},
                "Discovery Key": {"type": "rich_text"},
                "Agent Label": {"type": "rich_text"},
                "Source URL": {"type": "url"},
                "Status": {
                    "type": "select",
                    "select": {"options": [{"name": "Ready"}]},
                },
                "Evidence": {"type": "rich_text"},
            }
        }
    )
    fake_client.post.side_effect = [
        _mock_response({"results": []}),
        _mock_response({"results": []}),
        _mock_response({"id": "new-discovery-page"}),
    ]
    service = NotionService(client=fake_client)
    candidate = DiscoveryCandidate(
        company_name="North Star Health",
        agent_label="Payroll Complexity Agent",
        discovery_key="ksa-payroll-001",
        source_url="https://northstar.example/jobs/ksa-payroll",
        evidence="Payroll Manager - Riyadh. Matched target market: Saudi Arabia.",
    )

    result = service.sync_discovery_candidate_page(candidate)

    assert result == "created"
    create_payload = fake_client.post.call_args_list[2].kwargs["json"]["properties"]
    assert create_payload["Company"]["title"][0]["text"]["content"] == "North Star Health"
    assert create_payload["Discovery Key"]["rich_text"][0]["text"]["content"] == "ksa-payroll-001"
    assert (
        create_payload["Agent Label"]["rich_text"][0]["text"]["content"]
        == "Payroll Complexity Agent"
    )


def test_mark_lead_intake_record_processed_updates_supported_tracking_fields(
    monkeypatch,
) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Status": {"type": "select"},
                "Lead Reference": {"type": "rich_text"},
                "Fit Reason": {"type": "rich_text"},
                "Processed At": {"type": "date"},
                "Last Error": {"type": "rich_text"},
            }
        }
    )
    fake_client.patch.return_value = _mock_response({"id": "page-1"})
    service = NotionService(client=fake_client)
    intake_record = LeadIntakeRecord(
        page_id="page-1",
        company_name="North Star Labs",
    )
    lead = Lead(
        company_name="North Star Labs",
        contact_name="Mina Yusuf",
        contact_role="Head of People",
        target_country="Saudi Arabia",
        lead_type="direct_payroll",
        fit_reason="Hiring a first Saudi Arabia team with payroll needs.",
    )

    response = service.mark_lead_intake_record_processed(intake_record, lead)

    assert response == {"id": "page-1"}
    assert fake_client.get.call_args.args[0] == "/databases/intake-db"
    assert fake_client.patch.call_args.args[0] == "/pages/page-1"
    patch_payload = fake_client.patch.call_args.kwargs["json"]["properties"]
    assert patch_payload["Status"]["select"]["name"] == "ingested"
    assert (
        patch_payload["Lead Reference"]["rich_text"][0]["text"]["content"]
        == "North Star Labs|Mina Yusuf|Saudi Arabia|direct_payroll"
    )


def test_mark_lead_discovery_record_processed_updates_supported_tracking_fields(
    monkeypatch,
) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Status": {
                    "type": "select",
                    "select": {"options": [{"name": "Promoted"}]},
                },
                "Confidence Score": {"type": "number"},
                "Qualification Summary": {"type": "rich_text"},
                "Fit Reason": {"type": "rich_text"},
                "Lead Type": {
                    "type": "select",
                    "select": {"options": [{"name": "direct_payroll"}]},
                },
                "Target Country Hint": {
                    "type": "select",
                    "select": {"options": [{"name": "Saudi Arabia"}]},
                },
                "Lead Reference": {"type": "rich_text"},
                "Processed At": {"type": "date"},
                "Last Error": {"type": "rich_text"},
            }
        }
    )
    fake_client.patch.return_value = _mock_response({"id": "page-2"})
    service = NotionService(client=fake_client)
    discovery_record = LeadDiscoveryRecord(
        page_id="page-2",
        company_name="North Star Labs",
        source_url="https://example.com",
    )
    qualification = DiscoveryQualification(
        lead=Lead(
            company_name="North Star Labs",
            contact_name="Mina Yusuf",
            contact_role="Head of People",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            fit_reason="Evidence points to Saudi payroll expansion support.",
        ),
        evidence_summary="Hiring a first Saudi payroll team from Germany.",
        confidence_score=8,
        decision="promote",
    )

    response = service.mark_lead_discovery_record_processed(
        discovery_record,
        qualification,
    )

    assert response == {"id": "page-2"}
    assert fake_client.get.call_args.args[0] == "/databases/discovery-db"
    patch_payload = fake_client.patch.call_args.kwargs["json"]["properties"]
    assert patch_payload["Status"]["select"]["name"] == "Promoted"
    assert patch_payload["Confidence Score"]["number"] == 8
    assert (
        patch_payload["Lead Reference"]["rich_text"][0]["text"]["content"]
        == "North Star Labs|Mina Yusuf|Saudi Arabia|direct_payroll"
    )


def test_upsert_intake_page_from_discovery_creates_ready_intake_row(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Company": {"type": "title"},
                "Company Canonical": {"type": "rich_text"},
                "Contact": {"type": "rich_text"},
                "Role": {"type": "rich_text"},
                "Email": {"type": "email"},
                "LinkedIn URL": {"type": "url"},
                "Company Country": {"type": "rich_text"},
                "Target Country": {
                    "type": "select",
                    "select": {"options": [{"name": "Saudi Arabia"}]},
                },
                "Lead Type Hint": {
                    "type": "select",
                    "select": {"options": [{"name": "direct_payroll"}]},
                },
                "Campaign": {"type": "rich_text"},
                "Notes": {"type": "rich_text"},
                "Status": {
                    "type": "select",
                    "select": {"options": [{"name": "Ready"}]},
                },
                "Lead Reference": {"type": "rich_text"},
                "Fit Reason": {"type": "rich_text"},
                "Processed At": {"type": "date"},
                "Last Error": {"type": "rich_text"},
            }
        }
    )
    fake_client.post.side_effect = [
        _mock_response({"results": []}),
        _mock_response({"id": "intake-page"}),
    ]
    service = NotionService(client=fake_client)
    discovery_record = LeadDiscoveryRecord(
        page_id="discovery-1",
        company_name="North Star Labs",
        source_url="https://example.com/source",
        source_type="job_board",
        evidence="Hiring a first Saudi payroll team.",
        campaign="Saudi expansion campaign",
    )
    qualification = DiscoveryQualification(
        lead=Lead(
            company_name="North Star Labs",
            contact_name="Mina Yusuf",
            contact_role="Head of People",
            email="mina@example.com",
            linkedin_url="https://linkedin.com/in/mina-yusuf",
            company_country="Germany",
            target_country="Saudi Arabia",
            lead_type="direct_payroll",
            fit_reason="Hiring signals point to Saudi payroll complexity.",
        ),
        evidence_summary="Evidence shows active Saudi payroll hiring.",
        confidence_score=8,
        decision="promote",
    )

    response = service.upsert_intake_page_from_discovery(
        qualification.lead,
        discovery_record,
        qualification,
    )

    assert response == {"id": "intake-page"}
    create_payload = fake_client.post.call_args_list[1].kwargs["json"]["properties"]
    assert create_payload["Company"]["title"][0]["text"]["content"] == "North Star Labs"
    assert (
        create_payload["Company Canonical"]["rich_text"][0]["text"]["content"]
        == "north star labs"
    )
    assert create_payload["Status"]["select"]["name"] == "Ready"
    assert create_payload["Lead Type Hint"]["select"]["name"] == "direct_payroll"
    assert (
        create_payload["Notes"]["rich_text"][0]["text"]["content"]
        == "Evidence shows active Saudi payroll hiring.\nSource type: job_board\nSource URL: https://example.com/source"
    )


def test_upsert_outreach_queue_pages_maps_internal_values_to_capitalized_selects(
    monkeypatch,
) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Company Canonical": {"type": "rich_text"},
                "Priority": {
                    "type": "select",
                    "select": {"options": [{"name": "High"}, {"name": "Medium"}]},
                },
                "Target Country": {
                    "type": "select",
                    "select": {"options": [{"name": "United Arab Emirates"}]},
                },
                "Sales Motion": {
                    "type": "select",
                    "select": {"options": [{"name": "Direct client"}]},
                },
                "Primary Module": {
                    "type": "select",
                    "select": {"options": [{"name": "EOR"}]},
                },
                "Bundle Label": {
                    "type": "select",
                    "select": {"options": [{"name": "EOR + Payroll"}]},
                },
                "Status": {
                    "type": "select",
                    "select": {"options": [{"name": "Ready to send"}]},
                },
            }
        }
    )
    fake_client.post.side_effect = [
        _mock_response({"results": []}),
        _mock_response({"id": "queue-page"}),
    ]
    service = NotionService(client=fake_client)
    item = OutreachQueueItem(
        lead_reference="Blue Dune Technologies|Omar Rahman|the UAE|direct_eor",
        company_name="Blue Dune Technologies",
        contact_name="Omar Rahman",
        contact_role="Founder",
        priority="high",
        target_country="United Arab Emirates",
        sales_motion="direct_client",
        primary_module="EOR",
        bundle_label="EOR + Payroll",
        email_subject="UAE EOR + Payroll support",
        email_message="Email body",
        linkedin_message="LinkedIn body",
        follow_up_message="Follow-up body",
        generated_at="2026-03-22T12:00:00+00:00",
        run_marker="RUN_20260322120000",
    )

    responses = service.upsert_outreach_queue_pages([item])

    assert responses == [{"id": "queue-page"}]
    create_payload = fake_client.post.call_args_list[1].kwargs["json"]["properties"]
    assert (
        create_payload["Company Canonical"]["rich_text"][0]["text"]["content"]
        == "blue dune technologies"
    )
    assert create_payload["Priority"]["select"]["name"] == "High"
    assert create_payload["Sales Motion"]["select"]["name"] == "Direct client"
    assert create_payload["Status"]["select"]["name"] == "Ready to send"


def test_upsert_outreach_queue_pages_preserves_approved_rows(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.post.return_value = _mock_response(
        {
            "results": [
                {
                    "id": "queue-page",
                    "properties": {
                        "Lead Reference": {
                            "type": "title",
                            "title": [
                                {
                                    "plain_text": "Blue Dune Technologies|Omar Rahman|the UAE|direct_eor"
                                }
                            ],
                        },
                        "Status": {
                            "type": "select",
                            "select": {"name": "Approved"},
                        },
                    },
                }
            ]
        }
    )
    service = NotionService(client=fake_client)
    item = OutreachQueueItem(
        lead_reference="Blue Dune Technologies|Omar Rahman|the UAE|direct_eor",
        company_name="Blue Dune Technologies",
        contact_name="Omar Rahman",
        contact_role="Founder",
        priority="high",
        target_country="United Arab Emirates",
        sales_motion="direct_client",
        primary_module="EOR",
        bundle_label="EOR + Payroll",
        email_subject="Updated subject",
        email_message="Updated email body",
        linkedin_message="Updated LinkedIn body",
        follow_up_message="Updated follow-up body",
        generated_at="2026-03-23T09:00:00+00:00",
        run_marker="RUN_20260323090000",
    )

    responses = service.upsert_outreach_queue_pages([item])

    assert responses[0]["id"] == "queue-page"
    fake_client.patch.assert_not_called()


def test_upsert_outreach_queue_pages_refreshes_regenerate_rows(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Priority": {
                    "type": "select",
                    "select": {"options": [{"name": "High"}, {"name": "Medium"}]},
                },
                "Target Country": {
                    "type": "select",
                    "select": {"options": [{"name": "United Arab Emirates"}]},
                },
                "Sales Motion": {
                    "type": "select",
                    "select": {"options": [{"name": "Direct client"}]},
                },
                "Primary Module": {
                    "type": "select",
                    "select": {"options": [{"name": "EOR"}]},
                },
                "Bundle Label": {
                    "type": "select",
                    "select": {"options": [{"name": "EOR + Payroll"}]},
                },
                "Status": {
                    "type": "select",
                    "select": {
                        "options": [
                            {"name": "Ready to send"},
                            {"name": "Regenerate"},
                        ]
                    },
                },
            }
        }
    )
    fake_client.post.return_value = _mock_response(
        {
            "results": [
                {
                    "id": "queue-page",
                    "properties": {
                        "Lead Reference": {
                            "type": "title",
                            "title": [
                                {
                                    "plain_text": "Blue Dune Technologies|Omar Rahman|the UAE|direct_eor"
                                }
                            ],
                        },
                        "Status": {
                            "type": "select",
                            "select": {"name": "Regenerate"},
                        },
                    },
                }
            ]
        }
    )
    fake_client.patch.return_value = _mock_response({"id": "queue-page"})
    service = NotionService(client=fake_client)
    item = OutreachQueueItem(
        lead_reference="Blue Dune Technologies|Omar Rahman|the UAE|direct_eor",
        company_name="Blue Dune Technologies",
        contact_name="Omar Rahman",
        contact_role="Founder",
        priority="high",
        target_country="United Arab Emirates",
        sales_motion="direct_client",
        primary_module="EOR",
        bundle_label="EOR + Payroll",
        email_subject="Updated subject",
        email_message="Updated email body",
        linkedin_message="Updated LinkedIn body",
        follow_up_message="Updated follow-up body",
        generated_at="2026-03-23T09:00:00+00:00",
        run_marker="RUN_20260323090000",
    )

    responses = service.upsert_outreach_queue_pages([item])

    assert responses == [{"id": "queue-page"}]
    patch_payload = fake_client.patch.call_args.kwargs["json"]["properties"]
    assert patch_payload["Status"]["select"]["name"] == "Ready to send"
    assert patch_payload["Email Subject"]["rich_text"][0]["text"]["content"] == "Updated subject"


def test_upsert_sales_engine_run_page_maps_internal_values_to_existing_options(
    monkeypatch,
) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Status": {
                    "type": "select",
                    "select": {"options": [{"name": "Running"}]},
                },
                "Run Mode": {
                    "type": "select",
                    "select": {"options": [{"name": "Shadow"}]},
                },
                "Triggered By": {
                    "type": "select",
                    "select": {"options": [{"name": "Manual"}]},
                },
                "Notes": {"type": "rich_text"},
            }
        }
    )
    fake_client.post.side_effect = [
        _mock_response({"results": []}),
        _mock_response({"id": "run-page"}),
    ]
    service = NotionService(client=fake_client)
    run = SalesEngineRun(
        run_marker="RUN_20260322120000",
        status="running",
        started_at="2026-03-22T12:00:00+00:00",
        run_mode="shadow",
        triggered_by="manual",
        notes="Shadow run started.",
    )

    response = service.upsert_sales_engine_run_page(run)

    assert response == {"id": "run-page"}
    create_payload = fake_client.post.call_args_list[1].kwargs["json"]["properties"]
    assert create_payload["Status"]["select"]["name"] == "Running"
    assert create_payload["Run Mode"]["select"]["name"] == "Shadow"
    assert create_payload["Triggered By"]["select"]["name"] == "Manual"


def test_list_outreach_queue_records_returns_full_rows(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.post.return_value = _mock_response(
        {
            "results": [
                {
                    "id": "queue-page",
                    "properties": {
                        "Lead Reference": {
                            "type": "title",
                            "title": [
                                {
                                    "plain_text": "Blue Dune Technologies|Omar Rahman|the UAE|direct_eor"
                                }
                            ],
                        },
                        "Company": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "Blue Dune Technologies"}],
                        },
                        "Contact": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "Omar Rahman"}],
                        },
                        "Status": {
                            "type": "select",
                            "select": {"name": "Ready to send"},
                        },
                        "Email Subject": {
                            "type": "rich_text",
                            "rich_text": [{"plain_text": "UAE EOR + Payroll support"}],
                        },
                    },
                }
            ]
        }
    )
    service = NotionService(client=fake_client)

    records = service.list_outreach_queue_records(limit=10)

    assert len(records) == 1
    assert records[0].lead_reference == "Blue Dune Technologies|Omar Rahman|the UAE|direct_eor"
    assert records[0].status == "Ready to send"
    assert records[0].email_subject == "UAE EOR + Payroll support"


def test_update_outreach_queue_status_patches_existing_row(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.get.return_value = _mock_response(
        {
            "properties": {
                "Status": {
                    "type": "select",
                    "select": {"options": [{"name": "Approved"}, {"name": "Hold"}]},
                }
            }
        }
    )
    fake_client.post.return_value = _mock_response(
        {
            "results": [
                {
                    "id": "queue-page",
                    "properties": {
                        "Lead Reference": {
                            "type": "title",
                            "title": [
                                {
                                    "plain_text": "Blue Dune Technologies|Omar Rahman|the UAE|direct_eor"
                                }
                            ],
                        }
                    },
                }
            ]
        }
    )
    fake_client.patch.return_value = _mock_response({"id": "queue-page"})
    service = NotionService(client=fake_client)

    response = service.update_outreach_queue_status(
        "Blue Dune Technologies|Omar Rahman|the UAE|direct_eor",
        "Approved",
    )

    assert response == {"id": "queue-page"}
    patch_payload = fake_client.patch.call_args.kwargs["json"]["properties"]
    assert patch_payload["Status"]["select"]["name"] == "Approved"


def test_get_operator_dashboard_snapshot_aggregates_configured_views(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.post.side_effect = [
        _mock_response(
            {
                "results": [
                    {
                        "id": "discovery-page",
                        "properties": {
                            "Company": {
                                "type": "title",
                                "title": [{"plain_text": "North Star Labs"}],
                            },
                            "Status": {
                                "type": "select",
                                "select": {"name": "Ready"},
                            },
                        },
                    }
                ]
            }
        ),
        _mock_response(
            {
                "results": [
                    {
                        "id": "intake-page",
                        "properties": {
                            "Company": {
                                "type": "title",
                                "title": [{"plain_text": "North Star Labs"}],
                            },
                            "Status": {
                                "type": "select",
                                "select": {"name": "Ready"},
                            },
                        },
                    }
                ]
            }
        ),
        _mock_response(
            {
                "results": [
                    {
                        "id": "queue-page",
                        "properties": {
                            "Lead Reference": {
                                "type": "title",
                                "title": [{"plain_text": "North Star Labs|Mina Yusuf|Saudi Arabia|direct_payroll"}],
                            },
                            "Status": {
                                "type": "select",
                                "select": {"name": "Ready to send"},
                            },
                        },
                    }
                ]
            }
        ),
        _mock_response(
            {
                "results": [
                    {
                        "id": "run-page",
                        "properties": {
                            "Run Marker": {
                                "type": "title",
                                "title": [{"plain_text": "RUN_20260323120000"}],
                            },
                            "Status": {
                                "type": "select",
                                "select": {"name": "Completed"},
                            },
                            "Started At": {
                                "type": "date",
                                "date": {"start": "2026-03-23T12:00:00+00:00"},
                            },
                        },
                    }
                ]
            }
        ),
    ]
    service = NotionService(client=fake_client)

    snapshot = service.get_operator_dashboard_snapshot()

    assert isinstance(snapshot, OperatorDashboardSnapshot)
    assert len(snapshot.discovery_records) == 1
    assert len(snapshot.intake_records) == 1
    assert len(snapshot.outreach_queue_records) == 1
    assert len(snapshot.run_records) == 1


def test_fetch_feedback_signals_reads_outreach_queue_and_pipeline_rows(monkeypatch) -> None:
    _configure_notion_settings(monkeypatch)
    fake_client = MagicMock()
    fake_client.post.side_effect = [
        _mock_response(
            {
                "results": [
                    {
                        "id": "queue-page",
                        "properties": {
                            "Lead Reference": {
                                "type": "title",
                                "title": [{"plain_text": "Guidepoint|Unknown Contact|the UAE|direct_payroll"}],
                            },
                            "Company": {
                                "type": "rich_text",
                                "rich_text": [{"plain_text": "Guidepoint"}],
                            },
                            "Status": {
                                "type": "select",
                                "select": {"name": "Approved"},
                            },
                        },
                    }
                ]
            }
        ),
        _mock_response(
            {
                "results": [
                    {
                        "id": "pipeline-page",
                        "properties": {
                            "Lead Reference": {
                                "type": "title",
                                "title": [{"plain_text": "Guidepoint|Unknown Contact|the UAE|direct_payroll"}],
                            },
                            "Company": {
                                "type": "rich_text",
                                "rich_text": [{"plain_text": "Guidepoint"}],
                            },
                            "Stage": {
                                "type": "select",
                                "select": {"name": "proposal"},
                            },
                            "Outreach Status": {
                                "type": "select",
                                "select": {"name": "sent"},
                            },
                        },
                    }
                ]
            }
        ),
    ]
    service = NotionService(client=fake_client)

    queue_signals = service.fetch_outreach_queue_feedback_signals(limit=10)
    pipeline_signals = service.fetch_pipeline_feedback_signals(limit=10)

    assert queue_signals[0].company_name == "Guidepoint"
    assert queue_signals[0].queue_status == "Approved"
    assert pipeline_signals[0].pipeline_stage == "proposal"
    assert pipeline_signals[0].outreach_status == "sent"
