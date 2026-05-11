"""ufodossier // render page 1 of each source PDF as a cover image JPEG

Renders page 1 of PDF source files as 1200px-wide JPEG covers and uploads
them to Supabase Storage. Can read PDFs from Supabase Storage (if uploaded)
or from a local directory (for files too large to upload).

Usage:
    python -m pipeline.render_pdf_covers [--dry-run] [--limit N] [--force]
    python -m pipeline.render_pdf_covers --local-dir ./pursue-ufo-files/pdfs
"""
from __future__ import annotations

import argparse
import hashlib
import io
import logging
import os
from pathlib import Path

from pdf2image import convert_from_bytes
from PIL import Image

from pipeline.db import get_supabase
from pipeline.storage import upload_to_storage, download_from_storage

logger = logging.getLogger(__name__)

BUCKET = "source-files"
COVER_PREFIX = "covers"
JPEG_QUALITY = 80
RENDER_WIDTH = 1200
DPI = 150


def render_cover(pdf_bytes: bytes) -> bytes:
    """Render page 1 of a PDF as a JPEG, 1200px wide."""
    pages = convert_from_bytes(
        pdf_bytes, first_page=1, last_page=1, dpi=DPI, size=(RENDER_WIDTH, None)
    )
    img = pages[0]
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


def _normalize_name(name: str) -> str:
    """Normalize a filename for fuzzy matching.

    Collapses spaces, hyphens, underscores, and commas to a single canonical
    form, strips the .pdf extension, and lowercases everything.
    """
    import re
    n = name.lower()
    if n.endswith(".pdf"):
        n = n[:-4]
    n = re.sub(r"[\s_,\-]+", "-", n)
    return n


def _tokenize_name(name: str) -> set[str]:
    """Extract alphanumeric tokens >= 2 chars for fuzzy matching."""
    import re
    n = name.lower()
    if n.endswith(".pdf"):
        n = n[:-4]
    stop = {"the", "and", "for", "pdf", "of", "in", "at", "to", "report", "mission"}
    tokens = set(re.findall(r"[a-z0-9]+", n))
    return {t for t in tokens if len(t) >= 2 and t not in stop}


