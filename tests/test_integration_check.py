from app.orchestrators.integration_check import (
    INTEGRATION_TEST_PREFIX,
    IntegrationCheckRunner,
    format_integration_check_report,
)
from app.services.config import settings


class _UnconfiguredService:
    def is_configured(self) -> bool:
        return False


class _FakeResponse:
    def __init__(self, data):
        self.data = data


class _FakeSupabaseQuery:
    def __init__(self, rows):
        self._rows = rows
        self._filtered_rows = rows
        self._limit = None

    def select(self, _fields: str):
        return self

    def like(self, field_name: str, pattern: str):
        marker = pattern.strip("%")
        self._filtered_rows = [
            row for row in self._rows if marker in str(row.get(field_name, ""))
        ]
        return self

    def limit(self, limit: int):
        self._limit = limit
        return self

    def execute(self):
        if self._limit is None:
            return _FakeResponse(self._filtered_rows)
        return _FakeResponse(self._filtered_rows[: self._limit])


class _FakeSupabaseClient:
    def __init__(self, rows_by_table):
        self.rows_by_table = rows_by_table

    def table(self, table_name: str):
        return _FakeSupabaseQuery(self.rows_by_table.setdefault(table_name, []))


class _FakeSupabaseService:
    TABLE_LEADS = "leads"
    TABLE_OUTREACH_MESSAGES = "outreach_messages"
    TABLE_PIPELINE_RECORDS = "pipeline_records"
    TABLE_SOLUTION_RECOMMENDATIONS = "solution_recommendations"
    TABLE_DEAL_SUPPORT_PACKAGES = "deal_support_packages"
    TABLE_EXECUTION_TASKS = "execution_tasks"

    def __init__(self):
        self.rows_by_table = {
            self.TABLE_LEADS: [],
            self.TABLE_OUTREACH_MESSAGES: [],
            self.TABLE_PIPELINE_RECORDS: [],
            self.TABLE_SOLUTION_RECOMMENDATIONS: [],
            self.TABLE_DEAL_SUPPORT_PACKAGES: [],
            self.TABLE_EXECUTION_TASKS: [],
        }
        self.client = _FakeSupabaseClient(self.rows_by_table)

    def is_configured(self) -> bool:
        return True

    def insert_leads(self, leads):
        rows = [lead.model_dump() for lead in leads]
        self.rows_by_table[self.TABLE_LEADS].extend(rows)
        return _FakeResponse(rows)

    def insert_outreach_messages(self, messages):
        rows = [message.model_dump() for message in messages]
        self.rows_by_table[self.TABLE_OUTREACH_MESSAGES].extend(rows)
        return _FakeResponse(rows)

    def insert_pipeline_records(self, records):
        rows = [record.model_dump() for record in records]
        self.rows_by_table[self.TABLE_PIPELINE_RECORDS].extend(rows)
        return _FakeResponse(rows)

    def insert_solution_recommendations(self, recommendations):
        rows = [recommendation.model_dump() for recommendation in recommendations]
        self.rows_by_table[self.TABLE_SOLUTION_RECOMMENDATIONS].extend(rows)
        return _FakeResponse(rows)

    def insert_deal_support_packages(self, packages):
        rows = [package.model_dump() for package in packages]
        self.rows_by_table[self.TABLE_DEAL_SUPPORT_PACKAGES].extend(rows)
        return _FakeResponse(rows)

    def insert_execution_tasks(self, tasks):
        rows = [task.model_dump() for task in tasks]
        self.rows_by_table[self.TABLE_EXECUTION_TASKS].extend(rows)
        return _FakeResponse(rows)


class _FakeNotionSyncAgent:
    def __init__(self):
        self.last_payload = None

    def is_configured(self) -> bool:
        return True

    def sync_operating_views(
        self,
        leads,
        pipeline_records,
        solution_recommendations,
        execution_tasks,
        deal_support_packages,
    ):
        self.last_payload = {
            "leads": leads,
            "pipeline_records": pipeline_records,
            "solution_recommendations": solution_recommendations,
            "execution_tasks": execution_tasks,
            "deal_support_packages": deal_support_packages,
        }
        return {
            "leads": [{"id": "lead-page-1"}, {"id": "lead-page-2"}],
            "pipeline_records": [{"id": "pipeline-page-1"}, {"id": "pipeline-page-2"}],
            "solution_recommendations": [
                {"id": "solution-page-1"},
                {"id": "solution-page-2"},
            ],
            "execution_tasks": [{"id": "task-page-1"}, {"id": "task-page-2"}],
            "deal_support_packages": [{"id": "deal-page-1"}, {"id": "deal-page-2"}],
        }


