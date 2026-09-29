# V2 R2 Classifier Smoke (local-only)

**Date:** 2026-09-25  
**Mode:** Local / test-only — **no production writes, no Vercel deploy, no feature flags, no GPT-6**

## Stop gate

> Local R2 smoke test passes completely before any production migration, ingestion write, or deployment.

This document covers the **classifier** half of that gate.

## Command

```bash
pipeline/.venv/bin/python -m pipeline.tests.test_classify_document
pipeline/.venv/bin/python -m pipeline.classify_document \
  --local-cache .cache/files/pursue/r2 --limit 5
```

`--apply` is hard-refused (would write classifications to production).

## Unit tests

`pipeline/tests/test_classify_document.py` — **7/7 pass** (rules only, no network).

Coverage: incident report, historical case file, contract, research/DIRD, administrative invitation, correspondence with encounter, correspondence topic-only.

## Smoke inputs

Five PDFs already cached at `.cache/files/pursue/r2/`:

| File | Bytes | Pages | Text chars (pypdf) |
|------|------:|------:|-------------------:|
| CIA-UAP-D001.pdf | 154 KB | 3 | 4,188 |
| DOE-UAP-D001.pdf | 164 KB | 2 | 438 |
| DOE-UAP-D002.pdf | 554 KB | 4 | 1,248 |
| DOE-UAP-D003.pdf | 360 KB | 1 | 593 |
| DOW-UAP-D017.pdf | 68.8 MB | 116 | 167,669 |

OCR note: many DOW pages are scans (`<100` chars from pypdf). Tesseract deps are not installed in this smoke environment, so those pages stay thin/noisy. Classifier still runs on available text.

## Results

Report: `pipeline/reports/r2_smoke/classifications.json`  
Texts: `pipeline/reports/r2_smoke/texts/*.txt`

| File | Class | contains_incidents | Action |
|------|-------|--------------------|--------|
| CIA-UAP-D001.pdf | historical_case_file | true | **extract** |
| DOE-UAP-D001.pdf | incident_report | true | **extract** |
| DOE-UAP-D002.pdf | correspondence | false | source_only |
| DOE-UAP-D003.pdf | administrative | false | source_only |
| DOW-UAP-D017.pdf | historical_case_file | true | **extract** |

**Skipped by classifier: 2 / 5** (D002 letter requesting a recipe / Condon book reference; D003 Pajarito Astronomers meeting invitation with UFO lecture topic).

## Design notes that matter

1. Agency filenames like `DOE-UAP-D003` must **not** count as UAP topic hits (hyphenated ID false positive fixed).
2. Admin/invitation language wins even if the talk topic mentions UFOs.
3. Correspondence requires **encounter** cues (`sighting`, `observed …`, etc.), not bare “UFO” topic mention.
4. DIRD / research vocabulary classifies as `research_paper` with `contains_incidents=false` (before contract).

## Production impact

**None.** No Supabase writes. No schema applied. No Vercel changes.

## Gate status (classifier)

**PASS** — deterministic classifier + local OCR text + report artifacts ready for review.
