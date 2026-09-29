"""Evidence-sufficiency gate tests (does not touch quote substring tolerance)."""

from __future__ import annotations

import unittest

from pipeline.extract import evidence_sufficient


class EvidenceSufficiencyTests(unittest.TestCase):
    def test_substantive_observation_passes(self):
        ok, reason = evidence_sufficient(
            {
                "title": "Green circular object at Site 7",
                "raw_excerpt": (
                    "On one evening in late summer 1973, Source observed an unidentified "
                    "phenomenon at Site 7. He stepped outside and observed an unidentified "
                    "sharp green circular object or mass in the sky."
                ),
            }
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_thin_pantex_caption_fails(self):
        ok, reason = evidence_sufficient(
            {
                "title": "Pantex Unidentified Object Incident",
                "raw_excerpt": "Image from Ground Surveillance Radar Tower",
            }
        )
        self.assertFalse(ok)
        self.assertIn(reason, ("excerpt_too_short_for_claim", "excerpt_too_few_words", "thin_media_caption"))


if __name__ == "__main__":
    unittest.main()
