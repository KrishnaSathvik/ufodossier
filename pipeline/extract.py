"""
ufodossier // extract

The most important file in the pipeline. Takes OCR'd source text and asks
Claude Haiku to structure it into incident rows. Every field must be
supported by a verbatim excerpt that actually appears in the source — we
substring-validate before writing to the DB. If validation fails, we drop
the field rather than risk hallucination on a public site.

Usage:
    python -m pipeline.extract --limit 10
    python -m pipeline.extract --source-file-id <uuid>
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

import anthropic

from pipeline.db import get_supabase, upsert_incident
from pipeline.embed import embed_batch

logger = logging.getLogger(__name__)

EXTRACTION_MODEL = "claude-haiku-4-5"
EXTRACTION_VERSION = "v1.2"
MAX_INPUT_CHARS = 60_000  # safety cap; chunk longer docs
MAX_SPLIT_DEPTH = 4
MIN_SECTION_PAGES = 1
# Soft ceiling: if a section still truncates, page-boundary splits shrink toward this.
TARGET_SECTION_PAGES = 20

# JSON / call telemetry (local smoke / extract runs)
JSON_STATS: dict[str, int] = {
    "json_first_pass": 0,
    "json_retry_success": 0,
    "json_retry_failed": 0,
    "json_truncated": 0,
    "json_invalid": 0,
    "api_error": 0,
    "valid": 0,
    "extraction_failed": 0,
    "sections_subdivided": 0,
    "haiku_calls": 0,
}

_PAGE_MARKER_RE = re.compile(r"^--- PAGE (\d+) ---\s*", re.M)
_SECTION_COUNTER = 0

SYSTEM_PROMPT = """You are extracting structured incident data from a declassified U.S. government document about Unidentified Anomalous Phenomena (UAP).

Your output MUST be a valid JSON array of incident objects. Each incident represents ONE distinct UAP encounter described in the source.

CRITICAL RULES:
1. Every field must be SUPPORTED BY THE SOURCE TEXT. If a field isn't in the source, return null.
2. Each incident MUST include a `raw_excerpt` field containing 1-3 sentences of VERBATIM text copied exactly from the source. This excerpt must support the structured claims.
3. raw_excerpt MUST be copied character-for-character from SOURCE TEXT AS PROVIDED.
   Do NOT: correct spelling, fix OCR errors, expand abbreviations, normalize punctuation,
   repair grammar, or reconstruct missing characters.
   If OCR says `objecf`, raw_excerpt must say `objecf`, not `object`.
   The `summary` field MAY use clean language; the evidence quote MUST NOT.
4. NEVER infer, embellish, or speculate. If the source says "an object was observed" do not write "a UFO was observed" — preserve the document's hedging.
5. NEVER fabricate dates, locations, or names. If unclear, use null.
6. The `summary` field must be your own 1-2 sentence factual restatement, not copied text.
7. One document may contain zero, one, or many incidents. A single incident may be referenced multiple times — only return it once.
8. Redacted text in the source (██████ or [REDACTED]) should be preserved as ████ in raw_excerpt and not invented.
9. Image captions or titles alone are NOT incidents. If the source only has a short caption without an encounter narrative, return [].
10. This call receives ONE section of a larger file. Extract only encounters fully supported inside THIS section. If the section holds many encounters, return every distinct encounter you can support here with a verbatim raw_excerpt — do not invent, and do not omit a supported encounter to shorten the reply. Sections are processed independently.

OUTPUT SCHEMA (JSON array of objects):
[
  {
    "title": "short headline, <80 chars",
    "summary": "1-2 sentence factual restatement in your own words",
    "raw_excerpt": "verbatim text from source, 1-3 sentences",
    "occurred_at_text": "raw date string from source or null",
    "occurred_at": "YYYY-MM-DD or null — ONLY set this if the source contains a clearly specific date (e.g. 'March 15, 2024' -> '2024-03-15'). Fuzzy phrases like 'Late 2025', 'Early 2024', 'Recently', 'Last summer' MUST produce null here. Never default to January 1 of any year.",
    "occurred_at_precision": "day|month|year|decade|unknown",
    "location_text": "raw location string from source or null",
    "country": "country name or null",
    "region": "state/province/sea or null",
    "branch": "USAF|USN|USMC|USA|NASA|FBI|DOS|NORTHCOM|CENTCOM|INDOPACOM|EUCOM|AARO|other or null",  # TODO: Haiku sometimes writes the JSON string "null" instead of JSON null for branch. A future migration should UPDATE incidents SET branch = NULL WHERE branch = 'null' to clean these up.
    "reporting_unit": "specific unit/office mentioned or null",
    "sensor_types": ["eyewitness"|"infrared"|"radar"|"photo"|"video"],
    "duration_seconds": integer or null,
    "altitude_feet": integer or null,
    "shape_description": "brief shape description from source or null",
    "size_description": "brief size description from source or null",
    "resolution_status": "unresolved|identified|insufficient_data",
    "resolution_notes": "if identified, what was it; if unresolved, brief note or null"
  }
]

