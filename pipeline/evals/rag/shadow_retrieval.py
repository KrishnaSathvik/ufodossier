"""Production-equivalent local vector retrieval.

Reads the 380 unflagged Release 1 Voyage embeddings. Embeds the 203 local
R2–R6 fragments with voyage-3. Searches that 583-row shadow index. Does not
write Supabase, deploy, or change match_incidents.

Usage:
  python -m pipeline.evals.rag.shadow_retrieval
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

import numpy as np

from pipeline.corpus_qa import load_local_incidents
from pipeline.embed import VECTOR_DIM, embed_batch
from pipeline.evals.rag.runner import (
    QUESTIONS,
    RESULTS,
    call_openai,
    estimate_cost,
    format_fragment,
    identity_for,
    load_env,
    load_graph,
    load_production_fragments,
    score_answer,
    source_only_ids,
    summarize,
    system_prompt,
)

ROOT_INDEX = RESULTS.parents[2] / "reports" / "shadow_index"
MATCH_THRESHOLD = 0.3
MATCH_COUNT = 10
R1_EXPECTED = 380
LOCAL_EXPECTED = 203

FIXTURES = (
    {
        "name": "sary_shagan",
        "question_id": "q01",
        "any_of": ["UNDATED-CIA-6E72CA", "UNDATED-CIA-158652"],
    },
    {
        "name": "tremonton",
        "question_id": "q02",
        "any_of": ["1952-USN-80203D", "1952-DOW-141453", "1952-USAF-0585D4"],
    },
    {
        "name": "green_fireballs",
        "question_id": "q03",
        "any_of": ["1948-USAF-DDD5CA", "1948-USAF-BFA2CC", "UNDATED-DOE-80EBE8"],
    },
    {
        "name": "colorado_springs",
        "question_id": "q05",
        "any_of": ["UNDATED-USA-599D8B"],
        "pack_contains": ["evt-0424", "primary_narrative"],
    },
    {
        "name": "western_us_series",
        "question_id": "q26",
        "pack_contains": ["western-us-event-2023", "21"],
    },
)


def main() -> None:
    env = load_env()
    os.environ.update({key: value for key, value in env.items() if key not in os.environ})
    os.environ.setdefault("EMBEDDING_PROVIDER", "voyage")
    os.environ.setdefault("EMBEDDING_MODEL", "voyage-3")
    ROOT_INDEX.mkdir(parents=True, exist_ok=True)

    local = sorted(load_local_incidents(), key=lambda row: row["case_id"])
    production = sorted(load_production_fragments(env), key=lambda row: row["case_id"])
    if len(local) != LOCAL_EXPECTED or len(production) != R1_EXPECTED:
        raise SystemExit(f"corpus split is {len(production)} production and {len(local)} local")
    if {row["case_id"] for row in local} & {row["case_id"] for row in production}:
        raise SystemExit("local fragments overlap production case ids")

    r1_vectors, r1_report = load_r1_vectors(env, [row["case_id"] for row in production])
    local_vectors = load_local_vectors(local)
    incidents = production + local
    matrix = np.vstack([r1_vectors, local_vectors]).astype(np.float32)
    if matrix.shape != (R1_EXPECTED + LOCAL_EXPECTED, VECTOR_DIM):
        raise SystemExit(f"shadow index shape {matrix.shape}")
    np.save(ROOT_INDEX / "vectors.npy", matrix)
    (ROOT_INDEX / "ids.json").write_text(json.dumps([row["case_id"] for row in incidents], indent=2))

    graph = load_graph()
    events_by_case = {}
    for event in graph["canonical_events"]:
        for case_id in event.get("member_case_ids") or []:
            events_by_case[case_id.upper()] = event
    series_by_event = {}
    for series in graph.get("event_series") or []:
        for event_id in series.get("event_ids") or []:
            series_by_event[event_id] = series

    questions = json.loads(QUESTIONS.read_text())
    query_matrix = embed_in_small_batches([question["question"] for question in questions])
    queries = np.asarray(query_matrix, dtype=np.float32)
    similarities = cosine(queries, matrix)

    source_only = source_only_ids()
    packs = []
    metrics = []
    for index, question in enumerate(questions):
        order = np.argsort(-similarities[index])
        ranked = [incidents[int(position)]["case_id"] for position in order]
        scores = [float(similarities[index, int(position)]) for position in order]
        expected = [item.upper() for item in (question.get("expect") or {}).get("must_cite_any_of") or []]
        hits = [
            (incidents[int(position)], float(similarities[index, int(position)]))
            for position in order
            if float(similarities[index, int(position)]) > MATCH_THRESHOLD
        ][:MATCH_COUNT]
        user = render_pack(question["question"], hits, graph, events_by_case, series_by_event)
        pack = {
            "question_id": question["id"],
            "case_ids": [incident["case_id"] for incident, _score in hits],
            "similarities": [round(score, 6) for _incident, score in hits],
            "series_event_count": series_count(hits, events_by_case, series_by_event),
            "user": user,
        }
        packs.append(pack)
        metrics.append(retrieval_metric(question["id"], expected, ranked, scores))

    retrieval = {
        "index": {
            "fragments": int(matrix.shape[0]),
            "r1_production_read": R1_EXPECTED,
            "r2_r6_local_embedded": LOCAL_EXPECTED,
            "provider": "voyage",
            "model": "voyage-3",
            "dimensions": VECTOR_DIM,
            "voyage_signature": r1_report,
            "match_threshold": MATCH_THRESHOLD,
            "match_count": MATCH_COUNT,
            "production_writes": 0,
        },
        "recall": aggregate(metrics),
        "fixtures": [fixture_result(item, packs) for item in FIXTURES],
        "questions": metrics,
    }
    (ROOT_INDEX / "retrieval_report.json").write_text(json.dumps(retrieval, indent=2))
    (RESULTS / "shadow_evidence_packs.json").write_text(json.dumps(packs, indent=2))
    print(json.dumps({"recall": retrieval["recall"], "fixtures": retrieval["fixtures"], "voyage": r1_report}, indent=2), flush=True)

    system = system_prompt()
    by_id = {question["id"]: question for question in questions}
    arm = {"id": "shadow-gpt-6-sol-medium", "provider": "openai", "model": "gpt-6-sol", "reasoning_effort": "medium"}
    out = RESULTS / "shadow_gpt-6-sol-medium.json"
    rows = {}
    if out.exists():
        for row in json.loads(out.read_text()):
            if row.get("status") == "scored":
                rows[row["question_id"]] = row
    pending = [pack for pack in packs if pack["question_id"] not in rows]
    print(f"gpt-6-sol medium on vector packs pending {len(pending)}", flush=True)
    if pending and not env.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY missing")
    if pending:
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {
                pool.submit(run_pack, env, arm, by_id[pack["question_id"]], pack, system, source_only): pack["question_id"]
                for pack in pending
            }
            for future in as_completed(futures):
                row = future.result()
                rows[row["question_id"]] = row
                ordered = [rows[key] for key in sorted(rows)]
                out.write_text(json.dumps(ordered, indent=2))
                print(f"  {row['question_id']} {row['status']}", flush=True)
    ordered = [rows[key] for key in sorted(rows)]
    summary = summarize(arm, ordered)
    summary["retrieval"] = retrieval["recall"]
    summary["fixtures"] = retrieval["fixtures"]
    summary["voyage_signature"] = r1_report
    (RESULTS / "shadow_summary.json").write_text(json.dumps(summary, indent=2))
    print("SHADOW_DONE", json.dumps(summary), flush=True)


def load_r1_vectors(env: dict[str, str], case_ids: list[str]) -> tuple[np.ndarray, dict]:
    path = ROOT_INDEX / "r1_vectors.npy"
    ids_path = ROOT_INDEX / "r1_ids.json"
    if path.exists() and ids_path.exists() and json.loads(ids_path.read_text()) == case_ids:
        matrix = np.load(path)
    else:
        fetched = fetch_production_embeddings(env)
        by_id = {row["case_id"]: parse_vector(row["embedding"]) for row in fetched}
        missing = [case_id for case_id in case_ids if case_id not in by_id]
        if missing:
            raise SystemExit(f"{len(missing)} unflagged production rows have no embedding")
        matrix = np.asarray([by_id[case_id] for case_id in case_ids], dtype=np.float32)
        np.save(path, matrix)
        ids_path.write_text(json.dumps(case_ids))
    report = voyage_signature(matrix)
    if not report["pass"]:
        raise SystemExit(f"R1 embeddings are not voyage-3 padded vectors: {report}")
    return matrix, report


def fetch_production_embeddings(env: dict[str, str]) -> list[dict]:
    url = env["SUPABASE_URL"].rstrip("/")
    key = env["SUPABASE_SERVICE_KEY"]
    rows = []
    start = 0
    page = 25
    while True:
        request = urllib.request.Request(
            f"{url}/rest/v1/incidents?flagged=eq.false&select=case_id,embedding&order=case_id.asc",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Range": f"{start}-{start + page - 1}"},
        )
        with urllib.request.urlopen(request, timeout=120) as response:
            batch = json.loads(response.read().decode())
        if not batch:
            break
        rows.extend(batch)
        print(f"read production embeddings {len(rows)}", flush=True)
        if len(batch) < page:
            break
        start += page
    return rows


def parse_vector(value) -> list[float]:
    if isinstance(value, str):
        value = json.loads(value)
    return [float(item) for item in value]


def voyage_signature(matrix: np.ndarray) -> dict:
    tail = np.max(np.abs(matrix[:, 1024:]), axis=1)
    head = np.max(np.abs(matrix[:, :1024]), axis=1)
    bad_rows = int(np.sum((tail > 0) | (head <= 0)))
    return {
        "rows": int(matrix.shape[0]),
        "dimensions": int(matrix.shape[1]),
        "padded_zero_tail": int(np.sum(tail == 0)),
        "nonzero_voyage_prefix": int(np.sum(head > 0)),
        "invalid_rows": bad_rows,
        "pass": matrix.shape == (R1_EXPECTED, VECTOR_DIM) and bad_rows == 0,
    }


def load_local_vectors(incidents: list[dict]) -> np.ndarray:
    path = ROOT_INDEX / "local_vectors.npy"
    ids_path = ROOT_INDEX / "local_ids.json"
    case_ids = [row["case_id"] for row in incidents]
    if path.exists() and ids_path.exists() and json.loads(ids_path.read_text()) == case_ids:
        return np.load(path)
    texts = [f"{row.get('title') or ''}\n{row.get('summary') or ''}\n{row.get('raw_excerpt') or ''}" for row in incidents]
    print(f"embedding {len(texts)} local fragments with voyage-3", flush=True)
    matrix = np.asarray(embed_in_small_batches(texts), dtype=np.float32)
    if matrix.shape != (len(incidents), VECTOR_DIM):
        raise SystemExit(f"local embedding shape {matrix.shape}")
    if int(np.sum(np.max(np.abs(matrix[:, 1024:]), axis=1) > 0)):
        raise SystemExit("local voyage vectors were not 1024-d padded")
    np.save(path, matrix)
    ids_path.write_text(json.dumps(case_ids))
    return matrix


def embed_in_small_batches(texts: list[str], size: int = 16) -> list[list[float]]:
    vectors: list[list[float]] = []
    for start in range(0, len(texts), size):
        vectors.extend(embed_batch(texts[start : start + size]))
        print(f"embedded {min(start + size, len(texts))}/{len(texts)}", flush=True)
        if start + size < len(texts):
            time.sleep(12)
    return vectors


def cosine(queries: np.ndarray, docs: np.ndarray) -> np.ndarray:
    query_norm = np.linalg.norm(queries, axis=1, keepdims=True)
    doc_norm = np.linalg.norm(docs, axis=1, keepdims=True)
    return (queries @ docs.T) / (query_norm * doc_norm.T)


def retrieval_metric(question_id: str, expected: list[str], ranked: list[str], scores: list[float]) -> dict:
    positions = []
    for case_id in expected:
        if case_id in ranked:
            positions.append(ranked.index(case_id) + 1)
    best = min(positions) if positions else None
    return {
        "question_id": question_id,
        "expected": expected,
        "best_rank": best,
        "recall_at_5": None if not expected else int(best is not None and best <= 5),
        "recall_at_10": None if not expected else int(best is not None and best <= 10),
        "recall_at_20": None if not expected else int(best is not None and best <= 20),
        "reciprocal_rank": 0.0 if best is None else (1.0 / best if expected else None),
        "top1": ranked[0] if ranked else None,
        "top1_similarity": round(scores[0], 6) if scores else None,
    }


def aggregate(metrics: list[dict]) -> dict:
    scored = [row for row in metrics if row["expected"]]
    def mean(key: str) -> float | None:
        values = [row[key] for row in scored if row[key] is not None]
        return None if not values else round(sum(values) / len(values), 4)
    return {
        "questions_with_expected_case": len(scored),
        "recall_at_5": mean("recall_at_5"),
        "recall_at_10": mean("recall_at_10"),
        "recall_at_20": mean("recall_at_20"),
        "mrr": mean("reciprocal_rank"),
    }


def render_pack(question: str, hits: list[tuple[dict, float]], graph, events_by_case, series_by_event) -> str:
    blocks = []
    series_seen = set()
    series_blocks = []
    for incident, _score in hits:
        identity = identity_for(incident["case_id"], graph, events_by_case, series_by_event)
        blocks.append(format_fragment(incident, identity))
        series = (identity or {}).get("series")
        if series and series["series_id"] not in series_seen:
            series_seen.add(series["series_id"])
            count = len(series.get("event_ids") or [])
            series_blocks.append(
                f"Series {series['series_id']}: {series.get('label') or 'untitled'}\n"
                f"Canonical events in the series: {count}\n"
                "Treat this as separate events grouped as a series. Do not describe the series as one UAP event."
            )
    series_text = ""
    if series_blocks:
        series_text = "\n\nEVENT SERIES IN THIS EVIDENCE:\n" + "\n\n".join(series_blocks)
    body = "\n\n---\n\n".join(blocks)
    return (
        f"QUESTION:\n{question}\n\nARCHIVE EVIDENCE:\n{body}{series_text}\n\n"
        "Answer using only this evidence. Cite case IDs inline."
    )


def series_count(hits, events_by_case, series_by_event) -> int | None:
    for incident, _score in hits:
        event = events_by_case.get(incident["case_id"].upper())
        series = series_by_event.get(event["event_id"]) if event else None
        if series:
            return len(series.get("event_ids") or [])
    return None


def fixture_result(spec: dict, packs: list[dict]) -> dict:
    pack = next(item for item in packs if item["question_id"] == spec["question_id"])
    found = {case_id.upper() for case_id in pack["case_ids"]}
    expected = [item.upper() for item in spec.get("any_of") or []]
    retrieved = (not expected) or bool(found.intersection(expected))
    text_ok = all(token in pack["user"] for token in spec.get("pack_contains") or [])
    return {
        "name": spec["name"],
        "question_id": spec["question_id"],
        "retrieved": retrieved,
        "context_present": text_ok,
        "pass": retrieved and text_ok,
        "top_case_ids": pack["case_ids"][:5],
    }


def run_pack(env, arm, question, pack, system, source_only) -> dict:
    if not pack["case_ids"] and not (question.get("expect") or {}).get("must_abstain"):
        return {"question_id": question["id"], "status": "RETRIEVAL_FAILURE", "answer": "", "score": {"retrieval_failure": True, "fake_citations": 0, "citations_outside_retrieval": 0, "unsupported_claims": 0, "abstention_correct": None}}
    try:
        generated = call_openai(env, arm["model"], "medium", system, pack["user"])
    except urllib.error.HTTPError as error:
        detail = error.read().decode()[:500]
        return {"question_id": question["id"], "status": "API_ERROR", "error": f"{error.code} {detail}", "answer": ""}
    score = score_answer(
        question,
        generated["text"],
        pack["case_ids"],
        source_only_ids=source_only,
        series_event_count=pack["series_event_count"],
        evidence_text=pack["user"],
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


if __name__ == "__main__":
    main()
