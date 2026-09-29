# V2 R3 full local run

**Date:** 2026-09-25  
**Mode:** Local only. No Supabase writes, no Vercel deploy, no GPT-6.  
**Corpus:** all 53 Release 03 PDFs in the 2026-09-18 PURSUE snapshot.  
**Frozen sample:** the 18-document readiness extraction in `pipeline/reports/r3_readiness/` was not sent to Haiku again.  
**New work:** the other 35 PDFs. OCR, classification, extraction, read-only production dedupe, relationship hints, and review alarms.  
**Artifacts:** `pipeline/reports/r3_full/`

## Verdict

### **R3_LOCAL_COMPLETE** *(supersedes `NEEDS_EXTRACTION_FIX`)*

The original full-corpus stop was truncation on **DOW-UAP-D088** and **FBI-UAP-D013**. That blocker is cleared in `docs/V2_R3_EXTRACTION_TRUNCATION_FIX.md` (2026-09-28 local re-run of those two files only). Quote gates, evidence gates, catalog/admin inflation controls, and CIA-UAP-009 thumbnail behavior from this run remain in force.

Historical note from the 2026-09-25 corpus run (kept for audit trail):

> Two incident-bearing files returned no candidates after Haiku hit `max_tokens=4096` and the identical JSON retry failed: **DOW-UAP-D088** (210 pages) and **FBI-UAP-D013** (55 pages).

---

## What stayed frozen

Unchanged decision logic:

- classifier rules
- selective OCR, including the thumbnail skip
- page router (`auto` cue-routes only when pages ≥ 15, text > 60k, routing pages ≥ 3, and at least one narrative page)
- quote-safe normalization
- quote validator and the 90% word window
- evidence sufficiency
- JSON retry (one retry, then drop)
- regression fixtures

The frozen 18 classifications did not drift when the full cache was classified again (`classification_drift_vs_frozen_sample` is empty). Cue-routing fired once in the whole corpus: FBI-UAP-D012. The other 38 extraction plans used fixed chunks, including the large NASA transcripts.

---

## Corpus totals

| Metric | Value |
|---|---:|
| documents total | 53 |
| classified extract | 39 |
| classified source_only | 14 |
| pages total | 3,494 |
| pages OCR'd | 1,829 |
| OCR failed | 149 |
| unrecoverable thumbnail docs | 1 (CIA-UAP-009) |
| Haiku calls | 102 |
| JSON first pass | 88 |
| JSON retry success | 1 |
| JSON retry failure | 6 |
| candidates | 102 |
| quote-valid | 90 |
| quote-rejected | 12 |
| evidence-insufficient | 15 |
| accepted | 75 |
| new_event | 75 |
| likely_duplicate | 0 |
| uncertain | 0 |
| same_event_new_source vs production | 0 |
| possible_same_event hints | 0 |
| analysis_of_event hints | 1 |
| media_for_event hints | 1 |
| followup_to_event hints | 0 |
| duplicate_source hints | 0 |
| estimated cost | $2.04 |
| stage A runtime | 2,359.2s |
| frozen extract runtime (already spent) | 149.8s |
| new extract runtime | 794.7s |
| production writes | 0 |
| deploy | 0 |
| GPT-6 | off |

Cost is the same $0.02 per call ballpark used on the readiness sample: $0.76 for the frozen 38 calls plus $1.28 for 64 calls on the new files (57 first attempts and 7 retries). The pre-extract estimate was 57 sections and about $1.14 if every JSON reply succeeded the first time.

Accepted incidents are all `new_event` against the production excerpt set (read-only). Nothing was merged.

Per-document rows are also in `pipeline/reports/r3_full/per_document_metrics.json`.

