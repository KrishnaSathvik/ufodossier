"""Frozen eval question checks. Distribution is part of the contract."""

from __future__ import annotations

REQUIRED_CATEGORIES = {
    "direct_factual": 15,
    "metadata": 10,
    "synthesis": 15,
    "historical": 10,
    "abstention": 10,
}


def assert_question_set(questions: list[dict]) -> None:
    if len(questions) != 60:
        raise AssertionError(f"expected 60 frozen questions, found {len(questions)}")
    counts: dict[str, int] = {}
    ids: set[str] = set()
    for question in questions:
        category = question["category"]
        counts[category] = counts.get(category, 0) + 1
        if question["id"] in ids:
            raise AssertionError(f"duplicate id {question['id']}")
        ids.add(question["id"])
        if not question.get("question"):
            raise AssertionError(f"{question['id']} has no question text")
    if counts != REQUIRED_CATEGORIES:
        raise AssertionError(f"category counts {counts} != {REQUIRED_CATEGORIES}")
