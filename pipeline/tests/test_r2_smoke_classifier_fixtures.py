"""Regression: frozen R2 smoke classifier decisions on fixture texts."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pipeline.classify_document import classify_text

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "r2_smoke"
EXPECTED = json.loads((FIXTURE_DIR / "expected_classifications.json").read_text())
TEXTS = FIXTURE_DIR / "texts"


class R2SmokeClassifierFixtureTests(unittest.TestCase):
    def test_five_smoke_docs_match_frozen_baseline(self):
        for doc in EXPECTED["documents"]:
            stem = Path(doc["filename"]).stem
            text = (TEXTS / f"{stem}.txt").read_text()
            c = classify_text(
                title=stem.replace("-", " "),
                filename=doc["filename"],
                text=text,
                agency=doc["external_id"].split("-")[0],
            )
            self.assertEqual(
                c.document_class,
                doc["document_class"],
                msg=f"{doc['filename']} class",
            )
            self.assertEqual(
                c.contains_incidents,
                doc["contains_incidents"],
                msg=f"{doc['filename']} contains_incidents",
            )


if __name__ == "__main__":
    unittest.main()
