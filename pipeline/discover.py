"""
Discover official source manifests and write immutable snapshots.

Usage:
  python -m pipeline.discover --provider pursue --dry-run
  python -m pipeline.discover --provider pursue --allow-community-fallback
  python -m pipeline.discover --provider pursue --from-file path/to/uap-data.csv
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from pipeline.sources.base import file_sha256
from pipeline.sources.pursue import load_manifest, summarize_by_release

logger = logging.getLogger(__name__)

SNAPSHOT_ROOT = Path(__file__).parent / "snapshots"


def write_snapshot(
    *,
    provider: str,
    snapshot_date: date,
    raw: bytes,
    records: list,
    source_url: str,
    dry_run: bool,
) -> Path:
    digest = file_sha256(raw)
    out_dir = SNAPSHOT_ROOT / provider / snapshot_date.isoformat()
    manifest = {
        "provider": provider,
        "snapshot_date": snapshot_date.isoformat(),
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_url": source_url,
        "sha256": digest,
        "byte_size": len(raw),
        "record_count": len(records),
        "by_release": summarize_by_release(records),
        "by_type": _type_counts(records),
    }

    if dry_run:
        print(json.dumps(manifest, indent=2))
        print(f"[dry-run] would write snapshot to {out_dir}")
        return out_dir

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_name = "uap-data.csv" if provider == "pursue" else "manifest.csv"
    (out_dir / csv_name).write_bytes(raw)
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (out_dir / "manifest.sha256").write_text(f"{digest}  {csv_name}\n")

    # per-record index for diffing without re-parsing CSV later
    index = [r.to_row() for r in records]
    (out_dir / "records.json").write_text(json.dumps(index, indent=2, default=str) + "\n")

    logger.info("snapshot written: %s (%d records, sha256=%s)", out_dir, len(records), digest[:12])
    return out_dir


def _type_counts(records: list) -> dict[str, int]:
    from collections import Counter

    return dict(Counter(r.source_type for r in records))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Discover official source manifests")
    parser.add_argument("--provider", default="pursue", choices=["pursue", "aaro", "nara"])
    parser.add_argument("--snapshot-date", help="YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--from-file", type=Path, help="Local CSV instead of network fetch")
    parser.add_argument(
        "--allow-community-fallback",
        action="store_true",
        help="If official war.gov fetch fails, use SeeingBlue R06 snapshot (validation only)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if args.provider != "pursue":
        logger.error("%s provider not implemented yet (v2.1)", args.provider)
        return 2

    snapshot_date = (
        date.fromisoformat(args.snapshot_date)
        if args.snapshot_date
        else datetime.now(timezone.utc).date()
    )

    records, raw, source_url = load_manifest(
        path=args.from_file,
        allow_community_fallback=args.allow_community_fallback,
    )
    write_snapshot(
        provider=args.provider,
        snapshot_date=snapshot_date,
        raw=raw,
        records=records,
        source_url=source_url,
        dry_run=args.dry_run,
    )
    print(
        f"discovered {len(records)} {args.provider} records "
        f"from {source_url} (dry_run={args.dry_run})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
