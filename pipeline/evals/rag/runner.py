"""Local RAG model comparison.

Retrieval for this run is a frozen lexical pack plus linker context, identical
for every model. It does not change match_incidents, embeddings, or top-k on
the production Ask path.

Usage:
  python -m pipeline.evals.rag.runner
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from pipeline.evals.rag.schemas import assert_question_set
from pipeline.evals.rag.scoring import score_answer

ROOT = Path(__file__).resolve().parents[3]
EVAL_DIR = Path(__file__).resolve().parent
RESULTS = EVAL_DIR / "results"
QUESTIONS = EVAL_DIR / "questions.json"

ARMS = [
    {"id": "sonnet-4.5", "provider": "anthropic", "model": "claude-sonnet-4-5-20250929"},
    {"id": "sonnet-5.5", "provider": "anthropic", "model": "claude-sonnet-5-5"},
    {"id": "gpt-6-sol-low", "provider": "openai", "model": "gpt-6-sol", "reasoning_effort": "low"},
    {"id": "gpt-6-sol-medium", "provider": "openai", "model": "gpt-6-sol", "reasoning_effort": "medium"},
]

RATES = {
    "claude-sonnet-4-5-20250929": (3.0, 15.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    # OpenAI standard short-context rate, published on the GPT-6 Sol model page.
    "gpt-6-sol": (2.0, 10.0),
}

STOP = {
    "the", "and", "for", "with", "that", "this", "from", "what", "which", "about",
    "does", "did", "are", "was", "were", "have", "has", "into", "over", "under",
    "archive", "records", "record", "government", "contain", "contains", "these",
    "files", "file", "material",
}


def load_env() -> dict[str, str]:
    env = dict(os.environ)
    for path in (ROOT / "pipeline" / ".env", ROOT / "web" / ".env.local"):
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return env


def system_prompt() -> str:
    text = (ROOT / "web/src/lib/rag/prompt.ts").read_text()
    match = re.search(r"export const RAG_SYSTEM_PROMPT = `([\s\S]*?)`;", text)
    if not match:
        raise RuntimeError("RAG_SYSTEM_PROMPT missing from prompt.ts")
    return match.group(1)


def load_fragments() -> list[dict]:
    files = [
        "pipeline/reports/r2_smoke/extractions.json",
        "pipeline/reports/r3_full/extractions.json",
        "pipeline/reports/r4_local/extractions.json",
        "pipeline/reports/r5_local/extractions.json",
        "pipeline/reports/r6_local/extractions.json",
    ]
    rows = []
    seen = set()
    for file in files:
        payload = json.loads((ROOT / file).read_text())
        for incident in payload.get("validated_incidents") or []:
            case_id = incident.get("case_id")
            if not case_id or case_id in seen:
                continue
            seen.add(case_id)
            rows.append(incident)
    return rows


def load_production_fragments(env: dict[str, str]) -> list[dict]:
    url = env.get("SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_KEY")
    if not url or not key:
        return []
    request = urllib.request.Request(
        f"{url}/rest/v1/incidents?flagged=eq.false&select=case_id,title,summary,raw_excerpt,occurred_at,location_text,branch,resolution_status,slug",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Range": "0-999"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode())
    return payload


def load_graph() -> dict:
    return json.loads((ROOT / "pipeline/reports/corpus_qa/linker/full_graph.json").read_text())


def source_only_ids() -> list[str]:
    coverage = json.loads((ROOT / "pipeline/reports/corpus_qa/source_coverage.json").read_text())
    return [row["external_id"] for row in coverage["records"] if row.get("external_id") and (row.get("accepted_incident_count") or 0) == 0]


def tokenize(question: str) -> list[str]:
    return [tok for tok in re.split(r"[^a-z0-9]+", question.lower()) if len(tok) > 2 and tok not in STOP]


def identity_for(case_id: str, graph: dict, events_by_case: dict, series_by_event: dict) -> dict | None:
    event = events_by_case.get(case_id.upper())
    if not event:
        return None
    series = series_by_event.get(event["event_id"])
    return {"event": event, "series": series}


def format_fragment(incident: dict, identity: dict | None) -> str:
    lines = [
        f"CASE {incident.get('case_id')}",
        f"Title: {incident.get('title')}",
        f"Date: {incident.get('occurred_at') or 'undated'}",
        f"Location: {incident.get('location_text') or 'not stated'}",
        f"Agency or branch: {incident.get('branch') or 'not stated'}",
        f"Resolution recorded on the fragment: {incident.get('resolution_status') or 'not stated'}",
        f"Summary: {incident.get('summary')}",
        f"Verbatim excerpt: \"{incident.get('raw_excerpt')}\"",
    ]
    if identity and identity.get("event"):
        event = identity["event"]
        roles = "; ".join(f"{role['filename']} ({role['role']})" for role in event.get("source_roles") or [])
        lines.append(f"Canonical event: {event['event_id']} — {event['label']}")
        lines.append(f"Fragments in this event: {', '.join(event.get('member_case_ids') or [])}")
        lines.append(f"Source relationships: {roles or 'none listed'}")
        series = identity.get("series")
        if series:
            lines.append(
                f"Event series: {series['series_id']} ({series['label']}), {len(series['event_ids'])} canonical events. This is a series, not one event."
            )
    return "\n".join(lines)


def series_matches(question: str, graph: dict) -> list[dict]:
    lowered = question.lower()
    found = []
    for series in graph.get("event_series") or []:
        series_id = series["series_id"].lower()
        if "western" in lowered and "2023" in lowered and "western" in series_id and "2023" in series_id:
            found.append(series)
    return found


def fragment_score(incident: dict, tokens: list[str]) -> int:
    hay = " ".join(
        str(incident.get(field) or "")
        for field in (
            "title",
            "summary",
            "raw_excerpt",
            "location_text",
            "case_id",
            "branch",
            "source_filename",
            "source_external_id",
            "reporting_unit",
        )
    ).lower()
    score = sum(2 if len(tok) > 4 else 1 for tok in tokens if tok in hay)
    unit = str(incident.get("reporting_unit") or "").lower()
    if any(tok in unit for tok in tokens if len(tok) > 4):
        score += 6
    return score


def matching_events(question: str, graph: dict) -> list[dict]:
    tokens = [tok for tok in tokenize(question) if len(tok) > 3]
    ranked = []
    for event in graph.get("canonical_events") or []:
        label = f"{event.get('label') or ''} {event.get('location_text') or ''}".lower()
        overlap = [tok for tok in tokens if tok in label]
        if len(overlap) >= 2:
            ranked.append((len(overlap), event))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return [event for _, event in ranked[:3]]


def build_pack(question: dict, fragments: list[dict], graph: dict, events_by_case: dict, series_by_event: dict) -> dict:
    tokens = tokenize(question["question"])
    by_case = {incident["case_id"].upper(): incident for incident in fragments}
    chosen: list[dict] = []
    chosen_ids: set[str] = set()

    def add(incident: dict | None) -> None:
        if not incident:
            return
        case_id = str(incident.get("case_id") or "").upper()
        if not case_id or case_id in chosen_ids or len(chosen) >= 8:
            return
        chosen.append(incident)
        chosen_ids.add(case_id)

    for event in matching_events(question["question"], graph):
        for case_id in event.get("member_case_ids") or []:
            add(by_case.get(case_id.upper()))

    scored = sorted(
        ((fragment_score(incident, tokens), incident) for incident in fragments),
        key=lambda item: item[0],
        reverse=True,
    )
    for score, incident in scored:
        if score <= 0:
            break
        add(incident)

    series_count = None
    series_blocks = []
    series_member_ids: list[str] = []
    for series in series_matches(question["question"], graph):
        series_count = len(series["event_ids"])
        member_ids = []
        for event_id in series["event_ids"]:
            event = next((item for item in graph["canonical_events"] if item["event_id"] == event_id), None)
            if not event:
                continue
            member_ids.extend(event.get("member_case_ids") or [])
            series_member_ids.extend(event.get("member_case_ids") or [])
            for case_id in event.get("member_case_ids") or []:
                add(by_case.get(case_id.upper()))
        series_blocks.append(
            "\n".join(
                [
                    f"Series {series['series_id']}: {series['label']}",
                    f"Canonical events in the series: {series_count}",
                    "Treat this as separate events grouped as a series. Do not describe the series as one UAP event.",
                    "Member case IDs: " + ", ".join(member_ids),
                ]
            )
        )

    blocks = []
    allowed = []
    for incident in chosen:
        case_id = incident["case_id"]
        allowed.append(case_id)
        identity = identity_for(case_id, graph, events_by_case, series_by_event)
        if identity and identity.get("series") and not series_matches(question["question"], graph):
            identity = {**identity, "series": None}
        blocks.append(format_fragment(incident, identity))

    evidence = "\n\n---\n\n".join(blocks)
    if series_blocks:
        evidence = (evidence + "\n\n" if evidence else "") + "EVENT SERIES IN THIS EVIDENCE:\n" + "\n\n".join(series_blocks)
    if not evidence:
        evidence = "NO MATCHING ARCHIVE EVIDENCE WAS RETRIEVED."
    user = f"QUESTION:\n{question['question']}\n\nARCHIVE EVIDENCE:\n{evidence}\n\nAnswer using only this evidence. Cite case IDs inline."
    return {
        "question_id": question["id"],
        "case_ids": list(dict.fromkeys([*allowed, *series_member_ids])),
        "series_event_count": series_count,
        "user": user,
    }


def call_anthropic(env: dict[str, str], model: str, system: str, user: str) -> dict:
    body = json.dumps(
        {"model": model, "max_tokens": 1024, "system": system, "messages": [{"role": "user", "content": user}]}
    ).encode()
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": env["ANTHROPIC_API_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    started = time.time()
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode())
    text = "".join(block.get("text", "") for block in payload.get("content", []) if block.get("type") == "text")
    usage = payload.get("usage") or {}
    return {
        "text": text,
        "model": payload.get("model") or model,
        "latency_ms": int((time.time() - started) * 1000),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("thinking_tokens"),
    }


def call_openai(env: dict[str, str], model: str, effort: str, system: str, user: str) -> dict:
    body = json.dumps(
        {
            "model": model,
            "instructions": system,
            "input": user,
            "reasoning": {"effort": effort},
            "max_output_tokens": 1024,
        }
    ).encode()
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={"Authorization": f"Bearer {env['OPENAI_API_KEY']}", "content-type": "application/json"},
    )
    started = time.time()
    with urllib.request.urlopen(request, timeout=180) as response:
        payload = json.loads(response.read().decode())
    text = payload.get("output_text") or ""
    if not text:
        chunks = []
        for item in payload.get("output") or []:
            for content in item.get("content") or []:
                if content.get("type") in {"output_text", "text"}:
                    chunks.append(content.get("text") or "")
        text = "".join(chunks)
    usage = payload.get("usage") or {}
    return {
        "text": text,
        "model": payload.get("model") or model,
        "latency_ms": int((time.time() - started) * 1000),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "reasoning_tokens": (usage.get("output_tokens_details") or {}).get("reasoning_tokens"),
    }


def estimate_cost(model: str, input_tokens: int | None, output_tokens: int | None) -> float | None:
    rate = RATES.get(model)
    if not rate or input_tokens is None or output_tokens is None:
        return None
    return (input_tokens * rate[0] + output_tokens * rate[1]) / 1_000_000


def pack_is_retrieval_failure(question: dict, pack: dict) -> bool:
    if (question.get("expect") or {}).get("must_abstain"):
        return False
    must = [item.upper() for item in (question.get("expect") or {}).get("must_cite_any_of") or []]
    have = {item.upper() for item in pack["case_ids"]}
    if (question.get("expect") or {}).get("series_not_one_event") and pack["series_event_count"] is None:
        return True
    if must and not have.intersection(must):
        return True
    if not have and not (question.get("expect") or {}).get("series_not_one_event"):
        return True
    return False


def run_one(env, arm, question, pack, system, source_only) -> dict:
    if pack_is_retrieval_failure(question, pack):
        return {
            "question_id": question["id"],
            "status": "RETRIEVAL_FAILURE",
            "answer": "",
            "score": {"retrieval_failure": True, "fake_citations": 0, "citations_outside_retrieval": 0, "unsupported_claims": 0, "abstention_correct": None},
        }
    try:
        if arm["provider"] == "anthropic":
            generated = call_anthropic(env, arm["model"], system, pack["user"])
        else:
            generated = call_openai(env, arm["model"], arm.get("reasoning_effort") or "low", system, pack["user"])
    except urllib.error.HTTPError as error:
        detail = error.read().decode()[:500]
        return {"question_id": question["id"], "status": "API_ERROR", "error": f"{error.code} {detail}", "answer": ""}
    score = score_answer(
        question,
        generated["text"],
        pack["case_ids"],
        source_only_ids=source_only,
        series_event_count=pack["series_event_count"],
        evidence_text=pack.get("user") or "",
    )
    return {
        "question_id": question["id"],
        "status": "scored",
        "answer": generated["text"],
        "model": generated["model"],
        "latency_ms": generated["latency_ms"],
        "input_tokens": generated["input_tokens"],
        "output_tokens": generated["output_tokens"],
        "reasoning_tokens": generated["reasoning_tokens"],
        "estimated_cost_usd": estimate_cost(generated["model"], generated["input_tokens"], generated["output_tokens"]),
        "score": score,
    }


def summarize(arm: dict, rows: list[dict]) -> dict:
    scored = [row for row in rows if row.get("status") == "scored"]
    retrieval = [row for row in rows if row.get("status") == "RETRIEVAL_FAILURE"]
    errors = [row for row in rows if row.get("status") == "API_ERROR"]
    fake = sum(row["score"].get("fake_citations") or 0 for row in scored)
    outside = sum(row["score"].get("citations_outside_retrieval") or 0 for row in scored)
    unsupported = sum(row["score"].get("unsupported_claims") or 0 for row in scored)
    abstain_rows = [row for row in scored if row["score"].get("abstention_correct") is not None]
    abstain_fail = sum(1 for row in abstain_rows if row["score"]["abstention_correct"] is False)
    grounded_rows = [row for row in scored if row["score"].get("grounded") is not None]
    grounded_hits = sum(1 for row in grounded_rows if row["score"]["grounded"])
    epistemic_rows = [row for row in scored if row["score"].get("epistemic_fidelity") is not None]
    epistemic_hits = sum(1 for row in epistemic_rows if row["score"]["epistemic_fidelity"])
    complete_rows = [row for row in scored if row["score"].get("completeness") is not None]
    complete_hits = sum(1 for row in complete_rows if row["score"]["completeness"])
    paraphrases = sum(1 for row in scored if row["score"].get("evidence_status") == "SUPPORTED_WITH_ACCEPTABLE_PARAPHRASE")
    overstated = sum(1 for row in scored if row["score"].get("evidence_status") == "OVERSTATED")
    recalls = [row["score"]["citation_recall"] for row in scored if row["score"].get("citation_recall") is not None]
    precisions = [row["score"]["citation_precision"] for row in scored if row["score"].get("citation_precision") is not None]
    canonical_rows = [row for row in scored if (row["score"].get("canonical_correct") is not None)]
    costs = []
    cost_missing = False
    for row in scored:
        cost = row.get("estimated_cost_usd")
        if cost is None:
            cost = estimate_cost(row.get("model") or arm["model"], row.get("input_tokens"), row.get("output_tokens"))
        if cost is None:
            cost_missing = True
        else:
            costs.append(cost)
    latency = [row.get("latency_ms") or 0 for row in scored]
    hard_pass = fake == 0 and outside == 0 and unsupported == 0 and abstain_fail == 0 and not errors
    return {
        "arm": arm["id"],
        "provider": arm["provider"],
        "model": arm["model"],
        "reasoning_effort": arm.get("reasoning_effort"),
        "hard_gate_pass": hard_pass,
        "fake_citations": fake,
        "citations_outside_retrieval": outside,
        "unsupported_claims": unsupported,
        "hard_abstention_failures": abstain_fail,
        "abstention_checked": len(abstain_rows),
        "grounded_correct": grounded_hits,
        "grounded_checked": len(grounded_rows),
        "semantic_grounded_correct": grounded_hits,
        "semantic_grounded_checked": len(grounded_rows),
        "epistemic_correct": epistemic_hits,
        "epistemic_checked": len(epistemic_rows),
        "completeness_correct": complete_hits,
        "completeness_checked": len(complete_rows),
        "acceptable_paraphrases": paraphrases,
        "overstated": overstated,
        "citation_precision_mean": (sum(precisions) / len(precisions)) if precisions else None,
        "citation_recall_mean": (sum(recalls) / len(recalls)) if recalls else None,
        "canonical_correct": sum(1 for row in canonical_rows if row["score"]["canonical_correct"]),
        "canonical_checked": len(canonical_rows),
        "retrieval_failures": len(retrieval),
        "api_errors": len(errors),
        "estimated_cost_usd": None if cost_missing else round(sum(costs), 6),
        "latency_ms_mean": int(sum(latency) / len(latency)) if latency else None,
        "input_tokens": sum(row.get("input_tokens") or 0 for row in scored),
        "output_tokens": sum(row.get("output_tokens") or 0 for row in scored),
    }


def choose(summaries: list[dict]) -> dict:
    eligible = [item for item in summaries if item["hard_gate_pass"] and item["arm"] != "blocked"]
    if not eligible:
        return {"primary": None, "fallback": None, "reason": "no arm passed the hard gate"}

    def ratio(item: dict, hit: str, checked: str) -> float:
        count = item.get(checked) or 0
        return (item.get(hit) or 0) / count if count else 1.0

    def rank(item: dict) -> tuple:
        cost = item["estimated_cost_usd"]
        cost_rank = -(cost if isinstance(cost, (int, float)) else 1_000_000_000)
        return (
            -(item["unsupported_claims"] or 0),
            -(item["fake_citations"] or 0),
            -(item["citations_outside_retrieval"] or 0),
            item["citation_recall_mean"] or 0,
            -(item["hard_abstention_failures"] or 0),
            ratio(item, "semantic_grounded_correct", "semantic_grounded_checked"),
            ratio(item, "epistemic_correct", "epistemic_checked"),
            ratio(item, "completeness_correct", "completeness_checked"),
            ratio(item, "canonical_correct", "canonical_checked"),
            -(item["latency_ms_mean"] or 0),
            cost_rank,
        )

    ordered = sorted(eligible, key=rank, reverse=True)
    primary = ordered[0]["arm"]
    fallback = ordered[1]["arm"] if len(ordered) > 1 else None
    return {
        "primary": primary,
        "fallback": fallback,
        "reason": "unsupported claims, citation correctness, abstention, semantic grounding, epistemic fidelity, completeness, canonical events, latency, then cost",
    }


def main() -> None:
    env = load_env()
    questions = json.loads(QUESTIONS.read_text())
    assert_question_set(questions)
    fragments = load_fragments()
    local_ids = {row["case_id"] for row in fragments}
    for row in load_production_fragments(env):
        if row.get("case_id") and row["case_id"] not in local_ids:
            fragments.append(row)
    graph = load_graph()
    events_by_case = {}
    for event in graph["canonical_events"]:
        for case_id in event.get("member_case_ids") or []:
            events_by_case[case_id.upper()] = event
    series_by_event = {}
    for series in graph.get("event_series") or []:
        for event_id in series.get("event_ids") or []:
            series_by_event[event_id] = series
    source_only = source_only_ids()
    packs = [build_pack(question, fragments, graph, events_by_case, series_by_event) for question in questions]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "evidence_packs.json").write_text(json.dumps(packs, indent=2))
    system = system_prompt()
    by_id = {question["id"]: question for question in questions}
    summaries = []
    blocked = []
    if not env.get("OPENAI_API_KEY"):
        for arm in ARMS:
            if arm["provider"] == "openai":
                blocked.append({**arm, "status": "OPENAI_API_KEY_MISSING"})
                summaries.append({
                    "arm": arm["id"],
                    "provider": "openai",
                    "model": arm["model"],
                    "reasoning_effort": arm.get("reasoning_effort"),
                    "hard_gate_pass": False,
                    "status": "OPENAI_API_KEY_MISSING",
                    "fake_citations": None,
                    "citations_outside_retrieval": None,
                    "unsupported_claims": None,
                    "hard_abstention_failures": None,
                })
    runnable = [arm for arm in ARMS if not (arm["provider"] == "openai" and not env.get("OPENAI_API_KEY"))]
    if not env.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY missing")

    for arm in runnable:
        print(f"running {arm['id']}", flush=True)
        rows = []
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(run_one, env, arm, by_id[pack["question_id"]], pack, system, source_only): pack["question_id"]
                for pack in packs
            }
            for future in as_completed(futures):
                row = future.result()
                rows.append(row)
                print(f"  {arm['id']} {row['question_id']} {row['status']}", flush=True)
        rows.sort(key=lambda row: row["question_id"])
        (RESULTS / f"{arm['id']}.json").write_text(json.dumps(rows, indent=2))
        summaries.append(summarize(arm, rows))

    decision = choose([item for item in summaries if item.get("status") != "OPENAI_API_KEY_MISSING"])
    summary = {
        "prompt_version": "rag-v2.6",
        "retrieval_note": "Frozen lexical evidence plus linker context. Production match_incidents was not changed.",
        "sonnet_5_5_model_id": "claude-sonnet-5-5",
        "blocked_arms": blocked,
        "arms": summaries,
        "decision": decision,
    }
    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
