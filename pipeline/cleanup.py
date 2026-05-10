"""
Data cleanup for UFO Dossier incidents.

Fixes three issues found by audit.py:
  1. Dedup: flag duplicate excerpt pairs (keeps the better copy)
  2. Dates: backfill occurred_at from parseable occurred_at_text
  3. Branches: backfill NULL branch from source file agency

Usage:
  python3 -m pipeline.cleanup --dry-run          # preview all fixes
  python3 -m pipeline.cleanup                    # apply all fixes
  python3 -m pipeline.cleanup --only dedup       # just dedup
  python3 -m pipeline.cleanup --only dates       # just dates
  python3 -m pipeline.cleanup --only branches    # just branches
"""

import argparse
import re
import logging
from collections import defaultdict
from difflib import SequenceMatcher

from .db import get_supabase

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 1. DEDUP — flag duplicate excerpt pairs
# ---------------------------------------------------------------------------

def _completeness_score(inc: dict) -> int:
    """Higher = more metadata filled in = better copy to keep."""
    score = 0
    if inc.get("occurred_at"):
        score += 3
    if inc.get("branch") and inc["branch"] != "null":
        score += 2
    if inc.get("location_text"):
        score += 2
    if inc.get("country"):
        score += 1
    if inc.get("lat"):
        score += 1
    if inc.get("resolution_status") and inc["resolution_status"] != "insufficient_data":
        score += 1
    if inc.get("sensor_types"):
        score += 1
    raw = inc.get("raw_excerpt") or ""
    score += min(len(raw) // 100, 3)  # longer excerpt = better
    return score


def fix_duplicates(sb, dry_run: bool) -> int:
    """Flag the worse copy in each duplicate pair."""
    resp = sb.from_("incidents") \
        .select("id, case_id, source_file_id, raw_excerpt, title, occurred_at, branch, location_text, country, lat, resolution_status, sensor_types, flagged") \
        .eq("flagged", False) \
        .order("source_file_id") \
        .execute()
    rows = [r for r in (resp.data or []) if r.get("raw_excerpt")]

    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("source_file_id"):
            by_source[r["source_file_id"]].append(r)

    to_flag: set[str] = set()
    pairs_found = 0

    for sf_id, group in by_source.items():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            if a["id"] in to_flag:
                continue
            for b in group[i + 1:]:
                if b["id"] in to_flag:
                    continue
                excerpt_a = (a.get("raw_excerpt") or "").lower()
                excerpt_b = (b.get("raw_excerpt") or "").lower()
                sim = SequenceMatcher(None, excerpt_a, excerpt_b).ratio()
                if sim >= 0.80:
                    pairs_found += 1
                    score_a = _completeness_score(a)
                    score_b = _completeness_score(b)
                    # Flag the worse one (lower score); on tie, flag the second
                    loser = b if score_a >= score_b else a
                    to_flag.add(loser["id"])
                    logger.info(
                        "DEDUP %s (score %d) vs %s (score %d) — flagging %s (sim %.0f%%)",
                        a["case_id"], score_a, b["case_id"], score_b,
                        loser["case_id"], sim * 100
                    )

    if not dry_run and to_flag:
        for inc_id in to_flag:
            sb.from_("incidents").update({
                "flagged": True,
                "flag_reason": "duplicate_excerpt"
            }).eq("id", inc_id).execute()

    logger.info("DEDUP: %d pairs found, %d incidents %s",
                pairs_found, len(to_flag),
                "would be flagged" if dry_run else "flagged")
    return len(to_flag)


# ---------------------------------------------------------------------------
# 2. DATES — backfill occurred_at from occurred_at_text
# ---------------------------------------------------------------------------

# Patterns ordered from most specific to least
DATE_PATTERNS = [
    # "September 15, 1945" or "September 1947"
    (re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s+(\d{4})", re.I),
     lambda m: (f"{m.group(3)}-{_month_num(m.group(1))}-{int(m.group(2)):02d}", "day")),
    (re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", re.I),
     lambda m: (f"{m.group(2)}-{_month_num(m.group(1))}-01", "month")),
    # "November 5-12, 1946" → take the start date
    (re.compile(r"(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})-\d{1,2},?\s+(\d{4})", re.I),
     lambda m: (f"{m.group(3)}-{_month_num(m.group(1))}-{int(m.group(2)):02d}", "day")),
    # Bare 4-digit year
    (re.compile(r"\b(1[89]\d{2}|20[0-2]\d)\b"),
     lambda m: (f"{m.group(1)}-01-01", "year")),
]

MONTHS = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}

