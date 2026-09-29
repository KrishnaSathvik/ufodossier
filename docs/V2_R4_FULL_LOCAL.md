# V2 R4 full local run

**Date:** 2026-09-28  
**Mode:** Local only. No Supabase writes, no Vercel deploy, no GPT-6.  
**Corpus:** all Release 04 records in the 2026-09-18 PURSUE snapshot (17 records: 14 PDFs + 3 NASA images).  
**Frozen:** classifier decision logic, selective OCR, cue router rules, quote validator, evidence sufficiency, JSON `max_tokens=4096` with truncation→page subdivision (unchanged from R3 truncation fix).  
**Artifacts:** `pipeline/reports/r4_local/`  
**Orchestrator:** `python -m pipeline.r4_local`

## Verdict

### **R4_LOCAL_COMPLETE**

Linker V1 generalized to the R2+R3+R4 local corpus without regression failures. Extraction gates held. Truncation on DOE-UAP-D004 subdivided cleanly (`extraction_failed=0`). Two extract-class files landed at zero accepted because the quote gate dropped OCR-mangled excerpts — explained, not unexplained.

---

## What stayed frozen

Unchanged:

- classifier rules (no mid-run retune)
- selective OCR / thumbnail skip
- page router (`auto` cue-route thresholds)
- quote-safe normalization + 90% word window
- evidence sufficiency
- JSON path: one malformed retry; `max_tokens` truncation → page-boundary subdivision (no output-cap increase)
- canonical linker V1 relationship rules

---

## Corpus

| Metric | Value |
|---|---:|
| records total | 17 |
| PDFs | 14 |
| images | 3 (NASA-UAP-D030/031/032) |
| video / audio | 0 / 0 |
| agencies | CIA 2, DOE 2, DoW 9, FBI 1, NASA 3 |
| PDF cache bytes | ~223 MB (234,090,892) |
| already cached at inventory | 14 / 14 |
| pages total | 558 |
| pages OCR'd | 441 |
| OCR failed | 132 |
| classified extract | 8 |
| classified source_only | 6 |
| Stage A runtime | 5,277.9s |
| production writes | 0 |
| deploy | 0 |
| GPT-6 | off |

### Known pairings (catalog)

| Left | Right |
|---|---|
| CIA-UAP-D020 | CIA-UAP-D021 |
| DOE-UAP-D005 | DOE-UAP-D001 |
| NASA-UAP-D030 | D031 \| D032 |
| NASA-UAP-D031 | D030 \| D032 |
| NASA-UAP-D032 | D029 \| D031 |

Media (NASA STS-80 stills): metadata + pairing only — no deep media AI.

### Stage A classifications (frozen)

| File | pages | OCR fail | class | action | strategy | warning |
|---|---:|---:|---|---|---|---|
| CIA-UAP-D020 | 3 | 0 | historical_case_file | extract | fixed | — |
| CIA-UAP-D021 | 4 | 0 | historical_case_file | extract | fixed | — |
| DOE-UAP-D004 | 25 | 11 | historical_case_file | extract | fixed | OCR-poor |
| DOE-UAP-D005 | 7 | 0 | correspondence | extract | fixed | — |
| DOW-UAP-D089 | 2 | 0 | transcript | extract | fixed | — |
| DOW-UAP-D090 | 2 | 0 | other | source_only | — | — |
| DOW-UAP-D091 | 2 | 0 | transcript | extract | fixed | — |
| DOW-UAP-D092 | 85 | 10 | contract | source_only | — | — |
| DOW-UAP-D093 | 67 | 16 | administrative | source_only | — | — |
| DOW-UAP-D094 | 34 | 8 | analysis | source_only | — | — |
| DOW-UAP-D095 | 57 | 11 | correspondence | source_only | — | — |
| DOW-UAP-D096 | 220 | 75 | correspondence | source_only | — | huge, OCR-poor |
| DOW-UAP-D097 | 45 | 1 | historical_case_file | extract | fixed | — |
| FBI-UAP-D014 | 5 | 0 | correspondence | extract | fixed | — |

Cue-routing did not fire on R4 (all extract plans `fixed`).

---

## Extraction

| Metric | Value |
|---|---:|
| documents extracted | 8 |
| candidates | 28 |
| quote-valid | 25 |
| quote-rejected | 3 |
| evidence-insufficient | 9 |
| accepted | 16 |
| truncations (`stop_reason=max_tokens`) | 1 (DOE-UAP-D004) |
| sections subdivided | 1 |
| JSON first pass | 10 |
| JSON retry success | 0 |
| JSON retry failure | 1 (subdivided half of D004; sibling half recovered) |
| extraction_failed | 0 |
| Haiku calls | 13 |
| cost (ballpark $0.02/call) | $0.26 |
| extract runtime | 204.8s |
| quote rules changed | no |
| evidence gate changed | no |

