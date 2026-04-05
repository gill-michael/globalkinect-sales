from dataclasses import dataclass, field

from app.models.lead import Lead
from app.models.lead_feedback_signal import LeadFeedbackSignal
from app.services.notion_service import NotionService
from app.utils.logger import get_logger
from app.utils.target_markets import country_label

logger = get_logger(__name__)


@dataclass
class LeadFeedbackIndex:
    by_reference: dict[str, LeadFeedbackSignal] = field(default_factory=dict)
    by_company: dict[str, LeadFeedbackSignal] = field(default_factory=dict)

    def find(
        self,
        *,
        lead_reference: str | None = None,
        company_name: str | None = None,
    ) -> LeadFeedbackSignal | None:
        normalized_reference = _normalize_lookup_key(lead_reference)
        if normalized_reference and normalized_reference in self.by_reference:
            return self.by_reference[normalized_reference]

        normalized_company = _normalize_lookup_key(company_name)
        if normalized_company and normalized_company in self.by_company:
            return self.by_company[normalized_company]

        return None

    def count(self) -> int:
        return len({id(signal) for signal in [*self.by_reference.values(), *self.by_company.values()]})


class LeadFeedbackAgent:
    def __init__(self, notion_service: NotionService | None = None) -> None:
        self.notion_service = notion_service or NotionService()

    def is_configured(self) -> bool:
        return self.notion_service.is_configured()

    def collect_feedback_index(self, limit: int = 200) -> LeadFeedbackIndex:
        index = LeadFeedbackIndex()
        if not self.notion_service.is_configured():
            return index

        signals: list[LeadFeedbackSignal] = []
        if self.notion_service.is_outreach_queue_configured():
            signals.extend(self.notion_service.fetch_outreach_queue_feedback_signals(limit=limit))
        signals.extend(self.notion_service.fetch_pipeline_feedback_signals(limit=limit))

        for signal in signals:
            self._store_signal(index, signal)

        logger.info("Collected %s lead feedback signals.", index.count())
        return index

    def signal_for_lead(
        self,
        feedback_index: LeadFeedbackIndex,
        lead: Lead,
    ) -> LeadFeedbackSignal | None:
        return feedback_index.find(
            lead_reference=self.build_lead_reference(lead),
            company_name=lead.company_name,
        )

    def signal_for_reference(
        self,
        feedback_index: LeadFeedbackIndex,
        lead_reference: str | None,
        company_name: str | None,
    ) -> LeadFeedbackSignal | None:
        return feedback_index.find(
            lead_reference=lead_reference,
            company_name=company_name,
        )

    def _store_signal(
        self,
        index: LeadFeedbackIndex,
        signal: LeadFeedbackSignal,
    ) -> None:
        normalized_reference = _normalize_lookup_key(signal.lead_reference)
        existing = None
        if normalized_reference:
            existing = index.by_reference.get(normalized_reference)

        normalized_company = _normalize_lookup_key(signal.company_name)
        if existing is None and normalized_company:
            existing = index.by_company.get(normalized_company)

        merged = self._merge_signals(existing, signal)
        if normalized_reference:
            index.by_reference[normalized_reference] = merged
        if normalized_company:
            index.by_company[normalized_company] = merged

    def _merge_signals(
        self,
        existing: LeadFeedbackSignal | None,
        incoming: LeadFeedbackSignal,
    ) -> LeadFeedbackSignal:
        if existing is None:
            return incoming

        return LeadFeedbackSignal(
            lead_reference=existing.lead_reference or incoming.lead_reference,
            company_name=existing.company_name or incoming.company_name,
            queue_status=existing.queue_status or incoming.queue_status,
            pipeline_stage=existing.pipeline_stage or incoming.pipeline_stage,
            outreach_status=existing.outreach_status or incoming.outreach_status,
        )

    def build_lead_reference(self, lead: Lead) -> str:
        return "|".join(
            [
                lead.company_name,
                lead.contact_name,
                country_label(lead.target_country),
                lead.lead_type or "unknown",
            ]
        )


def _normalize_lookup_key(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().lower()
