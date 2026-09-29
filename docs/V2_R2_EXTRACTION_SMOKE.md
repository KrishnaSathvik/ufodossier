# V2 R2 Extraction Smoke (local-only)

**Date:** 2026-09-25  
**Mode:** Local / test-only — **no production writes, no Vercel deploy, no feature flags, no GPT-6**

## Stop gate

> Local R2 smoke test passes completely before any production migration, ingestion write, or deployment.

This document covers **extraction → quote validation → read-only duplicate triage**.

## Command

```bash
# after classify_document has written classifications.json
pipeline/.venv/bin/python -m pipeline.smoke_r2_extract
```

Uses Haiku (`claude-haiku-4-5`) for extraction only. Writes only under `pipeline/reports/r2_smoke/`.  
Loads production `incidents` for **read-only** duplicate scoring. Never upserts.

## Summary metrics

From `pipeline/reports/r2_smoke/extractions.json`:

| Metric | Value |
|--------|------:|
| Sources considered | 5 |
| Sources skipped by classifier | 2 |
| Sources extracted | 3 |
| Candidate incidents (model output) | 15 |
| Quote-valid incidents | **1** |
| Quote-rejected incidents | **14** |
| Duplicate review required | 0 |
| New unique (local, vs prod) | 1 |
| Production writes | **false** |

Prod comparison set: **480** incidents loaded via read-only Supabase select.

## Per-source outcome

| Source | Chunks | Validated | Rejected | Notes |
|--------|-------:|----------:|---------:|-------|
| CIA-UAP-D001.pdf | 1 | 0 | 1 | Real 1973 Sary Shagan green-circle narrative; Haiku cleaned OCR → substring fail (gate working) |
| DOE-UAP-D001.pdf | 1 | 1 | 0 | Pantex radar imagery packet; thin but verbatim excerpt |
| DOW-UAP-D017.pdf | 3 | 0 | 13 | Dense 1948–50 Sandia / green-fireball case file; OCR noise + one invalid-JSON chunk |

### Sole validated local incident

- **case_id:** `UNDATED-DOE-3A0A9F`
- **title:** Pantex Unidentified Object Incident
- **source:** DOE-UAP-D001.pdf
- **duplicate_status:** `new_event` (best prod similarity 0.382 → `1956-RAF-3BC0B2`)
- **excerpt:** `Image from Ground Surveillance Radar Tower` (verbatim; thin — expected for image-heavy packet)

## What the smoke proved

1. **Classifier → extract gate** skips non-incident docs before Haiku spend.
2. **Quote validator still drops** cleaned/hallucinated/non-substring excerpts (14/15). This is the intended safety behavior on noisy OCR.
3. **Duplicate triage** can score against production without writing.
4. **Cost:** 5 Haiku calls (1+1+3 chunks) — well under budget for this smoke.

## Open findings (review before any prod ingest)

1. **OCR quality is the bottleneck** for R2 scanned PDFs (especially DOW-UAP-D017). pypdf alone is insufficient; install/run tesseract (or better OCR) before production extraction of image-heavy releases.
2. **CIA-UAP-D001** almost certainly contains a real incident; smoke rejected it because the model’s excerpt did not match OCR-garbled source text. Fix path = better text layer, not weaker validation.
3. **Pantex validated excerpt is thin** — acceptable for smoke; production may want media-linked incidents to prefer caption + title context without inventing narrative.
4. One DOW chunk returned **invalid JSON** (unterminated string) — same class of failure already handled by extract.py (drop chunk).

## Akamai / inventory notes (carried forward)

- Official inventory remains **450** live `uap-data.csv` rows (vs 447 community mirror). See `docs/V2_DATA_FOUNDATION_CHECKPOINT.md`.
- war.gov still requires `curl_cffi` Chrome impersonation (Akamai 403 otherwise). Do not override User-Agent when using curl_cffi.
- This smoke used **already-cached** R2 PDFs only; no new war.gov fetches.

## Explicitly not done (per stop gate)

- No Supabase migration applied
- No `source_records` / `incidents` / Storage writes
- No Vercel deploy
- No `ENABLE_GPT6_RAG` / Ask model changes
- No production feature flags

## Gate status (extraction + validation + dedupe)

**PASS (harness)** — end-to-end local path completed with zero production mutation.

**CONDITIONAL (yield)** — usable extraction yield on this 5-PDF set is low until OCR improves. Do **not** treat 1/15 validated as a green light for R2 production ingest; treat it as evidence the safety gate works and that OCR is the next local work item.

## Review decision (next move)

After reviewing:

1. Accept classifier behavior for D002/D003 skips?
2. Prioritize local OCR upgrade for DOW/CIA before any further Haiku spend?
3. Only then consider (separately) production migration / ingestion — still behind this stop gate.
