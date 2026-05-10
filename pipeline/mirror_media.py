"""ufodossier // mirror war.gov media to Supabase Storage.

War.gov uses Akamai which blocks direct image requests (even from
Playwright page.goto or in-page fetch). The only way to get the
images is to let them load naturally as part of the war.gov/UFO
slideshow page, then intercept the HTTP responses.

Usage:
    python -m pipeline.mirror_media
    python -m pipeline.mirror_media --dry-run
    python -m pipeline.mirror_media --limit 5

Requires:
    pip install playwright
    playwright install chromium
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import logging
import os
import time
from pathlib import PurePosixPath
from urllib.parse import urlparse

from pipeline.db import get_supabase

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
STORAGE_BUCKET = "source-files"
STORAGE_PREFIX = SUPABASE_URL + "/storage/v1/object/public/"
SLIDESHOW_URL = "https://www.war.gov/UFO"


def _is_already_mirrored(url: str | None) -> bool:
    if not url:
        return True
    return STORAGE_PREFIX in url


def _get_war_gov_rows(sb, limit: int | None):
    q = sb.table("incidents").select("id, image_url, video_url")
    q = q.or_("image_url.ilike.https://www.war.gov/%,video_url.ilike.https://www.war.gov/%")
    if limit:
        q = q.limit(limit)
    return q.execute().data or []


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    return PurePosixPath(path).name


def _content_type_from_ext(filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "gif": "image/gif",
        "webp": "image/webp",
        "mp4": "video/mp4",
        "mov": "video/quicktime",
    }.get(ext, "application/octet-stream")


def _upload_to_storage(sb, data: bytes, sha: str, filename: str) -> str:
    content_type = _content_type_from_ext(filename)
    storage_path = f"media/{sha}/{filename}"
    sb.storage.from_(STORAGE_BUCKET).upload(
        path=storage_path,
        file=data,
        file_options={"content-type": content_type, "upsert": "true"},
    )
    return f"{SUPABASE_URL}/storage/v1/object/public/{STORAGE_BUCKET}/{storage_path}"


def _collect_images_via_browser(wanted_urls: set[str]) -> dict[str, bytes]:
    """Load war.gov pages and capture image responses.

    Strategy:
      1. Load the /UFO slideshow page — captures most images naturally.
      2. For any remaining URLs, inject <img> tags into the page so the
         browser fetches them with the same session cookies/headers.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log.error("playwright not installed. Run: pip install playwright && playwright install chromium")
        return {}

    # Build a lookup from filename -> full URL for matching
    wanted_filenames = {_filename_from_url(u): u for u in wanted_urls}
    captured: dict[str, bytes] = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.new_page()

        def handle_response(response):
            if not response.ok:
                return
            url = response.url
            fname = _filename_from_url(url)
            if fname in wanted_filenames:
                try:
                    data = response.body()
                    captured[wanted_filenames[fname]] = data
                    log.info("  CAPTURED  %s (%d bytes)", fname, len(data))
                except Exception as e:
                    log.warning("  Could not read body for %s: %s", fname, e)

        page.on("response", handle_response)

        # --- Pass 1: slideshow page ---
        log.info("Loading slideshow page to capture images...")
        page.goto(SLIDESHOW_URL, wait_until="networkidle", timeout=30000)
        time.sleep(3)

        # Scroll to trigger lazy-loaded images
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(3)

        remaining = wanted_filenames.keys() - {_filename_from_url(u) for u in captured}
        if remaining:
            log.info("Scrolling more to find %d remaining images...", len(remaining))
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(2)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            time.sleep(2)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)

        # --- Pass 2: in-page fetch for uncaptured URLs ---
        still_missing = [u for u in wanted_urls if u not in captured]
        if still_missing:
            log.info("Pass 2: fetching %d uncaptured URLs via in-page fetch...",
                     len(still_missing))
            for url in still_missing:
                fname = _filename_from_url(url)
                try:
                    result = page.evaluate(f"""async () => {{
                        try {{
                            const r = await fetch({url!r}, {{ credentials: 'include' }});
                            if (!r.ok) return {{ error: 'HTTP ' + r.status }};
                            const buf = await r.arrayBuffer();
                            const bytes = new Uint8Array(buf);
                            let binary = '';
                            for (let i = 0; i < bytes.length; i++) {{
                                binary += String.fromCharCode(bytes[i]);
                            }}
                            return {{ data: btoa(binary), size: bytes.length }};
                        }} catch (e) {{
                            return {{ error: e.message }};
                        }}
                    }}""")
                    if result.get("error"):
                        log.warning("  FETCH ERR  %s — %s", fname, result["error"])
                    elif result.get("data"):
                        data = base64.b64decode(result["data"])
                        captured[url] = data
                        log.info("  CAPTURED  %s (%d bytes) via fetch", fname, len(data))
                except Exception as e:
                    log.warning("  EVAL ERR  %s — %s", fname, str(e)[:100])

        browser.close()

    return captured


