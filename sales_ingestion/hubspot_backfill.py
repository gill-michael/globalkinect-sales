"""HubSpot backfill — one-shot import of HubSpot Contacts and Companies into the sales Supabase.

Idempotent: re-running with the same Contacts adds 0 new rows but updates
hubspot_id on previously-unlinked rows.

CLI (exactly one of --dry-run, --limit, --full required):
    python -m sales_ingestion.hubspot_backfill --dry-run
    python -m sales_ingestion.hubspot_backfill --limit 10
    python -m sales_ingestion.hubspot_backfill --full
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterator, Optional

import httpx
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sales_db.connection import get_connection  # noqa: E402
from sales_services.dedup import find_existing_contact, _normalise_linkedin  # noqa: E402

try:
    from app.utils.logger import get_logger  # noqa: E402
    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


HUBSPOT_BASE = 'https://api.hubapi.com'

REQUESTED_CONTACT_PROPS: list[str] = [
    'firstname', 'lastname', 'email', 'jobtitle', 'mobilephone',
    'hs_linkedin_url', 'country', 'lifecyclestage',
    'createdate', 'lastmodifieddate',
]
REQUESTED_COMPANY_PROPS: list[str] = [
    'name', 'domain', 'country', 'industry', 'numberofemployees',
    'createdate', 'hs_lastmodifieddate',
]

NOISE_EMAIL_PATTERN = re.compile(
    r'^(message|info|noreply|no-reply|sales|hello|contact|admin|support|webmaster|hr)@',
    re.IGNORECASE,
)


def _is_suppressed(conn, hubspot_id: Optional[str], email: Optional[str]) -> bool:
    """Permanent block: return True if either hubspot_id or email is on the suppression list."""
    if not hubspot_id and not email:
        return False
    with conn.cursor() as cur:
        if hubspot_id:
            cur.execute(
                "select 1 from contact_suppressions where hubspot_id = %s limit 1;",
                (hubspot_id,),
            )
            if cur.fetchone():
                return True
        if email:
            cur.execute(
                "select 1 from contact_suppressions "
                "where lower(email) = lower(%s) limit 1;",
                (email,),
            )
            if cur.fetchone():
                return True
    return False


def _matches_noise_pattern(email: Optional[str]) -> bool:
    """Heuristic filter: True if the email's local part is a generic role address."""
    if not email:
        return False
    return bool(NOISE_EMAIL_PATTERN.match(email.strip()))


def _load_token() -> str:
    load_dotenv(REPO_ROOT / '.env', override=True)
    key = os.getenv('HUBSPOT_API_KEY', '').strip()
    if not key:
        raise RuntimeError('HUBSPOT_API_KEY is not set in .env')
    return key


