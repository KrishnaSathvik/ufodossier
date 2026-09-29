# V2 production delta

**Date:** 2026-09-28  
**Status:** Design only. Nothing in this document has been written to production.  
**Source:** `docs/V2_R1_R6_CORPUS_QA.md` and `pipeline/reports/corpus_qa/summary.json`.  
**Production read:** 2026-09-28, select-only.

## Current production

```text
incidents              480
  unflagged            380
  flagged              100   (all duplicate_excerpt)
source_files           181
  linked to registry   160
  unlinked             21
source_records         450   (R1–R6 metadata already imported)
incident_sources       476
releases in the UI     R1 only
canonical events       none
event series           none
```

The registry metadata for all six releases is already in `source_records`. The public incident corpus is still the R1 extract.

## Local V2

```text
official source records          450
R1–R6
accepted incident fragments      583
  R1 unflagged baseline          380
  R2–R6 local                    203
canonical events                 575
event series                     1     (Western US 2023, 21 events)
link decisions                   44
event_source rows                3
review-supported, not applied    24
cross-release auto-links         0
```

583 fragments are not 583 real-world events. 575 canonical events is the event count. 572 of those events have one fragment. Three events are intra-source phase groups.

## What would change

| Object | Action | Count | Note |
|---|---|---:|---|
| `source_records` | already present | 450 | Do not insert a second copy. Fill class / checksum / ingestion state where still null. |
| new `source_files` | insert | 154 local R2–R6 PDFs | 6+53+14+22+59 cached under `.cache/files/pursue/`. Skip any URL already stored (the R2 smoke files). |
| media binaries | do not download yet | 180 | Image 30, video 134, audio 16. Registry rows exist. Metadata only. |
| new incidents | insert | 203 | R2–R6 accepted fragments only. |
| existing incidents | keep | 380 | Unflagged R1 rows. Do not re-extract. |
| existing incidents | keep flagged | 100 | `duplicate_excerpt`. Stay out of public stats. |
| R1 source links | manual | 4 incidents | URL-drift files. Link the file; do not rewrite the excerpt. |
| unlinked slideshow files | leave | 17 | Not official CSV rows. |
| official PDFs still unlinked | leave for review | 3 | The URL-drift trio in the corpus QA doc. |
| `incident_sources` | extend | +203 | One primary row per new fragment, plus the 4 manual R1 links if they have no row yet. |
| canonical events | insert | 575 | Migration `009` is still design-only. |
| event members | insert | 583 | One per linker fragment. |
| event series | insert | 1 | 21 member events. |
| source relationships | insert | 3 auto `event_source` rows | Plus 24 review-supported decisions stored as review, not as merges. |
| embeddings | generate | 203 | Voyage `voyage-3`, 1024-d, zero-pad to 1536. Do not re-embed the 380. Do not change the vector width. |
| flagged rows | no embed refresh | 100 | Excluded. |

## What must not change

- The 380 unflagged R1 excerpts, titles, and case ids.
- The 100 flagged rows (they stay flagged).
- Quote-gate and evidence-gate rules.
- Extraction model: Claude Haiku 4.5. This delta does not switch extraction to GPT-6.
- Embedding model and dimension.

## Identity consequence for the public site

Until canonical events are exposed, the honest public counts are:

```text
583 verified incident fragments
575 canonical events
450 official source records
6 PURSUE releases
```

Do not publish “583 UFO events.”

## Still blocked on purpose

```text
production writes     0
deploy                0
GPT-6 in production   off
```

Ask-the-Archive model migration is independent of this data delta. A bad RAG switch must be reversible without rolling the corpus back.
