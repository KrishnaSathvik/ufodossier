"""Deterministic scoring for one answer against a frozen question and evidence pack."""

from __future__ import annotations

import re

from pipeline.evals.rag.citations import validate_citations

ABSTAIN_MARKERS = (
    "does not establish",
    "do not establish",
    "does not contain",
    "do not contain",
    "not establish",
    "no record",
    "cannot produce",
    "does not prove",
    "do not prove",
    "not proven",
    "does not answer",
    "archive does not",
    "records do not",
    "no evidence in",
    "not supported",
)

# Legacy lexical list. Kept so the old miss can be shown. It is not the grounding score.
HEDGE_MARKERS = (
    "reported",
    "alleged",
    "described",
    "according to",
    "appeared",
    "possible",
    "unresolved",
    "assessed",
    "witness",
)

# Attribution paraphrases. These preserve "this is a report" without copying one verb.
ATTRIBUTION_MARKERS = (
    "reported",
    "said",
    "says",
    "stated",
    "described",
    "describes",
    "describe",
    "recounted",
    "according to",
    "told",
    "wrote",
    "alleged",
    "assessed",
    "appeared",
    "observed",
    "observation",
    "witness",
    "record says",
    "the record",
    "unresolved",
    "unidentified",
    "could not",
    "does not",
)

CERTAINTY_WORDS = (
    "proved",
    "proves",
    "proven",
    "confirmed",
    "confirms",
    "demonstrated",
    "conclusively",
    "definitely",
    "verified",
    "established",
)

CERTAINTY_LEMMA = {
    "proved": "prove",
    "proves": "prove",
    "proven": "prove",
    "confirmed": "confirm",
    "confirms": "confirm",
    "demonstrated": "demonstrate",
    "conclusively": "conclusively",
    "definitely": "definitely",
    "verified": "verify",
    "established": "establish",
}


def score_answer(
    question: dict,
    answer: str,
    retrieved_case_ids: list[str],
    *,
    source_only_ids: list[str] | None = None,
    series_event_count: int | None = None,
    evidence_text: str = "",
) -> dict:
    text = answer or ""
    lowered = text.lower()
    citation = validate_citations(text, retrieved_case_ids, source_only_ids=source_only_ids or [])
    expected = question.get("expect") or {}
    must_cite = [item.upper() for item in expected.get("must_cite_any_of") or []]
    retrieved = {item.upper() for item in retrieved_case_ids}
    retrieval_has_expected = (not must_cite) or bool(retrieved.intersection(must_cite))
    retrieval_failure = ((not retrieved) or (bool(must_cite) and not retrieval_has_expected)) and not expected.get("must_abstain")
    if expected.get("series_not_one_event") and series_event_count is None:
        retrieval_failure = True

    fake = len(citation["invalid"])
    outside = fake
    cited_known = [item for item in citation["cited"] if item in retrieved]
    precision = (len(cited_known) / len(citation["cited"])) if citation["cited"] else (1.0 if not must_cite else 0.0)
    recall = 1.0
    if must_cite and retrieval_has_expected:
        recall = 1.0 if any(item in cited_known for item in must_cite) else 0.0

    unsupported = _unsupported_claims(lowered, expected)
    abstain_ok = True
    if expected.get("must_abstain"):
        abstain_ok = _abstains(lowered) and not unsupported and fake == 0

    mention_ok = True
    for term in expected.get("must_mention") or []:
        if term.lower() not in lowered:
            mention_ok = False
    mention_any = expected.get("must_mention_any") or []
    if mention_any and not any(term.lower() in lowered for term in mention_any):
        mention_ok = False

    canonical_ok = None
    if expected.get("series_not_one_event") or expected.get("media_not_separate_incident"):
        canonical_ok = True
        if expected.get("series_not_one_event"):
            canonical_ok = _series_language(lowered, series_event_count)
        if expected.get("media_not_separate_incident"):
            canonical_ok = canonical_ok and _media_not_separate(lowered)

    lexical_hedge = any(marker in lowered for marker in HEDGE_MARKERS)
    hedge_ok = True if not expected.get("require_hedge") else lexical_hedge
    attributed = any(marker in lowered for marker in ATTRIBUTION_MARKERS)
    inflation = _certainty_inflation(lowered, (evidence_text or "").lower())
    if unsupported:
        evidence_status = "UNSUPPORTED"
    elif inflation:
        evidence_status = "OVERSTATED"
    elif expected.get("require_hedge") and attributed and not lexical_hedge:
        evidence_status = "SUPPORTED_WITH_ACCEPTABLE_PARAPHRASE"
    else:
        evidence_status = "SUPPORTED"
    semantic_grounded = evidence_status in {"SUPPORTED", "SUPPORTED_WITH_ACCEPTABLE_PARAPHRASE"}
    epistemic_ok = not inflation and (attributed if expected.get("require_hedge") else True)
    if retrieval_failure and not expected.get("must_abstain"):
        semantic_grounded = None
        evidence_status = None

    return {
        "retrieval_failure": retrieval_failure and not expected.get("must_abstain"),
        "fake_citations": fake,
        "citations_outside_retrieval": outside,
        "unsupported_claims": len(unsupported),
        "unsupported_examples": unsupported,
        "abstention_correct": abstain_ok if expected.get("must_abstain") else None,
        "citation_precision": precision,
        "citation_recall": None if retrieval_failure else recall,
        "canonical_correct": canonical_ok,
        "completeness": mention_ok,
        "grounded": semantic_grounded,
        "evidence_status": evidence_status,
        "epistemic_fidelity": epistemic_ok,
        "certainty_inflation": inflation,
        "hedge_ok": hedge_ok,
        "cited": citation["cited"],
        "invalid": citation["invalid"],
    }


