from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.models.platform_terms import BundleLabel, PlatformModule, SalesMotion
from app.utils.time import utc_now_iso

PipelineStage = Literal["new", "contacted", "replied", "call_booked", "proposal", "closed"]
OutreachStatus = Literal["not_started", "drafted", "approved", "sent", "replied"]


class PipelineRecord(BaseModel):
    lead_reference: str
    company_name: str
    company_canonical: str | None = None
    contact_name: str
    lead_type: str
    target_country: str
    score: int
    priority: str
    sales_motion: SalesMotion | None = None
    primary_module: PlatformModule | None = None
    bundle_label: BundleLabel | None = None
    recommended_modules: list[PlatformModule] | None = None
    stage: PipelineStage
    outreach_status: OutreachStatus
    created_at: str = Field(default_factory=utc_now_iso)
    last_updated_at: str = Field(default_factory=utc_now_iso)
    last_outreach_at: Optional[str] = None
    last_response_at: Optional[str] = None
    last_contacted: Optional[str] = None
    next_action: Optional[str] = None
    notes: Optional[str] = None
