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
    assert "Status and text filters apply together." in html


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
