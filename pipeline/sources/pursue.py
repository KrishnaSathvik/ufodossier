"""
PURSUE (war.gov/UFO) official source provider.

Canonical manifest (R02+):
  https://www.war.gov/Portals/1/Interactive/2026/UFO/uap-data.csv

R01 used uap-csv.csv (now 404). Community mirrors are validation-only.
war.gov is behind Akamai bot management — prefer curl_cffi when available.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

from .base import (
    RELEASE_NUMBER_TO_LABEL,
    SourceRecord,
    identity_key,
    normalize_ws,
    parse_us_short_date,
    release_number_for_date,
)

logger = logging.getLogger(__name__)

OFFICIAL_MANIFEST_URL = (
    "https://www.war.gov/Portals/1/Interactive/2026/UFO/uap-data.csv"
)

# Fallback for local / CI when war.gov is unreachable (NOT source of truth)
COMMUNITY_R06_SNAPSHOT = (
    "https://raw.githubusercontent.com/SeeingBlue/uap-corpus-viewer/"
    "main/snapshots/2026-09-18/uap-data.csv"
)

USER_AGENT = "ufodossier-bot/2.0 (+https://ufodossier.com/about)"

AGENCY_MAP = {
    "department of war": "DoW",
    "dow": "DoW",
    "dod": "DoW",
    "department of defense": "DoW",
    "fbi": "FBI",
    "nasa": "NASA",
    "cia": "CIA",
    "central intelligence agency": "CIA",
    "state": "State",
    "department of state": "State",
    "doe": "DoE",
    "department of energy": "DoE",
    "odni": "ODNI",
    "lle": "LLE",
    "local law enforcement": "LLE",
    "ica": "ICA",
    "intelligence community agency": "ICA",
    "usg": "USG",
    "u.s. government": "USG",
    "eop": "EOP",
    "executive office of the president": "EOP",
}


def normalize_agency(raw: str | None) -> tuple[str | None, str | None]:
    if not raw:
        return None, None
    agency_raw = normalize_ws(raw)
    key = agency_raw.lower()
    return AGENCY_MAP.get(key, agency_raw), agency_raw


def map_type(raw: str | None) -> str:
    t = normalize_ws(raw).upper().rstrip()
    return {
        "PDF": "pdf",
        "VID": "video",
        "IMG": "image",
        "AUD": "audio",
    }.get(t, "other")


def extract_external_id(title: str | None, url: str | None) -> str | None:
    """
    Prefer IDs embedded in titles / filenames:
      DOW-UAP-D114, FBI-UAP-..., LLE-UAP-PR001, etc.
    """
    for candidate in (title or "", unquote(url or "")):
        m = re.search(
            r"\b([A-Z]{2,6}-UAP-(?:D|PR)\d+[a-z]?)\b",
            candidate,
            flags=re.IGNORECASE,
        )
        if m:
            return m.group(1).upper()
        # filename stem sometimes is the id
        stem = Path(urlparse(candidate).path).stem
        m2 = re.match(r"^([A-Za-z]{2,6}-UAP-(?:D|PR)\d+[a-z]?)", stem, re.I)
        if m2:
            return m2.group(1).upper()
    return None


def _get_field(row: dict, *names: str) -> str:
    # handle BOM on first header
    normalized = {normalize_ws(k).lstrip("\ufeff"): v for k, v in row.items()}
    for name in names:
        if name in normalized and normalized[name] is not None:
            return normalize_ws(str(normalized[name]))
    return ""


def parse_manifest_csv(text: str) -> list[SourceRecord]:
    reader = csv.DictReader(io.StringIO(text))
    records: list[SourceRecord] = []
    for row in reader:
        title = _get_field(row, "Title")
        typ = map_type(_get_field(row, "Type"))
        release_raw = _get_field(row, "Release Date")
        url = _get_field(row, "PDF | Image Link", "source_url", "URL")
        thumb = _get_field(row, "Modal Image")
        agency_norm, agency_raw = normalize_agency(_get_field(row, "Agency"))
        desc = _get_field(row, "Description Blurb")
        incident_date = _get_field(row, "Incident Date")
        incident_loc = _get_field(row, "Incident Location")
        dvids = _get_field(row, "DVIDS Video ID")
        video_title = _get_field(row, "Video Title")
        featured = _get_field(row, "Featured")
        redaction = _get_field(row, "Redaction")

        external_id = extract_external_id(title, url)
        rel_num = release_number_for_date(release_raw)
        rel_date = parse_us_short_date(release_raw)

        # Videos/audio may lack a direct PDF URL; keep DVIDS id in metadata
        download_url = url if url.startswith("http") else None
        original_url = download_url

        ik = identity_key(
            "pursue",
            external_id=external_id,
            title=title,
            url=original_url or dvids or title,
        )

        meta = {
            "featured": featured.upper() in ("YES", "Y", "TRUE", "1") if featured else False,
            "redaction": redaction,
            "dvids_video_id": dvids or None,
            "video_title": video_title or None,
            "video_pairing": _get_field(row, "Video Pairing") or None,
            "pdf_pairing": _get_field(row, "PDF Pairing") or None,
            "image_alt_text": _get_field(row, "Image Alt Text") or None,
            "image_virin": _get_field(row, "Image VIRIN") or None,
            "release_date_raw": release_raw or None,
        }

        records.append(
            SourceRecord(
                provider="pursue",
                identity_key=ik,
                source_type=typ,  # type: ignore[arg-type]
                external_id=external_id,
                release_number=rel_num,
                release_date=rel_date,
                release_label=RELEASE_NUMBER_TO_LABEL.get(rel_num) if rel_num else None,
                title=title or None,
                description=desc or None,
                agency=agency_norm,
                agency_raw=agency_raw,
                incident_date_hint=incident_date or None,
                incident_location_hint=incident_loc or None,
                original_url=original_url,
                download_url=download_url,
                thumbnail_url=thumb if thumb.startswith("http") else None,
                status="active",
                metadata={k: v for k, v in meta.items() if v not in (None, "", False)},
            )
        )
    _disambiguate_identity_keys(records)
    return records


def _disambiguate_identity_keys(records: list[SourceRecord]) -> None:
    """
    Official CSV can reuse an external_id across asset types/releases
    (e.g. FBI-UAP-D014 as both a PDF and an image). Keep the first key;
    append :{source_type} (and url hash if needed) for collisions.
    """
    from collections import defaultdict

    by_key: dict[str, list[SourceRecord]] = defaultdict(list)
    for r in records:
        by_key[r.identity_key].append(r)
    for key, group in by_key.items():
        if len(group) < 2:
            continue
        # keep first; rewrite rest
        for r in group[1:]:
            candidate = f"{key}:{r.source_type}"
            if any(x.identity_key == candidate for x in records):
                digest = identity_key(
                    "pursue",
                    title=r.title,
                    url=r.original_url or r.download_url,
                ).split(":")[-1]
                candidate = f"{key}:{r.source_type}:{digest}"
            r.identity_key = candidate


def fetch_bytes(url: str, *, timeout: float = 120.0) -> bytes:
    """Fetch via OfficialSourceClient (httpx → curl_cffi on Akamai 403)."""
    from .http import OfficialSourceClient

    client = OfficialSourceClient(timeout=timeout)
    body, meta = client.get_bytes(url)
    logger.debug(
        "fetched %s status=%s impersonation=%s bytes=%d",
        url,
        meta.get("status"),
        meta.get("used_impersonation"),
        len(body),
    )
    return body


def load_manifest(
    *,
    url: str | None = None,
    path: Path | None = None,
    allow_community_fallback: bool = False,
) -> tuple[list[SourceRecord], bytes, str]:
    """
    Returns (records, raw_bytes, source_url_used).
    """
    if path:
        raw = path.read_bytes()
        text = raw.decode("utf-8-sig")
        return parse_manifest_csv(text), raw, str(path)

    primary = url or OFFICIAL_MANIFEST_URL
    try:
        raw = fetch_bytes(primary)
        text = raw.decode("utf-8-sig")
        return parse_manifest_csv(text), raw, primary
    except Exception as e:
        if not allow_community_fallback:
            raise
        logger.warning(
            "official manifest fetch failed (%s); falling back to community snapshot",
            e,
        )
        raw = fetch_bytes(COMMUNITY_R06_SNAPSHOT)
        text = raw.decode("utf-8-sig")
        return parse_manifest_csv(text), raw, COMMUNITY_R06_SNAPSHOT


def summarize_by_release(records: Iterable[SourceRecord]) -> dict[int, dict]:
    from collections import Counter, defaultdict

    by: dict[int, dict] = defaultdict(lambda: {"total": 0, "types": Counter()})
    for r in records:
        n = r.release_number or 0
        by[n]["total"] += 1
        by[n]["types"][r.source_type] += 1
    return {k: {"total": v["total"], "types": dict(v["types"])} for k, v in sorted(by.items())}
