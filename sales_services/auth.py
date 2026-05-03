"""Clerk JWT validation — fetches JWKS at startup and caches in memory (1-hour TTL).

Public surface:
    validate_clerk_jwt(token) -> dict | None
    prefetch_jwks() -> dict       (used by FastAPI lifespan to warm the cache)
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

try:
    from app.utils.logger import get_logger
    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


REPO_ROOT = Path(__file__).resolve().parents[1]
JWKS_TTL_SECONDS = 3600
USER_CACHE_TTL_SECONDS = 300
CLERK_BACKEND_API_BASE = 'https://api.clerk.com/v1'

_jwks_cache: dict = {}
_jwks_fetched_at: float = 0.0

# Per-sub user cache: sub -> (user_dict, expires_at_unix_ts)
_user_cache: dict = {}

# Module-load-time check — fail fast on misconfiguration.
load_dotenv(REPO_ROOT / '.env', override=True)
_CLERK_SECRET_KEY = os.getenv('CLERK_SECRET_KEY', '').strip()
if not _CLERK_SECRET_KEY:
    raise RuntimeError(
        'CLERK_SECRET_KEY is not set in .env '
        '(required for Clerk Backend API user fetch).'
    )


def _load_jwks_url() -> str:
    load_dotenv(REPO_ROOT / '.env', override=True)
    url = os.getenv('CLERK_JWKS_URL', '').strip()
    if not url:
        raise RuntimeError('CLERK_JWKS_URL is not set in .env')
    return url


def _fetch_jwks(force_refresh: bool = False) -> dict:
    global _jwks_cache, _jwks_fetched_at
    now = time.time()
    if not force_refresh and _jwks_cache and (now - _jwks_fetched_at) < JWKS_TTL_SECONDS:
        return _jwks_cache
    url = _load_jwks_url()
    r = httpx.get(url, timeout=10.0)
    r.raise_for_status()
    _jwks_cache = r.json()
    _jwks_fetched_at = now
    return _jwks_cache


def prefetch_jwks() -> dict:
    """Public entrypoint used at FastAPI startup to warm the JWKS cache."""
    return _fetch_jwks(force_refresh=True)


def _key_for_kid(jwks: dict, kid: str) -> Optional[dict]:
    for key in jwks.get('keys', []):
        if key.get('kid') == kid:
            return key
    return None


def validate_clerk_jwt(token: str) -> Optional[dict]:
    """Verify a Clerk-issued JWT. Returns claims dict on success, None on any failure.

    Never raises — every failure path logs and returns None so the caller
    can convert to a 401 response cleanly.
    """
    if not token or not isinstance(token, str):
        return None
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        logger.warning('Clerk JWT header parse failed: %s', exc)
        return None

    kid = unverified_header.get('kid')
    if not kid:
        logger.warning('Clerk JWT has no kid in header')
        return None

    try:
        jwks = _fetch_jwks()
    except Exception as exc:
        logger.warning('JWKS fetch failed: %s', exc)
        return None

    key = _key_for_kid(jwks, kid)
    if key is None:
        # The signing key may have rotated; force one refresh and retry.
        try:
            jwks = _fetch_jwks(force_refresh=True)
            key = _key_for_kid(jwks, kid)
        except Exception as exc:
            logger.warning('JWKS refresh on kid miss failed: %s', exc)
            return None
        if key is None:
            logger.warning('Clerk JWT signed with unknown kid=%s', kid)
            return None

    try:
        return jwt.decode(
            token,
            key,
            algorithms=['RS256'],
            options={'verify_aud': False},  # Clerk session tokens use `azp`, not `aud`
        )
    except ExpiredSignatureError:
        logger.warning('Clerk JWT expired')
        return None
    except JWTError as exc:
        logger.warning('Clerk JWT validation failed: %s', exc)
        return None


def fetch_clerk_user(sub: str) -> Optional[dict]:
    """Fetch user details from Clerk Backend API by Clerk user_id (`sub`).

    Returns dict {'email', 'first_name', 'last_name'} on success, None on
    any failure. Cached per-sub for USER_CACHE_TTL_SECONDS (5 min). Never
    raises; failures are logged and yield None.

    First successful resolve per sub logs at INFO; cache hits do not log
    (per spec — would be noisy).
    """
    if not sub:
        return None
    now = time.time()
    cached = _user_cache.get(sub)
    if cached and cached[1] > now:
        return cached[0]

    try:
        r = httpx.get(
            f'{CLERK_BACKEND_API_BASE}/users/{sub}',
            headers={'Authorization': 'Bearer ' + _CLERK_SECRET_KEY},
            timeout=10.0,
        )
    except Exception as exc:
        logger.warning('Clerk Backend API user fetch errored for %s: %s', sub, exc)
        return None

    if r.status_code != 200:
        logger.warning(
            'Clerk Backend API returned %s for user %s: %s',
            r.status_code, sub, r.text[:300],
        )
        return None

    try:
        data = r.json()
    except Exception as exc:
        logger.warning('Clerk Backend API JSON parse failed for %s: %s', sub, exc)
        return None

    # Resolve the primary email address by id; fall back to first available.
    primary_id = data.get('primary_email_address_id')
    email_addrs = data.get('email_addresses') or []
    email: Optional[str] = None
    if primary_id:
        for ea in email_addrs:
            if isinstance(ea, dict) and ea.get('id') == primary_id:
                email = ea.get('email_address')
                break
    if not email and email_addrs:
        first = email_addrs[0] if isinstance(email_addrs[0], dict) else None
        if first:
            email = first.get('email_address')

    user = {
        'email': email,
        'first_name': data.get('first_name'),
        'last_name': data.get('last_name'),
    }
    _user_cache[sub] = (user, now + USER_CACHE_TTL_SECONDS)
    logger.info('Resolved Clerk user %s from Backend API: email=%s', sub, email)
    return user
