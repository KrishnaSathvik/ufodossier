"""
Data audit for UFO Dossier incidents.

Runs five checks against the Supabase database and writes a Markdown
report to stdout (pipe to file with: python -m pipeline.audit > report.md).

Checks:
  1. Pre-1947 dates (likely extraction errors)
  2. Duplicate excerpts within the same source file (>80% overlap)
  3. Recoverable NULL dates (occurred_at_text contains a 4-digit year)
  4. Null/empty/"null"-string branches
  5. Row-to-source ratio (over-splitting check)

Does NOT modify any data.
"""

import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher

from .db import get_supabase


def _similarity(a: str, b: str) -> float:
    """Character-level similarity ratio (0-1) between two strings."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def check_pre_1947(sb) -> list[dict]:
    """1. Incidents with occurred_at before 1947-01-01."""
    resp = sb.from_("incidents") \
        .select("case_id, title, occurred_at, occurred_at_text, source_file_id") \
        .lt("occurred_at", "1947-01-01") \
        .order("occurred_at") \
        .execute()
    return resp.data or []


def check_duplicate_excerpts(sb, threshold: float = 0.80) -> list[dict]:
    """2. Incidents sharing a source file with >80% excerpt overlap."""
    resp = sb.from_("incidents") \
        .select("id, case_id, source_file_id, raw_excerpt, title") \
        .order("source_file_id") \
        .execute()
    rows = [r for r in (resp.data or []) if r.get("raw_excerpt")]

    # Group by source_file_id
    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("source_file_id"):
            by_source[r["source_file_id"]].append(r)

    dupes = []
    seen_pairs: set[tuple[str, str]] = set()
    for sf_id, group in by_source.items():
        if len(group) < 2:
            continue
        for i, a in enumerate(group):
            for b in group[i + 1:]:
                pair = tuple(sorted([a["id"], b["id"]]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                sim = _similarity(a.get("raw_excerpt", ""), b.get("raw_excerpt", ""))
                if sim >= threshold:
                    dupes.append({
                        "case_id_a": a["case_id"],
                        "case_id_b": b["case_id"],
                        "title_a": a["title"],
                        "title_b": b["title"],
                        "similarity": round(sim, 3),
                        "source_file_id": sf_id,
                    })
    return sorted(dupes, key=lambda d: -d["similarity"])


def check_recoverable_dates(sb) -> list[dict]:
    """3. Incidents where occurred_at is NULL but occurred_at_text has a year."""
    resp = sb.from_("incidents") \
        .select("case_id, title, occurred_at_text, source_file_id") \
        .is_("occurred_at", "null") \
        .execute()
    rows = [r for r in (resp.data or []) if r.get("occurred_at_text")]

    year_re = re.compile(r"\b(1[89]\d{2}|20[0-2]\d)\b")
    recoverable = []
    for r in rows:
        text = r.get("occurred_at_text", "") or ""
        m = year_re.search(text)
        if m:
            recoverable.append({
                "case_id": r["case_id"],
                "title": r["title"],
                "occurred_at_text": text,
                "parsed_year": m.group(1),
            })
    return recoverable


def check_bad_branches(sb) -> list[dict]:
    """4. Incidents where branch is NULL, 'null', or empty string."""
    # Fetch all incidents and filter client-side (easier than OR-ing Supabase filters)
    resp = sb.from_("incidents") \
        .select("case_id, title, branch, source_file_id") \
        .execute()
    rows = resp.data or []
    bad = []
    for r in rows:
        b = r.get("branch")
        if b is None or b == "" or b == "null":
            bad.append({
                "case_id": r["case_id"],
                "title": r["title"],
                "branch_value": repr(b),
            })
    return bad


def check_split_ratio(sb) -> dict:
    """5. Row count vs distinct source_file_id count."""
    resp = sb.from_("incidents").select("id, source_file_id").execute()
    rows = resp.data or []
    total = len(rows)
    distinct_sources = len({r["source_file_id"] for r in rows if r.get("source_file_id")})
    ratio = round(total / distinct_sources, 2) if distinct_sources else 0
    return {"total_incidents": total, "distinct_sources": distinct_sources, "ratio": ratio}


def _source_filename(sb, source_file_id: str) -> str:
    """Look up filename for a source_file_id."""
    if not source_file_id:
        return "—"
    resp = sb.from_("source_files").select("filename").eq("id", source_file_id).limit(1).execute()
    if resp.data:
        return resp.data[0].get("filename", "—")
    return "—"


def main():
    sb = get_supabase()

    # Build a filename cache for the report
    all_sf = sb.from_("source_files").select("id, filename").execute()
    sf_map: dict[str, str] = {r["id"]: r["filename"] for r in (all_sf.data or [])}

    def sf_name(sf_id: str | None) -> str:
        if not sf_id:
            return "—"
        return sf_map.get(sf_id, "—")

    print("# UFO Dossier — Data Audit Report\n")

    # --- Check 1: Pre-1947 dates ---
    pre47 = check_pre_1947(sb)
    print(f"## 1. Pre-1947 Dates ({len(pre47)} found)\n")
    if pre47:
        print("Incidents with `occurred_at` before 1947-01-01 (Roswell).")
        print("These are very likely date-extraction errors.\n")
        print("| case_id | title | occurred_at | source |")
        print("|---------|-------|-------------|--------|")
        for r in pre47[:20]:
            print(f"| `{r['case_id']}` | {r['title'][:60]} | {r['occurred_at']} | {sf_name(r.get('source_file_id'))} |")
    else:
        print("No pre-1947 incidents found. (Note: some legitimate pre-1947 reports may exist, e.g. 1890s airship sightings.)\n")
    print()

    # --- Check 2: Duplicate excerpts ---
    dupes = check_duplicate_excerpts(sb)
    print(f"## 2. Duplicate Excerpts ({len(dupes)} pairs found)\n")
    if dupes:
        print("Incident pairs from the same source file with >80% character overlap in `raw_excerpt`.\n")
        print("| case_id A | case_id B | similarity | source |")
        print("|-----------|-----------|------------|--------|")
        for d in dupes[:20]:
            print(f"| `{d['case_id_a']}` | `{d['case_id_b']}` | {d['similarity']:.0%} | {sf_name(d.get('source_file_id'))} |")
    else:
        print("No duplicate excerpt pairs found.\n")
    print()

    # --- Check 3: Recoverable dates ---
    recoverable = check_recoverable_dates(sb)
    print(f"## 3. Recoverable NULL Dates ({len(recoverable)} found)\n")
    if recoverable:
        print("`occurred_at` is NULL but `occurred_at_text` contains a parseable year.\n")
        print("| case_id | title | occurred_at_text | parsed_year |")
        print("|---------|-------|------------------|-------------|")
        for r in recoverable[:20]:
            oat = (r["occurred_at_text"] or "")[:40]
            print(f"| `{r['case_id']}` | {r['title'][:50]} | `{oat}` | {r['parsed_year']} |")
        if len(recoverable) > 20:
            print(f"\n... and {len(recoverable) - 20} more.")
    else:
        print("All incidents with `occurred_at_text` have a parsed `occurred_at`.\n")
    print()

    # --- Check 4: Bad branches ---
    bad_branches = check_bad_branches(sb)
    print(f"## 4. Null/Empty Branches ({len(bad_branches)} found)\n")
    if bad_branches:
        print("Incidents where `branch` is NULL, empty string, or the literal string `\"null\"`.\n")
        print("| case_id | title | branch value |")
        print("|---------|-------|-------------|")
        for r in bad_branches[:20]:
            print(f"| `{r['case_id']}` | {r['title'][:60]} | {r['branch_value']} |")
        if len(bad_branches) > 20:
            print(f"\n... and {len(bad_branches) - 20} more.")
    else:
        print("All incidents have a valid branch value.\n")
    print()

    # --- Check 5: Split ratio ---
    ratio = check_split_ratio(sb)
    print(f"## 5. Row-to-Source Ratio\n")
    print(f"- **Total incidents**: {ratio['total_incidents']}")
    print(f"- **Distinct source files**: {ratio['distinct_sources']}")
    print(f"- **Ratio**: {ratio['ratio']}x")
    if ratio["ratio"] > 5:
        print(f"\n**WARNING**: Ratio exceeds 5x — the extractor may be over-splitting documents.")
    else:
        print(f"\nRatio is within normal range (<=5x).")
    print()

    # --- Summary ---
    print("## Summary\n")
    print(f"| Check | Count |")
    print(f"|-------|-------|")
    print(f"| Pre-1947 dates | {len(pre47)} |")
    print(f"| Duplicate excerpt pairs | {len(dupes)} |")
    print(f"| Recoverable NULL dates | {len(recoverable)} |")
    print(f"| Bad branches | {len(bad_branches)} |")
    print(f"| Row:source ratio | {ratio['ratio']}x |")
    print()
    print("*Report generated by `pipeline/audit.py`. No data was modified.*")


if __name__ == "__main__":
    main()
