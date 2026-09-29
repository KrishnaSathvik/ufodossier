"""
Import source_records metadata from a snapshot (no downloads, no model calls).

Usage:
  python -m pipeline.import_source_records --release 2 --dry-run
  python -m pipeline.import_source_records --releases 2,3,4,5,6 --apply
  python -m pipeline.import_source_records --all --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline.db import get_supabase
from pipeline.sources.pursue import load_manifest

logger = logging.getLogger(__name__)

OFFICIAL_DIR = Path(__file__).parent / "snapshots" / "pursue" / "2026-09-18-official"
FALLBACK_DIR = Path(__file__).parent / "snapshots" / "pursue" / "2026-09-18"


def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import source_records metadata")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--release", type=int)
    parser.add_argument("--releases", help="Comma-separated release numbers")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    if args.apply:
        args.dry_run = False

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    _load_env()

    snap = args.snapshot
    if snap is None:
        if (OFFICIAL_DIR / "uap-data.csv").exists():
            snap = OFFICIAL_DIR
        else:
            snap = FALLBACK_DIR
    csv_path = snap / "uap-data.csv"
    records, raw, src = load_manifest(path=csv_path)

    wanted: set[int] | None = None
    if args.all:
        wanted = None
    elif args.releases:
        wanted = {int(x) for x in args.releases.split(",")}
    elif args.release:
        wanted = {args.release}
    else:
        parser.error("Specify --release, --releases, or --all")

    if wanted is not None:
        records = [r for r in records if r.release_number in wanted]

    from collections import Counter

    print(f"source: {src}")
    print(f"rows to import: {len(records)}")
    print(f"by_release: {dict(Counter(r.release_number for r in records))}")
    print(f"by_type: {dict(Counter(r.source_type for r in records))}")
    print(f"dry_run: {args.dry_run}")

    if args.dry_run:
        return 0

    sb = get_supabase()
    now = datetime.now(timezone.utc).isoformat()
    rows = []
    seen_keys: set[str] = set()
    dupes = 0
    for r in records:
        row = r.to_row()
        key = row["identity_key"]
        if key in seen_keys:
            dupes += 1
            logger.warning("skipping duplicate identity_key in batch: %s (%s)", key, row.get("title"))
            continue
        seen_keys.add(key)
        row["first_seen_at"] = now
        row["last_seen_at"] = now
        rows.append(row)
    if dupes:
        logger.warning("deduped %d duplicate identity_keys before upsert", dupes)

    upserted = 0
    for i in range(0, len(rows), 50):
        batch = rows[i : i + 50]
        sb.table("source_records").upsert(
            batch, on_conflict="provider,identity_key"
        ).execute()
        upserted += len(batch)
        logger.info("upserted %d/%d", upserted, len(rows))

    print(json.dumps({"upserted": upserted}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