| File | Action | Class | Pages | OCR fail | Candidates | Accepted |
|---|---|---|---:|---:|---:|---:|
| CIA-UAP-002 | source_only | contract | 42 | 2 | 0 | 0 |
| CIA-UAP-003 | extract | historical_case_file | 406 | 2 | 2 | 1 |
| CIA-UAP-004 | extract | historical_case_file | 1 | 0 | 0 | 0 |
| CIA-UAP-005 | extract | historical_case_file | 4 | 0 | 0 | 0 |
| CIA-UAP-006 | extract | incident_report | 2 | 0 | 1 | 1 |
| CIA-UAP-007 | extract | historical_case_file | 3 | 0 | 0 | 0 |
| CIA-UAP-008 | extract | historical_case_file | 2 | 0 | 1 | 0 |
| CIA-UAP-009 | source_only | other | 1 | 1 | 0 | 0 |
| CIA-UAP-010 | extract | incident_report | 2 | 0 | 2 | 1 |
| CIA-UAP-011 | extract | historical_case_file | 3 | 0 | 1 | 1 |
| CIA-UAP-012 | extract | historical_case_file | 2 | 0 | 1 | 0 |
| CIA-UAP-013 | source_only | correspondence | 1 | 0 | 0 | 0 |
| CIA-UAP-014 | extract | historical_case_file | 2 | 0 | 1 | 1 |
| CIA-UAP-015 | extract | historical_case_file | 312 | 1 | 0 | 0 |
| CIA-UAP-016 | extract | historical_case_file | 6 | 0 | 7 | 4 |
| CIA-UAP-017 | extract | incident_report | 3 | 0 | 1 | 1 |
| CIA-UAP-018 | source_only | correspondence | 3 | 0 | 0 | 0 |
| CIA-UAP-019 | extract | historical_case_file | 19 | 0 | 0 | 0 |
| DOW-UAP-D077 | source_only | analysis | 4 | 0 | 0 | 0 |
| DOW-UAP-D078 | extract | incident_report | 1 | 0 | 3 | 3 |
| DOW-UAP-D079 | extract | incident_report | 2 | 0 | 4 | 4 |
| DOW-UAP-D080 | extract | incident_report | 8 | 0 | 3 | 3 |
| DOW-UAP-D081 | extract | incident_report | 2 | 0 | 2 | 1 |
| DOW-UAP-D082 | extract | incident_report | 3 | 0 | 12 | 12 |
| DOW-UAP-D083 | extract | incident_report | 5 | 0 | 5 | 5 |
| DOW-UAP-D084 | extract | historical_case_file | 25 | 15 | 0 | 0 |
| DOW-UAP-D085 | source_only | other | 7 | 5 | 0 | 0 |
| DOW-UAP-D086 | source_only | other | 3 | 0 | 0 | 0 |
| DOW-UAP-D087 | extract | historical_case_file | 253 | 28 | 7 | 5 |
| DOW-UAP-D088 | extract | historical_case_file | 210 | 12 | 0 | 0 |
| FBI-UAP-D001 | extract | incident_report | 2 | 0 | 1 | 0 |
| FBI-UAP-D002 | extract | transcript | 2 | 0 | 1 | 1 |
| FBI-UAP-D003 | source_only | media_metadata | 1 | 0 | 0 | 0 |
| FBI-UAP-D004 | extract | incident_report | 3 | 0 | 2 | 2 |
| FBI-UAP-D005 | extract | transcript | 3 | 0 | 3 | 3 |
| FBI-UAP-D006 | extract | incident_report | 3 | 0 | 3 | 0 |
| FBI-UAP-D007 | extract | incident_report | 4 | 0 | 4 | 4 |
| FBI-UAP-D008 | extract | incident_report | 2 | 0 | 1 | 1 |
| FBI-UAP-D009 | extract | incident_report | 2 | 0 | 2 | 1 |
| FBI-UAP-D010 | source_only | other | 2 | 0 | 0 | 0 |
| FBI-UAP-D011 | extract | correspondence | 4 | 0 | 1 | 0 |
| FBI-UAP-D012 | extract | correspondence | 66 | 10 | 20 | 14 |
| FBI-UAP-D013 | extract | historical_case_file | 55 | 3 | 0 | 0 |
| ICA-UAP-D001 | source_only | analysis | 4 | 0 | 0 | 0 |
| NASA-UAP-D015 | source_only | other | 216 | 2 | 0 | 0 |
| NASA-UAP-D016 | extract | transcript | 340 | 7 | 1 | 0 |
| NASA-UAP-D017 | extract | transcript | 290 | 4 | 2 | 1 |
| NASA-UAP-D018 | source_only | administrative | 224 | 41 | 0 | 0 |
| NASA-UAP-D019 | extract | transcript | 223 | 4 | 1 | 1 |
| NASA-UAP-D020 | extract | transcript | 325 | 0 | 6 | 3 |
| NASA-UAP-D021 | extract | transcript | 222 | 4 | 1 | 1 |
| NASA-UAP-D022 | source_only | administrative | 78 | 8 | 0 | 0 |
| USG-UAP-D001 | source_only | correspondence | 86 | 0 | 0 | 0 |

---

## needs_review

Alarms do not fail the run. They are listed in `pipeline/reports/r3_full/needs_review.json`.

### extract and zero candidates

| File | Review |
|---|---|
| CIA-UAP-004 | One-page 1958 contact-division memo about destroyed records and a draft article. No encounter narrative. Empty extraction is the right outcome. |
| CIA-UAP-005 | 1950 information report about a German scientist’s article on “flying discs.” No firsthand incident kept. |
| CIA-UAP-007 | December 1953 status memo on the UFOB project. Organizational, not an encounter. |
| CIA-UAP-015 | 312-page CIA historical record. The word “sighting” appears hundreds of times in study prose. No routing-slip pages, so auto stayed on eight fixed chunks. JSON succeeded and returned no incidents. This is not the Newark failure mode. |
| CIA-UAP-019 | 19-page minute paper. OCR is badly broken. No usable encounter. |
| DOW-UAP-D084 | See OCR below. The extracted text is noise. |
| DOW-UAP-D088 | **Not explained away.** Real observation form. JSON retry failed. See verdict. |
| FBI-UAP-D013 | **Not explained away.** Clipping packet. JSON retry failed. See verdict. |

