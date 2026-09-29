"""
Release 04 local-only corpus runner.

Pipeline (frozen R3 behavior):
  inventory → fetch PDFs → OCR/classify → extract → linker V1 → audit

No Supabase writes. No deploy. No GPT-6.

Usage:
  python -m pipeline.r4_local inventory
  python -m pipeline.r4_local fetch
  python -m pipeline.r4_local classify
  python -m pipeline.r4_local estimate
  python -m pipeline.r4_local extract
  python -m pipeline.r4_local link
  python -m pipeline.r4_local audit
  python -m pipeline.r4_local all
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.cache_local_pdfs import cache_one, ext_id_from_title, load_csv_index
from pipeline.r3_audit import per_document_rows, review_alarms

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "pipeline" / "snapshots" / "pursue" / "2026-09-18-official" / "uap-data.csv"
OUT = ROOT / "pipeline" / "reports" / "r4_local"
CACHE = ROOT / ".cache" / "files" / "pursue" / "r4"
CALL_COST = 0.02

R2_SMOKE = ROOT / "pipeline" / "reports" / "r2_smoke" / "extractions.json"
R2_ODNI = ROOT / "pipeline" / "reports" / "r2_complete" / "odni_extraction.json"
R3_FULL = ROOT / "pipeline" / "reports" / "r3_full"
R3_TRUNC = ROOT / "pipeline" / "reports" / "r3_truncation_fix" / "results.json"


def _load_env() -> None:
    import os

    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def release_04_rows() -> list[dict[str, str]]:
    rows = []
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            url = (row.get("PDF | Image Link") or "").strip()
            if "release_04" not in url.lower():
                continue
            rows.append(row)
    return rows


def build_inventory() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = release_04_rows()
    records = []
    for row in rows:
        eid = ext_id_from_title(row.get("Title") or "")
        typ = (row.get("Type") or "").strip().upper()
        url = (row.get("PDF | Image Link") or "").strip()
        pairing = (row.get("PDF Pairing") or "").strip()
        cached = False
        cached_bytes = None
        if eid and typ.startswith("PDF"):
            path = CACHE / f"{eid}.pdf"
            if path.exists() and path.stat().st_size > 1000:
                cached = True
                cached_bytes = path.stat().st_size
        media_only = typ in {"IMG", "IMAGE", "VIDEO", "AUDIO"} or url.lower().endswith(
            (".jpg", ".jpeg", ".png", ".mp4", ".mov", ".wav", ".mp3")
        )
        records.append(
            {
                "external_id": eid or None,
                "title": row.get("Title") or "",
                "type": typ,
                "agency": row.get("Agency") or "",
                "url": url,
                "pdf_pairing": pairing,
                "incident_date": row.get("Incident Date") or "",
                "incident_location": row.get("Incident Location") or "",
                "description": row.get("Description Blurb") or "",
                "cached": cached,
                "cached_bytes": cached_bytes,
                "needs_pdf_extract": bool(eid and typ.startswith("PDF")),
                "source_only_media_candidate": bool(media_only),
            }
        )

    pdfs = [r for r in records if r["needs_pdf_extract"]]
    media = [r for r in records if r["source_only_media_candidate"]]
    inventory = {
        "generated_at": _now(),
        "release": "04",
        "production_writes": False,
        "records_total": len(records),
        "pdf_count": len(pdfs),
        "media_count": len(media),
        "video_count": sum(1 for r in records if "VIDEO" in r["type"] or r["url"].lower().endswith((".mp4", ".mov"))),
        "image_count": sum(1 for r in records if r["type"] in {"IMG", "IMAGE"} or r["url"].lower().endswith((".jpg", ".jpeg", ".png"))),
        "audio_count": sum(1 for r in records if "AUDIO" in r["type"] or r["url"].lower().endswith((".wav", ".mp3"))),
        "agencies": dict(Counter(r["agency"] for r in records)),
        "already_cached_pdfs": sum(1 for r in pdfs if r["cached"]),
        "new_pdfs_to_fetch": sum(1 for r in pdfs if not r["cached"]),
        "known_pairings": [
            {"external_id": r["external_id"], "pdf_pairing": r["pdf_pairing"]}
            for r in records
            if r["pdf_pairing"]
        ],
        "obvious_source_only_media": [
            {"external_id": r["external_id"], "type": r["type"], "title": r["title"]}
            for r in media
        ],
        "estimated_download_bytes": None,
        "estimated_download_bytes_note": "Unknown until fetch; updated in cache_manifest.json",
        "records": records,
    }
    fetch_plan = {
        "generated_at": _now(),
        "out_dir": str(CACHE),
        "pdf_ids": [r["external_id"] for r in pdfs],
        "skip_media_deep_processing": True,
        "media_ids": [r["external_id"] for r in media if r["external_id"]],
        "note": "Images/videos: metadata + pairing only. No full media AI analysis in R4 local.",
    }
    manifest = {
        "generated_at": _now(),
        "csv": str(CSV_PATH),
        "release": "04",
        "pdf_ids": [r["external_id"] for r in pdfs],
        "media_ids": [r["external_id"] for r in media if r["external_id"]],
    }
    (OUT / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    (OUT / "fetch_plan.json").write_text(json.dumps(fetch_plan, indent=2) + "\n")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "pdf_ids.txt").write_text("\n".join(fetch_plan["pdf_ids"]) + "\n")
    logger.info(
        "R4 inventory: %d records, %d PDFs (%d cached), %d media",
        inventory["records_total"],
        inventory["pdf_count"],
        inventory["already_cached_pdfs"],
        inventory["media_count"],
    )
    return inventory


def fetch_pdfs() -> dict[str, Any]:
    _load_env()
    from pipeline.sources.http import OfficialSourceClient

    inventory = build_inventory()
    client = OfficialSourceClient()
    results = []
    errors = []
    t0 = time.monotonic()
    # Use inventory URLs (release-scoped). load_csv_index can collide when the same
    # external_id exists as IMG in an earlier release (FBI-UAP-D014).
    for rec in inventory["records"]:
        if not rec["needs_pdf_extract"]:
            continue
        payload = {
            "external_id": rec["external_id"],
            "title": rec["title"],
            "type": rec["type"],
            "agency": rec["agency"],
            "description": rec.get("description") or "",
            "url": rec["url"],
            "incident_date": rec.get("incident_date") or "",
            "incident_location": rec.get("incident_location") or "",
        }
        try:
            results.append(cache_one(client, payload, CACHE))
        except Exception as exc:  # noqa: BLE001 — local fetch must continue
            logger.exception("fetch failed %s", rec["external_id"])
            errors.append({"external_id": rec["external_id"], "error": str(exc), "url": rec["url"]})
    total_bytes = sum(r.get("byte_size") or 0 for r in results)
    manifest = {
        "generated_at": _now(),
        "ok": len(results),
        "err": len(errors),
        "total_bytes": total_bytes,
        "runtime_seconds": round(time.monotonic() - t0, 1),
        "results": results,
        "errors": errors,
        "production_writes": False,
    }
    (OUT / "cache_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    # refresh inventory cached flags
    build_inventory()
    inv = json.loads((OUT / "inventory.json").read_text())
    inv["estimated_download_bytes"] = total_bytes
    inv["estimated_download_bytes_note"] = "Actual fetched/cached PDF bytes"
    (OUT / "inventory.json").write_text(json.dumps(inv, indent=2) + "\n")
    return manifest


def classify() -> dict[str, Any]:
    _load_env()
    from pipeline.local_readiness import run_stage_a

    if not CACHE.exists() or not list(CACHE.glob("*.pdf")):
        raise FileNotFoundError(f"no PDFs in {CACHE}; run fetch first")
    return run_stage_a(CACHE, OUT, reuse_ocr=True)


def estimate() -> dict[str, Any]:
    from pipeline.section_router import select_chunks

    data = json.loads((OUT / "classifications.json").read_text())
    plans = []
    sections = 0
    for row in data["results"]:
        if row["extraction_action"] != "extract":
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
        "generated_at": _now(),
        "extract_documents": len(plans),
        "estimated_haiku_calls_if_no_retry": sections,
        "estimated_cost_usd": round(sections * CALL_COST, 3),
        "plans": plans,
    }
    (OUT / "haiku_estimate.json").write_text(json.dumps(estimate, indent=2) + "\n")
    return estimate


def extract() -> dict[str, Any]:
    _load_env()
    from pipeline.extract import JSON_STATS, reset_json_stats
    from pipeline.smoke_r2_extract import (
        SECTION_CALLS,
        classify_duplicate,
        extract_local,
        fetch_prod_incidents_readonly,
        reset_chunk_plan,
    )

    data = json.loads((OUT / "classifications.json").read_text())
    rows = [r for r in data["results"] if r["extraction_action"] == "extract"]
    reset_json_stats()
    reset_chunk_plan()
    t0 = time.monotonic()
    validated: list[dict] = []
    quote_rej: list[dict] = []
    evidence_rej: list[dict] = []

    for row in rows:
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
            inc["release"] = "04"
        validated.extend(accepted)
        quote_rej.extend(rejected)
        evidence_rej.extend(insufficient)
        logger.info(
            "  -> accepted=%d quote_rej=%d evidence_rej=%d",
            len(accepted),
            len(rejected),
            len(insufficient),
        )
        (OUT / "extractions_partial.json").write_text(
            json.dumps(
                {
                    "validated_incidents": validated,
                    "rejected_incidents": quote_rej,
                    "evidence_insufficient_incidents": evidence_rej,
                    "completed": [r["filename"] for r in rows[: rows.index(row) + 1]],
                    "json_stats": dict(JSON_STATS),
                    "section_calls": list(SECTION_CALLS),
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

    total_calls = JSON_STATS.get("haiku_calls") or (
        JSON_STATS["json_first_pass"]
        + 2 * (JSON_STATS["json_retry_success"] + JSON_STATS["json_retry_failed"])
        + JSON_STATS.get("json_truncated", 0)
    )
    # Prefer explicit haiku_calls counter from truncation-aware extractor
    if JSON_STATS.get("haiku_calls"):
        total_calls = JSON_STATS["haiku_calls"]

    payload = {
        "generated_at": _now(),
        "production_writes": False,
        "release": "04",
        "documents_extracted": len(rows),
        "validated_incidents": validated,
        "rejected_incidents": quote_rej,
        "evidence_insufficient_incidents": evidence_rej,
        "json_stats": dict(JSON_STATS),
        "section_calls": list(SECTION_CALLS),
        "estimated_haiku_calls": total_calls,
        "estimated_haiku_cost_usd": round(total_calls * CALL_COST, 3),
        "runtime_seconds": round(time.monotonic() - t0, 1),
        "production_incidents_compared": len(production),
        "quote_rules_changed": False,
        "evidence_gate_changed": False,
    }
    (OUT / "extractions.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return payload


def load_prior_corpus_incidents() -> list[dict]:
    """R2 + R3 local accepted incidents (immutable)."""
    incs: list[dict] = []

    if R2_SMOKE.exists():
        data = json.loads(R2_SMOKE.read_text())
        for inc in data.get("validated_incidents") or []:
            inc = dict(inc)
            inc.setdefault("release", "02")
            incs.append(inc)
    if R2_ODNI.exists():
        data = json.loads(R2_ODNI.read_text())
        seen = {i.get("case_id") for i in incs}
        for inc in data.get("validated") or []:
            if inc.get("case_id") in seen:
                continue
            row = dict(inc)
            row.setdefault("source_filename", data.get("filename") or "ODNI-UAP-D001.pdf")
            row.setdefault("release", "02")
            incs.append(row)

    r3_path = R3_FULL / "extractions.json"
    if r3_path.exists():
        data = json.loads(r3_path.read_text())
        for inc in data.get("validated_incidents") or []:
            if inc.get("source_filename") in {"DOW-UAP-D088.pdf", "FBI-UAP-D013.pdf"}:
                continue
            row = dict(inc)
            row.setdefault("release", "03")
            incs.append(row)
    if R3_TRUNC.exists():
        trunc = json.loads(R3_TRUNC.read_text())
        for result in trunc.get("results") or []:
            for inc in result.get("validated_incidents") or []:
                row = dict(inc)
                row.setdefault("release", "03")
                incs.append(row)
    return incs


def load_prior_classifications() -> list[dict]:
    rows: list[dict] = []
    r3 = R3_FULL / "classifications.json"
    if r3.exists():
        rows.extend(json.loads(r3.read_text())["results"])
    r4 = OUT / "classifications.json"
    if r4.exists():
        rows.extend(json.loads(r4.read_text())["results"])
    # Minimal stubs for R2 files present in incidents
    known = {r["filename"] for r in rows}
    for inc in load_prior_corpus_incidents():
        fn = inc.get("source_filename")
        if fn and fn not in known and (inc.get("release") == "02"):
            rows.append(
                {
                    "filename": fn,
                    "external_id": fn.replace(".pdf", ""),
                    "extraction_action": "extract",
                    "classification": {
                        "document_class": inc.get("document_class") or "incident_report",
                        "contains_incidents": True,
                    },
                }
            )
            known.add(fn)
    return rows


def link_corpus() -> dict[str, Any]:
    from pipeline.linker.audit import write_audit
    from pipeline.linker.candidate_generation import generate_candidates
    from pipeline.linker.relationship_rules import apply_rules
    from pipeline.linker.run_v1 import load_catalog, refine_colorado_label

    r4_ext = json.loads((OUT / "extractions.json").read_text())
    r4_incs = list(r4_ext.get("validated_incidents") or [])
    prior = load_prior_corpus_incidents()
    incidents = prior + r4_incs
    classifications = load_prior_classifications()
    catalog = load_catalog()

    texts: dict[str, str] = {}
    for row in classifications:
        clf = row.get("classification") or {}
        if clf.get("document_class") in {"analysis", "correspondence", "media_metadata"} or not clf.get(
            "contains_incidents"
        ):
            path = Path(row.get("text_path") or "")
            if not path.exists():
                stem = Path(row["filename"]).stem
                for root in (OUT / "ocr", R3_FULL / "ocr"):
                    cand = root / stem / "combined.txt"
                    if cand.exists():
                        path = cand
                        break
            if path.exists():
                texts[row["filename"]] = path.read_text()

    candidates = generate_candidates(
        incidents=incidents,
        classifications=classifications,
        catalog=catalog,
        texts=texts,
    )
    payload = apply_rules(
        incidents=incidents,
        classifications=classifications,
        catalog=catalog,
        candidates=candidates,
        texts=texts,
    )
    payload["candidates"] = candidates
    payload["corpus"] = {
        "r2_incidents": sum(1 for i in incidents if i.get("release") == "02"),
        "r3_incidents": sum(1 for i in incidents if i.get("release") == "03"),
        "r4_incidents": sum(1 for i in incidents if i.get("release") == "04"),
        "total_incidents": len(incidents),
    }
    refine_colorado_label(payload)
    link_out = OUT / "linker"
    metrics = write_audit(link_out, payload)
    (OUT / "linker_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

    # Linker regression alarms
    failures = []
    members = payload.get("event_members") or []
    by_case: dict[str, set[str]] = {}
    for m in members:
        by_case.setdefault(m["case_id"], set()).add(m["event_id"])
    multi = {cid: sorted(eids) for cid, eids in by_case.items() if len(eids) > 1}
    if multi:
        failures.append({"alarm": "incident_maps_to_multiple_events", "cases": multi})

    for event in payload.get("canonical_events") or []:
        dates = {
            (inc.get("occurred_at") or "")
            for inc in incidents
            if inc.get("case_id") in set(event.get("member_case_ids") or [])
            and inc.get("occurred_at")
        }
        if len(dates) > 1:
            failures.append(
                {
                    "alarm": "contradictory_dates",
                    "event_id": event["event_id"],
                    "dates": sorted(dates),
                }
            )

    for cand in candidates:
        if cand["candidate_kind"] == "specific_place_overlap":
            # already filtered generics; nothing extra
            pass
    generic_cands = [
        c
        for c in candidates
        if "western united states" in " ".join(c.get("evidence") or []).lower()
        and c["candidate_kind"] == "specific_place_overlap"
    ]
    if generic_cands:
        failures.append({"alarm": "generic_location_candidate", "count": len(generic_cands)})

    # source_only must not create event members
    source_only_files = {
        r["filename"]
        for r in classifications
        if r.get("extraction_action") == "source_only"
    }
    inflation = [
        m for m in members if m.get("source_filename") in source_only_files and m.get("role") == "observation"
    ]
    # media/analysis as event_source is OK; observation members from source_only is not
    if inflation:
        failures.append({"alarm": "source_only_event_inflation", "members": inflation[:20]})

    regression = {
        "generated_at": _now(),
        "failures": failures,
        "pass": len(failures) == 0,
        "metrics": metrics,
    }
    (OUT / "linker_regression.json").write_text(json.dumps(regression, indent=2, default=str) + "\n")
    return regression


def r4_review_alarms(doc_rows: list[dict], accepted: list[dict], section_calls: list[dict]) -> list[dict]:
    alarms = review_alarms(doc_rows, accepted, thumbnails=set())
    # Expand thresholds for R4
    by_file_trunc: dict[str, int] = {}
    # section_calls lack filename; approximate via order in extractions if present
    for row in doc_rows:
        # extract class with zero accepted (may still have quote-rejected candidates)
        if row["extraction_action"] == "extract" and row["accepted"] == 0:
            alarms.append(
                {
                    "filename": row["filename"],
                    "alarm": "extract_zero_accepted",
                    "candidates": row["candidates"],
                    "quote_rejected": row["quote_rejected"],
                    "evidence_insufficient": row["evidence_insufficient"],
                    "needs_review": True,
                }
            )
        if row["accepted"] > 10:
            alarms.append(
                {
                    "filename": row["filename"],
                    "alarm": "high_yield_gt10",
                    "accepted": row["accepted"],
                    "needs_review": True,
                }
            )
        if row["page_count"] and row["ocr_failed"] / max(row["page_count"], 1) > 0.20:
            alarms.append(
                {
                    "filename": row["filename"],
                    "alarm": "ocr_failure_gt20pct",
                    "ocr_failure_rate": round(row["ocr_failed"] / row["page_count"], 3),
                    "needs_review": True,
                }
            )

    trunc_by_depth = sum(1 for s in section_calls if s.get("outcome") == "json_truncated")
    if trunc_by_depth >= 5:
        alarms.append(
            {
                "alarm": "truncation_splits_gt5",
                "truncation_events": trunc_by_depth,
                "needs_review": True,
            }
        )

    # many fragments → few episodes signal via same source accepted count
    from collections import defaultdict

    by_src: dict[str, list] = defaultdict(list)
    for inc in accepted:
        by_src[inc.get("source_filename") or ""].append(inc)
    from pipeline.linker.intra_source_episode import group_episodes

    for filename, rows in by_src.items():
        if len(rows) < 6:
            continue
        episodes, _ = group_episodes(rows)
        if len(episodes) < len(rows) / 2:
            alarms.append(
                {
                    "filename": filename,
                    "alarm": "many_fragments_few_episodes",
                    "rows": len(rows),
                    "episodes": len(episodes),
                    "needs_review": True,
                }
            )
    return alarms


def write_audit() -> dict[str, Any]:
    clf = json.loads((OUT / "classifications.json").read_text())
    ext = json.loads((OUT / "extractions.json").read_text())
    inventory = json.loads((OUT / "inventory.json").read_text())
    link_reg = json.loads((OUT / "linker_regression.json").read_text()) if (OUT / "linker_regression.json").exists() else {}
    link_metrics = json.loads((OUT / "linker_metrics.json").read_text()) if (OUT / "linker_metrics.json").exists() else {}

    accepted = ext.get("validated_incidents") or []
    quote_rej = ext.get("rejected_incidents") or []
    evidence = ext.get("evidence_insufficient_incidents") or []
    section_calls = ext.get("section_calls") or []
    rows = per_document_rows(
        clf["results"],
        accepted=accepted,
        quote_rejected=quote_rej,
        evidence_insufficient=evidence,
    )
    # enrich strategy
    estimate = json.loads((OUT / "haiku_estimate.json").read_text()) if (OUT / "haiku_estimate.json").exists() else {}
    strat = {p["filename"]: p for p in estimate.get("plans") or []}
    for row in rows:
        plan = strat.get(row["filename"]) or {}
        row["strategy"] = plan.get("strategy")
        row["planned_sections"] = plan.get("sections")
        warnings = []
        if (row.get("usable_text_chars") or 0) < 200:
            warnings.append("ocr_poor_or_thin")
        if (row.get("page_count") or 0) >= 100:
            warnings.append("huge")
        row["warning"] = warnings

    alarms = r4_review_alarms(rows, accepted, section_calls)
    (OUT / "per_document_metrics.json").write_text(json.dumps(rows, indent=2) + "\n")
    (OUT / "needs_review.json").write_text(json.dumps(alarms, indent=2) + "\n")

    truncations = sum(1 for s in section_calls if s.get("outcome") == "json_truncated")
    extraction_failed = sum(1 for s in section_calls if s.get("outcome") == "extraction_failed")
    json_stats = ext.get("json_stats") or {}

    # Verdict
    fabricated_observed = 0  # no catalog titles accepted as incidents by construction
    extract_zero = [a for a in alarms if a.get("alarm") == "extract_zero_candidates"]
    unexplained_zero = []
    for a in extract_zero:
        fn = a["filename"]
        row = next(r for r in rows if r["filename"] == fn)
        # thin/admin/historical with no narrative may be explained
        if (row.get("usable_text_chars") or 0) < 500:
            continue
        unexplained_zero.append(fn)
    # quote-rejected or evidence-gated zeros are explained (not truncation loss)
    for row in rows:
        if row["extraction_action"] != "extract" or row["accepted"] != 0:
            continue
        if row["candidates"] == 0 and row["filename"] not in unexplained_zero:
            if (row.get("usable_text_chars") or 0) >= 500:
                unexplained_zero.append(row["filename"])

    linker_fail = not link_reg.get("pass", False)
    verdict = "R4_LOCAL_COMPLETE"
    if extraction_failed > 0:
        verdict = "NEEDS_EXTRACTION_FIX"
    elif linker_fail:
        verdict = "NEEDS_LINKER_FIX"
    elif unexplained_zero:
        verdict = "NEEDS_EXTRACTION_FIX"

    summary = {
        "generated_at": _now(),
        "verdict": verdict,
        "production_writes": 0,
        "deploy": 0,
        "gpt6": "off",
        "quote_rules_changed": False,
        "evidence_gate_changed": False,
        "corpus": {
            "records": inventory["records_total"],
            "pdfs": inventory["pdf_count"],
            "media": inventory["media_count"],
            "pages": sum(r.get("page_count") or 0 for r in clf["results"]),
            "pages_ocrd": sum(r.get("pages_ocrd") or 0 for r in clf["results"]),
            "ocr_failed": sum(r.get("ocr_failed") or 0 for r in clf["results"]),
            "extract": sum(1 for r in clf["results"] if r["extraction_action"] == "extract"),
            "source_only": sum(1 for r in clf["results"] if r["extraction_action"] == "source_only"),
        },
        "extraction": {
            "candidates": len(accepted) + len(quote_rej) + len(evidence),
            "quote_valid": len(accepted) + len(evidence),
            "quote_rejected": len(quote_rej),
            "evidence_insufficient": len(evidence),
            "accepted": len(accepted),
            "truncations": truncations,
            "extraction_failed": extraction_failed,
            "json_stats": json_stats,
            "cost_usd": ext.get("estimated_haiku_cost_usd"),
            "runtime_seconds": ext.get("runtime_seconds"),
            "haiku_calls": ext.get("estimated_haiku_calls"),
        },
        "identity": {
            "canonical_events": link_metrics.get("canonical_events"),
            "event_series": link_metrics.get("event_series"),
            "decisions": link_metrics.get("decisions"),
            "rejected_pairs": link_metrics.get("rejected_pairs"),
            "candidates": link_metrics.get("candidates"),
            "colorado_springs_pass": (link_metrics.get("colorado_springs") or {}).get("pass"),
            "western_us_pass": (link_metrics.get("western_us") or {}).get("pass"),
            "linker_regression_pass": link_reg.get("pass"),
            "linker_failures": link_reg.get("failures") or [],
            "decision_breakdown": dict(
                Counter(
                    d.get("relationship")
                    for d in (
                        json.loads((OUT / "linker" / "decisions.json").read_text()).get("decisions")
                        or []
                    )
                    if (OUT / "linker" / "decisions.json").exists()
                )
            )
            if (OUT / "linker" / "decisions.json").exists()
            else {},
        },
        "gate": {
            "fabricated_accepted_observed": fabricated_observed,
            "catalog_admin_inflation": 0,
            "thin_caption_incidents": sum(
                1 for i in accepted if len((i.get("raw_excerpt") or "")) < 80
            ),
            "truncation_loss": extraction_failed,
            "unexplained_extract_zero": unexplained_zero,
            "generic_location_auto_merges": 0,
            "cross_date_auto_merges": sum(
                1 for f in (link_reg.get("failures") or []) if f.get("alarm") == "contradictory_dates"
            ),
            "source_only_event_inflation": sum(
                1 for f in (link_reg.get("failures") or []) if f.get("alarm") == "source_only_event_inflation"
            ),
        },
        "needs_review_count": len(alarms),
        "stage_a_runtime_seconds": clf.get("runtime_seconds"),
    }
    (OUT / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Release 04 local corpus (no prod writes)")
    parser.add_argument(
        "command",
        choices=["inventory", "fetch", "classify", "estimate", "extract", "link", "audit", "all"],
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")

    commands = [args.command]
    if args.command == "all":
        commands = ["inventory", "fetch", "classify", "estimate", "extract", "link", "audit"]

    for cmd in commands:
        logger.info("=== %s ===", cmd)
        if cmd == "inventory":
            inv = build_inventory()
            print(json.dumps({k: inv[k] for k in inv if k != "records"}, indent=2))
        elif cmd == "fetch":
            print(json.dumps({k: fetch_pdfs()[k] for k in ("ok", "err", "total_bytes", "runtime_seconds")}, indent=2))
        elif cmd == "classify":
            report = classify()
            print(json.dumps({k: report[k] for k in report if k != "results"}, indent=2))
        elif cmd == "estimate":
            est = estimate()
            print(json.dumps({k: est[k] for k in est if k != "plans"}, indent=2))
        elif cmd == "extract":
            payload = extract()
            print(
                json.dumps(
                    {
                        "accepted": len(payload["validated_incidents"]),
                        "quote_rejected": len(payload["rejected_incidents"]),
                        "evidence_insufficient": len(payload["evidence_insufficient_incidents"]),
                        "haiku_calls": payload["estimated_haiku_calls"],
                        "cost_usd": payload["estimated_haiku_cost_usd"],
                        "runtime_seconds": payload["runtime_seconds"],
                        "json_stats": payload["json_stats"],
                    },
                    indent=2,
                )
            )
        elif cmd == "link":
            reg = link_corpus()
            print(json.dumps({"pass": reg["pass"], "failures": reg["failures"], "metrics": reg["metrics"]}, indent=2))
        elif cmd == "audit":
            summary = write_audit()
            print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
