from io import BytesIO

from app.models.lead_discovery_record import LeadDiscoveryRecord
from app.models.lead_intake_record import LeadIntakeRecord
from app.models.operator_console import (
    OperatorDashboardSnapshot,
    OutreachQueueRecord,
    SalesEngineRunRecord,
)
from app.web.operator_console import OperatorConsoleApp


class FakeOperatorConsoleService:
    def __init__(self) -> None:
        self.updated: list[tuple[str, str]] = []

    def is_configured(self) -> bool:
        return True

    def configuration_error(self) -> str:
        return ""

    def dashboard_snapshot(self) -> OperatorDashboardSnapshot:
        return OperatorDashboardSnapshot(
            discovery_records=[
                LeadDiscoveryRecord(page_id="d1", company_name="North Star Labs", status="Ready"),
                LeadDiscoveryRecord(page_id="d2", company_name="Blue Dune Technologies", status="Review"),
            ],
            intake_records=[
                LeadIntakeRecord(page_id="i1", company_name="North Star Labs", status="Ready")
            ],
            outreach_queue_records=[
                OutreachQueueRecord(
                    page_id="q1",
                    lead_reference="North Star Labs|Mina Yusuf|Saudi Arabia|direct_payroll",
                    company_name="North Star Labs",
                    contact_name="Mina Yusuf",
                    status="Ready to send",
                    email_subject="Saudi payroll support",
                ),
                OutreachQueueRecord(
                    page_id="q2",
                    lead_reference="Blue Dune Technologies|Sara Khan|UAE|direct_eor",
                    company_name="Blue Dune Technologies",
                    contact_name="Sara Khan",
                    status="Hold",
                    email_subject="UAE EOR support",
                ),
            ],
            run_records=[
                SalesEngineRunRecord(
                    page_id="r1",
                    run_marker="RUN_1",
                    status="Completed",
                    started_at="2026-03-23T09:00:00+00:00",
                )
            ],
        )

    def list_discovery_records(self, limit: int = 100):
        return self.dashboard_snapshot().discovery_records

    def list_intake_records(self, limit: int = 100):
        return self.dashboard_snapshot().intake_records

    def list_outreach_queue_records(self, limit: int = 100):
        return self.dashboard_snapshot().outreach_queue_records

    def list_sales_engine_runs(self, limit: int = 50):
        return self.dashboard_snapshot().run_records

    def list_pipeline_records(self, limit: int = 200) -> list[dict]:
        # Default fixture returns nothing; subclasses override per test.
        return []

    def list_execution_tasks(self, limit: int = 200) -> list[dict]:
        return []

    def list_deal_support_packages(self, limit: int = 200) -> list[dict]:
        return []

    def update_outreach_queue_status(self, lead_reference: str, status: str) -> None:
        self.updated.append((lead_reference, status))


def _run_app(app: OperatorConsoleApp, environ: dict) -> tuple[str, bytes, list[tuple[str, str]]]:
    response_state: dict[str, object] = {"status": "", "headers": []}

    def start_response(status, headers):
        response_state["status"] = status
        response_state["headers"] = headers

    chunks = app(environ, start_response)
    body = b"".join(chunks)
    return response_state["status"], body, response_state["headers"]  # type: ignore[return-value]


def test_queue_page_renders_outreach_rows() -> None:
    app = OperatorConsoleApp(service=FakeOperatorConsoleService())
    status, body, _headers = _run_app(
        app,
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/queue",
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
        },
    )

    assert status == "200 OK"
    html = body.decode("utf-8")
    assert "Outreach Queue" in html
    assert "North Star Labs" in html
    assert "Approve" in html
    # The previous fourth assertion ("Status and text filters apply
    # together.") was tied to a piece of help-text copy that was removed
    # from the toolbar in early April 2026. The test's intent is "queue
    # page renders rows + actions"; the three remaining assertions cover
    # that fully.


def test_queue_page_filters_by_status_and_search_query() -> None:
    app = OperatorConsoleApp(service=FakeOperatorConsoleService())
    status, body, _headers = _run_app(
        app,
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/queue",
            "QUERY_STRING": "status=Hold&q=Blue",
            "wsgi.input": BytesIO(b""),
        },
    )

    assert status == "200 OK"
    html = body.decode("utf-8")
    assert "Blue Dune Technologies" in html
    assert "North Star Labs" not in html


