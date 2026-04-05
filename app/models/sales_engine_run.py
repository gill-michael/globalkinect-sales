from pydantic import BaseModel


class SalesEngineRun(BaseModel):
    run_marker: str
    status: str
    started_at: str
    run_mode: str = "live"
    completed_at: str | None = None
    lead_count: int = 0
    outreach_count: int = 0
    pipeline_count: int = 0
    task_count: int = 0
    error_summary: str | None = None
    triggered_by: str = "manual"
    notes: str | None = None
