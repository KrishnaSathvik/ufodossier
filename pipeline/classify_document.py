"""
Document classifier for UFO Dossier v2.

Separates incident-bearing sources from program/admin/research documents
BEFORE Haiku extraction runs.

Default mode is local/report-only. Production DB writes require --apply
AND an explicit confirmation that this is intentional.

Usage:
  # Local smoke (no DB writes):
  python -m pipeline.classify_document --local-cache .cache/files/pursue/r2 --dry-run

  # Persist classifications to source_records (PRODUCTION WRITE — do not use yet):
  python -m pipeline.classify_document --release 2 --limit 5 --apply
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

DocumentClass = Literal[
    "incident_report",
    "historical_case_file",
    "correspondence",
    "transcript",
    "analysis",
    "research_paper",
    "personnel_record",
    "program_document",
    "contract",
    "administrative",
    "media_metadata",
    "other",
]

Confidence = Literal["high", "medium", "low"]

DOCUMENT_CLASSES: tuple[str, ...] = (
    "incident_report",
    "historical_case_file",
    "correspondence",
    "transcript",
    "analysis",
    "research_paper",
    "personnel_record",
    "program_document",
    "contract",
    "administrative",
    "media_metadata",
    "other",
)

# Classes that normally contain extractable UAP encounter narratives
INCIDENT_BEARING_CLASSES = frozenset(
    {
        "incident_report",
        "historical_case_file",
        "transcript",
    }
)

# Defaults: correspondence/analysis may mention incidents but are inspected case-by-case
MAYBE_INCIDENT_CLASSES = frozenset({"correspondence", "analysis"})


@dataclass
class Classification:
    document_class: DocumentClass
    contains_incidents: bool
    confidence: Confidence
    reason: str
    method: str = "rules"  # rules | haiku | hybrid

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Deterministic rules (unit-testable, no API)
# ---------------------------------------------------------------------------

_CONTRACT_RE = re.compile(
    r"\b(contract|solicitation|statement of objectives|modification p00|"
    r"aawsap|bigelow aerospace|hhm402)\b",
    re.I,
)
# Whitespace-flexible: OCR often splits the DIRD banner across lines.
_DIRD_RE = re.compile(
    r"\b(?:dird|defense\s+intelligence\s+reference\s+document)\b",
    re.I,
)
_RESEARCH_RE = re.compile(
    r"\b("
    r"metamaterial|warp drive|wormhole|antigravity|spintronic|"
    r"negative.?mass|quantum.?vacuum|research paper|technical paper|"
    r"technical report|peer.?reviewed|"
    r"state of the art|survey of (?:the |current )?"
    r"|applications of (?:metamaterial|advanced|novel)|"
    r"gravitational waves?|high-?energy lasers?|"
    r"nuclear propulsion|drake equation|"
    r"technical literature|acquisition threat support"
    r")\b",
    re.I,
)
_PERSONNEL_RE = re.compile(
    r"\b("
    r"personnel record|service (?:record|history)|"
    r"fitness report|performance (?:report|evaluation)|"
    r"enlisted|officer(?:'s)? record|bupers|bureau of naval personnel|"
    r"promotion|assignment|duty station|orders to|"
    r"administrative history|discharge"
    r")\b",
    re.I,
)
_PERSONNEL_DENSE_RE = re.compile(
    r"\b(personnel|duty|naval|orders|rank|enlisted|bupers|assignment|"
    r"promotion|performance|service|officer)\b",
    re.I,
)
_PROGRAM_RE = re.compile(
    r"\b(program overview|program document|organizational chart|"
    r"budget justification|staffing plan)\b",
    re.I,
)
# "invitation" alone is too broad: CIA information reports say
# "at the invitation of" a host. Require an actual invite.
_ADMIN_RE = re.compile(
    r"\b(you are invited|agenda|minutes of|routing slip|transmittal|"
    r"dear members|membership|newsletter)\b",
    re.I,
)
_CORRESPONDENCE_RE = re.compile(
    r"\b(dear\s|correspondence|letter to|letter from|sincerely|"
    r"attention:|respectfully)\b",
    re.I,
)
_TRANSCRIPT_RE = re.compile(
    r"\b(transcript|debrief|interview of|oral history|q\s*&\s*a)\b",
    re.I,
)
_HISTORICAL_STRONG_RE = re.compile(
    r"\b(case file|project blue book|special reporting group|"
    r"security inspection|fbi file|hq-\d+|green fireball)\b",
    re.I,
)
_HISTORICAL_RE = re.compile(
    r"\b(case file|project blue book|special reporting group|"
    r"security inspection|194[0-9]|195[0-9]|196[0-9]|197[0-9]|"
    r"fbi file|hq-\d+|green fireball)\b",
    re.I,
)
# Strong encounter cues (used for contains_incidents decisions).
_ENCOUNTER_RE = re.compile(
    r"\b(mission report|incident report|unidentified (object|aerial|anomalous)|"
    r"sighting|observed (an? )?(object|craft|phenomenon)|"
    r"radar (return|contact)|visual contact|"
    r"aircraft observed|reported seeing|witness(es)? reported)\b",
    re.I,
)
# Broader topic mention kept for future hybrid prompts; encounter gate uses _ENCOUNTER_RE.
_INCIDENT_RE = re.compile(
    r"\b(mission report|incident report|unidentified (object|aerial|anomalous)|"
    r"(?<![A-Za-z0-9-])uap(?![A-Za-z0-9-])|(?<![A-Za-z0-9-])ufo'?s?(?![A-Za-z0-9-])|"
    r"sighting|observed (an? )?(object|craft|phenomenon)|"
    r"radar (return|contact)|visual contact)\b",
    re.I,
)
_ANALYSIS_RE = re.compile(
    r"\b(analysis of|assessment of|intelligence analysis|"
    r"pattern analysis|after.?action review|"
    r"analyst note|low confidence in this|backscattering)\b",
    re.I,
)
# Referral / catalog letters discuss UFO material without narrating an event.
_CATALOG_REFERRAL_RE = re.compile(
    r"\b("
    r"incoming correspondence action|"
    r"action tracking system|"
    r"forwards? (?:a |the )?letter|"
    r"fwds ltr|"
    r"requesting information|"
    r"thank you for your letter|"
    r"on behalf of|"
    r"constituent correspondence"
    r")\b",
    re.I,
)
# First-hand observation inside a letter. Excludes "I saw your letter".
_FIRSTHAND_NARRATIVE_RE = re.compile(
    r"\b("
    r"i (?:just )?(?:saw|observed|watched|witnessed)(?!\s+(?:your|the)\s+(?:letter|correspondence|memo))|"
    r"we (?:all )?(?:saw|observed|watched)"
    r")\b",
    re.I,
)
_MEDIA_RE = re.compile(
    r"\b(image caption|photograph of|still frame|imagery product|"
    r"ground surveillance radar image)\b",
    re.I,
)


def _primary_encounter(content: str) -> bool:
    """Strong primary encounter narrative — can override research/personnel."""
    return bool(_ENCOUNTER_RE.search(content) or _FIRSTHAND_NARRATIVE_RE.search(content))


def _personnel_score(text: str) -> int:
    return len(_PERSONNEL_DENSE_RE.findall(text[:20000]))


def classify_text(
    *,
    title: str = "",
    filename: str = "",
    text: str = "",
    agency: str = "",
    page_count: int | None = None,
    byte_size: int | None = None,
) -> Classification:
    """
    Deterministic classifier. Prefer false-negatives on contains_incidents
    for research/contract/admin so extraction does not invent incidents.

    Precedence:
      strong primary encounter narrative → incident-bearing classes
      otherwise research / personnel / program / admin → source_only
    """
    # Content blob excludes filename so DOE-UAP-D00N IDs don't fake "UAP" hits.
    content = f"{title}\n{text[:8000]}"
    blob = f"{title}\n{filename}\n{text[:8000]}"
    title_l = f"{title} {filename}".lower()
    primary = _primary_encounter(content)

    # --- Research / DIRD (content signals; OCR-tolerant whitespace) ----------
    # Do not use filename-only shortcuts. Encounter narrative still wins.
    dird_hit = bool(_DIRD_RE.search(content) or _DIRD_RE.search(blob))
    research_hit = bool(_RESEARCH_RE.search(content) or _RESEARCH_RE.search(blob))
    if (dird_hit or research_hit) and not primary:
        return Classification(
            "research_paper",
            False,
            "high",
            "Technical/research or DIRD vocabulary without an encounter framing",
        )

    # --- Personnel records (beats generic year → historical) ----------------
    if not primary and (
        bool(re.search(r"\bpersonnel record\b|\bservice (?:record|history)\b|\bbupers\b", content, re.I))
        or (_PERSONNEL_RE.search(content) and _personnel_score(text) >= 8)
    ):
        return Classification(
            "personnel_record",
            False,
            "high",
            "Personnel/service-history administrative record without encounter narrative",
        )

    # Order matters: most restrictive non-incident classes first
    if _CONTRACT_RE.search(blob):
        # AAWSAP contracts/solicitations — but a DIRD already returned above.
        # If primary encounter somehow sits inside a contract packet, extract.
        if primary:
            return Classification(
                "incident_report",
                True,
                "medium",
                "Encounter narrative inside otherwise contractual packet",
            )
        return Classification(
            "contract",
            False,
            "high",
            "Contract/solicitation language; not an encounter narrative",
        )
    if _PROGRAM_RE.search(blob):
        return Classification(
            "program_document",
            False,
            "high",
            "Program/administrative planning language",
        )
    if _ADMIN_RE.search(content):
        # Astronomy-club invitations etc. may mention UFOs as a talk topic.
        return Classification(
            "administrative",
            False,
            "high",
            "Invitation/agenda/membership/admin content",
        )
    if _MEDIA_RE.search(content) and len(text.strip()) < 800:
        # Short image-report packets can still be incident-bearing (e.g. PANTEX)
        if _ENCOUNTER_RE.search(content) or _INCIDENT_RE.search(content):
            return Classification(
                "incident_report",
                True,
                "medium",
                "Short imagery packet that names an unidentified-object incident",
            )
        return Classification(
            "media_metadata",
            False,
            "medium",
            "Short imagery/caption packet without clear encounter narrative",
        )
    if _TRANSCRIPT_RE.search(content):
        return Classification(
            "transcript",
            True,
            "high",
            "Transcript/debrief of an observed event",
        )
    # Historical case files often include internal letters — prefer historical
    # over bare correspondence when strong investigative cues are present.
    # A lone year (e.g. 1976 in a letter) is NOT enough to override correspondence.
    if _HISTORICAL_STRONG_RE.search(content) or _HISTORICAL_STRONG_RE.search(title_l):
        return Classification(
            "historical_case_file",
            True,
            "high",
            "Historical case file / mid-century investigative record",
        )
    if _CORRESPONDENCE_RE.search(content):
        # Catalog/referral letters mention sightings while forwarding, acknowledging,
        # or requesting information. That is not a primary encounter narrative.
        # A first-hand account ("I saw", "we all saw") still counts.
        catalog = bool(_CATALOG_REFERRAL_RE.search(content))
        firsthand = bool(_FIRSTHAND_NARRATIVE_RE.search(content))
        encounter = bool(_ENCOUNTER_RE.search(content))
        if catalog and not firsthand:
            incidentish = False
            reason = (
                "Catalog/referral correspondence; summarizes, forwards, or "
                "acknowledges UFO material without a first-hand encounter narrative"
            )
        elif firsthand or encounter:
            incidentish = True
            reason = "Letter/correspondence that narrates a first-hand encounter"
        else:
            incidentish = False
            reason = "Letter/correspondence form; no encounter narrative"
        return Classification(
            "correspondence",
            incidentish,
            "medium" if incidentish else "high",
            reason,
        )
    # Document ids such as "ICA-UAP-D001" / "ICA UAP D001" are not incident framing.
    title_without_id = re.sub(
        r"\b[a-z0-9]+-uap(?:-d\d+)?\b|\b[a-z]{2,6}\s+uap\s+d-?\d+\b",
        " ",
        title_l,
    )
    if _ANALYSIS_RE.search(content) and not _INCIDENT_RE.search(title_without_id):
        return Classification(
            "analysis",
            False,
            "medium",
            "Analytical assessment rather than a primary encounter report",
        )
    # Year-based historical is weaker — do not let bibliography years promote
    # research/personnel leftovers (those already returned above).
    if _HISTORICAL_RE.search(content) or _HISTORICAL_RE.search(title_l):
        return Classification(
            "historical_case_file",
            True,
            "high",
            "Historical case file / mid-century investigative record",
        )
    if _INCIDENT_RE.search(content) or _INCIDENT_RE.search(title):
        return Classification(
            "incident_report",
            True,
            "high",
            "Mission/incident report language describing an observation",
        )

    # Research/DIRD with primary encounter override lands here if earlier
    # research branch was skipped — prefer incident report.
    if (dird_hit or research_hit) and primary:
        return Classification(
            "incident_report",
            True,
            "medium",
            "Primary encounter narrative overrides research/DIRD framing",
        )

    # Large single-page image packets (digital renderings) have almost no text.
    word_count = len(re.findall(r"[A-Za-z]{2,}", text))
    if (
        page_count == 1
        and byte_size is not None
        and byte_size >= 1_000_000
        and word_count < 40
        and not _ENCOUNTER_RE.search(content)
    ):
        return Classification(
            "media_metadata",
            False,
            "medium",
            "Large single-page image packet with no usable encounter narrative",
        )

    # Agency defaults when text is thin
    if agency.upper() in ("CIA", "FBI", "DOE", "DOW", "DOD") and len(text.strip()) > 200:
        return Classification(
            "other",
            False,
            "low",
            "Insufficient cues; defaulting to non-incident until reviewed",
        )

    return Classification(
        "other",
        False,
        "low",
        "No strong classification cues",
    )


def classify_with_optional_haiku(
    *,
    title: str,
    filename: str,
    text: str,
    agency: str = "",
    use_haiku: bool = False,
) -> Classification:
    rules = classify_text(title=title, filename=filename, text=text, agency=agency)
    if not use_haiku or rules.confidence == "high":
        return rules

    # Low/medium confidence: optional Haiku second opinion (still local decision)
    try:
        import anthropic
    except ImportError:
        return rules

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return rules

    client = anthropic.Anthropic(api_key=api_key)
    prompt = f"""Classify this U.S. government UAP-related document.

