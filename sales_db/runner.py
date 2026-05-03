from __future__ import annotations

import hashlib
from pathlib import Path

import psycopg

from sales_db.connection import get_connection


MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
MIGRATION_PATTERN = "[0-9][0-9][0-9][0-9]_*.sql"
MIGRATIONS_TABLE_SQL = """
create table if not exists schema_migrations (
    version text primary key,
    checksum text not null,
    applied_at timestamptz not null default now()
);
"""


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
    migration_files = list_migration_files()

    with get_connection() as conn:
        # Always create the tracking table on first run, even when no
        # migration files exist yet — Task 1's acceptance check requires
        # `schema_migrations` to appear after the runner's first invocation.
        ensure_migrations_table(conn)

        if not migration_files:
            print("No migration files found.")
            return

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
