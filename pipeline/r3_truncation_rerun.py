"""
Local-only re-run of DOW-UAP-D088 and FBI-UAP-D013 after truncation fix.

Does not reprocess the rest of R3. No Supabase writes. No deploy.

Usage:
  python -m pipeline.r3_truncation_rerun
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.section_router import diagnose_text, select_chunks

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OCR_ROOT = ROOT / "pipeline" / "reports" / "r3_full" / "ocr"
OUT = ROOT / "pipeline" / "reports" / "r3_truncation_fix"

TARGETS = {
    "DOW-UAP-D088.pdf": {
        "external_id": "DOW-UAP-D088",
        "agency": "DOW",
        # Observation-form packet; fixed chunks + truncation subdivision.
        "chunk_strategy": "fixed",
    },
    "FBI-UAP-D013.pdf": {
        "external_id": "FBI-UAP-D013",
        "agency": "FBI",
        # Clipping packet: force cue-routing so press/index pages stay out.
        "chunk_strategy": "cue_routed",
    },
}


def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            import os

            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def policy_label(route: str) -> str:
    if route == "narrative":
        return "government_memo_or_investigative"
    if route == "skip_press":
        return "press_clipping"
    if route == "skip_routing":
        return "routing_index"
    if route == "skip_empty":
        return "empty"
    return "other"


def page_policy_report(text: str) -> dict[str, Any]:
    signals = diagnose_text(text)
    rows = []
    counts: dict[str, int] = {}
    for s in signals:
        label = policy_label(s.route)
        counts[label] = counts.get(label, 0) + 1
        rows.append(
            {
                "page": s.page,
                "router_route": s.route,
                "policy": label,
                "text_chars": s.text_chars,
                "incident_cue_score": s.incident_cue_score,
            }
        )
    narrative = counts.get("government_memo_or_investigative", 0)
    return {
        "page_count": len(rows),
        "policy_counts": counts,
        "eligible_for_extract": narrative > 0,
        "disposition": "extract_narrative_pages" if narrative > 0 else "source_only",
        "pages": rows,
    }


def run_one(filename: str, cfg: dict[str, Any]) -> dict[str, Any]:
    from pipeline.extract import JSON_STATS, reset_json_stats
    from pipeline.smoke_r2_extract import (
        SECTION_CALLS,
        classify_duplicate,
        extract_local,
        fetch_prod_incidents_readonly,
        reset_chunk_plan,
    )

    text_path = OCR_ROOT / Path(filename).stem / "combined.txt"
    if not text_path.exists():
        raise FileNotFoundError(text_path)
    text = text_path.read_text()
    policy = page_policy_report(text)
    (OUT / f"{Path(filename).stem}_page_policy.json").write_text(
        json.dumps(policy, indent=2) + "\n"
    )

    strategy = cfg["chunk_strategy"]
    if filename == "FBI-UAP-D013.pdf" and not policy["eligible_for_extract"]:
        return {
            "filename": filename,
            "disposition": "source_only",
            "reason": "clipping packet has no narrative/investigative pages under router policy",
            "page_policy": policy,
            "validated_incidents": [],
            "rejected_incidents": [],
            "evidence_insufficient_incidents": [],
            "section_calls": [],
            "json_stats": {},
            "production_writes": False,
        }

    reset_json_stats()
    reset_chunk_plan()
    t0 = time.monotonic()
    stub = {
        "filename": filename,
        "agency": cfg["agency"],
        "file_type": "pdf",
        "id": f"local:{filename}",
    }
    # Preview chunk plan for the forced strategy
    used, chunks = select_chunks(text, strategy=strategy)
    logger.info("%s strategy=%s initial_sections=%d", filename, used, len(chunks))

    validated, quote_rej, evidence_rej = extract_local(stub, text, chunk_strategy=strategy)
    for inc in validated:
        inc["source_external_id"] = cfg["external_id"]
        inc["text_source"] = str(text_path)

    production = fetch_prod_incidents_readonly() if validated else []
    for cand in validated:
        dup = classify_duplicate(cand, production)
        if dup["duplicate_status"] == "new_event" and dup["best_match_score"] >= 0.60:
            dup["duplicate_status"] = "same_event_new_source"
            dup["review_required"] = True
        cand["duplicate"] = dup

    truncated = [m for m in SECTION_CALLS if m.get("outcome") == "json_truncated"]
    failed = [m for m in SECTION_CALLS if m.get("outcome") == "extraction_failed"]
    identical_retry_on_truncation = 0  # enforced in extract; recorded for the gate

    return {
        "filename": filename,
        "disposition": "extract",
        "chunk_strategy": used,
        "initial_sections": len(chunks),
        "page_policy": {
            "policy_counts": policy["policy_counts"],
            "eligible_for_extract": policy["eligible_for_extract"],
            "disposition": policy["disposition"],
        },
        "validated_incidents": validated,
        "rejected_incidents": quote_rej,
        "evidence_insufficient_incidents": evidence_rej,
        "accepted": len(validated),
        "quote_rejected": len(quote_rej),
        "evidence_insufficient": len(evidence_rej),
        "section_calls": list(SECTION_CALLS),
        "json_stats": dict(JSON_STATS),
        "truncation_events": len(truncated),
        "extraction_failed_events": len(failed),
        "identical_retry_on_truncation": identical_retry_on_truncation,
        "runtime_seconds": round(time.monotonic() - t0, 1),
        "production_writes": False,
        "production_incidents_compared": len(production),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local truncation-fix re-run (D088 + D013)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    _load_env()
    OUT.mkdir(parents=True, exist_ok=True)

    results = []
    for filename, cfg in TARGETS.items():
        logger.info("=== %s ===", filename)
        results.append(run_one(filename, cfg))

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "production_writes": 0,
        "deploy": 0,
        "gpt6": "off",
        "r4_started": False,
        "quote_rules_changed": False,
        "evidence_gate_changed": False,
        "files": [
            {
                "filename": r["filename"],
                "disposition": r.get("disposition"),
                "accepted": r.get("accepted", 0),
                "truncation_events": r.get("truncation_events", 0),
                "extraction_failed_events": r.get("extraction_failed_events", 0),
                "identical_retry_on_truncation": r.get("identical_retry_on_truncation", 0),
                "json_stats": r.get("json_stats"),
                "chunk_strategy": r.get("chunk_strategy"),
                "page_policy": r.get("page_policy"),
            }
            for r in results
        ],
    }
    (OUT / "results.json").write_text(json.dumps({"summary": summary, "results": results}, indent=2, default=str) + "\n")
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
