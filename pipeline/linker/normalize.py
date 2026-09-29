"""Deterministic text/place/date normalization for linker V1."""

from __future__ import annotations

import re

# Generic tokens that must NEVER alone generate a candidate or merge.
GENERIC_PLACE = frozenset(
    """
    united states western eastern northern southern central west east north south
    america american country region area near over under around about valley
    mountain mountains ridge ridgelines hillside rural highway road lake pond
    base field site location observation point
    """.split()
)

GENERIC_TOPIC = frozenset(
    """
    uap ufo unidentified anomalous phenomena phenomenon aerial object objects
    light lights orb orbs craft flying sighting report incident
    """.split()
)

_SERIES_ID_RE = re.compile(r"\bwestern\s+us\s+event\b", re.I)
_NEXT_DAY_RE = re.compile(
    r"\b(the next day|next day|a few days later|some months thereafter|"
    r"months later|the following (?:day|night|morning))\b",
    re.I,
)
_SAME_NIGHT_RE = re.compile(
    r"\b(later(?: that| in the)? night|later that evening|shortly thereafter|"
    r"soon thereafter|after about \d+ minutes|at some point|"
    r"later,? I (?:saw|observed|watched)|I continued to see)\b",
    re.I,
)
_YEAR_RE = re.compile(r"(19|20)\d{2}")
_SPECIFIC_PLACE_RE = re.compile(
    r"\b("
    r"colorado\s+springs|cheyenne(?:\s+mountains?)?|cheyenne\s+mountain|"
    r"boise|bakersfield|newark|glen\s+ridge|pasco|richland|kennewick|"
    r"seattle|sand\s+point|fort\s+ross|green\s+river|smyrna|"
    r"lovelock|medford|mt\.?\s*shasta|houston|hartford|manitou|"
    r"budapest|ladakh|bhutan|harare|crimea|sary\s+shagan"
    r")\b",
    re.I,
)


def normalize_excerpt(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def year_from(text: str | None) -> str | None:
    if not text:
        return None
    match = _YEAR_RE.search(text)
    return match.group(0) if match else None


def specific_place_tokens(text: str) -> set[str]:
    """Only known distinctive places. Capitalized prose words are not places."""
    found: set[str] = set()
    for match in _SPECIFIC_PLACE_RE.finditer(text or ""):
        token = match.group(0).lower()
        found.add(token)
        head = token.split()[0]
        if head not in GENERIC_PLACE and len(head) >= 5:
            found.add(head)
    return found


def is_generic_location(text: str | None) -> bool:
    if not text or not text.strip():
        return True
    if _SPECIFIC_PLACE_RE.search(text):
        return False
    words = set(re.findall(r"[a-z]+", text.lower()))
    extras = {"airfield", "an", "and", "or", "to", "from", "the", "of", "in", "a", "on", "near"}
    return not words or words <= (GENERIC_PLACE | GENERIC_TOPIC | extras)


def series_identifiers(text: str) -> set[str]:
    ids: set[str] = set()
    if _SERIES_ID_RE.search(text or ""):
        ids.add("western-us-event-2023")
    return ids


def continuity_cue(excerpt: str) -> str | None:
    """Return 'new_episode', 'same_episode', or None from narrative language."""
    if _NEXT_DAY_RE.search(excerpt or ""):
        return "new_episode"
    if _SAME_NIGHT_RE.search(excerpt or ""):
        return "same_episode"
    return None
