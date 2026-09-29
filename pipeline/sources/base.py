"""Shared types and helpers for official source providers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any, Literal

Provider = Literal["pursue", "aaro", "nara"]
SourceType = Literal["pdf", "image", "video", "audio", "webpage", "other"]
RecordStatus = Literal["active", "deprecated", "superseded", "unavailable", "pending"]
DiffClass = Literal["UNCHANGED", "NEW", "MODIFIED", "DEPRECATED", "RETURNED"]


@dataclass
class SourceRecord:
    provider: Provider
    identity_key: str
    source_type: SourceType
    external_id: str | None = None
    release_number: int | None = None
    release_date: date | None = None
    release_label: str | None = None
    title: str | None = None
    description: str | None = None
    agency: str | None = None
    agency_raw: str | None = None
    incident_date_hint: str | None = None
    incident_location_hint: str | None = None
    original_url: str | None = None
    download_url: str | None = None
    thumbnail_url: str | None = None
    status: RecordStatus = "active"
    sha256: str | None = None
    byte_size: int | None = None
    mime_type: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_row(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("release_date",):
            if isinstance(d.get(k), date):
                d[k] = d[k].isoformat()
        return d


def normalize_ws(s: str | None) -> str:
    if not s:
        return ""
    # expand common typographic ligatures seen in R06
    s = s.replace("\ufb01", "fi").replace("\ufb02", "fl")
    s = s.replace("\u00a0", " ").replace("\u202f", " ")
    return re.sub(r"\s+", " ", s).strip()


def slugify(s: str, max_len: int = 80) -> str:
    s = normalize_ws(s).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len] or "untitled"


def identity_key(
    provider: str,
    *,
    external_id: str | None = None,
    title: str | None = None,
    url: str | None = None,
) -> str:
    """
    Prefer stable official IDs. Fall back to provider+title+url hash.
    """
    if external_id and normalize_ws(external_id):
        return f"{provider}:{normalize_ws(external_id).upper()}"
    payload = "|".join(
        [
            provider,
            normalize_ws(title).lower(),
            normalize_ws(url),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]
    return f"{provider}:h:{digest}"


def file_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_us_short_date(s: str | None) -> date | None:
    """Parse M/D/YY or M/D/YYYY as used in uap-data.csv Release Date."""
    if not s:
        return None
    s = normalize_ws(s)
    for fmt in ("%m/%d/%y", "%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


RELEASE_DATE_TO_NUMBER: dict[str, int] = {
    "5/8/26": 1,
    "5/22/26": 2,
    "6/12/26": 3,
    "7/10/26": 4,
    "8/7/26": 5,
    "9/18/26": 6,
}

RELEASE_NUMBER_TO_LABEL: dict[int, str] = {
    1: "Release 01",
    2: "Release 02",
    3: "Release 03",
    4: "Release 04",
    5: "Release 05",
    6: "Release 06",
}


def release_number_for_date(raw: str | None) -> int | None:
    if not raw:
        return None
    key = normalize_ws(raw)
    if key in RELEASE_DATE_TO_NUMBER:
        return RELEASE_DATE_TO_NUMBER[key]
    d = parse_us_short_date(key)
    if not d:
        return None
    # rebuild M/D/YY key
    yy = d.year % 100
    rebuilt = f"{d.month}/{d.day}/{yy:02d}"
    return RELEASE_DATE_TO_NUMBER.get(rebuilt)
