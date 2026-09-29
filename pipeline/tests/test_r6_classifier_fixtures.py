"""R6 classifier regression: DIRD/personnel false extracts + known-good DIRD controls."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from pipeline.classify_document import classify_text

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "r6_classifier"
EXPECTED = json.loads((FIXTURE_DIR / "expected_classifications.json").read_text())
TEXTS = FIXTURE_DIR / "texts"


class R6ClassifierFixtureTests(unittest.TestCase):
    def test_dird_personnel_and_controls(self):
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
                msg=f"{doc['filename']} class ({c.reason})",
            )
            self.assertEqual(
                c.contains_incidents,
                doc["contains_incidents"],
                msg=f"{doc['filename']} contains_incidents ({c.reason})",
            )
            action = "extract" if c.contains_incidents else "source_only"
            self.assertEqual(action, doc["extraction_action"], msg=doc["filename"])


if __name__ == "__main__":
    unittest.main()
