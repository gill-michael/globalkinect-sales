from pydantic import BaseModel


class LeadIntakeRecord(BaseModel):
    page_id: str
    company_name: str
    company_canonical: str | None = None
    lane_label: str | None = None
    contact_name: str | None = None
    contact_role: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    company_country: str | None = None
    target_country: str | None = None
    buyer_confidence: int | None = None
    account_fit_summary: str | None = None
    lead_type_hint: str | None = None
    campaign: str | None = None
    notes: str | None = None
    status: str | None = None
    lead_reference: str | None = None
    processed_at: str | None = None
