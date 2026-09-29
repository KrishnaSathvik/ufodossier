"""
Diff two PURSUE (or generic) manifest snapshots.

Classifies each identity_key as:
  UNCHANGED | NEW | MODIFIED | DEPRECATED | RETURNED

Usage:
  python -m pipeline.diff_manifest \\
    --prev pipeline/snapshots/pursue/2026-08-07 \\
    --curr pipeline/snapshots/pursue/2026-09-18

  python -m pipeline.diff_manifest --prev ... --curr ... --write-diff
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_records(snapshot_dir: Path) -> dict[str, dict[str, Any]]:
    records_path = snapshot_dir / "records.json"
    if not records_path.exists():
        raise FileNotFoundError(
            f"missing {records_path}; run pipeline.discover first"
        )
    rows = json.loads(records_path.read_text())
    return {r["identity_key"]: r for r in rows}


def _content_fingerprint(row: dict[str, Any]) -> str:
    """Fields that constitute a content change (not last_seen)."""
    keys = (
        "title",
        "description",
        "agency",
        "source_type",
        "original_url",
        "download_url",
        "thumbnail_url",
        "sha256",
        "release_number",
        "incident_date_hint",
        "incident_location_hint",
        "status",
        "metadata",
    )
    payload = {k: row.get(k) for k in keys}
    return json.dumps(payload, sort_keys=True, default=str)


def diff_snapshots(
    prev: dict[str, dict[str, Any]],
    curr: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    prev_keys = set(prev)
    curr_keys = set(curr)

    new_keys = curr_keys - prev_keys
    gone_keys = prev_keys - curr_keys
    shared = prev_keys & curr_keys

    unchanged: list[str] = []
    modified: list[str] = []
    returned: list[str] = []

    for k in sorted(shared):
        if _content_fingerprint(prev[k]) == _content_fingerprint(curr[k]):
            unchanged.append(k)
        else:
            modified.append(k)

    # RETURNED: was deprecated/unavailable in prev, active in curr
    for k in list(new_keys):
        # cannot detect returned without history beyond prev; leave empty unless
        # prev had status deprecated for a key that reappears — handled below
        pass

    for k in sorted(gone_keys):
        # if it reappears later, next diff marks RETURNED when we see
        # curr active and a prior deprecated — for two-snapshot diff:
        if prev[k].get("status") == "deprecated":
            continue

    # Heuristic RETURNED: key in curr with metadata.prior_status == deprecated
    # For now: if prev status was deprecated and key still in curr → RETURNED
    for k in sorted(shared):
        if prev[k].get("status") == "deprecated" and curr[k].get("status") == "active":
            if k in unmodified_safe(unchanged, modified):
                pass
            returned.append(k)
            if k in unchanged:
                unchanged.remove(k)
            if k in modified:
                modified.remove(k)

    deprecated = sorted(gone_keys)

    summary = {
        "new": len(new_keys),
        "modified": len(modified),
        "deprecated": len(deprecated),
        "unchanged": len(unchanged),
        "returned": len(returned),
        "prev_count": len(prev),
        "curr_count": len(curr),
    }

    return {
        "summary": summary,
        "new": sorted(new_keys),
        "modified": modified,
        "deprecated": deprecated,
        "unchanged": unchanged,
        "returned": returned,
        "modified_detail": [
            {
                "identity_key": k,
                "prev": {f: prev[k].get(f) for f in ("title", "original_url", "sha256", "status")},
                "curr": {f: curr[k].get(f) for f in ("title", "original_url", "sha256", "status")},
            }
            for k in modified
        ],
    }


def unmodified_safe(unchanged: list[str], modified: list[str]) -> set[str]:
    return set(unchanged) | set(modified)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diff two manifest snapshots")
    parser.add_argument("--prev", type=Path, required=True)
    parser.add_argument("--curr", type=Path, required=True)
    parser.add_argument(
        "--write-diff",
        action="store_true",
        help="Write diff.json into --curr snapshot directory",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    prev = _load_records(args.prev)
    curr = _load_records(args.curr)
    result = diff_snapshots(prev, curr)

    # Enrich with release hint from curr manifest.json if present
    curr_meta_path = args.curr / "manifest.json"
    meta = json.loads(curr_meta_path.read_text()) if curr_meta_path.exists() else {}
    out = {
        "provider": meta.get("provider"),
        "snapshot": meta.get("snapshot_date"),
        "prev_snapshot": args.prev.name,
        "curr_snapshot": args.curr.name,
        **result,
    }

    print(json.dumps(out["summary"], indent=2))
    if args.dry_run and not args.write_diff:
        return 0

    if args.write_diff and not args.dry_run:
        path = args.curr / "diff.json"
        path.write_text(json.dumps(out, indent=2) + "\n")
        logger.info("wrote %s", path)
    elif args.write_diff and args.dry_run:
        print(f"[dry-run] would write {args.curr / 'diff.json'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