def _find_local_file(pdf_dir: Path, filename: str) -> Path | None:
    """Find a local file matching the source_file filename.

    Tries exact match, then case-insensitive, then with/without .pdf extension,
    then normalized matching, then token-overlap matching as last resort.
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

    # Normalized matching: collapse spaces/hyphens/underscores
    norm = _normalize_name(filename)
    for p in pdf_dir.iterdir():
        if p.is_file() and p.suffix.lower() == ".pdf":
            if _normalize_name(p.name) == norm:
                return p

    # Token-overlap matching: find best match by shared tokens
    db_tokens = _tokenize_name(filename)
    if len(db_tokens) < 2:
        return None

    # Extract document identifiers (e.g. "d20", "pr20", "serial_153", "vm6")
    # These MUST match to avoid cross-linking different documents.
    import re as _re
    id_pattern = _re.compile(
        r"(?:serial[_\s-]*(\d+))|"       # serial_153 -> 153
        r"(?:(?:d|pr|vm)(\d+))|"          # d20, pr20, vm6
        r"(?:cable[_\s-]*(\d+))",         # cable 2 -> 2
        _re.IGNORECASE,
    )
    db_ids = set()
    for m in id_pattern.finditer(filename.lower()):
        db_ids.update(g for g in m.groups() if g)

    best_path = None
    best_score = 0.0
    for p in pdf_dir.iterdir():
        if not p.is_file() or p.suffix.lower() != ".pdf":
            continue
        local_tokens = _tokenize_name(p.name)
        if not local_tokens:
            continue

        # If DB filename has document IDs, require them in the local file too
        if db_ids:
            local_ids = set()
            for m in id_pattern.finditer(p.name.lower()):
                local_ids.update(g for g in m.groups() if g)
            if not db_ids & local_ids:
                continue

        overlap = len(db_tokens & local_tokens)
        # Jaccard-like score: overlap / max(len) to favor precise matches
        score = overlap / max(len(db_tokens), len(local_tokens))
        if overlap >= 3 and score > best_score:
            best_score = score
            best_path = p

    if best_path and best_score >= 0.5:
        logger.info("  Fuzzy matched %s -> %s (score=%.2f)", filename, best_path.name, best_score)
        return best_path

    return None


def main():
    parser = argparse.ArgumentParser(description="Render PDF page-1 covers")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without writing")
    parser.add_argument("--limit", type=int, default=0, help="Max files to process (0 = all)")
    parser.add_argument("--force", action="store_true", help="Re-render even if cover already set")
    parser.add_argument("--local-dir", type=str, default=None,
                        help="Path to local folder of PDFs (fallback when not in Storage)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sb = get_supabase()
    supabase_url = os.environ["SUPABASE_URL"]
    local_dir = Path(args.local_dir) if args.local_dir else None

    # 1. Find PDF source files needing covers
    query = (
        sb.table("source_files")
        .select("id, filename, storage_path, cover_image_url")
        .eq("file_type", "pdf")
    )
    if not args.force:
        query = query.is_("cover_image_url", "null")

    result = query.execute()
    files = result.data or []

    if args.limit > 0:
        files = files[: args.limit]

    logger.info("Found %d PDF source files to render covers for", len(files))

    rendered = 0
    skipped = 0
    errors = 0
    for sf in files:
        logger.info("Processing %s (%s)", sf["filename"], sf["id"])
        try:
            pdf_bytes = None

            # Try Supabase Storage first
            if sf.get("storage_path"):
                try:
                    pdf_bytes = download_from_storage(BUCKET, sf["storage_path"])
                except Exception as e:
                    logger.warning("  Storage download failed: %s", e)

            # Fall back to local directory
            if pdf_bytes is None and local_dir:
                local_path = _find_local_file(local_dir, sf["filename"])
                if local_path:
                    pdf_bytes = local_path.read_bytes()
                    logger.info("  Using local file: %s", local_path.name)

            if pdf_bytes is None:
                logger.warning("  SKIP: no storage_path and no local file for %s", sf["filename"])
                skipped += 1
                continue

            # Render page 1
            jpeg_bytes = render_cover(pdf_bytes)

            # Compute hash for dedup
            sha = hashlib.sha256(jpeg_bytes).hexdigest()
            cover_path = f"{COVER_PREFIX}/{sha}.jpg"
            public_url = f"{supabase_url}/storage/v1/object/public/{BUCKET}/{cover_path}"

            if args.dry_run:
                logger.info("  [DRY RUN] Would upload %s and set cover_image_url", cover_path)
            else:
                upload_to_storage(
                    bucket=BUCKET, path=cover_path, data=jpeg_bytes,
                    content_type="image/jpeg",
                )
                sb.table("source_files").update({"cover_image_url": public_url}).eq("id", sf["id"]).execute()
                logger.info("  Uploaded cover -> %s", cover_path)

            rendered += 1
        except Exception:
            logger.exception("  Failed to render cover for %s", sf["filename"])
            errors += 1

    logger.info("Rendered %d covers (%d skipped, %d errors)", rendered, skipped, errors)

    # 2. Propagate covers to incidents
    logger.info("Propagating cover_image_url to incidents...")
    incidents_query = sb.table("incidents").select("id, source_file_id, cover_image_url").is_("cover_image_url", "null")
    inc_result = incidents_query.execute()
    incidents = inc_result.data or []

    # Build source_file_id -> cover_image_url map
    all_sf = sb.table("source_files").select("id, cover_image_url").not_.is_("cover_image_url", "null").execute()
    sf_covers = {row["id"]: row["cover_image_url"] for row in (all_sf.data or [])}

    propagated = 0
    for inc in incidents:
        cover = sf_covers.get(inc["source_file_id"])
        if cover:
            if args.dry_run:
                logger.info("  [DRY RUN] Would set cover for incident %s", inc["id"])
            else:
                sb.table("incidents").update({"cover_image_url": cover}).eq("id", inc["id"]).execute()
            propagated += 1

    logger.info("Propagated cover to %d incidents", propagated)


if __name__ == "__main__":
    main()