def _month_num(name: str) -> str:
    return MONTHS[name.lower()]


def _parse_date_text(text: str) -> tuple[str, str] | None:
    """Try to extract (YYYY-MM-DD, precision) from free text."""
    if not text:
        return None
    for pattern, extractor in DATE_PATTERNS:
        m = pattern.search(text)
        if m:
            return extractor(m)
    return None


def fix_dates(sb, dry_run: bool) -> int:
    """Backfill occurred_at from occurred_at_text where parseable."""
    resp = sb.from_("incidents") \
        .select("id, case_id, occurred_at, occurred_at_text") \
        .is_("occurred_at", "null") \
        .execute()
    rows = [r for r in (resp.data or []) if r.get("occurred_at_text")]

    fixed = 0
    for r in rows:
        parsed = _parse_date_text(r["occurred_at_text"])
        if not parsed:
            continue
        date_str, precision = parsed
        fixed += 1
        logger.info("DATE %s: '%s' → %s (%s)",
                     r["case_id"], r["occurred_at_text"][:50], date_str, precision)
        if not dry_run:
            sb.from_("incidents").update({
                "occurred_at": date_str,
                "occurred_at_precision": precision,
            }).eq("id", r["id"]).execute()

    logger.info("DATES: %d incidents %s",
                fixed, "would be updated" if dry_run else "updated")
    return fixed


# ---------------------------------------------------------------------------
# 3. BRANCHES — backfill NULL branch from source file agency
# ---------------------------------------------------------------------------

# Map common agency names to standard branch codes
AGENCY_TO_BRANCH = {
    "FBI": "FBI",
    "USAF": "USAF",
    "USN": "USN",
    "USMC": "USMC",
    "USA": "USA",
    "NASA": "NASA",
    "DOS": "DOS",
    "AARO": "AARO",
    "NORTHCOM": "NORTHCOM",
    "CENTCOM": "CENTCOM",
    "INDOPACOM": "INDOPACOM",
    "EUCOM": "EUCOM",
    "DOD": "DoD",
    "DEPARTMENT OF DEFENSE": "DoD",
}


def fix_branches(sb, dry_run: bool) -> int:
    """Backfill NULL/empty branches from source file agency."""
    # Get all incidents with bad branches
    resp = sb.from_("incidents") \
        .select("id, case_id, branch, source_file_id") \
        .execute()
    bad = [r for r in (resp.data or [])
           if not r.get("branch") or r["branch"] == "null"]

    if not bad:
        logger.info("BRANCHES: no null branches found")
        return 0

    # Get source file agencies
    sf_ids = list({r["source_file_id"] for r in bad if r.get("source_file_id")})
    sf_resp = sb.from_("source_files").select("id, agency, filename").execute()
    sf_map = {r["id"]: r for r in (sf_resp.data or [])}

    fixed = 0
    for r in bad:
        sf = sf_map.get(r.get("source_file_id", ""), {})
        agency = sf.get("agency") or ""

        # Try direct match
        branch = AGENCY_TO_BRANCH.get(agency.upper().strip())

        # Try extracting from filename if agency is empty
        if not branch:
            fname = sf.get("filename", "")
            for prefix, code in AGENCY_TO_BRANCH.items():
                if prefix.lower() in fname.lower():
                    branch = code
                    break

        if branch:
            fixed += 1
            logger.info("BRANCH %s: NULL → %s (from source '%s')",
                        r["case_id"], branch, sf.get("filename", "?")[:50])
            if not dry_run:
                sb.from_("incidents").update({
                    "branch": branch,
                }).eq("id", r["id"]).execute()

    logger.info("BRANCHES: %d of %d null-branch incidents %s",
                fixed, len(bad),
                "would be updated" if dry_run else "updated")
    return fixed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="UFO Dossier data cleanup")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--only", choices=["dedup", "dates", "branches"], help="Run only one fix")
    args = parser.parse_args()

    sb = get_supabase()
    run_all = args.only is None

    if run_all or args.only == "dedup":
        fix_duplicates(sb, args.dry_run)
    if run_all or args.only == "dates":
        fix_dates(sb, args.dry_run)
    if run_all or args.only == "branches":
        fix_branches(sb, args.dry_run)

    if args.dry_run:
        logger.info("DRY RUN complete — no data was modified. Remove --dry-run to apply.")


if __name__ == "__main__":
    main()
