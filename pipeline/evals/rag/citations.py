"""Deterministic citation checks. Keep aligned with web/src/lib/rag/citations.ts."""

from __future__ import annotations

import re

CITE_RE = re.compile(r"\[([A-Za-z0-9][A-Za-z0-9._/-]{2,})\]")


def extract_cited_case_ids(text: str) -> list[str]:
    return list(dict.fromkeys(match.group(1).upper() for match in CITE_RE.finditer(text or "")))


def validate_citations(
    answer: str,
    allowed_case_ids: list[str] | set[str],
    excluded_case_ids: list[str] | set[str] | None = None,
    source_only_ids: list[str] | set[str] | None = None,
) -> dict:
    cited = extract_cited_case_ids(answer)
    allowed = {item.upper() for item in allowed_case_ids if item}
    excluded = {item.upper() for item in (excluded_case_ids or []) if item}
    source_only = {item.upper() for item in (source_only_ids or []) if item}
    invalid: list[str] = []
    reasons: list[str] = []
    for case_id in cited:
        if case_id in excluded:
            invalid.append(case_id)
            reasons.append(f"{case_id}: excluded or flagged")
            continue
        if case_id in source_only and case_id not in allowed:
            invalid.append(case_id)
            reasons.append(f"{case_id}: source-only record cited as an incident")
            continue
        if case_id not in allowed:
            invalid.append(case_id)
            reasons.append(f"{case_id}: not in retrieved evidence")
    return {"ok": not invalid, "cited": cited, "invalid": invalid, "reasons": reasons}
