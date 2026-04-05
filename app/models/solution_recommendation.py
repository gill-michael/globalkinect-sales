from pydantic import BaseModel

from app.models.platform_terms import BundleLabel, PlatformModule, SalesMotion


class SolutionRecommendation(BaseModel):
    lead_reference: str
    company_name: str
    contact_name: str
    target_country: str
    sales_motion: SalesMotion
    recommended_modules: list[PlatformModule]
    primary_module: PlatformModule
    bundle_label: BundleLabel
    commercial_strategy: str
    rationale: str
