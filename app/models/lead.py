from pydantic import BaseModel
from typing import Optional


class Lead(BaseModel):
    company_name: str
    company_canonical: Optional[str] = None
    lane_label: Optional[str] = None
    contact_name: str
    contact_role: str
    email: Optional[str] = None
    linkedin_url: Optional[str] = None
    company_country: Optional[str] = None
    target_country: Optional[str] = None
    buyer_confidence: Optional[int] = None
    account_fit_summary: Optional[str] = None
    lead_type: Optional[str] = None
    fit_reason: Optional[str] = None
    status: str = "new"
    score: Optional[int] = None
    priority: Optional[str] = None
    recommended_angle: Optional[str] = None
    feedback_summary: Optional[str] = None
