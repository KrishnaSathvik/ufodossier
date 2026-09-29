# V2 R5 full local run

**Date:** 2026-09-28  
**Mode:** Local only. No Supabase writes, no Vercel deploy, no GPT-6.  
**Corpus:** all Release 05 records in the 2026-09-18 PURSUE snapshot (25 records: 22 PDFs + 3 FBI JPG renderings).  
**Linker:** V1 **frozen** (no V1.1). R4 human review: `docs/V2_LINKER_V1_R4_REVIEW.md`.  
**Frozen extraction stack:** classifier, selective OCR, cue router, quote gate, evidence gate, `max_tokens=4096` + truncation→page subdivision.  
**Artifacts:** `pipeline/reports/r5_local/`  
**Orchestrator:** `python -m pipeline.r5_local`

## Verdict

### **R5_LOCAL_COMPLETE**

R5 challenged the frozen stack with new agencies (DOS, EOP), dense FBI FD-302 / rendering pairs, and two large DoW PDFs. Extraction gates held. Linker V1 preserved Colorado Springs and Western US fixtures on the full R2–R5 local corpus. Cross-release auto-links remain **0** (reporting only — expected at this stage).

---

## Preceding decision (R4 review)

| Check | Result |
|---|---|
| bad `same_event` | none |
| obvious missed strong pairing | none |
| series overmerge | none |
| **Linker V1.1** | **not started** |

Carry-forward watch cases recorded in `pipeline/reports/r5_local/regression_watch.json` (CIA D020/D021, DOE D005/D001, NASA D030–032, DOW-D090 sibling).

---

## Corpus

| Metric | Value |
|---|---:|
| records total | 25 |
| PDFs | 22 |
| images | 3 (FBI-UAP-D025/D029/D031 JPG) |
| video / audio | 0 / 0 |
| agencies | FBI 16, DoW 4, CIA 2, DOS 2, EOP 1 |
| PDF cache bytes | 127,047,244 (~121 MB) |
| pages total | 332 |
| pages OCR'd | 196 |
| OCR failed | 16 |
| classified extract | 9 |
| classified source_only | 13 |
| fixed-chunk extract plans | 9 |
| cue-routed | 0 |
| Stage A runtime | 936.9s |
| production writes | 0 |
| deploy | 0 |
| GPT-6 | off |

Notable large files (both correctly `source_only`):

- **DOW-UAP-D098** — 23 pp / ~63 MB (film analysis; classified correspondence)
- **DOW-UAP-D100** — 245 pp / ~39 MB (classified correspondence)

### Stage A extract set

| File | class | action | pages | OCR fail |
|---|---|---|---:|---:|
| CIA-UAP-D023 | incident_report | extract | 2 | 0 |
| DOS-UAP-D002 | historical_case_file | extract | 2 | 0 |
| DOW-UAP-D099 | historical_case_file | extract | 8 | 2 |
| DOW-UAP-D101 | incident_report | extract | 7 | 0 |
| FBI-UAP-D024 | transcript | extract | 3 | 0 |
| FBI-UAP-D026 | incident_report | extract | 3 | 0 |
| FBI-UAP-D028 | incident_report | extract | 3 | 0 |
| FBI-UAP-D030 | transcript | extract | 3 | 0 |
| FBI-UAP-D033 | incident_report | extract | 2 | 0 |

Paired analysis / cables / renderings stayed `source_only` (CIA-D022, DOS-D001, EOP-D001, most digital-rendering PDFs, thin-OCR JPGs not fetched as PDFs).

---

## Extraction

| Metric | Value |
|---|---:|
| documents extracted | 9 |
| candidates | 15 |
| quote-valid | 10 |
| quote-rejected | 5 |
| evidence-insufficient | 0 |
| accepted | 10 |
| truncations | 0 |
| extraction_failed | 0 |
| Haiku calls | 9 |
| cost | $0.18 |
| runtime | 61.7s |
| quote / evidence rules changed | no |

### Accepted by source

