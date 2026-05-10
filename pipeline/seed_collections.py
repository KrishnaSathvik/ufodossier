"""ufodossier // seed curated collections into Supabase.

Usage:
    python -m pipeline.seed_collections
"""
from __future__ import annotations

import logging
from pipeline.db import get_supabase

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

COLLECTIONS = [
    {
        "slug": "1947-fbi-flying-discs",
        "title": "1947 FBI Flying Disc Reports",
        "standfirst": "The original wave: FBI field-office memos from the summer America started watching the skies.",
        "sort_order": 1,
        "query": {
            "table": "v_incident_full",
            "filters": [
                ("source_filename", "ilike", "%62-HQ-83894%"),
                ("occurred_at", "gte", "1947-01-01"),
                ("occurred_at", "lte", "1948-12-31"),
            ],
            "limit": 12,
        },
    },
    {
        "slug": "apollo-lunar-anomalies",
        "title": "Apollo-Era Lunar Anomalies",
        "standfirst": "NASA mission transcripts and debriefs referencing unexplained observations during the Apollo program.",
        "sort_order": 2,
        "query": {
            "table": "v_incident_full",
            "or_filters": "branch.eq.NASA,source_filename.ilike.%apollo%",
            "limit": None,
        },
    },
    {
        "slug": "aaro-infrared-cases",
        "title": "AARO Infrared Sensor Cases",
        "standfirst": "Post-2020 incidents captured on infrared sensor systems and reviewed by AARO.",
        "sort_order": 3,
        "query": {
            "table": "v_incident_full",
            "filters": [
                ("sensor_types", "cs", ["infrared"]),
                ("occurred_at", "gte", "2020-01-01"),
            ],
            "limit": 15,
        },
    },
    {
        "slug": "cases-resolved",
        "title": "Resolved Cases",
        "standfirst": "Incidents the government eventually identified: weather balloons, satellites, aircraft, and atmospheric phenomena.",
        "sort_order": 4,
        "query": {
            "table": "v_incident_full",
            "filters": [
                ("resolution_status", "eq", "identified"),
            ],
            "limit": 20,
        },
    },
    {
        "slug": "unresolved",
        "title": "Still Unresolved",
        "standfirst": "The cases that remain unexplained after government review.",
        "sort_order": 5,
        "query": {
            "table": "v_incident_full",
            "filters": [
                ("resolution_status", "eq", "unresolved"),
            ],
            "order": ("occurred_at", {"desc": True}),
            "limit": 25,
        },
    },
    {
        "slug": "naval-radar-encounters",
        "title": "Naval Radar Encounters",
        "standfirst": "U.S. Navy incidents involving radar-tracked objects over open water.",
        "sort_order": 6,
        "query": {
            "table": "v_incident_full",
            "filters": [
                ("branch", "eq", "USN"),
                ("sensor_types", "cs", ["radar"]),
            ],
            "limit": None,
        },
    },
    {
        "slug": "state-dept-cables",
        "title": "State Department Cables",
        "standfirst": "Diplomatic dispatches and consular reports of aerial phenomena abroad.",
        "sort_order": 7,
        "query": {
            "table": "v_incident_full",
            "or_filters": "branch.eq.DOS,source_agency.eq.DOS",
            "limit": None,
        },
    },
]


def _run_query(sb, spec: dict) -> list[str]:
    """Run a collection query spec and return matching incident IDs."""
    q = sb.table(spec["table"]).select("id")

    if "or_filters" in spec:
        q = q.or_(spec["or_filters"])

    for col, op, val in spec.get("filters", []):
        q = getattr(q, op)(col, val)

    if "order" in spec:
        col, opts = spec["order"]
        q = q.order(col, **opts)

    if spec.get("limit"):
        q = q.limit(spec["limit"])

    result = q.execute()
    return [row["id"] for row in (result.data or [])]


def seed():
    sb = get_supabase()

    for coll in COLLECTIONS:
        slug = coll["slug"]

        # Idempotent: skip if slug exists
        existing = sb.table("collections").select("id").eq("slug", slug).execute()
        if existing.data:
            log.info("SKIP  %s (already exists)", slug)
            continue

        # Find matching incidents
        incident_ids = _run_query(sb, coll["query"])
        log.info("%-30s  %d incidents matched", slug, len(incident_ids))

        # Insert collection
        row = sb.table("collections").insert({
            "slug": slug,
            "title": coll["title"],
            "standfirst": coll["standfirst"],
            "sort_order": coll["sort_order"],
        }).execute()
        collection_id = row.data[0]["id"]

        # Insert junction rows
        if incident_ids:
            junction_rows = [
                {
                    "collection_id": collection_id,
                    "incident_id": iid,
                    "sort_order": idx,
                }
                for idx, iid in enumerate(incident_ids)
            ]
            sb.table("collection_incidents").insert(junction_rows).execute()

        log.info("OK    %s  (%d incidents)", slug, len(incident_ids))

    log.info("Done.")


if __name__ == "__main__":
    seed()
