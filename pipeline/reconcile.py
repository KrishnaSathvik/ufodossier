"""
Reconcile official PURSUE source_records against production source_files.

Usage:
  python -m pipeline.reconcile --provider pursue --release 1 --dry-run
  python -m pipeline.reconcile --provider pursue --release 1 --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from pipeline.db import get_supabase
from pipeline.sources.base import normalize_ws, slugify
from pipeline.sources.pursue import load_manifest

logger = logging.getLogger(__name__)

REPORTS_DIR = Path(__file__).parent / "reports"
DEFAULT_SNAPSHOT = (
    Path(__file__).parent / "snapshots" / "pursue" / "2026-09-18-official"
)
FALLBACK_SNAPSHOT = (
    Path(__file__).parent / "snapshots" / "pursue" / "2026-09-18"
)


def normalize_url(url: str | None) -> str:
    if not url:
        return ""
    u = unquote(normalize_ws(url)).lower().rstrip("/")
    # strip query/fragment
    parsed = urlparse(u)
    path = re.sub(r"/+", "/", parsed.path)
    # collapse common encoding artifacts seen across R01 mirrors
    path = path.replace("+", " ").replace("%20", " ")
    path = re.sub(r"\s+", "", path)  # remove spaces for comparison
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def extract_dvids_id(url: str | None, metadata: dict | None = None) -> str | None:
    if metadata:
        raw = metadata.get("dvids_video_id")
        if raw and str(raw).strip().isdigit():
            return str(raw).strip()
    if not url:
        return None
    m = re.search(r"(?:dvidshub\.net/video(?:/embed)?/|video/)(\d+)", url, re.I)
    return m.group(1) if m else None


def basename_key(url: str | None, title: str | None = None) -> str:
    if url:
        stem = Path(urlparse(unquote(url)).path).stem.lower()
        stem = re.sub(r"[^a-z0-9]+", "", stem)
        if stem:
            return stem
    if title:
        return re.sub(r"[^a-z0-9]+", "", title.lower())
    return ""


def load_canonical(release: int, snapshot_dir: Path | None) -> list[Any]:
    path = None
    if snapshot_dir and (snapshot_dir / "uap-data.csv").exists():
        path = snapshot_dir / "uap-data.csv"
    elif (DEFAULT_SNAPSHOT / "uap-data.csv").exists():
        path = DEFAULT_SNAPSHOT / "uap-data.csv"
    elif (FALLBACK_SNAPSHOT / "uap-data.csv").exists():
        path = FALLBACK_SNAPSHOT / "uap-data.csv"
    else:
        raise FileNotFoundError(
            "No snapshot CSV found. Run: python -m pipeline.discover --provider pursue"
        )
    records, _, src = load_manifest(path=path)
    filtered = [r for r in records if r.release_number == release]
    logger.info("loaded %d release-%d records from %s", len(filtered), release, src)
    return filtered


def fetch_production_source_files(sb) -> list[dict]:
    rows: list[dict] = []
    start = 0
    page = 1000
    while True:
        chunk = (
            sb.table("source_files")
            .select("id,url,filename,file_type,agency,sha256,source_record_id,byte_size")
            .range(start, start + page - 1)
            .execute()
        )
        data = chunk.data or []
        rows.extend(data)
        if len(data) < page:
            break
        start += page
    return rows


def match_records(
    canonical: list[Any],
    production: list[dict],
) -> dict[str, Any]:
    """
    Matching priority:
      1. exact URL
      2. normalized URL
      3. DVIDS video id (unique only)
      4. external_id in production filename/url (unique only)
      5. basename/title key (unique only)
    Ambiguous matches are NOT auto-linked.
    """
    from pipeline.sources.pursue import extract_external_id

    by_exact: dict[str, list[dict]] = defaultdict(list)
    by_norm: dict[str, list[dict]] = defaultdict(list)
    by_base: dict[str, list[dict]] = defaultdict(list)
    by_dvids: dict[str, list[dict]] = defaultdict(list)
    by_ext_id: dict[str, list[dict]] = defaultdict(list)

    for sf in production:
        url = sf.get("url") or ""
        by_exact[url].append(sf)
        n = normalize_url(url)
        if n:
            by_norm[n].append(sf)
        b = basename_key(url, sf.get("filename"))
        if b:
            by_base[b].append(sf)
        did = extract_dvids_id(url)
        if did:
            by_dvids[did].append(sf)
        eid = extract_external_id(sf.get("filename"), url)
        if eid:
            by_ext_id[eid].append(sf)

    exact: list[dict] = []
    normalized: list[dict] = []
    ambiguous: list[dict] = []
    missing_locally: list[dict] = []
    used_sf_ids: set[str] = set()

    for rec in canonical:
        cand_url = rec.original_url or rec.download_url or ""
        entry = {
            "identity_key": rec.identity_key,
            "external_id": rec.external_id,
            "title": rec.title,
            "source_type": rec.source_type,
            "original_url": cand_url,
            "agency": rec.agency,
        }

        # 1. exact
        hits = [h for h in by_exact.get(cand_url, []) if h["id"] not in used_sf_ids]
        if len(hits) == 1:
            exact.append({**entry, "source_file_id": hits[0]["id"], "match": "exact"})
            used_sf_ids.add(hits[0]["id"])
            continue
        if len(hits) > 1:
            ambiguous.append({
                **entry,
                "reason": "multiple_exact_url",
                "candidates": [h["id"] for h in hits],
            })
            continue

        # 2. normalized URL
        n = normalize_url(cand_url)
        hits = [h for h in by_norm.get(n, []) if h["id"] not in used_sf_ids]
        if n and len(hits) == 1:
            normalized.append({
                **entry,
                "source_file_id": hits[0]["id"],
                "match": "normalized_url",
                "production_url": hits[0].get("url"),
            })
            used_sf_ids.add(hits[0]["id"])
            continue
        if n and len(hits) > 1:
            ambiguous.append({
                **entry,
                "reason": "multiple_normalized_url",
                "candidates": [h["id"] for h in hits],
            })
            continue

        # 3. DVIDS id
        did = extract_dvids_id(cand_url, rec.metadata)
        if did and len(by_dvids.get(did, [])) == 1:
            hits = [h for h in by_dvids[did] if h["id"] not in used_sf_ids]
            if len(hits) == 1:
                normalized.append({
                    **entry,
                    "source_file_id": hits[0]["id"],
                    "match": "dvids_id",
                    "dvids_video_id": did,
                    "production_url": hits[0].get("url"),
                })
                used_sf_ids.add(hits[0]["id"])
                continue
        if did and len(by_dvids.get(did, [])) > 1:
            ambiguous.append({
                **entry,
                "reason": "ambiguous_dvids",
                "dvids_video_id": did,
                "candidates": [h["id"] for h in by_dvids[did]],
            })
            continue

        # 4. external_id unique in production
        if rec.external_id and len(by_ext_id.get(rec.external_id, [])) == 1:
            hits = [h for h in by_ext_id[rec.external_id] if h["id"] not in used_sf_ids]
            if len(hits) == 1:
                normalized.append({
                    **entry,
                    "source_file_id": hits[0]["id"],
                    "match": "external_id",
                    "production_url": hits[0].get("url"),
                })
                used_sf_ids.add(hits[0]["id"])
                continue
        if rec.external_id and len(by_ext_id.get(rec.external_id, [])) > 1:
            ambiguous.append({
                **entry,
                "reason": "ambiguous_external_id",
                "candidates": [
                    {"id": h["id"], "url": h.get("url")}
                    for h in by_ext_id[rec.external_id]
                ],
            })
            continue

        # 5. basename — only if unique across production AND unique among unused
        b = basename_key(cand_url, rec.title)
        hits = [h for h in by_base.get(b, []) if h["id"] not in used_sf_ids]
        if b and len(by_base.get(b, [])) == 1 and len(hits) == 1:
            normalized.append({
                **entry,
                "source_file_id": hits[0]["id"],
                "match": "normalized_basename",
                "production_url": hits[0].get("url"),
            })
            used_sf_ids.add(hits[0]["id"])
            continue
        if b and len(hits) > 1:
            ambiguous.append({
                **entry,
                "reason": "ambiguous_basename",
                "basename": b,
                "candidates": [
                    {"id": h["id"], "url": h.get("url"), "filename": h.get("filename")}
                    for h in hits
                ],
            })
            continue

        missing_locally.append(entry)

    local_only = [
        {
            "source_file_id": sf["id"],
            "url": sf.get("url"),
            "filename": sf.get("filename"),
            "file_type": sf.get("file_type"),
            "agency": sf.get("agency"),
        }
        for sf in production
        if sf["id"] not in used_sf_ids
    ]

    return {
        "exact": exact,
        "normalized": normalized,
        "ambiguous": ambiguous,
        "missing_locally": missing_locally,
        "local_only": local_only,
        "canonical_count": len(canonical),
        "production_count": len(production),
    }


def record_to_row(rec: Any) -> dict[str, Any]:
    row = rec.to_row()
    # ensure JSON-serializable metadata
    row["first_seen_at"] = datetime.now(timezone.utc).isoformat()
    row["last_seen_at"] = datetime.now(timezone.utc).isoformat()
    row["status"] = row.get("status") or "active"
    return row


def apply_links(
    sb,
    canonical: list[Any],
    result: dict[str, Any],
    *,
    link_incidents: bool = True,
) -> dict[str, int]:
    """Upsert source_records for matched + missing, link matched source_files."""
    writes = {
        "source_records_upserted": 0,
        "source_files_linked": 0,
        "incident_sources_created": 0,
    }

    matches = {m["identity_key"]: m for m in result["exact"] + result["normalized"]}
    # Also upsert missing_locally as discovered-but-not-downloaded
    to_upsert = []
    rec_by_key = {r.identity_key: r for r in canonical}
    for key, rec in rec_by_key.items():
        to_upsert.append(record_to_row(rec))

    # upsert in batches
    for i in range(0, len(to_upsert), 50):
        batch = to_upsert[i : i + 50]
        sb.table("source_records").upsert(
            batch, on_conflict="provider,identity_key"
        ).execute()
        writes["source_records_upserted"] += len(batch)

    # fetch ids for identity keys
    keys = list(rec_by_key.keys())
    id_map: dict[str, str] = {}
    for i in range(0, len(keys), 50):
        chunk = keys[i : i + 50]
        resp = (
            sb.table("source_records")
            .select("id,identity_key")
            .eq("provider", "pursue")
            .in_("identity_key", chunk)
            .execute()
        )
        for row in resp.data or []:
            id_map[row["identity_key"]] = row["id"]

    for key, m in matches.items():
        sr_id = id_map.get(key)
        sf_id = m.get("source_file_id")
        if not sr_id or not sf_id:
            continue
        sb.table("source_files").update({"source_record_id": sr_id}).eq(
            "id", sf_id
        ).execute()
        writes["source_files_linked"] += 1

        if link_incidents:
            incs = (
                sb.table("incidents")
                .select("id")
                .eq("source_file_id", sf_id)
                .execute()
            )
            for inc in incs.data or []:
                try:
                    sb.table("incident_sources").upsert(
                        {
                            "incident_id": inc["id"],
                            "source_record_id": sr_id,
                            "source_file_id": sf_id,
                            "role": "primary",
                            "confidence": "exact"
                            if m.get("match") == "exact"
                            else "normalized",
                        },
                        on_conflict="incident_id,source_record_id",
                    ).execute()
                    writes["incident_sources_created"] += 1
                except Exception as e:
                    logger.warning("incident_sources upsert failed: %s", e)

    return writes


def print_summary(result: dict[str, Any], writes: int) -> None:
    print()
    print("PURSUE R01 RECONCILIATION")
    print()
    print(f"canonical records:     {result['canonical_count']}")
    print(f"production records:    {result['production_count']}")
    print()
    print(f"exact matches:         {len(result['exact'])}")
    print(f"normalized matches:    {len(result['normalized'])}")
    print(f"missing locally:       {len(result['missing_locally'])}")
    print(f"local-only:            {len(result['local_only'])}")
    print(f"ambiguous:             {len(result['ambiguous'])}")
    print()
    print(f"writes:                {writes}")
    print()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reconcile official vs production sources")
    parser.add_argument("--provider", default="pursue", choices=["pursue"])
    parser.add_argument("--release", type=int, default=1)
    parser.add_argument("--snapshot", type=Path, help="Snapshot dir with uap-data.csv")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write source_records + links (disables dry-run)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.apply:
        args.dry_run = False

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    import os

    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

    canonical = load_canonical(args.release, args.snapshot)
    sb = get_supabase()
    production = fetch_production_source_files(sb)
    result = match_records(canonical, production)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / f"r{args.release:02d}_reconciliation.json"
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider": args.provider,
        "release": args.release,
        "dry_run": args.dry_run,
        "summary": {
            "canonical": result["canonical_count"],
            "production": result["production_count"],
            "exact": len(result["exact"]),
            "normalized": len(result["normalized"]),
            "missing_locally": len(result["missing_locally"]),
            "local_only": len(result["local_only"]),
            "ambiguous": len(result["ambiguous"]),
        },
        **{k: result[k] for k in (
            "exact", "normalized", "ambiguous", "missing_locally", "local_only"
        )},
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    logger.info("wrote %s", report_path)

    writes = 0
    if not args.dry_run:
        if result["ambiguous"]:
            logger.error(
                "Refusing --apply with %d ambiguous mappings. Resolve report first.",
                len(result["ambiguous"]),
            )
            print_summary(result, 0)
            return 2
        w = apply_links(sb, canonical, result)
        writes = sum(w.values())
        report["writes"] = w
        report["dry_run"] = False
        report_path.write_text(json.dumps(report, indent=2) + "\n")
        print("apply writes:", json.dumps(w, indent=2))

    print_summary(result, writes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
