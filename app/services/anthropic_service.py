from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.discovery_qualification import DiscoveryQualification
from app.models.lead import Lead
from app.models.lead_discovery_record import LeadDiscoveryRecord
from app.models.lead_intake_record import LeadIntakeRecord
from app.services.config import settings
from app.utils.logger import get_logger
from app.utils.target_markets import (
    market_score,
    normalize_target_country,
    supported_markets_text,
)

logger = get_logger(__name__)

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


class AnthropicService:
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    PLACEHOLDER_VALUES = {
        "",
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "unknown",
        "unknown contact",
        "unknown role",
        "not provided",
        "not available",
        "tbd",
    }

    def __init__(self, client: Any | None = None) -> None:
        self.api_key = settings.ANTHROPIC_API_KEY
        self.discovery_model = (
            settings.ANTHROPIC_DISCOVERY_MODEL
            or settings.ANTHROPIC_MODEL
            or self.DEFAULT_MODEL
        )
        self.model = (
            settings.ANTHROPIC_LEAD_RESEARCH_MODEL
            or settings.ANTHROPIC_MODEL
            or self.DEFAULT_MODEL
        )
        self.client = None

        if client is not None:
            self.client = client
            return

        if Anthropic is None:
            logger.warning("Anthropic package is not installed. Anthropic service is unavailable.")
            return

        if self.api_key:
            self.client = Anthropic(api_key=self.api_key)

    def is_configured(self) -> bool:
        return self.client is not None

    def normalize_lead_from_intake(
        self,
        intake_record: LeadIntakeRecord,
        campaign: str | None = None,
    ) -> Lead:
        if not self.is_configured():
            raise RuntimeError("Anthropic service is not configured.")

        parsed = self._structured_request(
            model=self.model,
            system=self._build_lead_research_instructions(),
            user_message=self._build_lead_research_input(intake_record, campaign),
            tool_name="normalize_lead",
            tool_description="Return the normalized lead data as structured output.",
            schema_model=_LeadResearchOutput,
        )
        if parsed is None:
            raise RuntimeError("Anthropic did not return a structured lead payload.")

        return Lead(
            company_name=self._coalesce(parsed.company_name, intake_record.company_name),
            company_canonical=intake_record.company_canonical,
            lane_label=intake_record.lane_label,
            contact_name=self._coalesce(
                parsed.contact_name,
                intake_record.contact_name,
            )
            or "Unknown Contact",
            contact_role=self._coalesce(
                parsed.contact_role,
                intake_record.contact_role,
            )
            or "Unknown Role",
            email=self._coalesce(parsed.email, intake_record.email),
            linkedin_url=self._coalesce(parsed.linkedin_url, intake_record.linkedin_url),
            company_country=self._coalesce(
                parsed.company_country,
                intake_record.company_country,
            ),
            target_country=self._normalize_target_country(
                parsed.target_country or intake_record.target_country
            ),
            buyer_confidence=self._normalized_buyer_confidence(
                intake_record.buyer_confidence,
                intake_record.contact_name,
                intake_record.contact_role,
            ),
            account_fit_summary=self._coalesce(
                intake_record.account_fit_summary,
                intake_record.notes,
            ),
            lead_type=self._normalize_lead_type(
                parsed.lead_type or intake_record.lead_type_hint
            ),
            fit_reason=self._coalesce(parsed.fit_reason, intake_record.notes),
        )

    def qualify_discovery_record(
        self,
        discovery_record: LeadDiscoveryRecord,
        campaign: str | None = None,
    ) -> DiscoveryQualification:
        if not self.is_configured():
            raise RuntimeError("Anthropic service is not configured.")

        parsed = self._structured_request(
            model=self.discovery_model,
            system=self._build_discovery_qualification_instructions(),
            user_message=self._build_discovery_qualification_input(discovery_record, campaign),
            tool_name="qualify_discovery",
            tool_description="Return the structured discovery qualification output.",
            schema_model=_DiscoveryQualificationOutput,
        )
        if parsed is None:
            raise RuntimeError("Anthropic did not return a structured discovery payload.")

        lead = Lead(
            company_name=self._coalesce(
                parsed.company_name,
                discovery_record.company_name,
            ),
            company_canonical=discovery_record.company_canonical,
            lane_label=discovery_record.lane_label,
            contact_name=self._coalesce(
                parsed.contact_name,
                discovery_record.contact_name,
            )
            or "Unknown Contact",
            contact_role=self._coalesce(
                parsed.contact_role,
                discovery_record.contact_role,
            )
            or "Unknown Role",
            email=self._coalesce(parsed.email, discovery_record.email),
            linkedin_url=self._coalesce(parsed.linkedin_url, discovery_record.linkedin_url),
            company_country=self._coalesce(
                parsed.company_country,
                discovery_record.company_country,
            ),
            target_country=self._normalize_target_country(
                parsed.target_country or discovery_record.target_country_hint
            ),
            buyer_confidence=self._normalized_buyer_confidence(
                discovery_record.buyer_confidence,
                parsed.contact_name or discovery_record.contact_name,
                parsed.contact_role or discovery_record.contact_role,
            ),
            account_fit_summary=self._coalesce(
                discovery_record.account_fit_summary,
                parsed.fit_reason,
                discovery_record.notes,
            ),
            lead_type=self._normalize_lead_type(parsed.lead_type),
            fit_reason=self._coalesce(parsed.fit_reason, parsed.evidence_summary),
        )
        decision = self._normalize_discovery_decision(parsed.decision)
        confidence_score = max(1, min(parsed.confidence_score, 10))

        return DiscoveryQualification(
            lead=lead,
            evidence_summary=parsed.evidence_summary,
            confidence_score=confidence_score,
            decision=decision,
            qualification_notes=self._coalesce(parsed.qualification_notes),
        )

    def _structured_request(
        self,
        model: str,
        system: str,
        user_message: str,
        tool_name: str,
        tool_description: str,
        schema_model: type[BaseModel],
    ) -> BaseModel | None:
        response = self.client.messages.create(
            model=model,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user_message}],
            tools=[
                {
                    "name": tool_name,
                    "description": tool_description,
                    "input_schema": schema_model.model_json_schema(),
                }
            ],
            tool_choice={"type": "tool", "name": tool_name},
        )
        tool_block = next(
            (b for b in response.content if b.type == "tool_use"),
            None,
        )
        if tool_block is None:
            return None
        return schema_model.model_validate(tool_block.input)

    def build_discovery_qualification_fallback(
        self,
        discovery_record: LeadDiscoveryRecord,
        campaign: str | None = None,
    ) -> DiscoveryQualification:
        target_country = self._normalize_target_country(discovery_record.target_country_hint)
        lead_type = self._infer_lead_type_from_discovery(discovery_record)
        confidence_score = 0
        commercial_context = " ".join(
            value
            for value in [
                discovery_record.evidence,
                discovery_record.notes,
                discovery_record.contact_role,
            ]
            if value
        ).lower()
        has_buyer_hypothesis = "buyer hypothesis:" in commercial_context or any(
            token in commercial_context
            for token in {
                "head of people",
                "people operations",
                "payroll manager",
                "finance director",
                "cfo",
                "coo",
                "country manager",
                "hr director",
                "hris owner",
            }
        )
        has_commercial_trigger = "commercial trigger:" in commercial_context or any(
            token in commercial_context
            for token in {
                "expansion",
                "market entry",
                "entity",
                "global mobility",
                "compliance",
                "regional",
                "payroll operations",
                "people operations",
                "hris",
            }
        )

        confidence_score += market_score(target_country)

        if lead_type in {"direct_eor", "direct_payroll", "recruitment_partner"}:
            confidence_score += 3
        elif lead_type == "hris":
            confidence_score += 2

        if (discovery_record.source_trust_score or 0) >= 8:
            confidence_score += 2
        elif (discovery_record.source_trust_score or 0) >= 6:
            confidence_score += 1

        if (discovery_record.source_priority or 0) >= 8:
            confidence_score += 1

        if discovery_record.contact_name:
            confidence_score += 1
        if discovery_record.contact_role:
            confidence_score += 1
        if discovery_record.source_url or discovery_record.website_url:
            confidence_score += 1
        if discovery_record.email or discovery_record.linkedin_url:
            confidence_score += 1
        if discovery_record.service_focus and lead_type:
            if discovery_record.service_focus.strip().lower() in {
                lead_type,
                lead_type.removeprefix("direct_"),
                "partner" if lead_type == "recruitment_partner" else lead_type,
            }:
                confidence_score += 1
        if has_buyer_hypothesis:
            confidence_score += 1
        if has_commercial_trigger:
            confidence_score += 1

        final_score = max(1, min(confidence_score, 10))
        if lead_type == "hris" and final_score >= 5 and has_commercial_trigger:
            decision = "promote"
        elif (
            final_score >= 6
            and lead_type
            and (target_country or lead_type == "hris")
            and has_commercial_trigger
            and has_buyer_hypothesis
        ):
            decision = "promote"
        elif final_score >= 4 and (has_commercial_trigger or has_buyer_hypothesis):
            decision = "review"
        else:
            decision = "reject"

        evidence_summary = self._coalesce(
            discovery_record.evidence,
            discovery_record.notes,
            f"Discovery record captured for {campaign or discovery_record.campaign or 'the active campaign'}.",
        ) or "Discovery record captured without detailed evidence."

        lead = Lead(
            company_name=discovery_record.company_name,
            company_canonical=discovery_record.company_canonical,
            lane_label=discovery_record.lane_label,
            contact_name=self._clean_optional_value(discovery_record.contact_name)
            or "Unknown Contact",
            contact_role=self._clean_optional_value(discovery_record.contact_role)
            or "Unknown Role",
            email=self._clean_optional_value(discovery_record.email),
            linkedin_url=self._clean_optional_value(discovery_record.linkedin_url),
            company_country=self._clean_optional_value(discovery_record.company_country),
            target_country=target_country,
            buyer_confidence=self._normalized_buyer_confidence(
                discovery_record.buyer_confidence,
                discovery_record.contact_name,
                discovery_record.contact_role,
            ),
            account_fit_summary=self._coalesce(
                discovery_record.account_fit_summary,
                discovery_record.notes,
            ),
            lead_type=lead_type,
            fit_reason=evidence_summary,
        )

        return DiscoveryQualification(
            lead=lead,
            evidence_summary=evidence_summary,
            confidence_score=final_score,
            decision=decision,
            qualification_notes=(
                "Deterministic fallback qualification was used. "
                "Promotion requires a plausible buyer hypothesis and commercial trigger."
            ),
        )

    def build_lead_from_intake_fallback(
        self,
        intake_record: LeadIntakeRecord,
        campaign: str | None = None,
    ) -> Lead:
        fit_reason = intake_record.notes
        if not fit_reason:
            campaign_label = campaign or intake_record.campaign or "GCC expansion campaign"
            fit_reason = (
                f"Captured from the real intake workflow for {campaign_label} and "
                "mapped without Anthropic enrichment."
            )

        return Lead(
            company_name=intake_record.company_name,
            company_canonical=intake_record.company_canonical,
            lane_label=intake_record.lane_label,
            contact_name=self._clean_optional_value(intake_record.contact_name)
            or "Unknown Contact",
            contact_role=self._clean_optional_value(intake_record.contact_role)
            or "Unknown Role",
            email=self._clean_optional_value(intake_record.email),
            linkedin_url=self._clean_optional_value(intake_record.linkedin_url),
            company_country=self._clean_optional_value(intake_record.company_country),
            target_country=self._normalize_target_country(intake_record.target_country),
            buyer_confidence=self._normalized_buyer_confidence(
                intake_record.buyer_confidence,
                intake_record.contact_name,
                intake_record.contact_role,
            ),
            account_fit_summary=self._coalesce(
                intake_record.account_fit_summary,
                intake_record.notes,
            ),
            lead_type=self._normalize_lead_type(intake_record.lead_type_hint),
            fit_reason=fit_reason,
        )

    def _build_lead_research_instructions(self) -> str:
        supported_markets = supported_markets_text()
        return (
            "You normalize raw B2B lead intake rows for a sales engine focused on "
            "employment infrastructure and payroll support across the Gulf states, "
            "Egypt, Lebanon, and Jordan. "
            "Return only structured data. Preserve source values when already usable. "
            "Allowed lead_type values are direct_eor, direct_payroll, recruitment_partner, "
            f"and hris. Allowed target_country values are {supported_markets}, or null when unclear. "
            "For HRIS-only opportunities, target_country can also be any other country that is "
            "explicitly supported by the source evidence. "
            "Do not invent companies. Only infer missing "
            "contact or role details when the notes or campaign context strongly support it. "
            "If contact_name is still unclear, use 'Unknown Contact'. If contact_role is still "
            "unclear, use 'Unknown Role'. fit_reason should be one short factual sentence tied "
            "to cross-border hiring, payroll, EOR, recruiter partnership, or HRIS need."
        )

    def _build_discovery_qualification_instructions(self) -> str:
        supported_markets = supported_markets_text()
        return (
            "You evaluate raw discovery evidence for a B2B sales engine selling employment "
            "infrastructure and payroll support across the Gulf states, Egypt, Lebanon, and "
            "Jordan. Use only the provided "
            "evidence. Do not invent companies or contacts. Return structured data that "
            "classifies whether the record should be promoted, reviewed, or rejected. "
            "Allowed decision values are promote, review, and reject. "
            "Allowed lead_type values are direct_eor, direct_payroll, recruitment_partner, "
            f"and hris. Allowed target_country values are {supported_markets}, or null. "
            "For HRIS-only opportunities, target_country can also be any other country that is "
            "explicitly supported by the source evidence. "
            "Use promote only when there is clear evidence of regional hiring, payroll, "
            "employer-of-record need, recruiter partnership, or HR operations need. "
            "Reject generic market-presence or commercial-hiring signals that do not show a "
            "people, payroll, HRIS, recruiter, or expansion-operations need. "
            "Generic sales, account executive, client growth, business development, cloud, "
            "software engineering, and unrelated product roles should not be promoted unless "
            "the evidence also explicitly shows payroll, HR, people operations, recruiter, "
            "mobility, or entity-expansion relevance. "
            "A useful discovery record must describe a plausible account trigger, a likely "
            "buyer or buyer team, and a believable product angle. "
            "If the record does not answer why this company, why now, and who likely owns "
            "the problem, prefer review or reject rather than promote. "
            "confidence_score must be 1-10 and should reflect evidence strength, not optimism. "
            "Source trust and priority should matter. "
            "evidence_summary should be one short factual summary of the source evidence."
        )

    def _build_lead_research_input(
        self,
        intake_record: LeadIntakeRecord,
        campaign: str | None,
    ) -> str:
        intake_campaign = campaign or intake_record.campaign or ""
        lines = [
            f"Campaign: {intake_campaign or 'N/A'}",
            f"Company: {intake_record.company_name}",
            f"Lane Label: {intake_record.lane_label or 'N/A'}",
            f"Contact: {intake_record.contact_name or 'N/A'}",
            f"Role: {intake_record.contact_role or 'N/A'}",
            f"Email: {intake_record.email or 'N/A'}",
            f"LinkedIn URL: {intake_record.linkedin_url or 'N/A'}",
            f"Company Country: {intake_record.company_country or 'N/A'}",
            f"Target Country Hint: {intake_record.target_country or 'N/A'}",
            f"Buyer Confidence: {intake_record.buyer_confidence or 'N/A'}",
            f"Account Fit Summary: {intake_record.account_fit_summary or 'N/A'}",
            f"Lead Type Hint: {intake_record.lead_type_hint or 'N/A'}",
            f"Notes: {intake_record.notes or 'N/A'}",
        ]
        return "\n".join(lines)

    def _build_discovery_qualification_input(
        self,
        discovery_record: LeadDiscoveryRecord,
        campaign: str | None,
    ) -> str:
        discovery_campaign = campaign or discovery_record.campaign or ""
        lines = [
            f"Campaign: {discovery_campaign or 'N/A'}",
            f"Company: {discovery_record.company_name}",
            f"Sourcing Agent: {discovery_record.agent_label or 'N/A'}",
            f"Lane Label: {discovery_record.lane_label or 'N/A'}",
            f"Website URL: {discovery_record.website_url or 'N/A'}",
            f"Source URL: {discovery_record.source_url or 'N/A'}",
            f"Source Type: {discovery_record.source_type or 'N/A'}",
            f"Published At: {discovery_record.published_at or 'N/A'}",
            f"Source Priority: {discovery_record.source_priority or 'N/A'}",
            f"Source Trust Score: {discovery_record.source_trust_score or 'N/A'}",
            f"Service Focus: {discovery_record.service_focus or 'N/A'}",
            f"Evidence: {discovery_record.evidence or 'N/A'}",
            f"Candidate Contact: {discovery_record.contact_name or 'N/A'}",
            f"Candidate Role: {discovery_record.contact_role or 'N/A'}",
            f"Email: {discovery_record.email or 'N/A'}",
            f"LinkedIn URL: {discovery_record.linkedin_url or 'N/A'}",
            f"Company Country: {discovery_record.company_country or 'N/A'}",
            f"Target Country Hint: {discovery_record.target_country_hint or 'N/A'}",
            f"Buyer Confidence: {discovery_record.buyer_confidence or 'N/A'}",
            f"Account Fit Summary: {discovery_record.account_fit_summary or 'N/A'}",
            f"Notes: {discovery_record.notes or 'N/A'}",
            "Qualification standard: only promote when there is a plausible buyer hypothesis, "
            "a commercial trigger, and a product angle that would help an operator sell.",
        ]
        return "\n".join(lines)

    def _coalesce(self, *values: str | None) -> str | None:
        for value in values:
            cleaned = self._clean_optional_value(value)
            if cleaned:
                return cleaned
        return None

    def _clean_optional_value(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.lower() in self.PLACEHOLDER_VALUES:
            return None
        return cleaned

    def _normalize_target_country(self, value: str | None) -> str | None:
        return normalize_target_country(value)

    def _normalize_lead_type(self, value: str | None) -> str | None:
        if not value:
            return None

        normalized = value.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "eor": "direct_eor",
            "direct_eor": "direct_eor",
            "eor_only": "direct_eor",
            "payroll": "direct_payroll",
            "direct_payroll": "direct_payroll",
            "payroll_only": "direct_payroll",
            "recruitment_partner": "recruitment_partner",
            "recruitment_agency": "recruitment_partner",
            "recruitment": "recruitment_partner",
            "partner": "recruitment_partner",
            "hris": "hris",
            "hris_only": "hris",
        }
        return aliases.get(normalized, value.strip())

    def _normalized_buyer_confidence(
        self,
        value: int | None,
        contact_name: str | None,
        contact_role: str | None,
    ) -> int | None:
        if value is not None:
            return max(1, min(int(value), 10))
        has_name = self._clean_optional_value(contact_name) is not None
        has_role = self._clean_optional_value(contact_role) is not None
        if has_name and has_role:
            return 9
        if has_role:
            return 7
        if has_name:
            return 6
        return None

    def _normalize_discovery_decision(self, value: str | None) -> str:
        if not value:
            return "review"

        normalized = value.strip().lower()
        if normalized in {"promote", "approved", "approve", "auto_approve"}:
            return "promote"
        if normalized in {"reject", "rejected", "discard"}:
            return "reject"
        return "review"

    def _infer_lead_type_from_discovery(
        self,
        discovery_record: LeadDiscoveryRecord,
    ) -> str | None:
        normalized_service_focus = (discovery_record.service_focus or "").strip().lower()
        if normalized_service_focus == "payroll":
            return "direct_payroll"
        if normalized_service_focus == "eor":
            return "direct_eor"
        if normalized_service_focus == "partner":
            return "recruitment_partner"
        if normalized_service_focus == "hris":
            return "hris"

        haystack = " ".join(
            value
            for value in [
                discovery_record.source_type,
                discovery_record.evidence,
                discovery_record.notes,
                discovery_record.contact_role,
            ]
            if value
        ).lower()

        if "recruit" in haystack or "staffing" in haystack or "placement" in haystack:
            return "recruitment_partner"
        if "payroll" in haystack:
            return "direct_payroll"
        if "eor" in haystack or "employer of record" in haystack or "entity setup" in haystack:
            return "direct_eor"
        if "hris" in haystack or "people ops" in haystack or "hr operations" in haystack:
            return "hris"
        return None


