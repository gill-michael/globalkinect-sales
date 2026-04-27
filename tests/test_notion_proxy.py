"""Integration tests for the api/ FastAPI proxy.

The proxy calls into NotionService. These tests verify that each PATCH
endpoint:
1. Calls the right NotionService method with the right arguments.
2. Validates input where applicable (rejects unknown statuses, empty notes).
3. Surfaces errors via the X-Notion-Proxy-Error header rather than 500s.

Each test installs a fake NotionService into the router by monkey-patching
`api.app.routers.notion_proxy._get_notion_service`. The fake records every
method call so the test can assert exactly what was invoked.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.app.main import app
from api.app.routers import notion_proxy


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


class FakeNotionService:
    """Recording-fake. Every method append onto `calls` so tests can
    assert exactly what was invoked."""

    def __init__(self, *, raise_on: str | None = None) -> None:
        self.calls: list[tuple[str, tuple, dict]] = []
        self.raise_on = raise_on

    def _record(self, name: str, args: tuple, kwargs: dict) -> None:
        if self.raise_on == name:
            raise RuntimeError(f"forced failure in {name}")
        self.calls.append((name, args, kwargs))

    # --- status writes ---

    def update_outreach_queue_record_status(self, page_id: str, status: str) -> dict[str, Any]:
        self._record("update_outreach_queue_record_status", (page_id, status), {})
        return {"id": page_id, "properties": {"Status": {"select": {"name": status}}}}

    def update_lead_intake_record_status(self, page_id: str, status: str) -> dict[str, Any]:
        self._record("update_lead_intake_record_status", (page_id, status), {})
        return {"id": page_id, "properties": {"Status": {"select": {"name": status}}}}

    def append_sales_engine_run_note(self, page_id: str, note: str) -> dict[str, Any]:
        self._record("append_sales_engine_run_note", (page_id, note), {})
        return {"id": page_id, "properties": {"Notes": {"rich_text": [{"plain_text": note}]}}}

    # --- read paths (so /health / list endpoints don't blow up if a test
    #     accidentally hits them; not exhaustive — read paths aren't the
    #     subject of this test file).

    def list_lead_discovery_records(self, limit: int = 50) -> list[Any]:
        self._record("list_lead_discovery_records", (), {"limit": limit})
        return []

    def list_lead_intake_records(self, limit: int = 50) -> list[Any]:
        self._record("list_lead_intake_records", (), {"limit": limit})
        return []

    def list_sales_engine_runs(self, limit: int = 20) -> list[Any]:
        self._record("list_sales_engine_runs", (), {"limit": limit})
        return []

    def list_outreach_queue_records(self, limit: int = 100) -> list[Any]:
        self._record("list_outreach_queue_records", (), {"limit": limit})
        return []


@pytest.fixture
def fake_notion(monkeypatch: pytest.MonkeyPatch) -> FakeNotionService:
    fake = FakeNotionService()
    monkeypatch.setattr(notion_proxy, "_get_notion_service", lambda: fake)
    return fake


def test_health_endpoint_returns_ok(client: TestClient) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_patch_outreach_status_calls_update_method_with_args(
    client: TestClient,
    fake_notion: FakeNotionService,
) -> None:
    response = client.patch(
        "/api/notion/outreach-queue/page-123/status",
        json={"status": "approved"},
    )
    assert response.status_code == 200
    assert fake_notion.calls == [
        ("update_outreach_queue_record_status", ("page-123", "approved"), {}),
    ]


def test_patch_outreach_status_rejects_unknown_status(
    client: TestClient,
    fake_notion: FakeNotionService,
) -> None:
    response = client.patch(
        "/api/notion/outreach-queue/page-123/status",
        json={"status": "delete_everything"},
    )
    assert response.status_code == 400
    assert response.headers.get("X-Notion-Proxy-Error", "").startswith("invalid status")
    assert fake_notion.calls == []


def test_patch_outreach_approve_uses_approved_value(
    client: TestClient,
    fake_notion: FakeNotionService,
) -> None:
    response = client.patch("/api/notion/outreach-queue/page-x/approve")
    assert response.status_code == 200
    assert fake_notion.calls == [
        ("update_outreach_queue_record_status", ("page-x", "approved"), {}),
    ]


def test_patch_outreach_hold_uses_hold_value(
    client: TestClient,
    fake_notion: FakeNotionService,
) -> None:
    response = client.patch("/api/notion/outreach-queue/page-y/hold")
    assert response.status_code == 200
    assert fake_notion.calls == [
        ("update_outreach_queue_record_status", ("page-y", "hold"), {}),
    ]


def test_patch_intake_status_calls_update_method_with_args(
    client: TestClient,
    fake_notion: FakeNotionService,
) -> None:
    response = client.patch(
        "/api/notion/intake/intake-1/status",
        json={"status": "ingested"},
    )
    assert response.status_code == 200
    assert fake_notion.calls == [
        ("update_lead_intake_record_status", ("intake-1", "ingested"), {}),
    ]


def test_patch_intake_status_rejects_unknown_status(
    client: TestClient,
    fake_notion: FakeNotionService,
) -> None:
    response = client.patch(
        "/api/notion/intake/intake-1/status",
        json={"status": "approved"},  # 'approved' isn't in INTAKE_STATUS_VALUES
    )
    assert response.status_code == 400
    assert response.headers.get("X-Notion-Proxy-Error", "").startswith("invalid status")


def test_patch_runs_note_appends_text(
    client: TestClient,
    fake_notion: FakeNotionService,
) -> None:
    response = client.patch(
        "/api/notion/runs/run-9/note",
        json={"note": "Reviewed by Sara — looks fine"},
    )
    assert response.status_code == 200
    assert fake_notion.calls == [
        ("append_sales_engine_run_note", ("run-9", "Reviewed by Sara — looks fine"), {}),
    ]


def test_patch_runs_note_rejects_empty_note(
    client: TestClient,
    fake_notion: FakeNotionService,
) -> None:
    response = client.patch(
        "/api/notion/runs/run-9/note",
        json={"note": "   "},
    )
    assert response.status_code == 400
    assert response.headers.get("X-Notion-Proxy-Error", "") == "note text is required"


def test_patch_failure_surfaces_error_header_not_500(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If NotionService throws, the proxy is expected to surface the error
    via X-Notion-Proxy-Error and a 500 status (per _safe_write)."""
    failing = FakeNotionService(raise_on="update_outreach_queue_record_status")
    monkeypatch.setattr(notion_proxy, "_get_notion_service", lambda: failing)

    response = client.patch(
        "/api/notion/outreach-queue/page-fail/status",
        json={"status": "approved"},
    )
    assert response.status_code == 500
    assert response.headers.get("X-Notion-Proxy-Error", "").startswith(
        "outreach-queue-status:"
    )
