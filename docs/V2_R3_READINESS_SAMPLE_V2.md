# V2 R3 Readiness Sample — fixes rerun (local-only)

**Date:** 2026-09-25  
**Mode:** Local / read-only vs production — **no writes, no deploy, no GPT-6**  
**Sample:** the same 18 PDFs as `docs/V2_R3_READINESS_SAMPLE.md`  
**Prior artifacts:** `pipeline/reports/r3_readiness/v1_snapshot/`

## Verdict

### **READY_FOR_BROADER_LOCAL_PROCESSING**

The safety boundary is unchanged: substring quote checks, the 90% word window, and evidence sufficiency were not loosened. Catalog correspondence is no longer mined as incidents. The large Newark file is routed by page instead of by blind chunks. Colorado Springs now has one accepted primary narrative plus two non-incident source roles.

One residual is called out under Colorado Springs: the accepted FBI-D002 quote is three verbatim sentences with text omitted between them. It passes the existing 90% window after quote-safe spacing normalization. It is not an exact contiguous substring.

---

## Stage B totals (same 18 PDFs)

| Metric | v1 | v2 |
|---|---:|---:|
| extract / source_only | 10 / 8 | **11 / 7** |
| candidates | 40 | **40** |
| quote-valid | 30 | **34** |
| quote-rejected | 10 | **6** |
| evidence-insufficient | 6 | **7** |
| accepted | 24 | **27** |
| false admin incidents (USG-D001) | **11** | **0** |
| FBI-D012 candidates | **0** | **20** (14 accepted) |
| Colorado Springs linked sources | **0** | **2** |
| new_event | 24 | 27 |
| same_event_new_source (vs production excerpts) | 0 | 0 |
| likely_duplicate / uncertain | 0 / 0 | 0 / 0 |
| JSON first-pass / retry success / retry fail | 29 / 1 / 2 | **38 / 0 / 0** |
| estimated Haiku calls (stage B) | ~35 | **38** |
| estimated stage B cost | ~$0.70 | **$0.76** |
| stage B runtime | 358.5s | **149.8s** |
| production writes | 0 | **0** |

Accepted count went up, not down, because the 11 USG rows disappeared and the Newark memos plus CIA-006 and FBI-D002 came in. That is the intended trade.

Stage B artifacts: `pipeline/reports/r3_readiness/extractions.json` (`extractions_v2.json`), `metrics.json`, `dedupe_candidates.json`, `classifications.json`, `colorado_springs_cluster.json`.

The FBI-D012 strategy comparison is separate from stage B and is not included in the $0.76 figure. It used about 35 additional Haiku calls (`d012_strategy_compare.json`).

---

## What changed

1. **Catalog vs firsthand correspondence.** Referral language (`forwards letter`, `fwds ltr`, `thank you for your letter`, `requesting information`, `incoming correspondence action`, HATS) keeps `contains_incidents=false` unless the letter actually says what the writer saw (`I saw`, `we all saw`). A bare “sighting” in a constituent referral is not enough.
2. **Analysis label.** `analyst note`, `backscattering`, and `low confidence in this` mark an assessment. Document ids such as `ICA-UAP-D001` are not treated as incident framing.
3. **Administrative false positive.** The word `invitation` alone no longer forces `administrative`. `you are invited` still does. CIA-006’s “at the invitation of a senior official” was the miss.
4. **Page router** (`pipeline/section_router.py`). Large mixed files are scored per page (chars, OCR quality, incident cues, date/location cues, routing likelihood, narrative likelihood). Index slips and press/contactee clippings are skipped. Narrative memo pages are grouped into sections. Ordinary reports and the NASA transcript stay on fixed chunks.
5. **Quote-safe normalization.** Page markers, end-of-line hyphens, space-before-punctuation, and OCR spaces inside a word (`bui l ding` → `building`, `to l ook` → `to look`). No spelling correction, no semantic fuzzy match, no model quote repair. `pipeline/tests/test_validation.py` is still 3 kept / 2 dropped.

Permanent classifier fixtures: `pipeline/tests/fixtures/r3_classifier/` for `USG-UAP-D001`, `ICA-UAP-D001`, `FBI-UAP-D011`, `CIA-UAP-006`.

---

## Classifier on the same 18

| Doc | v1 | v2 |
|---|---|---|
| **USG-UAP-D001** | correspondence **extract** → 11 accepted | correspondence **source_only** → **0** |
| **CIA-UAP-006** | administrative source_only | **incident_report extract** → **1 accepted** |
| **CIA-UAP-009** | other source_only | other source_only, now explained |
| **FBI-UAP-D011** | correspondence source_only | correspondence **extract**, then evidence-held |
| **ICA-UAP-D001** | other source_only | **analysis source_only** |
| **FBI-UAP-D003** | other source_only | **media_metadata source_only** |
| **FBI-UAP-D012** | correspondence extract | correspondence extract, **cue-routed** |
| CIA-003, CIA-005, CIA-016, CIA-017, DOW-D079, FBI-D002, FBI-D009, NASA-D016 | unchanged class / extract bit | unchanged |

No other file in the 18 flipped.

---

## False-skip dispositions

### CIA-UAP-006 — correct now

The text is an eyewitness unconventional-aircraft account (Baku–Tiflis, 4 Oct 55, triangular object launched from an airfield). v1 called it administrative because `_ADMIN_RE` matched `invitation` in “at the invitation of a senior Soviet official.” v2 class is `incident_report`, and stage B accepted one quote-checked incident (“Triangular Object Launch Near Baku”).

