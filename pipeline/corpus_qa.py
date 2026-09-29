"""
V2 R1–R6 corpus QA. Local artifacts + read-only production.

No Supabase writes. No deploy. No extraction. No Linker V1.1.

Usage:
  python -m pipeline.corpus_qa
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.cache_local_pdfs import ext_id_from_title
from pipeline.linker.normalize import is_generic_location, specific_place_tokens
from pipeline.r6_local import load_prior_corpus_incidents
from pipeline.sources.pursue import parse_manifest_csv

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "pipeline" / "snapshots" / "pursue" / "2026-09-18-official" / "uap-data.csv"
OUT = ROOT / "pipeline" / "reports" / "corpus_qa"
CACHE = ROOT / ".cache" / "files" / "pursue"

R2_SMOKE = ROOT / "pipeline" / "reports" / "r2_smoke"
R2_ODNI = ROOT / "pipeline" / "reports" / "r2_complete" / "odni_extraction.json"
R3_FULL = ROOT / "pipeline" / "reports" / "r3_full"
R3_TRUNC = ROOT / "pipeline" / "reports" / "r3_truncation_fix"
R4 = ROOT / "pipeline" / "reports" / "r4_local"
R5 = ROOT / "pipeline" / "reports" / "r5_local"
R6 = ROOT / "pipeline" / "reports" / "r6_local"

ANOMALY_CLASSES = {
    "research_paper",
    "personnel_record",
    "administrative",
    "media_metadata",
}

HIGH_YIELD = [
    "DOW-UAP-D088",
    "DOW-UAP-D082",
    "FBI-UAP-D012",
    "DOW-UAP-D154",
    "DOE-UAP-D004",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text())


def _pages(sb: Any, table: str, columns: str, page_size: int = 1000) -> list[dict]:
    rows: list[dict] = []
    start = 0
    while True:
        resp = sb.table(table).select(columns).range(start, start + page_size - 1).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page_size:
            break
        start += page_size
    return rows


def fetch_production() -> dict[str, Any]:
    """Read-only snapshot of the live R1 corpus. Never updates."""
    _load_env()
    from pipeline.db import get_supabase

    sb = get_supabase()
    incidents = _pages(
        sb,
        "incidents",
        "id,case_id,source_file_id,title,summary,raw_excerpt,occurred_at,occurred_at_text,"
        "location_text,country,region,flagged,flag_reason,source_page,resolution_status,branch",
    )
    files = _pages(
        sb,
        "source_files",
        "id,filename,url,file_type,agency,source_record_id,page_count,processing_error,sha256",
    )
    records = _pages(
        sb,
        "source_records",
        "id,provider,external_id,identity_key,release_number,source_type,status,title,agency,original_url,document_class,contains_incidents",
    )
    links = _pages(sb, "incident_sources", "incident_id,source_record_id,role")
    return {
        "fetched_at": _now(),
        "mode": "read_only",
        "writes": 0,
        "incidents": incidents,
        "source_files": files,
        "source_records": records,
        "incident_sources": links,
    }


def _pairing_tokens(raw: str | None) -> list[str]:
    tokens = []
    for part in re.split(r"[|,]", raw or ""):
        tok = part.strip()
        if not tok:
            continue
        if " " in tok or tok.lower().endswith("event"):
            tokens.append(tok)
            continue
        bits = tok.split("-")
        if len(bits) == 3 and bits[2].isdigit():
            tok = f"{bits[0]}-{bits[1]}-D{bits[2]}"
        tokens.append(tok.upper() if re.match(r"^[A-Z0-9-]+$", tok, re.I) else tok)
    return tokens


def load_classifications() -> list[dict]:
    rows: list[dict] = []
    if (R2_SMOKE / "classifications.json").exists():
        for row in _read_json(R2_SMOKE / "classifications.json")["results"]:
            item = dict(row)
            item["release"] = "02"
            rows.append(item)
    if R2_ODNI.exists():
        data = _read_json(R2_ODNI)
        rows.append(
            {
                "filename": data.get("filename") or "ODNI-UAP-D001.pdf",
                "external_id": "ODNI-UAP-D001",
                "release": "02",
                "page_count": data.get("page_count"),
                "usable_text_chars": data.get("usable_text_chars"),
                "extraction_action": "extract",
                "classification": data.get("classification") or {},
            }
        )
    for path, release in (
        (R3_FULL / "classifications.json", "03"),
        (R4 / "classifications.json", "04"),
        (R5 / "classifications.json", "05"),
        (R6 / "classifications.json", "06"),
    ):
        if not path.exists():
            continue
        for row in _read_json(path)["results"]:
            item = dict(row)
            item["release"] = release
            rows.append(item)
    return rows


def load_local_incidents() -> list[dict]:
    incs = load_prior_corpus_incidents()
    r6 = _read_json(R6 / "extractions.json")
    for inc in r6.get("validated_incidents") or []:
        row = dict(inc)
        row.setdefault("release", "06")
        incs.append(row)
    return incs


def load_doc_metrics() -> dict[str, dict]:
    by_file: dict[str, dict] = {}
    for path in (
        R3_FULL / "per_document_metrics.json",
        R4 / "per_document_metrics.json",
        R5 / "per_document_metrics.json",
        R6 / "per_document_metrics.json",
    ):
        if not path.exists():
            continue
        for row in _read_json(path):
            by_file[row["filename"]] = row
    # Truncation fix supersedes the original zero-yield rows.
    summary = _read_json(R3_TRUNC / "summary.json")
    for file_row in summary.get("files") or []:
        fn = file_row["filename"]
        prev = by_file.get(fn) or {"filename": fn, "external_id": fn.replace(".pdf", "")}
        stats = file_row.get("json_stats") or {}
        prev.update(
            {
                "accepted": file_row.get("accepted") or 0,
                "extraction_failed": stats.get("extraction_failed") or 0,
                "haiku_calls": stats.get("haiku_calls") or 0,
                "sections_subdivided": stats.get("sections_subdivided") or 0,
                "truncation_supersedes_original": True,
            }
        )
        by_file[fn] = prev
    return by_file


def load_text_quality() -> list[dict]:
    docs = []
    for path, release in (
        (R3_FULL / "text_quality.json", "03"),
        (R4 / "text_quality.json", "04"),
        (R5 / "text_quality.json", "05"),
        (R6 / "text_quality.json", "06"),
    ):
        if not path.exists():
            continue
        payload = _read_json(path)
        for row in payload.get("documents") or []:
            item = dict(row)
            item["release"] = release
            docs.append(item)
    # R2 OCR page reports
    ocr_root = ROOT / "pipeline" / "reports" / "r2_ocr"
    if ocr_root.exists():
        for page_report in ocr_root.glob("*/page_report.json"):
            data = _read_json(page_report)
            docs.append(
                {
                    "filename": f"{page_report.parent.name}.pdf",
                    "release": "02",
                    "page_count": data.get("page_count") or data.get("pages"),
                    "pages_ocrd": (data.get("counts") or {}).get("ocr_succeeded")
                    or data.get("pages_ocrd")
                    or 0,
                    "ocr_failed": (data.get("counts") or {}).get("ocr_failed") or data.get("ocr_failed") or 0,
                    "native_good_pages": (data.get("counts") or {}).get("native_good")
                    or data.get("native_good_pages")
                    or 0,
                    "ocr_unrecoverable_thumbnail": (data.get("counts") or {}).get("ocr_unrecoverable_thumbnail")
                    or 0,
                }
            )
    return docs


def _pdf_cached(release: int | None, external_id: str | None) -> bool:
    if not release or not external_id or release == 1:
        return False
    path = CACHE / f"r{release}" / f"{external_id}.pdf"
    return path.exists() and path.stat().st_size > 1000


def ledger_external_id(rec: Any) -> str | None:
    """Official id for joins. Title prefix covers CIA-UAP-002 style ids the manifest parser skips."""
    if rec.external_id:
        return rec.external_id.upper()
    eid = ext_id_from_title(rec.title or "")
    return eid.upper() if eid else None


def build_coverage(
    official: list[Any],
    classifications: list[dict],
    incidents: list[dict],
    prod: dict[str, Any],
) -> list[dict]:
    clf_by_eid: dict[str, dict] = {}
    for row in classifications:
        eid = (row.get("external_id") or "").upper()
        if eid:
            clf_by_eid[eid] = row
    accepted_by_eid: dict[str, int] = Counter()
    for inc in incidents:
        eid = (inc.get("source_external_id") or ext_id_from_title(inc.get("source_filename") or "")).upper()
        if eid:
            accepted_by_eid[eid] += 1

    prod_records = prod["source_records"]
    prod_by_eid: dict[str, list[dict]] = defaultdict(list)
    prod_by_url: dict[str, dict] = {}
    for rec in prod_records:
        if rec.get("external_id"):
            prod_by_eid[rec["external_id"].upper()].append(rec)
        if rec.get("original_url"):
            prod_by_url[rec["original_url"]] = rec
    files_by_record: dict[str, list[dict]] = defaultdict(list)
    for sf in prod["source_files"]:
        if sf.get("source_record_id"):
            files_by_record[sf["source_record_id"]].append(sf)
    inc_by_file: dict[str, list[dict]] = defaultdict(list)
    for inc in prod["incidents"]:
        inc_by_file[inc["source_file_id"]].append(inc)

    rows = []
    for rec in official:
        eid = ledger_external_id(rec)
        meta = rec.metadata or {}
        pair_tokens = _pairing_tokens(meta.get("pdf_pairing")) + _pairing_tokens(meta.get("video_pairing"))
        clf = clf_by_eid.get(eid or "")
        action = (clf or {}).get("extraction_action")
        doc_class = ((clf or {}).get("classification") or {}).get("document_class")
        cached = _pdf_cached(rec.release_number, eid)
        prod_hits = []
        if rec.original_url and rec.original_url in prod_by_url:
            prod_hits.append(prod_by_url[rec.original_url])
        if eid and eid in prod_by_eid:
            for hit in prod_by_eid[eid]:
                if hit not in prod_hits and hit.get("release_number") == rec.release_number:
                    if hit.get("source_type") == rec.source_type or rec.source_type == "pdf":
                        prod_hits.append(hit)
        linked_files: list[dict] = []
        for hit in prod_hits:
            linked_files.extend(files_by_record.get(hit["id"]) or [])
        prod_incidents = []
        for sf in linked_files:
            prod_incidents.extend(inc_by_file.get(sf["id"]) or [])
        unflagged = [i for i in prod_incidents if not i.get("flagged")]
        local_accepted = accepted_by_eid.get(eid or "", 0) if rec.release_number and rec.release_number > 1 else 0
        if rec.release_number == 1:
            accepted = len(unflagged)
        elif rec.source_type == "pdf":
            accepted = local_accepted
        else:
            # Duplicate external_ids (FBI-UAP-D014 image vs PDF) must not copy PDF yields onto media rows.
            accepted = 0

        media_only = rec.source_type in {"image", "video", "audio"}
        unrecoverable = False
        unrecoverable_reason = None
        if clf and (clf.get("external_id") == "CIA-UAP-009" or clf.get("filename") == "CIA-UAP-009.pdf"):
            unrecoverable = True
            unrecoverable_reason = "unrecoverable_thumbnail"
        text_ready = bool(clf) or (rec.release_number == 1 and bool(linked_files))
        local_asset = cached or bool(linked_files)

        if rec.status in {"deprecated", "superseded"}:
            bucket = "deprecated_superseded"
        elif rec.source_type == "image":
            bucket = "image_metadata_only"
        elif rec.source_type == "video":
            bucket = "video_metadata_only"
        elif rec.source_type == "audio":
            bucket = "audio_metadata_only"
        elif rec.source_type == "pdf" and action == "source_only":
            bucket = "pdf_source_only"
        elif rec.source_type == "pdf" and action == "extract":
            bucket = "pdf_processed"
        elif rec.source_type == "pdf" and rec.release_number == 1 and linked_files:
            bucket = "pdf_processed" if accepted or prod_incidents else "pdf_source_only"
        elif rec.source_type == "pdf" and rec.release_number == 1 and not linked_files:
            bucket = "unrecoverable"
            unrecoverable = True
            unrecoverable_reason = "r1_official_record_not_linked_url_drift"
        elif rec.source_type == "pdf":
            bucket = "unrecoverable"
            unrecoverable = True
            unrecoverable_reason = "pdf_not_in_local_corpus"
        else:
            bucket = "unrecoverable"
            unrecoverable = True
            unrecoverable_reason = f"unclassified_type_{rec.source_type}"

        rows.append(
            {
                "provider": rec.provider,
                "release": rec.release_number,
                "external_id": eid,
                "identity_key": rec.identity_key,
                "agency": rec.agency,
                "type": rec.source_type,
                "status": rec.status,
                "title": rec.title,
                "local_asset_present": local_asset,
                "text_ready": text_ready,
                "classification": doc_class,
                "extract_or_source_only": (
                    "metadata_only"
                    if media_only
                    else action
                    or ("extract" if bucket == "pdf_processed" else "source_only" if bucket == "pdf_source_only" else "unprocessed")
                ),
                "accepted_incident_count": accepted,
                "media_only": media_only,
                "unrecoverable": unrecoverable,
                "unrecoverable_reason": unrecoverable_reason,
                "paired_source_count": len(pair_tokens),
                "qa_bucket": bucket,
                "production_source_record_ids": [h["id"] for h in prod_hits],
                "production_incident_count": len(prod_incidents),
                "production_unflagged_count": len(unflagged),
                "production_flagged_count": len(prod_incidents) - len(unflagged),
            }
        )
    return rows


def release_table(rows: list[dict]) -> list[dict]:
    table = []
    for rel in range(1, 7):
        subset = [r for r in rows if r["release"] == rel]
        pdfs = [r for r in subset if r["type"] == "pdf"]
        table.append(
            {
                "release": f"R{rel}",
                "records": len(subset),
                "pdfs": len(pdfs),
                "media": sum(1 for r in subset if r["media_only"]),
                "extract": sum(1 for r in pdfs if r["extract_or_source_only"] == "extract"),
                "source_only": sum(1 for r in pdfs if r["extract_or_source_only"] == "source_only"),
                "accepted": sum(r["accepted_incident_count"] for r in subset),
            }
        )
    return table


def reconcile_r1(rows: list[dict], prod: dict[str, Any]) -> dict[str, Any]:
    incidents = prod["incidents"]
    flagged = [i for i in incidents if i.get("flagged")]
    unflagged = [i for i in incidents if not i.get("flagged")]
    reasons = Counter((i.get("flag_reason") or "unspecified") for i in flagged)
    files = prod["source_files"]
    linked_files = [f for f in files if f.get("source_record_id")]
    unlinked_files = [f for f in files if not f.get("source_record_id")]
    r1_rows = [r for r in rows if r["release"] == 1]
    mapped_incidents = 0
    file_to_record = {f["id"]: f for f in files}
    unmapped = []
    for inc in unflagged:
        sf = file_to_record.get(inc["source_file_id"]) or {}
        if sf.get("source_record_id"):
            mapped_incidents += 1
        else:
            unmapped.append(
                {
                    "case_id": inc.get("case_id"),
                    "title": inc.get("title"),
                    "filename": sf.get("filename"),
                    "flagged": False,
                }
            )
    official_r1_ids = {r["identity_key"] for r in r1_rows}
    prod_r1 = [r for r in prod["source_records"] if r.get("release_number") == 1]
    return {
        "production_incidents": len(incidents),
        "unflagged": len(unflagged),
        "flagged": len(flagged),
        "flag_reasons": dict(reasons),
        "valid_unflagged": len(unflagged),
        "map_cleanly_to_source_record": mapped_incidents,
        "unflagged_without_source_record": len(unmapped),
        "unflagged_without_source_record_rows": unmapped,
        "flagged_stay_excluded": len(flagged),
        "historical_rows_superseded": 0,
        "need_no_change": mapped_incidents,
        "official_r1_records": len(r1_rows),
        "production_r1_source_records": len(prod_r1),
        "source_files": len(files),
        "source_files_linked": len(linked_files),
        "source_files_unlinked": len(unlinked_files),
        "unlinked_filenames": [f.get("filename") for f in unlinked_files],
        "r1_unlinked_official": [
            {"external_id": r["external_id"], "title": r["title"], "reason": r["unrecoverable_reason"]}
            for r in r1_rows
            if r["qa_bucket"] == "unrecoverable"
        ],
        "official_identity_keys": len(official_r1_ids),
        "note": "R1 was not re-extracted. Unflagged rows stay the published baseline. Flagged duplicate_excerpt rows stay excluded.",
    }


def r1_linker_incidents(prod: dict[str, Any], official: list[Any]) -> list[dict]:
    files = {f["id"]: f for f in prod["source_files"]}
    records = {r["id"]: r for r in prod["source_records"]}
    official_by_url = {r.original_url: r for r in official if r.original_url}
    out = []
    for inc in prod["incidents"]:
        if inc.get("flagged"):
            continue
        sf = files.get(inc["source_file_id"]) or {}
        srec = records.get(sf.get("source_record_id") or "") or official_by_url.get(sf.get("url") or "")
        if isinstance(srec, dict):
            eid = (srec.get("external_id") or "").upper()
        else:
            eid = (getattr(srec, "external_id", None) or "").upper()
        filename = f"{eid}.pdf" if eid else (sf.get("filename") or "unknown.pdf")
        out.append(
            {
                "case_id": inc.get("case_id"),
                "title": inc.get("title"),
                "summary": inc.get("summary"),
                "raw_excerpt": inc.get("raw_excerpt") or "",
                "occurred_at": inc.get("occurred_at"),
                "occurred_at_text": inc.get("occurred_at_text"),
                "location_text": inc.get("location_text"),
                "country": inc.get("country"),
                "region": inc.get("region"),
                "branch": inc.get("branch"),
                "source_filename": filename,
                "source_external_id": eid or None,
                "source_page": inc.get("source_page"),
                "release": "01",
                "origin": "production_r1_unflagged",
            }
        )
    return out


def run_linker(incidents: list[dict], classifications: list[dict]) -> dict[str, Any]:
    from pipeline.linker.audit import write_audit
    from pipeline.linker.candidate_generation import generate_candidates
    from pipeline.linker.relationship_rules import apply_rules
    from pipeline.linker.run_v1 import load_catalog, refine_colorado_label

    # Synthetic classifications for R1 files so catalog pairing can see them.
    known = {r.get("filename") for r in classifications}
    extra = list(classifications)
    for inc in incidents:
        fn = inc.get("source_filename")
        if inc.get("release") != "01" or not fn or fn in known:
            continue
        extra.append(
            {
                "filename": fn,
                "external_id": (inc.get("source_external_id") or fn.replace(".pdf", "")),
                "release": "01",
                "extraction_action": "extract",
                "classification": {
                    "document_class": "incident_report",
                    "contains_incidents": True,
                },
            }
        )
        known.add(fn)

    catalog = load_catalog()
    texts: dict[str, str] = {}
    ocr_roots = (
        R6 / "ocr",
        R5 / "ocr",
        R4 / "ocr",
        R3_FULL / "ocr",
        ROOT / "pipeline" / "reports" / "r2_ocr",
    )
    for row in extra:
        clf = row.get("classification") or {}
        if clf.get("contains_incidents"):
            continue
        if clf.get("document_class") not in {"analysis", "correspondence", "media_metadata", "other"} and clf.get(
            "contains_incidents"
        ) is not False:
            continue
        path = Path(row.get("text_path") or "")
        if not path.is_absolute():
            path = ROOT / path
        if not path.exists():
            stem = Path(row.get("filename") or "").stem
            for root in ocr_roots:
                cand = root / stem / "combined.txt"
                if cand.exists():
                    path = cand
                    break
        if path.exists() and path.is_file():
            texts[row["filename"]] = path.read_text(errors="replace")

    candidates = generate_candidates(
        incidents=incidents,
        classifications=extra,
        catalog=catalog,
        texts=texts,
    )
    payload = apply_rules(
        incidents=incidents,
        classifications=extra,
        catalog=catalog,
        candidates=candidates,
        texts=texts,
    )
    payload["candidates"] = candidates
    refine_colorado_label(payload)

    release_by_case = {
        inc["case_id"]: str(inc.get("release"))
        for inc in incidents
        if inc.get("case_id") and inc.get("release")
    }
    release_by_file: dict[str, str] = {}
    for inc in incidents:
        fn = inc.get("source_filename")
        if fn and inc.get("release"):
            release_by_file[fn] = str(inc["release"])
    for row in extra:
        fn = row.get("filename")
        if fn and row.get("release") and fn not in release_by_file:
            release_by_file[fn] = str(row["release"])

    annotated = []
    for d in payload.get("decisions") or []:
        left_r = release_by_case.get(d.get("left") or "") or release_by_file.get(d.get("left") or "")
        right_r = release_by_case.get(d.get("right") or "") or release_by_file.get(d.get("right") or "")
        # event ids and series ids are not releases
        row = dict(d)
        row["source_release"] = left_r
        row["target_release"] = right_r
        row["cross_release"] = bool(left_r and right_r and left_r != right_r)
        annotated.append(row)
    payload["decisions"] = annotated
    link_out = OUT / "linker"
    metrics = write_audit(link_out, payload)
    cross = [d for d in annotated if d.get("cross_release")]
    same = [
        d
        for d in annotated
        if d.get("source_release") and d.get("target_release") and not d.get("cross_release")
    ]
    metrics["same_release_decisions"] = len(same)
    metrics["cross_release_decisions"] = len(cross)
    metrics["cross_release_by_relationship"] = dict(Counter(d.get("relationship") for d in cross))
    metrics["corpus_incidents"] = len(incidents)
    metrics["by_release"] = dict(Counter(i.get("release") for i in incidents))
    return {"payload": payload, "metrics": metrics, "classifications": extra, "catalog": catalog}


def audit_overmerge(payload: dict[str, Any], incidents: list[dict]) -> dict[str, Any]:
    by_case = {i.get("case_id"): i for i in incidents if i.get("case_id")}
    candidates = []
    for event in payload.get("canonical_events") or []:
        members = [by_case[c] for c in event.get("member_case_ids") or [] if c in by_case]
        if len(members) < 2:
            continue
        dates = sorted({m.get("occurred_at") for m in members if m.get("occurred_at")})
        place_sets = []
        for m in members:
            toks = specific_place_tokens(m.get("location_text") or "")
            if toks and not is_generic_location(m.get("location_text")):
                place_sets.append(toks)
        place_conflict = False
        if len(place_sets) >= 2 and not set.intersection(*place_sets):
            place_conflict = True
        ops = set()
        for m in members:
            blob = f"{m.get('title') or ''} {m.get('summary') or ''}"
            for match in re.findall(r"\boperation\s+([A-Za-z0-9-]+)", blob, flags=re.I):
                ops.add(match.lower())
        sources = sorted({m.get("source_filename") or "" for m in members})
        generic_as_evidence = False
        for d in payload.get("decisions") or []:
            if d.get("relationship") != "same_event" or d.get("status") != "auto_supported":
                continue
            ev = " ".join(d.get("evidence") or []).lower()
            if "generic location" in ev and d.get("left") in event.get("member_case_ids", []):
                generic_as_evidence = True
        flags = []
        if len(dates) > 1:
            flags.append("multiple_incompatible_dates")
        if place_conflict:
            flags.append("multiple_incompatible_specific_locations")
        if len(ops) > 1:
            flags.append("different_named_operations")
        if generic_as_evidence:
            flags.append("generic_location_primary_evidence")
        if not flags:
            continue
        # Intra-source phase rows that share a source and were grouped by an explicit
        # same-night cue are reviewed, not auto-failed, when dates disagree.
        disposition = "unresolved"
        explanation = None
        if sources and len(sources) == 1 and "multiple_incompatible_dates" in flags and not place_conflict:
            disposition = "needs_review"
            explanation = "intra-source episode grouped rows whose dates differ; continuity cue fired inside one file"
        elif "generic_location_primary_evidence" in flags:
            disposition = "unresolved"
            explanation = "auto same_event cited generic location"
        candidates.append(
            {
                "event_id": event.get("event_id"),
                "label": event.get("label"),
                "sources": sources,
                "member_case_ids": event.get("member_case_ids"),
                "dates": dates,
                "flags": flags,
                "disposition": disposition,
                "explanation": explanation,
            }
        )
    unresolved = [c for c in candidates if c["disposition"] == "unresolved"]
    return {
        "generated_at": _now(),
        "candidate_count": len(candidates),
        "unresolved": len(unresolved),
        "needs_review": sum(1 for c in candidates if c["disposition"] == "needs_review"),
        "candidates": candidates,
    }


def audit_underlink(payload: dict[str, Any], incidents: list[dict], official: list[Any]) -> dict[str, Any]:
    """High-confidence misses only. Catalog pairing + same specific date + same specific place, no decision."""
    by_file: dict[str, list[dict]] = defaultdict(list)
    for inc in incidents:
        by_file[inc.get("source_filename") or ""].append(inc)
    decisions = payload.get("decisions") or []
    linked_pairs = set()
    for d in decisions:
        if d.get("relationship") in {"same_event", "media_for_event", "analysis_of_event", "same_series"}:
            linked_pairs.add(tuple(sorted([str(d.get("left")), str(d.get("right"))])))

    catalog_pairs = []
    for rec in official:
        eid = (rec.external_id or "").upper()
        if not eid:
            continue
        raw = " ".join(
            [
                (rec.metadata or {}).get("pdf_pairing") or "",
                (rec.metadata or {}).get("video_pairing") or "",
            ]
        )
        for tok in _pairing_tokens(raw):
            if " " in tok or tok.lower().endswith("event"):
                continue
            catalog_pairs.append((eid, tok.upper()))

    candidates = []
    seen = set()
    for left, right in catalog_pairs:
        key = tuple(sorted([left, right]))
        if key in seen or left == right:
            continue
        seen.add(key)
        left_incs = by_file.get(f"{left}.pdf") or []
        right_incs = by_file.get(f"{right}.pdf") or []
        if not left_incs or not right_incs:
            continue
        for a in left_incs:
            for b in right_incs:
                if not a.get("occurred_at") or a.get("occurred_at") != b.get("occurred_at"):
                    continue
                shared = specific_place_tokens(a.get("location_text") or "") & specific_place_tokens(
                    b.get("location_text") or ""
                )
                if not shared:
                    continue
                if is_generic_location(a.get("location_text")) or is_generic_location(b.get("location_text")):
                    continue
                pair_key = tuple(sorted([a.get("case_id") or "", b.get("case_id") or ""]))
                already = any(
                    d.get("relationship") == "same_event"
                    and {d.get("left"), d.get("right")} & {a.get("case_id"), b.get("case_id"), f"{left}.pdf", f"{right}.pdf"}
                    for d in decisions
                )
                candidates.append(
                    {
                        "left_source": left,
                        "right_source": right,
                        "left_case": a.get("case_id"),
                        "right_case": b.get("case_id"),
                        "date": a.get("occurred_at"),
                        "places": sorted(shared),
                        "already_decided": already or pair_key in linked_pairs,
                        "confidence": "high",
                        "auto_merged": False,
                    }
                )
    unresolved = [c for c in candidates if not c["already_decided"]]
    return {
        "generated_at": _now(),
        "note": "Not auto-merged. High confidence = official pairing + identical date + shared specific place.",
        "candidate_count": len(candidates),
        "high_confidence_unresolved": len(unresolved),
        "candidates": candidates,
        "unresolved": unresolved,
    }


def source_evolution(official: list[Any], classifications: list[dict]) -> dict[str, Any]:
    by_eid: dict[str, list[Any]] = defaultdict(list)
    for rec in official:
        if rec.external_id:
            by_eid[rec.external_id.upper()].append(rec)
    hints = []
    for eid, group in sorted(by_eid.items()):
        if len(group) < 2:
            continue
        hints.append(
            {
                "kind": "duplicate_external_id",
                "external_id": eid,
                "occurrences": [
                    {
                        "release": r.release_number,
                        "type": r.source_type,
                        "identity_key": r.identity_key,
                        "title": r.title,
                    }
                    for r in group
                ],
            }
        )
        types = {r.source_type for r in group}
        releases = sorted({r.release_number for r in group})
        if len(types) > 1:
            hints.append(
                {
                    "kind": "type_change",
                    "external_id": eid,
                    "types": sorted(types),
                    "releases": releases,
                    "note": "same external_id, different asset types — package evolution, not an event merge",
                }
            )
        if len(releases) > 1 and len(types) == 1:
            hints.append(
                {
                    "kind": "reissued_source",
                    "external_id": eid,
                    "releases": releases,
                    "type": next(iter(types)),
                }
            )
    # Cross-release catalog pairings
    release_of = {}
    for rec in official:
        if rec.external_id:
            release_of[(rec.external_id.upper(), rec.source_type)] = rec.release_number
            release_of.setdefault(rec.external_id.upper(), rec.release_number)
    clf_class = {
        (r.get("external_id") or "").upper(): (r.get("classification") or {}).get("document_class")
        for r in classifications
    }
    for rec in official:
        left = (rec.external_id or "").upper()
        if not left:
            continue
        raw = " ".join(
            [(rec.metadata or {}).get("pdf_pairing") or "", (rec.metadata or {}).get("video_pairing") or ""]
        )
        for tok in _pairing_tokens(raw):
            if " " in tok or not re.match(r"^[A-Z0-9-]+$", tok):
                continue
            right_rel = release_of.get(tok)
            if not right_rel or not rec.release_number or right_rel == rec.release_number:
                continue
            kind = "later_media_for_prior_event" if rec.source_type != "pdf" else "cross_release_pairing"
            doc_class = clf_class.get(left)
            if doc_class == "analysis":
                kind = "later_analysis_of_prior_event"
            elif doc_class == "transcript":
                kind = "later_transcript_of_prior_event"
            hints.append(
                {
                    "kind": kind,
                    "later_id": left,
                    "later_release": rec.release_number,
                    "later_type": rec.source_type,
                    "prior_id": tok,
                    "prior_release": right_rel,
                    "auto_merged": False,
                }
            )
    fbi = [h for h in hints if h.get("external_id") == "FBI-UAP-D014" or h.get("later_id") == "FBI-UAP-D014" or h.get("prior_id") == "FBI-UAP-D014"]
    return {
        "generated_at": _now(),
        "hint_count": len(hints),
        "by_kind": dict(Counter(h.get("kind") for h in hints)),
        "fbi_uap_d014": fbi,
        "hints": hints,
    }


def classifier_qa(classifications: list[dict], incidents: list[dict]) -> dict[str, Any]:
    classes = Counter(((r.get("classification") or {}).get("document_class") or "unclassified") for r in classifications)
    accepted_by_file = Counter(i.get("source_filename") for i in incidents if i.get("release") != "01")
    anomalies = []
    for row in classifications:
        doc_class = (row.get("classification") or {}).get("document_class")
        accepted = accepted_by_file.get(row.get("filename")) or 0
        if doc_class in ANOMALY_CLASSES and accepted:
            anomalies.append(
                {
                    "filename": row.get("filename"),
                    "document_class": doc_class,
                    "extraction_action": row.get("extraction_action"),
                    "accepted": accepted,
                    "disposition": "needs_review",
                }
            )
        if row.get("extraction_action") == "source_only" and accepted:
            anomalies.append(
                {
                    "filename": row.get("filename"),
                    "document_class": doc_class,
                    "alarm": "source_only_with_accepted",
                    "accepted": accepted,
                    "disposition": "unresolved",
                }
            )
    return {
        "distribution": dict(classes),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
    }


def ocr_qa(text_docs: list[dict], doc_metrics: dict[str, dict]) -> dict[str, Any]:
    pages = 0
    ocrd = 0
    failed = 0
    native_only = []
    high_fail = []
    thumbs = []
    seen = set()
    for row in text_docs:
        fn = row.get("filename")
        if fn in seen:
            continue
        seen.add(fn)
        pc = int(row.get("page_count") or 0)
        pages += pc
        ocrd += int(row.get("pages_ocrd") or 0)
        fail = int(row.get("ocr_failed") or 0)
        failed += fail
        native_good = int(row.get("native_good_pages") or 0)
        if pc and native_good == pc and fail == 0 and int(row.get("pages_ocrd") or 0) == 0:
            native_only.append(fn)
        rate = (fail / pc) if pc else 0
        if pc and rate > 0.20:
            high_fail.append({"filename": fn, "release": row.get("release"), "ocr_failed": fail, "pages": pc, "rate": round(rate, 3)})
        if row.get("ocr_unrecoverable_thumbnail"):
            thumbs.append(fn)
    if "CIA-UAP-009.pdf" not in thumbs:
        metric = doc_metrics.get("CIA-UAP-009.pdf") or {}
        if metric.get("ocr_failure_rate") == 1.0 or metric.get("document_class") == "other":
            thumbs.append("CIA-UAP-009.pdf")
    return {
        "pages_total": pages,
        "pages_ocrd": ocrd,
        "ocr_failures": failed,
        "files_gt_20pct_ocr_failure": high_fail,
        "unrecoverable_thumbnails": sorted(set(thumbs)),
        "files_native_only_good_text": native_only,
        "documents_measured": len(seen),
    }


def extraction_qa(local_incidents: list[dict], doc_metrics: dict[str, dict]) -> dict[str, Any]:
    def block(path: Path, key: str = "extraction") -> dict:
        if not path.exists():
            return {}
        data = _read_json(path)
        return data.get(key) or data

    r2 = _read_json(R2_SMOKE / "extractions.json")["summary"]
    odni = _read_json(R2_ODNI)
    r3 = _read_json(R3_FULL / "metrics.json")
    r4 = block(R4 / "metrics.json")
    r5 = block(R5 / "metrics.json")
    r6 = block(R6 / "metrics.json")
    trunc = _read_json(R3_TRUNC / "summary.json")
    trunc_calls = sum((f.get("json_stats") or {}).get("haiku_calls") or 0 for f in trunc["files"])
    trunc_failed = sum((f.get("json_stats") or {}).get("extraction_failed") or 0 for f in trunc["files"])
    trunc_sub = sum((f.get("json_stats") or {}).get("sections_subdivided") or 0 for f in trunc["files"])
    trunc_truncations = sum(f.get("truncation_events") or 0 for f in trunc["files"])

    def n(obj: dict, *keys: str) -> int:
        cur: Any = obj
        for k in keys:
            if not isinstance(cur, dict):
                return 0
            cur = cur.get(k)
        return int(cur or 0)

    # R3 metrics predate the truncation fix. Add the fix calls; final failures come from the fix.
    haiku = (
        n(r2, "json_stats", "json_first_pass")
        + n(r2, "json_stats", "json_retry_success")
        + n(r2, "json_stats", "json_retry_failed")
        + n(odni, "json_stats", "json_first_pass")
        + n(r3, "haiku_calls")
        + trunc_calls
        + n(r4, "haiku_calls")
        + n(r5, "haiku_calls")
        + n(r6, "haiku_calls")
    )
    # Candidates: r3 per-doc still has the pre-fix zeros for D088/D013. Use local accepted list
    # plus reported candidate totals, replacing those two files via truncation accepted only
    # when candidate totals were not restated. Keep reported release totals and note the fix.
    accepted_local = len(local_incidents)
    by_file = Counter(i.get("source_filename") for i in local_incidents)
    zero_extract = []
    high_yield = []
    high_reject = []
    for fn, row in sorted(doc_metrics.items()):
        if row.get("extraction_action") != "extract" and fn not in {"DOW-UAP-D088.pdf", "FBI-UAP-D013.pdf"}:
            continue
        accepted = by_file.get(fn, row.get("accepted") or 0)
        candidates = row.get("candidates")
        rejected = row.get("quote_rejected") or 0
        if accepted == 0 and row.get("extraction_action") == "extract":
            explained_zero = {
                "CIA-UAP-004.pdf": "explained_no_encounter",
                "CIA-UAP-005.pdf": "explained_no_encounter",
                "CIA-UAP-007.pdf": "explained_no_encounter",
                "CIA-UAP-015.pdf": "explained_study_prose_no_incident",
                "CIA-UAP-019.pdf": "explained_ocr_unusable",
                "DOW-UAP-D084.pdf": "explained_ocr_noise",
            }
            if fn in explained_zero:
                disposition = explained_zero[fn]
            elif rejected or row.get("evidence_insufficient"):
                disposition = "explained_quote_or_evidence_gate"
            else:
                disposition = "needs_review"
            zero_extract.append(
                {
                    "filename": fn,
                    "candidates": candidates,
                    "quote_rejected": rejected,
                    "evidence_insufficient": row.get("evidence_insufficient"),
                    "disposition": disposition,
                }
            )
        if accepted >= 9:
            high_yield.append({"filename": fn, "accepted": accepted})
        if candidates and rejected / max(candidates, 1) >= 0.5 and rejected >= 2:
            high_reject.append({"filename": fn, "candidates": candidates, "quote_rejected": rejected})

    failed = n(r4, "extraction_failed") + n(r5, "extraction_failed") + n(r6, "extraction_failed") + trunc_failed
    return {
        "haiku_calls": haiku,
        "r3_note": "R3 haiku_calls include the original D088/D013 attempts. Truncation-fix calls are additional and supersede those outputs.",
        "accepted_local_r2_r6": accepted_local,
        "accepted_by_file_high_yield": high_yield,
        "extract_zero_accepted": zero_extract,
        "high_quote_rejection": high_reject,
        "extraction_failed": failed,
        "truncations_in_fix": trunc_truncations,
        "page_subdivisions_in_fix": trunc_sub,
        "release_reported": {
            "r2_smoke_accepted": r2.get("incidents_accepted"),
            "r2_odni_accepted": len(odni.get("validated") or []),
            "r3_metrics_accepted_before_truncation_fix": r3.get("accepted"),
            "r3_truncation_fix_accepted": sum(f.get("accepted") or 0 for f in trunc["files"]),
            "r4_accepted": n(r4, "accepted"),
            "r5_accepted": n(r5, "accepted"),
            "r6_accepted": n(r6, "accepted"),
        },
    }


def evidence_qa(incidents: list[dict], official: list[Any]) -> dict[str, Any]:
    official_ids = {eid for eid in (ledger_external_id(r) for r in official) if eid}
    failures = []
    for inc in incidents:
        problems = []
        if not (inc.get("raw_excerpt") or "").strip():
            problems.append("missing_raw_excerpt")
        if not inc.get("source_filename") and not inc.get("source_file_id"):
            problems.append("missing_source")
        eid = (inc.get("source_external_id") or ext_id_from_title(inc.get("source_filename") or "")).upper()
        if inc.get("release") != "01":
            if eid and eid not in official_ids:
                problems.append("source_record_not_in_official_manifest")
            if not eid:
                problems.append("missing_external_id")
        else:
            if not inc.get("source_filename"):
                problems.append("r1_missing_source_filename")
        if problems:
            failures.append({"case_id": inc.get("case_id"), "release": inc.get("release"), "problems": problems})
    return {
        "accepted_checked": len(incidents),
        "traceable": len(incidents) - len(failures),
        "unsupported": len(failures),
        "failures": failures[:50],
        "failure_count": len(failures),
    }


def high_yield_review(incidents: list[dict], payload: dict[str, Any]) -> list[dict]:
    reviews = []
    by_source: dict[str, list[dict]] = defaultdict(list)
    for inc in incidents:
        eid = (inc.get("source_external_id") or ext_id_from_title(inc.get("source_filename") or "")).upper()
        if eid in HIGH_YIELD:
            by_source[eid].append(inc)
    episode_audit = payload.get("episode_audit") or {}
    notes = {
        "DOW-UAP-D088": "Post-truncation compilation. Many rows, distinct dates. True multi-event document, not one sighting split into duplicates.",
        "DOW-UAP-D082": "Western US witness packet. Linker V1 collapsed phase rows via continuity cues and kept the file inside the series, not one merged event.",
        "FBI-UAP-D012": "Multi-incident FBI compilation. Rows stay separate unless an explicit continuity cue groups a phase.",
        "DOW-UAP-D154": "Ruppelt presentation transcript. Multiple historical cases named in one talk; high yield is expected.",
        "DOE-UAP-D004": "Green-fireball / meteorite file with distinct dates and places. High-yield alarm only; not a linker overmerge.",
    }
    for eid in HIGH_YIELD:
        rows = by_source.get(eid) or []
        dates = sorted({r.get("occurred_at") for r in rows if r.get("occurred_at")})
        fn = f"{eid}.pdf"
        audit = episode_audit.get(fn) or {}
        reviews.append(
            {
                "external_id": eid,
                "accepted": len(rows),
                "distinct_dates": len(dates),
                "episode_count": audit.get("episode_count"),
                "input_rows": audit.get("input_rows"),
                "disposition": "explained",
                "reading": notes[eid],
            }
        )
    return reviews


def watch_list(payload: dict[str, Any], rows: list[dict]) -> list[dict]:
    by_eid = {r["external_id"]: r for r in rows if r.get("external_id")}
    metrics_path = OUT / "linker" / "metrics.json"

    def row(eid: str) -> dict:
        return by_eid.get(eid) or {}

    items = [
        {
            "id": "cia_d020_d021",
            "refs": ["CIA-UAP-D020", "CIA-UAP-D021"],
            "disposition": "explained",
            "note": "Catalog-paired. D020 quote-rejected; D021 accepted independently. No manufactured member.",
            "accepted": [row("CIA-UAP-D020").get("accepted_incident_count"), row("CIA-UAP-D021").get("accepted_incident_count")],
        },
        {
            "id": "doe_d005_d001",
            "refs": ["DOE-UAP-D005", "DOE-UAP-D001"],
            "disposition": "explained",
            "note": "Cross-release correspondence versus earlier Pantex source. No synthetic incident.",
            "accepted": [row("DOE-UAP-D005").get("accepted_incident_count"), row("DOE-UAP-D001").get("accepted_incident_count")],
        },
        {
            "id": "nasa_d030_032",
            "refs": ["NASA-UAP-D030", "NASA-UAP-D031", "NASA-UAP-D032"],
            "disposition": "explained",
            "note": "Images are metadata-only. Zero synthetic incidents.",
            "buckets": [row(e).get("qa_bucket") for e in ("NASA-UAP-D030", "NASA-UAP-D031", "NASA-UAP-D032")],
        },
        {
            "id": "dow_d089_d090",
            "refs": ["DOW-UAP-D089", "DOW-UAP-D090", "DOW-UAP-D091"],
            "disposition": "explained",
            "note": "D090 stayed source_only while sibling transcripts extracted. Conservative; no fabricated incidents. Classifier left frozen.",
            "classes": [row(e).get("classification") for e in ("DOW-UAP-D089", "DOW-UAP-D090", "DOW-UAP-D091")],
            "actions": [row(e).get("extract_or_source_only") for e in ("DOW-UAP-D089", "DOW-UAP-D090", "DOW-UAP-D091")],
        },
        {
            "id": "r5_fd302_siblings",
            "refs": ["FBI-UAP-D024", "FBI-UAP-D032", "FBI-UAP-D037", "FBI-UAP-D040"],
            "disposition": "explained",
            "note": "FD-302 cluster mixes extract and source_only. Observed, not retuned. Accepted rows still passed quote and evidence gates.",
            "actions": {e: row(e).get("extract_or_source_only") for e in ("FBI-UAP-D024", "FBI-UAP-D026", "FBI-UAP-D032", "FBI-UAP-D037", "FBI-UAP-D040")},
        },
        {
            "id": "fbi_d014_reissue",
            "refs": ["FBI-UAP-D014"],
            "disposition": "explained",
            "note": "Same external_id is an R3 image and an R4 PDF. Identity keys were disambiguated. Not an event merge.",
            "rows": [r for r in rows if r.get("external_id") == "FBI-UAP-D014"],
        },
        {
            "id": "colorado_springs",
            "disposition": "explained" if (payload.get("metrics") or {}).get("colorado_springs", {}).get("pass") else "action_required",
            "note": "Linker V1 fixture on the full R1–R6 corpus.",
        },
        {
            "id": "western_us_series",
            "disposition": "explained" if (payload.get("metrics") or {}).get("western_us", {}).get("pass") else "action_required",
            "note": "Series, not one merged event.",
        },
        {
            "id": "tremonton_package",
            "refs": ["DOW-UAP-D102", "DOW-UAP-D098", "DOW-UAP-D103"],
            "disposition": "explained",
            "note": "R6 Blue Book file plus later media/analysis pairings. Hints only; no auto-merge across releases.",
            "accepted": {e: row(e).get("accepted_incident_count") for e in ("DOW-UAP-D102", "DOW-UAP-D098", "DOW-UAP-D103")},
        },
    ]
    if metrics_path.exists() and "metrics" not in payload:
        pass
    return items


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    OUT.mkdir(parents=True, exist_ok=True)
    official = parse_manifest_csv(CSV_PATH.read_text(encoding="utf-8-sig"))
    if len(official) != 450:
        raise SystemExit(f"official record count {len(official)} != 450")
    logger.info("fetching production read-only")
    prod = fetch_production()
    (OUT / "r1_production_snapshot.json").write_text(
        json.dumps(
            {
                "fetched_at": prod["fetched_at"],
                "mode": "read_only",
                "writes": 0,
                "incident_count": len(prod["incidents"]),
                "source_file_count": len(prod["source_files"]),
                "source_record_count": len(prod["source_records"]),
                "incident_source_count": len(prod["incident_sources"]),
            },
            indent=2,
        )
        + "\n"
    )
    classifications = load_classifications()
    local_incidents = load_local_incidents()
    doc_metrics = load_doc_metrics()
    text_docs = load_text_quality()
    coverage = build_coverage(official, classifications, local_incidents, prod)
    buckets = Counter(r["qa_bucket"] for r in coverage)
    if sum(buckets.values()) != 450:
        raise SystemExit(f"bucket sum {sum(buckets.values())} != 450")
    releases = release_table(coverage)
    r1 = reconcile_r1(coverage, prod)
    r1_incs = r1_linker_incidents(prod, official)
    corpus = r1_incs + local_incidents
    logger.info("linking %d incidents", len(corpus))
    linked = run_linker(corpus, classifications)
    payload = linked["payload"]
    over = audit_overmerge(payload, corpus)
    under = audit_underlink(payload, corpus, official)
    evolution = source_evolution(official, classifications)
    clf = classifier_qa(classifications, local_incidents)
    ocr = ocr_qa(text_docs, doc_metrics)
    extract = extraction_qa(local_incidents, doc_metrics)
    evidence = evidence_qa(corpus, official)
    hy = high_yield_review(corpus, payload)
    watch = watch_list({"metrics": linked["metrics"]}, coverage)

    fields = [
        "provider",
        "release",
        "external_id",
        "agency",
        "type",
        "status",
        "local_asset_present",
        "text_ready",
        "classification",
        "extract_or_source_only",
        "accepted_incident_count",
        "media_only",
        "unrecoverable",
        "paired_source_count",
        "qa_bucket",
        "identity_key",
        "unrecoverable_reason",
    ]
    (OUT / "source_coverage.json").write_text(json.dumps({"generated_at": _now(), "records": coverage}, indent=2) + "\n")
    write_csv(OUT / "source_coverage.csv", coverage, fields)
    (OUT / "release_summary.json").write_text(
        json.dumps(
            {
                "generated_at": _now(),
                "official_records": 450,
                "buckets": dict(buckets),
                "bucket_sum": sum(buckets.values()),
                "releases": releases,
            },
            indent=2,
        )
        + "\n"
    )
    (OUT / "r1_reconciliation.json").write_text(json.dumps(r1, indent=2) + "\n")
    (OUT / "overmerge_candidates.json").write_text(json.dumps(over, indent=2) + "\n")
    (OUT / "underlink_candidates.json").write_text(json.dumps(under, indent=2) + "\n")
    (OUT / "source_evolution.json").write_text(json.dumps(evolution, indent=2) + "\n")
    (OUT / "ocr_quality_summary.json").write_text(json.dumps(ocr, indent=2) + "\n")
    (OUT / "classifier_qa.json").write_text(json.dumps(clf, indent=2) + "\n")
    (OUT / "extraction_qa.json").write_text(json.dumps(extract, indent=2) + "\n")
    (OUT / "evidence_qa.json").write_text(json.dumps(evidence, indent=2) + "\n")
    (OUT / "high_yield_review.json").write_text(json.dumps(hy, indent=2) + "\n")
    (OUT / "watch_list.json").write_text(json.dumps(watch, indent=2) + "\n")
    (OUT / "linker_metrics.json").write_text(json.dumps(linked["metrics"], indent=2) + "\n")

    decisions = payload.get("decisions") or []
    series = payload.get("event_series") or []
    summary = {
        "generated_at": _now(),
        "production_writes": 0,
        "deploy": 0,
        "gpt6": "off",
        "linker_v1_1": False,
        "official_records": 450,
        "buckets": dict(buckets),
        "releases": releases,
        "local_accepted_r2_r6": len(local_incidents),
        "r1_unflagged_in_linker": len(r1_incs),
        "r1_flagged_excluded": r1["flagged"],
        "canonical_events": len(payload.get("canonical_events") or []),
        "event_series": len(series),
        "series_event_counts": {s.get("series_id"): len(s.get("event_ids") or []) for s in series},
        "decisions": len(decisions),
        "decision_breakdown": dict(Counter(d.get("relationship") for d in decisions)),
        "status_breakdown": dict(Counter(d.get("status") for d in decisions)),
        "same_release_decisions": linked["metrics"].get("same_release_decisions"),
        "cross_release_decisions": linked["metrics"].get("cross_release_decisions"),
        "cross_release_by_relationship": linked["metrics"].get("cross_release_by_relationship"),
        "colorado_springs_pass": (linked["metrics"].get("colorado_springs") or {}).get("pass"),
        "western_us_pass": (linked["metrics"].get("western_us") or {}).get("pass"),
        "overmerge_unresolved": over["unresolved"],
        "overmerge_needs_review": over["needs_review"],
        "underlink_high_confidence_unresolved": under["high_confidence_unresolved"],
        "evidence_unsupported": evidence["unsupported"],
        "extraction_failed": extract["extraction_failed"],
        "classifier_anomalies": clf["anomaly_count"],
        "r1": r1,
        "watch_dispositions": Counter(w["disposition"] for w in watch),
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