class _LeadResearchOutput(BaseModel):
    company_name: str = Field(min_length=1)
    contact_name: str = Field(min_length=1)
    contact_role: str = Field(min_length=1)
    email: str | None = None
    linkedin_url: str | None = None
    company_country: str | None = None
    target_country: str | None = None
    lead_type: str | None = None
    fit_reason: str | None = None

    @field_validator(
        "company_name",
        "contact_name",
        "contact_role",
        "email",
        "linkedin_url",
        "company_country",
        "target_country",
        "lead_type",
        "fit_reason",
        mode="before",
    )
    @classmethod
    def _strip_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class _DiscoveryQualificationOutput(BaseModel):
    company_name: str = Field(min_length=1)
    contact_name: str = Field(min_length=1)
    contact_role: str = Field(min_length=1)
    email: str | None = None
    linkedin_url: str | None = None
    company_country: str | None = None
    target_country: str | None = None
    lead_type: str | None = None
    fit_reason: str | None = None
    evidence_summary: str = Field(min_length=1)
    confidence_score: int = Field(ge=1, le=10)
    decision: str = Field(min_length=1)
    qualification_notes: str | None = None

    @field_validator(
        "company_name",
        "contact_name",
        "contact_role",
        "email",
        "linkedin_url",
        "company_country",
        "target_country",
        "lead_type",
        "fit_reason",
        "evidence_summary",
        "decision",
        "qualification_notes",
        mode="before",
    )
    @classmethod
    def _strip_discovery_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
