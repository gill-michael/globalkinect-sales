from app.models.account import Account
from app.models.buyer import Buyer
from app.models.lead import Lead
from app.utils.identity import normalize_company_canonical
from app.utils.logger import get_logger

logger = get_logger(__name__)

_PLACEHOLDERS = {
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


class EntityMapperAgent:
    def build_accounts(self, leads: list[Lead]) -> list[Account]:
        accounts_by_canonical: dict[str, Account] = {}
        for lead in leads:
            account_canonical = normalize_company_canonical(
                lead.company_canonical or lead.company_name
            )
            if not account_canonical:
                continue

            existing = accounts_by_canonical.get(account_canonical)
            lane_labels = self._merge_values(
                existing.lane_labels if existing else None,
                [lead.lane_label] if lead.lane_label else None,
            )
            notes = self._merge_notes(
                existing.notes if existing else None,
                "Derived from active sales-engine lead output.",
            )
            account_fit_summary = (
                existing.account_fit_summary if existing else None
            ) or lead.account_fit_summary
            primary_target_country = (
                existing.primary_target_country if existing else None
            ) or lead.target_country

            accounts_by_canonical[account_canonical] = Account(
                account_name=(existing.account_name if existing else None)
                or lead.company_name,
                account_canonical=account_canonical,
                primary_target_country=primary_target_country,
                lane_labels=lane_labels,
                account_fit_summary=account_fit_summary,
                notes=notes,
            )

        logger.info("Mapped %s accounts from %s leads.", len(accounts_by_canonical), len(leads))
        return list(accounts_by_canonical.values())

    def build_buyers(self, leads: list[Lead]) -> list[Buyer]:
        buyers_by_key: dict[str, Buyer] = {}
        for lead in leads:
            if not self._has_known_value(lead.contact_name):
                continue

            account_canonical = normalize_company_canonical(
                lead.company_canonical or lead.company_name
            )
            if not account_canonical:
                continue

            buyer_name = lead.contact_name.strip()
            buyer_key = f"{buyer_name} | {lead.company_name}"
            buyer_canonical = normalize_company_canonical(buyer_name)
            if not buyer_canonical:
                continue

            existing = buyers_by_key.get(buyer_key)
            lane_labels = self._merge_values(
                existing.lane_labels if existing else None,
                [lead.lane_label] if lead.lane_label else None,
            )
            notes = self._merge_notes(
                existing.notes if existing else None,
                "Derived from active sales-engine lead output.",
            )
            existing_confidence = existing.buyer_confidence if existing else None

            buyers_by_key[buyer_key] = Buyer(
                buyer_key=buyer_key,
                buyer_name=buyer_name,
                buyer_canonical=buyer_canonical,
                account_name=lead.company_name,
                account_canonical=account_canonical,
                contact_role=(
                    existing.contact_role if existing and self._has_known_value(existing.contact_role) else None
                ) or (lead.contact_role if self._has_known_value(lead.contact_role) else None),
                email=(existing.email if existing else None) or lead.email,
                linkedin_url=(existing.linkedin_url if existing else None) or lead.linkedin_url,
                target_country=(existing.target_country if existing else None) or lead.target_country,
                buyer_confidence=max(existing_confidence or 0, lead.buyer_confidence or 0)
                or None,
                lane_labels=lane_labels,
                notes=notes,
            )

        logger.info("Mapped %s buyers from %s leads.", len(buyers_by_key), len(leads))
        return list(buyers_by_key.values())

    def _has_known_value(self, value: str | None) -> bool:
        cleaned = (value or "").strip().lower()
        return bool(cleaned) and cleaned not in _PLACEHOLDERS

    def _merge_values(
        self,
        existing: list[str] | None,
        incoming: list[str] | None,
    ) -> list[str] | None:
        merged = []
        seen: set[str] = set()
        for value in (existing or []) + (incoming or []):
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)
        return merged or None

    def _merge_notes(self, existing: str | None, incoming: str | None) -> str | None:
        notes = []
        for note in [existing, incoming]:
            if not note or note in notes:
                continue
            notes.append(note)
        return "\n".join(notes) if notes else None
