"""ufodossier // geocode incidents via Nominatim

Queries incidents with location_text but no lat/lon, geocodes each
via the OpenStreetMap Nominatim API, and writes lat/lon back.

Rate limited to 1 request/second per Nominatim usage policy.

Usage:
    python -m pipeline.geocode                  # geocode all pending
    python -m pipeline.geocode --limit 10       # first 10 only
    python -m pipeline.geocode --dry-run        # log proposals, no writes
"""
from __future__ import annotations

import argparse
import logging
import time
from urllib.parse import quote_plus

import requests

from .db import get_supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "UFODossier-Pipeline/1.0 (https://github.com/ufodossier)"
MIN_DELAY = 1.1  # seconds between requests (Nominatim policy: max 1/s)


def geocode_location(location_text: str) -> dict | None:
    """Call Nominatim for a single location string.

    Returns dict with lat, lon, importance (confidence proxy) or None.
    """
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={
                "q": location_text,
                "format": "json",
                "limit": 1,
            },
            headers={"User-Agent": USER_AGENT},
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json()
        if not results:
            return None
        hit = results[0]
        return {
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
            "importance": float(hit.get("importance", 0)),
            "display_name": hit.get("display_name", ""),
        }
    except Exception as e:
        logger.warning("Nominatim error for %r: %s", location_text, e)
        return None


def confidence_from_importance(importance: float) -> str:
    if importance >= 0.6:
        return "high"
    elif importance >= 0.3:
        return "med"
    return "low"


def run(*, limit: int | None = None, dry_run: bool = False) -> None:
    sb = get_supabase()

    # Fetch incidents needing geocoding
    query = (
        sb.table("incidents")
        .select("id, case_id, location_text")
        .not_.is_("location_text", "null")
        .is_("lat", "null")
    )
    if limit:
        query = query.limit(limit)

    result = query.execute()
    rows = result.data or []

    logger.info("Found %d incidents to geocode%s", len(rows), " (dry run)" if dry_run else "")

    geocoded = 0
    failed = 0

    for i, row in enumerate(rows):
        loc = row["location_text"].strip()
        if not loc:
            continue

        logger.info("[%d/%d] %s — %r", i + 1, len(rows), row["case_id"], loc)

        geo = geocode_location(loc)
        if geo is None:
            logger.info("  -> no result")
            failed += 1
        else:
            conf = confidence_from_importance(geo["importance"])
            logger.info(
                "  -> %.4f, %.4f (%s confidence) — %s",
                geo["lat"], geo["lon"], conf, geo["display_name"],
            )
            if not dry_run:
                sb.table("incidents").update({
                    "lat": geo["lat"],
                    "lon": geo["lon"],
                    "geocode_method": "nominatim",
                    "geocode_confidence": conf,
                }).eq("id", row["id"]).execute()
            geocoded += 1

        # Respect Nominatim rate limit
        if i < len(rows) - 1:
            time.sleep(MIN_DELAY)

    logger.info(
        "Done. Geocoded: %d, Failed: %d, Skipped: %d",
        geocoded, failed, len(rows) - geocoded - failed,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Geocode incidents via Nominatim")
    parser.add_argument("--limit", type=int, default=None, help="Max incidents to process")
    parser.add_argument("--dry-run", action="store_true", help="Log proposals without writing")
    args = parser.parse_args()
    run(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
