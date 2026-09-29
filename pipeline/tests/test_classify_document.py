"""Unit tests for deterministic document classifier (no network, no DB)."""

from __future__ import annotations

import unittest

from pipeline.classify_document import classify_text


class ClassifierTests(unittest.TestCase):
    def test_incident_report(self):
        c = classify_text(
            title="DOW-UAP Mission Report Iraq 2022",
            filename="DOW-UAP-D106.pdf",
            text="US AIRCRAFT OBSERVED 1X POSS UAP FOR 23 SECONDS. Mission report follows.",
        )
        self.assertEqual(c.document_class, "incident_report")
        self.assertTrue(c.contains_incidents)

    def test_historical_case_file(self):
        c = classify_text(
            title="Project Blue Book Case File Tremonton 1952",
            filename="DOW-UAP-D102.pdf",
            text="HEADQUARTERS DETACHMENT special reporting group. Security inspection of sightings.",
        )
        self.assertEqual(c.document_class, "historical_case_file")
        self.assertTrue(c.contains_incidents)

    def test_contract(self):
        c = classify_text(
            title="AAWSAP Contract HHM402-08-C-0072",
            filename="DOW-UAP-D111.pdf",
            text="This solicitation and contract modification P00001 awards Bigelow Aerospace Advanced Space Studies.",
        )
        self.assertEqual(c.document_class, "contract")
        self.assertFalse(c.contains_incidents)

    def test_research_paper(self):
        c = classify_text(
            title="DIRD Warp Drive Metrics",
            filename="DOW-UAP-D132.pdf",
            text="Defense Intelligence Reference Document on traversable wormholes and negative-mass propulsion.",
        )
        self.assertEqual(c.document_class, "research_paper")
        self.assertFalse(c.contains_incidents)

    def test_administrative_invitation(self):
        c = classify_text(
            title="Pajarito Astronomers Invitation",
            filename="DOE-UAP-D003.pdf",
            text="Dear Members, You are invited to the next club meeting. Agenda and membership dues enclosed.",
        )
        self.assertEqual(c.document_class, "administrative")
        self.assertFalse(c.contains_incidents)

    def test_correspondence_with_sighting(self):
        c = classify_text(
            title="James Tuck Correspondence",
            filename="DOE-UAP-D002.pdf",
            text="Dear Sir, I write regarding an unidentified aerial sighting observed near the laboratory.",
        )
        self.assertEqual(c.document_class, "correspondence")
        self.assertTrue(c.contains_incidents)

    def test_catalog_referral_correspondence_is_source_only(self):
        c = classify_text(
            title="Congressional UFO correspondence",
            filename="USG-UAP-D001.pdf",
            text=(
                "INCOMING CORRESPONDENCE ACTION. Senator Snowe forwards letter from a constituent "
                "requesting information on UFO sightings by astronauts. "
                "Dear Senator, Thank you for your letter on behalf of the constituent. "
                "Most objects sighted were later identified."
            ),
        )
        self.assertEqual(c.document_class, "correspondence")
        self.assertFalse(c.contains_incidents)

    def test_correspondence_with_firsthand_encounter(self):
        c = classify_text(
            title="Letter to Hoover",
            filename="FBI-UAP-D011.pdf",
            text=(
                "Dear Mr. Hoover: Last May one afternoon I saw four beams in the sky "
                "passing from the northwest and converging in the mountains."
            ),
        )
        self.assertEqual(c.document_class, "correspondence")
        self.assertTrue(c.contains_incidents)

    def test_invitation_of_a_host_is_not_administrative(self):
        c = classify_text(
            title="Sighting of Unconventional Aircraft",
            filename="CIA-UAP-006.pdf",
            text=(
                "Sighting of Unconventional Aircraft. He visited at the invitation of a senior official. "
                "I just saw a flying saucer. We all saw a triangular object launched from the airfield."
            ),
        )
        self.assertNotEqual(c.document_class, "administrative")
        self.assertTrue(c.contains_incidents)

    def test_analyst_note_is_analysis_source_only(self):
        c = classify_text(
            title="Colorado Springs assessment",
            filename="ICA-UAP-D001.pdf",
            text=(
                "An airborne object over Cheyenne Mountain was observed by five service members. "
                "Analyst Note: backscattering of sunlight. Has low confidence in this assessment."
            ),
        )
        self.assertEqual(c.document_class, "analysis")
        self.assertFalse(c.contains_incidents)

    def test_large_single_page_image_is_media(self):
        c = classify_text(
            title="Digital rendering",
            filename="FBI-UAP-D003.pdf",
            text="~~ yy noise miler",
            page_count=1,
            byte_size=3_400_000,
        )
        self.assertEqual(c.document_class, "media_metadata")
        self.assertFalse(c.contains_incidents)

    def test_correspondence_topic_only_no_incident(self):
        c = classify_text(
            title="Recipe Request",
            filename="DOE-UAP-D002.pdf",
            text="Dear Sir, We are interested in atmospheric vortices reported in the book "
            "Scientific Study of Unidentified Flying Objects. Yours sincerely,",
        )
        self.assertEqual(c.document_class, "correspondence")
        self.assertFalse(c.contains_incidents)


if __name__ == "__main__":
    unittest.main()
