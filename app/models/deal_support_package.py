from pydantic import BaseModel

from app.models.platform_terms import BundleLabel, PlatformModule, SalesMotion
from app.models.pipeline_record import PipelineStage


class DealSupportPackage(BaseModel):
    lead_reference: str
    company_name: str
    contact_name: str
    lead_type: str
    target_country: str
    sales_motion: SalesMotion | None = None
    primary_module: PlatformModule | None = None
    bundle_label: BundleLabel | None = None
    recommended_modules: list[PlatformModule] | None = None
    stage: PipelineStage
    call_prep_summary: str
    recap_email_subject: str
    recap_email_body: str
    proposal_summary: str
    next_steps_message: str
    objection_response: str
