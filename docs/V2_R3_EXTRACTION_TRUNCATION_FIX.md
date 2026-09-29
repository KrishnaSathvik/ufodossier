# V2 R3 extraction truncation fix

**Date:** 2026-09-28  
**Mode:** Local only. No Supabase writes, no Vercel deploy, no GPT-6.  
**Scope:** Truncation robustness only. Re-ran **DOW-UAP-D088** and **FBI-UAP-D013**. Did not reprocess the other 51 Release 03 PDFs. Did not start R4. Did not build the canonical linker. Did not touch DOW-UAP-D082 phase-splitting.

**Artifacts:** `pipeline/reports/r3_truncation_fix/`  
**Prior stop:** `docs/V2_R3_FULL_LOCAL.md` (`NEEDS_EXTRACTION_FIX`)

## Verdict

### **R3_LOCAL_COMPLETE**

Truncation is a first-class extraction condition. Identical-chunk retry is reserved for malformed JSON with a normal stop. Page-boundary subdivision recovered D088. D013 was policy-routed so press pages were not promoted. Quote validation and evidence sufficiency are unchanged.

---

## What changed

| Piece | Behavior |
|---|---|
| `stop_reason == max_tokens` | `json_truncated`. Never retry the same input. Subdivide at page midpoints. |
| Normal stop + invalid JSON | `json_invalid`. One same-input retry (unchanged rule). |
| Child still truncates | Recurse, `MAX_SPLIT_DEPTH = 4`, `MIN_SECTION_PAGES = 1`. |
| Cannot split further | `extraction_failed`. No fabricate / no JSON repair. |
| After subdivision | Deterministic within-source dedupe (normalized excerpt equality, high overlap, date+location). |
| Telemetry | `json_truncated`, `json_invalid`, `api_error`, `valid`, `extraction_failed`, `sections_subdivided`, `haiku_calls` |
| `max_tokens` | Still **4096**. Not raised. |

Regression fixtures: `pipeline/tests/test_extraction_truncation.py` (A–D + page split + within-source dedupe).

SYSTEM_PROMPT gained one section-scoped rule: extract only encounters supported in the supplied section; sections are processed independently. The quote and evidence gates were not loosened.

---

## Re-run results

### DOW-UAP-D088

| Metric | Before (full R3) | After truncation fix |
|---|---:|---:|
| accepted | 0 | **67** |
| truncation events detected | (hidden inside JSON retry) | **9** |
| identical retry on truncation | 3 chunks × failed retry | **0** |
| extraction_failed | n/a | **0** |
| sections subdivided | 0 | **9** |
| Haiku calls | 6 (all failed) | **22** |
| quote-rejected | 0 | 8 |
| evidence-insufficient | 0 | 7 |
| min accepted excerpt length | — | 120 |

Initial plan stayed **fixed** (3 × ~60k char chunks). Each truncated parent split on page boundaries; children recovered observation-form incidents (Boise object, Fort Ross lookout, Green River fireball, Bakersfield falls, and so on). Source-supported recovery is non-zero. Truncated output loss is zero.

67 accepts from a 210-page historical observation packet is a high-yield `needs_review` case for the later linker. It is not catalog inflation and not thin captions. It is out of scope for this milestone (same rule as D082: do not mix phase/over-split design into truncation work).

### FBI-UAP-D013

| Metric | Before | After |
|---|---:|---:|
| strategy | fixed (1 section) | **cue_routed** (forced) |
| accepted | 0 | **8** |
| truncation events | 1 (+ identical retry fail) | **0** |
| press_clipping pages | 1 | **16** |
| narrative / investigative pages | 18 | **10** (after FOIA press cues) |
| other / empty | rest | 19 / 10 |

Page policy was written to `FBI-UAP-D013_page_policy.json`:

```text
government_memo_or_investigative  10
press_clipping                    16
empty                             10
other                             19
disposition                       extract_narrative_pages
```

Only narrative/investigative pages were extracted. Press/FOIA newspaper pages (`serialized`, `Columbia Basin`, mastheads, `DocId`) were skipped. Accepted rows are FBI/AF investigative notes (Sand Point NAS, Richland, Pasco, TIMOTHY radar, Kennewick), not wire-service contactee blurbs. The packet is **not** press-only, so `source_only` would have been wrong.

FOIA press cues were added to `_PRESS_RE`. FBI-UAP-D012 route counts stayed identical (20 narrative / 10 skip_press / 4 skip_routing).

---

## Stop-gate checklist

| Requirement | Result |
|---|---|
| D088 truncated output loss | **0** (`extraction_failed` = 0) |
| D088 supported incidents | **67** (> 0) |
| D013 pages policy-classified | **yes** |
| D013 truncation loss | **0** |
| D013 press-only material | not blindly promoted (16 press pages skipped) |
| JSON truncation detected | **9/9** on D088 |
| identical retry on truncation | **0** |
| recursive subdivision | working (depths 1–2; 18 children of truncated parents) |
| quote validator | unchanged |
| evidence sufficiency | unchanged |
| production writes | **0** |
| deploy | **0** |
| GPT-6 | **off** |
| R4 | **not started** |

---

## R3 status

With this fix, Release 03 local processing is complete enough to leave extraction frozen and move to the **generalized canonical event linker**.

Fixtures already in hand:

1. **Colorado Springs** — one event: FBI-D002 narrative, FBI-D003 media, ICA-D001 analysis (no duplicate incidents).
2. **Western U.S. DOW series** — D078–D083 redacted multi-file / multi-night / phase-split hard case (includes D082’s 12-phase over-split). Treat separately from truncation.

Do **not** start R4 until the linker is designed against those fixtures.

```text
FULL LOCAL R3
TRUNCATION FIX          ← you are here (R3_LOCAL_COMPLETE)
      ↓
design generalized canonical linker
      ↓
local R4
```
