def normalize_company_canonical(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().lower().split())
    return normalized or None


def company_name_from_lead_reference(lead_reference: str | None) -> str | None:
    if not lead_reference:
        return None
    company_name, _, _ = lead_reference.partition("|")
    company_name = company_name.strip()
    return company_name or None


def contact_name_from_lead_reference(lead_reference: str | None) -> str | None:
    if not lead_reference:
        return None
    parts = [part.strip() for part in lead_reference.split("|")]
    if len(parts) < 2:
        return None
    return parts[1] or None