| File | n | Notes |
|---|---:|---|
| CIA-UAP-D023 | 3 | Puerto Rico / Atlantic Fleet cluster (1968) |
| DOS-UAP-D002 | 1 | Bahia / Salvador cable follow-up |
| DOW-UAP-D099 | 2 | Ghost rockets / Swedish pilot |
| FBI-UAP-D024 | 2 | Transatlantic lights (partial redactions → some quote drops) |
| FBI-UAP-D030 | 1 | Colorado Springs triangle Oct 2023 |
| FBI-UAP-D033 | 1 | Thermally elevated object |

### Extract → 0 accepted (explained — quote gate)

| File | candidates | Cause |
|---|---:|---|
| DOW-UAP-D101 | 1 | quote validation failed |
| FBI-UAP-D026 | 1 | quote validation failed (redacted FD-302) |
| FBI-UAP-D028 | 1 | quote validation failed (OCR/spacing garble) |

No unexplained extract→0. No truncation loss.

---

## Identity (Linker V1 on R2 + R3 + R4 + R5)

Input: **12** R2 + **150** R3 + **16** R4 + **10** R5 = **188** accepted local incidents.

| Metric | Value |
|---|---:|
| canonical events | 181 |
| event series | 1 (Western US) |
| candidates | 84 |
| decisions | 55 |
| rejected pairs | 20 |
| same_event | 3 |
| same_series | 49 |
| media_for_event | 1 |
| analysis_of_event | 2 |
| auto_supported / review_supported | 54 / 1 |
| same-release decisions | 2 |
| **cross-release decisions** | **0** |
| Colorado Springs | pass |
| Western US | pass (`D082` 12 → 5 episodes) |
| linker regression | **pass** |

Cross-release reporting artifact: `pipeline/reports/r5_local/cross_release_links.json` (logic unchanged; annotation only).

### Regression gates

| Gate | Status |
|---|---|
| generic-location auto merges | 0 |
| cross-date auto merges | 0 |
| source_only → event inflation | 0 |
| incident → multiple events | 0 |
| manufactured members for catalog pairs | 0 observed |

FBI-UAP-D030 (Colorado Springs, 2023) remained its own event — same city alone is not a merge signal; fixture Colorado Springs cluster untouched.

---

## Quality / review alarms

`needs_review.json` — **37** review signals (not failures). Dominant buckets:

| Alarm | Count | Notes |
|---|---:|---|
| `paired_source_without_event` | 20 | Expected: FD-302↔rendering pairs, CIA D022/D023 one-sided accept, DOS/EOP cables, media-only JPGs |
| `ocr_failure_gt20pct` / `high_ocr_failure` | 4 / 2 | Thin rendering PDFs (D027/D038/D041/D042) |
| `one_source_many_events` | 4 | Prior-corpus high-yield sources |
| `extract_zero_accepted` | 3 | Quote-explained (above) |
| `one_event_many_sources` | 1 | Colorado Springs evt-0044 (3 sources) — fixture |
| `source_only_sibling_inconsistency` | 1 | **DOW-D089/D090** R4 carry-forward watch |
| `very_large_document` | 1 | DOW-D100 (245 pp) |
| `high_quote_rejection` | 1 | FBI-D024 redactions |

### Classifier watch (observe only — not retuned)

- **DOW-D090** siblings (R4) still on the watch list.
- R5 FD-302 cluster: D024/D026/D028/D030/D033 → extract; D032/D037/D040 → `other`/`source_only` despite similar form — possible future classifier edge, left frozen.
- CIA-D022 (`analysis`/`source_only`) ↔ D023 (`extract`) mirrors the R4 “paired, one-sided accept” principle.

Media JPGs: metadata + catalog pairing only; **0** synthetic incidents.

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
| unexplained extract→0 | 0 |
| generic-location auto merges | 0 |
| cross-date auto merges | 0 |
| source_only → event inflation | 0 |
| Colorado fixture | pass |
| Western US fixture | pass |
| production writes | 0 |
| deploy | 0 |
| GPT-6 | off |
| Linker V1.1 | not applied |

### **R5_LOCAL_COMPLETE**

---

## After R5

```text
R4_LOCAL_COMPLETE
      ↓
human linker review → NO V1.1
      ↓
R5_LOCAL_COMPLETE
      ↓
R6_LOCAL
      ↓
R1–R6 corpus-wide QA
```

Keep the stack frozen unless R6 forces a concrete failure.
