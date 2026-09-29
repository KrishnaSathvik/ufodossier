"""Page router: index slips skip, narrative memos group, press clippings skip."""

from __future__ import annotations

import unittest

from pipeline.section_router import diagnose_text, select_chunks

SAMPLE = """--- PAGE 1 ---
INDICES SEARCH SLIP
TO CHIEF CLERK
Exact Spelling
Subversive References
FILE AND SERIAL NO. REMARKS. Searched by clerk. References reviewed by agent on this slip.

--- PAGE 2 ---
UNITED STATES GOVERNMENT
Office Memorandum
TO: SAC, NEWARK DATE: 11/15/57
On the afternoon of November 5, 1957 they observed a long cylindrical dark silver object with no wings but fins on the rear, moving toward the northeast over Glen Ridge.

--- PAGE 3 ---
Official Journal of the Amalgamated Flying Saucer Clubs of America.
New York Times coverage of the national convention.
"""


class SectionRouterTests(unittest.TestCase):
    def test_routes_index_narrative_and_press(self):
        signals = diagnose_text(SAMPLE)
        routes = {s.page: s.route for s in signals}
        self.assertEqual(routes[1], "skip_routing")
        self.assertEqual(routes[2], "narrative")
        self.assertEqual(routes[3], "skip_press")
        page2 = next(s for s in signals if s.page == 2)
        self.assertGreater(page2.incident_cue_score, 0)
        self.assertGreater(page2.date_location_cues, 0)
        self.assertGreater(page2.narrative_likelihood, page2.routing_index_likelihood)

    def test_cue_routed_keeps_only_narrative(self):
        strategy, chunks = select_chunks(SAMPLE, strategy="cue_routed")
        self.assertEqual(strategy, "cue_routed")
        self.assertEqual(len(chunks), 1)
        self.assertIn("cylindrical dark silver object", chunks[0])
        self.assertNotIn("CHIEF CLERK", chunks[0])
        self.assertNotIn("Flying Saucer Clubs", chunks[0])

    def test_auto_stays_fixed_on_short_text(self):
        strategy, chunks = select_chunks(SAMPLE, strategy="auto")
        self.assertEqual(strategy, "fixed")
        self.assertEqual(len(chunks), 1)

    def test_auto_cue_routes_large_mixed_file(self):
        parts = []
        for i in range(1, 18):
            if i <= 5:
                body = "INDICES SEARCH SLIP TO CHIEF CLERK Exact Spelling " * 30
            else:
                body = (
                    "UNITED STATES GOVERNMENT Office Memorandum dated November 5, 1957. "
                    "The witness observed a silver flying object over Newark. "
                ) * 80
            parts.append(f"--- PAGE {i} ---\n{body}")
        text = "\n\n".join(parts)
        self.assertGreater(len(text), 60_000)
        strategy, chunks = select_chunks(text, strategy="auto")
        self.assertEqual(strategy, "cue_routed")
        self.assertGreaterEqual(len(chunks), 1)
        joined = "\n".join(chunks)
        self.assertIn("silver flying object", joined)
        self.assertNotIn("CHIEF CLERK", joined)


if __name__ == "__main__":
    unittest.main()
