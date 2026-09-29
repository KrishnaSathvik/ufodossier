"""Unit tests for PURSUE manifest parsing (no network)."""

from __future__ import annotations

import unittest

from pipeline.sources.pursue import parse_manifest_csv, map_type, extract_external_id
from pipeline.sources.base import identity_key, release_number_for_date
from pipeline.diff_manifest import diff_snapshots


SAMPLE_CSV = """Featured,Redaction,Release Date,Title,Type,Video Pairing,PDF Pairing,Description Blurb,DVIDS Video ID,Video Title,Agency,Incident Date,Incident Location,PDF | Image Link,Modal Image,Image Alt Text,Image VIRIN
YES,TRUE,9/18/26,DOW-UAP-D114 Example DIRD,PDF,,,A sample DIRD summary.,,,Department of War,N/A,Las Vegas Nevada,https://www.war.gov/medialink/ufo/sept-18/release-06/assets/DOW-UAP-D114_Example.pdf,https://www.war.gov/thumb.jpg,,
,FALSE,5/8/26,Some FBI File,PDF,,,Old R1 row.,,,FBI,1952,Utah,https://www.war.gov/medialink/ufo/release_1/fbi_file.pdf,,,
,,5/22/26,NASA Audio Debrief,AUD,,,Audio record.,1001234,Debrief,NASA,2023,Houston,,,,,
"""


class PursueParseTests(unittest.TestCase):
    def test_parse_counts_and_types(self):
        rows = parse_manifest_csv(SAMPLE_CSV)
        self.assertEqual(len(rows), 3)
        types = {r.source_type for r in rows}
        self.assertEqual(types, {"pdf", "audio"})

    def test_release_numbers(self):
        rows = parse_manifest_csv(SAMPLE_CSV)
        by_title = {r.title: r for r in rows}
        self.assertEqual(by_title["DOW-UAP-D114 Example DIRD"].release_number, 6)
        self.assertEqual(by_title["Some FBI File"].release_number, 1)
        self.assertEqual(by_title["NASA Audio Debrief"].release_number, 2)

    def test_external_id(self):
        self.assertEqual(
            extract_external_id("DOW-UAP-D114 Example", None),
            "DOW-UAP-D114",
        )
        self.assertEqual(map_type("PDF "), "pdf")

    def test_identity_stable(self):
        a = identity_key("pursue", external_id="DOW-UAP-D114")
        b = identity_key("pursue", external_id="dow-uap-d114")
        self.assertEqual(a, b)

    def test_release_date_map(self):
        self.assertEqual(release_number_for_date("9/18/26"), 6)
        self.assertIsNone(release_number_for_date(""))


class DiffTests(unittest.TestCase):
    def test_new_modified_deprecated(self):
        prev = {
            "pursue:A": {
                "identity_key": "pursue:A",
                "title": "Same",
                "original_url": "http://a",
                "status": "active",
            },
            "pursue:B": {
                "identity_key": "pursue:B",
                "title": "Old",
                "original_url": "http://b",
                "status": "active",
            },
            "pursue:C": {
                "identity_key": "pursue:C",
                "title": "Gone",
                "original_url": "http://c",
                "status": "active",
            },
        }
        curr = {
            "pursue:A": {
                "identity_key": "pursue:A",
                "title": "Same",
                "original_url": "http://a",
                "status": "active",
            },
            "pursue:B": {
                "identity_key": "pursue:B",
                "title": "Changed",
                "original_url": "http://b",
                "status": "active",
            },
            "pursue:D": {
                "identity_key": "pursue:D",
                "title": "New",
                "original_url": "http://d",
                "status": "active",
            },
        }
        result = diff_snapshots(prev, curr)
        self.assertEqual(result["summary"]["new"], 1)
        self.assertEqual(result["summary"]["modified"], 1)
        self.assertEqual(result["summary"]["deprecated"], 1)
        self.assertEqual(result["summary"]["unchanged"], 1)


if __name__ == "__main__":
    unittest.main()
