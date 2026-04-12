"""
Explorium prospecting scan — populates the Notion Lead Intake database with
prospects pulled from the Explorium API so that the daily sourcing engine
picks them up on its next run.

Usage:
    python scripts/vibe_prospecting_scan.py --region gcc --icp A1 --limit 1000

API contract reconciled against https://developers.explorium.ai/ (April 2026):
- Base URL:       https://api.explorium.ai/v1
- Auth header:    api_key: <key>   (raw, not Bearer)
- Prospects:      POST /v1/prospects   (response body -> `data` array)
- Businesses:     POST /v1/businesses  (response body -> `data` array)
- Events + number_of_locations filters only exist on /businesses, so ICPs
  that use them (A3, B3) and ICPs with location bucketing (A1/A2/B1/B2/B4)
  require a two-step flow: /businesses -> business_ids -> /prospects.

Known limitations surfaced by the live API:
- Email is returned as `professional_email_hashed` (a hash, not a plaintext
  address). We write it into Notes; the Notion `Email` property is left
  blank unless a plaintext email surfaces in the response. Dedupe against
  existing Lead Intake rows therefore falls back to company_name|full_name
  when no plaintext email is present.
- Job department enum values for "c-suite" and "administration" aren't
  documented. `c-suite` is mapped via `job_level` rather than
  `job_department`; `administration` is dropped with a log note. See
  JOB_DEPARTMENT_MAP / JOB_LEVEL_MAP below to override once confirmed.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.config import settings  # noqa: E402
from app.services.notion_service import NotionService  # noqa: E402
from app.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)


REGION_COUNTRIES: dict[str, list[str]] = {
    "gcc": ["ae", "sa", "qa", "kw", "bh", "om"],
    "mena": ["ae", "sa", "qa", "kw", "bh", "om", "eg", "ma", "dz", "jo", "lb"],
    "apac": ["in", "sg", "my", "th", "id", "ph", "vn", "hk", "au", "nz"],
    "uk": ["gb"],
    "europe": ["de", "nl", "fr", "ie", "se", "dk", "no", "fi", "es", "it"],
}

# Explorium uses bucket strings for company_size / number_of_locations,
# lowercase ISO alpha-2 for country_code, and lowercase strings for
# job_department. See the businesses filter docs for the full enums.
COMPANY_SIZE_BUCKETS = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1001-5000", "5001-10000", "10001+"]
LOCATION_BUCKETS = ["1", "2-5", "6-20", "21-50", "51-100", "101-1000", "1001+"]


def company_size_range(low: int, high: int) -> list[str]:
    buckets = {
        "1-10": (1, 10),
        "11-50": (11, 50),
        "51-200": (51, 200),
        "201-500": (201, 500),
        "501-1000": (501, 1000),
        "1001-5000": (1001, 5000),
        "5001-10000": (5001, 10000),
        "10001+": (10001, 10_000_000),
    }
    return [name for name, (lo, hi) in buckets.items() if hi >= low and lo <= high]


def locations_range(low: int, high: int) -> list[str]:
    buckets = {
        "1": (1, 1),
        "2-5": (2, 5),
        "6-20": (6, 20),
        "21-50": (21, 50),
        "51-100": (51, 100),
        "101-1000": (101, 1000),
        "1001+": (1001, 10_000),
    }
    return [name for name, (lo, hi) in buckets.items() if hi >= low and lo <= high]


# Explorium `job_department` values seen in docs: "engineering", "sales",
# "human resources". Other values inferred from the hiring event enum
# (hiring_in_<dept>_department). TODO (API ENUM): confirm "c suite" /
# "administration" equivalents; current mapping uses job_level for c-suite.
JOB_DEPARTMENT_MAP: dict[str, str] = {
    "HR": "human resources",
    "finance": "finance",
    "administration": "operations",  # best guess — confirm against enum
}
JOB_LEVEL_MAP: dict[str, str] = {
    "c-suite": "c-suite",  # confirmed against Explorium /prospects docs
}


ICP_FILTERS: dict[str, dict[str, Any]] = {
    "A1": {
        "company_size": company_size_range(51, 500),
        "departments": ["HR", "finance"],
        "levels": ["c-suite"],
        "number_of_locations": locations_range(2, 20),
    },
    "A2": {
        "company_size": company_size_range(11, 200),
        "departments": ["HR", "administration"],
        "levels": ["c-suite"],
        "number_of_locations": locations_range(0, 1),
    },
    "A3": {
        "company_size": company_size_range(201, 1000),
        "events": ["new_funding_round", "new_office", "increase_in_all_departments"],
        "events_last_occurrence": 90,
    },
    "B1": {
        "company_size": company_size_range(201, 5000),
        "departments": ["HR", "finance"],
        "number_of_locations": locations_range(6, 50),
    },
    "B2": {
        "company_size": company_size_range(11, 200),
        "departments": ["HR"],
        "levels": ["c-suite"],
        "number_of_locations": locations_range(0, 1),
    },
    "B3": {
        "company_size": company_size_range(51, 500),
        "events": ["new_office", "new_partnership"],
        "events_last_occurrence": 90,
    },
    "B4": {
        "company_size": company_size_range(201, 1000),
        "departments": ["HR", "finance"],
        "levels": ["c-suite"],
        "number_of_locations": locations_range(2, 20),
    },
}

ICP_LEAD_TYPE_HINT: dict[str, str] = {
    "A1": "direct_payroll",
    "A2": "direct_payroll",
    "A3": "direct_payroll",
    "B1": "hris",
    "B2": "hris",
    "B3": "direct_eor",
    "B4": "direct_eor",
}

COUNTRY_CODE_TO_NAME: dict[str, str] = {
    "ae": "United Arab Emirates",
    "sa": "Saudi Arabia",
    "qa": "Qatar",
    "kw": "Kuwait",
    "bh": "Bahrain",
    "om": "Oman",
    "eg": "Egypt",
    "ma": "Morocco",
    "dz": "Algeria",
    "jo": "Jordan",
    "lb": "Lebanon",
    "gb": "United Kingdom",
    "de": "Germany",
    "nl": "Netherlands",
    "fr": "France",
    "ie": "Ireland",
    "se": "Sweden",
    "dk": "Denmark",
    "no": "Norway",
    "fi": "Finland",
    "es": "Spain",
    "it": "Italy",
}


EXPLORIUM_BASE_URL_DEFAULT = "https://api.explorium.ai/v1"
BUSINESSES_PATH = "/businesses"
PROSPECTS_PATH = "/prospects"
MAX_PAGE_SIZE = 100   # docs allow up to 500 but recommend 100 for stability
MAX_BUSINESS_IDS = 2000  # cap on how many business_ids we forward to /prospects


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="explorium-prospecting-scan",
        description="Scan the Explorium prospects API and populate Notion Lead Intake.",
    )
    parser.add_argument("--region", required=True, choices=sorted(REGION_COUNTRIES))
    parser.add_argument("--icp", required=True, choices=sorted(ICP_FILTERS))
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def translate_departments(labels: list[str]) -> list[str]:
    out: list[str] = []
    for label in labels:
        if label in JOB_DEPARTMENT_MAP:
            out.append(JOB_DEPARTMENT_MAP[label])
        else:
            logger.warning("Unmapped job_department label %r — dropping.", label)
    return out


def translate_levels(labels: list[str]) -> list[str]:
    return [JOB_LEVEL_MAP[label] for label in labels if label in JOB_LEVEL_MAP]


def build_business_filters(icp: str, country_codes: list[str]) -> dict[str, Any] | None:
    """Filters for the /businesses pre-query.

    Returns None when the ICP has no business-level filters (locations or
    events), in which case we can skip the two-step flow.

    Every Explorium list filter wraps its payload in {"values": [...]}.
    """
    spec = ICP_FILTERS[icp]
    needs_business_step = ("number_of_locations" in spec) or ("events" in spec)
    if not needs_business_step:
        return None

    filters: dict[str, Any] = {
        "company_size": {"values": spec["company_size"]},
        "country_code": {"values": country_codes},
    }
    if "number_of_locations" in spec:
        filters["number_of_locations"] = {"values": spec["number_of_locations"]}
    if "events" in spec:
        filters["events"] = {
            "values": spec["events"],
            "last_occurrence": spec.get("events_last_occurrence", 90),
        }
    return filters


def build_prospect_filters(
    icp: str,
    country_codes: list[str],
    business_ids: list[str] | None,
) -> dict[str, Any]:
    spec = ICP_FILTERS[icp]
    filters: dict[str, Any] = {
        "country_code": {"values": country_codes},
    }
    if business_ids:
        filters["business_id"] = {"values": business_ids}
    else:
        filters["company_size"] = {"values": spec["company_size"]}

    departments = translate_departments(spec.get("departments", []))
    if departments:
        filters["job_department"] = {"values": departments}
    levels = translate_levels(spec.get("levels", []))
    if levels:
        filters["job_level"] = {"values": levels}

    return filters


def explorium_post(
    client: httpx.Client,
    api_key: str,
    base_url: str,
    path: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    print(f"DEBUG POST {path} request body:")
    print(json.dumps(body, indent=2))
    response = client.post(
        f"{base_url.rstrip('/')}{path}",
        headers={
            "api_key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        json=body,
        timeout=60.0,
    )
    if response.status_code >= 400:
        print(f"DEBUG response status: {response.status_code}")
        print(f"DEBUG response body: {response.text[:1500]}")
    response.raise_for_status()
    return response.json()


def fetch_business_ids(
    client: httpx.Client,
    api_key: str,
    base_url: str,
    filters: dict[str, Any],
    max_ids: int = MAX_BUSINESS_IDS,
) -> list[str]:
    collected: list[str] = []
    page = 1
    while len(collected) < max_ids:
        body = {
            "mode": "preview",
            "page": page,
            "page_size": MAX_PAGE_SIZE,
            "filters": filters,
        }
        payload = explorium_post(client, api_key, base_url, BUSINESSES_PATH, body)
        data = payload.get("data") or []
        if not data:
            break
        for row in data:
            business_id = row.get("business_id")
            if business_id:
                collected.append(business_id)
                if len(collected) >= max_ids:
                    break
        total_pages = payload.get("total_pages") or 0
        if page >= total_pages:
            break
        page += 1
    logger.info("Fetched %s matching business_ids.", len(collected))
    return collected


def fetch_prospects(
    client: httpx.Client,
    api_key: str,
    base_url: str,
    filters: dict[str, Any],
    limit: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    meta: dict[str, Any] = {}
    page = 1
    while len(results) < limit:
        page_size = min(MAX_PAGE_SIZE, limit - len(results))
        body = {
            "mode": "full",
            "page": page,
            "page_size": page_size,
            "filters": filters,
        }
        payload = explorium_post(client, api_key, base_url, PROSPECTS_PATH, body)
        data = payload.get("data") or []
        if not data:
            meta = {k: payload.get(k) for k in ("total_results", "total_pages") if payload.get(k) is not None}
            break
        results.extend(data)
        meta = {k: payload.get(k) for k in ("total_results", "total_pages") if payload.get(k) is not None}
        total_pages = payload.get("total_pages") or 0
        if page >= total_pages:
            break
        page += 1
    return results[:limit], meta


def first(*values: Any) -> Any:
    for v in values:
        if v not in (None, "", [], {}):
            return v
    return None


def first_linkedin(record: dict[str, Any]) -> str | None:
    raw = record.get("linkedin_url_array") or record.get("linkedin_url")
    if isinstance(raw, list):
        return raw[0] if raw else None
    if isinstance(raw, str):
        return raw
    return None


def normalise_result(record: dict[str, Any]) -> dict[str, Any]:
    full_name = record.get("full_name")
    if not full_name:
        parts = [record.get("first_name"), record.get("last_name")]
        full_name = " ".join(p for p in parts if p).strip() or None

    return {
        "prospect_id": record.get("prospect_id"),
        "company_name": record.get("company_name"),
        "contact_name": full_name,
        "role": first(record.get("job_title"), record.get("job_department_main")),
        "email_plain": first(record.get("email"), record.get("work_email"), record.get("professional_email")),
        "email_hashed": record.get("professional_email_hashed"),
        "linkedin_url": first_linkedin(record),
        "company_country": first(record.get("country_name"), record.get("company_country_name")),
        "company_country_code": record.get("company_country_code"),
        "raw": record,
    }


def target_country_for(region: str, normalised: dict[str, Any]) -> str | None:
    if region == "uk":
        return "United Kingdom"
    name = normalised.get("company_country")
    if name:
        return name
    code = (normalised.get("company_country_code") or "").lower()
    if code:
        return COUNTRY_CODE_TO_NAME.get(code)
    return None


def compose_notes(normalised: dict[str, Any]) -> str:
    reserved = {
        "first_name", "last_name", "full_name",
        "job_title", "job_department_main", "job_level_main",
        "email", "work_email", "professional_email",
        "linkedin_url", "linkedin_url_array",
        "company_name", "country_name", "company_country_code", "company_country_name",
        "prospect_id",
    }
    raw = normalised.get("raw") or {}
    lines: list[str] = []
    if normalised.get("prospect_id"):
        lines.append(f"prospect_id: {normalised['prospect_id']}")
    if normalised.get("email_hashed") and not normalised.get("email_plain"):
        lines.append(f"professional_email_hashed: {normalised['email_hashed']}")
    for key, value in raw.items():
        if key in reserved or value in (None, "", [], {}):
            continue
        if isinstance(value, (dict, list)):
            continue
        lines.append(f"{key}: {value}")
    return "\n".join(lines)


def load_existing_intake_keys(notion_service: NotionService) -> tuple[set[str], set[str]]:
    """Return (emails, name_company_keys) already present in Lead Intake."""
    try:
        records = notion_service.list_lead_intake_records(limit=500)
    except Exception as exc:
        logger.warning("Could not preload intake records for dedupe: %s", exc)
        return set(), set()
    emails: set[str] = set()
    pairs: set[str] = set()
    for record in records:
        if record.email:
            emails.add(record.email.strip().lower())
        if record.company_name and record.contact_name:
            pairs.add(
                f"{record.company_name.strip().lower()}|{record.contact_name.strip().lower()}"
            )
    return emails, pairs


def write_intake_page(
    notion_service: NotionService,
    normalised: dict[str, Any],
    *,
    icp: str,
    target_country: str | None,
    campaign: str,
) -> None:
    database_id = notion_service.intake_database_id
    property_types = notion_service._get_database_property_types(database_id)
    lead_type_hint = ICP_LEAD_TYPE_HINT[icp]

    properties: dict[str, Any] = {
        "Company": notion_service._title(normalised["company_name"] or "Unknown Company"),
    }

    def add_text(name: str, value: str | None) -> None:
        if value is None:
            return
        prop = notion_service._text_property(property_types.get(name), value)
        if prop is not None:
            properties[name] = prop

    def add_email(name: str, value: str | None) -> None:
        if value is None:
            return
        prop = notion_service._email_property(property_types.get(name), value)
        if prop is not None:
            properties[name] = prop

    def add_url(name: str, value: str | None) -> None:
        if value is None:
            return
        prop = notion_service._url_property(property_types.get(name), value)
        if prop is not None:
            properties[name] = prop

    def add_select(name: str, value: str | None) -> None:
        if value is None:
            return
        prop = notion_service._database_choice_or_text_property(database_id, name, value)
        if prop is not None:
            properties[name] = prop

    add_text("Contact", normalised.get("contact_name"))
    add_text("Role", normalised.get("role"))
    add_email("Email", normalised.get("email_plain"))
    add_url("LinkedIn URL", normalised.get("linkedin_url"))
    add_text("Company Country", normalised.get("company_country"))
    add_select("Target Country", target_country)
    add_select("Lane Label", "Direct Outbound Signals")
    add_select("Lead Type Hint", lead_type_hint)

    status_prop = notion_service._database_option_property(database_id, "Status", "ready")
    if status_prop is not None:
        properties["Status"] = status_prop

    add_text("Campaign", campaign)
    add_text("Notes", compose_notes(normalised))

    notion_service._create_page(database_id, properties)


def run_scan(args: argparse.Namespace) -> int:
    api_key = (settings.VIBE_PROSPECTING_API_KEY or "").strip()
    base_url = (settings.VIBE_PROSPECTING_API_BASE_URL or EXPLORIUM_BASE_URL_DEFAULT).strip()
    if not api_key:
        print(
            "VIBE_PROSPECTING_API_KEY is not set. Configure it in .env before running."
        )
        return 1

    notion_service: NotionService | None = None
    if not args.dry_run:
        notion_service = NotionService()
        if not notion_service.is_intake_configured():
            print(
                "Notion Lead Intake is not configured. "
                "Set NOTION_API_KEY and NOTION_INTAKE_DATABASE_ID in .env."
            )
            return 1

    country_codes = REGION_COUNTRIES[args.region]
    campaign = f"Vibe Scan {args.region} {args.icp} {date.today().isoformat()}"
    logger.info(
        "Starting Explorium scan region=%s icp=%s limit=%s dry_run=%s",
        args.region, args.icp, args.limit, args.dry_run,
    )

    with httpx.Client() as client:
        business_filters = build_business_filters(args.icp, country_codes)
        business_ids: list[str] | None = None
        if business_filters is not None:
            logger.info("Two-step flow: querying /businesses first for %s.", args.icp)
            business_ids = fetch_business_ids(
                client,
                api_key=api_key,
                base_url=base_url,
                filters=business_filters,
                max_ids=MAX_BUSINESS_IDS,
            )
            if not business_ids:
                print("No matching businesses — nothing to scan.")
                return 0

        prospect_filters = build_prospect_filters(args.icp, country_codes, business_ids)
        results, meta = fetch_prospects(
            client,
            api_key=api_key,
            base_url=base_url,
            filters=prospect_filters,
            limit=args.limit,
        )

    logger.info("Explorium returned %s prospect results", len(results))

    existing_emails: set[str] = set()
    existing_pairs: set[str] = set()
    if not args.dry_run and notion_service is not None:
        existing_emails, existing_pairs = load_existing_intake_keys(notion_service)

    written = 0
    skipped_empty = 0
    skipped_duplicate = 0

    for record in results:
        normalised = normalise_result(record)
        if not (normalised.get("company_name") or normalised.get("contact_name")):
            skipped_empty += 1
            continue

        email_key = (normalised.get("email_plain") or "").strip().lower()
        pair_key = ""
        if normalised.get("company_name") and normalised.get("contact_name"):
            pair_key = (
                f"{normalised['company_name'].strip().lower()}|"
                f"{normalised['contact_name'].strip().lower()}"
            )
        if email_key and email_key in existing_emails:
            skipped_duplicate += 1
            continue
        if pair_key and pair_key in existing_pairs:
            skipped_duplicate += 1
            continue

        target_country = target_country_for(args.region, normalised)

        if args.dry_run:
            print(
                f"[dry-run] {normalised.get('company_name')} | "
                f"{normalised.get('contact_name')} | {normalised.get('role')} | "
                f"email_plain={normalised.get('email_plain') or '(none)'} | "
                f"linkedin={normalised.get('linkedin_url') or '(none)'} | "
                f"target={target_country}"
            )
            written += 1
            continue

        try:
            write_intake_page(
                notion_service,
                normalised,
                icp=args.icp,
                target_country=target_country,
                campaign=campaign,
            )
            written += 1
            if email_key:
                existing_emails.add(email_key)
            if pair_key:
                existing_pairs.add(pair_key)
        except Exception as exc:
            logger.warning(
                "Failed to write intake page for %s: %s",
                normalised.get("company_name"),
                exc,
            )

    print()
    print("Explorium prospecting scan summary")
    print(f"  Region:             {args.region}")
    print(f"  ICP:                {args.icp}")
    print(f"  Business pre-query: {'yes' if business_filters is not None else 'no'}")
    if business_ids is not None:
        print(f"  Matching businesses: {len(business_ids)}")
    print(f"  Total prospects:    {len(results)}")
    print(f"  Written to Notion:  {written}{' (dry-run)' if args.dry_run else ''}")
    print(f"  Skipped (empty):    {skipped_empty}")
    print(f"  Skipped (dupe):     {skipped_duplicate}")
    for key, value in meta.items():
        print(f"  {key}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(run_scan(parse_args()))