### Accepted by source

| File | accepted | quote-rej | evidence-insuf |
|---|---:|---:|---:|
| CIA-UAP-D020 | 0 | 1 | 0 |
| CIA-UAP-D021 | 1 | 0 | 0 |
| DOE-UAP-D004 | 10 | 1 | 4 |
| DOE-UAP-D005 | 0 | 1 | 0 |
| DOW-UAP-D089 | 1 | 0 | 0 |
| DOW-UAP-D091 | 1 | 0 | 0 |
| DOW-UAP-D097 | 1 | 0 | 5 |
| FBI-UAP-D014 | 2 | 0 | 0 |

### Truncation path

DOE-UAP-D004 (25 pp, heavy OCR): first section hit `max_tokens` → page split 21→10+11 → continued extraction. One subdivided JSON reply failed after the single retry; overall file still produced 10 accepted rows. **Truncation loss = 0** (`extraction_failed=0`).

### Extract → 0 accepted (explained)

- **CIA-UAP-D020** — Haiku proposed one incident; quote gate rejected OCR-garbled excerpt (`sbout`/`mimstes`/`Alyaty`). Catalog pair with D021; D021 accepted a Prague sighting independently.
- **DOE-UAP-D005** — quote gate rejected; paired catalog target DOE-UAP-D001 is outside this R4 extract set.

Neither is unexplained zero-candidate truncation loss.

---

## Identity (linker V1 on R2 + R3 + R4)

Input corpus: **12** R2 + **150** R3 + **16** R4 = **178** accepted local incidents.

| Metric | Value |
|---|---:|
| canonical events | 171 |
| event series | 1 (Western US) |
| candidates generated | 65 |
| auto/review decisions | 54 |
| rejected pairs | 20 |
| same_event | 3 |
| same_series | 49 |
| media_for_event | 1 |
| analysis_of_event | 1 |
| needs_review links | 0 (1 `review_supported` decision status) |
| Colorado Springs fixture | pass |
| Western US series fixture | pass |
| linker regression | **pass** (0 failures) |

### Linker failure checks

| Check | Observed |
|---|---|
| one incident → multiple canonical events | 0 |
| contradictory dates on one event | 0 |
| generic-location auto merge | 0 |
| source_only → event inflation | 0 |
| generic “western United States” candidates auto-merged | 0 (20 explicit rejections for generic location) |

R4-accepted rows did not form new cross-release `same_event` decisions in this pass; prior-corpus fixtures (Colorado Springs media/analysis, Western US series) remain intact. Catalog CIA-D020↔D021 analysis link could not auto-attach because D020 has no accepted observation after the quote gate.

---

## Quality / review alarms

Review only (do not fail the gate). `pipeline/reports/r4_local/needs_review.json` — **9** alarms:

| Alarm | Files |
|---|---|
| `extract_zero_accepted` | CIA-UAP-D020, DOE-UAP-D005 |
| `high_yield` | DOE-UAP-D004 (10 accepted / 15 candidates) |
| `high_ocr_failure` / `ocr_failure_gt20pct` | DOE-UAP-D004 (44%), DOW-UAP-D093 (24%), DOW-UAP-D094 (24%), DOW-UAP-D096 (34%) |

Notes for later review (not blockers):

- DOW-UAP-D090 classified `source_only` / `other` while sibling range-fouler transcripts D089/D091 extracted — frozen classifier regression signal, not retuned mid-run.
- DOW-UAP-D096 (220 pp, 75 OCR failures) correctly stayed `source_only` correspondence; huge OCR cost already paid in Stage A.
- External-id collision: R4 `FBI-UAP-D014` is a PDF; R3 had an IMG with the same id. Fetch used release-scoped inventory URLs (not the CSV type-key index) so the PDF cached correctly.

---

## Stop gate

| Requirement | Status |
|---|---|
| fabricated accepted incidents observed | 0 |
| catalog/admin inflation | 0 |
| thin-caption incidents | 0 |
| quote rules unchanged | yes |
| evidence gate unchanged | yes |
| truncation loss | 0 |
| unexplained extract→0 | 0 |
| generic-location auto merges | 0 |
| cross-date auto merges | 0 |
| source_only → event inflation | 0 |
| auto-supported links explainable | yes |
| production writes | 0 |
| deploy | 0 |
| GPT-6 | off |

### **R4_LOCAL_COMPLETE**

---

## After R4

Per plan — do **not** redesign the linker yet:

```text
R4_LOCAL_COMPLETE
      ↓
linker regression review (human)
      ↓
small linker V1.1 tune if needed
      ↓
R5 LOCAL
```

Artifacts to inspect first: `pipeline/reports/r4_local/metrics.json`, `needs_review.json`, `linker_regression.json`, `linker/`.
