# V2 R1–R6 corpus QA

**Date:** 2026-09-28  
**Mode:** Local artifacts + read-only production. No Supabase writes, no deploy, no GPT-6, no re-extraction of R1.  
**Question:** Is the full local corpus internally consistent, complete against the 450 official records, and safe enough to prepare a production migration plan?  
**Runner:** `python -m pipeline.corpus_qa`  
**Artifacts:** `pipeline/reports/corpus_qa/`

## Verdict

### **CORPUS_QA_COMPLETE**

The official 2026-09-18 PURSUE snapshot reconciles to 450 records with no remainder. Every accepted fragment in the identity graph has a source and a verbatim excerpt. Linker V1 still passes Colorado Springs and the Western US series on R1–R6 together. Two catalog bugs showed up only when R1 was included; both are guarded, and the Western US series is back to 21 events.

---

## Stop gate

| Check | Result |
|---|---|
| 450 official records reconciled | yes |
| unexplained missing records | 0 |
| unexplained extraction failures | 0 |
| unsupported accepted incidents | 0 |
| catalog inflation | 0 |
| thin-caption incidents (R2–R6) | 0 (shortest accepted excerpt 88 characters) |
| overmerge candidates unresolved | 0 |
| high-confidence underlinks unresolved | 0 |
| watch items dispositioned | yes (9/9 explained) |
| production writes | 0 |
| deploy | 0 |
| GPT-6 | off |
| Linker V1.1 | not started |

---

## 1. Official coverage

Ledger: `source_coverage.json`, `source_coverage.csv`, `release_summary.json`.

```text
pdf processed            142
pdf source_only          125
image metadata-only       30
video metadata-only      134
audio metadata-only       16
deprecated/superseded      0
unrecoverable              3
────────────────────────────
                         450
```

The three unrecoverable rows are the known R1 URL-drift PDFs. They are accounted for, not missing:

| Official record | Why it is unlinked |
|---|---|
| `59_64634_711.5612[7-2852` | Official URL does not match the production file |
| `65_HS1-834228961_62-HQ-83894_Serial_153` | Official URL does not match the production file |
| `DOW-UAP-D020` Iraq 2023 | Production file is a different document (Southern United States, 2020). Do not merge |

CIA-UAP-002 through CIA-UAP-019 use ids without a `D`/`PR` token. The manifest parser was skipping them. The ledger joins on the title prefix, so those 18 PDFs sit in processed / source_only instead of a false “missing” bucket. CIA-UAP-009 remains an unrecoverable thumbnail inside `pdf_source_only` (class `other`, 0 incidents).

---

## 2. Release inventory

| Release | Records | PDFs | Media | Extract | Source-only | Accepted |
|---|---:|---:|---:|---:|---:|---:|
| R1 | 158 | 116 | 42 | 75 | 38 | 380 |
| R2 | 64 | 6 | 58 | 4 | 2 | 12 |
| R3 | 72 | 53 | 19 | 39 | 14 | 150 |
| R4 | 40 | 14 | 26 | 8 | 6 | 16 |
| R5 | 41 | 22 | 19 | 9 | 13 | 10 |
| R6 | 75 | 59 | 16 | 7 | 52 | 15 |
| **Total** | **450** | **270** | **180** | **142** | **125** | **583** |

R1 “accepted” is the unflagged production baseline. R2–R6 accepted rows are local and sum to **203**. R3’s 150 includes the truncation fix (DOW-UAP-D088 67, FBI-UAP-D013 8) on top of the earlier full-corpus extract. Media rows are metadata-only: no multimodal extraction.

Extract + source_only + the 3 unlinked PDFs = 270 PDFs.

---

## 3. R1 production reconciliation

Read-only snapshot at run time. R1 was not re-extracted.

| | Count |
|---|---:|
| production incidents | 480 |
| unflagged, still valid | 380 |
| flagged `duplicate_excerpt`, stay excluded | 100 |
| unflagged mapped to a `source_record` | 376 |
| unflagged on an unlinked file | 4 |
| historical rows superseded | 0 |
| incident text that needs no change | 380 |
| `source_files` | 181 |
| `source_files` linked to a registry row | 160 |
| `source_files` still unlinked | 21 |
| production `source_records` | 450 |

