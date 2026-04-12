from pydantic import BaseModel, Field


class OpportunityRecord(BaseModel):
    page_id: str
    company_name: str
    contact_name: str | None = None
    contact_role: str | None = None
    contact_email: str | None = None
    linkedin_url: str | None = None
    countries: list[str] = Field(default_factory=list)
    icp: str | None = None
    source: str | None = None
    headcount: str | None = None
    notes: str | None = None
    status: str | None = None
    next_action: str | None = None
    next_action_date: str | None = None
    fit_score: int | None = None
    modules_interested_in: list[str] = Field(default_factory=list)
    operating_model_preference: str | None = None
    current_setup: str | None = None
    main_problem: str | None = None
    expanding_to: list[str] = Field(default_factory=list)
    estimated_headcount_at_start: int | None = None
    demo_date: str | None = None
