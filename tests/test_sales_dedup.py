"""Dedup library tests against the live sales Supabase project (per Task 8 spec).

Fixture inserts three known contacts at module setup, deletes them at module
teardown. The contacts table is expected to be empty before and after this
module runs — the TEST_TAG sentinel makes cleanup unambiguous.
"""

from __future__ import annotations

import pytest

from sales_db.connection import get_connection
from sales_services.dedup import find_existing_contact


TEST_TAG = 'TEST-DEDUP-PYTEST'


@pytest.fixture(scope='module')
def fixtures():
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "insert into companies (name) values (%s) returning id;",
                (TEST_TAG + ' Co',),
            )
            company_id = cur.fetchone()[0]

            # Alice — has email AND linkedin (used to test email-priority case)
            cur.execute(
                """insert into contacts
                   (full_name, first_name, last_name, email, linkedin_url, source, company_id)
                   values (%s, %s, %s, %s, %s, %s, %s) returning id;""",
                (TEST_TAG + ' Alice', 'Alice', 'Smith',
                 'Alice@Example.Com',
                 'https://linkedin.com/in/alice-smith',
                 TEST_TAG, company_id),
            )
            alice_id = cur.fetchone()[0]

            # Bob — no email, has linkedin + name+company
            cur.execute(
                """insert into contacts
                   (full_name, first_name, last_name, linkedin_url, source, company_id)
                   values (%s, %s, %s, %s, %s, %s) returning id;""",
                (TEST_TAG + ' Bob', 'Bob', 'Jones',
                 'https://linkedin.com/in/bob-jones',
                 TEST_TAG, company_id),
            )
            bob_id = cur.fetchone()[0]

            # Carol — no email, no linkedin, only name+company
            cur.execute(
                """insert into contacts
                   (full_name, first_name, last_name, source, company_id)
                   values (%s, %s, %s, %s, %s) returning id;""",
                (TEST_TAG + ' Carol', 'Carol', 'Williams',
                 TEST_TAG, company_id),
            )
            carol_id = cur.fetchone()[0]
        conn.commit()

        yield {
            'company_id': company_id,
            'alice_id': alice_id,
            'bob_id': bob_id,
            'carol_id': carol_id,
        }
    finally:
        with conn.cursor() as cur:
            cur.execute("delete from contacts where source = %s;", (TEST_TAG,))
            cur.execute("delete from companies where name = %s;", (TEST_TAG + ' Co',))
        conn.commit()
        conn.close()


def test_email_match_found(fixtures):
    """(a) email match found returns id (case-insensitive)."""
    with get_connection() as conn:
        result = find_existing_contact(conn, email='alice@example.com')
    assert result == fixtures['alice_id']


def test_linkedin_match_when_email_missing(fixtures):
    """(b) email absent, linkedin match found returns id."""
    with get_connection() as conn:
        result = find_existing_contact(
            conn, linkedin_url='https://linkedin.com/in/bob-jones'
        )
    assert result == fixtures['bob_id']


def test_name_company_match_when_email_and_linkedin_missing(fixtures):
    """(c) email + linkedin absent, name+company match found returns id."""
    with get_connection() as conn:
        result = find_existing_contact(
            conn,
            first_name='Carol',
            last_name='Williams',
            company_id=fixtures['company_id'],
        )
    assert result == fixtures['carol_id']


def test_email_mismatch_returns_none(fixtures):
    """(d) email mismatched returns None."""
    with get_connection() as conn:
        result = find_existing_contact(conn, email='nonexistent-dedup@example.com')
    assert result is None


def test_no_identifiers_returns_none(fixtures):
    """(e) all identifiers missing returns None."""
    with get_connection() as conn:
        result = find_existing_contact(conn)
    assert result is None


def test_email_priority_over_linkedin_mismatch(fixtures):
    """(f) email matches but linkedin doesn't — email wins (priority verified)."""
    with get_connection() as conn:
        result = find_existing_contact(
            conn,
            email='alice@example.com',
            linkedin_url='https://linkedin.com/in/some-wrong-person',
        )
    assert result == fixtures['alice_id']
