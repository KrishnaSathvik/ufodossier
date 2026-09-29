"""
Deterministic relationship rules. No LLM auto-merge.

Only strong evidence reaches auto_supported.
"""

from __future__ import annotations

from typing import Any

from pipeline.linker.intra_source_episode import group_episodes
from pipeline.linker.models import (
    CanonicalEvent,
    EventMember,
    EventSeries,
    EventSource,
    LinkDecision,
)
from pipeline.linker.normalize import is_generic_location, specific_place_tokens, year_from


def _decision(
    *,
    decision_id: str,
    relationship: str,
    status: str,
    left: str,
    right: str,
    evidence: list[str],
    score_band: str,
) -> LinkDecision:
    return LinkDecision(
        decision_id=decision_id,
        relationship=relationship,  # type: ignore[arg-type]
        status=status,  # type: ignore[arg-type]
        left=left,
        right=right,
        evidence=evidence,
        score_band=score_band,
        auto_merged=False,
        incidents_rewritten=False,
    )


def apply_rules(
    *,
    incidents: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
    catalog: dict[str, dict[str, Any]],
    candidates: list[dict[str, Any]],
    texts: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Build canonical events, series, and explainable decisions.
    Never deletes or rewrites extracted incidents.
    """
    texts = texts or {}
    by_file = {row["filename"]: row for row in classifications}
    decisions: list[LinkDecision] = []
    rejected: list[LinkDecision] = []
    events: list[CanonicalEvent] = []
    members: list[EventMember] = []
    sources: list[EventSource] = []
    series_list: list[EventSeries] = []
    n = 0

    def next_id(prefix: str) -> str:
        nonlocal n
        n += 1
        return f"{prefix}-{n:04d}"

    # --- Negative controls: record rejections for weak signals ---
    for left in incidents:
        for right in incidents:
            if left is right:
                continue
            if left.get("source_filename") == right.get("source_filename"):
                continue
            # same agency alone
            if (left.get("branch") or left.get("document_class")) and is_generic_location(
                left.get("location_text")
            ) and is_generic_location(right.get("location_text")):
                pass  # handled in bulk below once

    # Explicit reject: generic western US location pairs
    generic_pairs_checked = 0
    for i, left in enumerate(incidents):
        if not is_generic_location(left.get("location_text")):
            continue
        for right in incidents[i + 1 :]:
            if left.get("source_filename") == right.get("source_filename"):
                continue
            if not is_generic_location(right.get("location_text")):
                continue
            generic_pairs_checked += 1
            if generic_pairs_checked > 20:
                break
            rejected.append(
                _decision(
                    decision_id=next_id("rej"),
                    relationship="unrelated",
                    status="rejected",
                    left=left.get("case_id") or "",
                    right=right.get("case_id") or "",
                    evidence=[
                        "generic location alone is not linking evidence",
                        f"left_location={left.get('location_text')!r}",
                        f"right_location={right.get('location_text')!r}",
                    ],
                    score_band="weak",
                )
            )
        if generic_pairs_checked > 20:
            break

    # --- Intra-source episodes: each episode becomes a provisional canonical event ---
    by_source: dict[str, list[dict]] = {}
    for inc in incidents:
        by_source.setdefault(inc.get("source_filename") or "", []).append(inc)

    episode_events: dict[str, str] = {}  # case_id -> event_id
    episode_audit: dict[str, Any] = {}

    for filename, rows in by_source.items():
        episodes, boundaries = group_episodes(rows)
        episode_audit[filename] = {
            "input_rows": len(rows),
            "episode_count": len(episodes),
            "boundaries": [b.to_dict() for b in boundaries],
        }
        for idx, ep in enumerate(episodes, start=1):
            primary = ep[0]
            places = specific_place_tokens(primary.get("location_text") or "")
            label_place = sorted(places)[0] if places else (primary.get("location_text") or "unspecified")
            year = year_from(primary.get("occurred_at")) or year_from(primary.get("raw_excerpt") or "") or "undated"
            event = CanonicalEvent(
                event_id=next_id("evt"),
                label=f"{label_place} / {year} / {filename}#ep{idx}",
                occurred_at=primary.get("occurred_at"),
                location_text=primary.get("location_text"),
                member_case_ids=[r.get("case_id") or "" for r in ep],
                source_roles=[{"filename": filename, "role": "primary_narrative"}],
                notes=[f"intra-source episode {idx} of {len(episodes)} from {filename}"],
            )
            events.append(event)
            for r in ep:
                cid = r.get("case_id") or ""
                episode_events[cid] = event.event_id
                members.append(
                    EventMember(
                        event_id=event.event_id,
                        case_id=cid,
                        source_filename=filename,
                        role="observation",
                        episode_id=f"{filename}#ep{idx}",
                    )
                )
            if len(ep) > 1:
                decisions.append(
                    _decision(
                        decision_id=next_id("dec"),
                        relationship="same_event",
                        status="auto_supported",
                        left=ep[0].get("case_id") or "",
                        right=ep[-1].get("case_id") or "",
                        evidence=[
                            "intra-source continuity cues grouped phase rows into one episode",
                            f"episode size={len(ep)}",
                            f"source={filename}",
                        ],
                        score_band="strong",
                    )
                )

    # --- Catalog pairing → media / analysis / followup roles ---
    for cand in candidates:
        kind = cand["candidate_kind"]
        if kind == "catalog_pdf_pairing":
            left = cand["left"]
            right = cand["right"]
            left_row = by_file.get(left) or {}
            right_row = by_file.get(right) or {}
            left_class = (left_row.get("classification") or {}).get("document_class")
            right_class = (right_row.get("classification") or {}).get("document_class")

            # Prefer attaching source_only media/analysis onto an extract primary.
            media_file = None
            primary_file = None
            relationship = None
            if left_class == "media_metadata" and (right_row.get("extraction_action") == "extract"):
                media_file, primary_file, relationship = left, right, "media_for_event"
            elif right_class == "media_metadata" and (left_row.get("extraction_action") == "extract"):
                media_file, primary_file, relationship = right, left, "media_for_event"

            if relationship and media_file and primary_file:
                # Attach to canonical event(s) that have members from primary_file.
                target_events = [e for e in events if any(m.source_filename == primary_file for m in members if m.event_id == e.event_id)]
                # Simpler: events whose members include primary_file
                target_events = [
                    e
                    for e in events
                    if any(
                        mem.event_id == e.event_id and mem.source_filename == primary_file for mem in members
                    )
                ]
                for e in target_events:
                    sources.append(
                        EventSource(
                            event_id=e.event_id,
                            source_filename=media_file,
                            relationship="media_for_event",
                            document_class=left_class if media_file == left else right_class,
                        )
                    )
                    e.source_roles.append({"filename": media_file, "role": "media_for_event"})
                    decisions.append(
                        _decision(
                            decision_id=next_id("dec"),
                            relationship="media_for_event",
                            status="auto_supported",
                            left=media_file,
                            right=e.event_id,
                            evidence=list(cand["evidence"])
                            + ["official catalog PDF pairing", f"primary narrative source {primary_file}"],
                            score_band="strong",
                        )
                    )

        elif kind == "analysis_place_match":
            analysis_file = cand["left"]
            case_id = cand["right"]
            event_id = episode_events.get(case_id)
            if not event_id:
                continue
            event = next(e for e in events if e.event_id == event_id)
            band = cand.get("score_band") or "medium"
            status = "auto_supported" if band == "strong" else "needs_review"
            if status == "auto_supported":
                sources.append(
                    EventSource(
                        event_id=event_id,
                        source_filename=analysis_file,
                        relationship="analysis_of_event",
                        document_class="analysis",
                    )
                )
                event.source_roles.append({"filename": analysis_file, "role": "analysis_of_event"})
            decisions.append(
                _decision(
                    decision_id=next_id("dec"),
                    relationship="analysis_of_event",
                    status=status,
                    left=analysis_file,
                    right=event_id,
                    evidence=list(cand["evidence"]),
                    score_band=band,
                )
            )

        elif kind == "series_identifier":
            series_id = cand.get("series_id")
            label = cand.get("series_label") or ""
            # Spaced catalog tokens (photo captions, filenames) are not the
            # Western US series. Only an explicit series_id, or a label that
            # actually names that series, may join it.
            if not series_id:
                if "western" in label.lower() and "event" in label.lower():
                    series_id = "western-us-event-2023"
                else:
                    continue
            if not label:
                label = (
                    "Western U.S. 2023 Series"
                    if series_id == "western-us-event-2023"
                    else series_id
                )
            existing = next((s for s in series_list if s.series_id == series_id), None)
            if existing is None:
                existing = EventSeries(
                    series_id=series_id,
                    label=str(label),
                    evidence=list(cand["evidence"]),
                )
                series_list.append(existing)
            filename = cand["left"]
            # Add all episode events from this file into the series (same_series, NOT same_event)
            file_event_ids = [
                e.event_id
                for e in events
                if any(m.event_id == e.event_id and m.source_filename == filename for m in members)
            ]
            for eid in file_event_ids:
                if eid not in existing.event_ids:
                    existing.event_ids.append(eid)
            decisions.append(
                _decision(
                    decision_id=next_id("dec"),
                    relationship="same_series",
                    status="auto_supported",
                    left=filename,
                    right=series_id,
                    evidence=list(cand["evidence"])
                    + [
                        "series membership does not imply same_event",
                        f"episodes from {filename}: {len(file_event_ids)}",
                    ],
                    score_band="strong",
                )
            )

        elif kind == "specific_place_overlap":
            left_case = cand["left"]
            right_case = cand["right"]
            left_event = episode_events.get(left_case)
            right_event = episode_events.get(right_case)
            if not left_event or not right_event or left_event == right_event:
                continue
            # Distinctive places with matching year → review_supported same_event candidate, not auto merge
            decisions.append(
                _decision(
                    decision_id=next_id("dec"),
                    relationship="same_event",
                    status="review_supported",
                    left=left_event,
                    right=right_event,
                    evidence=list(cand["evidence"])
                    + ["cross-source specific place overlap; review before consolidating events"],
                    score_band="medium",
                )
            )

    # Dedupe media/analysis attachments per event+file
    uniq_sources: list[EventSource] = []
    seen_src: set[tuple[str, str, str]] = set()
    for src in sources:
        key = (src.event_id, src.source_filename, src.relationship)
        if key in seen_src:
            continue
        seen_src.add(key)
        uniq_sources.append(src)

    # Collapse duplicate same_series decisions per file
    # (keep all for audit transparency)

    return {
        "canonical_events": [e.to_dict() for e in events],
        "event_members": [m.to_dict() for m in members],
        "event_sources": [s.to_dict() for s in uniq_sources],
        "event_series": [s.to_dict() for s in series_list],
        "decisions": [d.to_dict() for d in decisions],
        "rejected_pairs": [d.to_dict() for d in rejected],
        "episode_audit": episode_audit,
        "production_writes": False,
        "auto_merged": False,
        "incidents_rewritten": False,
    }
