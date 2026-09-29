"""
Compare fixed chunks, page-grouped sections, and cue-routed sections
on one local document. No production writes.

Usage:
  python -m pipeline.compare_section_strategies \\
      --text pipeline/reports/r3_readiness/ocr/FBI-UAP-D012/combined.txt \\
      --filename FBI-UAP-D012.pdf \\
      --out pipeline/reports/r3_readiness/d012_strategy_compare.json
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline.extract import JSON_STATS, reset_json_stats
from pipeline.section_router import diagnose_text, select_chunks
from pipeline.smoke_r2_extract import extract_local, reset_chunk_plan

logger = logging.getLogger(__name__)

STRATEGIES = ("fixed", "page_grouped", "cue_routed")


def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _summarize(incidents: list[dict]) -> list[dict]:
    return [
        {
            "title": inc.get("title"),
            "occurred_at": inc.get("occurred_at"),
            "location_text": inc.get("location_text"),
            "raw_excerpt": (inc.get("raw_excerpt") or "")[:240],
        }
        for inc in incidents
    ]


def compare(text: str, filename: str, agency: str) -> dict:
    signals = diagnose_text(text)
    route_counts: dict[str, int] = {}
    for sig in signals:
        route_counts[sig.route] = route_counts.get(sig.route, 0) + 1

    sf = {"filename": filename, "agency": agency, "file_type": "pdf", "id": f"local:{filename}"}
    strategies = []
    for name in STRATEGIES:
        reset_json_stats()
        reset_chunk_plan()
        planned, chunks = select_chunks(text, strategy=name)
        logger.info("strategy %s -> %s sections=%d", name, planned, len(chunks))
        validated, quote_rej, evidence_rej = extract_local(sf, text, chunk_strategy=name)
        calls = JSON_STATS["json_first_pass"] + 2 * (
            JSON_STATS["json_retry_success"] + JSON_STATS["json_retry_failed"]
        )
        strategies.append(
            {
                "name": name,
                "strategy_used": planned,
                "sections": len(chunks),
                "section_chars": [len(c) for c in chunks],
                "candidates": len(validated) + len(quote_rej) + len(evidence_rej),
                "quote_valid": len(validated) + len(evidence_rej),
                "quote_rejected": len(quote_rej),
                "evidence_insufficient": len(evidence_rej),
                "accepted": len(validated),
                "estimated_haiku_calls": calls,
                "accepted_incidents": _summarize(validated),
                "quote_rejected_titles": [r.get("title") for r in quote_rej],
                "evidence_insufficient_titles": [r.get("title") for r in evidence_rej],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "filename": filename,
        "production_writes": False,
        "page_count": len(signals),
        "route_counts": route_counts,
        "strategies": strategies,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare section strategies on one local file")
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--filename", required=True)
    parser.add_argument("--agency", default="FBI")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    _load_env()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        logger.error("ANTHROPIC_API_KEY is not set; refusing to run a model comparison")
        return 2
    report = compare(args.text.read_text(), args.filename, args.agency)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    for row in report["strategies"]:
        logger.info(
            "%s candidates=%d accepted=%d calls=%d",
            row["name"],
            row["candidates"],
            row["accepted"],
            row["estimated_haiku_calls"],
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
