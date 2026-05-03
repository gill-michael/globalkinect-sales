"""Additive write of a Vibe-normalised prospect into the sales Supabase.

Idempotent and exception-safe: this module never raises into its caller.
Every call returns a status dict. On any error the function rolls back its
own transaction and reports `status='error'` with a reason — the existing
Notion / engine paths in `scripts/vibe_prospecting_scan.py` are unaffected.
"""

from __future__ import annotations

import json
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

from sales_db.connection import get_connection
from sales_services.dedup import find_existing_contact, _normalise_linkedin

try:
    from app.utils.logger import get_logger
    _logger = get_logger(__name__)
except Exception:  # pragma: no cover - logger import never blocks the write
    import logging
    _logger = logging.getLogger(__name__)


_DOMAIN_KEYS = ('company_website', 'website', 'company_domain', 'domain')


def _extract_domain(raw: dict) -> Optional[str]:
    for key in _DOMAIN_KEYS:
        value = raw.get(key)
        if not isinstance(value, str):
            continue
        candidate = value.strip()
        if not candidate:
            continue
        # Treat bare domains (no scheme) by prepending https:// so urlparse works.
        if '://' not in candidate:
            candidate = 'https://' + candidate
        host = (urlparse(candidate).netloc or '').lower()
        if host.startswith('www.'):
            host = host[4:]
        if host:
            return host
    return None


def _resolve_or_create_company(
    conn,
    name: str,
    domain: Optional[str],
    country: Optional[str],
    raw: dict,
) -> uuid.UUID:
    if domain:
        with conn.cursor() as cur:
            cur.execute(
                "select id from companies where lower(domain) = lower(%s) limit 1;",
                (domain,),
            )
            row = cur.fetchone()
        if row:
            return row[0]

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
                    "where lower(name) = lower(%s) and country is null "
                    "limit 1;",
                    (name,),
                )
            row = cur.fetchone()
        if row:
            return row[0]

    with conn.cursor() as cur:
        cur.execute(
            """insert into companies (name, domain, country, firmographic)
               values (%s, %s, %s, %s::jsonb) returning id;""",
            (name or 'Unknown Company',
             domain.lower() if domain else None,
             country,
             json.dumps(raw, default=str)),
        )
        return cur.fetchone()[0]


def write_to_sales_supabase(prospect_dict: dict) -> dict[str, Any]:
    """Write one Vibe-normalised prospect into the sales Supabase.

    Args:
        prospect_dict: output of `normalise_result()` in
            `scripts/vibe_prospecting_scan.py` (with optional enrichment
            overlays applied). Must contain a `raw` dict of the original
            Explorium response.

    Returns:
        {'status': 'created' | 'skipped_duplicate' | 'error',
         'contact_id': uuid.UUID | None,
         'reason': str | None}

    Never raises.
    """
    try:
        raw = prospect_dict.get('raw') or {}

        company_name = (prospect_dict.get('company_name') or '').strip()
        domain = _extract_domain(raw)
        country = (
            prospect_dict.get('company_country')
            or (prospect_dict.get('company_country_code') or None)
        )

        first_name = (raw.get('first_name') or '').strip() or None
        last_name = (raw.get('last_name') or '').strip() or None
        full_name = (prospect_dict.get('contact_name') or '').strip() or None
        email = (prospect_dict.get('email_plain') or '').strip() or None
        linkedin_raw = prospect_dict.get('linkedin_url') or ''
        linkedin_url = _normalise_linkedin(linkedin_raw) or None
        job_title = (prospect_dict.get('role') or '').strip() or None

        with get_connection() as conn:
            company_id = _resolve_or_create_company(
                conn, company_name, domain, country, raw
            )

            existing = find_existing_contact(
                conn,
                email=email,
                linkedin_url=linkedin_url,
                first_name=first_name,
                last_name=last_name,
                company_id=company_id,
            )
            if existing is not None:
                return {
                    'status': 'skipped_duplicate',
                    'contact_id': existing,
                    'reason': None,
                }

            with conn.cursor() as cur:
                cur.execute(
                    """insert into contacts
                       (company_id, first_name, last_name, full_name, email,
                        linkedin_url, job_title, source, source_metadata)
                       values (%s, %s, %s, %s, %s, %s, %s, 'vibe', %s::jsonb)
                       returning id;""",
                    (company_id, first_name, last_name, full_name, email,
                     linkedin_url, job_title, json.dumps(raw, default=str)),
                )
                new_id = cur.fetchone()[0]

        return {'status': 'created', 'contact_id': new_id, 'reason': None}

    except Exception as exc:
        try:
            _logger.warning('write_to_sales_supabase failed: %s', exc)
        except Exception:
            pass
        return {'status': 'error', 'contact_id': None, 'reason': str(exc)}
