"""Permanent R3 classifier regressions on real OCR heads. No network, no DB."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pipeline.classify_document import classify_text

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "r3_classifier"
EXPECTED = json.loads((FIXTURE_DIR / "expected_classifications.json").read_text())
TEXTS = FIXTURE_DIR / "texts"


class R3ClassifierFixtureTests(unittest.TestCase):
    def test_four_readiness_docs_match_expected_disposition(self):
        for doc in EXPECTED["documents"]:
            stem = Path(doc["filename"]).stem
            text = (TEXTS / f"{stem}.txt").read_text()
            c = classify_text(
                title=stem.replace("_", " "),
                filename=doc["filename"],
                text=text,
                agency=doc["external_id"].split("-")[0],
            )
            self.assertEqual(
                c.document_class,
                doc["document_class"],
                msg=f"{doc['filename']} class ({c.reason})",
            )
            self.assertEqual(
                c.contains_incidents,
                doc["contains_incidents"],
                msg=f"{doc['filename']} contains_incidents ({c.reason})",
            )


if __name__ == "__main__":
    unittest.main()
