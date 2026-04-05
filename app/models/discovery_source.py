from typing import Any

from pydantic import BaseModel, Field


class DiscoverySource(BaseModel):
    company_name: str
    agent_label: str | None = None
    lane_label: str | None = None
    feed_url: str | None = None
    website_url: str | None = None
    source_type: str = "careers_feed"
    company_country: str | None = None
    default_target_country: str | None = None
    target_countries: list[str] = Field(default_factory=list)
    lead_type_hint: str | None = None
    service_focus: str | None = None
    campaign: str | None = None
    watch_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    derive_company_name_from_title: bool = False
    entry_url_keywords: list[str] = Field(default_factory=list)
    same_domain_only: bool = True
    fetch_detail_pages: bool = False
    source_priority: int = 5
    trust_score: int = 5
    active: bool = True
    max_items: int | None = None
    entries: list[dict[str, Any]] = Field(default_factory=list)
