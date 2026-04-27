"""Tests for the bulk_enrich step in scripts/vibe_prospecting_scan.py.

Mocks `explorium_post` at the module level. No real HTTP calls; no
Explorium credits consumed by this test file.
"""

from __future__ import annotations

import argparse
from typing import Any

import pytest

import scripts.vibe_prospecting_scan as scan
from scripts.vibe_prospecting_scan import (
    BUSINESSES_PATH,
    CREDITS_PER_PROSPECT_EMAIL_ONLY,
    ENRICH_BATCH_SIZE,
    ENRICH_PATH,
    EnrichmentResult,
    PROSPECTS_PATH,
    _extract_email_from_enriched_record,
    enrich_prospect_emails,
    run_scan,
)


# ---------------------------------------------------------------------------
# Unit tests for the extraction helper
# ---------------------------------------------------------------------------

class TestExtractEmail:
    def test_prefers_professions_email(self) -> None:
        out = _extract_email_from_enriched_record({
            "data": {
                "professions_email": "primary@example.com",
                "emails": [{"address": "secondary@example.com"}],
            },
        })
        assert out == "primary@example.com"

    def test_falls_back_to_first_emails_address_when_professions_missing(self) -> None:
        out = _extract_email_from_enriched_record({
            "data": {
                "professions_email": None,
                "emails": [
                    {"address": "first@example.com", "type": "personal"},
                    {"address": "second@example.com", "type": "current"},
                ],
            },
        })
        assert out == "first@example.com"

    def test_returns_none_when_no_addresses_present(self) -> None:
        out = _extract_email_from_enriched_record({
            "data": {"professions_email": "", "emails": []},
        })
        assert out is None

    def test_returns_none_for_malformed_input(self) -> None:
        assert _extract_email_from_enriched_record({}) is None
        assert _extract_email_from_enriched_record({"data": "not a dict"}) is None
        assert _extract_email_from_enriched_record({"data": {"emails": "wrong"}}) is None


# ---------------------------------------------------------------------------
# Unit tests for enrich_prospect_emails
# ---------------------------------------------------------------------------

class TestEnrichProspectEmails:
    def test_empty_input_returns_empty_result(self, monkeypatch) -> None:
        called = []
        monkeypatch.setattr(scan, "explorium_post", lambda *a, **kw: called.append(a))
        result = enrich_prospect_emails(client=None, api_key="k", base_url="b", prospect_ids=[])
        assert result.emails == {}
        assert result.succeeded_count == 0
        assert result.failed_count == 0
        assert result.credits_consumed == 0
        assert called == []  # no API call when input is empty

    def test_happy_path_single_batch(self, monkeypatch) -> None:
        captured = []

        def fake_post(client, api_key, base_url, path, body):
            captured.append((path, body))
            return {
                "data": [
                    {"prospect_id": "pid1", "data": {"professions_email": "a@x.co", "emails": []}},
                    {"prospect_id": "pid2", "data": {"professions_email": "b@x.co", "emails": []}},
                ],
            }

        monkeypatch.setattr(scan, "explorium_post", fake_post)
        result = enrich_prospect_emails(
            client=None, api_key="k", base_url="b",
            prospect_ids=["pid1", "pid2"],
        )

        assert result.emails == {"pid1": "a@x.co", "pid2": "b@x.co"}
        assert result.succeeded_count == 2
        assert result.failed_count == 0
        assert result.credits_consumed == 4  # 2 prospects × 2 credits each
        assert len(captured) == 1
        path, body = captured[0]
        assert path == ENRICH_PATH
        assert body["prospect_ids"] == ["pid1", "pid2"]
        assert body["parameters"] == {"contact_types": ["email"]}

    def test_batches_at_max_size(self, monkeypatch) -> None:
        captured_batches: list[list[str]] = []

        def fake_post(client, api_key, base_url, path, body):
            captured_batches.append(list(body["prospect_ids"]))
            return {"data": [{"prospect_id": pid, "data": {"professions_email": f"{pid}@x.co"}}
                              for pid in body["prospect_ids"]]}

        monkeypatch.setattr(scan, "explorium_post", fake_post)
        # 120 ids → expect batches of 50, 50, 20
        ids = [f"pid{i:03d}" for i in range(120)]
        result = enrich_prospect_emails(client=None, api_key="k", base_url="b", prospect_ids=ids)

        assert len(captured_batches) == 3
        assert len(captured_batches[0]) == ENRICH_BATCH_SIZE
        assert len(captured_batches[1]) == ENRICH_BATCH_SIZE
        assert len(captured_batches[2]) == 20
        assert result.succeeded_count == 120
        assert result.failed_count == 0
        assert result.credits_consumed == 120 * CREDITS_PER_PROSPECT_EMAIL_ONLY

    def test_partial_batch_failure_continues_with_remaining(self, monkeypatch) -> None:
        call_count = {"n": 0}

        def fake_post(client, api_key, base_url, path, body):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated batch failure")
            return {
                "data": [
                    {"prospect_id": pid, "data": {"professions_email": f"{pid}@x.co"}}
                    for pid in body["prospect_ids"]
                ],
            }

        monkeypatch.setattr(scan, "explorium_post", fake_post)
        ids = [f"pid{i}" for i in range(60)]   # two batches: 50 + 10
        result = enrich_prospect_emails(client=None, api_key="k", base_url="b", prospect_ids=ids)

        # First batch failed → those 50 ids are in failed-batch set, no emails
        for pid in ids[:50]:
            assert result.emails[pid] is None
            assert pid in result.prospect_ids_in_failed_batches
        # Second batch succeeded → emails populated
        for pid in ids[50:]:
            assert result.emails[pid] is not None
        assert result.succeeded_count == 10
        assert result.failed_count == 50
        assert result.credits_consumed == 10 * CREDITS_PER_PROSPECT_EMAIL_ONLY  # only successful batch

    def test_full_failure_yields_zero_credits(self, monkeypatch) -> None:
        def fake_post(*args, **kwargs):
            raise RuntimeError("dead")

        monkeypatch.setattr(scan, "explorium_post", fake_post)
        ids = ["pid1", "pid2"]
        result = enrich_prospect_emails(client=None, api_key="k", base_url="b", prospect_ids=ids)
        assert result.succeeded_count == 0
        assert result.failed_count == 2
        assert result.credits_consumed == 0
        assert result.prospect_ids_in_failed_batches == {"pid1", "pid2"}

    def test_succeeded_batch_with_no_email_returned_for_some_prospects(self, monkeypatch) -> None:
        """If Explorium returns the batch successfully but a prospect has no
        email on file, that prospect's email entry stays None and is NOT in
        the failed-batch set. credits are still charged for the whole batch."""
        def fake_post(*args, **kwargs):
            return {
                "data": [
                    {"prospect_id": "pid1", "data": {"professions_email": "found@x.co"}},
                    {"prospect_id": "pid2", "data": {"professions_email": None, "emails": []}},
                ],
            }

        monkeypatch.setattr(scan, "explorium_post", fake_post)
        result = enrich_prospect_emails(
            client=None, api_key="k", base_url="b",
            prospect_ids=["pid1", "pid2"],
        )
        assert result.emails == {"pid1": "found@x.co", "pid2": None}
        assert result.succeeded_count == 1
        assert result.failed_count == 0
        assert result.prospect_ids_in_failed_batches == set()
        assert result.credits_consumed == 4  # full batch charged


