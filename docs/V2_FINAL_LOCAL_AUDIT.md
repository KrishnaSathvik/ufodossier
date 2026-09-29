# V2 final local audit

**Date:** 2026-09-28  
**Verdict:** `LOCAL_RELEASE_READY`

## What this milestone changed

Ask the Archive no longer hardcodes `claude-sonnet-4-5-20250929` inside the route. `web/src/lib/rag/` selects Anthropic or OpenAI from the environment, builds one prompt (`rag-v2.0`), checks citations without deleting them out of an otherwise unchanged answer, and writes telemetry locally unless `RAG_TELEMETRY_SINK=supabase`.

The unset default is still Anthropic on the historical Sonnet 4.5 id. Starting the app does not turn on GPT-6.

New local pages read the corpus artifacts:

- `/releases` and `/releases/[release]`
- `/sources` and `/source/[id]`
- `/audio`

Homepage, about, sitemap, robots, Open Graph, and `llms.txt` use fragment / event / source language. Counts are computed from the coverage file and the linker graph.

Extraction, the quote gate, embeddings, and Linker V1 were not redesigned.

## Safety metrics that were measured

Four arms, 60 frozen questions, identical evidence. `gpt-6-sol` was called on the Responses API at reasoning effort low and medium.

```text
fake citations                 0 on every arm
citations outside retrieval    0 on every arm
unsupported claims             0 on every arm
hard abstention failures       0 on every arm
semantic grounding             60/60 on every arm
epistemic fidelity             60/60 on every arm
```

```text
PRIMARY                  gpt-6-sol / medium
DEGRADED RETRY           gpt-6-sol / low
PROVIDER FAILOVER        claude-sonnet-5-5
```

`grounding_v2` rescored the saved answers. The lexical rank that selected Sonnet 4.5 is withdrawn and kept in `pipeline/evals/rag/results/summary_v1_lexical_SUPERSEDED.json`. Production `RAG_PROVIDER` stays unset-as-Anthropic until the sequence below reaches the Ask flip.

## Shadow vector retrieval

`pipeline/evals/rag/shadow_retrieval.py` read the 380 unflagged production embeddings, embedded the 203 local R2–R6 fragments with Voyage `voyage-3`, and searched the combined 583-row index. All 380 stored vectors have a 1024-dimension Voyage prefix and a zero tail. The run did not write those vectors back to Supabase.

```text
Recall@5  0.854
Recall@10 0.896
Recall@20 0.958
MRR       0.821
```

GPT-6 Sol medium, answering from the production top-10 window, had 0 fake citations, 0 outside-retrieval citations, 0 unsupported claims, and 0 abstention failures. Sary Shagan, Tremonton, green fireballs, Colorado Springs 2022, and the Western US 2023 series were in the retrieved context for their direct questions. Five of 48 expected-case questions miss that top-10 window. Details are in `docs/V2_LOCAL_RELEASE_GATE.md`.

Embeddings no longer fall back from Voyage to OpenAI. `EMBEDDING_PROVIDER=voyage` and `EMBEDDING_MODEL=voyage-3` are required. A Voyage failure stops retrieval.

## What remains outside this gate

Production vector search still does not contain R2–R6 fragment embeddings. Local Ask used `RAG_EVIDENCE_SOURCE=local` for the manual questions. That flag is not the production retrieval path. Embedding those fragments is a step in the migration sequence below, not a local-gate failure.

## What was not done

```text
production writes     0
deploys               0
schema migrations     0
RAG_PROVIDER flip     0
```

`db/migrations/010_rag_telemetry_DESIGN_ONLY.sql` is design only.

## Production sequence, when a later instruction says to start

```text
backup
verify baseline counts
apply reviewed schema migrations
update existing source registry
reconcile R1 source links
insert R2–R6 source files
insert the computed new fragments
preserve the existing unflagged R1 fragments
preserve the flagged duplicate rows
insert incident_sources
insert canonical events
insert event memberships
insert source relationships
embed only the new fragments
shadow production QA
deploy the V2 UI
production smoke
RAG_PROVIDER=openai
RAG_MODEL=gpt-6-sol
RAG_REASONING_EFFORT=medium
smoke Ask
```

If the Ask smoke fails, roll the environment back immediately:

```text
RAG_PROVIDER=anthropic
ANTHROPIC_RAG_MODEL=claude-sonnet-4-5-20250929
```

Leave the migrated rows in place. After a successful flip, one failed OpenAI call retries `gpt-6-sol` at low effort and then calls `claude-sonnet-5-5`. That retry is not a substitute for the environment rollback above.

The migration runner must compute the delta and assert it against the reviewed expectation. If that assertion changes, stop. Do not edit the expected number to match.
