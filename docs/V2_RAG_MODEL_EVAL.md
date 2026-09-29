# V2 RAG model evaluation

**Date:** 2026-09-28  
**Verdict:** `RAG_MODEL_EVAL_COMPLETE`  
**Scoring:** `grounding_v2` (rescored from saved answers; models were not called again)  
**Prompt:** `rag-v2.0`  
**Sonnet 5.5 API id:** `claude-sonnet-5-5`  
**GPT-6 Sol API id:** `gpt-6-sol`

The first ranking treated a missing hedge word as a grounding miss. That ranking is withdrawn. `said` and `says` are attribution paraphrases, not unsupported claims.

The prompt already says to preserve uncertainty. It does not require the verb "reported". Rule 6 in `web/src/lib/rag/prompt.ts` is about meaning: do not make a hedged observation sound conclusive.

## Scores

Same frozen 60 questions. Same evidence packs. Same saved answers.

| Arm | Hard gate | Fake IDs | Outside retrieval | Unsupported | Abstention failures | Semantic grounding | Epistemic fidelity | Citation recall | Completeness | Canonical | Est. cost | Latency |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| GPT-6 Sol medium | pass | 0 | 0 | 0 | 0 | 60/60 | 60/60 | 1.000 | 60/60 | 4/4 | $0.387 | 3.5s |
| GPT-6 Sol low | pass | 0 | 0 | 0 | 0 | 60/60 | 60/60 | 1.000 | 60/60 | 4/4 | $0.365 | 4.0s |
| Claude Sonnet 5.5 | pass | 0 | 0 | 0 | 0 | 60/60 | 60/60 | 0.983 | 60/60 | 4/4 | $0.833 | 5.1s |
| Claude Sonnet 4.5 | pass | 0 | 0 | 0 | 0 | 60/60 | 60/60 | 0.983 | 60/60 | 4/4 | $0.695 | 5.5s |

Overstated answers: 0. Acceptable paraphrases: low 2, medium 1, both Claude arms 0. Retrieval failures: 0.

Rank order is unsupported claims, citation correctness, abstention, semantic grounding, epistemic fidelity, completeness, canonical events, latency, then cost. Safety, grounding, epistemic fidelity, completeness, and canonical checks tie. Both GPT-6 Sol arms cite every expected case in brackets. They rank above both Claude arms. Medium is faster than low, so medium is primary.

```text
PRIMARY
gpt-6-sol
reasoning = medium

DEGRADED RETRY
gpt-6-sol
reasoning = low

PROVIDER FAILOVER
claude-sonnet-5-5
```

Low is the same OpenAI model at lower reasoning effort. It is not a second vendor. If OpenAI is unavailable, both efforts fail together, and the adapter calls Anthropic. The route does not hardcode those ids. `getRagAttempts()` in `web/src/lib/rag/config.ts` reads them from the environment, and only after `RAG_PROVIDER=openai`.

```env
RAG_PROVIDER=openai
RAG_MODEL=gpt-6-sol
RAG_REASONING_EFFORT=medium
RAG_FALLBACK_MODEL=gpt-6-sol
RAG_FALLBACK_REASONING_EFFORT=low
RAG_SECONDARY_PROVIDER=anthropic
ANTHROPIC_RAG_MODEL=claude-sonnet-5-5
```

That block is not applied. Unset `RAG_PROVIDER` still runs `claude-sonnet-4-5-20250929`.

## Withdrawn lexical rank

`pipeline/evals/rag/results/summary_v1_lexical_SUPERSEDED.json` keeps the first rank. It scored GPT-6 Sol low 58/60 and medium 59/60 because the answers said "said" or "says" instead of a frozen hedge word. That rank selected Sonnet 4.5. It is superseded by `summary.json` (`grounding_v2`). Do not use it to choose a model.

## Rollback

If the later production Ask smoke fails, restore the current production model:

```env
RAG_PROVIDER=anthropic
ANTHROPIC_RAG_MODEL=claude-sonnet-4-5-20250929
```

After a successful flip, an OpenAI error in one request retries `gpt-6-sol` at low, then `claude-sonnet-5-5`. That in-request failover is separate from rolling the environment back.

## Manual review of the old GPT misses

Both were wording misses. Neither added an entity, a cause, or a proof the file does not contain.

**q01, Sary Shagan, effort low.** The CIA excerpt says the source observed an unidentified bright green circular object, could not judge altitude or size, and heard no sound. The answer says: "The source said they saw a bright green circular object or mass." That is `SUPPORTED_WITH_ACCEPTABLE_PARAPHRASE`. Effort medium uses both "said" and "reported" and was already `SUPPORTED`.

**q14, Puerto Rico, both efforts.** The record is an unresolved high-speed, high-altitude track that pulled away from a Crusader. Low says: "The record says it rapidly pulled away... The target's identity was not resolved." Medium says the target was unidentified and "does not identify the target." Both keep the track as a record, not a confirmed craft. Both are `SUPPORTED_WITH_ACCEPTABLE_PARAPHRASE`.

A sentence such as "A green extraterrestrial craft was proved" still scores `OVERSTATED`. "No document proves recovered alien bodies" does not, because the certainty is denied.

## Claude citation misses

These are missing square brackets, not invented cases.

- Sonnet 4.5 on q42 names `1952-USN-80203D` in prose and bold, without `[1952-USN-80203D]`.
- Sonnet 5.5 on q15 names `UNDATED-USAF-58C451` in prose, without brackets.

Giving those two answers credit for the prose IDs would tie citation recall. Latency would still place GPT-6 Sol medium first and GPT-6 Sol low second.

## Production-equivalent retrieval

A separate run, `python -m pipeline.evals.rag.shadow_retrieval`, did not reuse this lexical pack. It embedded the question with Voyage `voyage-3`, searched a local index of the 380 production vectors plus 203 newly embedded R2–R6 fragments, and called GPT-6 Sol medium on the top 10 hits above similarity 0.3. Safety counts on that path are also 0. Retrieval recall is in `docs/V2_LOCAL_RELEASE_GATE.md`. The lexical rank above is still the model comparison. It is not the retrieval measurement.
