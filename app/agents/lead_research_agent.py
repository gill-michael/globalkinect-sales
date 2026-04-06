from typing import List

from app.models.lead import Lead
from app.models.lead_intake_record import LeadIntakeRecord
from app.services.notion_service import NotionService
from app.services.anthropic_service import AnthropicService
from app.utils.logger import get_logger

logger = get_logger(__name__)


class LeadResearchAgent:
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

    def __init__(
        self,
        notion_service: NotionService | None = None,
        anthropic_service: AnthropicService | None = None,
    ) -> None:
        self.notion_service = notion_service or NotionService()
        self.anthropic_service = anthropic_service or AnthropicService()

    def is_real_intake_configured(self) -> bool:
        return self.notion_service.is_intake_configured()

    def collect_leads(
        self,
        campaign: str,
        max_records: int = 10,
        allow_mock_fallback: bool = True,
        mark_processed: bool = True,
    ) -> List[Lead]:
        if not self.notion_service.is_intake_configured():
            if allow_mock_fallback:
                logger.info(
                    "Notion intake database is not configured. Falling back to mock leads."
                )
                return self.generate_mock_leads(campaign)

            logger.info(
                "Notion intake database is not configured. No real leads collected."
            )
            return []

        intake_records = self.notion_service.fetch_lead_intake_records(limit=max_records)
        if not mark_processed:
            intake_records = [
                record for record in intake_records if not self._is_shadow_replay(record)
            ]
        if not intake_records:
            logger.info("No ready lead intake records found in Notion.")
            return []

        leads: List[Lead] = []
        for intake_record in intake_records:
            try:
                lead = self._normalize_intake_record(intake_record, campaign)
                leads.append(lead)
                if mark_processed:
                    self._mark_processed(intake_record, lead)
            except Exception as exc:
                logger.exception(
                    "Lead intake normalization failed for page %s.",
                    intake_record.page_id,
                )
                if mark_processed:
                    self._mark_failed(intake_record, str(exc))

        logger.info(f"Collected {len(leads)} real leads from Notion intake.")
        return leads

    def _is_shadow_replay(self, intake_record: LeadIntakeRecord) -> bool:
        has_reference = self._has_known_value(intake_record.lead_reference)
        has_processed_at = self._has_known_value(intake_record.processed_at)
        if not (has_reference or has_processed_at):
            return False

        logger.info(
            "Skipping intake page %s during shadow mode because it already has prior processing markers.",
            intake_record.page_id,
        )
        return True

    def _has_known_value(self, value: str | None) -> bool:
        cleaned = (value or "").strip().lower()
        return bool(cleaned) and cleaned not in self.PLACEHOLDER_VALUES

    def generate_mock_leads(self, campaign: str) -> List[Lead]:
        logger.info(f"Generating mock leads for campaign: {campaign}")

        mock_data = [
            {
                "company_name": "Desert Peak Technologies",
                "contact_name": "Amira Hassan",
                "contact_role": "Head of People",
                "email": "amira@desertpeaktech.com",
                "linkedin_url": "https://linkedin.com/in/amira-hassan",
                "company_country": "United Kingdom",
                "target_country": "United Arab Emirates",
                "lead_type": "direct_eor",
                "fit_reason": "UK company likely expanding into UAE and may need payroll/EOR support.",
            },
            {
                "company_name": "ScaleBridge Health",
                "contact_name": "Daniel Morris",
                "contact_role": "Founder",
                "email": "daniel@scalebridgehealth.com",
                "linkedin_url": "https://linkedin.com/in/daniel-morris",
                "company_country": "Germany",
                "target_country": "Saudi Arabia",
                "lead_type": "direct_payroll",
                "fit_reason": "European company expanding into Saudi Arabia with likely compliance and payroll needs.",
            },
            {
                "company_name": "Nile Talent Partners",
                "contact_name": "Layla Fawzi",
                "contact_role": "Managing Director",
                "email": "layla@niletalentpartners.com",
                "linkedin_url": "https://linkedin.com/in/layla-fawzi",
                "company_country": "Egypt",
                "target_country": "United Arab Emirates",
                "lead_type": "recruitment_partner",
                "fit_reason": "Recruitment agency placing talent into the UAE and may need an employer/payroll partner.",
            },
        ]

        leads = [Lead(**item) for item in mock_data]
        logger.info(f"Generated {len(leads)} leads.")
        return leads

    def _normalize_intake_record(
        self,
        intake_record: LeadIntakeRecord,
        campaign: str,
    ) -> Lead:
        if self.anthropic_service.is_configured():
            try:
                return self.anthropic_service.normalize_lead_from_intake(
                    intake_record,
                    campaign=campaign,
                )
            except Exception:
                logger.warning(
                    "Anthropic normalization failed for intake page %s. Falling back to direct mapping.",
                    intake_record.page_id,
                )

        return self.anthropic_service.build_lead_from_intake_fallback(
            intake_record,
            campaign=campaign,
        )

    def _mark_processed(self, intake_record: LeadIntakeRecord, lead: Lead) -> None:
        try:
            self.notion_service.mark_lead_intake_record_processed(intake_record, lead)
        except Exception:
            logger.warning(
                "Failed to update intake page %s after processing.",
                intake_record.page_id,
            )

    def _mark_failed(self, intake_record: LeadIntakeRecord, error_message: str) -> None:
        try:
            self.notion_service.mark_lead_intake_record_failed(
                intake_record,
                error_message,
            )
        except Exception:
            logger.warning(
                "Failed to update intake page %s after error.",
                intake_record.page_id,
            )
