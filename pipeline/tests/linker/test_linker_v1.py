"""Canonical linker V1 regression tests. No API keys. No production writes."""

from __future__ import annotations

import unittest

from pipeline.linker.candidate_generation import generate_candidates
from pipeline.linker.intra_source_episode import group_episodes, episode_summary
from pipeline.linker.normalize import is_generic_location, specific_place_tokens
from pipeline.linker.relationship_rules import apply_rules
from pipeline.linker.run_v1 import load_catalog


def _inc(
    case_id: str,
    source: str,
    *,
    excerpt: str,
    title: str = "",
    location: str = "western United States",
    occurred_at: str | None = None,
) -> dict:
    return {
        "case_id": case_id,
        "source_filename": source,
        "raw_excerpt": excerpt,
        "title": title or case_id,
        "location_text": location,
        "occurred_at": occurred_at,
    }


def _row(filename: str, doc_class: str, contains: bool) -> dict:
    return {
        "filename": filename,
        "external_id": filename.replace(".pdf", ""),
        "extraction_action": "extract" if contains else "source_only",
        "classification": {"document_class": doc_class, "contains_incidents": contains},
    }


class NormalizeTests(unittest.TestCase):
    def test_generic_western_us_is_generic(self):
        self.assertTrue(is_generic_location("western United States"))
        self.assertTrue(is_generic_location("Western United States, near an airfield"))

    def test_cheyenne_is_specific(self):
        self.assertFalse(is_generic_location("Cheyenne Mountains"))
        self.assertIn("cheyenne", {t for t in specific_place_tokens("Cheyenne Mountains")})


class EpisodeGrouperTests(unittest.TestCase):
    def test_d082_style_phases_are_not_twelve_events(self):
        rows = [
            _inc("1", "DOW-UAP-D082.pdf", excerpt="In October 2023 just after sunset I saw a bright ball of light."),
            _inc("2", "DOW-UAP-D082.pdf", excerpt="After about 10 minutes I saw multiple bright orange lights/orbs."),
            _inc("3", "DOW-UAP-D082.pdf", excerpt="Later, I observed very bright orange lights that appeared to shoot out smaller lights."),
            _inc("4", "DOW-UAP-D082.pdf", excerpt="Soon thereafter I saw nine lights formed a horizontal line."),
            _inc("5", "DOW-UAP-D082.pdf", excerpt="The next day between 7-9pm I saw the same light phenomenon."),
            _inc("6", "DOW-UAP-D082.pdf", excerpt="Shortly thereafter, I saw one light source just above the ridgeline."),
            _inc("7", "DOW-UAP-D082.pdf", excerpt="Later in the night while stationary in a vehicle I watched a light source."),
            _inc("8", "DOW-UAP-D082.pdf", excerpt="At some point I saw a very bright white light appear just below a ridgeline."),
            _inc("9", "DOW-UAP-D082.pdf", excerpt="Later in the night between 1-3am I continued to see same distant lights."),
            _inc("10", "DOW-UAP-D082.pdf", excerpt="A few days later at around the same time after dusk I saw lights moving."),
            _inc("11", "DOW-UAP-D082.pdf", excerpt="The next day I saw at least four lights hovering and moving."),
            _inc("12", "DOW-UAP-D082.pdf", excerpt="Some months thereafter at around midnight I saw a yellow light."),
        ]
        episodes, decisions = group_episodes(rows)
        self.assertEqual(len(rows), 12)
        self.assertGreater(len(episodes), 1)
        self.assertLess(len(episodes), 12)
        # First four night-1 phases should consolidate
        self.assertGreaterEqual(len(episodes[0]), 3)
        boundaries = [d.boundary for d in decisions]
        self.assertIn("new_episode", boundaries)
        self.assertIn("same_episode", boundaries)

    def test_adjacency_alone_does_not_merge(self):
        rows = [
            _inc("a", "X.pdf", excerpt="I observed an object over the hangar at dusk."),
            _inc("b", "X.pdf", excerpt="Witnesses elsewhere reported a different fireball at dawn."),
        ]
        episodes, decisions = group_episodes(rows)
        self.assertEqual(len(episodes), 2)
        self.assertEqual(decisions[0].boundary, "uncertain_boundary")


