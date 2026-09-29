"""Aggregate the local V2 gate. Does not write production or deploy."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REVIEWED = {
    "official_records": 450,
    "fragments": 583,
    "canonical_events": 575,
    "western_us_events": 21,
    "audio": 16,
    "local_accepted_r2_r6": 203,
}


def run_module(module: str) -> dict:
    completed = subprocess.run([sys.executable, "-m", module], cwd=ROOT, capture_output=True, text=True)
    return {
        "module": module,
        "returncode": completed.returncode,
        "tail": (completed.stdout + completed.stderr)[-1500:],
    }


def corpus_counts() -> dict:
    coverage = json.loads((ROOT / "pipeline/reports/corpus_qa/source_coverage.json").read_text())
    graph = json.loads((ROOT / "pipeline/reports/corpus_qa/linker/full_graph.json").read_text())
    summary = json.loads((ROOT / "pipeline/reports/corpus_qa/summary.json").read_text())
    fragment_ids = set()
    for event in graph["canonical_events"]:
        for case_id in event.get("member_case_ids") or []:
            fragment_ids.add(case_id.upper())
    western = next(series for series in graph["event_series"] if series["series_id"] == "western-us-event-2023")
    audio = sum(1 for row in coverage["records"] if row.get("type") == "audio")
    actual = {
        "official_records": len(coverage["records"]),
        "fragments": len(fragment_ids),
        "canonical_events": len(graph["canonical_events"]),
        "western_us_events": len(western["event_ids"]),
        "audio": audio,
        "local_accepted_r2_r6": summary.get("local_accepted_r2_r6"),
        "corpus_qa_verdict": summary.get("verdict"),
        "overmerge_unresolved": summary.get("overmerge_unresolved"),
        "underlink_high_confidence_unresolved": summary.get("underlink_high_confidence_unresolved"),
        "extraction_failed": summary.get("extraction_failed"),
        "colorado_springs_pass": summary.get("colorado_springs_pass"),
        "western_us_pass": summary.get("western_us_pass"),
    }
    mismatches = {
        key: {"actual": actual[key], "reviewed": expected}
        for key, expected in REVIEWED.items()
        if actual.get(key) != expected
    }
    actual["reviewed_mismatches"] = mismatches
    return actual


def rag_status() -> dict:
    path = ROOT / "pipeline/evals/rag/results/summary.json"
    if not path.exists():
        return {"present": False}
    return {"present": True, **json.loads(path.read_text())}


def main() -> None:
    modules = [
        "pipeline.tests.test_validation",
        "pipeline.tests.test_quote_normalization",
        "pipeline.tests.test_evidence_sufficiency",
        "pipeline.tests.test_extraction_truncation",
        "pipeline.tests.test_classify_document",
        "pipeline.tests.test_r2_smoke_classifier_fixtures",
        "pipeline.tests.test_r3_classifier_fixtures",
        "pipeline.tests.test_r6_classifier_fixtures",
        "pipeline.tests.linker.test_linker_v1",
        "pipeline.tests.test_rag_citations",
        "pipeline.tests.test_rag_scoring",
        "pipeline.tests.test_embedding_provider",
    ]
    tests = [run_module(module) for module in modules]
    report = {
        "corpus": corpus_counts(),
        "tests": tests,
        "rag": rag_status(),
        "production_writes": 0,
        "deploy": 0,
    }
    out = ROOT / "pipeline/reports/qa_v2_gate.json"
    out.write_text(json.dumps(report, indent=2))
    failed = [item["module"] for item in tests if item["returncode"] != 0]
    mismatches = report["corpus"]["reviewed_mismatches"]
    print(json.dumps({"failed_tests": failed, "reviewed_mismatches": mismatches, "rag_present": report["rag"].get("present")}, indent=2))
    if failed or mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
