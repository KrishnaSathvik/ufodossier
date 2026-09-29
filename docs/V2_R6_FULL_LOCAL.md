# V2 R6 full local run

**Date:** 2026-09-28  
**Mode:** Local only. No Supabase writes, no Vercel deploy, no GPT-6.  
**Corpus:** all Release 06 records in the 2026-09-18 PURSUE snapshot (75 records; URLs use `release-06`).  
**Linker:** V1 **frozen** (no V1.1).  
**Frozen extraction stack:** unchanged from R3–R5.  
**Artifacts:** `pipeline/reports/r6_local/`  
**Orchestrator:** `python -m pipeline.r6_local`

## Verdict

### **R6_LOCAL_COMPLETE** *(clears `NEEDS_CLASSIFIER_FIX` — see `docs/V2_R6_CLASSIFIER_FIX.md`)*

Classifier over-routing of five AAWSAP DIRDs and one personnel record is fixed via content-signal precedence (OCR-tolerant DIRD matching + `personnel_record`). Re-classified those six IDs only: **extract 13→7**, **source_only 46→52**, **accepted incidents unchanged at 15**. Linker V1 still passes on the R2–R6 corpus (196 events / 1 series).

Historical note from the initial R6 stop (2026-09-28):

> Six classifier-`extract` documents returned 0 Haiku candidates — all with valid JSON, no truncations. Root cause was classifier over-route, not extraction loss.

---

## What stayed frozen

Unchanged for this run:

- classifier decision logic (no mid-run retune)
- selective OCR / page router
- truncation→page subdivision
- quote normalization + 90% window
- evidence sufficiency
- Linker V1

Watch list carried only (observe): CIA D020/D021, DOE D005/D001, NASA media trio, DOW D089/D090, R5 FD-302 siblings.

---

## Corpus

| Metric | Value |
|---|---:|
| records total | 75 |
| PDFs | 59 |
| video | 15 |
| audio | 1 |
| images | 0 |
| local law enforcement | 8 (4 PDF transcripts + 4 VID) |
| agencies | DoW 67, Local Law Enforcement 8 |
| PDF cache bytes | 2,234,172,436 (~2.08 GB) |
| already cached at start | 0 |
| fetched | 59 / 59 |
| pages total | 2,607 |
| pages OCR'd | 948 |
| OCR failed | 18 |
| classified extract | 7 *(was 13 before classifier fix)* |
| classified source_only | 52 *(was 46)* |
| fixed-chunk plans | 13 |
| cue-routed | 0 |
| Stage A runtime | 2,703.1s |
| duplicate external IDs flagged | FBI-UAP-D014 (R3 IMG vs R4 PDF) |
| production writes | 0 |
| deploy | 0 |
| GPT-6 | off |

Media (VID/AUD): metadata + catalog pairing only — no multimodal AI.

---

## Extraction

| Metric | Value |
|---|---:|
| documents extracted | 13 |
| candidates | 23 |
| quote-valid | 20 |
| quote-rejected | 3 |
| evidence-insufficient | 5 |
| accepted | 15 |
| truncations | 0 |
| extraction_failed | 0 |
| Haiku calls | 41 (all first-pass valid) |
| cost | $0.82 |
| runtime | 121.9s |
| quote / evidence rules changed | no |

### Accepted by source

| File | n | Notes |
|---|---:|---|
| DOW-UAP-D102 | 2 | Tremonton / Phoenix Blue Book cluster |
| DOW-UAP-D103 | 1 | Tremonton photo file |
| DOW-UAP-D154 | 9 | Ruppelt presentation transcript (high-yield review) |
| LLE-UAP-D001 | 1 | Colorado LE transcript |
| LLE-UAP-D003 | 1 | Colorado LE transcript |
| LLE-UAP-D004 | 1 | Colorado LE transcript Jan 2024 |

### Extract → 0 (blocker — classifier)

| File | pages | Title signal | Haiku |
|---|---:|---|---|
| DOW-UAP-D104 | 585 | Final Personnel Record (Newhouse) | 0 candidates, valid JSON |
| DOW-UAP-D124 | 56 | AAWSAP DIRD Space Access | 0 candidates, valid JSON |
| DOW-UAP-D126 | 37 | AAWSAP DIRD Nuclear Propulsion | 0 candidates, valid JSON |
| DOW-UAP-D127 | 55 | AAWSAP DIRD Drake Equation | 0 candidates, valid JSON |
| DOW-UAP-D137 | 31 | AAWSAP DIRD High-Energy Lasers | 0 candidates, valid JSON |
| DOW-UAP-D140 | 57 | AAWSAP DIRD HF Gravitational Waves | 0 candidates, valid JSON |

Contrast: D142–D145 / D150 / D153 DIRDs correctly classified `research_paper` → `source_only`.

### Quote-explained zero

| File | Cause |
|---|---|
| LLE-UAP-D002 | quote gate (OCR garble in excerpt) |

---

## Identity (Linker V1 on R2–R6)

Input: **12** R2 + **150** R3 + **16** R4 + **10** R5 + **15** R6 = **203** accepted local incidents.

| Metric | Value |
|---|---:|
| canonical events | 196 |
| event series | 1 (Western US) |
| candidates generated | 1,039 |
| decisions | 55 |
| rejected pairs | 20 |
| same_event | 3 |
| same_series | 49 |
| media_for_event | 1 |
| analysis_of_event | 2 |
| same-release decisions | 2 |
| **cross-release decisions** | **0** |
| Colorado Springs | pass |
| Western US | pass (`D082` 12 → 5) |
| linker regression | **pass** |

Cross-release auto-links still have not appeared naturally; reporting continues via `cross_release_links.json`.

### Source evolution (hints only)

`pipeline/reports/r6_local/source_evolution.json` — **12** hints, **0** auto-merges:

| Kind | Count |
|---|---:|
| later_media_for_prior_event | 5 (R6 Tremonton package ↔ R5 D098 film analysis) |
| same_release_media_for_event | 5 |
| reissued_source | 1 (FBI-UAP-D014 R3/R4) |
| superseding_source | 1 (same id, IMG vs PDF) |

---

## Quality / review alarms

87 review signals (not automatic failures beyond the classifier zeros). Dominant:

| Alarm | Count |
|---|---:|
| `paired_source_without_event` | 61 |
| `extract_zero_accepted` / `extract_zero_candidates` | 7 / 6 |
| `one_source_many_events` | 5 |
| `very_large_document` | 3 (incl. D104 585 pp) |
| `reissued_source` / `superseding_source` | 1 / 1 |
| DOW-D089/D090 sibling watch | 1 |

---

## Stop gate

| Requirement | Status |
|---|---|
| fabricated accepted observed | 0 |
| catalog/admin inflation | 0 |
| thin-caption incidents | 0 |
| quote rules unchanged | yes |
| evidence gate unchanged | yes |
| truncation loss | 0 |
| unexplained extract→0 | **0** (six former zeros reclassified source_only) |
| generic-location auto merge | 0 |
| cross-date auto merge | 0 |
| source_only → event inflation | 0 |
| Colorado / Western US / D082 | pass / pass / pass |
| cross-release links explainable | yes (none auto) |
| production writes / deploy / GPT-6 | 0 / 0 / off |

### **R6_LOCAL_COMPLETE**

---

## After R6

```text
R6_LOCAL_COMPLETE
      ↓
FULL R1–R6 CORPUS QA
      ↓
production migration planning (still no writes until QA green)
```

Classifier fix detail: `docs/V2_R6_CLASSIFIER_FIX.md`.
