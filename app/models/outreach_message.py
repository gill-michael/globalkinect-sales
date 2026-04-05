from pydantic import BaseModel

from app.models.platform_terms import BundleLabel, PlatformModule, SalesMotion


class OutreachMessage(BaseModel):
    lead_reference: str
    company_name: str
    contact_name: str
    contact_role: str
    lead_type: str
    target_country: str
    sales_motion: SalesMotion | None = None
    primary_module: PlatformModule | None = None
    bundle_label: BundleLabel | None = None
    linkedin_message: str
    email_subject: str
    email_message: str
    follow_up_message: str