def test_queue_card_renders_reply_field_when_present() -> None:
    """When the Reply property is populated on the queue record, the
    rendered card includes a 'Prospect reply' details block with the text.
    Operators shouldn't have to leave the Console to read the reply."""

    class ReplyService(FakeOperatorConsoleService):
        def list_outreach_queue_records(self, limit: int = 100):
            return [
                OutreachQueueRecord(
                    page_id="q-replied",
                    lead_reference="Acme Corp|Sara Khan|UAE|direct_eor",
                    company_name="Acme Corp",
                    contact_name="Sara Khan",
                    status="Replied",
                    email_subject="UAE EOR support",
                    reply="Thanks — interested. Can we book a call next week?",
                ),
            ]

    app = OperatorConsoleApp(service=ReplyService())
    status, body, _headers = _run_app(
        app,
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/queue",
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
        },
    )

    assert status == "200 OK"
    html = body.decode("utf-8")
    assert "Prospect reply" in html
    assert "Thanks — interested. Can we book a call next week?" in html


def test_queue_card_omits_reply_block_when_empty() -> None:
    """A record with no reply set should not render an empty 'Prospect reply'
    block — _details_block returns an empty string for falsy input."""
    app = OperatorConsoleApp(service=FakeOperatorConsoleService())
    status, body, _headers = _run_app(
        app,
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/queue",
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
        },
    )

    assert status == "200 OK"
    html = body.decode("utf-8")
    # The default fixture has no replies set, so the heading should be absent.
    assert "Prospect reply" not in html


def test_queue_status_post_updates_service_and_redirects() -> None:
    service = FakeOperatorConsoleService()
    app = OperatorConsoleApp(service=service)
    payload = (
        "lead_reference=North+Star+Labs%7CMina+Yusuf%7CSaudi+Arabia%7Cdirect_payroll"
        "&status=Approved"
    ).encode("utf-8")
    status, _body, headers = _run_app(
        app,
        {
            "REQUEST_METHOD": "POST",
            "PATH_INFO": "/queue/status",
            "QUERY_STRING": "",
            "CONTENT_LENGTH": str(len(payload)),
            "wsgi.input": BytesIO(payload),
        },
    )

    assert status == "303 See Other"
    assert service.updated == [
        ("North Star Labs|Mina Yusuf|Saudi Arabia|direct_payroll", "Approved")
    ]
    location_headers = [value for key, value in headers if key == "Location"]
    assert location_headers
    assert location_headers[0].startswith("/queue?")


# ---------------------------------------------------------------------------
# Pipeline view (Task 3a)
# ---------------------------------------------------------------------------

def _pipeline_record_dict(
    *,
    company: str,
    contact: str,
    lead_type: str,
    outreach_status: str,
    priority: str = "medium",
    last_edited: str = "2026-04-15T09:00:00Z",
) -> dict:
    """Helper that mirrors NotionService.list_pipeline_records output."""
    lead_reference = f"{company}|{contact}|United Arab Emirates|{lead_type}"
    pid = f"page-{company.lower().replace(' ', '-')}"
    return {
        "page_id": pid,
        "page_url": f"https://notion.so/{pid.replace('-', '')}",
        "last_edited_time": last_edited,
        "lead_reference": lead_reference,
        "lead_type": lead_type,
        "company_name": company,
        "contact_name": contact,
        "stage": "contacted",
        "outreach_status": outreach_status,
        "next_action": "review_and_send_message",
        "priority": priority,
        "sales_motion": "direct_client",
        "primary_module": "EOR",
        "bundle_label": "EOR + Payroll",
        "last_updated": "2026-04-15",
    }


class _PipelineFakeService(FakeOperatorConsoleService):
    def __init__(self, records: list[dict]) -> None:
        super().__init__()
        self._records = records

    def list_pipeline_records(self, limit: int = 200) -> list[dict]:
        return list(self._records[:limit])


def test_pipeline_page_renders_pipeline_records() -> None:
    records = [
        _pipeline_record_dict(
            company="Acme Ltd", contact="John Doe",
            lead_type="direct_eor", outreach_status="drafted", priority="high",
        ),
        _pipeline_record_dict(
            company="Beta Co", contact="Jane Smith",
            lead_type="direct_payroll", outreach_status="sent", priority="medium",
        ),
    ]
    app = OperatorConsoleApp(service=_PipelineFakeService(records))
    status, body, _headers = _run_app(
        app,
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/pipeline",
            "QUERY_STRING": "",
            "wsgi.input": BytesIO(b""),
        },
    )

    assert status == "200 OK"
    html = body.decode("utf-8")
    assert ">Pipeline<" in html  # nav link or section header
    assert "Acme Ltd" in html
    assert "Beta Co" in html
    assert "John Doe" in html
    assert "Open in Notion" in html


