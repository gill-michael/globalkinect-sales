from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - validated by install step
    raise RuntimeError(
        "psycopg is required. Install dependencies first."
    ) from exc


ROOT_DIR = Path(__file__).resolve().parents[1]


def get_connection() -> psycopg.Connection:
    load_dotenv(ROOT_DIR / ".env")
    database_url = os.getenv("SALES_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "SALES_DATABASE_URL is not set. The sales engine requires the "
            "isolated sales Supabase Postgres connection string."
        )
    return psycopg.connect(database_url, autocommit=False)


def get_supabase_client():
    """Stub for future use — not exercised by week-1 code paths."""
    from supabase import create_client

    load_dotenv(ROOT_DIR / ".env")
    url = os.getenv("SALES_SUPABASE_URL", "").strip()
    publishable_key = os.getenv("SALES_SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not url or not publishable_key:
        raise RuntimeError(
            "SALES_SUPABASE_URL and SALES_SUPABASE_PUBLISHABLE_KEY must be set "
            "to call get_supabase_client()."
        )
    return create_client(url, publishable_key)
