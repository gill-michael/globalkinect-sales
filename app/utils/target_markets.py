from __future__ import annotations

PRIMARY_TARGET_MARKETS = (
    "United Arab Emirates",
    "Saudi Arabia",
    "Egypt",
)

SECONDARY_TARGET_MARKETS = (
    "Qatar",
    "Kuwait",
    "Bahrain",
    "Oman",
    "Lebanon",
    "Jordan",
)

SUPPORTED_TARGET_MARKETS = PRIMARY_TARGET_MARKETS + SECONDARY_TARGET_MARKETS

TARGET_MARKET_ALIASES = {
    "uae": "United Arab Emirates",
    "u.a.e.": "United Arab Emirates",
    "the uae": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "dubai": "United Arab Emirates",
    "abu dhabi": "United Arab Emirates",
    "sharjah": "United Arab Emirates",
    "saudi arabia": "Saudi Arabia",
    "ksa": "Saudi Arabia",
    "kingdom of saudi arabia": "Saudi Arabia",
    "riyadh": "Saudi Arabia",
    "jeddah": "Saudi Arabia",
    "dammam": "Saudi Arabia",
    "egypt": "Egypt",
    "cairo": "Egypt",
    "alexandria": "Egypt",
    "giza": "Egypt",
    "qatar": "Qatar",
    "doha": "Qatar",
    "kuwait": "Kuwait",
    "kuwait city": "Kuwait",
    "bahrain": "Bahrain",
    "manama": "Bahrain",
    "oman": "Oman",
    "muscat": "Oman",
    "lebanon": "Lebanon",
    "beirut": "Lebanon",
    "jordan": "Jordan",
    "amman": "Jordan",
}


def normalize_target_country(value: str | None) -> str | None:
    if not value:
        return None

    normalized = value.strip().lower()
    canonical = TARGET_MARKET_ALIASES.get(normalized)
    if canonical:
        return canonical
    return value.strip()


def is_supported_market(value: str | None) -> bool:
    normalized = normalize_target_country(value)
    return normalized in SUPPORTED_TARGET_MARKETS


def is_primary_market(value: str | None) -> bool:
    normalized = normalize_target_country(value)
    return normalized in PRIMARY_TARGET_MARKETS


def market_score(value: str | None) -> int:
    normalized = normalize_target_country(value)
    if normalized in PRIMARY_TARGET_MARKETS:
        return 3
    if normalized in SECONDARY_TARGET_MARKETS:
        return 2
    return 0


def country_label(value: str | None) -> str:
    normalized = normalize_target_country(value)
    labels = {
        "United Arab Emirates": "the UAE",
    }
    return labels.get(normalized or "", normalized or "the target market")


def country_subject_label(value: str | None) -> str:
    normalized = normalize_target_country(value)
    labels = {
        "United Arab Emirates": "UAE",
    }
    return labels.get(normalized or "", normalized or "target market")


def supported_markets_text() -> str:
    return ", ".join(SUPPORTED_TARGET_MARKETS)
