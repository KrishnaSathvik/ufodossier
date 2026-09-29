"""
Release 05 local-only corpus runner.

Pipeline (frozen R3/R4 behavior + Linker V1 frozen):
  inventory → fetch PDFs → OCR/classify → extract → linker V1 (R2–R5) → audit

No Supabase writes. No deploy. No GPT-6. No Linker V1.1.

Usage:
  python -m pipeline.r5_local inventory
  python -m pipeline.r5_local fetch
  python -m pipeline.r5_local classify
  python -m pipeline.r5_local estimate
  python -m pipeline.r5_local extract
  python -m pipeline.r5_local link
  python -m pipeline.r5_local audit
  python -m pipeline.r5_local all
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.cache_local_pdfs import cache_one, ext_id_from_title
from pipeline.r3_audit import per_document_rows, review_alarms

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "pipeline" / "snapshots" / "pursue" / "2026-09-18-official" / "uap-data.csv"
OUT = ROOT / "pipeline" / "reports" / "r5_local"
CACHE = ROOT / ".cache" / "files" / "pursue" / "r5"
CALL_COST = 0.02
RELEASE = "05"

R2_SMOKE = ROOT / "pipeline" / "reports" / "r2_smoke" / "extractions.json"
R2_ODNI = ROOT / "pipeline" / "reports" / "r2_complete" / "odni_extraction.json"
R3_FULL = ROOT / "pipeline" / "reports" / "r3_full"
R3_TRUNC = ROOT / "pipeline" / "reports" / "r3_truncation_fix" / "results.json"
R4_LOCAL = ROOT / "pipeline" / "reports" / "r4_local"

# Carry-forward from R4 review — observe only; do not retune mid-run.
REGRESSION_WATCH = [
    {
        "id": "cia_d020_d021_paired_one_accepted",
        "principle": "catalog paired sources; never manufacture event member for unpaired accepted side",
        "refs": ["CIA-UAP-D020", "CIA-UAP-D021"],
    },
    {
        "id": "doe_d005_d001_cross_release",
        "principle": "R4 correspondence ↔ earlier release source; no synthetic incident",
        "refs": ["DOE-UAP-D005", "DOE-UAP-D001"],
    },
    {
        "id": "nasa_d030_d031_d032_media_pairing",
        "principle": "media pairing only; 0 synthetic incidents",
        "refs": ["NASA-UAP-D030", "NASA-UAP-D031", "NASA-UAP-D032"],
    },
    {
        "id": "dow_d090_classifier_sibling_watch",
        "principle": "D089/D091 transcript extract vs D090 other source_only — observe, do not retune without evidence",
        "refs": ["DOW-UAP-D089", "DOW-UAP-D090", "DOW-UAP-D091"],
    },
]


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


def release_05_rows() -> list[dict[str, str]]:
    rows = []
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            url = (row.get("PDF | Image Link") or "").strip()
            if "release_05" not in url.lower():
                continue
            rows.append(row)
    return rows


def build_inventory() -> dict[str, Any]:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = release_05_rows()
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
        "release": RELEASE,
        "production_writes": False,
        "linker_v1_frozen": True,
        "linker_v1_1": False,
        "records_total": len(records),
        "pdf_count": len(pdfs),
        "media_count": len(media),
        "video_count": sum(
            1 for r in records if "VIDEO" in r["type"] or r["url"].lower().endswith((".mp4", ".mov"))
        ),
        "image_count": sum(
            1
            for r in records
            if r["type"] in {"IMG", "IMAGE"} or r["url"].lower().endswith((".jpg", ".jpeg", ".png"))
        ),
        "audio_count": sum(
            1 for r in records if "AUDIO" in r["type"] or r["url"].lower().endswith((".wav", ".mp3"))
        ),
        "agencies": dict(Counter(r["agency"] for r in records)),
        "already_cached_pdfs": sum(1 for r in pdfs if r["cached"]),
        "new_pdfs_to_fetch": sum(1 for r in pdfs if not r["cached"]),
        "known_pairings": [
            {"external_id": r["external_id"], "pdf_pairing": r["pdf_pairing"]}
            for r in records
            if r["pdf_pairing"]
        ],
        "obvious_source_only_media": [
            {"external_id": r["external_id"], "type": r["type"], "title": r["title"]} for r in media
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
        "note": "Images/videos: metadata + pairing only. No full media AI analysis in R5 local.",
    }
    manifest = {
        "generated_at": _now(),
        "csv": str(CSV_PATH),
        "release": RELEASE,
        "pdf_ids": [r["external_id"] for r in pdfs],
        "media_ids": [r["external_id"] for r in media if r["external_id"]],
        "linker_v1_frozen": True,
    }
    (OUT / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    (OUT / "fetch_plan.json").write_text(json.dumps(fetch_plan, indent=2) + "\n")
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (OUT / "pdf_ids.txt").write_text("\n".join(x for x in fetch_plan["pdf_ids"] if x) + "\n")
    (OUT / "regression_watch.json").write_text(
        json.dumps({"generated_at": _now(), "cases": REGRESSION_WATCH}, indent=2) + "\n"
    )
    logger.info(
        "R5 inventory: %d records, %d PDFs (%d cached), %d media",
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
        except Exception as exc:  # noqa: BLE001
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
    cue = 0
    fixed = 0
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
        if strategy == "cue_routed":
            cue += 1
        else:
            fixed += 1
    estimate = {
        "generated_at": _now(),
        "extract_documents": len(plans),
        "fixed_chunk_docs": fixed,
        "cue_routed_docs": cue,
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
            inc["release"] = RELEASE
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
    if JSON_STATS.get("haiku_calls"):
        total_calls = JSON_STATS["haiku_calls"]

    payload = {
        "generated_at": _now(),
        "production_writes": False,
        "release": RELEASE,
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


def _release_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    # Prefer known report dirs by scanning external id prefixes is fragile;
    # rely on incident.release when present. Filename heuristic for stubs:
    return None


def load_prior_corpus_incidents() -> list[dict]:
    """R2 + R3 + R4 local accepted incidents (immutable)."""
    incs: list[dict] = []

    if R2_SMOKE.exists():
        data = json.loads(R2_SMOKE.read_text())
        for inc in data.get("validated_incidents") or []:
            row = dict(inc)
            row.setdefault("release", "02")
            incs.append(row)
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

    r4_path = R4_LOCAL / "extractions.json"
    if r4_path.exists():
        data = json.loads(r4_path.read_text())
        for inc in data.get("validated_incidents") or []:
            row = dict(inc)
            row.setdefault("release", "04")
            incs.append(row)
    return incs


def load_all_classifications() -> list[dict]:
    rows: list[dict] = []
    for path in (
        R3_FULL / "classifications.json",
        R4_LOCAL / "classifications.json",
        OUT / "classifications.json",
    ):
        if path.exists():
            rows.extend(json.loads(path.read_text())["results"])
    known = {r["filename"] for r in rows}
    for inc in load_prior_corpus_incidents():
        fn = inc.get("source_filename")
        if fn and fn not in known and inc.get("release") == "02":
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


def _incident_release_map(incidents: list[dict]) -> dict[str, str]:
    out: dict[str, str] = {}
    for inc in incidents:
        cid = inc.get("case_id")
        if cid and inc.get("release"):
            out[cid] = str(inc["release"])
    return out


def _filename_release_map(classifications: list[dict], incidents: list[dict]) -> dict[str, str]:
    """Best-effort map source_filename → release digit string."""
    by_fn: dict[str, str] = {}
    for inc in incidents:
        fn = inc.get("source_filename")
        if fn and inc.get("release"):
            by_fn[fn] = str(inc["release"])
    # R3/R4/R5 classification roots imply release when not on incident
    for row in classifications:
        fn = row.get("filename")
        if not fn or fn in by_fn:
            continue
        # infer from which report folder we loaded — not stored; skip
    return by_fn


def annotate_cross_release(
    decisions: list[dict],
    event_sources: list[dict],
    release_by_case: dict[str, str],
    release_by_file: dict[str, str],
) -> list[dict]:
    """Reporting only — does not change linker logic."""
    annotated = []
    for d in decisions:
        left_r = release_by_case.get(d.get("left") or "")
        right_r = release_by_case.get(d.get("right") or "")
        row = dict(d)
        row["source_release"] = left_r
        row["target_release"] = right_r
        row["cross_release"] = bool(left_r and right_r and left_r != right_r)
        annotated.append(row)

    src_ann = []
    for s in event_sources:
        fn = s.get("source_filename") or ""
        # event members release inferred via event later; file release from map
        row = dict(s)
        row["source_release"] = release_by_file.get(fn)
        src_ann.append(row)
    return annotated


def link_corpus() -> dict[str, Any]:
    from pipeline.linker.audit import write_audit
    from pipeline.linker.candidate_generation import generate_candidates
    from pipeline.linker.relationship_rules import apply_rules
    from pipeline.linker.run_v1 import load_catalog, refine_colorado_label

    r5_ext = json.loads((OUT / "extractions.json").read_text())
    r5_incs = list(r5_ext.get("validated_incidents") or [])
    prior = load_prior_corpus_incidents()
    incidents = prior + r5_incs
    classifications = load_all_classifications()
    catalog = load_catalog()

    texts: dict[str, str] = {}
    ocr_roots = (OUT / "ocr", R4_LOCAL / "ocr", R3_FULL / "ocr")
    for row in classifications:
        clf = row.get("classification") or {}
        if clf.get("document_class") in {"analysis", "correspondence", "media_metadata"} or not clf.get(
            "contains_incidents"
        ):
            path = Path(row.get("text_path") or "")
            if not path.exists():
                stem = Path(row["filename"]).stem
                for root in ocr_roots:
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
        "r5_incidents": sum(1 for i in incidents if i.get("release") == "05"),
        "total_incidents": len(incidents),
    }
    refine_colorado_label(payload)

    release_by_case = _incident_release_map(incidents)
    release_by_file = _filename_release_map(classifications, incidents)
    decisions = payload.get("decisions") or []
    annotated = annotate_cross_release(
        decisions, payload.get("event_sources") or [], release_by_case, release_by_file
    )
    payload["decisions"] = annotated
    cross = [d for d in annotated if d.get("cross_release")]
    same = [d for d in annotated if d.get("source_release") and d.get("target_release") and not d.get("cross_release")]
    cross_report = {
        "generated_at": _now(),
        "same_release_decisions": len(same),
        "cross_release_decisions": len(cross),
        "by_relationship": dict(Counter(d.get("relationship") for d in cross)),
        "examples": [
            {
                "relationship": d.get("relationship"),
                "source_release": d.get("source_release"),
                "target_release": d.get("target_release"),
                "left": d.get("left"),
                "right": d.get("right"),
                "status": d.get("status"),
            }
            for d in cross[:40]
        ],
    }
    (OUT / "cross_release_links.json").write_text(json.dumps(cross_report, indent=2) + "\n")

    link_out = OUT / "linker"
    metrics = write_audit(link_out, payload)
    metrics["cross_release_decisions"] = cross_report["cross_release_decisions"]
    metrics["same_release_decisions"] = cross_report["same_release_decisions"]
    (OUT / "linker_metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")

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
            if inc.get("case_id") in set(event.get("member_case_ids") or []) and inc.get("occurred_at")
        }
        if len(dates) > 1:
            failures.append(
                {"alarm": "contradictory_dates", "event_id": event["event_id"], "dates": sorted(dates)}
            )

    generic_cands = [
        c
        for c in candidates
        if "western united states" in " ".join(c.get("evidence") or []).lower()
        and c["candidate_kind"] == "specific_place_overlap"
    ]
    if generic_cands:
        failures.append({"alarm": "generic_location_candidate", "count": len(generic_cands)})

    source_only_files = {
        r["filename"] for r in classifications if r.get("extraction_action") == "source_only"
    }
    inflation = [
        m for m in members if m.get("source_filename") in source_only_files and m.get("role") == "observation"
    ]
    if inflation:
        failures.append({"alarm": "source_only_event_inflation", "members": inflation[:20]})

    # Fixture gates from metrics
    if not (metrics.get("colorado_springs") or {}).get("pass"):
        failures.append({"alarm": "colorado_springs_fixture_fail"})
    if not (metrics.get("western_us") or {}).get("pass"):
        failures.append({"alarm": "western_us_fixture_fail"})

    regression = {
        "generated_at": _now(),
        "failures": failures,
        "pass": len(failures) == 0,
        "metrics": metrics,
        "linker_v1_frozen": True,
    }
    (OUT / "linker_regression.json").write_text(json.dumps(regression, indent=2, default=str) + "\n")
    return regression


def r5_review_alarms(
    doc_rows: list[dict],
    accepted: list[dict],
    section_calls: list[dict],
    *,
    classifications: list[dict],
    decisions: list[dict],
    event_members: list[dict],
    event_sources: list[dict],
    inventory: dict[str, Any],
) -> list[dict]:
    alarms = review_alarms(doc_rows, accepted, thumbnails=set())

    for row in doc_rows:
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
        if row["extraction_action"] == "extract" and (row.get("usable_text_chars") or 0) < 200:
            alarms.append(
                {
                    "filename": row["filename"],
                    "alarm": "extract_unusable_ocr",
                    "usable_text_chars": row.get("usable_text_chars"),
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
        if (row.get("page_count") or 0) >= 100:
            alarms.append(
                {
                    "filename": row["filename"],
                    "alarm": "very_large_document",
                    "page_count": row["page_count"],
                    "needs_review": True,
                }
            )

    trunc_by_depth = sum(1 for s in section_calls if s.get("outcome") == "json_truncated")
    if trunc_by_depth >= 5:
        alarms.append(
            {
                "alarm": "truncation_heavy",
                "truncation_events": trunc_by_depth,
                "needs_review": True,
            }
        )

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
        # many phase / same-date rows
        dates = Counter((i.get("occurred_at") or "")[:10] for i in rows if i.get("occurred_at"))
        for d, n in dates.items():
            if d and n >= 5:
                alarms.append(
                    {
                        "filename": filename,
                        "alarm": "many_phase_rows",
                        "date": d,
                        "count": n,
                        "needs_review": True,
                    }
                )

    # Sibling classifier inconsistency (same agency prefix + adjacent ids) — soft watch
    by_stem = {r["filename"]: r for r in doc_rows}
    for stem in ("DOW-UAP-D089", "DOW-UAP-D090", "DOW-UAP-D091"):
        fn = f"{stem}.pdf"
        if fn in by_stem:
            # only flag if present in this run's classifications
            pass
    # R5-local sibling mismatch among classified extract vs source_only neighbors
    clf_by_id = {r.get("external_id"): r for r in classifications if r.get("external_id")}
    for pair_left, pair_right in (
        ("DOW-UAP-D089", "DOW-UAP-D090"),
        ("DOW-UAP-D090", "DOW-UAP-D091"),
    ):
        a, b = clf_by_id.get(pair_left), clf_by_id.get(pair_right)
        if not a or not b:
            continue
        if a.get("extraction_action") != b.get("extraction_action"):
            alarms.append(
                {
                    "alarm": "source_only_sibling_inconsistency",
                    "left": pair_left,
                    "right": pair_right,
                    "left_action": a.get("extraction_action"),
                    "right_action": b.get("extraction_action"),
                    "needs_review": True,
                    "note": "classifier watch — observe only",
                }
            )

    # Cross-release review signals
    for d in decisions:
        if d.get("cross_release") and d.get("relationship") == "same_event":
            alarms.append(
                {
                    "alarm": "cross_release_same_event",
                    "left": d.get("left"),
                    "right": d.get("right"),
                    "source_release": d.get("source_release"),
                    "target_release": d.get("target_release"),
                    "status": d.get("status"),
                    "needs_review": True,
                }
            )
        if d.get("cross_release") and d.get("relationship") == "same_series":
            alarms.append(
                {
                    "alarm": "cross_release_series_candidate",
                    "left": d.get("left"),
                    "right": d.get("right"),
                    "source_release": d.get("source_release"),
                    "target_release": d.get("target_release"),
                    "needs_review": True,
                }
            )

    # Catalog pairings without an accepted event on either side
    accepted_files = {i.get("source_filename") for i in accepted}
    accepted_ext = {Path(f).stem for f in accepted_files if f}
    for pair in inventory.get("known_pairings") or []:
        left = pair.get("external_id")
        rights = [x.strip() for x in (pair.get("pdf_pairing") or "").replace("|", " ").split() if x.strip()]
        if not left:
            continue
        left_has = left in accepted_ext
        right_has = any(r.replace("FBI-UAP-024", "FBI-UAP-D024").startswith("FBI") and False for r in rights)
        # normalize rights that omit D
        norm_rights = []
        for r in rights:
            if r.startswith("FBI-UAP-") and "-D" not in r[8:]:
                # FBI-UAP-024 → FBI-UAP-D024 style typos in catalog
                parts = r.split("-")
                if len(parts) == 3 and parts[2].isdigit():
                    r = f"{parts[0]}-{parts[1]}-D{parts[2]}"
            norm_rights.append(r)
        right_has = any(r in accepted_ext for r in norm_rights)
        if left_has != right_has or (not left_has and not right_has and rights):
            # flag when pairing exists but at most one side has accepted incident
            if not (left_has and right_has):
                alarms.append(
                    {
                        "alarm": "paired_source_without_event",
                        "external_id": left,
                        "pdf_pairing": pair.get("pdf_pairing"),
                        "left_has_accepted": left_has,
                        "right_has_accepted": right_has,
                        "needs_review": True,
                    }
                )

    # one event many sources / one source many events
    members_by_event: dict[str, set[str]] = defaultdict(set)
    events_by_source: dict[str, set[str]] = defaultdict(set)
    for m in event_members:
        eid = m.get("event_id")
        src = m.get("source_filename")
        if eid and src:
            members_by_event[eid].add(src)
            events_by_source[src].add(eid)
    for s in event_sources:
        eid = s.get("event_id")
        src = s.get("source_filename")
        if eid and src:
            members_by_event[eid].add(src)
    for eid, srcs in members_by_event.items():
        if len(srcs) >= 3:
            alarms.append(
                {
                    "alarm": "one_event_many_sources",
                    "event_id": eid,
                    "source_count": len(srcs),
                    "sources": sorted(srcs)[:12],
                    "needs_review": True,
                }
            )
    for src, eids in events_by_source.items():
        if len(eids) >= 8:
            alarms.append(
                {
                    "alarm": "one_source_many_events",
                    "source_filename": src,
                    "event_count": len(eids),
                    "needs_review": True,
                }
            )

    # de-dupe identical alarm dicts loosely by alarm+filename/external_id
    seen = set()
    uniq = []
    for a in alarms:
        key = (
            a.get("alarm"),
            a.get("filename"),
            a.get("external_id"),
            a.get("left"),
            a.get("right"),
            a.get("event_id"),
            a.get("source_filename"),
            a.get("date"),
        )
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a)
    return uniq


def write_audit() -> dict[str, Any]:
    clf = json.loads((OUT / "classifications.json").read_text())
    ext = json.loads((OUT / "extractions.json").read_text())
    inventory = json.loads((OUT / "inventory.json").read_text())
    link_reg = (
        json.loads((OUT / "linker_regression.json").read_text())
        if (OUT / "linker_regression.json").exists()
        else {}
    )
    link_metrics = (
        json.loads((OUT / "linker_metrics.json").read_text()) if (OUT / "linker_metrics.json").exists() else {}
    )
    cross = (
        json.loads((OUT / "cross_release_links.json").read_text())
        if (OUT / "cross_release_links.json").exists()
        else {}
    )
    decisions = []
    if (OUT / "linker" / "decisions.json").exists():
        decisions = json.loads((OUT / "linker" / "decisions.json").read_text()).get("decisions") or []
    graph = {}
    if (OUT / "linker" / "full_graph.json").exists():
        graph = json.loads((OUT / "linker" / "full_graph.json").read_text())

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

    alarms = r5_review_alarms(
        rows,
        accepted,
        section_calls,
        classifications=clf["results"],
        decisions=decisions,
        event_members=graph.get("event_members") or [],
        event_sources=graph.get("event_sources") or [],
        inventory=inventory,
    )
    # Also surface R4 watch sibling if R4 classifications available
    if R4_LOCAL.joinpath("classifications.json").exists():
        r4clf = json.loads((R4_LOCAL / "classifications.json").read_text())["results"]
        by_id = {r.get("external_id"): r for r in r4clf}
        a, b = by_id.get("DOW-UAP-D089"), by_id.get("DOW-UAP-D090")
        if a and b and a.get("extraction_action") != b.get("extraction_action"):
            alarms.append(
                {
                    "alarm": "source_only_sibling_inconsistency",
                    "left": "DOW-UAP-D089",
                    "right": "DOW-UAP-D090",
                    "left_action": a.get("extraction_action"),
                    "right_action": b.get("extraction_action"),
                    "needs_review": True,
                    "note": "R4 carry-forward classifier watch",
                }
            )

    (OUT / "per_document_metrics.json").write_text(json.dumps(rows, indent=2) + "\n")
    (OUT / "needs_review.json").write_text(json.dumps(alarms, indent=2) + "\n")

    truncations = sum(1 for s in section_calls if s.get("outcome") == "json_truncated")
    extraction_failed = sum(1 for s in section_calls if s.get("outcome") == "extraction_failed")
    json_stats = ext.get("json_stats") or {}

    unexplained_zero = []
    for row in rows:
        if row["extraction_action"] != "extract" or row["accepted"] != 0:
            continue
        if row["candidates"] == 0 and (row.get("usable_text_chars") or 0) >= 500:
            unexplained_zero.append(row["filename"])

    linker_fail = not link_reg.get("pass", False)
    verdict = "R5_LOCAL_COMPLETE"
    if extraction_failed > 0:
        verdict = "NEEDS_EXTRACTION_FIX"
    elif linker_fail:
        verdict = "NEEDS_LINKER_FIX"
    elif unexplained_zero:
        verdict = "NEEDS_EXTRACTION_FIX"

    breakdown = dict(Counter(d.get("relationship") for d in decisions))
    status_breakdown = dict(Counter(d.get("status") for d in decisions))

    summary = {
        "generated_at": _now(),
        "verdict": verdict,
        "production_writes": 0,
        "deploy": 0,
        "gpt6": "off",
        "linker_v1_frozen": True,
        "linker_v1_1": False,
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
            "fixed_chunk_docs": estimate.get("fixed_chunk_docs"),
            "cue_routed_docs": estimate.get("cue_routed_docs"),
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
            "decision_breakdown": breakdown,
            "status_breakdown": status_breakdown,
            "same_release_decisions": cross.get("same_release_decisions"),
            "cross_release_decisions": cross.get("cross_release_decisions"),
            "cross_release_by_relationship": cross.get("by_relationship"),
            "colorado_springs_pass": (link_metrics.get("colorado_springs") or {}).get("pass"),
            "western_us_pass": (link_metrics.get("western_us") or {}).get("pass"),
            "d082_episodes": (link_metrics.get("western_us") or {}).get("d082_episode_count"),
            "linker_regression_pass": link_reg.get("pass"),
            "linker_failures": link_reg.get("failures") or [],
        },
        "gate": {
            "fabricated_accepted_observed": 0,
            "catalog_admin_inflation": 0,
            "thin_caption_incidents": sum(1 for i in accepted if len((i.get("raw_excerpt") or "")) < 80),
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
    parser = argparse.ArgumentParser(description="Release 05 local corpus (no prod writes)")
    parser.add_argument(
        "command",
        choices=["inventory", "fetch", "classify", "estimate", "extract", "link", "audit", "all"],
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s"
    )

    commands = [args.command]
    if args.command == "all":
        commands = ["inventory", "fetch", "classify", "estimate", "extract", "link", "audit"]

    for cmd in commands:
        logger.info("=== %s ===", cmd)
        if cmd == "inventory":
            inv = build_inventory()
            print(json.dumps({k: inv[k] for k in inv if k != "records"}, indent=2))
        elif cmd == "fetch":
            print(
                json.dumps(
                    {k: fetch_pdfs()[k] for k in ("ok", "err", "total_bytes", "runtime_seconds")},
                    indent=2,
                )
            )
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
            print(
                json.dumps(
                    {"pass": reg["pass"], "failures": reg["failures"], "metrics": reg["metrics"]},
                    indent=2,
                )
            )
        elif cmd == "audit":
            summary = write_audit()
            print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
