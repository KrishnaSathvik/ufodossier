"""Intra-source episode grouper. Does not invent a target event count."""

from __future__ import annotations

from typing import Any

from pipeline.linker.models import EpisodeDecision
from pipeline.linker.normalize import continuity_cue, normalize_excerpt


def group_episodes(incidents: list[dict[str, Any]]) -> tuple[list[list[dict]], list[EpisodeDecision]]:
    """
    Group accepted rows from ONE source into episodes.

    Boundaries:
      - explicit "next day" / "few days later" / "months later" → new_episode
      - "later that night" / "shortly thereafter" / minutes later → same_episode
      - adjacent rows with no cue → uncertain_boundary (kept separate unless same cue chain)

    Never merges solely because excerpts are adjacent.
    """
    if not incidents:
        return [], []
    ordered = list(incidents)
    source = ordered[0].get("source_filename") or ""
    episodes: list[list[dict]] = [[ordered[0]]]
    decisions: list[EpisodeDecision] = []

    for prev, curr in zip(ordered, ordered[1:]):
        cue = continuity_cue(curr.get("raw_excerpt") or "")
        # Also check title for "next day" etc.
        if cue is None:
            cue = continuity_cue(curr.get("title") or "")
        if cue == "new_episode":
            boundary = "new_episode"
            episodes.append([curr])
        elif cue == "same_episode":
            boundary = "same_episode"
            episodes[-1].append(curr)
        else:
            # No continuity language: do not fold into prior episode.
            boundary = "uncertain_boundary"
            episodes.append([curr])
        decisions.append(
            EpisodeDecision(
                source_filename=source,
                left_case_id=prev.get("case_id") or "",
                right_case_id=curr.get("case_id") or "",
                boundary=boundary,
                evidence=[f"continuity_cue={cue or 'none'}"],
            )
        )
    return episodes, decisions


def episode_summary(incidents: list[dict[str, Any]]) -> dict[str, Any]:
    episodes, decisions = group_episodes(incidents)
    return {
        "source_filename": incidents[0].get("source_filename") if incidents else None,
        "input_rows": len(incidents),
        "episode_count": len(episodes),
        "episodes": [
            {
                "episode_index": i,
                "case_ids": [row.get("case_id") for row in ep],
                "titles": [row.get("title") for row in ep],
                "excerpt_norms": [normalize_excerpt(row.get("raw_excerpt") or "")[:80] for row in ep],
            }
            for i, ep in enumerate(episodes, start=1)
        ],
        "boundaries": [d.to_dict() for d in decisions],
    }