def _hs_get(client: httpx.Client, token: str, path: str,
            params: Optional[dict] = None) -> dict:
    r = client.get(
        HUBSPOT_BASE + path,
        headers={'Authorization': 'Bearer ' + token},
        params=params or {},
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def _hs_post(client: httpx.Client, token: str, path: str, body: dict) -> dict:
    r = client.post(
        HUBSPOT_BASE + path,
        headers={
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json',
        },
        json=body,
        timeout=30.0,
    )
    r.raise_for_status()
    return r.json()


def do_dry_run(client: httpx.Client, token: str) -> None:
    contact_total = _hs_post(
        client, token, '/crm/v3/objects/contacts/search',
        {'filterGroups': [], 'limit': 1, 'properties': ['hs_object_id']},
    ).get('total', 0)
    company_total = _hs_post(
        client, token, '/crm/v3/objects/companies/search',
        {'filterGroups': [], 'limit': 1, 'properties': ['hs_object_id']},
    ).get('total', 0)

    contact_props = _hs_get(client, token, '/crm/v3/properties/contacts').get('results', [])
    company_props = _hs_get(client, token, '/crm/v3/properties/companies').get('results', [])

    custom_contact = sorted(p['name'] for p in contact_props if not p.get('hubspotDefined', True))
    custom_company = sorted(p['name'] for p in company_props if not p.get('hubspotDefined', True))

    print('HubSpot dry-run summary')
    print(f'  Total contacts:               {contact_total}')
    print(f'  Total companies:              {company_total}')
    print(f'  Contact properties (all):     {len(contact_props)}')
    print(f'  Company properties (all):     {len(company_props)}')
    print(f'  Requested contact properties: {len(REQUESTED_CONTACT_PROPS)} '
          f'-> {", ".join(REQUESTED_CONTACT_PROPS)}')
    print(f'  Requested company properties: {len(REQUESTED_COMPANY_PROPS)} '
          f'-> {", ".join(REQUESTED_COMPANY_PROPS)}')
    print()
    if custom_contact:
        print(f'Custom contact properties discovered ({len(custom_contact)}):')
        for name in custom_contact:
            print(f'  - {name}')
    else:
        print('Custom contact properties discovered: (none)')
    print()
    if custom_company:
        print(f'Custom company properties discovered ({len(custom_company)}):')
        for name in custom_company:
            print(f'  - {name}')
    else:
        print('Custom company properties discovered: (none)')


def fetch_contacts_paginated(
    client: httpx.Client, token: str, limit: Optional[int],
) -> Iterator[dict]:
    after: Optional[str] = None
    fetched = 0
    while limit is None or fetched < limit:
        page_size = 100 if limit is None else min(100, limit - fetched)
        params: dict[str, Any] = {
            'limit': page_size,
            'properties': ','.join(REQUESTED_CONTACT_PROPS),
            'associations': 'companies',
        }
        if after:
            params['after'] = after
        body = _hs_get(client, token, '/crm/v3/objects/contacts', params=params)
        for contact in body.get('results', []):
            yield contact
            fetched += 1
            if limit is not None and fetched >= limit:
                return
        after = ((body.get('paging') or {}).get('next') or {}).get('after')
        if not after:
            return


def _company_id_from_associations(contact: dict) -> Optional[str]:
    assoc = (contact.get('associations') or {}).get('companies') or {}
    for entry in assoc.get('results', []):
        cid = entry.get('id')
        if cid:
            return cid
    return None


def _fetch_company(client: httpx.Client, token: str, hubspot_company_id: str) -> dict:
    return _hs_get(
        client, token, f'/crm/v3/objects/companies/{hubspot_company_id}',
        params={'properties': ','.join(REQUESTED_COMPANY_PROPS)},
    )


def _resolve_or_create_company(
    conn,
    name: str,
    domain: Optional[str],
    country: Optional[str],
    hubspot_id: Optional[str],
    raw: dict,
) -> tuple:
    """Returns (company_id, was_created)."""
    if hubspot_id:
        with conn.cursor() as cur:
            cur.execute(
                "select id from companies where hubspot_id = %s limit 1;",
                (hubspot_id,),
            )
            row = cur.fetchone()
        if row:
            return row[0], False

    if domain:
        with conn.cursor() as cur:
            cur.execute(
                "select id from companies where lower(domain) = lower(%s) limit 1;",
                (domain,),
            )
            row = cur.fetchone()
        if row:
            if hubspot_id:
                with conn.cursor() as cur:
                    cur.execute(
                        "update companies set hubspot_id = %s "
                        "where id = %s and hubspot_id is null;",
                        (hubspot_id, row[0]),
                    )
            return row[0], False

    if name:
        with conn.cursor() as cur:
            if country:
                cur.execute(
                    "select id from companies "
                    "where lower(name) = lower(%s) and lower(country) = lower(%s) "
                    "limit 1;",
                    (name, country),
                )
            else:
                cur.execute(
                    "select id from companies "
                    "where lower(name) = lower(%s) and country is null limit 1;",
                    (name,),
                )
            row = cur.fetchone()
        if row:
            if hubspot_id:
                with conn.cursor() as cur:
                    cur.execute(
                        "update companies set hubspot_id = %s "
                        "where id = %s and hubspot_id is null;",
                        (hubspot_id, row[0]),
                    )
            return row[0], False

    with conn.cursor() as cur:
        cur.execute(
            """insert into companies (name, domain, country, hubspot_id, firmographic)
               values (%s, %s, %s, %s, %s::jsonb) returning id;""",
            (name or 'Unknown Company',
             domain.lower() if domain else None,
             country,
             hubspot_id,
             json.dumps(raw, default=str)),
        )
        return cur.fetchone()[0], True


def _process_contact(
    conn,
    contact: dict,
    client: httpx.Client,
    token: str,
    company_cache: dict,
    counters: dict,
) -> None:
    hubspot_contact_id = contact.get('id')
    props = contact.get('properties') or {}

    first = (props.get('firstname') or '').strip() or None
    last = (props.get('lastname') or '').strip() or None
    email = (props.get('email') or '').strip() or None

    # Permanent block (suppression list) and heuristic noise filter both run
    # BEFORE any company resolution or dedup work — short-circuit to avoid
    # touching the rest of the schema for contacts we already know to skip.
    if _is_suppressed(conn, hubspot_contact_id, email):
        counters['suppressed'] += 1
        return
    if _matches_noise_pattern(email):
        counters['filtered_noise'] += 1
        return

    linkedin = _normalise_linkedin(props.get('hs_linkedin_url') or '') or None
    job_title = (props.get('jobtitle') or '').strip() or None
    mobile = (props.get('mobilephone') or '').strip() or None
    full_name = ' '.join(p for p in [first, last] if p) or None

    company_id = None
    company_assoc = _company_id_from_associations(contact)
    if company_assoc:
        if company_assoc in company_cache:
            company_id = company_cache[company_assoc]
        else:
            try:
                co_data = _fetch_company(client, token, company_assoc)
                co_props = co_data.get('properties') or {}
                company_id, was_created = _resolve_or_create_company(
                    conn,
                    name=(co_props.get('name') or '').strip(),
                    domain=(co_props.get('domain') or '').strip() or None,
                    country=(co_props.get('country') or '').strip() or None,
                    hubspot_id=company_assoc,
                    raw=co_data,
                )
                company_cache[company_assoc] = company_id
                if was_created:
                    counters['companies_created'] += 1
            except Exception as exc:
                logger.warning(
                    'Company fetch failed for HubSpot company id %s: %s',
                    company_assoc, exc,
                )
                company_id = None

    existing = find_existing_contact(
        conn,
        email=email,
        linkedin_url=linkedin,
        first_name=first,
        last_name=last,
        company_id=company_id,
    )

    if existing is not None:
        with conn.cursor() as cur:
            cur.execute("select hubspot_id from contacts where id = %s;", (existing,))
            current_hid = cur.fetchone()[0]
            if current_hid is None:
                cur.execute(
                    "update contacts set hubspot_id = %s where id = %s;",
                    (hubspot_contact_id, existing),
                )
        counters['linked'] += 1
        return

    with conn.cursor() as cur:
        cur.execute(
            """insert into contacts
               (company_id, first_name, last_name, full_name, email, mobile,
                linkedin_url, job_title, hubspot_id, source, source_metadata)
               values (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'hubspot_import', %s::jsonb)
               returning id;""",
            (company_id, first, last, full_name, email, mobile,
             linkedin, job_title, hubspot_contact_id, json.dumps(contact, default=str)),
        )
        cur.fetchone()
    counters['new'] += 1


def do_backfill(client: httpx.Client, token: str, limit: Optional[int]) -> None:
    counters = {
        'processed': 0,
        'new': 0,
        'linked': 0,
        'suppressed': 0,
        'filtered_noise': 0,
        'error': 0,
        'companies_created': 0,
    }
    company_cache: dict[str, Any] = {}

    conn = get_connection()
    try:
        for contact in fetch_contacts_paginated(client, token, limit):
            counters['processed'] += 1
            try:
                _process_contact(conn, contact, client, token, company_cache, counters)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                counters['error'] += 1
                logger.warning(
                    'Per-contact error for hubspot_id=%s: %s',
                    contact.get('id'), exc,
                )
            if counters['processed'] % 100 == 0:
                print(f'  ... processed {counters["processed"]} contacts')
    finally:
        conn.close()

    print()
    print(
        f'HubSpot backfill: {counters["processed"]} processed, '
        f'{counters["new"]} new, {counters["linked"]} linked, '
        f'{counters["suppressed"]} suppressed, '
        f'{counters["filtered_noise"]} filtered_noise, '
        f'{counters["error"]} errors, '
        f'{counters["companies_created"]} companies created.'
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='hubspot-backfill',
        description='One-shot import of HubSpot Contacts and Companies into the sales Supabase.',
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true',
                       help='Count contacts and companies, list custom properties, no writes.')
    mode.add_argument('--limit', type=int,
                       help='Process only the first N contacts.')
    mode.add_argument('--full', action='store_true',
                       help='Process all contacts.')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = _load_token()
    with httpx.Client() as client:
        if args.dry_run:
            do_dry_run(client, token)
        elif args.full:
            do_backfill(client, token, limit=None)
        else:
            do_backfill(client, token, limit=args.limit)


if __name__ == '__main__':
    main()
