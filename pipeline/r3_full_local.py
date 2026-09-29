"""
Full local Release 03 runner.

Reuses the frozen 18-document readiness extraction. Classifies every cached
R3 PDF, then calls Haiku only for incident-bearing files outside that sample.
Relationship hints and review alarms are recorded. Nothing is auto-linked,
merged, or written to Supabase.

Usage:
  python -m pipeline.r3_full_local prepare
  python -m pipeline.r3_full_local classify
  python -m pipeline.r3_full_local estimate
  python -m pipeline.r3_full_local extract
  python -m pipeline.r3_full_local audit
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.cache_local_pdfs import ext_id_from_title
from pipeline.r3_audit import collect_relationship_hints, per_document_rows, review_alarms

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "pipeline" / "reports" / "r3_readiness"
OUT = ROOT / "pipeline" / "reports" / "r3_full"
CACHE = ROOT / ".cache" / "files" / "pursue" / "r3"
CSV_PATH = ROOT / "pipeline" / "snapshots" / "pursue" / "2026-09-18-official" / "uap-data.csv"
FROZEN_EXTRACTIONS = READINESS / "extractions.json"
FROZEN_METRICS = READINESS / "metrics.json"
# Readiness sample Haiku spend, already paid. Not re-run.
FROZEN_CALL_COST_USD = 0.02


def link_frozen_ocr() -> int:
    src = READINESS / "ocr"
    dst = OUT / "ocr"
    dst.mkdir(parents=True, exist_ok=True)
    linked = 0
    for child in sorted(src.iterdir()):
        if not child.is_dir():
            continue
        target = dst / child.name
        if target.exists() or target.is_symlink():
            continue
        target.symlink_to(child.resolve())
        linked += 1
    logger.info("linked %d frozen OCR directories into %s", linked, dst)
    return linked


def frozen_filenames() -> set[str]:
    data = json.loads((READINESS / "classifications.json").read_text())
    return {row["filename"] for row in data["results"]}


def load_catalog() -> dict[str, dict]:
    catalog: dict[str, dict] = {}
    with CSV_PATH.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            title = row.get("Title") or ""
            external_id = ext_id_from_title(title)
            if not external_id:
                continue
            catalog[external_id] = {
                "pdf_pairing": row.get("PDF Pairing") or "",
                "incident_location": row.get("Incident Location") or "",
                "incident_date": row.get("Incident Date") or "",
                "title": title,
            }
    return catalog


def thumbnail_filenames(classifications: list[dict]) -> set[str]:
    found: set[str] = set()
    for row in classifications:
        report_path = OUT / "ocr" / Path(row["filename"]).stem / "page_report.json"
        if not report_path.exists():
            continue
        report = json.loads(report_path.read_text())
        stats = report.get("stats") or {}
        thumb_pages = stats.get("ocr_unrecoverable_thumbnail") or 0
        pages = report.get("page_count") or 0
        chars = report.get("usable_text_chars") or 0
        # A postage-stamp source, not a normal file that contains one small image page.
        if pages > 0 and thumb_pages and (thumb_pages >= pages or (pages <= 2 and chars < 400)):
            found.add(row["filename"])
    return found


def estimate_new_chunks() -> dict[str, Any]:
    from pipeline.section_router import select_chunks

    data = json.loads((OUT / "classifications.json").read_text())
    frozen = frozen_filenames()
    plans = []
    sections = 0
    for row in data["results"]:
        if row["filename"] in frozen or row["extraction_action"] != "extract":
            continue
        text = Path(row["text_path"]).read_text() if Path(row["text_path"]).exists() else ""
        strategy, chunks = select_chunks(text, strategy="auto")
        plans.append(
            {
                "filename": row["filename"],
                "strategy": strategy,
                "sections": len(chunks),
                "chars": len(text),
                "page_count": row.get("page_count"),
            }
        )
        sections += len(chunks)
    estimate = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "new_extract_documents": len(plans),
        "estimated_new_haiku_calls_if_no_retry": sections,
        "estimated_new_cost_usd": round(sections * FROZEN_CALL_COST_USD, 3),
        "plans": plans,
        "note": "One call per section if JSON succeeds on the first pass. Retries add a second call.",
    }
    (OUT / "haiku_estimate.json").write_text(json.dumps(estimate, indent=2) + "\n")
    return estimate


def extract_new() -> dict[str, Any]:
    from pipeline.extract import JSON_STATS, reset_json_stats
    from pipeline.local_readiness import _load_env
    from pipeline.smoke_r2_extract import (
        CHUNK_PLAN,
        classify_duplicate,
        extract_local,
        fetch_prod_incidents_readonly,
        reset_chunk_plan,
    )

    _load_env()
    data = json.loads((OUT / "classifications.json").read_text())
    frozen = frozen_filenames()
    new_rows = [
        row
        for row in data["results"]
        if row["extraction_action"] == "extract" and row["filename"] not in frozen
    ]
    reset_json_stats()
    reset_chunk_plan()
    t0 = time.monotonic()
    validated: list[dict] = []
    quote_rej: list[dict] = []
    evidence_rej: list[dict] = []
    for row in new_rows:
        text = Path(row["text_path"]).read_text() if Path(row["text_path"]).exists() else ""
        stub = {
            "filename": row["filename"],
            "agency": row.get("agency"),
            "file_type": "pdf",
            "id": f"local:{row['filename']}",
        }
        logger.info("extract %s (%d chars)", row["filename"], len(text))
        accepted, rejected, insufficient = extract_local(stub, text)
        for inc in accepted:
            inc["source_external_id"] = row.get("external_id")
            inc["document_class"] = row["classification"]["document_class"]
            inc["text_source"] = row["text_path"]
        validated.extend(accepted)
        quote_rej.extend(rejected)
        evidence_rej.extend(insufficient)
        logger.info(
            "  -> accepted=%d quote_rej=%d evidence_rej=%d",
            len(accepted),
            len(rejected),
            len(insufficient),
        )
        (OUT / "extractions_incremental_partial.json").write_text(
            json.dumps(
                {
                    "validated_incidents": validated,
                    "rejected_incidents": quote_rej,
                    "evidence_insufficient_incidents": evidence_rej,
                    "completed_filenames": [item["filename"] for item in new_rows[: new_rows.index(row) + 1]],
                    "json_stats": dict(JSON_STATS),
                },
                indent=2,
                default=str,
            )
            + "\n"
        )

    production = fetch_prod_incidents_readonly() if validated else []
    for cand in validated:
        dup = classify_duplicate(cand, production)
        if dup["duplicate_status"] == "new_event" and dup["best_match_score"] >= 0.60:
            dup["duplicate_status"] = "same_event_new_source"
            dup["review_required"] = True
        cand["duplicate"] = dup

    total_calls = JSON_STATS["json_first_pass"] + 2 * (
        JSON_STATS["json_retry_success"] + JSON_STATS["json_retry_failed"]
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_writes": False,
        "documents_extracted": len(new_rows),
        "skipped_frozen_filenames": sorted(frozen),
        "validated_incidents": validated,
        "rejected_incidents": quote_rej,
        "evidence_insufficient_incidents": evidence_rej,
        "json_stats": dict(JSON_STATS),
        "estimated_haiku_calls": total_calls,
        "estimated_haiku_cost_usd": round(total_calls * FROZEN_CALL_COST_USD, 3),
        "runtime_seconds": round(time.monotonic() - t0, 1),
        "chunk_plan": list(CHUNK_PLAN),
        "production_incidents_compared": len(production),
    }
    (OUT / "extractions_incremental.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return payload


def _status_counts(incidents: list[dict]) -> dict[str, int]:
    counts = {"new_event": 0, "same_event_new_source": 0, "likely_duplicate": 0, "uncertain": 0}
    for inc in incidents:
        status = (inc.get("duplicate") or {}).get("duplicate_status") or "new_event"
        if status not in counts:
            counts[status] = 0
        counts[status] += 1
    return counts


def _classification_drift(full_rows: list[dict]) -> list[dict]:
    frozen = {row["filename"]: row for row in json.loads((READINESS / "classifications.json").read_text())["results"]}
    drift = []
    for row in full_rows:
        prior = frozen.get(row["filename"])
        if not prior:
            continue
        if (
            prior["extraction_action"] != row["extraction_action"]
            or prior["classification"]["document_class"] != row["classification"]["document_class"]
        ):
            drift.append(
                {
                    "filename": row["filename"],
                    "frozen_action": prior["extraction_action"],
                    "full_action": row["extraction_action"],
                    "frozen_class": prior["classification"]["document_class"],
                    "full_class": row["classification"]["document_class"],
                }
            )
    return drift


def write_audit() -> dict[str, Any]:
    classifications = json.loads((OUT / "classifications.json").read_text())["results"]
    frozen_extract = json.loads(FROZEN_EXTRACTIONS.read_text())
    frozen_metrics = json.loads(FROZEN_METRICS.read_text())
    incremental_path = OUT / "extractions_incremental.json"
    incremental = json.loads(incremental_path.read_text()) if incremental_path.exists() else {
        "validated_incidents": [],
        "rejected_incidents": [],
        "evidence_insufficient_incidents": [],
        "json_stats": {"json_first_pass": 0, "json_retry_success": 0, "json_retry_failed": 0},
        "estimated_haiku_calls": 0,
        "estimated_haiku_cost_usd": 0,
        "runtime_seconds": 0,
        "chunk_plan": [],
    }

    accepted = list(frozen_extract["validated_incidents"]) + list(incremental["validated_incidents"])
    quote_rejected = list(frozen_extract["rejected_incidents"]) + list(incremental["rejected_incidents"])
    evidence = list(frozen_extract["evidence_insufficient_incidents"]) + list(
        incremental["evidence_insufficient_incidents"]
    )
    statuses = _status_counts(accepted)
    thumbnails = thumbnail_filenames(classifications)
    doc_rows = per_document_rows(
        classifications,
        accepted=accepted,
        quote_rejected=quote_rejected,
        evidence_insufficient=evidence,
    )
    alarms = review_alarms(doc_rows, accepted, thumbnails)

    texts: dict[str, str] = {}
    for row in classifications:
        doc_class = row["classification"]["document_class"]
        if row["extraction_action"] == "source_only" and doc_class in {"analysis", "correspondence"}:
            path = Path(row["text_path"])
            texts[row["filename"]] = path.read_text() if path.exists() else ""

    hints = collect_relationship_hints(
        accepted,
        classifications,
        catalog=load_catalog(),
        texts=texts,
        thumbnails=thumbnails,
    )
    hint_counts: dict[str, int] = {}
    for hint in hints:
        hint_counts[hint["relationship"]] = hint_counts.get(hint["relationship"], 0) + 1

    json_first = frozen_metrics["json_stats"]["json_first_pass"] + incremental["json_stats"]["json_first_pass"]
    json_ok = frozen_metrics["json_stats"]["json_retry_success"] + incremental["json_stats"]["json_retry_success"]
    json_fail = frozen_metrics["json_stats"]["json_retry_failed"] + incremental["json_stats"]["json_retry_failed"]
    calls = frozen_metrics["estimated_haiku_calls"] + incremental["estimated_haiku_calls"]
    cost = round(frozen_metrics["estimated_haiku_cost_usd"] + incremental["estimated_haiku_cost_usd"], 3)
    stage_a = json.loads((OUT / "classifications.json").read_text())
    candidates = len(accepted) + len(quote_rejected) + len(evidence)
    quote_valid = len(accepted) + len(evidence)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_writes": 0,
        "deploy": 0,
        "gpt6": "off",
        "documents_total": len(classifications),
        "classified_extract": sum(1 for row in classifications if row["extraction_action"] == "extract"),
        "classified_source_only": sum(1 for row in classifications if row["extraction_action"] == "source_only"),
        "pages_total": sum(row.get("page_count") or 0 for row in classifications),
        "pages_ocrd": sum(row.get("pages_ocrd") or 0 for row in classifications),
        "ocr_failed": sum(row.get("ocr_failed") or 0 for row in classifications),
        "unrecoverable_thumbnail_docs": sorted(thumbnails),
        "haiku_calls": calls,
        "json_first_pass": json_first,
        "json_retry_success": json_ok,
        "json_retry_failure": json_fail,
        "candidates": candidates,
        "quote_valid": quote_valid,
        "quote_rejected": len(quote_rejected),
        "evidence_insufficient": len(evidence),
        "accepted": len(accepted),
        "new_event": statuses.get("new_event", 0),
        "likely_duplicate": statuses.get("likely_duplicate", 0),
        "uncertain": statuses.get("uncertain", 0),
        "same_event_new_source": statuses.get("same_event_new_source", 0),
        "possible_event_clusters": hint_counts.get("possible_same_event", 0),
        "analysis_source_relationships": hint_counts.get("analysis_of_event", 0),
        "media_source_relationships": hint_counts.get("media_for_event", 0),
        "followup_relationships": hint_counts.get("followup_to_event", 0),
        "duplicate_source_relationships": hint_counts.get("duplicate_source", 0),
        "cost_usd": cost,
        "stage_a_runtime_seconds": stage_a.get("runtime_seconds"),
        "frozen_extract_runtime_seconds": frozen_metrics.get("runtime_seconds"),
        "incremental_extract_runtime_seconds": incremental.get("runtime_seconds"),
        "classification_drift_vs_frozen_sample": _classification_drift(classifications),
        "needs_review_count": len(alarms),
        "auto_linked": False,
        "quote_rules_changed": False,
        "evidence_gate_changed": False,
    }
    (OUT / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    (OUT / "per_document_metrics.json").write_text(json.dumps(doc_rows, indent=2) + "\n")
    (OUT / "needs_review.json").write_text(json.dumps(alarms, indent=2) + "\n")
    (OUT / "relationship_hints.json").write_text(
        json.dumps(
            {
                "note": "Hints only. No auto-link and no merge.",
                "production_writes": False,
                "counts": hint_counts,
                "hints": hints,
            },
            indent=2,
        )
        + "\n"
    )
    merged = {
        "summary": summary,
        "validated_incidents": accepted,
        "rejected_incidents": quote_rejected,
        "evidence_insufficient_incidents": evidence,
        "chunk_plan": list(frozen_metrics.get("chunk_plan") or []) + list(incremental.get("chunk_plan") or []),
    }
    (OUT / "extractions.json").write_text(json.dumps(merged, indent=2, default=str) + "\n")
    logger.info("audit summary: %s", json.dumps(summary, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Full local R3 (no prod writes)")
    parser.add_argument("command", choices=["prepare", "classify", "estimate", "extract", "audit"])
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    if args.command == "prepare":
        link_frozen_ocr()
        return 0
    if args.command == "classify":
        from pipeline.local_readiness import _load_env, run_stage_a

        _load_env()
        link_frozen_ocr()
        run_stage_a(CACHE, OUT, reuse_ocr=True)
        return 0
    if args.command == "estimate":
        estimate = estimate_new_chunks()
        print(json.dumps({k: estimate[k] for k in estimate if k != "plans"}, indent=2))
        return 0
    if args.command == "extract":
        extract_new()
        return 0
    write_audit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
