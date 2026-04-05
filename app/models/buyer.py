from pydantic import BaseModel


class Buyer(BaseModel):
    buyer_key: str
    buyer_name: str
    buyer_canonical: str
    account_name: str
    account_canonical: str
    contact_role: str | None = None
    email: str | None = None
    linkedin_url: str | None = None
    target_country: str | None = None
    buyer_confidence: int | None = None
    lane_labels: list[str] | None = None
    notes: str | None = None

