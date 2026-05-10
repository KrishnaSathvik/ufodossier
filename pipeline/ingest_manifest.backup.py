"""
ufodossier // ingest_manifest

Replaces the original scrape.py. war.gov/UFO is a JavaScript-rendered SPA
that doesn't expose file URLs to a static HTTP fetch, so we instead pull
the file inventory from a community-maintained mirror:

    https://github.com/DenisSergeevitch/UFO-USA

That repo includes metadata/uap-csv.csv listing every file in Release 01
(162 rows: 120 PDFs, 28 videos, 14 images) with the original war.gov URLs.
We use that as our manifest, then download files directly from war.gov so
that storage paths in our DB still trace back to primary sources.

Usage:
    python -m pipeline.ingest_manifest --tranche 1
    python -m pipeline.ingest_manifest --tranche 1 --limit 5  # smoke test
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import logging
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx

from pipeline.db import get_supabase, upsert_release, upsert_source_file
from pipeline.storage import upload_to_storage

# canonical manifest URLs (raw github so we get the CSV, not HTML)
MANIFEST_URL = "https://raw.githubusercontent.com/DenisSergeevitch/UFO-USA/main/metadata/uap-csv.csv"

USER_AGENT = "ufodossier-bot/1.0 (+https://ufodossier.com/methodology)"

CACHE_DIR = Path("./.cache/files")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)


def fetch_manifest() -> list[dict]:
    """Download the UFO-USA manifest CSV and parse to dicts."""
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True) as client:
        r = client.get(MANIFEST_URL)
        r.raise_for_status()
        text = r.text

    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    logger.info("manifest loaded: %d rows", len(rows))
    return rows


def normalize_row(row: dict) -> dict | None:
    """
    Map manifest CSV row to our internal shape.
    The manifest schema has evolved; we look for likely column names.
    Returns None if the row isn't useful (missing URL, etc.)
    """
    url = (
        row.get("source_url")
        or row.get("url")
        or row.get("URL")
        or row.get("File URL")
        or ""
    ).strip()
    if not url or not url.startswith("http"):
        return None

    filename = (
        row.get("source_file")
        or row.get("filename")
        or row.get("File")
        or Path(urlparse(url).path).name
    ).strip()

    asset_type = (row.get("asset_type") or row.get("type") or "").lower().strip()
    ext = Path(urlparse(url).path).suffix.lower().lstrip(".")
    file_type = {
        "jpeg": "jpg", "mov": "mp4",
    }.get(ext, ext) or asset_type

    # crude agency hint
    agency_hint = (row.get("agency") or "").upper().strip()
    if not agency_hint:
        ctx = (filename + " " + url).lower()
        for needle, label in (
            ("fbi", "FBI"),
            ("nasa", "NASA"),
            ("apollo", "NASA"),
            ("state", "DOS"),
            ("indopacom", "DoD"),
            ("northcom", "DoD"),
            ("centcom", "DoD"),
            ("eucom", "DoD"),
            ("aaro", "DoD"),
            ("dow-uap", "DoD"),
            ("dod", "DoD"),
        ):
            if needle in ctx:
                agency_hint = label
                break

    return {
        "url": url,
        "filename": filename,
        "file_type": file_type or "pdf",
        "agency": agency_hint or None,
        "title": (row.get("title") or row.get("Title") or "").strip() or None,
        "incident_date_hint": (row.get("incident_date") or row.get("Incident Date") or "").strip() or None,
        "incident_location_hint": (row.get("incident_location") or row.get("Incident Location") or "").strip() or None,
    }


def download_file(url: str) -> tuple[bytes, str]:
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=180.0, follow_redirects=True) as client:
        r = client.get(url)
        r.raise_for_status()
        content = r.content
    sha = hashlib.sha256(content).hexdigest()
    return content, sha


def run(tranche: int, limit: int | None = None, dry_run: bool = False, pdf_only: bool = True) -> None:
    sb = get_supabase()
    release = upsert_release(sb, tranche_number=tranche, captured_at=datetime.now(timezone.utc))
    logger.info("release id=%s tranche=%d", release["id"], tranche)

    manifest = fetch_manifest()
    rows: list[dict] = []
    for raw in manifest:
        n = normalize_row(raw)
        if n is None:
            continue
        if pdf_only and n["file_type"] != "pdf":
            continue
        rows.append(n)

    logger.info("ingesting %d files (pdf_only=%s)", len(rows), pdf_only)
    if limit:
        rows = rows[:limit]
        logger.info("LIMIT applied: %d", limit)

    new_count = skipped_count = error_count = 0

    for f in rows:
        try:
            existing = sb.table("source_files").select("id").eq("url", f["url"]).execute()
            if existing.data:
                skipped_count += 1
                continue

            logger.info("downloading %s", f["url"])
            content, sha = download_file(f["url"])

            local_path = CACHE_DIR / f"{sha}_{f['filename']}"
            local_path.write_bytes(content)

            if not dry_run:
                storage_path = upload_to_storage(
                    bucket="source-files",
                    path=f"{sha}/{f['filename']}",
                    data=content,
                    content_type=_content_type(f["file_type"]),
                )
                upsert_source_file(
                    sb,
                    release_id=release["id"],
                    url=f["url"],
                    filename=f["filename"],
                    file_type=f["file_type"],
                    agency=f["agency"],
                    sha256=sha,
                    storage_path=storage_path,
                    byte_size=len(content),
                )
            new_count += 1
        except Exception as e:
            logger.exception("failed on %s: %s", f["url"], e)
            error_count += 1

    logger.info(
        "ingest complete // new=%d skipped=%d errors=%d",
        new_count, skipped_count, error_count,
    )

    if not dry_run:
        sb.table("releases").update({
            "file_count": new_count + skipped_count,
        }).eq("id", release["id"]).execute()


def _content_type(file_type: str) -> str:
    return {
        "pdf": "application/pdf",
        "mp4": "video/mp4",
        "jpg": "image/jpeg",
        "png": "image/png",
    }.get(file_type, "application/octet-stream")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--tranche", type=int, default=1)
    parser.add_argument("--limit", type=int, help="cap files for smoke testing")
    parser.add_argument("--include-non-pdf", action="store_true",
                        help="also download videos and images (slow, large)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(
        tranche=args.tranche,
        limit=args.limit,
        dry_run=args.dry_run,
        pdf_only=not args.include_non_pdf,
    )