### high yield

**FBI-UAP-D012** — 20 candidates, 14 accepted. This is the frozen Newark cue-routed recovery: separate memos, not one witness split into phases. Press pages were skipped by the router. Left as needs_review so the next file like it is visible.

**DOW-UAP-D082** — 12 accepted, 0 quote rejections. One October 2023 firsthand statement, location redacted to “western United States,” split into phases (ball of light, orange orbs, a line of nine lights, the next night, and so on). Excerpts are long and observational. This is over-splitting of one narrative, not catalog inflation and not a thin caption. Not merged.

The same redacted label also covers DOW-UAP-D078 (3), D079 (4), D081 (1), and D083 (5): 25 accepted incidents whose location text is only “western United States.” Place-token hints correctly refused to call that a shared city. It is a candidate series for a later linker, recorded here and not auto-linked.

### OCR

| File | What happened |
|---|---|
| CIA-UAP-009 | Unrecoverable thumbnail. Short side 67pt. 126 usable characters. Class `other`, source_only. Catalog title mentions Budapest. That title was not used as evidence and was not used as a relationship hint. Behavior left as documented. |
| DOW-UAP-D084 | 15 of 25 pages failed OCR. About 7,800 characters of glyph noise and no encounter words. Zero candidates follows from the text, not from a missed quote. |
| DOW-UAP-D085 | source_only `other`. 5 of 7 pages failed OCR. 169 usable characters. An unusable scan, not a postage-stamp thumbnail. |
| DOW-UAP-D087 | 28 OCR failures out of 253 pages (about 11%). Below the alarm rate. Five incidents still accepted from the pages that read. |
| NASA-UAP-D018 | 41 OCR failures out of 224 pages (about 18%). Classified administrative and source_only, so it was not extracted. |

Corpus quote-rejection rate is 12/102 (about 12%). No file crossed the alarm line of at least 4 candidates and a rejection rate of 50% or higher. FBI-UAP-D006 rejected all 3 candidates on quote match; that is under the count threshold and the quotes were dropped rather than repaired.

---

## Relationship hints

Hints only. `auto_linked` and `auto_merged` are false on every row. File: `pipeline/reports/r3_full/relationship_hints.json`.

Colorado Springs, the fixture:

| Source | Role | Hint |
|---|---|---|
| FBI-UAP-D002 | primary narrative | 1 accepted incident, case `UNDATED-USA-599D8B`, location text “Cheyenne Mountains” |
| FBI-UAP-D003 | media | `media_for_event` via the catalog PDF pairing column, not via image OCR |
| ICA-UAP-D001 | analysis | `analysis_of_event` because the analysis text contains “Cheyenne” |

Duplicate incident inflation on that cluster remains 0. ICA and FBI-D003 were not extracted.

No other cross-file place cluster survived the hint rules. Generic words (`approximately`, `western`, `observation`, `sighting`) and the USG catalog’s list of cities were not allowed to create links. USG-UAP-D001 stayed source_only with 0 accepted incidents.

Production excerpt similarity produced no `likely_duplicate`, `uncertain`, or `duplicate_source` hint.

---

## Stop-gate checklist

| Requirement | Result |
|---|---|
| fabricated accepted incidents | 0 observed. High-yield excerpts are firsthand observation language. No catalog titles were stored as incidents. |
| catalog/admin inflation | 0. USG-UAP-D001 source_only. NASA-D018 and NASA-D022 administrative source_only. |
| thin-caption incidents | 0. Shortest accepted excerpt is 88 characters. Evidence gate unchanged. |
| quote rules | unchanged |
| evidence gate | unchanged |
| extract → 0 candidate anomalies | reviewed above. Two of them are real losses. |
| high-yield sources | reviewed. D012 is the Newark multi-case file. D082 is one redacted statement split into phases. |
| OCR failures | explained above. CIA-UAP-009 was not re-engineered. |
| production writes | 0 |
| deploy | 0 |
| GPT-6 | off |

---

## After this

```text
FULL LOCAL R3          done (see truncation-fix follow-up)
      ↓
V2-R3-EXTRACTION-TRUNCATION-FIX   done → R3_LOCAL_COMPLETE
      ↓
design a generalized canonical linker
  (Colorado Springs + western-US DOW series fixtures)
      ↓
local R4
      ↓
R5, R6, full corpus QA
      ↓
only then discuss production ingestion
```

No linker was built in the corpus run. No Release 04 processing was started.
