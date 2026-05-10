"""
ufodossier // ingest_slideshow

Downloads the 17 curated evidence photos from the war.gov/UFO homepage
slideshow carousel, registers them in source_files, and links them to
matching incidents via token overlap.

These images are at /portals/1/Interactive/2026/UFO/Slideshow/ — a different
path than the /MediaLink/ URLs (which 403). They were scraped via Playwright.

Usage:
    python -m pipeline.ingest_slideshow
    python -m pipeline.ingest_slideshow --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import re
from pathlib import Path

import httpx

from pipeline.db import get_supabase, upsert_source_file_safe
from pipeline.storage import upload_to_storage

logger = logging.getLogger(__name__)

USER_AGENT = "ufodossier-bot/1.0 (+https://ufodossier.com/methodology)"
CACHE_DIR = Path("./.cache/slideshow")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# 17 slideshow images scraped from war.gov/UFO carousel via Playwright
SLIDESHOW_IMAGES = [
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/FBI-Photo-1.jpg",
        "filename": "FBI-Photo-1.jpg",
        "alt_text": "Infrared still image (black hot) captured of unidentified object over western United States in December of 2025.",
        "agency": "FBI",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/FBI-Photo-A5.jpg",
        "filename": "FBI-Photo-A5.jpg",
        "alt_text": "Infrared still image (black hot) captured of unidentified object over western United States in December of 2025.",
        "agency": "FBI",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/FBI-Photo-B2.jpg",
        "filename": "FBI-Photo-B2.jpg",
        "alt_text": "Infrared still image (black hot) captured of unidentified object over western United States in September of 2025.",
        "agency": "FBI",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/FBI-Photo-B7-.jpg",
        "filename": "FBI-Photo-B7-.jpg",
        "alt_text": "nfrared still image (black hot) captured of unidentified object below helicopter over western United States in September of 2025.",
        "agency": "FBI",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/FBI-Photo-B18.jpg",
        "filename": "FBI-Photo-B18.jpg",
        "alt_text": "Infrared still image (black hot) captured of unidentified object(s) over western United States in September of 2025.",
        "agency": "FBI",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/FBI-Photo-B20.jpg",
        "filename": "FBI-Photo-B20.jpg",
        "alt_text": "Infrared still image (black hot) captured of unidentified object(s) over western United States in September of 2025.",
        "agency": "FBI",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/2024-04-30-Composite-Sketch.jpg",
        "filename": "2024-04-30-Composite-Sketch.jpg",
        "alt_text": "Recreation of potential anomalous sighting in southeastern United States in September of 2023.",
        "agency": "FBI",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/NASA-UAP-VM6-Apollo-17-1972.jpg",
        "filename": "NASA-UAP-VM6-Apollo-17-1972.jpg",
        "alt_text": "Archival imagery from the Apollo 17 mission to the Moon. The yellow box contains an enlarged area of the original photo in which three lights are visible above the lunar terrain.",
        "agency": "NASA",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/DOW-UAP-PR19-Unresolved-UAP-Report-Middle-East-May-2022.jpg",
        "filename": "DOW-UAP-PR19-Unresolved-UAP-Report-Middle-East-May-2022.jpg",
        "alt_text": "Still from a video that a U.S. military operator reported as featuring UAP flying across their screen.",
        "agency": "DoD",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/DOW-UAP-PR26-Unresolved-UAP-Report-United-Arab-Emirates-October-2023.jpg",
        "filename": "DOW-UAP-PR26-Unresolved-UAP-Report-United-Arab-Emirates-October-2023.jpg",
        "alt_text": "Still from a video captured near the United Arab Emirates featuring reported UAP.",
        "agency": "DoD",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/DOW-UAP-PR34-Unresolved-UAP-Report-Greece-October-2023.jpg",
        "filename": "DOW-UAP-PR34-Unresolved-UAP-Report-Greece-October-2023.jpg",
        "alt_text": "Aqua-colored scope lines are shown over a gray background, with a scattering of clouds and black squares and rectangles.",
        "agency": "DoD",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/DOW-UAP-PR35-Unresolved-UAP-Report-Greece-October-2023.jpg",
        "filename": "DOW-UAP-PR35-Unresolved-UAP-Report-Greece-October-2023.jpg",
        "alt_text": "A U.S. military operator reported UAP near Greece flying straight above the ocean towards land.",
        "agency": "DoD",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/DOW-UAP-PR38-Unresolved-UAP-Report-Middle-East-2013.jpg",
        "filename": "DOW-UAP-PR38-Unresolved-UAP-Report-Middle-East-2013.jpg",
        "alt_text": "Still from a video featuring an eight-pointed area of contrast captured via infrared sensor.",
        "agency": "DoD",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/DOW-UAP-PR43-Unresolved-UAP-Report-Africa-2025.jpg",
        "filename": "DOW-UAP-PR43-Unresolved-UAP-Report-Africa-2025.jpg",
        "alt_text": "A U.S. military operator reported UAP while operating within African airspace.",
        "agency": "DoD",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/DOW-UAP-PR45-Unresolved-UAP-Report-Middle-East-2020.jpg",
        "filename": "DOW-UAP-PR45-Unresolved-UAP-Report-Middle-East-2020.jpg",
        "alt_text": "In 2020, the U.S. Air Force reported UAP in the southern United States.",
        "agency": "DoD",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/DOW-UAP-PR46-Unresolved-UAP-Report-INDOPACOM-2024.jpg",
        "filename": "DOW-UAP-PR46-Unresolved-UAP-Report-INDOPACOM-2024.jpg",
        "alt_text": "U.S. Indo-Pacific Command reported UAP that resembles a football-shaped body near Japan.",
        "agency": "DoD",
    },
    {
        "url": "https://www.war.gov/portals/1/Interactive/2026/UFO/Slideshow/DOW-UAP-PR49-Unresolved-UAP-Report-Department-of-the-Army-2026.jpg",
        "filename": "DOW-UAP-PR49-Unresolved-UAP-Report-Department-of-the-Army-2026.jpg",
        "alt_text": "The U.S. Army reported UAP in North America in 2026.",
        "agency": "DoD",
    },
]


def _tokenize(text: str, min_len: int = 2) -> set[str]:
    """Extract alphanumeric tokens for matching (mirrors extract._tokenize)."""
    stop = {
        "the", "and", "for", "from", "pdf", "jpg", "png", "mp4", "mov", "release",
        "https", "http", "www", "gov", "war", "com", "medialink", "ufo", "release_1",
        "unresolved", "uap", "report",
    }
    tokens = set(re.findall(r"[A-Za-z0-9]+", text.lower()))
    return {t for t in tokens if len(t) >= min_len and t not in stop}


def run(dry_run: bool = False) -> None:
    sb = get_supabase()

    downloaded = 0
    registered = 0
    linked = 0

    for img in SLIDESHOW_IMAGES:
        # Check if already registered
        existing = sb.table("source_files").select("id").eq("url", img["url"]).execute()
        if existing.data:
            logger.info("skip %s: already registered", img["filename"])
            continue

        # Try downloading
        content = None
        sha = None
        storage_path = None
        try:
            with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=60.0, follow_redirects=True) as client:
                r = client.get(img["url"])
                r.raise_for_status()
                content = r.content
            sha = hashlib.sha256(content).hexdigest()
            downloaded += 1
            logger.info("downloaded %s (%d bytes)", img["filename"], len(content))
        except Exception as e:
            logger.warning("download failed (%s) for %s, registering metadata only", e.__class__.__name__, img["filename"])
            sha = hashlib.sha256(img["url"].encode()).hexdigest()

        if content is not None:
            local_path = CACHE_DIR / f"{sha}_{img['filename']}"
            local_path.write_bytes(content)
            if not dry_run:
                storage_path = upload_to_storage(
                    bucket="source-files",
                    path=f"slideshow/{sha}/{img['filename']}",
                    data=content,
                    content_type="image/jpeg",
                )

        if not dry_run:
            upsert_source_file_safe(
                sb,
                url=img["url"],
                filename=img["filename"],
                file_type="jpg",
                agency=img["agency"],
                sha256=sha,
                storage_path=storage_path,
                byte_size=len(content) if content else None,
            )
        registered += 1
        logger.info("registered %s", img["filename"])

    logger.info("slideshow ingest // downloaded=%d registered=%d", downloaded, registered)

    # Link slideshow images to incidents via token matching
    logger.info("linking slideshow images to incidents...")
    incidents = sb.table("incidents").select("id, case_id, source_file_id, image_url").execute().data

    # Build source_file lookup for incident token matching
    sf_ids = list({i["source_file_id"] for i in incidents if i["source_file_id"]})
    sf_lookup: dict[str, dict] = {}
    for batch_start in range(0, len(sf_ids), 50):
        batch = sf_ids[batch_start:batch_start + 50]
        rows = sb.table("source_files").select("id, filename, url").in_("id", batch).execute().data
        for r in rows:
            sf_lookup[r["id"]] = {"filename": r["filename"], "url": r.get("url", "")}

    for img in SLIDESHOW_IMAGES:
        img_tokens = _tokenize(img["filename"])
        if len(img_tokens) < 2:
            continue

        best_match = None
        best_overlap = 0

        for inc in incidents:
            sf_info = sf_lookup.get(inc["source_file_id"], {"filename": "", "url": ""})
            inc_tokens = _tokenize(sf_info["filename"]) | _tokenize(sf_info["url"])
            overlap = len(img_tokens & inc_tokens)
            if overlap > best_overlap and overlap >= 3:
                best_overlap = overlap
                best_match = inc

        if best_match:
            if not dry_run and not best_match.get("image_url"):
                sb.table("incidents").update({"image_url": img["url"]}).eq("id", best_match["id"]).execute()
            logger.info("linked %s -> %s (overlap=%d tokens)", img["filename"], best_match["case_id"], best_overlap)
            linked += 1
        else:
            logger.info("no match for %s (tokens=%s)", img["filename"], sorted(img_tokens)[:8])

    logger.info("slideshow link // linked=%d of %d images", linked, len(SLIDESHOW_IMAGES))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="log actions without writing to DB or storage")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