The four unflagged incidents sit on the URL-drift copies already in production. Keep the incident rows. At migration, link the file; do not re-extract:

| Case | File |
|---|---|
| `2023-USAF-24C074` | `DOW-UAP-D20, Mission Report, Southern United States, 2020` |
| `1965-NASA-E762B7` | `NASA-UAP-D3, Gemini 7 Transcript, 1965` |
| `1965-NASA-EE52BC` | same Gemini file |
| `UNDATED-FBI-6DDF67` | `65_HS1-834228961_62-HQ-83894_Serial_153` |

The other 17 unlinked files are slideshow JPGs and similar local-only assets from the earlier reconciliation. They are not official CSV rows.

---

## 4. Fragments versus events

These are different counts. The product must not treat them as the same thing.

| Layer | Count | What it is |
|---|---:|---|
| R1 published fragments | 380 | unflagged production incidents |
| R1 excluded fragments | 100 | flagged `duplicate_excerpt` |
| R2–R6 raw accepted fragments | 203 | local, quote- and evidence-gated |
| fragments in the linker | 583 | 380 + 203 |
| canonical events | 575 | one real-world occurrence each |
| events with a single fragment | 572 | |
| multi-fragment events | 3 | sizes 2, 4, and 5; intra-source phase groups |
| event series | 1 | Western US 2023, **21** events |
| link decisions | 44 | |
| `event_source` rows | 3 | 1 `media_for_event`, 2 `analysis_of_event` |
| review-supported decisions | 24 | specific-place overlaps, not applied |
| rejected generic-location pairs | 20 | negative control, capped sample |

Same-release decisions: **3**. Cross-release auto-links: **0**.

R1 did not produce a cross-release `same_event`. The new review-supported rows are place overlaps held for a human, which is what V1 is supposed to do.

---

## 5. Linker V1 on R1–R6

Colorado Springs fixture: **pass**. Western US fixture: **pass**. D082: **12 rows → 5 episodes**. Generic location auto-merges: **0**.

Two guards were required once R1 classifications entered the catalog. They are not a V1.1 redesign:

1. A spaced catalog token such as `FBI Photo A001` was defaulting into `western-us-event-2023` and renaming the series. Only an explicit series id, or a label that actually says Western US Event, joins that series.
2. `load_catalog()` kept one row per external id, so the R3 FBI-UAP-D014 **image** pairing overwrote the R4 **correspondence PDF** and pulled two 1967/1974 letters into the 2023 series. The PDF row now wins. The image is stored as an alternate asset. Series size returned to **21**.

Regression: `python -m unittest pipeline.tests.linker.test_linker_v1` (11 tests) and `python -m pipeline.tests.test_validation` (5/5).

---

## 6. Overmerge

`overmerge_candidates.json`: **0 unresolved**.

No canonical event combined incompatible dates, incompatible specific places, different named operations, or a generic location as the reason for an auto merge. Multi-fragment events are intra-source continuity groups inside one file.

---

## 7. Underlink

`underlink_candidates.json`: **0 high-confidence unresolved**.

High confidence means an official pairing, the same specific date, and the same specific place, with no linker decision. Nothing met that bar. Weaker hints stay in source evolution and in the 24 `review_supported` place overlaps. Nothing was auto-merged.

---

## 8. Source evolution

`source_evolution.json`. Hints only.

| Kind | Count |
|---|---:|
| cross-release catalog pairing | 9 |
| duplicate external id | 1 |
| type change | 1 |
| later media for a prior event | 1 |

**FBI-UAP-D014** is the duplicate. It is two assets, not one reissue:

| Release | Type | Identity | What it is |
|---|---|---|---|
| R3 | image | `pursue:FBI-UAP-D014:image` | Digital rendering for the Western US narrative (DOW-UAP-D079) |
| R4 | pdf | `pursue:FBI-UAP-D014` | 1967/1974 correspondence. Not the 2023 series |

