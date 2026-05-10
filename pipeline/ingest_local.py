"""
ufodossier // ingest_local

Ingest Release 01 PDFs from a local folder into Supabase Storage and
source_files table. This replaces ingest_manifest.py for Release 01 since
war.gov 403s automated downloads. The PDFs must be downloaded manually
through a browser first.

The war.gov URL is kept as source_files.url (canonical citation) even
though the bytes come from the local folder.

Usage:
    python -m pipeline.ingest_local --tranche 1 --pdf-dir ./release01_pdfs
    python -m pipeline.ingest_local --tranche 1 --dry-run
    python -m pipeline.ingest_local --tranche 1 --limit 5
"""
from __future__ import annotations

import argparse
import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path

from pipeline.db import get_supabase, upsert_release, upsert_source_file
from pipeline.ingest_manifest import fetch_manifest, normalize_row, load_supplementary
from pipeline.storage import upload_to_storage

logger = logging.getLogger(__name__)


def _content_type(file_type: str) -> str:
    return {
        "pdf": "application/pdf",
        "mp4": "video/mp4",
        "jpg": "image/jpeg",
        "png": "image/png",
    }.get(file_type, "application/octet-stream")


def _find_local_file(pdf_dir: Path, filename: str) -> Path | None:
    """Find a local file matching the manifest filename.

    Tries exact match first, then case-insensitive, then with/without
    the .pdf extension appended.
    """
    # Exact match
    candidate = pdf_dir / filename
    if candidate.is_file():
        return candidate

    # With .pdf extension
    if not filename.lower().endswith(".pdf"):
        candidate = pdf_dir / (filename + ".pdf")
        if candidate.is_file():
            return candidate

    # Case-insensitive search
    lower = filename.lower()
    lower_pdf = lower if lower.endswith(".pdf") else lower + ".pdf"
    for p in pdf_dir.iterdir():
        if p.is_file() and p.name.lower() in (lower, lower_pdf):
            return p

    return None


def run(
    tranche: int,
    pdf_dir: Path,
    limit: int | None = None,
    dry_run: bool = False,
    pdf_only: bool = True,
    update_existing: bool = False,
) -> None:
    sb = get_supabase()
    release = upsert_release(sb, tranche_number=tranche, captured_at=datetime.now(timezone.utc))
    logger.info("release id=%s tranche=%d", release["id"], tranche)

    if not pdf_dir.is_dir():
        logger.error("PDF directory does not exist: %s", pdf_dir)
        return

    local_files = list(pdf_dir.iterdir())
    logger.info("Local folder %s contains %d files", pdf_dir, len([f for f in local_files if f.is_file()]))

    # Build manifest from UFO-USA CSV + supplementary records
    manifest = fetch_manifest()
    rows: list[dict] = []
    seen_urls: set[str] = set()
    for raw in manifest:
        n = normalize_row(raw)
        if n is None:
            continue
        if pdf_only and n["file_type"] != "pdf":
            continue
        rows.append(n)
        seen_urls.add(n["url"])

    for supp in load_supplementary():
        if supp["url"] not in seen_urls:
            if pdf_only and supp["file_type"] != "pdf":
                continue
            rows.append(supp)
            seen_urls.add(supp["url"])

    logger.info("Manifest has %d rows (pdf_only=%s)", len(rows), pdf_only)

    if limit:
        rows = rows[:limit]
        logger.info("LIMIT applied: %d", limit)

    ingested = 0
    skipped = 0
    missing = 0
    errors = 0

    for f in rows:
        try:
            # Check if already in DB
            existing = sb.table("source_files").select("id, storage_path").eq("url", f["url"]).execute()
            if existing.data:
                row = existing.data[0]
                if row.get("storage_path") or not update_existing:
                    skipped += 1
                    continue
                # Row exists but has no storage_path — upload and backfill
                local_path = _find_local_file(pdf_dir, f["filename"])
                if local_path is None:
                    logger.warning("MISSING: %s", f["filename"])
                    missing += 1
                    continue
                content = local_path.read_bytes()
                sha = hashlib.sha256(content).hexdigest()
                storage_path = f"{sha}/{f['filename']}"
                logger.info("Backfilling storage for %s (%d bytes)", f["filename"], len(content))
                if not dry_run:
                    upload_to_storage(
                        bucket="source-files",
                        path=storage_path,
                        data=content,
                        content_type=_content_type(f["file_type"]),
                    )
                    sb.table("source_files").update({
                        "storage_path": storage_path,
                        "sha256": sha,
                        "byte_size": len(content),
                    }).eq("id", row["id"]).execute()
                ingested += 1
                continue

            # Find the local file
            local_path = _find_local_file(pdf_dir, f["filename"])
            if local_path is None:
                logger.warning("MISSING: %s", f["filename"])
                missing += 1
                continue

            content = local_path.read_bytes()
            sha = hashlib.sha256(content).hexdigest()
            storage_path = f"{sha}/{f['filename']}"

            logger.info("Ingesting %s (%d bytes, sha=%s…)", f["filename"], len(content), sha[:12])

            if dry_run:
                logger.info("  [DRY RUN] Would upload to %s", storage_path)
            else:
                upload_to_storage(
                    bucket="source-files",
                    path=storage_path,
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

            ingested += 1
        except Exception as e:
            logger.exception("Failed on %s: %s", f["filename"], e)
            errors += 1

    logger.info("--- Ingest complete ---")
    logger.info("  Ingested:  %d", ingested)
    logger.info("  Skipped:   %d (already in DB)", skipped)
    logger.info("  Missing:   %d (not in local folder)", missing)
    logger.info("  Errors:    %d", errors)

    if not dry_run:
        sb.table("releases").update({
            "file_count": ingested + skipped,
        }).eq("id", release["id"]).execute()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Ingest local PDFs into Supabase")
    parser.add_argument("--tranche", type=int, default=1)
    parser.add_argument("--pdf-dir", type=str, default="./release01_pdfs",
                        help="Path to folder of manually downloaded PDFs")
    parser.add_argument("--limit", type=int, help="Cap files for smoke testing")
    parser.add_argument("--include-non-pdf", action="store_true",
                        help="Also ingest videos and images")
    parser.add_argument("--update-existing", action="store_true",
                        help="Upload files for existing DB rows that lack storage_path")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    run(
        tranche=args.tranche,
        pdf_dir=Path(args.pdf_dir),
        limit=args.limit,
        dry_run=args.dry_run,
        pdf_only=not args.include_non_pdf,
        update_existing=args.update_existing,
    )
