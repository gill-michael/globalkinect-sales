from pydantic import BaseModel, Field

from app.models.lead_discovery_record import LeadDiscoveryRecord
from app.models.lead_intake_record import LeadIntakeRecord


class OutreachQueueRecord(BaseModel):
    page_id: str
    lead_reference: str
    company_name: str | None = None
    company_canonical: str | None = None
    contact_name: str | None = None
    contact_role: str | None = None
    priority: str | None = None
    target_country: str | None = None
    sales_motion: str | None = None
    primary_module: str | None = None
    bundle_label: str | None = None
    email_subject: str | None = None
    email_message: str | None = None
    linkedin_message: str | None = None
    follow_up_message: str | None = None
    status: str | None = None
    generated_at: str | None = None
    run_marker: str | None = None
    notes: str | None = None


class SalesEngineRunRecord(BaseModel):
    page_id: str
    run_marker: str
    status: str
    started_at: str
    run_mode: str | None = None
    completed_at: str | None = None
    lead_count: int = 0
    outreach_count: int = 0
    pipeline_count: int = 0
    task_count: int = 0
    error_summary: str | None = None
    triggered_by: str | None = None
    notes: str | None = None


class OperatorDashboardSnapshot(BaseModel):
    discovery_records: list[LeadDiscoveryRecord] = Field(default_factory=list)
    intake_records: list[LeadIntakeRecord] = Field(default_factory=list)
    outreach_queue_records: list[OutreachQueueRecord] = Field(default_factory=list)
    run_records: list[SalesEngineRunRecord] = Field(default_factory=list)
