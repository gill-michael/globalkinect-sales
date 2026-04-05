from pydantic import BaseModel, Field

from app.models.lead import Lead


class DiscoveryQualification(BaseModel):
    lead: Lead
    evidence_summary: str = Field(min_length=1)
    confidence_score: int = Field(ge=1, le=10)
    decision: str
    qualification_notes: str | None = None
