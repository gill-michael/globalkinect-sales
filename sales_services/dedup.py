"""Contact dedup library — find existing contacts by email / linkedin / name+company."""

from __future__ import annotations

import uuid
from typing import Optional

import psycopg


def _normalise_linkedin(url: str) -> str:
    s = (url or '').strip()
    if not s:
        return ''
    if not s.lower().startswith(('http://', 'https://')):
        s = 'https://' + s
    if s.endswith('/'):
        s = s[:-1]
    return s


def find_existing_contact(
    conn: psycopg.Connection,
    email: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    company_id: Optional[uuid.UUID] = None,
) -> Optional[uuid.UUID]:
    """Return the id of an existing contact that matches, or None.

    Match priority (first match wins):
      1. email match (case-insensitive)         — highest confidence
      2. linkedin_url exact match (normalised)  — high confidence
      3. (first_name + last_name + company_id)  — medium confidence
    """
    if email:
        with conn.cursor() as cur:
            cur.execute(
                "select id from contacts where lower(email) = lower(%s) limit 1;",
                (email,),
            )
            row = cur.fetchone()
        if row:
            return row[0]

    if linkedin_url:
        normalised = _normalise_linkedin(linkedin_url)
        if normalised:
            with conn.cursor() as cur:
                cur.execute(
                    "select id from contacts where linkedin_url = %s limit 1;",
                    (normalised,),
                )
                row = cur.fetchone()
            if row:
                return row[0]

    if first_name and last_name and company_id:
        with conn.cursor() as cur:
            cur.execute(
                """select id from contacts
                   where first_name = %s
                     and last_name = %s
                     and company_id = %s
                   limit 1;""",
                (first_name, last_name, company_id),
            )
            row = cur.fetchone()
        if row:
            return row[0]

    return None
