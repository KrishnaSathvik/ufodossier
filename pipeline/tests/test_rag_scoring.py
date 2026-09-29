import unittest

from pipeline.evals.rag.scoring import score_answer


def _score(answer: str, *, hedge: bool = False, evidence: str = "", forbidden: list[str] | None = None) -> dict:
    question = {
        "id": "q-test",
        "expect": {
            "must_cite_any_of": ["UNDATED-CIA-6E72CA"],
            "require_hedge": hedge,
            "forbidden_phrases": forbidden or [],
        },
    }
    return score_answer(
        question,
        answer,
        ["UNDATED-CIA-6E72CA"],
        evidence_text=evidence,
    )


class ScoringTests(unittest.TestCase):
    def test_said_is_an_acceptable_attribution_paraphrase(self):
        score = _score(
            "The source said they saw a bright green circular object [UNDATED-CIA-6E72CA].",
            hedge=True,
            evidence="Source observed an unidentified green circular object.",
        )
        self.assertEqual(score["evidence_status"], "SUPPORTED_WITH_ACCEPTABLE_PARAPHRASE")
        self.assertTrue(score["grounded"])
        self.assertTrue(score["epistemic_fidelity"])
        self.assertFalse(score["hedge_ok"])

    def test_record_says_is_not_a_grounding_failure(self):
        score = _score(
            "The record says the target pulled away. Its identity was not resolved [UNDATED-CIA-6E72CA].",
            hedge=True,
            evidence="The range tracked a high-speed target. Resolution: unresolved.",
        )
        self.assertEqual(score["evidence_status"], "SUPPORTED_WITH_ACCEPTABLE_PARAPHRASE")
        self.assertTrue(score["epistemic_fidelity"])

    def test_reported_stays_supported(self):
        score = _score(
            "The witness reported a green object [UNDATED-CIA-6E72CA].",
            hedge=True,
            evidence="The witness reported a green object.",
        )
        self.assertEqual(score["evidence_status"], "SUPPORTED")
        self.assertTrue(score["hedge_ok"])

    def test_proved_without_evidence_is_overstated(self):
        score = _score(
            "A green extraterrestrial craft was proved [UNDATED-CIA-6E72CA].",
            hedge=True,
            evidence="Source observed an unidentified green circular object.",
        )
        self.assertEqual(score["evidence_status"], "OVERSTATED")
        self.assertFalse(score["grounded"])
        self.assertFalse(score["epistemic_fidelity"])
        self.assertIn("proved", score["certainty_inflation"])

    def test_negated_proof_is_not_inflation(self):
        score = _score(
            "No document proves recovered alien bodies [UNDATED-CIA-6E72CA].",
            evidence="A witness reported a claim.",
            forbidden=["recovered alien bodies"],
        )
        self.assertEqual(score["unsupported_claims"], 0)
        self.assertEqual(score["certainty_inflation"], [])
        self.assertEqual(score["evidence_status"], "SUPPORTED")

    def test_rather_than_established_is_not_inflation(self):
        score = _score(
            "Each record is a claim rather than established proof [UNDATED-CIA-6E72CA].",
            evidence="A witness reported a claim.",
        )
        self.assertEqual(score["certainty_inflation"], [])
        self.assertEqual(score["evidence_status"], "SUPPORTED")

    def test_certainty_word_in_the_evidence_is_allowed(self):
        score = _score(
            "The astronomer confirmed observing a peculiar object [UNDATED-CIA-6E72CA].",
            evidence="The astronomer confirmed observing a peculiar object.",
        )
        self.assertEqual(score["certainty_inflation"], [])
        self.assertTrue(score["epistemic_fidelity"])
