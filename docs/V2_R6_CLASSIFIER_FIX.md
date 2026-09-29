# V2 R6 classifier fix

**Date:** 2026-09-28  
**Mode:** Local only. No Supabase writes, no deploy, no GPT-6.  
**Scope:** Classifier precedence only. Linker V1, quote gate, evidence gate, OCR, and truncation logic **unchanged**.

## Verdict

### **R6_LOCAL_COMPLETE** *(clears `NEEDS_CLASSIFIER_FIX`)*

Six false `extract` routes are now `source_only`. Accepted incident count stays **15**. Linker regression still **pass** (196 events / 1 series).

---

## Failure mode (pre-fix)

OCR splits the DIRD banner across newlines:

```text
Defense
Intelligence
Reference
Document
```

The old regex required a single-line phrase, so DIRD detection missed. Bibliography years (e.g. `1964`) then promoted docs to `historical_case_file` / `extract`.

Personnel file **DOW-UAP-D104** likewise fell through to year-based historical despite dense service-record vocabulary.

---

## Fix (content signals, not filenames)

In `pipeline/classify_document.py`:

1. **Whitespace-flexible DIRD** — `defense\s+intelligence\s+reference\s+document` / `\bdird\b`
2. **Research phrases** (tightened after R2 fixture check) — technical report, state of the art, nuclear propulsion, gravitational waves, Drake equation, acquisition threat support, etc. Removed bare `propulsion` (false-positive on DOE-UAP-D002 correspondence).
3. **New class `personnel_record`** — personnel/service-history / BUPERS cues with density gate; `contains_incidents=false`
4. **Encounter override** — strong primary encounter narrative still wins over research/personnel

Precedence:

```text
strong primary encounter → incident-bearing
otherwise DIRD/research/personnel/program → source_only
```

---

## Fixtures

`pipeline/tests/fixtures/r6_classifier/` + `pipeline/tests/test_r6_classifier_fixtures.py`

| Role | IDs | Expected |
|---|---|---|
| Negative refute | D104 | `personnel_record` / source_only |
| Negative refute | D124, D126, D127, D137, D140 | `research_paper` / source_only |
| Positive control | D142, D143, D144, D145, D150, D153 | `research_paper` / source_only |

Regression runs (no network):

```text
python -m pipeline.tests.test_r2_smoke_classifier_fixtures   # PASS
python -m pipeline.tests.test_r3_classifier_fixtures          # PASS
python -m pipeline.tests.test_r6_classifier_fixtures          # PASS
```

---

## Re-run (affected IDs only)

Reclassified in place (OCR reused; no Haiku):

| File | Before | After |
|---|---|---|
| DOW-UAP-D104 | historical_case_file / extract | personnel_record / source_only |
| DOW-UAP-D124 | historical_case_file / extract | research_paper / source_only |
| DOW-UAP-D126 | historical_case_file / extract | research_paper / source_only |
| DOW-UAP-D127 | historical_case_file / extract | research_paper / source_only |
| DOW-UAP-D137 | historical_case_file / extract | research_paper / source_only |
| DOW-UAP-D140 | historical_case_file / extract | research_paper / source_only |

Corpus disposition:

| Metric | Before | After |
|---|---:|---:|
| extract | 13 | **7** |
| source_only | 46 | **52** |
| accepted incidents | 15 | **15** |

Stage B had nothing to redo for those six (they never contributed accepted rows).

---

## Linker (unchanged V1)

R2–R6 accepted corpus re-linked:

| Metric | Value |
|---|---:|
| accepted incidents | 203 (12+150+16+10+15) |
| canonical events | 196 |
| event series | 1 |
| linker regression | pass |
| Colorado / Western US / D082 | pass / pass / 12→5 |

Counts stable vs pre-fix link — classifier-only change produced no new accepted incidents.

---

## Gate

| Check | Status |
|---|---|
| DIRD false extracts | 0 |
| personnel false extracts | 0 |
| R2/R3/R6 classifier fixtures | PASS |
| accepted incidents unchanged | 15 |
| quote / evidence rules | unchanged |
| linker regression | PASS |
| unexplained extract→0 | 0 |
| production writes / deploy / GPT-6 | 0 / 0 / off |

### **R6_LOCAL_COMPLETE**

Next phase: **full R1–R6 corpus QA** (no further release-by-release engineering unless QA forces it).
