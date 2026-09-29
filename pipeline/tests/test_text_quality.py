"""Unit tests for page-level text quality scoring (no network)."""

from __future__ import annotations

import unittest

from pipeline.text_quality import score_page_text


class TextQualityTests(unittest.TestCase):
    def test_empty_needs_ocr(self):
        q = score_page_text(1, "")
        self.assertEqual(q.category, "needs_ocr")

    def test_native_good(self):
        text = (
            "On one evening in late summer 1973, Source observed an unidentified "
            "phenomenon at Site 7. While watching a sport competition between Canada "
            "and the USSR on television, he stepped outside for some air and observed "
            "an unidentified sharp green circular object or mass in the sky."
        )
        q = score_page_text(1, text)
        self.assertEqual(q.category, "native_good")

    def test_native_thin_caption(self):
        text = "Image from Ground Surveillance Radar Tower\nPantex Unidentified Object Incident Report"
        q = score_page_text(1, text)
        self.assertIn(q.category, ("native_thin", "native_good"))

    def test_garbage_needs_ocr(self):
        text = "DIR!CIOUTC Of OP!UIIONS \\\\'Alll',;J:-;c; F\\OTICE lNT~LUC.lNC..:E SOUltCES A~D MLl"
        q = score_page_text(1, text)
        self.assertEqual(q.category, "needs_ocr")

    def test_replacement_chars_needs_ocr(self):
        text = "Source observed an object " + ("\ufffd" * 5) + " in the sky near Site 7 with witnesses present."
        q = score_page_text(1, text)
        self.assertEqual(q.category, "needs_ocr")


if __name__ == "__main__":
    unittest.main()