If the document contains no UAP incidents, return [].
Output ONLY the JSON array. No prose, no markdown fences, no explanation.
"""


def extract_from_source_file(sf: dict[str, Any], client: anthropic.Anthropic) -> list[dict]:
    """Run Haiku on a source file's OCR text, return validated incident dicts."""
    text = sf.get("ocr_text") or sf.get("transcript") or ""
    if not text or len(text.strip()) < 50:
        logger.info("skipping %s: no text", sf["filename"])
        return []

    # chunk if needed (rare for individual war.gov pdfs but defensive)
    chunks = _chunk(text, MAX_INPUT_CHARS)
    all_incidents: list[dict] = []

    for chunk_idx, chunk in enumerate(chunks):
        logger.info("extracting %s chunk %d/%d (%d chars)", sf["filename"], chunk_idx + 1, len(chunks), len(chunk))
        incidents = _call_haiku(client, chunk, sf)
        for inc in incidents:
            validated = _validate_incident(inc, chunk, sf)
            if not validated:
                continue
            ok_ev, reason = evidence_sufficient(validated)
            if not ok_ev:
                logger.warning(
                    "dropping incident in %s after quote match: insufficient evidence (%s)",
                    sf["filename"],
                    reason,
                )
                continue
            all_incidents.append(validated)

    return all_incidents


def _chunk(text: str, max_chars: int) -> list[str]:
    """Split on paragraph boundaries when possible. Hard-splits oversized paragraphs."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    paragraphs = text.split("\n\n")
    current = ""
    for p in paragraphs:
        # hard-split any single paragraph that exceeds max_chars
        if len(p) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            for i in range(0, len(p), max_chars):
                chunks.append(p[i:i + max_chars])
            continue
        if len(current) + len(p) > max_chars and current:
            chunks.append(current)
            current = p
        else:
            current = (current + "\n\n" + p) if current else p
    if current:
        chunks.append(current)
    return chunks


def reset_json_stats() -> None:
    for k in JSON_STATS:
        JSON_STATS[k] = 0
    global _SECTION_COUNTER
    _SECTION_COUNTER = 0


def _next_section_id() -> str:
    global _SECTION_COUNTER
    _SECTION_COUNTER += 1
    return f"sec-{_SECTION_COUNTER}"


def _strip_fences(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _parse_incident_json(raw: str, filename: str) -> list[dict] | None:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.error("haiku returned invalid JSON for %s: %s", filename, e)
        logger.debug("raw output: %s", raw[:500])
        return None
    if not isinstance(parsed, list):
        logger.error("haiku output not a list for %s", filename)
        return None
    return parsed


def pages_in_section(text: str) -> list[tuple[int, str]]:
    matches = list(_PAGE_MARKER_RE.finditer(text))
    if not matches:
        body = text.strip()
        return [(1, body)] if body else []
    pages: list[tuple[int, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pages.append((int(match.group(1)), text[start:end].strip()))
    return pages


def join_pages(pages: list[tuple[int, str]]) -> str:
    return "\n\n".join(f"--- PAGE {num} ---\n{body}" for num, body in pages)


def split_section_at_midpoint(text: str) -> tuple[str, str]:
    """Split on page boundaries only. Raises if fewer than two pages."""
    pages = pages_in_section(text)
    if len(pages) < 2:
        raise ValueError("cannot split a single-page section at a page boundary")
    mid = len(pages) // 2
    return join_pages(pages[:mid]), join_pages(pages[mid:])


def _stamp_section(incidents: list[dict], text: str) -> list[dict]:
    out = []
    for inc in incidents:
        if not isinstance(inc, dict):
            continue
        row = dict(inc)
        row["_section_text"] = text
        out.append(row)
    return out


def _haiku_request(
    client: anthropic.Anthropic,
    *,
    system: str,
    messages: list[dict],
) -> Any:
    JSON_STATS["haiku_calls"] += 1
    return client.messages.create(
        model=EXTRACTION_MODEL,
        max_tokens=4096,
        system=system,
        messages=messages,
    )


def _classify_response(resp: Any, filename: str) -> tuple[str, list[dict] | None, str, str]:
    """
    Returns (outcome, parsed_or_none, stop_reason, raw_text).
    outcome: valid | json_truncated | json_invalid | api_error
    """
    stop_reason = getattr(resp, "stop_reason", None) or "end_turn"
    raw = _strip_fences(resp.content[0].text if resp.content else "")
    if stop_reason == "max_tokens":
        return "json_truncated", None, stop_reason, raw
    parsed = _parse_incident_json(raw, filename)
    if parsed is not None:
        return "valid", parsed, stop_reason, raw
    return "json_invalid", None, stop_reason, raw


def _section_meta(
    *,
    section_id: str,
    parent_section_id: str | None,
    split_depth: int,
    page_start: int | None,
    page_end: int | None,
    stop_reason: str | None,
    outcome: str,
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "parent_section_id": parent_section_id,
        "split_depth": split_depth,
        "page_start": page_start,
        "page_end": page_end,
        "stop_reason": stop_reason,
        "outcome": outcome,
    }


def extract_chunk_with_subdivision(
    client: anthropic.Anthropic,
    text: str,
    sf: dict,
    *,
    split_depth: int = 0,
    parent_section_id: str | None = None,
) -> tuple[list[dict], list[dict]]:
    """
    Extract one section. Truncation subdivides at page boundaries.
    Malformed JSON (normal stop) gets one same-input retry.
    Truncation never retries the identical chunk.
    """
    section_id = _next_section_id()
    pages = pages_in_section(text)
    page_start = pages[0][0] if pages else None
    page_end = pages[-1][0] if pages else None
    metas: list[dict] = []

    user_prompt = f"""SOURCE DOCUMENT METADATA:
