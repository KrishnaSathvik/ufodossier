"""
Local corpus readiness runner (OCR → classify → optional extract → dedupe).

LOCAL ONLY. Never writes to Supabase.

Usage:
  # Stage A (OCR + classify):
  python -m pipeline.local_readiness --cache .cache/files/pursue/r3 \\
      --out-dir pipeline/reports/r3_readiness --stage a

  # Stage B (extract classifier-approved):
  python -m pipeline.local_readiness --cache .cache/files/pursue/r3 \\
      --out-dir pipeline/reports/r3_readiness --stage b --label v1
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def run_stage_a(
    cache: Path,
    out_dir: Path,
    force_ocr_all: bool = False,
    reuse_ocr: bool = False,
) -> dict[str, Any]:
    from pipeline.classify_document import classify_text, _meta_from_filename
    from pipeline.local_ocr import process_pdf

    ocr_root = out_dir / "ocr"
    ocr_root.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(cache.glob("*.pdf"))
    rows = []
    t0 = time.monotonic()

    for pdf in pdfs:
        logger.info("stage A: %s", pdf.name)
        existing_combined = ocr_root / pdf.stem / "combined.txt"
        existing_report = ocr_root / pdf.stem / "page_report.json"
        if reuse_ocr and existing_combined.exists() and existing_report.exists():
            ocr_report = json.loads(existing_report.read_text())
            logger.info("reusing OCR for %s", pdf.name)
        else:
            ocr_report = process_pdf(pdf, out_dir=ocr_root, force_ocr_all=force_ocr_all)
        combined = Path(ocr_report["combined_path"])
        text = combined.read_text() if combined.exists() else ""
        meta = _meta_from_filename(pdf.name)
        clf = classify_text(
            title=meta["title"],
            filename=pdf.name,
            text=text,
            agency=meta["agency"],
            page_count=ocr_report["page_count"],
            byte_size=pdf.stat().st_size,
        )
        stats = ocr_report.get("stats") or {}
        rows.append(
            {
                "filename": pdf.name,
                "external_id": meta["external_id"],
                "agency": meta["agency"],
                "byte_size": pdf.stat().st_size,
                "page_count": ocr_report["page_count"],
                "usable_text_chars": ocr_report["usable_text_chars"],
                "native_good_pages": stats.get("native_good", 0),
                "native_thin_pages": stats.get("native_thin", 0),
                "pages_ocrd": stats.get("pages_ocrd", 0),
                "ocr_succeeded": stats.get("ocr_succeeded", 0),
                "ocr_failed": stats.get("ocr_failed", 0),
                "text_path": str(combined),
                "classification": clf.to_dict(),
                "extraction_action": "extract" if clf.contains_incidents else "source_only",
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stage": "a",
        "production_writes": False,
        "cache_dir": str(cache),
        "runtime_seconds": round(time.monotonic() - t0, 1),
        "count": len(rows),
        "extract_count": sum(1 for r in rows if r["extraction_action"] == "extract"),
        "source_only_count": sum(1 for r in rows if r["extraction_action"] == "source_only"),
        "results": rows,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "classifications.json").write_text(json.dumps(report, indent=2) + "\n")
    (out_dir / "text_quality.json").write_text(
        json.dumps(
            {
                "generated_at": report["generated_at"],
                "documents": [
                    {
                        "filename": r["filename"],
                        "page_count": r["page_count"],
                        "usable_text_chars": r["usable_text_chars"],
                        "native_good_pages": r["native_good_pages"],
                        "native_thin_pages": r["native_thin_pages"],
                        "pages_ocrd": r["pages_ocrd"],
                        "ocr_succeeded": r["ocr_succeeded"],
                        "ocr_failed": r["ocr_failed"],
                    }
                    for r in rows
                ],
            },
            indent=2,
        )
        + "\n"
    )
    logger.info(
        "stage A done: %d docs, %d extract, %d source_only, %.1fs",
        len(rows),
        report["extract_count"],
        report["source_only_count"],
        report["runtime_seconds"],
    )
    return report


def run_stage_b(out_dir: Path, label: str = "v1") -> dict[str, Any]:
    from pipeline.extract import JSON_STATS, reset_json_stats
    from pipeline.smoke_r2_extract import (
        CHUNK_PLAN,
        classify_duplicate,
        extract_local,
        fetch_prod_incidents_readonly,
        reset_chunk_plan,
    )

    clf_path = out_dir / "classifications.json"
    data = json.loads(clf_path.read_text())
    results = data["results"]
    incident_bearing = [r for r in results if r["classification"]["contains_incidents"]]
    skipped = [r for r in results if not r["classification"]["contains_incidents"]]

    reset_json_stats()
    reset_chunk_plan()
    t0 = time.monotonic()
    all_validated: list[dict] = []
    all_quote_rej: list[dict] = []
    all_evidence_rej: list[dict] = []

    for r in incident_bearing:
        text = Path(r["text_path"]).read_text() if Path(r["text_path"]).exists() else ""
        sf_stub = {
            "filename": r["filename"],
            "agency": r.get("agency"),
            "file_type": "pdf",
            "id": f"local:{r['filename']}",
        }
        logger.info("extract %s (%d chars)", r["filename"], len(text))
        validated, quote_rej, evidence_rej = extract_local(sf_stub, text)
        for v in validated:
            v["source_external_id"] = r.get("external_id")
            v["document_class"] = r["classification"]["document_class"]
            v["text_source"] = r["text_path"]
        all_validated.extend(validated)
        all_quote_rej.extend(quote_rej)
        all_evidence_rej.extend(evidence_rej)
        logger.info(
            "  -> accepted=%d quote_rej=%d evidence_rej=%d",
            len(validated),
            len(quote_rej),
            len(evidence_rej),
        )

    production = fetch_prod_incidents_readonly() if all_validated else []
    dup_rows = []
    for cand in all_validated:
        d = classify_duplicate(cand, production)
        # Enrich statuses for readiness reporting
        status = d["duplicate_status"]
        if status == "likely_duplicate":
            pass
        elif status == "uncertain":
            pass
        elif d["best_match_score"] >= 0.60:
            # Possible same-event/new-source cluster — surface for review
            d["duplicate_status"] = "same_event_new_source"
            d["review_required"] = True
            status = "same_event_new_source"
        cand["duplicate"] = d
        dup_rows.append(
            {
                "case_id": cand.get("case_id"),
                "title": cand.get("title"),
                "source_filename": cand.get("source_filename"),
                "occurred_at": cand.get("occurred_at"),
                "location_text": cand.get("location_text"),
                **d,
            }
        )

    runtime = round(time.monotonic() - t0, 1)
    # Rough Haiku cost: ~$0.001/1k input + $0.005/1k output; ballpark from calls
    haiku_calls = JSON_STATS["json_first_pass"] + JSON_STATS["json_retry_success"] + JSON_STATS["json_retry_failed"]
    # Prefer first_pass + retries as total model calls
    model_calls = JSON_STATS["json_first_pass"] + JSON_STATS["json_retry_success"] + JSON_STATS["json_retry_failed"]
    # Actually first_pass counts successes; failed first then retry: better estimate:
    # each chunk = 1 call minimum; retries add. Use sum of all counters as lower bound on calls...
    # json_first_pass = successful first attempts; json_retry_* = second attempts.
    # Total calls ≈ first_pass + retry_success + retry_failed + (retries that followed failures)
    # When first fails, first_pass doesn't increment, then retry runs.
    # So total calls = (chunks that succeeded first) + 2*(chunks that needed retry)
    # ≈ json_first_pass + 2*(json_retry_success + json_retry_failed)
    total_calls = JSON_STATS["json_first_pass"] + 2 * (
        JSON_STATS["json_retry_success"] + JSON_STATS["json_retry_failed"]
    )
    estimated_cost_usd = round(total_calls * 0.02, 3)  # conservative per-call ballpark

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "stage": "b",
        "production_writes": False,
        "documents_considered": len(results),
        "documents_source_only": len(skipped),
        "documents_extracted": len(incident_bearing),
        "candidate_incidents": len(all_validated) + len(all_quote_rej) + len(all_evidence_rej),
        "quote_valid_incidents": len(all_validated) + len(all_evidence_rej),
        "quote_rejected_incidents": len(all_quote_rej),
        "evidence_insufficient": len(all_evidence_rej),
        "incidents_accepted": len(all_validated),
        "new_event": sum(1 for d in dup_rows if d["duplicate_status"] == "new_event"),
        "same_event_new_source": sum(1 for d in dup_rows if d["duplicate_status"] == "same_event_new_source"),
        "likely_duplicate": sum(1 for d in dup_rows if d["duplicate_status"] == "likely_duplicate"),
        "uncertain": sum(1 for d in dup_rows if d["duplicate_status"] == "uncertain"),
        "json_stats": dict(JSON_STATS),
        "estimated_haiku_calls": total_calls,
        "estimated_haiku_cost_usd": estimated_cost_usd,
        "runtime_seconds": runtime,
        "production_incidents_compared": len(production),
        "chunk_plan": list(CHUNK_PLAN),
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
    (out_dir / f"extractions_{label}.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    (out_dir / "extractions.json").write_text(json.dumps(out, indent=2, default=str) + "\n")
    (out_dir / "dedupe_candidates.json").write_text(
        json.dumps(
            {
                "generated_at": summary["generated_at"],
                "production_writes": False,
                "triage": dup_rows,
                "clusters_note": "No auto-merge. Review same_event_new_source / uncertain / likely_duplicate.",
            },
            indent=2,
            default=str,
        )
        + "\n"
    )
    (out_dir / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    _write_colorado_springs_cluster(out_dir, results, all_validated)
    logger.info("stage B summary: %s", json.dumps(summary, indent=2))
    return out


# Named fixture for the first multi-source cluster. Not a general linker.
_COLORADO_SPRINGS_ROLES = {
    "FBI-UAP-D002.pdf": "primary_narrative",
    "FBI-UAP-D003.pdf": "media",
    "ICA-UAP-D001.pdf": "analysis",
}


def _write_colorado_springs_cluster(
    out_dir: Path,
    classifications: list[dict],
    accepted: list[dict],
) -> None:
    by_name = {r["filename"]: r for r in classifications}
    accepted_names = {a.get("source_filename") for a in accepted}
    members = []
    for filename, role in _COLORADO_SPRINGS_ROLES.items():
        row = by_name.get(filename)
        if not row:
            continue
        clf = row["classification"]
        members.append(
            {
                "filename": filename,
                "role": role,
                "document_class": clf["document_class"],
                "contains_incidents": clf["contains_incidents"],
                "extraction_action": row["extraction_action"],
                "accepted_incidents": sum(1 for a in accepted if a.get("source_filename") == filename),
            }
        )
    primary_ok = "FBI-UAP-D002.pdf" in accepted_names
    media_ok = any(
        m["filename"] == "FBI-UAP-D003.pdf" and m["document_class"] == "media_metadata" and not m["contains_incidents"]
        for m in members
    )
    analysis_ok = any(
        m["filename"] == "ICA-UAP-D001.pdf" and m["document_class"] == "analysis" and not m["contains_incidents"]
        for m in members
    )
    linked_sources = int(media_ok) + int(analysis_ok)
    payload = {
        "cluster_id": "colorado-springs-2022",
        "note": (
            "Reviewed source-role fixture for one event. "
            "Not a generalized canonical linker and not an auto-merge."
        ),
        "production_writes": False,
        "primary_recovered": primary_ok,
        "linked_sources": linked_sources,
        "duplicate_incident_inflation": sum(
            m["accepted_incidents"] for m in members if m["role"] != "primary_narrative"
        ),
        "members": members,
    }
    (out_dir / "colorado_springs_cluster.json").write_text(json.dumps(payload, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local corpus readiness (no prod writes)")
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--stage", choices=["a", "b", "all"], default="all")
    parser.add_argument("--label", default="v1")
    parser.add_argument("--force-ocr-all", action="store_true")
    parser.add_argument(
        "--reuse-ocr",
        action="store_true",
        help="Reuse existing combined.txt / page_report.json instead of re-OCR",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    _load_env()

    if not args.cache.exists():
        logger.error("cache missing: %s", args.cache)
        return 1

    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.stage in ("a", "all"):
        run_stage_a(
            args.cache,
            args.out_dir,
            force_ocr_all=args.force_ocr_all,
            reuse_ocr=args.reuse_ocr,
        )
    if args.stage in ("b", "all"):
        if not (args.out_dir / "classifications.json").exists():
            logger.error("run stage a first")
            return 1
        run_stage_b(args.out_dir, label=args.label)
    return 0


if __name__ == "__main__":
    sys.exit(main())
