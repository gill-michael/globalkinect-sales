"""Read-only proxy endpoints that expose Notion data to the dashboard.

The dashboard has no Notion client, so these endpoints fetch from Notion via
NotionService and return JSON. Notion API failures are swallowed into an empty
array plus an X-Notion-Proxy-Error header rather than a 500.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

from fastapi import APIRouter, Query, Response

from app.services.notion_service import NotionService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()

ERROR_HEADER = "X-Notion-Proxy-Error"


def _get_notion_service() -> NotionService:
    return NotionService()


def _safe_fetch(
    response: Response,
    fetch: Callable[[], list[Any]],
    context: str,
) -> list[dict[str, Any]]:
    try:
        records = fetch()
    except Exception as exc:
        logger.warning("Notion proxy %s failed: %s", context, exc)
        response.headers[ERROR_HEADER] = f"{context}: {exc}"
        return []
    return [_dump(record) for record in records]


def _dump(record: Any) -> dict[str, Any]:
    dump = getattr(record, "model_dump", None)
    if dump is not None:
        return dump(mode="json")
    if hasattr(record, "dict"):
        return record.dict()
    return dict(record)


def _matches(value: Any, wanted: str | None) -> bool:
    if wanted is None:
        return True
    if value is None:
        return False
    return str(value).strip().lower() == wanted.strip().lower()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        text = value.replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except ValueError:
        return None


@router.get("/discovery")
def get_discovery(
    response: Response,
    status: str | None = Query(default=None),
    lane: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    service = _get_notion_service()
    records = _safe_fetch(
        response,
        lambda: service.list_lead_discovery_records(limit=limit),
        context="discovery",
    )
    if status is not None or lane is not None:
        records = [
            record
            for record in records
            if _matches(record.get("status"), status)
            and _matches(record.get("lane_label"), lane)
        ]
    return records[:limit]


@router.get("/intake")
def get_intake(
    response: Response,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
) -> list[dict[str, Any]]:
    service = _get_notion_service()
    records = _safe_fetch(
        response,
        lambda: service.list_lead_intake_records(limit=limit),
        context="intake",
    )
    if status is not None:
        records = [
            record for record in records if _matches(record.get("status"), status)
        ]
    return records[:limit]


@router.get("/runs")
def get_runs(
    response: Response,
    limit: int = Query(default=20, ge=1, le=200),
) -> list[dict[str, Any]]:
    service = _get_notion_service()
    records = _safe_fetch(
        response,
        lambda: service.list_sales_engine_runs(limit=limit),
        context="runs",
    )
    for record in records:
        started = _parse_iso(record.get("started_at"))
        completed = _parse_iso(record.get("completed_at"))
        if started and completed:
            record["duration_seconds"] = (completed - started).total_seconds()
        else:
            record["duration_seconds"] = None
    return records[:limit]


@router.get("/outreach-queue")
def get_outreach_queue(
    response: Response,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    service = _get_notion_service()
    records = _safe_fetch(
        response,
        lambda: service.list_outreach_queue_records(limit=limit),
        context="outreach-queue",
    )
    if status is not None:
        records = [
            record for record in records if _matches(record.get("status"), status)
        ]
    return records[:limit]
