"""Clerk JWT auth dependency for FastAPI.

`require_user` is the dependency: validates the bearer token, looks up the
matching `users` row (by `sso_subject` first, falling back to `email`), or
provisions a fresh `users` row with role='sdr' if neither matches. Updates
`last_login_at` on every successful resolve.

Raises `UnauthorizedError` (caught by main.py's exception handler) on any
auth failure so the response body is the spec-shaped `{"error": "unauthorized"}`.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from sales_db.connection import get_connection
from sales_services.auth import fetch_clerk_user, validate_clerk_jwt

try:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


class UnauthorizedError(Exception):
    """Raised by require_user; converted to 401 by main.py's exception handler."""


_bearer = HTTPBearer(auto_error=False)


def _claims_email(claims: dict) -> Optional[str]:
    for key in ('email', 'primary_email_address', 'email_address'):
        v = claims.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    addrs = claims.get('email_addresses') or []
    if isinstance(addrs, list) and addrs:
        first = addrs[0]
        if isinstance(first, dict):
            v = first.get('email_address') or first.get('email')
            if isinstance(v, str) and v.strip():
                return v.strip()
    return None


def _claims_name(claims: dict) -> Optional[str]:
    name = claims.get('name')
    if isinstance(name, str) and name.strip():
        return name.strip()
    fn = (claims.get('first_name') or '').strip()
    ln = (claims.get('last_name') or '').strip()
    full = (fn + ' ' + ln).strip()
    return full or None


def _row_to_user_dict(row: tuple) -> dict:
    user_id, email, full_name, role, last_login_at = row
    return {
        'id': str(user_id),
        'email': email,
        'full_name': full_name,
        'role': role,
        'last_login_at': last_login_at.isoformat() if last_login_at else None,
    }


def _resolve_or_provision_user(
    sub: str, email: Optional[str], name: Optional[str],
) -> Optional[dict]:
    if not sub:
        return None
    with get_connection() as conn:
        with conn.cursor() as cur:
            # 1. by sso_subject
            cur.execute(
                "select id, email, full_name, role, last_login_at "
                "from users where sso_subject = %s limit 1;",
                (sub,),
            )
            row = cur.fetchone()
            if row:
                cur.execute(
                    "update users set last_login_at = (now() AT TIME ZONE 'utc') "
                    "where id = %s returning id, email, full_name, role, last_login_at;",
                    (row[0],),
                )
                return _row_to_user_dict(cur.fetchone())

            # 2. by email — link existing row to this Clerk subject
            if email:
                cur.execute(
                    "select id from users where lower(email) = lower(%s) limit 1;",
                    (email,),
                )
                existing = cur.fetchone()
                if existing:
                    cur.execute(
                        "update users set sso_subject = %s, "
                        "last_login_at = (now() AT TIME ZONE 'utc') "
                        "where id = %s "
                        "returning id, email, full_name, role, last_login_at;",
                        (sub, existing[0]),
                    )
                    return _row_to_user_dict(cur.fetchone())

            # 3. provision new sdr (requires email)
            if not email:
                logger.warning('Cannot provision user without email; sub=%s', sub)
                return None
            cur.execute(
                """insert into users (email, full_name, role, sso_subject, last_login_at)
                   values (%s, %s, 'sdr', %s, (now() AT TIME ZONE 'utc'))
                   returning id, email, full_name, role, last_login_at;""",
                (email, name, sub),
            )
            return _row_to_user_dict(cur.fetchone())


def require_user(
    request: Request,
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    if creds is None or (creds.scheme or '').lower() != 'bearer':
        raise UnauthorizedError()
    claims = validate_clerk_jwt(creds.credentials)
    if claims is None:
        raise UnauthorizedError()
    sub = claims.get('sub')
    if not sub:
        raise UnauthorizedError()

    # Prefer claims when present (forward-compat with custom Clerk session
    # templates), otherwise fall back to Clerk Backend API.
    email = _claims_email(claims)
    name = _claims_name(claims)
    if not email or not name:
        api_user = fetch_clerk_user(sub)
        if api_user:
            if not email:
                email = api_user.get('email')
            if not name:
                fn = (api_user.get('first_name') or '').strip()
                ln = (api_user.get('last_name') or '').strip()
                merged = (fn + ' ' + ln).strip()
                if merged:
                    name = merged

    user = _resolve_or_provision_user(sub, email, name)
    if user is None:
        raise UnauthorizedError()
    request.state.user = user
    return user
