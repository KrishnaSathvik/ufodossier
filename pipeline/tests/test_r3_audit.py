"""Relationship hints and review alarms. No extraction and no auto-link."""

from __future__ import annotations

import unittest

from pipeline.r3_audit import collect_relationship_hints, review_alarms


def _row(filename: str, doc_class: str, contains: bool, chars: int = 1000) -> dict:
    return {
        "filename": filename,
        "external_id": filename.replace(".pdf", ""),
        "usable_text_chars": chars,
        "page_count": 2,
        "pages_ocrd": 0,
        "ocr_failed": 0,
        "extraction_action": "extract" if contains else "source_only",
        "classification": {"document_class": doc_class, "contains_incidents": contains},
    }


class RelationshipHintTests(unittest.TestCase):
    def test_colorado_springs_roles_without_creating_incidents(self):
        accepted = [
            {
                "case_id": "C1",
                "source_filename": "FBI-UAP-D002.pdf",
                "location_text": "Cheyenne Mountains",
                "occurred_at": None,
                "raw_excerpt": "observed a UAP over the Cheyenne Mountains as they exited their office building.",
                "duplicate": {"duplicate_status": "new_event"},
            }
        ]
        classifications = [
            _row("FBI-UAP-D002.pdf", "transcript", True),
            _row("FBI-UAP-D003.pdf", "media_metadata", False, chars=93),
            _row("ICA-UAP-D001.pdf", "analysis", False),
            _row("CIA-UAP-009.pdf", "other", False, chars=126),
        ]
        catalog = {
            "FBI-UAP-D002": {"pdf_pairing": "", "incident_location": "Colorado Springs", "incident_date": "2022"},
            "FBI-UAP-D003": {"pdf_pairing": "FBI-UAP-D002", "incident_location": "Colorado Springs", "incident_date": "2022"},
            "ICA-UAP-D001": {"pdf_pairing": "", "incident_location": "Colorado Springs", "incident_date": "2022"},
            "CIA-UAP-009": {"pdf_pairing": "", "incident_location": "Budapest, Hungary", "incident_date": "1957"},
        }
        texts = {
            "ICA-UAP-D001.pdf": "An airborne object over Cheyenne Mountain in February 2022 was possible backscattering.",
            "CIA-UAP-009.pdf": "~~~~",
            "FBI-UAP-D003.pdf": "yy noise",
        }
        hints = collect_relationship_hints(
            accepted,
            classifications,
            catalog=catalog,
            texts=texts,
            thumbnails={"CIA-UAP-009.pdf"},
        )
        kinds = {(h["relationship"], h["source_filename"]) for h in hints}
        self.assertIn(("media_for_event", "FBI-UAP-D003.pdf"), kinds)
        self.assertIn(("analysis_of_event", "ICA-UAP-D001.pdf"), kinds)
        self.assertFalse(any(h["source_filename"] == "CIA-UAP-009.pdf" for h in hints))
        self.assertTrue(all(h["auto_linked"] is False and h["auto_merged"] is False for h in hints))
        self.assertEqual(len(accepted), 1)

    def test_generic_words_do_not_form_place_clusters(self):
        accepted = [
            {
                "case_id": "A",
                "source_filename": "A.pdf",
                "location_text": "western United States",
                "occurred_at": None,
                "raw_excerpt": "I saw a bright ball of light over a hillside in the western United States after sunset.",
                "duplicate": {"duplicate_status": "new_event"},
            },
            {
                "case_id": "B",
                "source_filename": "B.pdf",
                "location_text": "Between train and coast, approximately 50 miles south",
                "occurred_at": "1955-10-04",
                "raw_excerpt": "The object was observed between the train and the coast approximately fifty miles south.",
                "duplicate": {"duplicate_status": "new_event"},
            },
        ]
        hints = collect_relationship_hints(
            accepted,
            [_row("A.pdf", "incident_report", True), _row("B.pdf", "incident_report", True)],
            catalog={},
            texts={},
            thumbnails=set(),
        )
        self.assertFalse(any(h["relationship"] == "possible_same_event" for h in hints))

    def test_alarms_flag_without_failing_closed(self):
        docs = [
            {
                "filename": "EMPTY.pdf",
                "extraction_action": "extract",
                "candidates": 0,
                "accepted": 0,
                "quote_rejection_rate": 0,
                "page_count": 1,
                "ocr_failure_rate": 0,
            },
            {
                "filename": "MANY.pdf",
                "extraction_action": "extract",
                "candidates": 20,
                "accepted": 14,
                "quote_rejection_rate": 0.2,
                "page_count": 66,
                "ocr_failure_rate": 0.15,
            },
            {
                "filename": "QUOTES.pdf",
                "extraction_action": "extract",
                "candidates": 8,
                "accepted": 2,
                "quote_rejection_rate": 0.75,
                "page_count": 10,
                "ocr_failure_rate": 0.4,
            },
        ]
        alarms = review_alarms(docs, [], thumbnails=set())
        names = {(a["filename"], a["alarm"]) for a in alarms if "filename" in a}
        self.assertIn(("EMPTY.pdf", "extract_zero_candidates"), names)
        self.assertIn(("MANY.pdf", "high_yield"), names)
        self.assertIn(("QUOTES.pdf", "high_quote_rejection"), names)
        self.assertIn(("QUOTES.pdf", "high_ocr_failure"), names)
        self.assertTrue(all(a["needs_review"] for a in alarms))


if __name__ == "__main__":
    unittest.main()