Return ONLY JSON:
{{
  "document_class": one of {list(DOCUMENT_CLASSES)},
  "contains_incidents": true/false,
  "confidence": "high"|"medium"|"low",
  "reason": "one sentence"
}}

contains_incidents=true ONLY if the document narrates one or more specific UAP/UFO encounters
(observations with time/place/sensors). Contracts, research papers, invitations, and
program admin docs are false even if they mention UAP as a topic.

TITLE: {title}
FILENAME: {filename}
AGENCY: {agency}
TEXT (truncated):
{text[:6000]}
"""
    try:
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        data = json.loads(raw)
        dclass = data.get("document_class", rules.document_class)
        if dclass not in DOCUMENT_CLASSES:
            dclass = rules.document_class
        return Classification(
            document_class=dclass,  # type: ignore[arg-type]
            contains_incidents=bool(data.get("contains_incidents", rules.contains_incidents)),
            confidence=data.get("confidence", rules.confidence),  # type: ignore[arg-type]
            reason=str(data.get("reason") or rules.reason)[:300],
            method="hybrid",
        )
    except Exception as e:
        logger.warning("haiku classify failed, keeping rules result: %s", e)
        return rules


# ---------------------------------------------------------------------------
# Local PDF text
# ---------------------------------------------------------------------------

def extract_local_pdf_text(pdf_path: Path) -> tuple[str, str, int]:
    """Prefer OCR-hardened combined.txt when available; else pypdf via pipeline.ocr."""
    ocr_combined = Path("pipeline/reports/r2_ocr") / pdf_path.stem / "combined.txt"
    if ocr_combined.exists():
        text = ocr_combined.read_text()
        # page count from markers
        pages = text.count("--- PAGE ")
        return text, "selective_ocr", pages or 1
    from pipeline.ocr import extract_pdf_text

    return extract_pdf_text(pdf_path.read_bytes())


def _load_env() -> None:
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _meta_from_filename(name: str) -> dict[str, str]:
    stem = Path(name).stem
    # e.g. CIA-UAP-D001
    m = re.match(r"^([A-Z]+)-UAP-", stem, re.I)
    agency = m.group(1).upper() if m else ""
    return {"external_id": stem, "title": stem.replace("_", " "), "agency": agency}


def run_local_cache(
    cache_dir: Path,
    *,
    limit: int | None,
    dry_run: bool,
    use_haiku: bool,
    out_dir: Path,
) -> list[dict[str, Any]]:
    pdfs = sorted(cache_dir.glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]
    out_dir.mkdir(parents=True, exist_ok=True)
    texts_dir = out_dir / "texts"
    texts_dir.mkdir(exist_ok=True)

    results: list[dict[str, Any]] = []
    for pdf in pdfs:
        meta = _meta_from_filename(pdf.name)
        text, method, pages = extract_local_pdf_text(pdf)
        (texts_dir / f"{pdf.stem}.txt").write_text(text)
        clf = classify_with_optional_haiku(
            title=meta["title"],
            filename=pdf.name,
            text=text,
            agency=meta["agency"],
            use_haiku=use_haiku,
        )
        action = "extract" if clf.contains_incidents else "source_only"
        row = {
            "filename": pdf.name,
            "external_id": meta["external_id"],
            "agency": meta["agency"],
            "byte_size": pdf.stat().st_size,
            "page_count": pages,
            "text_chars": len(text),
            "text_method": method,
            "text_path": str(texts_dir / f"{pdf.stem}.txt"),
            "classification": clf.to_dict(),
            "extraction_action": action,
        }
        results.append(row)
        logger.info(
            "%s -> %s contains_incidents=%s action=%s",
            pdf.name,
            clf.document_class,
            clf.contains_incidents,
            action,
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "local_cache",
        "dry_run": dry_run,
        "production_writes": False,
        "cache_dir": str(cache_dir),
        "count": len(results),
        "results": results,
    }
    out_path = out_dir / "classifications.json"
    if not dry_run:
        out_path.write_text(json.dumps(report, indent=2) + "\n")
        logger.info("wrote %s", out_path)
    else:
        print(json.dumps(report, indent=2))
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify source documents")
    parser.add_argument(
        "--local-cache",
        type=Path,
        default=Path(".cache/files/pursue/r2"),
        help="Directory of local PDFs (default: R2 smoke cache)",
    )
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--use-haiku", action="store_true", help="Hybrid classify low-confidence cases")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("pipeline/reports/r2_smoke"),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="FORBIDDEN for current milestone: would write classifications to production",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )
    _load_env()

    if args.apply:
        logger.error(
            "--apply would write to production source_records. "
            "Current milestone is local-only. Refusing."
        )
        return 2

    if not args.local_cache.exists():
        logger.error("local cache not found: %s", args.local_cache)
        return 1

    run_local_cache(
        args.local_cache,
        limit=args.limit,
        dry_run=args.dry_run,
        use_haiku=args.use_haiku,
        out_dir=args.out_dir,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
