"""Local-only canonical identity models. Incidents remain immutable."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Relationship = Literal[
    "same_event",
    "same_series",
    "primary_narrative",
    "supporting_narrative",
    "media_for_event",
    "analysis_of_event",
    "followup_to_event",
    "duplicate_source",
    "unrelated",
    "needs_review",
]

DecisionStatus = Literal[
    "auto_supported",
    "review_supported",
    "needs_review",
    "rejected",
]

EpisodeBoundary = Literal[
    "same_episode",
    "new_episode",
    "uncertain_boundary",
]


@dataclass
class CanonicalEvent:
    event_id: str
    label: str
    occurred_at: str | None = None
    location_text: str | None = None
    member_case_ids: list[str] = field(default_factory=list)
    source_roles: list[dict[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventMember:
    event_id: str
    case_id: str
    source_filename: str
    role: str = "observation"
    episode_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventSource:
    event_id: str
    source_filename: str
    relationship: Relationship
    document_class: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EventSeries:
    series_id: str
    label: str
    event_ids: list[str] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LinkDecision:
    decision_id: str
    relationship: Relationship
    status: DecisionStatus
    left: str
    right: str
    evidence: list[str] = field(default_factory=list)
    score_band: str = "none"  # strong | medium | weak | negative | none
    auto_merged: bool = False
    incidents_rewritten: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class EpisodeDecision:
    source_filename: str
    left_case_id: str
    right_case_id: str
    boundary: EpisodeBoundary
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
