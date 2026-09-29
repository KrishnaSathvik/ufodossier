"""
Candidate generation. No candidate without linking evidence.

Generic agency / year / "western United States" / "UAP" alone never qualify.
"""

from __future__ import annotations

from typing import Any

from pipeline.linker.normalize import (
    is_generic_location,
    series_identifiers,
    specific_place_tokens,
    year_from,
)


def _ext_id(filename: str) -> str:
    return (filename or "").replace(".pdf", "").replace(".PDF", "")


def generate_candidates(
    *,
    incidents: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    catalog: dict[str, dict[str, Any]],
    texts: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Return candidate link records with evidence lists.
    Candidates are not decisions.
    """
    texts = texts or {}
    by_file = {row["filename"]: row for row in classifications}
    candidates: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    def add(kind: str, left: str, right: str, evidence: list[str], payload: dict | None = None) -> None:
        key = (kind, left, right)
        rev = (kind, right, left)
        if key in seen or rev in seen:
            return
        seen.add(key)
        row = {"candidate_kind": kind, "left": left, "right": right, "evidence": evidence}
        if payload:
            row.update(payload)
        candidates.append(row)

    # 1) Official PDF / media pairing from catalog.
    for filename, row in by_file.items():
        eid = row.get("external_id") or _ext_id(filename)
        meta = catalog.get(eid) or {}
        pairing_raw = meta.get("pdf_pairing") or ""
        for part in pairing_raw.replace("|", ",").split(","):
            token = part.strip()
            if not token:
                continue
            # Series labels are not PDF ids.
            if " " in token or token.lower().endswith("event"):
                add(
                    "series_identifier",
                    filename,
                    token,
                    [f"catalog pdf_pairing series label: {token}"],
                    {"series_label": token},
                )
                continue
            target = token if token.lower().endswith(".pdf") else f"{token}.pdf"
            if target == filename:
                continue
            add(
                "catalog_pdf_pairing",
                filename,
                target,
                [f"catalog PDF Pairing links {eid} → {token}"],
            )

    # 2) Explicit series identifiers in catalog title/pairing for DOW western set.
    for filename, row in by_file.items():
        eid = row.get("external_id") or _ext_id(filename)
        meta = catalog.get(eid) or {}
        blob = " ".join(
            [
                meta.get("title") or "",
                meta.get("pdf_pairing") or "",
                meta.get("description") or "",
            ]
        )
        for series_id in series_identifiers(blob) | (
            {"western-us-event-2023"} if "western us event" in (meta.get("pdf_pairing") or "").lower() else set()
        ):
            add(
                "series_identifier",
                filename,
                series_id,
                [f"catalog series identifier {series_id}"],
                {"series_id": series_id},
            )

    # 3) Analysis / media source roles against specific places in incident text.
    for filename, row in by_file.items():
        clf = row.get("classification") or {}
        doc_class = clf.get("document_class")
        contains = clf.get("contains_incidents")
        if contains:
            continue
        text = texts.get(filename) or ""
        places = specific_place_tokens(text)
        if not places and doc_class == "media_metadata":
            # Media packets may be empty OCR; catalog location is allowed only as a hint signal
            # when an official pairing already exists (handled above). Skip bare catalog place.
            continue
        # Prefer places that appear in the lede / are repeated — avoids secondary mentions.
        lede = text[:800].lower()
        primary_places = {
            tok for tok in places if tok in lede or text.lower().count(tok) >= 2
        }
        for inc in incidents:
            inc_places = specific_place_tokens(
                " ".join(
                    [
                        inc.get("location_text") or "",
                        inc.get("raw_excerpt") or "",
                        inc.get("title") or "",
                    ]
                )
            )
            shared_primary = primary_places & inc_places
            shared_any = places & inc_places
            if not shared_any:
                continue
            if doc_class == "analysis":
                band = "strong" if shared_primary else "medium"
                add(
                    "analysis_place_match",
                    filename,
                    inc.get("case_id") or "",
                    [
                        f"analysis source text shares specific place token(s): {sorted(shared_primary or shared_any)}",
                        f"target incident {inc.get('case_id')} from {inc.get('source_filename')}",
                        f"place_prominence={'lede_or_repeated' if shared_primary else 'secondary_mention'}",
                    ],
                    {
                        "target_filename": inc.get("source_filename"),
                        "score_band": band,
                    },
                )
            elif doc_class == "correspondence":
                year = year_from(text)
                inc_year = year_from(inc.get("occurred_at")) or year_from(inc.get("raw_excerpt") or "")
                if year and inc_year and year == inc_year and shared_primary:
                    add(
                        "followup_place_year",
                        filename,
                        inc.get("case_id") or "",
                        [
                            f"correspondence shares place {sorted(shared_primary)} and year {year}",
                        ],
                        {"target_filename": inc.get("source_filename")},
                    )

    # 4) Specific place + date overlap between accepted incidents (not generic).
    for i, left in enumerate(incidents):
        for right in incidents[i + 1 :]:
            if left.get("source_filename") == right.get("source_filename"):
                continue
            left_loc = left.get("location_text") or ""
            right_loc = right.get("location_text") or ""
            if is_generic_location(left_loc) or is_generic_location(right_loc):
                continue
            shared = specific_place_tokens(left_loc) & specific_place_tokens(right_loc)
            if not shared:
                continue
            ly = year_from(left.get("occurred_at")) or year_from(left.get("raw_excerpt") or "")
            ry = year_from(right.get("occurred_at")) or year_from(right.get("raw_excerpt") or "")
            if ly and ry and ly != ry:
                continue
            evidence = [f"shared specific place token(s): {sorted(shared)}"]
            if ly and ry and ly == ry:
                evidence.append(f"matching year {ly}")
            add(
                "specific_place_overlap",
                left.get("case_id") or "",
                right.get("case_id") or "",
                evidence,
                {
                    "left_filename": left.get("source_filename"),
                    "right_filename": right.get("source_filename"),
                },
            )

    return candidates
