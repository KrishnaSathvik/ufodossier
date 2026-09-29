# V2 R2 OCR Hardening (local-only)

**Date:** 2026-09-25  
**Mode:** Local / test-only — **no production writes, no schema apply, no Vercel, no GPT-6**

## Question answered

> Can we materially improve real-incident recovery from scanned R2 documents while keeping the exact same strict evidence boundary?

**Yes — with caveats.** Same 5 PDFs, same classifier shape (3 extract / 2 source_only), unchanged quote-tolerance rules, materially higher quote-valid recovery.

## Acceptance gate

| Requirement | Result |
|-------------|--------|
| Classifier regression unit tests | **7/7 PASS** |
| Frozen R2 smoke fixtures | **5/5 PASS** |
| Quote validation (`test_validation`) | **5/5 PASS** (tolerance unchanged) |
| CIA real incident survives gate | **YES** (1 accepted; core phrases exact in OCR text) |
| DOW OCR materially improved | **YES** (77 pages selectively OCR'd; 7 accepted incidents) |
| No evidence weakening | **YES** — no fuzzy quote acceptance; only page-marker / EOL-hyphen normalize for matching |
| Pantex thin-evidence detected | **YES** → `source_media_not_incident` |
| Invalid JSON retry path | **Implemented**; this run needed 0 retries (`json_first_pass=4`) |
| Production writes | **0** |
| Vercel / GPT-6 | **untouched** |

## Smoke V1 → V2 (same 5 PDFs)

| Metric | V1 (pypdf only) | V2 (selective OCR + gates) |
|--------|----------------:|---------------------------:|
| Classifier extract / source_only | 3 / 2 | **3 / 2** |
| Candidate incidents | 15 | 16 |
| Quote-valid (incl. later evidence drop) | 1 | **11** |
| Quote-rejected | 14 | **5** |
| Evidence-insufficient | — | **3** |
| Incidents accepted | 1 | **8** |
| Invalid JSON chunks | 1 | **0** |
| Production writes | 0 | 0 |

Artifacts:

- V1: `pipeline/reports/r2_smoke/extractions_v1.json`
- V2: `pipeline/reports/r2_smoke/extractions_v2.json`
- OCR: `pipeline/reports/r2_ocr/`

### V2 accepted incidents (local only)

1. **CIA-UAP-D001** — Green circular object at Sary Shagan, Summer 1973  
2–8. **DOW-UAP-D017** — seven green-fireball / light episodes (1948–49)

### Evidence-insufficient (kept as source/media, not public incidents)

- **DOE-UAP-D001** Pantex caption (`excerpt_too_few_words` / thin media)  
- 2 DOW thin/caption-like excerpts lacking observation language  

## What was built

1. **Frozen classifier baseline** — `pipeline/tests/fixtures/r2_smoke/` + fixture regression test.  
2. **Page quality scoring** — `pipeline/text_quality.py` (`native_good` / `native_thin` / `needs_ocr` / `ocr_failed`).  
3. **Selective local OCR** — `pipeline/local_ocr.py` (PyMuPDF 300 DPI → Tesseract), page files + `combined.txt` with `--- PAGE N ---`.  
4. **Extraction prompt v1.1** — `raw_excerpt` must preserve OCR typos; summary may clean.  
5. **Evidence sufficiency gate** — deterministic; thin captions ≠ incidents.  
6. **JSON retry** — one controlled re-ask; no silent JSON repair; `JSON_STATS` telemetry.  
7. **Classifier tweak** — strong historical cues beat letter-form false positives (years alone do not).

## OCR page stats

| Document | Pages | OCR'd | OCR ok | Usable chars (after) |
|----------|------:|------:|-------:|---------------------:|
| CIA-UAP-D001 | 3 | 3 (force) | 3 | 4,032 |
| DOE-UAP-D001 | 2 | 1 | 1 | 429 |
| DOE-UAP-D002 | 4 | 4 | 3 | 1,148 |
| DOE-UAP-D003 | 1 | 1 | 1 | 562 |
| DOW-UAP-D017 | 116 | 77 | 75 | 115,816 |

DOW char count **fell** vs raw pypdf (167k → 116k) because garbage/mojibake was replaced with shorter clean OCR — quality over bulk.

CIA required `--force-ocr-all` for page 3: native layer scored `native_good` by length but still garbled; soft-hyphen / garbled-token signals were tightened afterward.

## Commands (local)

```bash
# OCR benchmark targets (then remaining smoke PDFs)
pipeline/.venv/bin/python -m pipeline.local_ocr --pdfs CIA-UAP-D001 --force-ocr-all
pipeline/.venv/bin/python -m pipeline.local_ocr --pdfs DOW-UAP-D017
pipeline/.venv/bin/python -m pipeline.local_ocr --pdfs DOE-UAP-D001 DOE-UAP-D002 DOE-UAP-D003

# Same five-document smoke
pipeline/.venv/bin/python -m pipeline.classify_document --local-cache .cache/files/pursue/r2 --limit 5
pipeline/.venv/bin/python -m pipeline.smoke_r2_extract --label v2

# Regression
pipeline/.venv/bin/python -m pipeline.tests.test_classify_document
pipeline/.venv/bin/python -m pipeline.tests.test_r2_smoke_classifier_fixtures
pipeline/.venv/bin/python -m pipeline.tests.test_text_quality
pipeline/.venv/bin/python -m pipeline.tests.test_evidence_sufficiency
pipeline/.venv/bin/python -m pipeline.tests.test_validation
```

## Explicit non-goals (still hold)

- No broader R2 run yet  
- No Supabase mutations / migrations applied  
- No Vercel deploy  
- No GPT-6 / Ask changes  
- Do **not** weaken `_validate_incident` matching tolerance

## Recommended next move (after review)

A **representative ~15–20 PDF local R2 sample** (not full R2) measuring class mix, OCR pages, yield, JSON failures, Haiku cost, and time — then decide readiness for any production path.

**STOP.**
