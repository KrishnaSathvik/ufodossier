"""
ufodossier // enrich_metadata

Cross-references the 161 records from war.gov's records table against our
source_files and incidents to fill in missing dates and locations with
government-provided metadata.

Usage:
    python -m pipeline.enrich_metadata --dry-run   # preview changes
    python -m pipeline.enrich_metadata              # apply changes
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime
from pathlib import Path

from pipeline.db import get_supabase

logger = logging.getLogger(__name__)

RECORDS_PATH = Path(__file__).parent / "data" / "war_gov_records.json"


def load_records() -> list[dict]:
    """Load the 161 records scraped from war.gov's records table."""
    with open(RECORDS_PATH) as f:
        return json.load(f)


def parse_gov_date(date_str: str | None) -> str | None:
    """Parse government date formats into YYYY-MM-DD.

    Handles:
      - M/D/YY, M/D/YYYY
      - Date ranges like 10/28/2001-10/29/2001 (takes first date)
      - "Late 2025", "1969", etc. -> None (too imprecise for occurred_at)
      - "N/A", empty, None -> None
    """
    if not date_str or date_str.strip() in ("N/A", ""):
        return None

    date_str = date_str.strip()

    # Handle date ranges — take the first date
    if "-" in date_str and "/" in date_str:
        date_str = date_str.split("-")[0].strip()

    # Try M/D/YY or M/D/YYYY
    for fmt in ("%m/%d/%y", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(date_str, fmt)
            # Fix 2-digit year: 00-29 -> 2000s, 30-99 -> 1900s
            if fmt == "%m/%d/%y" and dt.year > 2030:
                dt = dt.replace(year=dt.year - 100)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Pure year like "1969"
    if re.match(r"^\d{4}$", date_str):
        return None  # Too imprecise for occurred_at column

    # Textual like "Late 2025", "September 2023"
    return None


def parse_gov_date_text(date_str: str | None) -> str | None:
    """Return the raw date string for occurred_at_text if it contains useful info."""
    if not date_str or date_str.strip() in ("N/A", ""):
        return None
    return date_str.strip()


def infer_country(location: str | None) -> str | None:
    """Infer country from location string."""
    if not location:
        return None

    loc = location.strip()
    # Direct country matches
    country_map = {
        "Iraq": "Iraq",
        "Syria": "Syria",
        "Germany": "Germany",
        "Netherlands": "Netherlands",
        "Azerbaijan": "Azerbaijan",
        "Iran": "Iran",
        "Japan": "Japan",
        "Greece": "Greece",
        "Djibouti": "Djibouti",
        "Papua New Guinea": "Papua New Guinea",
        "Georgia": "Georgia",
        "Turkmenistan": "Turkmenistan",
        "United Arab Emirates": "United Arab Emirates",
    }
    for key, country in country_map.items():
        if key in loc:
            return country

    # Regional matches
    region_map = {
        "Arabian Gulf": "International Waters",
        "Arabian Sea": "International Waters",
        "Gulf of Aden": "International Waters",
        "Gulf of Oman": "International Waters",
        "Mediterranean Sea": "International Waters",
        "Aegean Sea": "International Waters",
        "Strait of Hormuz": "International Waters",
        "Pacific Ocean": "International Waters",
        "Low Earth Orbit": None,
        "Middle East": None,  # Too ambiguous
        "Africa": None,
        "North America": "United States",
    }
    for key, country in region_map.items():
        if key in loc:
            return country

    # US locations
    us_patterns = [
        "United States", "Western US", "Western United States",
        "Detroit", "Vandenberg", "Pacific Time Zone",
    ]
    for pattern in us_patterns:
        if pattern in loc:
            return "United States"

    return None


def _normalize_filename(name: str) -> str:
    """Normalize a filename for matching: lowercase, strip extension, collapse whitespace."""
    name = name.lower()
    name = re.sub(r"\.(pdf|jpg|png|mp4|mov|vid)$", "", name)
    name = re.sub(r"[,\s_-]+", " ", name).strip()
    return name


def run(dry_run: bool = False) -> None:
    sb = get_supabase()
    records = load_records()
    logger.info("loaded %d records from %s", len(records), RECORDS_PATH)

    # Load all source_files for matching
    source_files = sb.table("source_files").select("id, filename, url").execute().data
    logger.info("loaded %d source_files from DB", len(source_files))

    # Build normalized lookup
    sf_index: list[tuple[str, dict]] = []
    for sf in source_files:
        norm = _normalize_filename(sf["filename"])
        sf_index.append((norm, sf))

    enriched = 0
    skipped = 0
    no_match = 0

    for rec in records:
        rec_norm = _normalize_filename(rec["filename"])

        # Find best matching source_file by substring
        matched_sf = None
        best_overlap = 0
        for sf_norm, sf in sf_index:
            # Check if record filename is a substring of source filename or vice versa
            if rec_norm in sf_norm or sf_norm in rec_norm:
                overlap = len(rec_norm)
                if overlap > best_overlap:
                    best_overlap = overlap
                    matched_sf = sf
            else:
                # Token overlap fallback
                rec_tokens = set(rec_norm.split())
                sf_tokens = set(sf_norm.split())
                overlap = len(rec_tokens & sf_tokens)
                if overlap >= 3 and overlap > best_overlap:
                    best_overlap = overlap
                    matched_sf = sf

        if not matched_sf:
            logger.debug("no source_file match for record: %s", rec["filename"])
            no_match += 1
            continue

        # Get incidents for this source_file
        incidents = (
            sb.table("incidents")
            .select("id, case_id, occurred_at, occurred_at_text, location_text, country, region")
            .eq("source_file_id", matched_sf["id"])
            .execute()
            .data
        )

        if not incidents:
            logger.debug("no incidents for source_file %s", matched_sf["filename"])
            skipped += 1
            continue

        gov_date = parse_gov_date(rec.get("incident_date"))
        gov_date_text = parse_gov_date_text(rec.get("incident_date"))
        gov_location = rec.get("incident_location")
        gov_country = infer_country(gov_location)

        for inc in incidents:
            updates: dict[str, str] = {}

            # Fill occurred_at if NULL and gov date parses
            if not inc.get("occurred_at") and gov_date:
                updates["occurred_at"] = gov_date
                logger.info(
                    "%s: occurred_at NULL -> %s (from gov date %s)",
                    inc["case_id"], gov_date, rec.get("incident_date"),
                )

            # Fill occurred_at_text if NULL and gov has text
            if not inc.get("occurred_at_text") and gov_date_text:
                updates["occurred_at_text"] = gov_date_text

            # Fill location_text if NULL
            if not inc.get("location_text") and gov_location:
                updates["location_text"] = gov_location
                logger.info(
                    "%s: location_text NULL -> %s",
                    inc["case_id"], gov_location,
                )

            # Fill country if NULL
            if not inc.get("country") and gov_country:
                updates["country"] = gov_country
                logger.info(
                    "%s: country NULL -> %s (inferred from %s)",
                    inc["case_id"], gov_country, gov_location,
                )

            # Fill region if NULL and location has useful info
            if not inc.get("region") and gov_location:
                updates["region"] = gov_location

            if updates:
                if not dry_run:
                    sb.table("incidents").update(updates).eq("id", inc["id"]).execute()
                enriched += 1
                logger.info(
                    "enriched %s: %s",
                    inc["case_id"],
                    ", ".join(f"{k}={v}" for k, v in updates.items()),
                )
            else:
                skipped += 1

    logger.info(
        "enrichment complete // enriched=%d skipped=%d no_match=%d",
        enriched, skipped, no_match,
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="log proposed changes without writing to DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
