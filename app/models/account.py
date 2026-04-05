from pydantic import BaseModel


class Account(BaseModel):
    account_name: str
    account_canonical: str
    primary_target_country: str | None = None
    lane_labels: list[str] | None = None
    account_fit_summary: str | None = None
    notes: str | None = None