def test_pipeline_page_filters_by_outreach_status() -> None:
    records = [
        _pipeline_record_dict(
            company="Drafted Co", contact="A",
            lead_type="direct_eor", outreach_status="drafted",
        ),
        _pipeline_record_dict(
            company="Sent Co", contact="B",
            lead_type="direct_eor", outreach_status="sent",
        ),
    ]
    app = OperatorConsoleApp(service=_PipelineFakeService(records))
    status, body, _headers = _run_app(
        app,
        {
            "REQUEST_METHOD": "GET",
            "PATH_INFO": "/pipeline",
            "QUERY_STRING": "status=sent",
            "wsgi.input": BytesIO(b""),
        },
    )

    assert status == "200 OK"
    html = body.decode("utf-8")
    assert "Sent Co" in html
    assert "Drafted Co" not in html


def test_pipeline_page_sorts_by_priority_high_first() -> None:
    records = [
        _pipeline_record_dict(
            company="Low Priority Co", contact="A",
            lead_type="direct_eor", outreach_status="drafted", priority="low",
        ),
        _pipeline_record_dict(
            company="High Priority Co", contact="B",
            lead_type="direct_eor", outreach_status="drafted", priority="high",
        ),
        _pipeline_record_dict(
            company="Medium Priority Co", contact="C",
            lead_type="direct_eor", outreach_status="drafted", priority="medium",
        ),
    ]
    app = OperatorConsoleApp(service=_PipelineFakeService(records))
    _, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/pipeline",
         "QUERY_STRING": "", "wsgi.input": BytesIO(b"")},
    )
    html = body.decode("utf-8")
    high_idx = html.find("High Priority Co")
    medium_idx = html.find("Medium Priority Co")
    low_idx = html.find("Low Priority Co")
    assert 0 < high_idx < medium_idx < low_idx


def test_pipeline_page_empty_state_when_no_records() -> None:
    app = OperatorConsoleApp(service=_PipelineFakeService([]))
    status, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/pipeline",
         "QUERY_STRING": "", "wsgi.input": BytesIO(b"")},
    )
    assert status == "200 OK"
    assert "No pipeline records yet." in body.decode("utf-8")


# ---------------------------------------------------------------------------
# Tasks view (Task 3b)
# ---------------------------------------------------------------------------

def _task_dict(
    *,
    title: str,
    company: str,
    status: str,
    due_in_days: int | None,
    priority: str = "medium",
    task_type: str = "send_message",
) -> dict:
    pid = f"task-{title.lower().replace(' ', '-')}"
    return {
        "page_id": pid,
        "page_url": f"https://notion.so/{pid.replace('-', '')}",
        "last_edited_time": "2026-04-15T09:00:00Z",
        "task_title": title,
        "lead_reference": f"{company}|Sara|UAE|direct_eor",
        "company_name": company,
        "task_type": task_type,
        "description": f"Process the {task_type} for {company}",
        "priority": priority,
        "due_in_days": due_in_days,
        "status": status,
    }


class _TasksFakeService(FakeOperatorConsoleService):
    def __init__(self, records: list[dict]) -> None:
        super().__init__()
        self._records = records

    def list_execution_tasks(self, limit: int = 200) -> list[dict]:
        return list(self._records[:limit])


def test_tasks_page_groups_by_status_with_three_sections() -> None:
    records = [
        _task_dict(title="Send pending one", company="Acme", status="open", due_in_days=0),
        _task_dict(title="Done one", company="Beta", status="completed", due_in_days=3),
        _task_dict(title="Cancelled one", company="Gamma", status="cancelled", due_in_days=5),
    ]
    app = OperatorConsoleApp(service=_TasksFakeService(records))
    status, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/tasks",
         "QUERY_STRING": "", "wsgi.input": BytesIO(b"")},
    )
    assert status == "200 OK"
    html = body.decode("utf-8")
    # Three section headings present
    assert ">Pending<" in html
    assert ">Done<" in html
    assert ">Cancelled<" in html
    # Each task lands in its section
    assert "Send pending one" in html
    assert "Done one" in html
    assert "Cancelled one" in html


def test_tasks_page_sorts_within_pending_by_due_in_days_asc() -> None:
    records = [
        _task_dict(title="Due in 5", company="Five", status="open", due_in_days=5),
        _task_dict(title="Due today", company="Today", status="open", due_in_days=0),
        _task_dict(title="Overdue", company="Overdue", status="open", due_in_days=-2),
    ]
    app = OperatorConsoleApp(service=_TasksFakeService(records))
    _, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/tasks",
         "QUERY_STRING": "", "wsgi.input": BytesIO(b"")},
    )
    html = body.decode("utf-8")
    # Pending section orders most-overdue first (smallest due_in_days)
    overdue_idx = html.find("Overdue")
    today_idx = html.find("Due today")
    five_idx = html.find("Due in 5")
    assert 0 < overdue_idx < today_idx < five_idx


