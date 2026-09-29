# V2 R3 Readiness Sample (local-only)

**Date:** 2026-09-25  
**Mode:** Local / read-only vs production — **no writes, no deploy, no GPT-6**

## Verdict

### **NEEDS_CLASSIFIER_FIX**

Secondary flags (do not ignore):

| Flag | Why |
|------|-----|
| **NEEDS_EXTRACTION_FIX** (partial) | `FBI-UAP-D012` (66 pp historical multi-case) → **0 candidates** |
| **NEEDS_OCR_FIX** (partial) | `DOW-UAP-D085` (169 chars / 5 OCR fails); `CIA-UAP-009` nearly empty; `FBI-UAP-D003` image packet OCR noise |
| **NEEDS_DEDUPE_MODEL** (deferred) | Colorado Springs cluster never produced ≥2 accepted sources to link — classifier/OCR gated them first |

**Not** `READY_FOR_BROADER_LOCAL_PROCESSING` yet.

---

## Stage B stop-gate totals

```text
10 extracted documents
40 candidate incidents
30 quote-valid
10 quote-rejected
 6 evidence-insufficient
24 accepted

new_event                 24
same_event_new_source      0
likely_duplicate           0
uncertain                  0

JSON first-pass success   29
JSON retry success         1
JSON retry failure         2

estimated Haiku calls     ~35
estimated cost            ~$0.70
runtime                   358.5s
production writes          0
```

Artifacts: `pipeline/reports/r3_readiness/`  
(`classifications.json`, `text_quality.json`, `extractions.json`, `dedupe_candidates.json`, `metrics.json`, `per_document_metrics.json`, `sample_manifest.json`)

---

## Stage A classifier (sanity vs actual)

| Expected band | Actual |
|---------------|--------|
| ~10 incident-bearing | **10 extract** |
| ~5–8 source-only | **8 source_only** |

Notable mismatches (review, not auto-fix):

| Doc | Expected intuition | Actual | Issue |
|------|-------------------|--------|-------|
| **USG-UAP-D001** | admin/correspondence → source_only | correspondence **extract** → **11 accepted** | Catalog letters mined as incidents — **primary classifier miss** |
| **CIA-UAP-003** | program/history → source_only | historical **extract** | Softened by Stage B: only **1** accepted (U-2/BLUE BOOK) |
| **CIA-UAP-005** | research → source_only | historical extract → **0** yield | Harmless but wasted call |
| **CIA-UAP-006** | short eyewitness → extract | **administrative** source_only | Possible false skip |
| **CIA-UAP-009** | historical incident → extract | **other** source_only | OCR collapse (126 chars) |
| **FBI-UAP-D011** | correspondence w/ encounter → extract | correspondence **source_only** | Encounter cues missed |
| **ICA-UAP-D001** | analysis (judgment) | **other** source_only | Correct disposition; class label weak |
| **DOW-UAP-D077** | analysis | **analysis** source_only | Good |
| **FBI-UAP-D003** | media | **other** source_only | Correct disposition; OCR useless |

---

## Stress case reviews

### 1. Colorado Springs cluster — **INCONCLUSIVE / blocked upstream**

| Source | Stage A | Stage B |
|--------|---------|---------|
| FBI-UAP-D002 | extract (transcript) | **1 candidate → quote-rejected** (OCR-spaced excerpt ≠ source) |
| FBI-UAP-D003 | source_only | — (image/noise) |
| ICA-UAP-D001 | source_only | — (analysis text present; classified `other`) |

ICA text *does* describe Cheyenne Mountain / Fort Carson 2022 and assesses backscattering — correctly kept non-incident, but never entered dedupe as `same_event_new_source`.

**Conclusion:** Multi-source linking was not exercised. Fix OCR/quote fidelity on FBI-D002 and treat ICA as `analysis` / linked source before claiming dedupe readiness.

### 2. CIA-UAP-016 multi-incident — **PASS**

- Candidates 7 → accepted **5** distinct Himalayan/South Asia sightings (Ladakh, Sikkim, Bhutan, Nepal)
- Separate excerpts per event; 1 quote-reject + 1 evidence-drop
- Demonstrates one-source → many-incidents path works when text is usable

### 3. FBI-UAP-D012 historical multi-case — **FAIL**

- 66 pages, 121k chars after selective OCR
- Opening pages are indices/routing slips
- Haiku returned **[]** — zero candidates
- No duplicate explosion (good) but also **no recovery** of embedded sightings

**Conclusion:** Large collection files need page-routing / section-aware chunking or stronger OCR before broader R3 historical FBI sets.

### 4. CIA-UAP-003 inflation watch — **PASS (restraint)**

- ~756k chars / 13 Haiku chunks
- Candidates 2 → accepted **1** (U-2 flights mistaken for UFOs)
- TOC-line evidence correctly insufficient-gated
- Model did **not** invent dozens of program mentions as incidents

### 5. NASA-UAP-D016 transcript — **PASS (gates held)**

- 340 pages / 372k chars
- 1 quote-valid candidate → **evidence-insufficient** (`excerpt_lacks_observation_language` — Gemini rendezvous phrasing)
- No false accepted transcript merges

---

## Safety checklist

```text
fabricated accepted incidents (observed)   0 clear fabrications
unsupported accepted (thin captions)       0 (Pantex-style gate held)
quote tolerance weakened                   NO
obvious admin false positives              YES — USG-UAP-D001 (11)
obvious incident docs skipped              CIA-006?, CIA-009 (OCR), FBI-D011?
OCR failures reported                      YES (not hidden)
JSON retry path                            worked (1 success / 2 fail)
production writes                          0
```

---

## Recommended next engineering order

1. **Classifier:** treat USG-style catalog/referral correspondence as `source_only` unless primary encounter narrative; label ICA-like assessments as `analysis`.  
2. **FBI-UAP-D012 path:** diagnose empty extract (chunk strategy / OCR of body pages vs index pages).  
3. **Colorado Springs:** re-OCR FBI-D002; keep ICA as analysis source; only then design `same_event_new_source` linking.  
4. **Do not** run full local R3 until (1) lands and FBI-D012 is understood.

---

## Prior checkpoint (still valid)

- R2 complete locally 6/6 — `docs/V2_R2_COMPLETE_LOCAL.md`
- ODNI-UAP-D001: 4 accepted

**STOP.**
