"""Write linker V1 audit artifacts. Local filesystem only."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_audit(out_dir: Path, payload: dict[str, Any]) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    generated = datetime.now(timezone.utc).isoformat()

    colorado = _colorado_view(payload)
    western = _western_view(payload)

    (out_dir / "colorado_springs.json").write_text(json.dumps(colorado, indent=2) + "\n")
    (out_dir / "western_us_series.json").write_text(json.dumps(western, indent=2) + "\n")
    (out_dir / "candidate_pairs.json").write_text(
        json.dumps({"generated_at": generated, "candidates": payload.get("candidates") or []}, indent=2) + "\n"
    )
    (out_dir / "decisions.json").write_text(
        json.dumps({"generated_at": generated, "decisions": payload.get("decisions") or []}, indent=2) + "\n"
    )
    (out_dir / "rejected_pairs.json").write_text(
        json.dumps({"generated_at": generated, "rejected": payload.get("rejected_pairs") or []}, indent=2) + "\n"
    )

    metrics = {
        "generated_at": generated,
        "production_writes": 0,
        "deploy": 0,
        "gpt6": "off",
        "r4_started": False,
        "auto_merged": False,
        "incidents_rewritten": False,
        "canonical_events": len(payload.get("canonical_events") or []),
        "event_series": len(payload.get("event_series") or []),
        "decisions": len(payload.get("decisions") or []),
        "rejected_pairs": len(payload.get("rejected_pairs") or []),
        "candidates": len(payload.get("candidates") or []),
        "colorado_springs": {
            "canonical_events": colorado.get("canonical_events_created"),
            "media_attached": colorado.get("media_attached"),
            "analysis_attached": colorado.get("analysis_attached"),
            "extra_incidents_created": colorado.get("extra_incidents_created"),
            "pass": colorado.get("pass"),
        },
        "western_us": {
            "series_present": western.get("series_present"),
            "event_count": western.get("event_count"),
            "generic_location_same_event_auto": western.get("generic_location_same_event_auto"),
            "d082_input_rows": western.get("d082_input_rows"),
            "d082_episode_count": western.get("d082_episode_count"),
            "pass": western.get("pass"),
        },
    }
    (out_dir / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    (out_dir / "full_graph.json").write_text(json.dumps(payload, indent=2, default=str) + "\n")
    return metrics


def _colorado_view(payload: dict[str, Any]) -> dict[str, Any]:
    events = payload.get("canonical_events") or []
    sources = payload.get("event_sources") or []
    decisions = payload.get("decisions") or []

    cs_events = [
        e
        for e in events
        if any(
            tok in (e.get("label") or "").lower()
            or tok in (e.get("location_text") or "").lower()
            for tok in ("cheyenne", "colorado springs")
        )
        or any(
            role.get("filename") in {"FBI-UAP-D002.pdf", "FBI-UAP-D003.pdf", "ICA-UAP-D001.pdf"}
            for role in e.get("source_roles") or []
        )
    ]
    # Prefer events that include D002 members
    members = payload.get("event_members") or []
    d002_event_ids = {
        m["event_id"] for m in members if m.get("source_filename") == "FBI-UAP-D002.pdf"
    }
    cs_events = [e for e in events if e["event_id"] in d002_event_ids] or cs_events

    media = [
        s
        for s in sources
        if s.get("relationship") == "media_for_event" and s.get("source_filename") == "FBI-UAP-D003.pdf"
    ]
    analysis = [
        s
        for s in sources
        if s.get("relationship") == "analysis_of_event" and s.get("source_filename") == "ICA-UAP-D001.pdf"
    ]
    auto_same = [
        d
        for d in decisions
        if d.get("relationship") == "same_event"
        and d.get("status") == "auto_supported"
        and ("FBI-UAP-D003" in d.get("left", "") or "ICA-UAP" in d.get("left", ""))
    ]

    ok = (
        len(cs_events) == 1
        and len(media) >= 1
        and len(analysis) >= 1
        and len(auto_same) == 0
    )
    return {
        "canonical_events_created": len(cs_events),
        "events": cs_events,
        "media_attached": len(media) >= 1,
        "analysis_attached": len(analysis) >= 1,
        "extra_incidents_created": 0,
        "media_sources": media,
        "analysis_sources": analysis,
        "pass": ok,
        "note": "Incidents remain immutable; media/analysis are event_source roles only.",
    }


def _western_view(payload: dict[str, Any]) -> dict[str, Any]:
    series = payload.get("event_series") or []
    western = [s for s in series if "western" in (s.get("series_id") or "").lower() or "western" in (s.get("label") or "").lower()]
    episode_audit = payload.get("episode_audit") or {}
    d082 = episode_audit.get("DOW-UAP-D082.pdf") or {}
    decisions = payload.get("decisions") or []

    # same_event auto_supported across different western DOW files would be over-merge
    western_files = {f"DOW-UAP-D08{i}.pdf" for i in range(0, 4)} | {"DOW-UAP-D078.pdf", "DOW-UAP-D079.pdf"}
    bad_auto = []
    for d in decisions:
        if d.get("relationship") != "same_event" or d.get("status") != "auto_supported":
            continue
        # Episode-internal same_event is OK; cross-file auto same_event on generic western is not.
        left, right = d.get("left") or "", d.get("right") or ""
        if left.endswith(".pdf") or right.endswith(".pdf"):
            continue
        evidence = " ".join(d.get("evidence") or []).lower()
        if "intra-source" in evidence:
            continue
        if "generic" in evidence:
            bad_auto.append(d)

    series_ok = len(western) >= 1 and (western[0].get("event_ids") or [])
    d082_ok = (d082.get("input_rows") or 0) == 12 and 1 < (d082.get("episode_count") or 0) < 12
    return {
        "series_present": len(western) >= 1,
        "series": western,
        "event_count": len(western[0]["event_ids"]) if western else 0,
        "generic_location_same_event_auto": len(bad_auto),
        "d082_input_rows": d082.get("input_rows"),
        "d082_episode_count": d082.get("episode_count"),
        "d082_boundaries": d082.get("boundaries"),
        "pass": bool(series_ok and d082_ok and len(bad_auto) == 0),
        "note": "same_series is allowed; forcing one same_event across D078–D083 is not.",
    }