def test_tasks_page_search_filters_across_groups() -> None:
    records = [
        _task_dict(title="Process Acme", company="Acme Ltd", status="open", due_in_days=1),
        _task_dict(title="Process Beta", company="Beta Co", status="completed", due_in_days=2),
    ]
    app = OperatorConsoleApp(service=_TasksFakeService(records))
    _, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/tasks",
         "QUERY_STRING": "q=Beta", "wsgi.input": BytesIO(b"")},
    )
    html = body.decode("utf-8")
    assert "Process Beta" in html
    assert "Process Acme" not in html


def test_tasks_page_empty_state_when_no_records() -> None:
    app = OperatorConsoleApp(service=_TasksFakeService([]))
    _, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/tasks",
         "QUERY_STRING": "", "wsgi.input": BytesIO(b"")},
    )
    html = body.decode("utf-8")
    assert "No pending tasks" in html
    assert "No completed tasks" in html


# ---------------------------------------------------------------------------
# Deal Support view (Task 3c)
# ---------------------------------------------------------------------------

def _deal_support_dict(
    *,
    company: str,
    contact: str,
    lead_type: str,
    stage: str = "proposal",
    proposal_summary: str = "Proposed model: ...",
) -> dict:
    lead_reference = f"{company}|{contact}|United Arab Emirates|{lead_type}"
    pid = f"deal-{company.lower().replace(' ', '-')}"
    return {
        "page_id": pid,
        "page_url": f"https://notion.so/{pid.replace('-', '')}",
        "last_edited_time": "2026-04-15T09:00:00Z",
        "lead_reference": lead_reference,
        "lead_type": lead_type,
        "company_name": company,
        "contact_name": contact,
        "stage": stage,
        "recap_subject": f"Recap: {company} call",
        "proposal_summary": proposal_summary,
        "next_steps": f"Send {company} a one-pager.",
        "objection_response": f"If price is the concern: {company} ROI breakdown.",
    }


class _DealSupportFakeService(FakeOperatorConsoleService):
    def __init__(self, records: list[dict]) -> None:
        super().__init__()
        self._records = records

    def list_deal_support_packages(self, limit: int = 200) -> list[dict]:
        return list(self._records[:limit])


def test_deal_support_page_renders_packages() -> None:
    records = [
        _deal_support_dict(
            company="Acme Ltd", contact="John Doe",
            lead_type="direct_eor", proposal_summary="Acme proposal narrative.",
        ),
        _deal_support_dict(
            company="Beta Co", contact="Jane Smith",
            lead_type="direct_payroll", proposal_summary="Beta proposal narrative.",
        ),
    ]
    app = OperatorConsoleApp(service=_DealSupportFakeService(records))
    status, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/deal-support",
         "QUERY_STRING": "", "wsgi.input": BytesIO(b"")},
    )
    assert status == "200 OK"
    html = body.decode("utf-8")
    assert "Acme Ltd" in html
    assert "Beta Co" in html
    assert "Acme proposal narrative." in html
    assert "Beta proposal narrative." in html
    assert "Open in Notion" in html


def test_deal_support_page_filters_by_motion() -> None:
    records = [
        _deal_support_dict(
            company="EOR Co", contact="A", lead_type="direct_eor"
        ),
        _deal_support_dict(
            company="Payroll Co", contact="B", lead_type="direct_payroll"
        ),
    ]
    app = OperatorConsoleApp(service=_DealSupportFakeService(records))
    _, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/deal-support",
         "QUERY_STRING": "motion=direct_eor", "wsgi.input": BytesIO(b"")},
    )
    html = body.decode("utf-8")
    assert "EOR Co" in html
    assert "Payroll Co" not in html


def test_deal_support_page_truncates_long_proposal_summary() -> None:
    long_proposal = "Long narrative. " * 30
    records = [
        _deal_support_dict(
            company="Acme", contact="X", lead_type="direct_eor",
            proposal_summary=long_proposal,
        ),
    ]
    app = OperatorConsoleApp(service=_DealSupportFakeService(records))
    _, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/deal-support",
         "QUERY_STRING": "", "wsgi.input": BytesIO(b"")},
    )
    html = body.decode("utf-8")
    # Long narrative should have been truncated with an ellipsis
    assert "…" in html


def test_deal_support_page_empty_state_when_no_records() -> None:
    app = OperatorConsoleApp(service=_DealSupportFakeService([]))
    _, body, _ = _run_app(
        app,
        {"REQUEST_METHOD": "GET", "PATH_INFO": "/deal-support",
         "QUERY_STRING": "", "wsgi.input": BytesIO(b"")},
    )
    html = body.decode("utf-8")
    assert "No deal support packages yet." in html