def _certainty_inflation(answer: str, evidence: str) -> list[str]:
    """Strong certainty that the retrieved evidence does not itself assert."""
    evidence_lemmas = {item[0] for item in _certainty_hits(evidence)}
    extra = []
    for lemma, word in _certainty_hits(answer):
        if lemma not in evidence_lemmas and word not in extra:
            extra.append(word)
    return extra


def _certainty_hits(text: str) -> list[tuple[str, str]]:
    hits = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if _sentence_negated(sentence):
            continue
        if re.search(r"\bonly\s+confirms?\b", sentence):
            continue
        for word in CERTAINTY_WORDS:
            if re.search(rf"\b{word}\b", sentence):
                hits.append((CERTAINTY_LEMMA[word], word))
    return hits


def _sentence_negated(sentence: str) -> bool:
    return bool(
        re.search(
            r"\b(not|no|never|without|cannot|can't|doesn't|does not|do not|none|nothing|nor)\b|rather than|instead of|short of|far from",
            sentence,
        )
    )


def _unsupported_claims(lowered: str, expected: dict) -> list[str]:
    hits = []
    for phrase in expected.get("forbidden_phrases") or []:
        if phrase.lower() in lowered and not _negated(lowered, phrase.lower()):
            hits.append(phrase)
    return hits


def _negated(lowered: str, phrase: str) -> bool:
    index = lowered.find(phrase.lower())
    if index < 0:
        return False
    start = lowered.rfind(".", 0, index)
    sentence = lowered[0 if start < 0 else start + 1 : index]
    return bool(
        re.search(
            r"\b(not|no|never|without|cannot|can't|doesn't|does not|do not|none|nothing)\b",
            sentence,
        )
    )


def _abstains(lowered: str) -> bool:
    if any(marker in lowered for marker in ABSTAIN_MARKERS):
        return True
    return bool(
        re.search(
            r"\b(no|none|nothing|not|does not|do not)\b",
            lowered[:500],
        )
    )


def _series_language(lowered: str, count: int | None) -> bool:
    if count is not None and str(count) not in lowered:
        return False
    if "series" not in lowered and "separate" not in lowered:
        return False
    if re.search(r"\b(one|single|a)\s+(giant\s+)?(uap\s+)?event\b", lowered) and "not" not in lowered and "series" not in lowered:
        return False
    return True


def _media_not_separate(lowered: str) -> bool:
    return any(
        phrase in lowered
        for phrase in (
            "not a separate incident",
            "not a separate event",
            "same event",
            "media for",
            "not its own incident",
        )
    )
