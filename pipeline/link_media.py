"""ufodossier // link AARO mission report PDFs to sibling image/video files

Matches source files that share the same DOW-UAP case identifier pattern
(e.g. DOW-UAP-D6) and links image_url / video_url on incidents extracted
from the PDF to the sibling media files.

Usage:
    python -m pipeline.link_media [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import logging
import re
from collections import defaultdict

from pipeline.db import get_supabase

logger = logging.getLogger(__name__)

# Matches patterns like DOW-UAP-D6, DOW-UAP-A12, etc.
CASE_ID_RE = re.compile(r"DOW-UAP-[A-Z]\d+", re.IGNORECASE)


def extract_case_identifier(filename: str) -> str | None:
    """Extract the DOW-UAP case identifier from a filename."""
    m = CASE_ID_RE.search(filename)
    return m.group(0).upper() if m else None


def main():
    parser = argparse.ArgumentParser(description="Link AARO media to incidents")
    parser.add_argument("--dry-run", action="store_true", help="Log actions without writing")
    parser.add_argument("--limit", type=int, default=0, help="Max groups to process (0 = all)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    sb = get_supabase()

    # 1. Fetch all source files
    result = sb.table("source_files").select("id, filename, file_type, url, storage_path").execute()
    all_files = result.data or []
    logger.info("Loaded %d source files", len(all_files))

    # 2. Group by case identifier
    groups: dict[str, list[dict]] = defaultdict(list)
    for sf in all_files:
        case_id = extract_case_identifier(sf["filename"])
        if case_id:
            groups[case_id].append(sf)

    logger.info("Found %d DOW-UAP case groups", len(groups))

    # 3. Process each group
    linked = 0
    processed_groups = 0
    for case_key, files in sorted(groups.items()):
        if args.limit > 0 and processed_groups >= args.limit:
            break

        # Separate PDFs from media files
        pdfs = [f for f in files if f["file_type"] == "pdf"]
        images = [f for f in files if f["file_type"] in ("jpg", "jpeg", "png", "webp")]
        videos = [f for f in files if f["file_type"] in ("mp4", "mov", "avi")]

        if not pdfs or (not images and not videos):
            continue

        processed_groups += 1
        logger.info("Group %s: %d PDFs, %d images, %d videos", case_key, len(pdfs), len(images), len(videos))

        # Get the public URL for the first image/video sibling
        image_url = images[0]["url"] if images else None
        video_url = videos[0]["url"] if videos else None

        # Find incidents from the PDF source files in this group
        for pdf in pdfs:
            inc_result = sb.table("incidents").select("id, image_url, video_url").eq("source_file_id", pdf["id"]).execute()
            incidents = inc_result.data or []

            for inc in incidents:
                updates: dict[str, str] = {}
                if image_url and not inc.get("image_url"):
                    updates["image_url"] = image_url
                if video_url and not inc.get("video_url"):
                    updates["video_url"] = video_url

                if updates:
                    if args.dry_run:
                        logger.info("  [DRY RUN] Would update incident %s with %s", inc["id"], updates)
                    else:
                        sb.table("incidents").update(updates).eq("id", inc["id"]).execute()
                        logger.info("  Updated incident %s: %s", inc["id"], list(updates.keys()))
                    linked += 1

    logger.info("Linked media to %d incidents across %d groups", linked, processed_groups)


if __name__ == "__main__":
    main()