### CIA-UAP-009 — correct to leave source_only

The released PDF is one page, **67×110 points**, with an embedded JPEG of **134×221 pixels**. That is a thumbnail, not a page scan. Upscaling to 200/300/400 dpi still returns garbage. OCR is skipped and recorded as `unrecoverable thumbnail page (short side 67pt)`. Usable text remains 126 characters of native noise. Classification on that text is not meaningful, and the file is not sent to Haiku. The Budapest title lives on the manifest, not in recoverable page text, so it is not used as a source excerpt.

### FBI-UAP-D011 — classifier correct, evidence gate held

The Barnes letter is correspondence that describes an observation (“Last May one afternoon I saw four beams in the sky…”). v2 sets `contains_incidents=true` and extracts. Haiku returned that passage. Evidence sufficiency, unchanged, dropped it as `excerpt_lacks_observation_language`: the quote says “saw” / “beams” / “explosion,” and the existing observation pattern does not treat those tokens as sufficient. This is not a classifier skip. It is also not an accepted incident.

---

## FBI-UAP-D012

66 pages, 121k characters. Opening pages are index slips. Later pages mix FBI memoranda with flying-saucer press clippings.

Page router on the current OCR:

| Route | Pages |
|---|---:|
| narrative memos | 20 |
| skip empty / failed OCR | 19 |
| uncertain | 13 |
| skip press / contactee clippings | 10 |
| skip routing / index slips | 4 |

Strategy comparison (same text, three chunkers, quote and evidence gates unchanged):

| Strategy | Sections | Candidates | Quote-valid | Accepted |
|---|---:|---:|---:|---:|
| fixed 60k chunks | 3 | **0** | 0 | **0** |
| page-grouped (non-empty pages) | 19 | 39 | 21 | 18 |
| cue-routed narrative sections | 10 | 20 | 19 | **15** |

Fixed chunking reproduces the v1 failure: Haiku returns `[]`. The memos are buried in index pages and newsletter text.

Page grouping recovers cases and also accepts clipping-file stories (Hillsdale College, Dr. Daniel Fry photographs, Three Rivers constables). Those quotes sit in the scanned press, so the quote gate does not reject them.

Cue routing is what stage B uses for this file. It keeps Newark-area memoranda (Glen Ridge 1957, Clifton, Union, Jersey City, Woodbridge, West Orange, Bloomfield, and related 1958–1966 calls) and leaves the contactee newspapers out. Stage B, a second model draw, accepted **14** of **20** candidates (4 quote-rejected, 2 evidence-insufficient). The source does contain extractable cases. The empty v1 result was the chunker, not an absence of incidents.

Diagnostic: `pipeline/reports/r3_readiness/d012_page_signals.json` and `d012_strategy_compare.json`.

---

## Colorado Springs

| Source | v2 class | v2 result |
|---|---|---|
| FBI-UAP-D002 | transcript, extract | **1 accepted** primary narrative |
| FBI-UAP-D003 | media_metadata, source_only | rendering / image packet, **0 incidents** |
| ICA-UAP-D001 | analysis, source_only | Cheyenne Mountain assessment, **0 incidents** |

`pipeline/reports/r3_readiness/colorado_springs_cluster.json` records the roles:

```text
Colorado Springs — 2022
  FBI-UAP-D002   primary narrative   (1 accepted)
  FBI-UAP-D003   media               (not an incident)
  ICA-UAP-D001   analysis            (not an incident)
linked_sources = 2
duplicate incident inflation = 0
```

That file is a reviewed fixture for this one cluster. It is not a generalized canonical linker and it does not auto-merge. Production excerpt similarity still scores the FBI-D002 quote as `new_event` (best score 0.305). `same_event_new_source` in the stage B dedupe counter stays 0 because that counter only compares accepted excerpts to production incidents.

**Quote fidelity.** The accepted excerpt is the model’s three-sentence highlight: the intelligence officer leaving the building, the potato-shaped object, and the object vanishing. Those sentences are in the OCR, and they are not adjacent — the blue-bird weather paragraph and the panel description sit between them. Exact substring match is still false. After spacing normalization (`inte l ligence` → `intelligence`, `bui l ding` → `building`, space before the period removed), the unchanged 90% word window covers that span and keeps the row. A synthetic excerpt that skips a much longer gap is still dropped. Fabricated and paraphrased quotes in `test_validation.py` are still dropped.

---

## Readiness checklist

```text
USG-D001 catalog inflation                 0
obvious source-only docs extracted         0

CIA-UAP-006 disposition                    incident_report, 1 accepted
CIA-UAP-009 disposition                    unrecoverable 67pt thumbnail, source_only
FBI-UAP-D011 disposition                   correspondence extract; evidence gate held

FBI-UAP-D012                               understood
  fixed chunks                             0 candidates (reproduced)
  cue-routed memos                         14 accepted in stage B

Colorado Springs
  primary event recovered                  yes (FBI-D002)
  analysis and media attached as sources   yes (2)
  duplicate incident inflation             0

quote validation rules                     unchanged (5/5 validation script)
evidence sufficiency                       unchanged
production writes                          0
deploy                                     0
GPT-6                                      off
```

Generalized canonical linking was not built. The next design can start from the Colorado Springs fixture.

**STOP.**
