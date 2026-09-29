"""
Page and section router for large historical files.

Scores each page, skips index/routing slips and press clippings, and groups
remaining narrative pages into sections. Fixed-size chunks stay the default
for ordinary documents.

LOCAL ONLY. Does not call a model and does not write to Supabase.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from pipeline.extract import MAX_INPUT_CHARS, _chunk
from pipeline.text_quality import score_page_text

_PAGE_RE = re.compile(r"^--- PAGE (\d+) ---\s*", re.M)

_ROUTING_RE = re.compile(
    r"\b(search slip|indices search|indice[s]? search|chief clerk|"
    r"fd-?\s*160|fd-?\s*110|exact spelling|subversive references|"
    r"declassification authority)\b",
    re.I,
)
_MEMO_RE = re.compile(
    r"\b(office memorandum|memorandum|united states government|"
    r"telephonically|advised this office|advised on the above|"
    r"to\s*:?\s*sac)\b",
    re.I,
)
_OBSERVATION_RE = re.compile(
    r"\b(unidentified(?:\s+(?:flying|aerial))?|sighted|sighting|flying object|"
    r"observed|saw (?:an? |the )?(?:object|ufo|lights?)|flying saucer|"
    r"objects in the sky)\b",
    re.I,
)
_PRESS_RE = re.compile(
    r"\b(flying saucer clubs|official journal|new york times|"
    r"national convention|afsca|amalgamated flying|"
    r"newspaper|magazine|martian|spacemen|telepathy|staff writer|"
    r"serialized|columbia basin|herald|tribune|gazette|"
    r"docid:\s*\d+)\b|"
    r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday),"
    r"\s+[a-z]+\s+\d{1,2},\s+19\d{2}\b",
    re.I,
)
_DATE_RE = re.compile(
    r"\b(\d{1,2}/\d{1,2}/\d{2,4}|19[4-6]\d|"
    r"january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\b",
    re.I,
)
_LOCATION_RE = re.compile(
    r"\b(newark|new jersey|n\.\s?j\.|glen ridge|nutley|union)\b",
    re.I,
)

# Pack narrative pages into sections of about this size.
SECTION_MAX_CHARS = 15_000


@dataclass
class PageSignal:
    page: int
    text_chars: int
    ocr_quality: str
    incident_cue_score: float
    date_location_cues: int
    routing_index_likelihood: float
    narrative_likelihood: float
    route: str  # narrative | skip_routing | skip_press | skip_empty | uncertain


def split_pages(text: str) -> list[tuple[int, str]]:
    matches = list(_PAGE_RE.finditer(text))
    if not matches:
        body = text.strip()
        return [(1, body)] if body else []
    pages: list[tuple[int, str]] = []
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        pages.append((int(match.group(1)), text[start:end].strip()))
    return pages


def score_page(page: int, body: str) -> PageSignal:
    quality = score_page_text(page, body)
    chars = len(body.strip())
    routing_hits = len(_ROUTING_RE.findall(body))
    memo_hits = len(_MEMO_RE.findall(body))
    observation_hits = len(_OBSERVATION_RE.findall(body))
    press_hits = len(_PRESS_RE.findall(body))
    date_hits = len(_DATE_RE.findall(body))
    location_hits = len(_LOCATION_RE.findall(body))
    date_location = date_hits + location_hits

    incident_cue_score = round(min(1.0, (observation_hits + memo_hits) / 3), 3)
    if routing_hits and observation_hits == 0 and memo_hits == 0:
        routing_likelihood = 0.9
    elif routing_hits:
        routing_likelihood = 0.55
    else:
        routing_likelihood = 0.0

    narrative_raw = 0.0
    if routing_hits == 0 and press_hits == 0 and chars >= 200:
        if memo_hits >= 1 or (observation_hits >= 1 and date_hits >= 1):
            narrative_raw = 0.85 if (memo_hits + observation_hits) >= 2 else 0.7
    narrative_likelihood = round(narrative_raw, 3)

    if chars < 80:
        route = "skip_empty"
    elif routing_hits >= 1 and observation_hits == 0 and memo_hits == 0:
        route = "skip_routing"
    elif press_hits >= 1 and memo_hits == 0:
        route = "skip_press"
    elif narrative_raw >= 0.7:
        route = "narrative"
    else:
        route = "uncertain"

    return PageSignal(
        page=page,
        text_chars=chars,
        ocr_quality=quality.category,
        incident_cue_score=incident_cue_score,
        date_location_cues=date_location,
        routing_index_likelihood=routing_likelihood,
        narrative_likelihood=narrative_likelihood,
        route=route,
    )


def diagnose_text(text: str) -> list[PageSignal]:
    return [score_page(num, body) for num, body in split_pages(text)]


def _group(
    pages: list[tuple[int, str]],
    signals: dict[int, PageSignal],
    keep: Callable[[PageSignal], bool],
    max_chars: int,
) -> list[str]:
    sections: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if current:
            sections.append("\n\n".join(current))
            current = []
            current_len = 0

    for num, body in pages:
        signal = signals[num]
        if not keep(signal):
            flush()
            continue
        block = f"--- PAGE {num} ---\n{body}"
        if current and current_len + len(block) > max_chars:
            flush()
        current.append(block)
        current_len += len(block)
    flush()
    return sections


def select_chunks(
    text: str,
    *,
    strategy: str = "auto",
    max_chars: int = MAX_INPUT_CHARS,
) -> tuple[str, list[str]]:
    """
    Return (strategy_used, chunks).

    auto: cue-route only when the file is large AND mixes routing slips
    with narrative pages. Transcripts and ordinary reports stay on fixed chunks.
    """
    if strategy not in {"auto", "fixed", "page_grouped", "cue_routed"}:
        raise ValueError(f"unknown chunk strategy: {strategy}")

    if strategy == "fixed":
        return "fixed", _chunk(text, max_chars)

    pages = split_pages(text)
    signals_list = [score_page(num, body) for num, body in pages]
    signals = {s.page: s for s in signals_list}
    routing_pages = sum(1 for s in signals_list if s.route == "skip_routing")
    narrative_pages = sum(1 for s in signals_list if s.route == "narrative")

    if strategy == "auto":
        mixed_historical = (
            len(pages) >= 15
            and len(text) > max_chars
            and routing_pages >= 3
            and narrative_pages >= 1
        )
        strategy = "cue_routed" if mixed_historical else "fixed"
        if strategy == "fixed":
            return "fixed", _chunk(text, max_chars)

    if strategy == "page_grouped":
        chunks = _group(
            pages,
            signals,
            lambda s: s.route != "skip_empty",
            min(max_chars, SECTION_MAX_CHARS),
        )
        return "page_grouped", chunks or _chunk(text, max_chars)

    chunks = _group(
        pages,
        signals,
        lambda s: s.route == "narrative",
        min(max_chars, SECTION_MAX_CHARS),
    )
    return "cue_routed", chunks


def write_diagnostic(text: str, out_path: Path) -> list[dict]:
    rows = [asdict(s) for s in diagnose_text(text)]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"pages": rows, "count": len(rows)}, indent=2) + "\n")
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score pages and write a routing diagnostic")
    parser.add_argument("--text", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = write_diagnostic(args.text.read_text(), args.out)
    narrative = sum(1 for r in rows if r["route"] == "narrative")
    routing = sum(1 for r in rows if r["route"] == "skip_routing")
    press = sum(1 for r in rows if r["route"] == "skip_press")
    print(
        f"pages={len(rows)} narrative={narrative} routing={routing} press={press} wrote {args.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