class CandidateAndRuleTests(unittest.TestCase):
    def test_generic_location_does_not_create_place_candidate(self):
        incidents = [
            _inc("A", "DOW-UAP-D079.pdf", excerpt="I saw orange orbs.", location="western United States"),
            _inc("B", "DOW-UAP-D080.pdf", excerpt="I saw orange orbs too.", location="western United States"),
        ]
        classifications = [
            _row("DOW-UAP-D079.pdf", "incident_report", True),
            _row("DOW-UAP-D080.pdf", "incident_report", True),
        ]
        cands = generate_candidates(incidents=incidents, classifications=classifications, catalog={}, texts={})
        self.assertFalse(any(c["candidate_kind"] == "specific_place_overlap" for c in cands))

    def test_same_agency_year_uap_do_not_auto_merge(self):
        incidents = [
            _inc("A", "A.pdf", excerpt="UAP observed in 2023", location="western United States", occurred_at=None),
            _inc("B", "B.pdf", excerpt="UAP observed in 2023", location="western United States", occurred_at=None),
        ]
        classifications = [_row("A.pdf", "incident_report", True), _row("B.pdf", "incident_report", True)]
        cands = generate_candidates(incidents=incidents, classifications=classifications, catalog={}, texts={})
        payload = apply_rules(
            incidents=incidents,
            classifications=classifications,
            catalog={},
            candidates=cands,
            texts={},
        )
        auto_same = [
            d
            for d in payload["decisions"]
            if d["relationship"] == "same_event" and d["status"] == "auto_supported" and "intra-source" not in " ".join(d["evidence"])
        ]
        self.assertEqual(auto_same, [])
        self.assertTrue(any(d["status"] == "rejected" for d in payload["rejected_pairs"]))

    def test_excerpt_similarity_alone_is_not_auto_merge(self):
        excerpt = "Observed an unidentified object over the hangar for several minutes."
        incidents = [
            _inc("A", "A.pdf", excerpt=excerpt, location="Hangar Field Testville"),
            _inc("B", "B.pdf", excerpt=excerpt, location="Hangar Field Testville"),
        ]
        # Without catalog pairing / series / analysis evidence, similar excerpts must not auto_merge.
        payload = apply_rules(
            incidents=incidents,
            classifications=[_row("A.pdf", "incident_report", True), _row("B.pdf", "incident_report", True)],
            catalog={},
            candidates=[],
            texts={},
        )
        self.assertFalse(payload["auto_merged"])
        self.assertFalse(
            any(
                d["relationship"] == "same_event" and d["status"] == "auto_supported" and "intra-source" not in " ".join(d["evidence"])
                for d in payload["decisions"]
            )
        )

    def test_colorado_springs_fixture(self):
        incidents = [
            _inc(
                "UNDATED-USA-599D8B",
                "FBI-UAP-D002.pdf",
                excerpt="observed a UAP over the Cheyenne Mountains as they exited their office building.",
                location="Cheyenne Mountains",
                title="Colorado Springs interview",
            )
        ]
        classifications = [
            _row("FBI-UAP-D002.pdf", "transcript", True),
            _row("FBI-UAP-D003.pdf", "media_metadata", False),
            _row("ICA-UAP-D001.pdf", "analysis", False),
        ]
        catalog = {
            "FBI-UAP-D002": {"pdf_pairing": "", "title": "FBI-UAP-D002 Colorado Springs 2022"},
            "FBI-UAP-D003": {"pdf_pairing": "FBI-UAP-D002", "title": "FBI-UAP-D003 Digital Rendering Colorado Springs"},
            "ICA-UAP-D001": {"pdf_pairing": "", "title": "ICA-UAP-D001 Analysis Colorado Springs"},
        }
        texts = {
            "ICA-UAP-D001.pdf": "An airborne object over Cheyenne Mountain in February 2022 was possible backscattering.",
            "FBI-UAP-D003.pdf": "",
        }
        cands = generate_candidates(
            incidents=incidents,
            classifications=classifications,
            catalog=catalog,
            texts=texts,
        )
        payload = apply_rules(
            incidents=incidents,
            classifications=classifications,
            catalog=catalog,
            candidates=cands,
            texts=texts,
        )
        # Exactly one event for D002
        d002_events = {
            m["event_id"]
            for m in payload["event_members"]
            if m["source_filename"] == "FBI-UAP-D002.pdf"
        }
        self.assertEqual(len(d002_events), 1)
        event_id = next(iter(d002_events))
        media = [
            s
            for s in payload["event_sources"]
            if s["event_id"] == event_id and s["relationship"] == "media_for_event" and s["source_filename"] == "FBI-UAP-D003.pdf"
        ]
        analysis = [
            s
            for s in payload["event_sources"]
            if s["event_id"] == event_id
            and s["relationship"] == "analysis_of_event"
            and s["source_filename"] == "ICA-UAP-D001.pdf"
        ]
        self.assertEqual(len(media), 1)
        self.assertEqual(len(analysis), 1)
        self.assertFalse(payload["incidents_rewritten"])
        self.assertFalse(payload["auto_merged"])

    def test_western_series_without_same_event_collapse(self):
        incidents = [
            _inc("w1", "DOW-UAP-D079.pdf", excerpt="Night one: I saw orange orbs.", location="western United States"),
            _inc("w2", "DOW-UAP-D080.pdf", excerpt="Night one: I saw a bright object.", location="western United States"),
            _inc(
                "w3a",
                "DOW-UAP-D082.pdf",
                excerpt="In October 2023 after sunset I saw a bright ball of light.",
                location="western United States",
            ),
            _inc(
                "w3b",
                "DOW-UAP-D082.pdf",
                excerpt="After about 10 minutes I saw multiple orange orbs.",
                location="western United States",
            ),
            _inc(
                "w3c",
                "DOW-UAP-D082.pdf",
                excerpt="The next day between 7-9pm I saw the same light phenomenon.",
                location="western United States",
            ),
        ]
        classifications = [
            _row("DOW-UAP-D078.pdf", "incident_report", True),
            _row("DOW-UAP-D079.pdf", "incident_report", True),
            _row("DOW-UAP-D080.pdf", "incident_report", True),
            _row("DOW-UAP-D082.pdf", "incident_report", True),
        ]
        catalog = {
            "DOW-UAP-D078": {"pdf_pairing": "Western US Event", "title": "DOW-UAP-D078 Notional Map Western United States Event"},
            "DOW-UAP-D079": {"pdf_pairing": "Western US Event", "title": "DOW-UAP-D079 Narrative 1 Western United States Event"},
            "DOW-UAP-D080": {"pdf_pairing": "Western US Event", "title": "DOW-UAP-D080 Narrative 2 Western United States Event"},
            "DOW-UAP-D082": {"pdf_pairing": "Western US Event", "title": "DOW-UAP-D082 Narrative 4 Western United States Event"},
        }
        cands = generate_candidates(
            incidents=incidents,
            classifications=classifications,
            catalog=catalog,
            texts={},
        )
        payload = apply_rules(
            incidents=incidents,
            classifications=classifications,
            catalog=catalog,
            candidates=cands,
            texts={},
        )
        self.assertTrue(payload["event_series"])
        series = payload["event_series"][0]
        self.assertGreaterEqual(len(series["event_ids"]), 2)
        # D082 should have more than one episode event
        d082_events = {
            m["event_id"] for m in payload["event_members"] if m["source_filename"] == "DOW-UAP-D082.pdf"
        }
        self.assertGreaterEqual(len(d082_events), 2)
        # No cross-file same_event auto_supported from generic location
        cross = [
            d
            for d in payload["decisions"]
            if d["relationship"] == "same_event"
            and d["status"] == "auto_supported"
            and "intra-source" not in " ".join(d["evidence"]).lower()
        ]
        self.assertEqual(cross, [])
        self.assertTrue(any(d["relationship"] == "same_series" for d in payload["decisions"]))

    def test_spaced_caption_does_not_join_western_series(self):
        incidents = [
            _inc("p1", "FBI-UAP-D001.pdf", excerpt="A light was observed.", location="Quantico"),
            _inc("w1", "DOW-UAP-D079.pdf", excerpt="Night one: I saw orange orbs.", location="western United States"),
        ]
        classifications = [
            _row("FBI-UAP-D001.pdf", "incident_report", True),
            _row("DOW-UAP-D079.pdf", "incident_report", True),
        ]
        catalog = {
            "FBI-UAP-D001": {"pdf_pairing": "FBI Photo A001", "title": "FBI-UAP-D001"},
            "DOW-UAP-D079": {"pdf_pairing": "Western US Event", "title": "DOW-UAP-D079 Western United States Event"},
        }
        cands = generate_candidates(
            incidents=incidents,
            classifications=classifications,
            catalog=catalog,
            texts={},
        )
        payload = apply_rules(
            incidents=incidents,
            classifications=classifications,
            catalog=catalog,
            candidates=cands,
            texts={},
        )
        series = payload["event_series"]
        self.assertEqual(len(series), 1)
        self.assertEqual(series[0]["series_id"], "western-us-event-2023")
        self.assertNotIn("FBI Photo", series[0]["label"])
        fbi_events = {
            m["event_id"] for m in payload["event_members"] if m["source_filename"] == "FBI-UAP-D001.pdf"
        }
        self.assertTrue(fbi_events.isdisjoint(set(series[0]["event_ids"])))

    def test_duplicate_external_id_keeps_pdf_catalog_row(self):
        catalog = load_catalog()
        row = catalog["FBI-UAP-D014"]
        self.assertEqual(row["type"], "PDF")
        self.assertNotIn("western us event", (row.get("pdf_pairing") or "").lower())
        alts = row.get("alternate_assets") or []
        self.assertTrue(any(a.get("type") == "IMG" for a in alts))


if __name__ == "__main__":
    unittest.main()
