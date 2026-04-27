"""Explorium plaintext-contact + profile probe.

Diagnostic tool to confirm whether Michael's Explorium account returns
plaintext emails, mobile numbers, and richer LinkedIn-derived profile
data via the enrichment endpoints. Use this once, manually, BEFORE
wiring enrichment into vibe_prospecting_scan.py for the monthly scan.

What it does:
1. Fetches 3 prospects via POST /v1/prospects (the same flow as the
   monthly scan, capped at limit=3).
2. Calls POST /v1/prospects/contacts_information/bulk_enrich with the
   3 prospect_ids — both email AND phone (5 credits per prospect →
   15 credits total per run).
3. Calls POST /v1/prospects/profiles/enrich for the first prospect
   only — to gauge richer LinkedIn-profile data and surface its
   per-call cost (currently undocumented). Cost: 1 × profile credit.
4. Prints all responses with PII redacted (full names, full domains,
   full LinkedIn URLs are obscured) so the output can be safely shared.
5. Prints a side-by-side summary of which fields contain email- and
   phone-shaped values.

Total cost per invocation: ~15 contact credits + ~1 profile credit.
The script does NOT write to Notion, Supabase, or anywhere else. Pure
read.

Usage:
    python scripts/explorium_email_probe.py --region gcc --icp A1

DO NOT add this to the monthly runner. DO NOT schedule it. Run by hand
with Michael's explicit go-ahead.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.services.config import settings  # noqa: E402
from scripts.vibe_prospecting_scan import (  # noqa: E402
    EXPLORIUM_BASE_URL_DEFAULT,
    REGION_COUNTRIES,
    build_business_filters,
    build_prospect_filters,
    explorium_post,
    fetch_business_ids,
    fetch_prospects,
)


BULK_ENRICH_PATH = "/prospects/contacts_information/bulk_enrich"
PROFILE_ENRICH_PATH = "/prospects/profiles/enrich"
EMAIL_LIKE_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_LIKE_PATTERN = re.compile(r"^\+?\d[\d\s\-().]{6,}$")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="explorium-email-probe",
        description="Probe whether Explorium returns plaintext emails, "
                    "mobile numbers, and richer profile data via the "
                    "enrichment endpoints. Costs ~16 credits per run.",
    )
    parser.add_argument("--region", required=True, choices=sorted(REGION_COUNTRIES))
    parser.add_argument("--icp", required=True, choices=["A1", "A2", "A3", "B1", "B2", "B3", "B4"])
    return parser.parse_args()


def redact(value: Any) -> Any:
    """Defensive PII redaction. Hides everything past the first 3 chars
    of any string field, except enum-shaped values."""
    if isinstance(value, str):
        if len(value) <= 4:
            return value
        if value.lower() in {"valid", "invalid", "catch-all", "professional", "personal"}:
            return value
        return value[:3] + "…[redacted]"
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def find_pattern_strings(record: Any, pattern: re.Pattern[str], prefix: str = "") -> list[tuple[str, str]]:
    """Walk a (possibly nested) record and return (path, value) pairs
    where the value matches `pattern`."""
    matches: list[tuple[str, str]] = []
    if isinstance(record, dict):
        for key, value in record.items():
            path = f"{prefix}.{key}" if prefix else key
            matches.extend(find_pattern_strings(value, pattern, path))
    elif isinstance(record, list):
        for idx, item in enumerate(record):
            path = f"{prefix}[{idx}]"
            matches.extend(find_pattern_strings(item, pattern, path))
    elif isinstance(record, str) and pattern.match(record):
        matches.append((prefix, record))
    return matches


def bulk_enrich_contacts(
    client: httpx.Client,
    api_key: str,
    base_url: str,
    prospect_ids: list[str],
) -> dict[str, Any]:
    body = {
        "prospect_ids": prospect_ids,
        # Default behaviour returns email + phone (5 credits/prospect).
        "parameters": {"contact_types": ["email", "phone"]},
    }
    return explorium_post(client, api_key, base_url, BULK_ENRICH_PATH, body)


def enrich_profile(
    client: httpx.Client,
    api_key: str,
    base_url: str,
    prospect_id: str,
) -> dict[str, Any]:
    body = {"prospect_id": prospect_id}
    return explorium_post(client, api_key, base_url, PROFILE_ENRICH_PATH, body)


def main() -> int:
    args = parse_args()
    api_key = (settings.VIBE_PROSPECTING_API_KEY or "").strip()
    base_url = (settings.VIBE_PROSPECTING_API_BASE_URL or EXPLORIUM_BASE_URL_DEFAULT).strip()
    if not api_key:
        print("VIBE_PROSPECTING_API_KEY is not set. Configure it in .env first.")
        return 1

    country_codes = REGION_COUNTRIES[args.region]
    print(f"Probing region={args.region} icp={args.icp} (limit=3, cost ~15 contact "
          f"credits + 1 profile credit if both endpoints are accessible)")

    with httpx.Client() as client:
        # Step 1: optional /businesses pre-query if the ICP needs it.
        business_filters = build_business_filters(args.icp, country_codes)
        business_ids: list[str] | None = None
        if business_filters is not None:
            business_ids = fetch_business_ids(
                client, api_key=api_key, base_url=base_url,
                filters=business_filters, max_ids=200,
            )
            if not business_ids:
                print("No matching businesses — probe ends.")
                return 0

        # Step 2: /prospects, capped at 3 results.
        prospect_filters = build_prospect_filters(args.icp, country_codes, business_ids)
        prospects, _meta = fetch_prospects(
            client, api_key=api_key, base_url=base_url,
            filters=prospect_filters, limit=3,
        )
        if not prospects:
            print("No prospects returned — probe ends.")
            return 0

        prospect_ids = [p.get("prospect_id") for p in prospects if p.get("prospect_id")]
        print(f"\n=== Fetched {len(prospects)} prospect records (sample, redacted) ===")
        print(json.dumps(redact(prospects[0]), indent=2)[:1200])

        # Step 3: bulk contact enrichment (email + mobile).
        if not prospect_ids:
            print("No prospect_ids on the response — cannot enrich.")
            return 0
        print(f"\n=== Calling bulk_enrich (email + mobile) for {len(prospect_ids)} id(s) ===")
        try:
            contact_enrichment = bulk_enrich_contacts(
                client, api_key, base_url, prospect_ids
            )
        except httpx.HTTPStatusError as exc:
            print(f"Contact enrichment failed: HTTP {exc.response.status_code}")
            print(f"Response body: {exc.response.text[:1500]}")
            print("\nLikely reasons:")
            print("  - Plan tier doesn't include contact enrichment endpoint")
            print("  - Out of credits")
            print("  - Endpoint path/shape changed (re-check docs)")
            contact_enrichment = {}

        if contact_enrichment:
            print("Contact enrichment response (redacted):")
            print(json.dumps(redact(contact_enrichment), indent=2)[:2000])

        # Step 4: profile enrichment for the first prospect only — cheaper
        # way to gauge whether profile data is worth the cost.
        first_id = prospect_ids[0]
        print(f"\n=== Calling /profiles/enrich for prospect_id={first_id[:8]}… ===")
        try:
            profile_enrichment = enrich_profile(client, api_key, base_url, first_id)
        except httpx.HTTPStatusError as exc:
            print(f"Profile enrichment failed: HTTP {exc.response.status_code}")
            print(f"Response body: {exc.response.text[:1500]}")
            profile_enrichment = {}

        if profile_enrichment:
            print("Profile enrichment response (redacted):")
            print(json.dumps(redact(profile_enrichment), indent=2)[:2500])

    # Side-by-side: where do email- and phone-shaped values actually live?
    print("\n=== Email-like fields, /v1/prospects ===")
    for prospect in prospects:
        for path, _ in find_pattern_strings(prospect, EMAIL_LIKE_PATTERN):
            print(f"  prospect_id={prospect.get('prospect_id', '')[:8]}…  {path}")
    print("\n=== Email-like fields, contact bulk_enrich ===")
    for path, _ in find_pattern_strings(contact_enrichment, EMAIL_LIKE_PATTERN):
        print(f"  {path}")
    print("\n=== Phone-like fields, contact bulk_enrich ===")
    for path, _ in find_pattern_strings(contact_enrichment, PHONE_LIKE_PATTERN):
        print(f"  {path}")
    print("\n=== Profile-enrichment fields of interest ===")
    for key in ("linkedin", "linkedin_url_array", "company_linkedin",
                "company_website", "experience", "education", "skills"):
        if key in profile_enrichment:
            value = profile_enrichment[key]
            preview = value if isinstance(value, str) else (
                f"({type(value).__name__}, len={len(value)})"
                if hasattr(value, "__len__") else str(value)[:60]
            )
            print(f"  {key}: {preview}")

    print("\nDone. If contact_enrichment shows plaintext email/phone fields and the")
    print("prospects block does not, the diagnosis in EXPLORIUM_EMAIL_INVESTIGATION")
    print("is confirmed and we can wire bulk_enrich (+ optionally profiles/enrich)")
    print("into vibe_prospecting_scan.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
