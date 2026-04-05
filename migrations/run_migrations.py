from __future__ import annotations

import hashlib
import os
from pathlib import Path

from dotenv import load_dotenv

try:
    import psycopg
except ImportError as exc:  # pragma: no cover - validated by install step
    raise RuntimeError(
        "psycopg is required to run migrations. Install dependencies first."
    ) from exc


ROOT_DIR = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT_DIR / "migrations"
MIGRATION_PATTERN = "[0-9][0-9][0-9][0-9]_*.sql"
MIGRATIONS_TABLE_SQL = """
create table if not exists schema_migrations (
    version text primary key,
    checksum text not null,
    applied_at timestamptz not null default now()
);
"""


def load_database_url() -> str:
    load_dotenv(ROOT_DIR / ".env")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Migrations require a direct Postgres connection string."
        )
    return database_url


def list_migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob(MIGRATION_PATTERN))


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_migrations_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cursor:
        cursor.execute(MIGRATIONS_TABLE_SQL)
    conn.commit()


def fetch_applied_migrations(conn: psycopg.Connection) -> dict[str, str]:
    with conn.cursor() as cursor:
        cursor.execute("select version, checksum from schema_migrations order by version;")
        rows = cursor.fetchall()
    return {version: checksum for version, checksum in rows}


def apply_migration(
    conn: psycopg.Connection,
    migration_path: Path,
    checksum: str,
) -> None:
    migration_sql = migration_path.read_text(encoding="utf-8")
    print(f"Applying migration: {migration_path.name}")
    with conn.transaction():
        with conn.cursor() as cursor:
            cursor.execute(migration_sql)
            cursor.execute(
                """
                insert into schema_migrations (version, checksum)
                values (%s, %s);
                """,
                (migration_path.name, checksum),
            )


def main() -> None:
    database_url = load_database_url()
    migration_files = list_migration_files()

    if not migration_files:
        print("No migration files found.")
        return

    with psycopg.connect(database_url) as conn:
        ensure_migrations_table(conn)
        applied_migrations = fetch_applied_migrations(conn)

        pending_count = 0
        for migration_path in migration_files:
            checksum = file_checksum(migration_path)
            applied_checksum = applied_migrations.get(migration_path.name)

            if applied_checksum is not None:
                if applied_checksum != checksum:
                    raise RuntimeError(
                        f"Migration checksum mismatch for {migration_path.name}. "
                        "Do not edit applied migrations; create a new migration instead."
                    )
                continue

            apply_migration(conn, migration_path, checksum)
            pending_count += 1

    if pending_count == 0:
        print("All migrations are already applied.")
    else:
        print(f"Applied {pending_count} migration(s).")


if __name__ == "__main__":
    main()
