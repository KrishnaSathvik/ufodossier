"""
Truncation and JSON-outcome regression fixtures.

No API keys. Fake Haiku responses drive the extraction control flow.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from pipeline.extract import (
    JSON_STATS,
    dedupe_within_source,
    extract_chunk_with_subdivision,
    join_pages,
    reset_json_stats,
    split_section_at_midpoint,
)


def _pages(n: int, body: str = "Observed an unidentified object over the airfield.") -> str:
    parts = []
    for i in range(1, n + 1):
        parts.append(f"--- PAGE {i} ---\n{body} Page {i}.")
    return "\n\n".join(parts)


def _resp(text: str, stop_reason: str) -> SimpleNamespace:
    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(text=text)])


def _valid_array(*excerpts: str) -> str:
    rows = []
    for i, excerpt in enumerate(excerpts, start=1):
        rows.append(
            {
                "title": f"Incident {i}",
                "summary": "An object was observed.",
                "raw_excerpt": excerpt,
                "occurred_at_text": None,
                "occurred_at": None,
                "occurred_at_precision": "unknown",
                "location_text": "test field",
                "country": None,
                "region": None,
                "branch": None,
                "reporting_unit": None,
                "sensor_types": ["eyewitness"],
                "duration_seconds": None,
                "altitude_feet": None,
                "shape_description": None,
                "size_description": None,
                "resolution_status": "unresolved",
                "resolution_notes": None,
            }
        )
    import json

    return json.dumps(rows)


class TruncationFixtures(unittest.TestCase):
    def setUp(self) -> None:
        reset_json_stats()
        self.sf = {"filename": "TEST.pdf", "agency": "TEST", "file_type": "pdf"}

    def test_fixture_a_truncation_subdivides_without_identical_retry(self) -> None:
        """stop_reason=max_tokens → subdivide; do not retry the same input."""
        text = _pages(4)
        truncated = '[{"title": "x", "raw_excerpt": "Observed an unidentified'
        child_a = _valid_array("Observed an unidentified object over the airfield. Page 1.")
        child_b = _valid_array("Observed an unidentified object over the airfield. Page 3.")

        client = MagicMock()
        client.messages.create.side_effect = [
            _resp(truncated, "max_tokens"),
            _resp(child_a, "end_turn"),
            _resp(child_b, "end_turn"),
        ]

        incidents, metas = extract_chunk_with_subdivision(client, text, self.sf)
        self.assertGreaterEqual(len(incidents), 1)
        self.assertEqual(client.messages.create.call_count, 3)
        self.assertEqual(JSON_STATS["json_truncated"], 1)
        self.assertEqual(JSON_STATS["json_retry_failed"], 0)
        self.assertEqual(JSON_STATS["sections_subdivided"], 1)
        self.assertTrue(any(m["outcome"] == "json_truncated" for m in metas))
        # Parent input must not appear twice consecutively with a JSON-repair prompt.
        prompts = [c.kwargs["messages"][-1]["content"] for c in client.messages.create.call_args_list]
        self.assertFalse(any("not valid JSON" in p for p in prompts))

    def test_fixture_b_malformed_json_retries_once(self) -> None:
        """Normal completion + invalid JSON → one same-input retry."""
        text = _pages(2)
        bad = "{not json"
        good = _valid_array("Observed an unidentified object over the airfield. Page 1.")

        client = MagicMock()
        client.messages.create.side_effect = [
            _resp(bad, "end_turn"),
            _resp(good, "end_turn"),
        ]

        incidents, metas = extract_chunk_with_subdivision(client, text, self.sf)
        self.assertEqual(len(incidents), 1)
        self.assertEqual(client.messages.create.call_count, 2)
        self.assertEqual(JSON_STATS["json_invalid"], 1)
        self.assertEqual(JSON_STATS["json_retry_success"], 1)
        self.assertEqual(JSON_STATS["json_truncated"], 0)
        self.assertTrue(any("not valid JSON" in c.kwargs["messages"][-1]["content"] for c in client.messages.create.call_args_list))

    def test_fixture_c_child_truncation_recurses(self) -> None:
        """Child section that still truncates is split again."""
        text = _pages(4)
        truncated = '[{"title": "x", "raw_excerpt": "Observed'
        leaf = _valid_array("Observed an unidentified object over the airfield. Page 1.")

        client = MagicMock()
        # parent truncates → left truncates → left-left ok, left-right ok, right ok
        client.messages.create.side_effect = [
            _resp(truncated, "max_tokens"),  # pages 1-4
            _resp(truncated, "max_tokens"),  # pages 1-2
            _resp(leaf, "end_turn"),  # page 1
            _resp(leaf, "end_turn"),  # page 2
            _resp(leaf, "end_turn"),  # pages 3-4
        ]

        incidents, metas = extract_chunk_with_subdivision(client, text, self.sf)
        self.assertGreaterEqual(JSON_STATS["json_truncated"], 2)
        self.assertGreaterEqual(JSON_STATS["sections_subdivided"], 2)
        self.assertGreaterEqual(max(m["split_depth"] for m in metas), 2)
        self.assertGreaterEqual(len(incidents), 1)

    def test_fixture_d_min_size_truncation_flags_failed(self) -> None:
        """Single-page section that still truncates → extraction_failed, no fabricate."""
        text = _pages(1)
        truncated = '[{"title": "x", "raw_excerpt": "Observed an unidentified'

        client = MagicMock()
        client.messages.create.side_effect = [_resp(truncated, "max_tokens")]

        incidents, metas = extract_chunk_with_subdivision(client, text, self.sf)
        self.assertEqual(incidents, [])
        self.assertEqual(JSON_STATS["extraction_failed"], 1)
        self.assertEqual(JSON_STATS["sections_subdivided"], 0)
        self.assertEqual(metas[0]["outcome"], "extraction_failed")
        self.assertEqual(client.messages.create.call_count, 1)

    def test_split_uses_page_boundaries(self) -> None:
        text = _pages(5)
        left, right = split_section_at_midpoint(text)
        self.assertIn("--- PAGE 1 ---", left)
        self.assertIn("--- PAGE 2 ---", left)
        self.assertNotIn("--- PAGE 3 ---", left)
        self.assertIn("--- PAGE 3 ---", right)
        self.assertIn("--- PAGE 5 ---", right)

    def test_within_source_dedupe_same_excerpt(self) -> None:
        a = {
            "title": "A",
            "raw_excerpt": "Observed an unidentified object over the airfield.",
            "occurred_at": "2020-01-01",
            "location_text": "airfield",
        }
        b = {
            "title": "B",
            "raw_excerpt": "Observed an unidentified object over the airfield.",
            "occurred_at": "2020-01-01",
            "location_text": "airfield",
        }
        c = {
            "title": "C",
            "raw_excerpt": "A different craft hovered near the hangar for several minutes.",
            "occurred_at": "2020-01-02",
            "location_text": "hangar",
        }
        kept = dedupe_within_source([a, b, c])
        self.assertEqual(len(kept), 2)
        excerpts = {k["raw_excerpt"] for k in kept}
        self.assertIn(c["raw_excerpt"], excerpts)


if __name__ == "__main__":
    unittest.main()