filename: {sf['filename']}
agency: {sf.get('agency', 'unknown')}
file_type: {sf['file_type']}

SOURCE TEXT:
{text}

Extract every distinct UAP incident as JSON per the schema. Output ONLY the JSON array.
Remember: raw_excerpt must match SOURCE TEXT character-for-character (keep OCR typos)."""

    try:
        resp = _haiku_request(
            client,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except anthropic.APIError as e:
        logger.error("haiku api error on %s: %s", sf["filename"], e)
        JSON_STATS["api_error"] += 1
        metas.append(
            _section_meta(
                section_id=section_id,
                parent_section_id=parent_section_id,
                split_depth=split_depth,
                page_start=page_start,
                page_end=page_end,
                stop_reason=None,
                outcome="api_error",
            )
        )
        return [], metas

    outcome, parsed, stop_reason, raw = _classify_response(resp, sf["filename"])

    if outcome == "valid":
        JSON_STATS["valid"] += 1
        JSON_STATS["json_first_pass"] += 1
        metas.append(
            _section_meta(
                section_id=section_id,
                parent_section_id=parent_section_id,
                split_depth=split_depth,
                page_start=page_start,
                page_end=page_end,
                stop_reason=stop_reason,
                outcome="valid",
            )
        )
        return _stamp_section(parsed or [], text), metas

    if outcome == "json_truncated":
        JSON_STATS["json_truncated"] += 1
        metas.append(
            _section_meta(
                section_id=section_id,
                parent_section_id=parent_section_id,
                split_depth=split_depth,
                page_start=page_start,
                page_end=page_end,
                stop_reason=stop_reason,
                outcome="json_truncated",
            )
        )
        return _subdivide_after_truncation(
            client,
            text,
            sf,
            split_depth=split_depth,
            parent_section_id=section_id,
            prior_metas=metas,
        )

    # json_invalid with a normal stop — one same-input retry only.
    JSON_STATS["json_invalid"] += 1
    logger.warning("retrying JSON once for %s (malformed, not truncated)", sf["filename"])
    retry_prompt = (
        "Your previous response was not valid JSON. "
        "Return ONLY a valid JSON array conforming to the extraction schema. "
        "No prose, no markdown fences, no trailing commentary."
    )
    try:
        resp2 = _haiku_request(
            client,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw[:2000]},
                {"role": "user", "content": retry_prompt},
            ],
        )
    except anthropic.APIError as e:
        logger.error("haiku retry api error on %s: %s", sf["filename"], e)
        JSON_STATS["json_retry_failed"] += 1
        metas.append(
            _section_meta(
                section_id=section_id,
                parent_section_id=parent_section_id,
                split_depth=split_depth,
                page_start=page_start,
                page_end=page_end,
                stop_reason=None,
                outcome="api_error",
            )
        )
        return [], metas

    outcome2, parsed2, stop2, _raw2 = _classify_response(resp2, sf["filename"])
    if outcome2 == "valid":
        JSON_STATS["json_retry_success"] += 1
        JSON_STATS["valid"] += 1
        metas.append(
            _section_meta(
                section_id=section_id,
                parent_section_id=parent_section_id,
                split_depth=split_depth,
                page_start=page_start,
                page_end=page_end,
                stop_reason=stop2,
                outcome="valid",
            )
        )
        return _stamp_section(parsed2 or [], text), metas

    if outcome2 == "json_truncated":
        JSON_STATS["json_truncated"] += 1
        JSON_STATS["json_retry_failed"] += 1
        metas.append(
            _section_meta(
                section_id=section_id,
                parent_section_id=parent_section_id,
                split_depth=split_depth,
                page_start=page_start,
                page_end=page_end,
                stop_reason=stop2,
                outcome="json_truncated",
            )
        )
        return _subdivide_after_truncation(
            client,
            text,
            sf,
            split_depth=split_depth,
            parent_section_id=section_id,
            prior_metas=metas,
        )

    JSON_STATS["json_retry_failed"] += 1
    metas.append(
        _section_meta(
            section_id=section_id,
            parent_section_id=parent_section_id,
            split_depth=split_depth,
            page_start=page_start,
            page_end=page_end,
            stop_reason=stop2,
            outcome="json_invalid",
        )
    )
    return [], metas


def _subdivide_after_truncation(
    client: anthropic.Anthropic,
    text: str,
    sf: dict,
    *,
    split_depth: int,
    parent_section_id: str,
    prior_metas: list[dict],
) -> tuple[list[dict], list[dict]]:
    pages = pages_in_section(text)
    if split_depth >= MAX_SPLIT_DEPTH or len(pages) <= MIN_SECTION_PAGES:
        logger.error(
            "extraction_failed for %s at depth=%d pages=%d (truncated, cannot split further)",
            sf["filename"],
            split_depth,
            len(pages),
        )
        JSON_STATS["extraction_failed"] += 1
        failed = dict(prior_metas[-1]) if prior_metas else {}
        failed["outcome"] = "extraction_failed"
        return [], prior_metas[:-1] + [failed] if prior_metas else [
            _section_meta(
                section_id=parent_section_id,
                parent_section_id=None,
                split_depth=split_depth,
                page_start=pages[0][0] if pages else None,
                page_end=pages[-1][0] if pages else None,
                stop_reason="max_tokens",
                outcome="extraction_failed",
            )
        ]

    JSON_STATS["sections_subdivided"] += 1
    left, right = split_section_at_midpoint(text)
    logger.info(
        "subdividing %s after truncation depth=%d pages=%d→%d+%d",
        sf["filename"],
        split_depth,
        len(pages),
        len(pages_in_section(left)),
        len(pages_in_section(right)),
    )
    left_incs, left_metas = extract_chunk_with_subdivision(
        client,
        left,
        sf,
        split_depth=split_depth + 1,
        parent_section_id=parent_section_id,
    )
    right_incs, right_metas = extract_chunk_with_subdivision(
        client,
        right,
        sf,
        split_depth=split_depth + 1,
        parent_section_id=parent_section_id,
    )
    return left_incs + right_incs, prior_metas + left_metas + right_metas


def dedupe_within_source(incidents: list[dict]) -> list[dict]:
    """
    Deterministic within-source dedupe after subdivision.
    Same normalized excerpt, or same date+location with high excerpt overlap.
    """
    from difflib import SequenceMatcher

    kept: list[dict] = []
    for cand in incidents:
        excerpt = _normalize_for_match(cand.get("raw_excerpt") or "")
        if not excerpt:
            kept.append(cand)
            continue
        duplicate = False
        for prior in kept:
            prior_ex = _normalize_for_match(prior.get("raw_excerpt") or "")
            if excerpt == prior_ex:
                duplicate = True
                break
            if len(excerpt) >= 40 and len(prior_ex) >= 40:
                overlap = SequenceMatcher(None, excerpt, prior_ex).ratio()
                same_date = (cand.get("occurred_at") or "") == (prior.get("occurred_at") or "")
                same_loc = (cand.get("location_text") or "").strip().lower() == (
                    prior.get("location_text") or ""
                ).strip().lower()
                if overlap >= 0.92 or (overlap >= 0.85 and same_date and same_loc):
                    duplicate = True
                    break
        if not duplicate:
            kept.append(cand)
    return kept


def _call_haiku(client: anthropic.Anthropic, text: str, sf: dict) -> list[dict]:
    """Backward-compatible wrapper. Subdivision runs on truncation."""
    incidents, _metas = extract_chunk_with_subdivision(client, text, sf)
    return incidents


# Deterministic evidence-sufficiency (after substring validation passes).
_OBSERVATION_RE = re.compile(
    r"\b(observ|sight|witness|report|appear|detect|radar|sensor|object|craft|"
    r"phenomenon|fireball|light|unidentified|uap|ufo|aircraft|flew|hover|"
    r"altitude|visual|contact)\w*\b",
    re.I,
)
MIN_EVIDENCE_EXCERPT_CHARS = 80
MIN_EVIDENCE_WORD_COUNT = 12


def evidence_sufficient(inc: dict) -> tuple[bool, str]:
    """
    Quote exists ≠ claim supported. Thin captions must not become public incidents.
    Does NOT relax substring matching — only adds a sufficiency bar after it passes.
    """
    excerpt = (inc.get("raw_excerpt") or "").strip()
    if len(excerpt) < MIN_EVIDENCE_EXCERPT_CHARS:
        return False, "excerpt_too_short_for_claim"
    words = re.findall(r"[A-Za-z0-9']+", excerpt)
    if len(words) < MIN_EVIDENCE_WORD_COUNT:
        return False, "excerpt_too_few_words"
    if not _OBSERVATION_RE.search(excerpt):
        return False, "excerpt_lacks_observation_language"
    title = (inc.get("title") or "").lower()
    if "image from" in excerpt.lower() and len(excerpt) < 120:
        return False, "thin_media_caption"
    if re.search(r"\b(page \d+ of \d+|ucni)\b", excerpt, re.I) and len(excerpt) < 100:
        return False, "thin_media_caption"
    if "incident report" in title and len(excerpt) < 100 and not re.search(
        r"\b(observ|sight|detect|appear)\w*\b", excerpt, re.I
    ):
        return False, "thin_media_caption"
    return True, "ok"


# Function words and agency abbreviations must not be glued to the next token.
# Joining is only for OCR spaces inserted inside a word, not spelling repair.
_OCR_STOPWORDS = frozenset(
    """
    a i of to in on at be we he or an as by if is it my no so up us do go am me
    the and for was were that with from this they have had his her she not but
    its are has been said over into then than also only out our you your who all
    can may any did him too
    """.split()
)
_OCR_ABBREV = frozenset(
    {"mr", "ms", "dr", "sa", "af", "hq", "pm", "nj", "ny", "dc", "uk", "re"}
)


def _collapse_ocr_letter_spacing(s: str) -> str:
    """Collapse OCR spaces inserted inside a word.

    Applied to both the excerpt and the source, so lexical identity is kept:
    ``bui l ding`` and ``building`` both become ``building``.
    A lone ``l``/``i`` is glued only when both neighbors look like word
    fragments. ``to l ook`` becomes ``to look``, not ``tolook``.
    Ordinary word spaces stay: ``the object`` stays ``the object``.
    This is not spelling correction and not fuzzy matching.
    """
    def _core_punct(tok: str) -> tuple[str, str]:
        match = re.match(r"^([a-z]*)([^a-z]*)$", tok)
        if not match:
            return tok, ""
        return match.group(1), match.group(2)

    tokens = s.split(" ")
    changed = True
    while changed:
        changed = False
        out: list[str] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            nxt = tokens[i + 1] if i + 1 < len(tokens) else ""
            left = out[-1] if out else ""
            left_core, left_punct = _core_punct(left) if left else ("", "")
            nxt_core, nxt_punct = _core_punct(nxt) if nxt else ("", "")
            # "bui l ding." / "inte l ligence": fragment + lone letter + fragment.
            if (
                tok in {"l", "i"}
                and left_core.isalpha()
                and nxt_core.isalpha()
                and len(left_core) >= 3
                and len(nxt_core) >= 3
                and left_core not in _OCR_STOPWORDS
                and nxt_core not in _OCR_STOPWORDS
                and left_core not in _OCR_ABBREV
                and not left_punct
            ):
                out[-1] = left_core + tok + nxt_core + nxt_punct
                i += 2
                changed = True
                continue
            # "pane l on": lone letter finishes the previous word; next word stays.
            if (
                tok in {"l", "i"}
                and left_core.isalpha()
                and len(left_core) >= 3
                and left_core not in _OCR_STOPWORDS
                and left_core not in _OCR_ABBREV
                and not left_punct
                and nxt_core in _OCR_STOPWORDS
            ):
                out[-1] = left_core + tok + left_punct
                i += 1
                changed = True
                continue
            # "to l ook" / leading "l ook": attach l to the following fragment only.
            if (
                tok == "l"
                and nxt_core.isalpha()
                and len(nxt_core) >= 3
                and nxt_core not in _OCR_STOPWORDS
                and (
                    not left_core
                    or left_core in _OCR_STOPWORDS
                    or left_core in _OCR_ABBREV
                )
            ):
                out.append("l" + nxt_core + nxt_punct)
                i += 2
                changed = True
                continue
            # "wi th", "di stinct": short non-word shards, not "to look" or "red orb".
            tok_core, tok_punct = _core_punct(tok)
            if (
                nxt
                and tok_core.isalpha()
                and nxt_core.isalpha()
                and not tok_punct
                and tok_core not in _OCR_STOPWORDS
                and nxt_core not in _OCR_STOPWORDS
                and tok_core not in _OCR_ABBREV
            ):
                both_fragments = len(tok_core) <= 2 and len(nxt_core) <= 2
                prefix_split = len(tok_core) == 2 and len(nxt_core) >= 4
                if both_fragments or prefix_split:
                    out.append(tok_core + nxt_core + nxt_punct)
                    i += 2
                    changed = True
                    continue
            out.append(tok)
            i += 1
        tokens = out
    return " ".join(tokens)


def _normalize_for_match(s: str) -> str:
    """Normalize text for verbatim substring checks.

    Preserves lexical identity. Allows:
    line-wrap joins, page-marker removal, end-of-line hyphen joins,
    space-before-punctuation, and OCR spaces inserted between letters.

    Does not correct spelling, fuzzy-match meaning, or repair quotes with a model.
    """
    s = s.replace("\u00ad", "")
    s = re.sub(r"---\s*PAGE\s+\d+\s*---", " ", s)
    s = re.sub(r"([A-Za-z])-\s+([A-Za-z])", r"\1\2", s)
    s = re.sub(r"\s+", " ", s.strip().lower())
    s = re.sub(r"\s+([.,;:!?])", r"\1", s)
    return _collapse_ocr_letter_spacing(s)


def _validate_incident(inc: dict, source_text: str, sf: dict) -> dict | None:
    """
    Critical step: verify raw_excerpt is actually in source_text.
    If not, drop the incident entirely — it's likely hallucinated.
    """
    if not isinstance(inc, dict):
        return None

    excerpt = inc.get("raw_excerpt", "")
    if not excerpt or len(excerpt.strip()) < 20:
        logger.warning("dropping incident in %s: missing/short raw_excerpt", sf["filename"])
        return None

    norm_source = _normalize_for_match(source_text)
    norm_excerpt = _normalize_for_match(excerpt)

    # check if at least 80% of the excerpt's words appear contiguously
    if norm_excerpt in norm_source:
        match_ok = True
    else:
        # fallback: check if 90% of excerpt words appear in any 200-char window of source
        excerpt_words = set(norm_excerpt.split())
        match_ok = False
        for i in range(0, len(norm_source) - len(norm_excerpt), 100):
            window = norm_source[i : i + len(norm_excerpt) + 200]
            window_words = set(window.split())
            if excerpt_words and len(excerpt_words & window_words) / len(excerpt_words) >= 0.9:
                match_ok = True
                break

    if not match_ok:
        logger.warning(
            "dropping incident in %s: raw_excerpt not found in source. excerpt=%r",
            sf["filename"], excerpt[:120],
        )
        return None

    # required fields
    if not inc.get("title") or not inc.get("summary"):
        logger.warning("dropping incident in %s: missing title or summary", sf["filename"])
        return None

    if inc.get("resolution_status") not in ("unresolved", "identified", "insufficient_data"):
        inc["resolution_status"] = "insufficient_data"

    # clean date
    if inc.get("occurred_at"):
        try:
            datetime.strptime(inc["occurred_at"], "%Y-%m-%d")
        except (ValueError, TypeError):
            inc["occurred_at"] = None

    # clean sensor_types
    valid_sensors = {"eyewitness", "infrared", "radar", "photo", "video"}
    sensors = inc.get("sensor_types") or []
    inc["sensor_types"] = [s for s in sensors if s in valid_sensors]

    inc["source_file_id"] = sf["id"]
    inc["case_id"] = _generate_case_id(inc, sf)
    inc["slug"] = _generate_slug(inc)
    inc["extraction_model"] = EXTRACTION_MODEL
    inc["extraction_version"] = EXTRACTION_VERSION
    inc["extracted_at"] = datetime.now(timezone.utc).isoformat()

    return inc


def _generate_slug(inc: dict) -> str:
    """Generate a human-readable URL slug.
    Format: {year}-{branch}-{first-3-words-kebab}-{4charhash}
    Example: 2024-indopacom-football-shaped-object-a1b2
    """
    import hashlib

    # year part
    year = "undated"
    if inc.get("occurred_at"):
        year = inc["occurred_at"].split("-")[0]

    # branch part
    branch = (inc.get("branch") or "gov").lower().replace(" ", "")

    # first 3+ words of title, kebab-cased
    title = inc.get("title", "untitled")
    words = re.findall(r"[a-z0-9]+", title.lower())
    title_slug = "-".join(words[:5]) if words else "untitled"

    # 4 char hash for uniqueness
    h = hashlib.sha1(inc.get("raw_excerpt", title).encode()).hexdigest()[:4]

    return f"{year}-{branch}-{title_slug}-{h}"


def _generate_case_id(inc: dict, sf: dict) -> str:
    """Generate a stable, human-readable case ID.

    TODO: Some existing incidents have UNDATED- prefixed case_ids but later gained
    real dates via re-extraction (e.g. "UNDATED-USAF-11F3" with date 1949-08-19).
    Case_ids are stable identifiers used in URLs, so we cannot simply regenerate them.
    Future runs should detect this case (UNDATED prefix + non-null occurred_at) and
    log a warning, or provide a migration path that sets up redirects from old to new IDs.
    """
    date_part = "UNDATED"
    if inc.get("occurred_at"):
        date_part = inc["occurred_at"].split("-")[0]

    branch = (inc.get("branch") or sf.get("agency") or "GOV").upper().replace(" ", "")[:10]

    # short hash of the excerpt for uniqueness (6 hex chars = 16M combinations)
    import hashlib
    h = hashlib.sha1(inc["raw_excerpt"].encode()).hexdigest()[:6].upper()

    return f"{date_part}-{branch}-{h}"


def run(limit: int | None = None, source_file_id: str | None = None, skip_embed: bool = False) -> None:
    sb = get_supabase()
    client = anthropic.Anthropic()

    # find source files with extractable text (OCR for PDFs, transcript for videos)
    q_ocr = sb.table("source_files").select("*").not_.is_("ocr_text", "null")
    q_transcript = sb.table("source_files").select("*").not_.is_("transcript", "null")
    if source_file_id:
        q_ocr = q_ocr.eq("id", source_file_id)
        q_transcript = q_transcript.eq("id", source_file_id)
    if limit:
        q_ocr = q_ocr.limit(limit)
        q_transcript = q_transcript.limit(limit)

    rows_ocr = q_ocr.execute().data
    rows_transcript = q_transcript.execute().data
    seen_ids = {r["id"] for r in rows_ocr}
    rows = rows_ocr + [r for r in rows_transcript if r["id"] not in seen_ids]
    logger.info("found %d source files to extract from (%d ocr, %d transcript)", len(rows), len(rows_ocr), len(rows_transcript))

    total_incidents = 0
    for sf in rows:
        # Skip photo-only sources where OCR text is just a community-written
        # image caption, not real document narrative. These files still appear
        # in /media (via source_files) but should not produce incident rows.
        if sf.get("filename", "").lower().startswith("fbi photo"):
            logger.info("skipping %s: photo-only source, no narrative text", sf["filename"])
            continue

        # skip if we've already extracted from this one
        existing = sb.table("incidents").select("id", count="exact").eq("source_file_id", sf["id"]).execute()
        if existing.count and existing.count > 0:
            logger.info("skip %s: already has %d incidents", sf["filename"], existing.count)
            continue

        incidents = extract_from_source_file(sf, client)

        if incidents:
            if not skip_embed:
                # batch embed all incidents in 1 API call (much fewer rate-limit hits)
                embed_texts = [f"{inc['title']}\n{inc['summary']}\n{inc['raw_excerpt']}" for inc in incidents]
                embeddings = embed_batch(embed_texts)
                for inc, emb in zip(incidents, embeddings):
                    inc["embedding"] = emb

            for inc in incidents:
                # propagate media URLs from source file
                if sf["file_type"] in ("mp4", "mov"):
                    inc["video_url"] = sf.get("url")
                elif sf["file_type"] in ("jpg", "png", "jpeg"):
                    inc["image_url"] = sf.get("url")

                upsert_incident(sb, inc)

        logger.info("extracted %d incidents from %s", len(incidents), sf["filename"])
        total_incidents += len(incidents)

    logger.info("extraction complete // total new incidents=%d", total_incidents)


def _tokenize(text: str, min_len: int = 2) -> set[str]:
    """Extract alphanumeric tokens from text for matching.

    Uses min_len=2 by default so short but discriminating tokens like
    '12', '17', 'a1', 'vm1' are preserved.  Common stop-words that
    appear in nearly every filename are excluded.
    """
    stop = {
        "the", "and", "for", "from", "pdf", "jpg", "png", "mp4", "mov", "release",
        # URL infrastructure tokens (present in all war.gov URLs, not discriminating)
        "https", "http", "www", "gov", "war", "com", "medialink", "ufo", "release_1",
    }
    tokens = set(re.findall(r"[A-Za-z0-9]+", text.lower()))
    return {t for t in tokens if len(t) >= min_len and t not in stop}


def link_media(dry_run: bool = False) -> None:
    """
    Post-processing step: scan source_files for images and videos that
    aren't yet linked to incidents. Match by shared case tokens in filenames
    and URLs. Uses both filename and URL tokens for better discrimination
    (e.g. 'apollo-12' vs 'apollo-11').
    """
    sb = get_supabase()

    # all image/video source files
    media_files = (
        sb.table("source_files")
        .select("id, filename, url, file_type")
        .in_("file_type", ["jpg", "png", "jpeg", "mp4", "mov"])
        .execute()
        .data
    )
    logger.info("found %d media source files", len(media_files))

    # all incidents missing media
    incidents_no_img = (
        sb.table("incidents")
        .select("id, case_id, source_file_id, image_url, video_url")
        .is_("image_url", "null")
        .execute()
        .data
    )
    # get their source filenames AND urls for token matching
    sf_lookup: dict[str, dict] = {}
    if incidents_no_img:
        sf_ids = list({i["source_file_id"] for i in incidents_no_img})
        for batch_start in range(0, len(sf_ids), 50):
            batch = sf_ids[batch_start:batch_start + 50]
            rows = sb.table("source_files").select("id, filename, url").in_("id", batch).execute().data
            for r in rows:
                sf_lookup[r["id"]] = {"filename": r["filename"], "url": r.get("url", "")}

    linked = 0
    for mf in media_files:
        # tokenize both filename and URL for richer matching
        mf_tokens = _tokenize(mf["filename"]) | _tokenize(mf.get("url", ""))
        if len(mf_tokens) < 2:
            logger.debug("skipping %s: too few tokens", mf["filename"])
            continue

        best_match = None
        best_overlap = 0

        for inc in incidents_no_img:
            sf_info = sf_lookup.get(inc["source_file_id"], {"filename": "", "url": ""})
            inc_tokens = _tokenize(sf_info["filename"]) | _tokenize(sf_info["url"])
            overlap = len(mf_tokens & inc_tokens)
            if overlap > best_overlap and overlap >= 3:
                best_overlap = overlap
                best_match = inc

        if best_match:
            col = "video_url" if mf["file_type"] in ("mp4", "mov") else "image_url"
            if not dry_run:
                sb.table("incidents").update({col: mf["url"]}).eq("id", best_match["id"]).execute()
            logger.info("linked %s -> incident %s (%s, overlap=%d tokens)",
                        mf["filename"], best_match["case_id"], col, best_overlap)
            linked += 1
        else:
            logger.info("no match for %s (tokens=%s)", mf["filename"], sorted(mf_tokens)[:10])

    logger.info("link_media complete // linked=%d", linked)


def backfill_embeddings() -> None:
    """Embed all incidents that don't have embeddings yet. Run this after
    extract --no-embed to fill in embeddings at whatever pace the API allows."""
    sb = get_supabase()

    # fetch incidents missing embeddings
    rows = sb.table("incidents").select("id, title, summary, raw_excerpt").is_("embedding", "null").execute().data
    logger.info("found %d incidents without embeddings", len(rows))
    if not rows:
        return

    # process in batches of 20 (Voyage handles up to 128 but smaller batches
    # give us more frequent progress logging and reduce token-per-request pressure)
    batch_size = 20
    embedded = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        texts = [f"{r['title']}\n{r['summary']}\n{r['raw_excerpt']}" for r in batch]
        vecs = embed_batch(texts)
        for r, vec in zip(batch, vecs):
            vec_str = "[" + ",".join(str(x) for x in vec) + "]"
            sb.table("incidents").update({"embedding": vec_str}).eq("id", r["id"]).execute()
        embedded += len(batch)
        logger.info("embedded %d/%d incidents", embedded, len(rows))

    logger.info("backfill complete // embedded=%d", embedded)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int)
    parser.add_argument("--source-file-id")
    parser.add_argument("--no-embed", action="store_true",
                        help="skip embedding (extract only, embed later with --backfill-embed)")
    parser.add_argument("--backfill-embed", action="store_true",
                        help="embed all incidents missing embeddings (run after --no-embed)")
    parser.add_argument("--link-media", action="store_true",
                        help="link image/video source files to incidents by filename")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.link_media:
        link_media(dry_run=args.dry_run)
    elif args.backfill_embed:
        backfill_embeddings()
    else:
        run(limit=args.limit, source_file_id=args.source_file_id, skip_embed=args.no_embed)