No deprecated or superseded official rows in this snapshot. No automatic merge.

---

## 9. Classifier

Local classifications only (R1 was never run through the v2 classifier).

| Class | Documents |
|---|---:|
| other | 33 |
| historical_case_file | 25 |
| incident_report | 21 |
| research_paper | 21 |
| transcript | 17 |
| correspondence | 12 |
| analysis | 9 |
| contract | 9 |
| administrative | 5 |
| media_metadata | 1 |
| personnel_record | 1 |

`research_paper`, `personnel_record`, `administrative`, and `media_metadata` have **0** accepted incidents. No source_only file has accepted incidents. Anomaly count: **0**.

---

## 10. OCR

`ocr_quality_summary.json`. Measured on the local R2–R6 text reports (154 documents).

| | |
|---|---:|
| pages total | 7,119 |
| pages OCR'd | 3,414 |
| OCR failures | 315 |
| files over 20% OCR failure | 11 |
| unrecoverable thumbnails | 1 (`CIA-UAP-009.pdf`) |
| native-only good text | 19 |

Failures are listed. They did not silently become incidents. DOW-UAP-D084 (60% OCR failure) returned 0 candidates from glyph noise. CIA-UAP-009 is source_only.

---

## 11. Extraction

| | |
|---|---:|
| Haiku calls (R2 smoke + ODNI + R3 + truncation fix + R4 + R5 + R6) | 198 |
| R2–R6 accepted fragments | 203 |
| extraction_failed | 0 |
| R2–R6 excerpts under 80 characters | 0 |

The 198 calls include the original D088/D013 attempts **and** the later truncation-fix calls (28). Final `extraction_failed` on the fix and on R4–R6 is 0. D088 and D013 are recovered (67 and 8).

Every extract file with 0 accepted rows has a disposition: no encounter in the text, study prose, OCR noise, or a quote/evidence drop. None are unexplained.

---

## 12. Evidence

583 linker fragments checked (380 unflagged R1 + 203 local).

| | |
|---|---:|
| source present | 583 |
| raw excerpt present | 583 |
| local rows inside the official id set | 203 / 203 |
| unsupported | 0 |

R1 rows were validated by the original quote gate and were not re-validated here. Local rows are the validated-incident sets from R2–R6.

---

## 13. High-yield sources

| Source | Accepted | Reading | Disposition |
|---|---:|---|---|
| DOW-UAP-D088 | 67 | 30 distinct dates, 67 episodes. A compilation, not one sighting. | explained |
| DOW-UAP-D082 | 12 | 5 episodes from continuity cues, inside the Western US series. | explained |
| FBI-UAP-D012 | 14 | 8 distinct dates, 14 episodes. Separate memos. | explained |
| DOW-UAP-D154 | 9 | Ruppelt transcript naming several historical cases. | explained |
| DOE-UAP-D004 | 10 | Green-fireball file, 10 episodes, not one merged event. | explained |

Counts were not reduced.

---

## 14. Watch list

| Item | Disposition |
|---|---|
| CIA D020 / D021 | explained — D020 quote-rejected; D021 kept; no manufactured member |
| DOE D005 / D001 | explained — no synthetic cross-release incident |
| NASA D030–D032 | explained — images, metadata only |
| DOW D089 / D090 / D091 | explained — D090 stayed source_only; siblings extracted; no fabricated rows |
| R5 FD-302 siblings | explained — mixed extract / source_only; accepted rows still passed both gates |
| FBI D014 type collision | explained — image and PDF kept as separate identity keys |
| Colorado Springs | explained — fixture pass |
| Western US series | explained — 21 events, not one merge |
| Tremonton package | explained — R6 Blue Book file plus pairing hints; no cross-release auto-merge |

---

## What this does not authorize

Production writes, deploy, GPT-6 on the Ask path, embedding changes, and Linker V1.1. The next documents are the delta and the migration order. The RAG provider move is a separate local track.