# ---------------------------------------------------------------------------
# Integration: run_scan() end-to-end with mocked Explorium + Notion
# ---------------------------------------------------------------------------

class _FakeNotionService:
    """Minimal stand-in. Records every page write so the test can assert
    Email population on intake creates."""

    def __init__(self) -> None:
        self.intake_database_id = "fake-intake-db"
        self.created_pages: list[dict[str, Any]] = []

    def is_intake_configured(self) -> bool:
        return True

    def list_lead_intake_records(self, limit: int = 500) -> list:
        return []

    def _get_database_property_types(self, _db: str) -> dict[str, str]:
        return {
            "Contact": "rich_text", "Role": "rich_text",
            "Company Country": "rich_text", "Campaign": "rich_text",
            "Notes": "rich_text", "Email": "email", "LinkedIn URL": "url",
            "Target Country": "select", "Lane Label": "select",
            "Lead Type Hint": "select", "Status": "select",
        }

    # Property-builder shims that record values verbatim.
    def _title(self, value):                                  return {"title": value}
    def _text_property(self, _t, value):                      return {"text": value} if value else None
    def _email_property(self, _t, value):                     return {"email": value} if value else None
    def _url_property(self, _t, value):                       return {"url": value} if value else None
    def _database_choice_or_text_property(self, _db, name, value):
        return {name: {"select": value}} if value else None
    def _database_option_property(self, _db, name, value):
        return {name: {"select": value}} if value else None

    def _create_page(self, _db: str, properties: dict[str, Any]) -> None:
        self.created_pages.append(properties)


