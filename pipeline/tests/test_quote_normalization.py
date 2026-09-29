"""Quote-safe OCR normalization. Does not relax substring validation."""

from __future__ import annotations

import unittest

from pipeline.extract import _normalize_for_match, _validate_incident


class QuoteNormalizationTests(unittest.TestCase):
    def test_ocr_letter_spacing_matches_intact_word(self):
        source = (
            "a former U. S. Army inte l ligence officer observed a UAP as they exited "
            "their office bui l ding ."
        )
        excerpt = (
            "a former U. S. Army intelligence officer observed a UAP as they exited "
            "their office building."
        )
        self.assertIn(_normalize_for_match(excerpt), _normalize_for_match(source))

    def test_spaced_excerpt_still_matches_spaced_source(self):
        source = "The object was opa l escent and the officer exited the bui l ding ."
        excerpt = "The object was opa l escent and the officer exited the bui l ding."
        self.assertIn(_normalize_for_match(excerpt), _normalize_for_match(source))

    def test_lone_letter_does_not_cross_word_boundaries(self):
        self.assertEqual(
            _normalize_for_match("appeared to l ook painted"),
            "appeared to look painted",
        )
        self.assertEqual(
            _normalize_for_match("each pane l on the object"),
            "each panel on the object",
        )
        self.assertNotIn("tolook", _normalize_for_match("to l ook"))
        self.assertNotIn("panelon", _normalize_for_match("pane l on"))

    def test_ordinary_word_spaces_are_not_glued(self):
        text = "the object was still over the mountain"
        self.assertEqual(_normalize_for_match(text), text)

    def test_first_person_saw_is_not_glued(self):
        text = "i saw four beams in the sky"
        self.assertEqual(_normalize_for_match(text), text)

    def test_eol_hyphen_and_page_marker(self):
        source = "--- PAGE 2 ---\ncom-\npetition of the craft"
        excerpt = "competition of the craft"
        self.assertIn(_normalize_for_match(excerpt), _normalize_for_match(source))

    def test_stitched_noncontiguous_excerpt_still_dropped(self):
        gap = "unrelated routing text " * 40
        source = (
            "They exited their office building. "
            + gap
            + "A separate note said the object vanished."
        )
        inc = {
            "title": "Cheyenne object",
            "summary": "An object was seen and then vanished.",
            "raw_excerpt": "They exited their office building. The object vanished.",
            "resolution_status": "unresolved",
        }
        self.assertIsNone(_validate_incident(inc, source, {"filename": "x.pdf", "id": "local"}))

    def test_spacing_normalized_contiguous_excerpt_kept(self):
        source = "They exited their office bui l ding and observed a UAP over the ridge."
        inc = {
            "title": "Cheyenne object",
            "summary": "Witnesses observed a UAP after leaving the building.",
            "raw_excerpt": "They exited their office building and observed a UAP over the ridge.",
            "resolution_status": "unresolved",
        }
        kept = _validate_incident(inc, source, {"filename": "x.pdf", "id": "local"})
        self.assertIsNotNone(kept)

    def test_fabricated_excerpt_still_dropped(self):
        source = "The sensor focuses on a football-shaped body."
        inc = {
            "title": "Roswell",
            "summary": "Bodies were recovered.",
            "raw_excerpt": "Three small humanoid bodies were recovered from the Roswell crash site.",
            "resolution_status": "identified",
        }
        self.assertIsNone(_validate_incident(inc, source, {"filename": "x.pdf", "id": "local"}))


if __name__ == "__main__":
    unittest.main()
