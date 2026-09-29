# V2 local release gate

**Date:** 2026-09-28  
**Verdict:** `LOCAL_RELEASE_READY`  
**Blocker:** none in the local gate. This document does not start the migration.

Production writes during this milestone: 0  
Deploys: 0  
Production `RAG_PROVIDER` flip: 0

## Corpus

```text
450 official records reconciled
unexplained missing = 0
```

Computed from `pipeline/reports/corpus_qa/source_coverage.json` (450 rows) and checked against the reviewed expectation. The assertion matched. It was not edited to force a match.

Release record totals computed from that file: 158, 64, 72, 40, 41, 75.

## Extraction

```text
classifier fixtures PASS
quote validation PASS
evidence gate PASS
truncation PASS
extraction_failed unexplained = 0
```

`python -m pipeline.qa_v2` using `.venv/bin/python` exited 0. The system Python without that virtualenv cannot import `anthropic`, so the gate command has to run inside the project virtualenv.

## Identity

```text
linker regression PASS
Colorado Springs PASS
Western US PASS
unresolved overmerge = 0
high-confidence underlink = 0
```

Computed identity counts: 583 fragment case IDs on canonical events, 575 canonical events, 1 series, 21 events in `western-us-event-2023`. Reviewed expectations matched.

## RAG

```text
CORPUS_QA_COMPLETE              pass
RAG_MODEL_EVAL_COMPLETE         pass
scoring                         grounding_v2
primary                         gpt-6-sol / medium
degraded retry                  gpt-6-sol / low
provider failover               claude-sonnet-5-5
web build                       pass
route QA                        pass
production writes               0
deploys                         0
production RAG flip             0
```

The lexical rank that selected Sonnet 4.5 is withdrawn. It is kept at `pipeline/evals/rag/results/summary_v1_lexical_SUPERSEDED.json`. See `docs/V2_RAG_MODEL_EVAL.md`. Production `RAG_PROVIDER` is still the Anthropic default.

## Vector retrieval

The 60-question model eval used one frozen lexical pack. This gate also ran those questions through a local shadow index:

```text
380 unflagged R1 embeddings read from production
voyage-3 signature             380/380 (1024-d prefix, 512-d zero pad, 1536 stored)
203 R2–R6 fragments embedded   voyage-3 locally
shadow index                   583
production writes              0
```

Unthresholded retrieval on the 48 questions that name an expected case:

```text
Recall@5     0.854
Recall@10    0.896
Recall@20    0.958
MRR          0.821
```

Generation used the production window: cosine similarity above 0.3, top 10, then the same canonical-event annotation the Ask route attaches. GPT-6 Sol medium on that window:

```text
fake citations                 0
citations outside retrieval    0
unsupported claims             0
hard abstention failures       0
```

Direct packs for Sary Shagan, Tremonton, the December 1948 green fireball, Colorado Springs 2022 (`evt-0424`, `primary_narrative`), and the Western US 2023 series (21 events) all contained the expected context.

Five questions fall outside that top-10 window: Colorado Springs source and media follow-ups (q27 rank 11, q28 rank 16, q38 below the 0.3 cutoff at rank 14), Puerto Rico records in common (q32), and Newark FBI files (q44). Those are measured retrieval misses. They are not a reason to change the embedding model or Linker V1 in this local milestone.

## Web

```text
TypeScript PASS
build PASS
routes PASS
mobile PASS
SEO PASS
```

`npx tsc --noEmit` exited 0. `npm run build` exited 0 after Google fonts could be downloaded (the sandboxed build failed in `next/font` before that). The build's own lint and type check passed. `npx next lint` has no committed ESLint config and opens an interactive prompt, so that command was not used to invent a new config.

Local server on port 3456, `RAG_EVIDENCE_SOURCE=local`:

- `/`, `/incidents`, `/map`, `/collections`, `/releases`, `/releases/03`, `/sources`, `/source/DOW-UAP-D102`, `/source/FBI-UAP-D002`, `/media`, `/audio`, `/ask`, `/about`, `/sitemap.xml`, `/robots.txt`, `/llms.txt` returned 200.
- `/releases/99` and `/source/NOT-A-FILE` returned 404.
- Homepage text: 583 verified incident fragments, 575 canonical events, 450 official source records, 6 PURSUE releases. It does not say "583 UFO events."
- `/audio` lists 16 official audio records and does not invent transcripts.
- `/source/FBI-UAP-D002` shows the Colorado Springs 2022 event, role `primary_narrative`, and fragment `UNDATED-USA-599D8B`.
- A 390px viewport still exposed Releases, Sources, and Audio in the nav.

Some source rows have no local SHA-256 or page count. The page says those values are not recorded. R6 cached PDFs that have a cache manifest show a checksum.

## Production

```text
writes = 0
deploy = 0
GPT-6 production = off
```

Ask telemetry for the local server went to `pipeline/reports/rag_telemetry/`, not to production `ask_log`. The eval's only database call was a read of unflagged incident text.

## Production sequence, not started

The local gate is `LOCAL_RELEASE_READY`. Local implementation stops here. This run did not back up production, apply migrations, write incidents, deploy, or set `RAG_PROVIDER`. The shadow index read the 380 production embeddings and wrote new vectors only under `pipeline/reports/shadow_index/`. When a later instruction says to start, finish the data migration, shadow QA, V2 UI deploy, and production smoke before:

```text
RAG_PROVIDER=openai
RAG_MODEL=gpt-6-sol
RAG_REASONING_EFFORT=medium
```

Then smoke Ask. If that smoke fails, set `RAG_PROVIDER=anthropic` and `ANTHROPIC_RAG_MODEL=claude-sonnet-4-5-20250929` immediately. The full data sequence is in `docs/V2_FINAL_LOCAL_AUDIT.md`.
