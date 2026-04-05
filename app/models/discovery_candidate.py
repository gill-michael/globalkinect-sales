from pydantic import BaseModel


class DiscoveryCandidate(BaseModel):
    company_name: str
    company_canonical: str | None = None
    agent_label: str | None = None
    lane_label: str | None = None
    discovery_key: str | None = None
    website_url: str | None = None
    source_url: str | None = None
    source_type: str | None = None
    published_at: str | None = None
    source_priority: int | None = None
    source_trust_score: int | None = None
    service_focus: str | None = None
    evidence: str
    contact_name: str | None = None
    contact_role: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    company_country: str | None = None
    target_country_hint: str | None = None
    buyer_confidence: int | None = None
    account_fit_summary: str | None = None
    campaign: str | None = None
    notes: str | None = None
    status: str = "ready"
