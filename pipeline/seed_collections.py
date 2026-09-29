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
    {
        "slug": "western-us-2023",
        "title": "Western US 2023 Series",
        "standfirst": "The linked series of western United States reports from DOW-UAP-D078 through D083. These are separate events in one series, not one sighting.",
        "sort_order": 8,
        "query": {
            "case_ids": [
                "UNDATED-FBI-42C272",
                "UNDATED-FBI-B8A3AB",
                "UNDATED-FBI-C98A18",
                "UNDATED-FBI-C390B7",
                "UNDATED-FBI-031A45",
                "UNDATED-FBI-CD3613",
                "UNDATED-FBI-63F44E",
                "UNDATED-OTHER-7258F0",
                "UNDATED-OTHER-F8E57A",
                "UNDATED-OTHER-B40E2C",
                "UNDATED-OTHER-C1D19C",
                "UNDATED-FBI-82CCDD",
                "UNDATED-FBI-F4CE38",
                "UNDATED-FBI-AF6C31",
                "UNDATED-FBI-15D04A",
                "UNDATED-FBI-FEDFE7",
                "UNDATED-FBI-4557DC",
                "UNDATED-FBI-2EAE94",
                "UNDATED-FBI-42FC0E",
                "UNDATED-FBI-578E28",
                "UNDATED-FBI-4FF3BA",
                "UNDATED-FBI-09122D",
                "UNDATED-FBI-C4AD20",
                "UNDATED-DOW-03C815",
                "UNDATED-DOW-8BB3D1",
                "UNDATED-DOW-0AF53F",
                "UNDATED-DOW-75EF1D",
                "UNDATED-DOW-94EB50",
            ],
        },
    },
    {
        "slug": "green-fireballs",
        "title": "Green Fireball Reports",
        "standfirst": "Excerpts that name green fireballs, mostly over New Mexico in the late 1940s, drawn from the later PURSUE releases.",
        "sort_order": 9,
        "query": {
            "case_ids": [
                "1949-USAF-9D1046",
                "1949-USAF-5C0132",
                "1948-USAF-DDD5CA",
                "1948-USAF-BFA2CC",
                "UNDATED-DOE-80EBE8",
                "UNDATED-DOE-BBFEBB",
                "1946-USAF-380402",
                "UNDATED-DOE-A60A48",
                "UNDATED-DOE-5FC004",
                "UNDATED-DOE-DA531C",
                "UNDATED-USAF-B32231",
            ],
        },
    },
    {
        "slug": "odni-test-range-narrative",
        "title": "ODNI Test Range Narrative",
        "standfirst": "Four excerpts from the senior intelligence official's account of orb encounters on a mountain test range.",
        "sort_order": 10,
        "query": {
            "case_ids": [
                "UNDATED-USAF-668927",
                "UNDATED-USAF-8AFE60",
                "UNDATED-USAF-B4E651",
                "UNDATED-USAF-61107E",
            ],
        },
    },
]


def _run_query(sb, spec: dict) -> list[str]:
    """Run a collection query spec and return matching incident IDs."""
    case_ids = spec.get("case_ids")
    if case_ids:
        result = (
            sb.table("incidents")
            .select("id, case_id")
            .in_("case_id", case_ids)
            .eq("flagged", False)
            .execute()
        )
        order = {case_id: index for index, case_id in enumerate(case_ids)}
        rows = sorted(result.data or [], key=lambda row: order.get(row["case_id"], 10_000))
        return [row["id"] for row in rows]

    q = sb.table(spec["table"]).select("id").eq("flagged", False)

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

        existing = sb.table("collections").select("id").eq("slug", slug).execute()
        incident_ids = _run_query(sb, coll["query"])
        log.info("%-30s  %d incidents matched", slug, len(incident_ids))

        if existing.data:
            collection_id = existing.data[0]["id"]
            sb.table("collection_incidents").delete().eq("collection_id", collection_id).execute()
            sb.table("collections").update({
                "title": coll["title"],
                "standfirst": coll["standfirst"],
                "sort_order": coll["sort_order"],
            }).eq("id", collection_id).execute()
        else:
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