def _make_args(**overrides) -> argparse.Namespace:
    base = {
        "region": "uk",  # uk skips the businesses pre-query
        "icp": "B2",
        "limit": 2,
        "dry_run": False,
        "skip_enrichment": False,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def test_run_scan_populates_email_property_from_bulk_enrich(monkeypatch) -> None:
    """The headline integration assertion: when /v1/prospects returns rows
    without plaintext emails, bulk_enrich is called and the Notion intake
    page gets the enriched email written into the Email property."""
    fake_notion = _FakeNotionService()
    monkeypatch.setattr(scan, "NotionService", lambda: fake_notion)
    monkeypatch.setattr(scan.settings, "VIBE_PROSPECTING_API_KEY", "test-key")

    captured_calls: list[tuple[str, dict]] = []

    def fake_post(client, api_key, base_url, path, body):
        captured_calls.append((path, body))
        if path == BUSINESSES_PATH:
            return {
                "data": [{"business_id": "biz-1"}, {"business_id": "biz-2"}],
                "total_pages": 1,
                "total_results": 2,
            }
        if path == PROSPECTS_PATH:
            return {
                "data": [
                    {
                        "prospect_id": "pid1",
                        "company_name": "Acme Ltd",
                        "first_name": "John",
                        "last_name": "Doe",
                        "job_title": "CFO",
                        "country_name": "United Kingdom",
                        "company_country_code": "gb",
                        "linkedin_url_array": ["linkedin.com/in/john"],
                        "professional_email_hashed": "hash1",
                    },
                    {
                        "prospect_id": "pid2",
                        "company_name": "Beta Co",
                        "first_name": "Jane",
                        "last_name": "Smith",
                        "job_title": "HR Director",
                        "country_name": "United Kingdom",
                        "company_country_code": "gb",
                    },
                ],
                "total_pages": 1,
                "total_results": 2,
            }
        if path == ENRICH_PATH:
            assert body["parameters"] == {"contact_types": ["email"]}
            return {
                "data": [
                    {"prospect_id": "pid1", "data": {
                        "professions_email": "john@acme.com",
                        "professional_email_status": "valid",
                        "emails": [{"address": "john@acme.com", "type": "current"}],
                    }},
                    {"prospect_id": "pid2", "data": {
                        "professions_email": "jane@beta.co",
                        "professional_email_status": "valid",
                        "emails": [],
                    }},
                ],
            }
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(scan, "explorium_post", fake_post)

    rc = run_scan(_make_args())

    assert rc == 0
    paths_called = [c[0] for c in captured_calls]
    assert ENRICH_PATH in paths_called
    enrich_call = next(c for c in captured_calls if c[0] == ENRICH_PATH)
    assert sorted(enrich_call[1]["prospect_ids"]) == ["pid1", "pid2"]

    assert len(fake_notion.created_pages) == 2
    emails_on_pages = [
        page.get("Email", {}).get("email") for page in fake_notion.created_pages
    ]
    assert "john@acme.com" in emails_on_pages
    assert "jane@beta.co" in emails_on_pages


def test_run_scan_skip_enrichment_does_not_call_bulk_enrich(monkeypatch) -> None:
    """--skip-enrichment must not hit /bulk_enrich. The Email property is
    left blank because /v1/prospects only returns hashed addresses."""
    fake_notion = _FakeNotionService()
    monkeypatch.setattr(scan, "NotionService", lambda: fake_notion)
    monkeypatch.setattr(scan.settings, "VIBE_PROSPECTING_API_KEY", "test-key")

    captured_paths: list[str] = []

    def fake_post(client, api_key, base_url, path, body):
        captured_paths.append(path)
        if path == BUSINESSES_PATH:
            return {"data": [{"business_id": "biz-1"}], "total_pages": 1}
        if path == PROSPECTS_PATH:
            return {
                "data": [
                    {
                        "prospect_id": "pid1",
                        "company_name": "Acme Ltd",
                        "first_name": "John",
                        "last_name": "Doe",
                        "job_title": "CFO",
                        "country_name": "United Kingdom",
                        "company_country_code": "gb",
                        "professional_email_hashed": "hash1",
                    },
                ],
                "total_pages": 1,
                "total_results": 1,
            }
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(scan, "explorium_post", fake_post)

    rc = run_scan(_make_args(skip_enrichment=True))
    assert rc == 0
    assert ENRICH_PATH not in captured_paths
    # Email property absent because no plaintext was available
    assert all("Email" not in page for page in fake_notion.created_pages)


def test_run_scan_dry_run_skips_enrichment_entirely(monkeypatch) -> None:
    """--dry-run must skip enrichment AND skip Notion writes."""
    captured_paths: list[str] = []

    def fake_post(client, api_key, base_url, path, body):
        captured_paths.append(path)
        if path == BUSINESSES_PATH:
            return {"data": [{"business_id": "biz-1"}], "total_pages": 1}
        if path == PROSPECTS_PATH:
            return {
                "data": [{
                    "prospect_id": "pid1",
                    "company_name": "Acme Ltd",
                    "first_name": "John", "last_name": "Doe",
                    "country_name": "United Kingdom", "company_country_code": "gb",
                }],
                "total_pages": 1, "total_results": 1,
            }
        raise AssertionError(f"unexpected path: {path}")

    monkeypatch.setattr(scan, "explorium_post", fake_post)
    monkeypatch.setattr(scan.settings, "VIBE_PROSPECTING_API_KEY", "test-key")
    # NotionService is not constructed in dry-run, so no fake needed.

    rc = run_scan(_make_args(dry_run=True))
    assert rc == 0
    assert ENRICH_PATH not in captured_paths
