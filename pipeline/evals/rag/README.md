# RAG evaluation

Frozen questions live in `questions.json`. Do not rewrite them from model outputs.

```bash
python -m pipeline.evals.rag.runner
python -m unittest pipeline.tests.test_rag_citations
```

The runner builds one evidence pack per question from local validated fragments, a read-only pull of unflagged production incidents, and Linker V1 canonical context. Every model sees that same pack.

Production `match_incidents` settings are not changed here. Embeddings are not regenerated.

Arms:

- Claude Sonnet 4.5, `claude-sonnet-4-5-20250929`
- Claude Sonnet 5.5, `claude-sonnet-5-5`
- GPT-6 Sol, `gpt-6-sol`, reasoning effort `low`
- GPT-6 Sol, `gpt-6-sol`, reasoning effort `medium`

If `OPENAI_API_KEY` is absent, the GPT-6 arms are recorded as `OPENAI_API_KEY_MISSING` and are not substituted with another model.

Hard gate, counted only on questions that were not `RETRIEVAL_FAILURE`:

- fake case IDs = 0
- citations outside the retrieved set = 0
- unsupported claims matched by the deterministic phrase checks = 0
- hard abstention failures = 0

`grounding_v2` scores semantic support separately from epistemic fidelity. `said`, `says`, and `stated` are acceptable attribution paraphrases. A strong word such as `proved` or `confirmed` fails only when the retrieved evidence does not assert it and the sentence does not deny it. The old hedge-word list is recorded as `hedge_ok` and is not the rank key.

Raw answers are stored under `results/`. Scoring rereads those files. It does not call the models again.
