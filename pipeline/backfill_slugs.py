"""
ufodossier // backfill slugs

Generates human-readable URL slugs for all incidents that don't have one yet.
Idempotent — safe to re-run.

Usage:
    python -m pipeline.backfill_slugs
    python -m pipeline.backfill_slugs --dry-run
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import re

from pipeline.db import get_supabase

logger = logging.getLogger(__name__)


def generate_slug(inc: dict) -> str:
    """Generate a human-readable URL slug.
    Format: {year}-{branch}-{first-3-words-kebab}-{4charhash}
    Example: 2024-indopacom-football-shaped-object-a1b2
    """
    year = "undated"
    if inc.get("occurred_at"):
        d = inc["occurred_at"]
        if isinstance(d, str):
            year = d.split("-")[0] if "-" in d else d[:4]

    branch = (inc.get("branch") or "gov").lower().replace(" ", "")

    title = inc.get("title", "untitled")
    words = re.findall(r"[a-z0-9]+", title.lower())
    title_slug = "-".join(words[:5]) if words else "untitled"

    h = hashlib.sha1(inc.get("raw_excerpt", title).encode()).hexdigest()[:4]

    return f"{year}-{branch}-{title_slug}-{h}"


def run(dry_run: bool = False) -> None:
    sb = get_supabase()

    # fetch all incidents missing slugs
    rows = (
        sb.table("incidents")
        .select("id, title, occurred_at, branch, raw_excerpt, slug")
        .is_("slug", "null")
        .execute()
        .data
    )
    logger.info("found %d incidents without slugs", len(rows))
    if not rows:
        return

    # track used slugs to handle collisions within this run
    used_slugs: set[str] = set()

    # also load existing slugs from DB
    existing = sb.table("incidents").select("slug").not_.is_("slug", "null").execute().data
    for r in existing:
        if r["slug"]:
            used_slugs.add(r["slug"])

    updated = 0
    for inc in rows:
        slug = generate_slug(inc)

        # handle collisions by extending hash
        base_slug = slug
        suffix_len = 4
        while slug in used_slugs:
            suffix_len += 2
            h = hashlib.sha1(inc.get("raw_excerpt", inc.get("title", "")).encode()).hexdigest()[:suffix_len]
            slug = f"{base_slug[:-4]}{h}"

        used_slugs.add(slug)

        if dry_run:
            logger.info("would set slug for %s -> %s", inc["id"][:8], slug)
        else:
            sb.table("incidents").update({"slug": slug}).eq("id", inc["id"]).execute()
            logger.info("set slug for %s -> %s", inc["id"][:8], slug)

        updated += 1

    logger.info("backfill complete // %s %d slugs", "would update" if dry_run else "updated", updated)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="log changes without writing to DB")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
