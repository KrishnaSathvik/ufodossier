"""
Local-only R2 extraction smoke gate.

Reads classifications from pipeline/reports/r2_smoke/classifications.json,
prefers OCR-hardened text from pipeline/reports/r2_ocr/<stem>/combined.txt
when present, runs Haiku extraction ONLY on incident-bearing docs, validates
excerpts (unchanged tolerance) + evidence sufficiency, checks duplicates
against production READ-ONLY, writes local reports.

NEVER writes to Supabase.

Usage:
  python -m pipeline.smoke_r2_extract
  python -m pipeline.smoke_r2_extract --label v2
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

OUT_DIR = Path("pipeline/reports/r2_smoke")
OCR_DIR = Path("pipeline/reports/r2_ocr")

# Filled by extract_local so readiness reports can show which chunker ran.
CHUNK_PLAN: list[dict] = []
SECTION_CALLS: list[dict] = []


def reset_chunk_plan() -> None:
    CHUNK_PLAN.clear()
    SECTION_CALLS.clear()

def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def load_classifications(path: Path) -> list[dict]:
    data = json.loads(path.read_text())
    return data["results"]


def resolve_text(row: dict) -> tuple[str, str]:
    """Prefer OCR-hardened combined.txt when available."""
    stem = Path(row["filename"]).stem
    ocr_combined = OCR_DIR / stem / "combined.txt"
    if ocr_combined.exists():
        return ocr_combined.read_text(), str(ocr_combined)
    text_path = Path(row["text_path"])
    if text_path.exists():
        return text_path.read_text(), str(text_path)
    return "", ""


def extract_local(
    sf_stub: dict,
    text: str,
    *,
    chunk_strategy: str = "auto",
) -> tuple[list[dict], list[dict], list[dict]]:
    """
    Returns (validated, quote_rejected, evidence_rejected). No DB writes.
    """
    import anthropic
    from pipeline.extract import (
        _generate_case_id,
        _generate_slug,
        _validate_incident,
        dedupe_within_source,
        evidence_sufficient,
        extract_chunk_with_subdivision,
    )
    from pipeline.section_router import select_chunks

    client = anthropic.Anthropic()
    strategy, chunks = select_chunks(text, strategy=chunk_strategy)
    CHUNK_PLAN.append(
        {
            "filename": sf_stub.get("filename"),
            "strategy": strategy,
            "sections": len(chunks),
            "section_chars": [len(c) for c in chunks],
        }
    )
    logger.info(
        "chunk plan %s strategy=%s sections=%d",
        sf_stub.get("filename"),
        strategy,
        len(chunks),
    )
    validated: list[dict] = []
    quote_rejected: list[dict] = []
    evidence_rejected: list[dict] = []

    for chunk in chunks:
        raw_incs, metas = extract_chunk_with_subdivision(client, chunk, sf_stub)
        SECTION_CALLS.extend(metas)
        for inc in raw_incs:
            section_text = (inc or {}).pop("_section_text", chunk) if isinstance(inc, dict) else chunk
            ok = _validate_incident(inc, section_text, sf_stub)
            if not ok:
                quote_rejected.append(
                    {
                        "title": (inc or {}).get("title") if isinstance(inc, dict) else None,
                        "raw_excerpt": (inc or {}).get("raw_excerpt") if isinstance(inc, dict) else None,
                        "reason": "quote_validation_failed",
                        "source_filename": sf_stub["filename"],
                    }
                )
                continue
            sufficient, reason = evidence_sufficient(ok)
            if not sufficient:
                evidence_rejected.append(
                    {
                        "title": ok.get("title"),
                        "raw_excerpt": ok.get("raw_excerpt"),
                        "reason": reason,
                        "source_filename": sf_stub["filename"],
                        "disposition": "source_media_not_incident",
                    }
                )
                continue
            ok["case_id"] = _generate_case_id(ok, sf_stub)
            ok["slug"] = _generate_slug(ok)
            ok["source_filename"] = sf_stub["filename"]
            ok["ingestion_state"] = "validated_local"
            validated.append(ok)

    before = len(validated)
    validated = dedupe_within_source(validated)
    if len(validated) < before:
        logger.info(
            "within-source dedupe %s: %d -> %d",
            sf_stub.get("filename"),
            before,
            len(validated),
        )
    return validated, quote_rejected, evidence_rejected


def fetch_prod_incidents_readonly() -> list[dict]:
    """Read-only comparison set from production."""
    from pipeline.db import get_supabase

    sb = get_supabase()
    rows: list[dict] = []
    start = 0
    page = 1000
    while True:
        chunk = (
            sb.table("incidents")
            .select("id,case_id,title,raw_excerpt,occurred_at,location_text,source_file_id,flagged")
            .range(start, start + page - 1)
            .execute()
        )
        data = chunk.data or []
        rows.extend(data)
        if len(data) < page:
            break
        start += page
    return rows


def classify_duplicate(
    candidate: dict,
    production: list[dict],
) -> dict[str, Any]:
    excerpt = (candidate.get("raw_excerpt") or "").strip()
    best = None
    best_score = 0.0
    for p in production:
        score = _similarity(excerpt, p.get("raw_excerpt") or "")
        if score > best_score:
            best_score = score
            best = p

    status = "new_event"
    if best_score >= 0.92:
        status = "likely_duplicate"
    elif best_score >= 0.75:
        status = "uncertain"
    elif best and candidate.get("occurred_at") and best.get("occurred_at"):
        if candidate["occurred_at"] == best["occurred_at"]:
            loc_a = (candidate.get("location_text") or "").lower()
            loc_b = (best.get("location_text") or "").lower()
            if loc_a and loc_b and (loc_a in loc_b or loc_b in loc_a):
                status = "uncertain"

    return {
        "duplicate_status": status,
        "best_match_case_id": best.get("case_id") if best else None,
        "best_match_score": round(best_score, 3),
        "review_required": status in ("likely_duplicate", "uncertain"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local R2 extraction smoke (no prod writes)")
    parser.add_argument(
        "--classifications",
        type=Path,
        default=OUT_DIR / "classifications.json",
    )
    parser.add_argument("--skip-haiku", action="store_true")
    parser.add_argument("--label", default="v2", help="Output suffix, e.g. v2 -> extractions_v2.json")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    _load_env()

    from pipeline.extract import JSON_STATS, reset_json_stats

    reset_json_stats()

    if not args.classifications.exists():
        logger.error(
            "Missing %s — run: python -m pipeline.classify_document --local-cache .cache/files/pursue/r2",
            args.classifications,
        )
        return 1

    results = load_classifications(args.classifications)
    considered = len(results)
    incident_bearing = [r for r in results if r["classification"]["contains_incidents"]]
    skipped = [r for r in results if not r["classification"]["contains_incidents"]]

    print(f"sources considered:          {considered}")
    print(f"sources skipped by classifier: {len(skipped)}")
    print(f"sources to extract:          {len(incident_bearing)}")

    all_validated: list[dict] = []
    all_quote_rej: list[dict] = []
    all_evidence_rej: list[dict] = []
    text_sources: dict[str, str] = {}

    if args.skip_haiku:
        logger.info("--skip-haiku set; not calling extraction model")
    else:
        for r in incident_bearing:
            text, text_src = resolve_text(r)
            text_sources[r["filename"]] = text_src
            sf_stub = {
                "filename": r["filename"],
                "agency": r.get("agency"),
                "file_type": "pdf",
                "id": f"local:{r['filename']}",
            }
            logger.info(
                "extracting locally from %s (%d chars) text=%s",
                r["filename"],
                len(text),
                text_src,
            )
            validated, quote_rej, evidence_rej = extract_local(sf_stub, text)
            for v in validated:
                v["source_external_id"] = r.get("external_id")
                v["document_class"] = r["classification"]["document_class"]
                v["text_source"] = text_src
            all_validated.extend(validated)
            all_quote_rej.extend(quote_rej)
            all_evidence_rej.extend(evidence_rej)
            logger.info(
                "  -> validated=%d quote_rejected=%d evidence_rejected=%d",
                len(validated),
                len(quote_rej),
                len(evidence_rej),
            )

    dup_rows = []
    if all_validated:
        logger.info("loading production incidents for read-only duplicate check...")
        production = fetch_prod_incidents_readonly()
        logger.info("production incidents loaded: %d", len(production))
        for cand in all_validated:
            d = classify_duplicate(cand, production)
            cand["duplicate"] = d
            dup_rows.append(
                {
                    "case_id": cand.get("case_id"),
                    "title": cand.get("title"),
                    "source_filename": cand.get("source_filename"),
                    **d,
                }
            )

    new_unique = [
        c
        for c in all_validated
        if c.get("duplicate", {}).get("duplicate_status") == "new_event"
    ]
    review = [
        c
        for c in all_validated
        if c.get("duplicate", {}).get("review_required")
    ]

    candidates = len(all_validated) + len(all_quote_rej) + len(all_evidence_rej)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": args.label,
        "production_writes": False,
        "sources_considered": considered,
        "sources_skipped_by_classifier": len(skipped),
        "sources_extracted": len(incident_bearing) if not args.skip_haiku else 0,
        "candidate_incidents": candidates,
        "quote_valid_incidents": len(all_validated) + len(all_evidence_rej),
        "quote_rejected_incidents": len(all_quote_rej),
        "evidence_insufficient": len(all_evidence_rej),
        "incidents_accepted": len(all_validated),
        "duplicate_candidates_review": len(review),
        "new_unique_incidents_local": len(new_unique),
        "json_stats": dict(JSON_STATS),
        "text_sources": text_sources,
        "note": "Local smoke only — nothing written to Supabase / Vercel",
    }

    out = {
        "summary": summary,
        "skipped_sources": [
            {
                "filename": r["filename"],
                "class": r["classification"]["document_class"],
                "reason": r["classification"]["reason"],
            }
            for r in skipped
        ],
        "validated_incidents": all_validated,
        "rejected_incidents": all_quote_rej,
        "evidence_insufficient_incidents": all_evidence_rej,
        "duplicate_triage": dup_rows,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"extractions_{args.label}.json"
    out_path.write_text(json.dumps(out, indent=2, default=str) + "\n")
    # also refresh canonical name for convenience
    (OUT_DIR / "extractions.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    logger.info("wrote %s", out_path)

    print()
    print(f"LOCAL R2 EXTRACTION SMOKE {args.label} (no production writes)")
    for k, v in summary.items():
        if k in ("generated_at", "note", "text_sources"):
            continue
        print(f"  {k}: {v}")
    print()
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
