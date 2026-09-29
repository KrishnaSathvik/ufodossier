import json
import unittest
from pathlib import Path

from pipeline.evals.rag.citations import validate_citations
from pipeline.evals.rag.schemas import assert_question_set

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "pipeline/evals/rag/questions.json"


class CitationTests(unittest.TestCase):
    def test_accepts_retrieved_id(self):
        result = validate_citations("A witness reported a film [1952-USN-80203D].", ["1952-USN-80203D"])
        self.assertTrue(result["ok"])
        self.assertEqual(result["invalid"], [])

    def test_rejects_id_outside_retrieval(self):
        result = validate_citations("See [1952-USN-80203D].", ["1949-USAF-9D1046"])
        self.assertFalse(result["ok"])
        self.assertIn("1952-USN-80203D", result["invalid"])

    def test_rejects_flagged_id(self):
        result = validate_citations("See [1947-FBI-AAAA].", ["1947-FBI-AAAA"], excluded_case_ids=["1947-FBI-AAAA"])
        self.assertIn("excluded or flagged", result["reasons"][0])

    def test_rejects_source_only_id(self):
        result = validate_citations("The contract [DOW-UAP-D110] is an incident.", [], source_only_ids=["DOW-UAP-D110"])
        self.assertFalse(result["ok"])
        self.assertIn("source-only", result["reasons"][0])

    def test_leaves_the_answer_text_unchanged(self):
        answer = "Invented detail [NOT-A-REAL-CASE]."
        result = validate_citations(answer, ["1952-USN-80203D"])
        self.assertIn("NOT-A-REAL-CASE", result["invalid"])
        self.assertIn("[NOT-A-REAL-CASE]", answer)

    def test_frozen_question_distribution(self):
        questions = json.loads(QUESTIONS.read_text())
        assert_question_set(questions)


if __name__ == "__main__":
    unittest.main()