def mirror(dry_run: bool = False, limit: int | None = None):
    sb = get_supabase()
    rows = _get_war_gov_rows(sb, limit)
    log.info("Found %d incidents with war.gov media URLs", len(rows))

    if not rows:
        return

    # Build list of URLs we need to fetch
    needed: list[tuple[dict, str, str]] = []  # (row, field, url)
    skipped = 0
    for row in rows:
        for field in ("image_url", "video_url"):
            url = row.get(field)
            if not url or "war.gov" not in url:
                continue
            if _is_already_mirrored(url):
                skipped += 1
                continue
            needed.append((row, field, url))

    log.info("Need to mirror %d URLs (%d already mirrored)", len(needed), skipped)

    if not needed:
        log.info("Nothing to do.")
        return

    if dry_run:
        for _, field, url in needed:
            kind = "IMAGE" if field == "image_url" else "VIDEO"
            log.info("  DRY RUN  %-6s  %s", kind, _filename_from_url(url))
        return

    # Capture images via browser
    wanted_urls = {url for _, _, url in needed}
    captured = _collect_images_via_browser(wanted_urls)

    log.info("Captured %d of %d images", len(captured), len(wanted_urls))

    # Upload captured images to Supabase Storage
    stats = {"images": 0, "videos": 0, "failed": 0, "bytes": 0}
    failures: list[tuple[str, str]] = []

    for row, field, url in needed:
        filename = _filename_from_url(url)
        kind = "image" if field == "image_url" else "video"

        if url not in captured:
            log.warning("MISS    %s — not captured from slideshow", filename)
            failures.append((url, "not loaded by slideshow page"))
            stats["failed"] += 1
            continue

        data = captured[url]
        sha = hashlib.sha256(data).hexdigest()

        try:
            public_url = _upload_to_storage(sb, data, sha, filename)
            sb.table("incidents").update({field: public_url}).eq("id", row["id"]).execute()
            log.info("OK      %s (%d bytes)", filename, len(data))
            stats[f"{kind}s"] += 1
            stats["bytes"] += len(data)
        except Exception as e:
            reason = str(e)[:120]
            log.warning("FAIL    %s — %s", filename, reason)
            failures.append((url, reason))
            stats["failed"] += 1

    # Report
    log.info("")
    log.info("=== Mirror complete ===")
    log.info("Images mirrored:  %d", stats["images"])
    log.info("Videos mirrored:  %d", stats["videos"])
    log.info("Skipped:          %d", skipped)
    log.info("Failed:           %d", stats["failed"])
    log.info("Total uploaded:   %.1f KB", stats["bytes"] / 1024)

    if failures:
        log.info("")
        log.info("Failed downloads:")
        for url, reason in failures:
            log.info("  %s — %s", _filename_from_url(url), reason)


def main():
    parser = argparse.ArgumentParser(description="Mirror war.gov media to Supabase Storage")
    parser.add_argument("--dry-run", action="store_true", help="List files without downloading")
    parser.add_argument("--limit", type=int, default=None, help="Max incidents to process")
    args = parser.parse_args()
    mirror(dry_run=args.dry_run, limit=args.limit)


if __name__ == "__main__":
    main()
