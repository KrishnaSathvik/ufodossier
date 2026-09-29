"""
Cache official PURSUE PDFs locally from the official uap-data.csv snapshot.

LOCAL ONLY — never writes to Supabase.

Usage:
  python -m pipeline.cache_local_pdfs --ids ODNI-UAP-D001 --out-dir .cache/files/pursue/r2
  python -m pipeline.cache_local_pdfs --ids-file pipeline/reports/r3_readiness/sample_ids.txt \\
      --out-dir .cache/files/pursue/r3
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline.sources.http import OfficialSourceClient

logger = logging.getLogger(__name__)

DEFAULT_CSV = Path("pipeline/snapshots/pursue/2026-09-18-official/uap-data.csv")


def _load_env() -> None:
    import os

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def ext_id_from_title(title: str) -> str:
    m = re.match(r"^([A-Z0-9]+-UAP-[A-Z0-9]+)", title or "", re.I)
    return m.group(1).upper() if m else ""


def load_csv_index(csv_path: Path) -> dict[str, dict]:
    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    index: dict[str, dict] = {}
    for r in rows:
        eid = ext_id_from_title(r.get("Title") or "")
        if not eid:
            continue
        url = (r.get("PDF | Image Link") or "").strip()
        if not url:
            continue
        # Prefer PDF type when duplicates exist
        prev = index.get(eid)
        if prev and (prev.get("Type") or "").upper() == "PDF" and (r.get("Type") or "").upper() != "PDF":
            continue
        index[eid] = {
            "external_id": eid,
            "title": r.get("Title") or "",
            "type": r.get("Type") or "",
            "agency": r.get("Agency") or "",
            "description": r.get("Description Blurb") or "",
            "url": url,
            "incident_date": r.get("Incident Date") or "",
            "incident_location": r.get("Incident Location") or "",
        }
    return index


def cache_one(client: OfficialSourceClient, rec: dict, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    dest = out_dir / f"{rec['external_id']}.pdf"
    if dest.exists() and dest.stat().st_size > 1000:
        digest = hashlib.sha256(dest.read_bytes()).hexdigest()
        logger.info("cached (exists) %s (%d bytes)", dest.name, dest.stat().st_size)
        return {
            "external_id": rec["external_id"],
            "status": "exists",
            "path": str(dest),
            "byte_size": dest.stat().st_size,
            "sha256": digest,
            "url": rec["url"],
            "title": rec["title"],
        }

    logger.info("fetching %s", rec["external_id"])
    body, meta = client.get_bytes(rec["url"])
    if body[:4] != b"%PDF":
        raise RuntimeError(f"not a PDF for {rec['external_id']}: content-type={meta.get('content_type')}")
    dest.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    logger.info("wrote %s (%d bytes)", dest, len(body))
    return {
        "external_id": rec["external_id"],
        "status": "downloaded",
        "path": str(dest),
        "byte_size": len(body),
        "sha256": digest,
        "url": rec["url"],
        "title": rec["title"],
        "content_type": meta.get("content_type"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cache PURSUE PDFs locally (no DB writes)")
    parser.add_argument("--ids", nargs="+", help="External IDs e.g. ODNI-UAP-D001")
    parser.add_argument("--ids-file", type=Path, help="Newline-separated external IDs")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, help="Write fetch manifest JSON")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    _load_env()

    ids: list[str] = []
    if args.ids:
        ids.extend(args.ids)
    if args.ids_file:
        ids.extend(
            line.strip()
            for line in args.ids_file.read_text().splitlines()
            if line.strip() and not line.strip().startswith("#")
        )
    ids = [i.upper() for i in ids]
    if not ids:
        logger.error("provide --ids or --ids-file")
        return 1

    index = load_csv_index(args.csv)
    client = OfficialSourceClient()
    results = []
    errors = []
    for eid in ids:
        rec = index.get(eid)
        if not rec:
            errors.append({"external_id": eid, "error": "not_in_csv"})
            logger.error("not in CSV: %s", eid)
            continue
        try:
            results.append(cache_one(client, rec, args.out_dir))
        except Exception as e:
            logger.exception("fetch failed %s", eid)
            errors.append({"external_id": eid, "error": str(e), "url": rec.get("url")})

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_writes": False,
        "out_dir": str(args.out_dir),
        "fetched": results,
        "errors": errors,
    }
    out_path = args.manifest_out or (args.out_dir / "cache_manifest.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(manifest, indent=2) + "\n")
    logger.info("wrote %s (%d ok, %d err)", out_path, len(results), len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
