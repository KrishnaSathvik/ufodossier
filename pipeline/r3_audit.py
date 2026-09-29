"""
Review-only relationship hints and alarms for a local R3 run.

Does not modify classification, OCR, routing, quote validation, or evidence
sufficiency. Does not auto-link, merge, or write incidents.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Any

# Cross-source place overlap. Generic geography and prose words are not a cluster.
_PLACE_STOP = frozenset(
    """
    united states state county mountain mountains north south east west
    western eastern northern southern central near area base field over
    orange white blue green black yellow silver brown gray grey
    from with that this report reports incident object objects unidentified
    aerial anomalous phenomenon flying light lights approximately between
    observation location sighting northwest northeast southwest southeast
    during after before around within along about under above several
    multiple unknown october valley rural highway point road lake ridge
    peak side home pond tree line edge rear left house residence vicinity
    trees water property window flight mission reentry orbital orbit city
    fort first avenue street route miles coast train site international airport
    observatory astrophysical distinctive slightly night area
    """.split()
)

HIGH_YIELD_ACCEPTED = 8
HIGH_YIELD_CANDIDATES = 15
HIGH_QUOTE_REJECTION_RATE = 0.50
HIGH_QUOTE_REJECTION_MIN_CANDIDATES = 4
HIGH_OCR_FAILURE_RATE = 0.25
HIGH_OCR_FAILURE_MIN_PAGES = 4
REPEATED_DATE_LOCATION = 4
DUPLICATE_EXCERPT_RATIO = 0.92


def place_tokens(text: str) -> set[str]:
    """Capitalized name tokens only, so prose words like 'approximately' do not cluster."""
    words = re.findall(r"\b[A-Z][a-zA-Z]{3,}\b", text or "")
    return {w.lower() for w in words if w.lower() not in _PLACE_STOP and len(w) >= 4}


def _year(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"(19|20)\d{2}", value)
    return match.group(0) if match else None


def _hint(**fields: Any) -> dict[str, Any]:
    row = {"auto_linked": False, "auto_merged": False}
    row.update(fields)
    return row


def _incidents_by_source(accepted: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for inc in accepted:
        grouped.setdefault(inc.get("source_filename") or "", []).append(inc)
    return grouped


def collect_relationship_hints(
    accepted: list[dict],
    classifications: list[dict],
    *,
    catalog: dict[str, dict],
    texts: dict[str, str],
    thumbnails: set[str],
) -> list[dict]:
    """
    Candidate relationships only. Nothing here changes an incident or a class.
    Unrecoverable thumbnails are excluded so catalog metadata cannot stand in
    for missing source text (CIA-UAP-009).
    """
    hints: list[dict] = []
    by_source = _incidents_by_source(accepted)
    by_file = {row["filename"]: row for row in classifications}

    hints.extend(_possible_same_events(accepted))
    hints.extend(_duplicate_sources(accepted))

    for filename, row in by_file.items():
        if filename in thumbnails:
            continue
        external_id = row.get("external_id") or filename.replace(".pdf", "")
        meta = catalog.get(external_id) or {}
        doc_class = (row.get("classification") or {}).get("document_class")
        contains = (row.get("classification") or {}).get("contains_incidents")
        for pairing_file in _pairing_filenames(meta.get("pdf_pairing") or ""):
            target_incs = by_source.get(pairing_file) or []
            if not target_incs or filename == pairing_file:
                continue
            relationship = _relationship_for_class(doc_class, contains)
            if relationship:
                hints.append(
                    _hint(
                        relationship=relationship,
                        source_filename=filename,
                        target_filename=pairing_file,
                        target_case_ids=[inc.get("case_id") for inc in target_incs],
                        signal="catalog_pdf_pairing",
                    )
                )

        if doc_class == "analysis" and not contains and not any(
            h["relationship"] == "analysis_of_event" and h["source_filename"] == filename for h in hints
        ):
            text = texts.get(filename) or ""
            match = _best_text_place_match(text, accepted, exclude_filename=filename)
            if match:
                hints.append(
                    _hint(
                        relationship="analysis_of_event",
                        source_filename=filename,
                        target_filename=match["source_filename"],
                        target_case_ids=match["case_ids"],
                        signal="source_text_place",
                        matched_tokens=match["tokens"],
                    )
                )

        reason = ((row.get("classification") or {}).get("reason") or "").lower()
        if doc_class == "correspondence" and not contains and "catalog/referral" not in reason:
            text = texts.get(filename) or ""
            match = _best_text_place_match(text, accepted, exclude_filename=filename, require_year=True)
            if match and not any(
                h["relationship"] == "followup_to_event" and h["source_filename"] == filename for h in hints
            ):
                hints.append(
                    _hint(
                        relationship="followup_to_event",
                        source_filename=filename,
                        target_filename=match["source_filename"],
                        target_case_ids=match["case_ids"],
                        signal="source_text_place_and_year",
                        matched_tokens=match["tokens"],
                    )
                )

    return hints


def _pairing_filenames(raw: str) -> list[str]:
    names = []
    for part in re.split(r"[|,]", raw or ""):
        token = part.strip()
        if not token:
            continue
        if not token.lower().endswith(".pdf"):
            token = token + ".pdf"
        names.append(token)
    return names


def _relationship_for_class(doc_class: str | None, contains_incidents: bool | None) -> str | None:
    if doc_class == "media_metadata":
        return "media_for_event"
    if doc_class == "analysis" and not contains_incidents:
        return "analysis_of_event"
    if doc_class == "correspondence" and not contains_incidents:
        return "followup_to_event"
    return None


def _possible_same_events(accepted: list[dict]) -> list[dict]:
    hints = []
    for i, left in enumerate(accepted):
        for right in accepted[i + 1 :]:
            if left.get("source_filename") == right.get("source_filename"):
                continue
            shared = place_tokens(left.get("location_text") or "") & place_tokens(right.get("location_text") or "")
            if not shared:
                continue
            year_l = _year(left.get("occurred_at"))
            year_r = _year(right.get("occurred_at"))
            if year_l and year_r and year_l != year_r:
                continue
            if not year_l and not year_r and max(len(tok) for tok in shared) < 8:
                continue
            hints.append(
                _hint(
                    relationship="possible_same_event",
                    source_filename=left.get("source_filename"),
                    target_filename=right.get("source_filename"),
                    target_case_ids=[left.get("case_id"), right.get("case_id")],
                    signal="shared_place",
                    matched_tokens=sorted(shared),
                )
            )
    return hints


def _duplicate_sources(accepted: list[dict]) -> list[dict]:
    hints = []
    for i, left in enumerate(accepted):
        status = (left.get("duplicate") or {}).get("duplicate_status")
        if status == "likely_duplicate":
            hints.append(
                _hint(
                    relationship="duplicate_source",
                    source_filename=left.get("source_filename"),
                    target_filename=None,
                    target_case_ids=[left.get("case_id"), (left.get("duplicate") or {}).get("best_match_case_id")],
                    signal="production_excerpt_similarity",
                )
            )
        excerpt_l = (left.get("raw_excerpt") or "").strip().lower()
        if len(excerpt_l) < 40:
            continue
        for right in accepted[i + 1 :]:
            if left.get("source_filename") == right.get("source_filename"):
                continue
            excerpt_r = (right.get("raw_excerpt") or "").strip().lower()
            if len(excerpt_r) < 40:
                continue
            score = SequenceMatcher(None, excerpt_l, excerpt_r).ratio()
            if score >= DUPLICATE_EXCERPT_RATIO:
                hints.append(
                    _hint(
                        relationship="duplicate_source",
                        source_filename=left.get("source_filename"),
                        target_filename=right.get("source_filename"),
                        target_case_ids=[left.get("case_id"), right.get("case_id")],
                        signal="corpus_excerpt_similarity",
                        score=round(score, 3),
                    )
                )
    return hints


def _best_text_place_match(
    text: str,
    accepted: list[dict],
    *,
    exclude_filename: str,
    require_year: bool = False,
) -> dict | None:
    lowered = text.lower()
    best: dict | None = None
    best_len = 0
    grouped = _incidents_by_source(accepted)
    for filename, incidents in grouped.items():
        if filename == exclude_filename:
            continue
        tokens: set[str] = set()
        years: set[str] = set()
        for inc in incidents:
            tokens |= place_tokens(inc.get("location_text") or "")
            year = _year(inc.get("occurred_at"))
            if year:
                years.add(year)
        matched = sorted(tok for tok in tokens if re.search(rf"\b{re.escape(tok)}\b", lowered))
        if not matched:
            continue
        if require_year and years and not any(year in text for year in years):
            continue
        strength = max(len(tok) for tok in matched)
        if strength > best_len:
            best_len = strength
            best = {
                "source_filename": filename,
                "case_ids": [inc.get("case_id") for inc in incidents],
                "tokens": matched,
            }
    return best


def per_document_rows(
    classifications: list[dict],
    *,
    accepted: list[dict],
    quote_rejected: list[dict],
    evidence_insufficient: list[dict],
) -> list[dict]:
    counts: dict[str, dict[str, int]] = {}
    for inc in accepted:
        bucket = counts.setdefault(inc.get("source_filename") or "", {"accepted": 0, "quote_rejected": 0, "evidence_insufficient": 0})
        bucket["accepted"] += 1
    for inc in quote_rejected:
        bucket = counts.setdefault(inc.get("source_filename") or "", {"accepted": 0, "quote_rejected": 0, "evidence_insufficient": 0})
        bucket["quote_rejected"] += 1
    for inc in evidence_insufficient:
        bucket = counts.setdefault(inc.get("source_filename") or "", {"accepted": 0, "quote_rejected": 0, "evidence_insufficient": 0})
        bucket["evidence_insufficient"] += 1

    rows = []
    for row in classifications:
        filename = row["filename"]
        stats = counts.get(filename, {"accepted": 0, "quote_rejected": 0, "evidence_insufficient": 0})
        candidates = stats["accepted"] + stats["quote_rejected"] + stats["evidence_insufficient"]
        pages = row.get("page_count") or 0
        ocr_failed = row.get("ocr_failed") or 0
        quote_rate = (stats["quote_rejected"] / candidates) if candidates else 0.0
        ocr_rate = (ocr_failed / pages) if pages else 0.0
        rows.append(
            {
                "filename": filename,
                "external_id": row.get("external_id"),
                "document_class": (row.get("classification") or {}).get("document_class"),
                "extraction_action": row.get("extraction_action"),
                "page_count": pages,
                "usable_text_chars": row.get("usable_text_chars"),
                "pages_ocrd": row.get("pages_ocrd") or 0,
                "ocr_failed": ocr_failed,
                "ocr_failure_rate": round(ocr_rate, 3),
                "candidates": candidates,
                "quote_rejected": stats["quote_rejected"],
                "quote_rejection_rate": round(quote_rate, 3),
                "evidence_insufficient": stats["evidence_insufficient"],
                "accepted": stats["accepted"],
            }
        )
    return rows


def review_alarms(doc_rows: list[dict], accepted: list[dict], thumbnails: set[str]) -> list[dict]:
    """Flags for needs_review. They do not fail the run."""
    alarms: list[dict] = []
    for row in doc_rows:
        filename = row["filename"]
        if row["extraction_action"] == "extract" and row["candidates"] == 0:
            alarms.append({"filename": filename, "alarm": "extract_zero_candidates", "needs_review": True})
        if row["accepted"] >= HIGH_YIELD_ACCEPTED or row["candidates"] >= HIGH_YIELD_CANDIDATES:
            alarms.append(
                {
                    "filename": filename,
                    "alarm": "high_yield",
                    "accepted": row["accepted"],
                    "candidates": row["candidates"],
                    "needs_review": True,
                }
            )
        if (
            row["candidates"] >= HIGH_QUOTE_REJECTION_MIN_CANDIDATES
            and row["quote_rejection_rate"] >= HIGH_QUOTE_REJECTION_RATE
        ):
            alarms.append(
                {
                    "filename": filename,
                    "alarm": "high_quote_rejection",
                    "quote_rejection_rate": row["quote_rejection_rate"],
                    "needs_review": True,
                }
            )
        if filename in thumbnails:
            alarms.append(
                {
                    "filename": filename,
                    "alarm": "unrecoverable_thumbnail",
                    "needs_review": True,
                    "note": "Provenance case. Do not substitute catalog metadata for source text.",
                }
            )
        elif row["page_count"] >= HIGH_OCR_FAILURE_MIN_PAGES and row["ocr_failure_rate"] >= HIGH_OCR_FAILURE_RATE:
            alarms.append(
                {
                    "filename": filename,
                    "alarm": "high_ocr_failure",
                    "ocr_failure_rate": row["ocr_failure_rate"],
                    "needs_review": True,
                }
            )

    repeats: dict[tuple[str, str], int] = {}
    for inc in accepted:
        year = _year(inc.get("occurred_at")) or ""
        places = place_tokens(inc.get("location_text") or "")
        for place in places:
            key = (inc.get("occurred_at") or year, place)
            repeats[key] = repeats.get(key, 0) + 1
    for (when, place), count in sorted(repeats.items()):
        if count >= REPEATED_DATE_LOCATION:
            alarms.append(
                {
                    "alarm": "repeated_date_location",
                    "occurred_at": when,
                    "place": place,
                    "count": count,
                    "needs_review": True,
                }
            )
    return alarms
