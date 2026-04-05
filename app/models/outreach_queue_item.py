from pydantic import BaseModel

from app.models.platform_terms import BundleLabel, PlatformModule, SalesMotion


class OutreachQueueItem(BaseModel):
    lead_reference: str
    company_name: str
    company_canonical: str | None = None
    contact_name: str
    contact_role: str
    priority: str
    target_country: str
    sales_motion: SalesMotion | None = None
    primary_module: PlatformModule | None = None
    bundle_label: BundleLabel | None = None
    email_subject: str
    email_message: str
    linkedin_message: str
    follow_up_message: str
    status: str = "ready_to_send"
    generated_at: str
    run_marker: str
    notes: str | None = None
