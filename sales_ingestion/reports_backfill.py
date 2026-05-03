"""Reports backfill — one-shot import of `leads/Reports/<slug>/` content into the sales Supabase.

`leads/Reports/` is SACRED (per SYSTEM.md): this script reads only, never
modifies, moves, or deletes anything inside it. The acceptance check
verifies a SHA256 of the entire tree is byte-identical before and after.

Idempotent: re-running adds 0 new assets thanks to the
`assets_contact_type_path_idx` unique index added in migration 0008.

CLI (exactly one of --dry-run, --limit, --full required):
    python -m sales_ingestion.reports_backfill --dry-run
    python -m sales_ingestion.reports_backfill --limit 5
    python -m sales_ingestion.reports_backfill --full
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sales_db.connection import get_connection  # noqa: E402
from sales_services.dedup import find_existing_contact, _normalise_linkedin  # noqa: E402
from sales_ingestion.hubspot_backfill import _is_suppressed  # noqa: E402

try:
    from app.utils.logger import get_logger  # noqa: E402
    logger = get_logger(__name__)
except Exception:  # pragma: no cover
    import logging
    logger = logging.getLogger(__name__)


REPORTS_BASE = REPO_ROOT / 'leads' / 'Reports'

# Mapping: filename -> (asset.type, status-key in metadata.json that holds usage data)
ASSET_FILES = {
    'report.md':   ('research_report',   'perplexity_usage'),
    'email.md':    ('email',             'claude_usage'),
    'sequence.md': ('sequence',          'claude_usage'),
    'call.md':     ('call_script',       'claude_usage'),
    'linkedin.md': ('linkedin_message',  'claude_usage'),
}


def _slug_folders() -> list[Path]:
    return sorted(
        p for p in REPORTS_BASE.iterdir()
        if p.is_dir() and not p.name.startswith('_')
    )


def _tree_sha256(base: Path) -> str:
    """Deterministic SHA256 of the entire tree under `base`.

    Hashes each file's relative path + bytes, in sorted order. Used to
    prove byte-identical state of the SACRED leads/Reports/ folder
    before and after the backfill run.
    """
    hasher = hashlib.sha256()
    for p in sorted(base.rglob('*')):
        if not p.is_file():
            continue
        hasher.update(p.relative_to(base).as_posix().encode('utf-8'))
        hasher.update(b'\0')
        with open(p, 'rb') as fh:
            while True:
                chunk = fh.read(65536)
                if not chunk:
                    break
                hasher.update(chunk)
        hasher.update(b'\0')
    return hasher.hexdigest()


def _domain_from_website(website: Optional[str]) -> Optional[str]:
    if not website:
        return None
    s = website.strip()
    if not s:
        return None
    if '://' not in s:
        s = 'https://' + s
    host = (urlparse(s).netloc or '').lower()
    if host.startswith('www.'):
        host = host[4:]
    return host or None


def _split_name(full_name: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if not full_name:
        return None, None
    parts = full_name.strip().split()
    if not parts:
        return None, None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], ' '.join(parts[1:])


def _resolve_or_create_company(
    conn,
    name: str,
    domain: Optional[str],
    country: Optional[str],
    raw: dict,
) -> tuple:
    """Returns (company_id, was_created)."""
    if domain:
        with conn.cursor() as cur:
            cur.execute(
                "select id from companies where lower(domain) = lower(%s) limit 1;",
                (domain,),
            )
            row = cur.fetchone()
        if row:
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
            return row[0], False

    with conn.cursor() as cur:
        cur.execute(
            """insert into companies (name, domain, country, firmographic)
               values (%s, %s, %s, %s::jsonb) returning id;""",
            (name or 'Unknown Company',
             domain.lower() if domain else None,
             country,
             json.dumps(raw, default=str)),
        )
        return cur.fetchone()[0], True


def _insert_assets(
    conn, contact_id, folder: Path, metadata: dict, counters: dict,
) -> None:
    status = metadata.get('status') or {}
    processed_at = metadata.get('processed_at')
    slug = folder.name
    for filename, (asset_type, usage_key) in ASSET_FILES.items():
        asset_path = folder / filename
        if not asset_path.exists():
            continue
        relative_path = f'leads/Reports/{slug}/{filename}'
        usage = status.get(usage_key) or {}
        asset_metadata: dict[str, Any] = {}
        if usage:
            asset_metadata[usage_key] = usage
        errors = status.get('errors') or []
        if errors:
            asset_metadata['errors'] = errors
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """insert into assets
                       (contact_id, type, storage_path, generated_by, generated_at, metadata)
                       values (%s, %s, %s, %s, %s, %s::jsonb)
                       on conflict (contact_id, type, storage_path) do nothing
                       returning id;""",
                    (contact_id, asset_type, relative_path,
                     'unknown', processed_at,
                     json.dumps(asset_metadata, default=str)),
                )
                if cur.fetchone():
                    counters['assets_created'] += 1
        except Exception as exc:
            logger.warning('Asset insert failed for %s: %s', relative_path, exc)


def _process_folder(conn, folder: Path, counters: dict) -> None:
    metadata_path = folder / 'metadata.json'
    if not metadata_path.exists():
        counters['skipped_no_metadata'] += 1
        logger.warning('No metadata.json in %s', folder.name)
        return

    try:
        with open(metadata_path, 'r', encoding='utf-8') as fh:
            metadata = json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        counters['skipped_no_metadata'] += 1
        logger.warning('Could not parse metadata.json in %s: %s', folder.name, exc)
        return

    lead = metadata.get('lead') or {}
    full_name = (lead.get('full_name') or '').strip() or None
    role = (lead.get('role') or '').strip() or None
    company_name = (lead.get('company') or '').strip()
    website = lead.get('website')
    email = (lead.get('best_email')
             or lead.get('professional_email')
             or lead.get('personal_email') or '').strip() or None
    mobile = (lead.get('mobile') or '').strip() or None
    linkedin = _normalise_linkedin(lead.get('linkedin_url') or '') or None
    country = (lead.get('prospect_country') or '').strip() or None

    # Suppression check (no hubspot_id available for this source).
    if _is_suppressed(conn, None, email):
        counters['suppressed'] += 1
        return

    domain = _domain_from_website(website)
    company_id, was_created = _resolve_or_create_company(
        conn, company_name, domain, country, lead,
    )
    if was_created:
        counters['companies_created'] += 1

    first, last = _split_name(full_name)
    contact_id = find_existing_contact(
        conn,
        email=email,
        linkedin_url=linkedin,
        first_name=first,
        last_name=last,
        company_id=company_id,
    )

    if contact_id is not None:
        counters['linked_to_existing'] += 1
    else:
        with conn.cursor() as cur:
            cur.execute(
                """insert into contacts
                   (company_id, first_name, last_name, full_name, email, mobile,
                    linkedin_url, job_title, source, source_metadata)
                   values (%s, %s, %s, %s, %s, %s, %s, %s, 'manual', %s::jsonb)
                   returning id;""",
                (company_id, first, last, full_name, email, mobile,
                 linkedin, role, json.dumps(metadata, default=str)),
            )
            contact_id = cur.fetchone()[0]
        counters['new_contact'] += 1

    _insert_assets(conn, contact_id, folder, metadata, counters)


def do_dry_run() -> None:
    folders = _slug_folders()
    print('Reports dry-run summary')
    print(f'  Total slug folders:           {len(folders)}')
    metadata_count = sum(1 for p in folders if (p / 'metadata.json').exists())
    print(f'  Folders with metadata.json:   {metadata_count}/{len(folders)}')
    print()
    print('  Per-asset presence across folders:')
    for filename in ASSET_FILES:
        present = sum(1 for p in folders if (p / filename).exists())
        print(f'    {filename:<14} {present}/{len(folders)}')
    print()
    pre_hash = _tree_sha256(REPORTS_BASE)
    print(f'  leads/Reports/ tree SHA256:   {pre_hash}')


def do_backfill(limit: Optional[int]) -> None:
    folders = _slug_folders()
    print(f'Found {len(folders)} slug folders under leads/Reports/')
    if limit is not None:
        folders = folders[:limit]
        print(f'  --limit {limit}: processing first {len(folders)} alphabetically')

    print('Computing pre-run SHA256 of leads/Reports/ tree ...')
    pre_hash = _tree_sha256(REPORTS_BASE)
    print(f'  pre_hash:  {pre_hash}')

    counters = {
        'processed': 0,
        'new_contact': 0,
        'linked_to_existing': 0,
        'suppressed': 0,
        'skipped_no_metadata': 0,
        'errors': 0,
        'assets_created': 0,
        'companies_created': 0,
    }

    conn = get_connection()
    try:
        for folder in folders:
            counters['processed'] += 1
            try:
                _process_folder(conn, folder, counters)
                conn.commit()
            except Exception as exc:
                conn.rollback()
                counters['errors'] += 1
                logger.warning(
                    'Per-folder error for %s: %s', folder.name, exc,
                )
            if counters['processed'] % 10 == 0:
                print(f'  ... processed {counters["processed"]} folders')
    finally:
        conn.close()

    print('Computing post-run SHA256 of leads/Reports/ tree ...')
    post_hash = _tree_sha256(REPORTS_BASE)
    print(f'  post_hash: {post_hash}')
    print()
    print(
        f'Reports backfill: {counters["processed"]} folders processed, '
        f'{counters["new_contact"]} new_contact, '
        f'{counters["linked_to_existing"]} linked_to_existing, '
        f'{counters["suppressed"]} suppressed, '
        f'{counters["skipped_no_metadata"]} skipped_no_metadata, '
        f'{counters["errors"]} errors, '
        f'{counters["assets_created"]} assets created, '
        f'{counters["companies_created"]} companies created.'
    )
    print()
    if pre_hash == post_hash:
        print('SACRED check: leads/Reports/ tree is byte-identical (pre == post). PASS.')
    else:
        print('SACRED check: leads/Reports/ tree CHANGED. FAIL.')
        print(f'  pre:  {pre_hash}')
        print(f'  post: {post_hash}')
        sys.exit(2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='reports-backfill',
        description='One-shot backfill of leads/Reports/<slug>/ content into the sales Supabase.',
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--dry-run', action='store_true',
                       help='Count folders and assets, no writes.')
    mode.add_argument('--limit', type=int,
                       help='Process first N slug folders alphabetically.')
    mode.add_argument('--full', action='store_true',
                       help='Process all slug folders.')
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        do_dry_run()
    elif args.full:
        do_backfill(limit=None)
    else:
        do_backfill(limit=args.limit)


if __name__ == '__main__':
    main()
