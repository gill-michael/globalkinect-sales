from __future__ import annotations

import argparse
import re
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = ROOT_DIR / "migrations"
MIGRATION_PATTERN = re.compile(r"^(?P<number>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not slug:
        raise ValueError("Migration name must contain letters or numbers.")
    return slug


def next_migration_number() -> int:
    numbers = []
    for path in MIGRATIONS_DIR.glob("*.sql"):
        match = MIGRATION_PATTERN.match(path.name)
        if match:
            numbers.append(int(match.group("number")))
    return (max(numbers) + 1) if numbers else 1


def build_template(migration_name: str) -> str:
    created_at = datetime.now(timezone.utc).isoformat()
    return (
        f"-- Migration: {migration_name}\n"
        f"-- Created at: {created_at}\n\n"
        "-- Write forward-only SQL here.\n"
        "-- If rollback is needed, create a compensating migration.\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a new forward-only SQL migration file.",
    )
    parser.add_argument("name", help="Short migration name, for example: add_task_indexes")
    args = parser.parse_args()

    migration_name = slugify(args.name)
    migration_number = next_migration_number()
    migration_path = MIGRATIONS_DIR / f"{migration_number:04d}_{migration_name}.sql"

    if migration_path.exists():
        raise RuntimeError(f"Migration already exists: {migration_path.name}")

    migration_path.write_text(build_template(migration_name), encoding="utf-8")
    print(f"Created migration: {migration_path}")


if __name__ == "__main__":
    main()