def test_validate_environment_reports_missing_values(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_PUBLISHABLE_KEY", "")
    monkeypatch.setattr(settings, "NOTION_API_KEY", "")
    monkeypatch.setattr(settings, "NOTION_LEADS_DATABASE_ID", "")
    monkeypatch.setattr(settings, "NOTION_PIPELINE_DATABASE_ID", "")
    monkeypatch.setattr(settings, "NOTION_SOLUTIONS_DATABASE_ID", "")
    monkeypatch.setattr(settings, "NOTION_TASKS_DATABASE_ID", "")
    monkeypatch.setattr(settings, "NOTION_DEAL_SUPPORT_DATABASE_ID", "")

    runner = IntegrationCheckRunner(
        supabase_service=_UnconfiguredService(),
        notion_sync_agent=_UnconfiguredService(),
        database_url="",
    )

    result = runner.validate_environment()

    assert result.checks["DATABASE_URL"] is False
    assert result.supabase_ready is False
    assert result.notion_ready is False
    assert result.cleanup_ready is False


def test_build_test_leads_uses_integration_marker() -> None:
    runner = IntegrationCheckRunner(
        supabase_service=_UnconfiguredService(),
        notion_sync_agent=_UnconfiguredService(),
        database_url="",
    )

    leads = runner.build_test_leads("validation_run")

    assert len(leads) == 2
    assert all(INTEGRATION_TEST_PREFIX in lead.company_name for lead in leads)
    assert all("validation_run" in lead.company_name for lead in leads)
    assert all(lead.email.endswith("@example.com") for lead in leads if lead.email)


def test_run_returns_success_summary_with_mocked_services(monkeypatch) -> None:
    monkeypatch.setattr(settings, "DATABASE_URL", "postgresql://example")
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://supabase.example.com")
    monkeypatch.setattr(settings, "SUPABASE_PUBLISHABLE_KEY", "supabase-key")
    monkeypatch.setattr(settings, "NOTION_API_KEY", "notion-key")
    monkeypatch.setattr(settings, "NOTION_LEADS_DATABASE_ID", "leads-db")
    monkeypatch.setattr(settings, "NOTION_PIPELINE_DATABASE_ID", "pipeline-db")
    monkeypatch.setattr(settings, "NOTION_SOLUTIONS_DATABASE_ID", "solutions-db")
    monkeypatch.setattr(settings, "NOTION_TASKS_DATABASE_ID", "tasks-db")
    monkeypatch.setattr(settings, "NOTION_DEAL_SUPPORT_DATABASE_ID", "deal-db")

    fake_supabase = _FakeSupabaseService()
    fake_notion = _FakeNotionSyncAgent()
    runner = IntegrationCheckRunner(
        supabase_service=fake_supabase,
        notion_sync_agent=fake_notion,
        database_url="postgresql://example",
    )

    result = runner.run(run_marker="validation_run")
    report = format_integration_check_report(result)

    assert result.run_marker == f"{INTEGRATION_TEST_PREFIX}_validation_run"
    assert result.generated_counts["leads"] == 2
    assert result.supabase.insert_success is True
    assert result.supabase.fetch_success is True
    assert result.notion.sync_success is True
    assert result.notion.synced_counts["leads"] == 2
    assert result.is_fully_integration_ready is True
    assert fake_notion.last_payload is not None
    assert "fully integration-ready: yes" in report
    assert result.run_marker in report
    assert all(
        result.run_marker in lead.company_name
        for lead in fake_notion.last_payload["leads"]
    )


def test_cleanup_requires_database_url_when_requested() -> None:
    runner = IntegrationCheckRunner(
        supabase_service=_UnconfiguredService(),
        notion_sync_agent=_UnconfiguredService(),
        database_url="",
    )

    result = runner.cleanup()

    assert result.success is False
    assert "DATABASE_URL" in (result.error or "")
    assert result.marker == INTEGRATION_TEST_PREFIX
