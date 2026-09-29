"""
Canonical linker V1 — local-only runner.

Usage:
  python -m pipeline.linker.run_v1
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from pathlib import Path
from typing import Any

from pipeline.cache_local_pdfs import ext_id_from_title
from pipeline.linker.audit import write_audit
from pipeline.linker.candidate_generation import generate_candidates
from pipeline.linker.relationship_rules import apply_rules

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
R3_FULL = ROOT / "pipeline" / "reports" / "r3_full"
TRUNC = ROOT / "pipeline" / "reports" / "r3_truncation_fix"
OUT = ROOT / "pipeline" / "reports" / "linker_v1"
CSV_PATH = ROOT / "pipeline" / "snapshots" / "pursue" / "2026-09-18-official" / "uap-data.csv"
OCR_ROOT = R3_FULL / "ocr"


def load_catalog() -> dict[str, dict[str, Any]]:
    catalog: dict[str, dict[str, Any]] = {}
    with CSV_PATH.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            title = row.get("Title") or ""
            eid = ext_id_from_title(title)
            if not eid:
                continue
            entry = {
                "title": title,
                "type": (row.get("Type") or "").strip().upper(),
                "pdf_pairing": row.get("PDF Pairing") or "",
                "incident_location": row.get("Incident Location") or "",
                "incident_date": row.get("Incident Date") or "",
                "description": row.get("Description Blurb") or "",
                "agency": row.get("Agency") or "",
            }
            prev = catalog.get(eid)
            # FBI-UAP-D014 is both an R4 correspondence PDF and an R3 rendering.
            # The PDF must keep its own pairing; the image must not overwrite it.
            if prev and prev.get("type") == "PDF" and entry["type"] != "PDF":
                prev.setdefault("alternate_assets", []).append(entry)
                continue
            if prev and prev.get("type") != "PDF" and entry["type"] == "PDF":
                entry["alternate_assets"] = [prev]
            catalog[eid] = entry
    return catalog


def load_incidents() -> list[dict[str, Any]]:
    full = json.loads((R3_FULL / "extractions.json").read_text())
    incs = [
        i
        for i in full["validated_incidents"]
        if i.get("source_filename") not in {"DOW-UAP-D088.pdf", "FBI-UAP-D013.pdf"}
    ]
    trunc_path = TRUNC / "results.json"
    if trunc_path.exists():
        trunc = json.loads(trunc_path.read_text())
        for result in trunc.get("results") or []:
            incs.extend(result.get("validated_incidents") or [])
    return incs


def load_classifications() -> list[dict[str, Any]]:
    return json.loads((R3_FULL / "classifications.json").read_text())["results"]


def load_texts(classifications: list[dict[str, Any]]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for row in classifications:
        clf = row.get("classification") or {}
        if clf.get("document_class") in {"analysis", "correspondence", "media_metadata"} or not clf.get(
            "contains_incidents"
        ):
            path = Path(row.get("text_path") or OCR_ROOT / Path(row["filename"]).stem / "combined.txt")
            if path.exists():
                texts[row["filename"]] = path.read_text()
    # Always load ICA / FBI-D003 for Colorado Springs
    for stem in ("ICA-UAP-D001", "FBI-UAP-D003", "FBI-UAP-D002"):
        path = OCR_ROOT / stem / "combined.txt"
        if path.exists():
            texts[f"{stem}.pdf"] = path.read_text()
    return texts


def refine_colorado_label(payload: dict[str, Any]) -> None:
    """Human-readable label when Cheyenne/Colorado Springs evidence is present."""
    members = payload.get("event_members") or []
    d002_ids = {m["event_id"] for m in members if m.get("source_filename") == "FBI-UAP-D002.pdf"}
    for event in payload.get("canonical_events") or []:
        if event["event_id"] not in d002_ids:
            continue
        event["label"] = "Colorado Springs 2022"
        event["location_text"] = event.get("location_text") or "Cheyenne Mountains / Colorado Springs"
        if "2022" not in (event.get("notes") or []):
            event.setdefault("notes", []).append("Labeled from Colorado Springs fixture evidence")


def run() -> dict[str, Any]:
    incidents = load_incidents()
    classifications = load_classifications()
    catalog = load_catalog()
    texts = load_texts(classifications)

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
    refine_colorado_label(payload)
    metrics = write_audit(OUT, payload)
    logger.info("linker metrics: %s", json.dumps(metrics, indent=2))
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Canonical linker V1 (local only)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format="%(levelname)s %(message)s")
    metrics = run()
    print(json.dumps(metrics, indent=2))
    colorado_ok = metrics["colorado_springs"]["pass"]
    western_ok = metrics["western_us"]["pass"]
    return 0 if colorado_ok and western_ok else 1


if __name__ == "__main__":
    sys.exit(main())
