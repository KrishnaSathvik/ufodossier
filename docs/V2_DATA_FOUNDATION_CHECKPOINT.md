# UFO Dossier v2 — Data Foundation Checkpoint

**Stopped after milestone step 17 (smoke test).**  
Full R02–R06 extraction / GPT-6 / UI **not run**.

## Checklist

| Step | Status |
|------|--------|
| DB migrations 004–006 (registry, media, stats) | **PASS** (applied) |
| Migration 007 `incident_sources` | **PASS** (live; 476 rows) |
| Production corpus unchanged after schema | **PASS** — incidents **480**, unflagged **380**, flagged **100** |
| R01 reconcile dry-run | **PASS** — 0 ambiguous |
| R01 populate + link | **PASS** — 158 records, 155 files linked |
| `V2_R01_RECONCILIATION.md` | **PASS** |
| curl_cffi official client | **PASS** (do not override UA under impersonation) |
| Official `uap-data.csv` fetch | **PASS** — **450** records |
| Official vs community diff | **PASS** — +3 LLE PDFs documented |
| R02–R06 metadata import | **PASS** — **450** `source_records` total |
| `fetch_assets.py` | **PASS** |
| 5-PDF smoke test (R2) | **PASS** — 5/5 downloaded + checksummed; 4/5 in Storage (1× 68MB hit 413 limit, kept local) |
| Full extraction | **NOT RUN** |
| GPT-6 | **OFF** |
| `/releases` `/sources` UI | **NOT BUILT** |

## Current production inventory (post-checkpoint)

```text
incidents:         480  (unchanged)
unflagged:         380
flagged:           100
source_files:      181  (+5 R2 smoke PDFs)
source_records:    450  (R1–R6 metadata)
incident_sources:  476
```

### source_records by release

```text
R1 158
R2  64
R3  72
R4  40
R5  41
R6  75
───
   450
```

### source_records by type

```text
pdf   270
video 134
image  30
audio  16
```

## Commands that work now

```bash
# use project venv
.venv-v2/bin/python -m pipeline.discover --provider pursue --snapshot-date 2026-09-18
.venv-v2/bin/python -m pipeline.reconcile --provider pursue --release 1 --dry-run
.venv-v2/bin/python -m pipeline.import_source_records --all --apply
.venv-v2/bin/python -m pipeline.fetch_assets --provider pursue --release 2 --type pdf --limit 5 --dry-run
```

## Known follow-ups (next milestone)

1. Raise Supabase Storage object size limit (or multipart) for large PDFs (~68MB+).  
2. Manual review of 3 R01 PDF URL-drift cases.  
3. Document classifier before Haiku on new PDFs.  
4. Incremental extract R2→R6 with `--limit 5` gates.  
5. Then `/releases` + `/sources` UI.
