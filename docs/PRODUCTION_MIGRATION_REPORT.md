# Production migration report

**Verdict:** `PRODUCTION_MIGRATION_STOPPED`

**Stopped at:** Step 20 — deploy the tested application

**Failed invariant:** This session has no Vercel project link and cannot deploy the tested app. Data migration and shadow retrieval passed. GPT-6 was not enabled.

**Expected:** Deploy the exact local release candidate, then smoke the live site, then set `RAG_PROVIDER=openai`.

**Actual:** No deployment. Production database now holds the migrated corpus. `RAG_PROVIDER` is still unset, so Ask stays on the historical Anthropic model.

**Writes already completed:** schema (SQL editor), registry null-fills, release rows 2–6, 149 source files, 203 fragments, 203 incident links, linker graph, 203 Voyage embeddings. No incident text was rewritten. No flagged row was unflagged.

**Rollback:** not performed. The pre-change logical export is `backup_20260929T135423Z`.

## Passed phases

| Step | Status | Result |
|---|---|---|
| 1. Baseline | PASS | 480 / 380 / 100 / 181 files / 450 records / 476 links |
| 2. R1 fingerprint | PASS | `f50af77d3baf5d3f2e50ef109e7f6955fec8bd3e5ddefc67c924e5c089cfa0b0` |
| 3. Schema | PASS | User ran the reviewed SQL. New tables started empty. Incidents stayed 480 / 380 / 100. |
| 4. Registry | PASS | 154 classified PDFs filled where null. 180 media rows left untouched. Still 450 records, 0 duplicate identity keys. `pursue:FBI-UAP-D014` is the R4 PDF. `pursue:FBI-UAP-D014:image` stayed unclassified. |
| 5. R1 source links | PASS, no new links | Checksums for the URL-drift files were not available, so Gemini 7, Serial 153, and `59_64634` stayed unlinked. Southern United States 2020 was not merged with official `DOW-UAP-D020`. |
| 6–8. Delta and inserts | PASS | Computed overlap was 0 case IDs. Inserted 149 new PDFs (5 R2 files already existed) and 203 fragments. |
| 9. R1 again | PASS | Same fingerprint. 380/380 substantive rows unchanged. |
| 10. Flagged rows | PASS | 100 `duplicate_excerpt` still flagged. |
| 11. incident_sources | PASS | 476 + 203 = 679. |
| 12–15. Linker graph | PASS | 575 events, 583 memberships, 3 event-source rows, 1 series / 21 events, 44 decisions, 0 auto-merged. FBI-UAP-D014 is not in the Western US series. |
| 16–17. Embeddings | PASS | 203 new voyage-3 vectors, 1536 dimensions, 512-value zero tail. 380 existing R1 vectors left in place. 0 unflagged rows missing a vector. |
| 18. Shadow retrieval | PASS | Threshold 0.3, top 10. Sary Shagan, Tremonton, December 1948 green fireballs, Colorado Springs 2022 (`UNDATED-USA-599D8B` / `evt-0424` / `FBI-UAP-D002` primary, `FBI-UAP-D003` media, `ICA-UAP-D001` analysis), and Western US members all returned. |
| 19. Counts | PASS | See below. |
| 20. Deploy | STOPPED | No linked Vercel project. |
| 21–22. App smoke and GPT-6 | not started | |

## Counts now

```text
source_records             450
source_files               330
releases                     6

unflagged fragments        583
flagged duplicates         100
incidents total            683

canonical events           575
event memberships          583
event series                 1
Western US members          21

new Voyage embeddings      203
unflagged missing vectors    0
```

## Recommended next action

Do not deploy until that is explicitly requested. The local web catalog now loads the same 203 R2–R6 fragments that were inserted. `RAG_PROVIDER` stays unset. When a deploy is requested, deploy this same working tree, smoke the production routes, and only then set `RAG_PROVIDER=openai`, `RAG_MODEL=gpt-6-sol`, and `RAG_REASONING_EFFORT=medium`. Do not roll back the corpus if the deploy or the model switch fails.
