# V2 Canonical Linker V1

**Date:** 2026-09-28  
**Mode:** Local only. No Supabase writes, no Vercel deploy, no GPT-6.  
**Prerequisite:** `R3_LOCAL_COMPLETE` (`docs/V2_R3_EXTRACTION_TRUNCATION_FIX.md`)  
**Extraction:** frozen. Incidents are immutable evidence units.

**Code:** `pipeline/linker/`  
**Artifacts:** `pipeline/reports/linker_v1/`  
**SQL:** `db/migrations/009_canonical_events_DESIGN_ONLY.sql` (not applied)

## Verdict

### **READY_FOR_R4_LOCAL**

Colorado Springs reproduces as one canonical event with media and analysis attached. The Western U.S. material is a **series of events**, not one merged incident. D082’s 12 phase rows collapse to 5 episodes from continuity language. Generic “western United States” never auto-merges across sources.

---

## Hierarchy

```text
SOURCE DOCUMENT
      ↓
extracted incident fragments   (immutable)
      ↓
CANONICAL EVENT                 (one real-world occurrence)
      ↓
EVENT SERIES                    (optional; related but not identical)
```

### Colorado Springs 2022

```text
Canonical Event: Colorado Springs 2022
├── FBI-UAP-D002  primary_narrative   (1 member incident)
├── FBI-UAP-D003  media_for_event
└── ICA-UAP-D001  analysis_of_event
```

Canonical events created: **1**  
Extra incidents created: **0**  
Auto physical merge: **0**

### Western U.S. 2023 Series

```text
Series: western-us-event-2023  ("Western US Event" catalog label)
├── events from D078 (map/overview rows → 3 episode events)
├── events from D079 (witness 1 → 4)
├── events from D080 (witness 2 → 3)
├── events from D081 (witness 3 → 1)
├── events from D082 (witness 4 → 5 episodes from 12 rows)
└── events from D083 (witness 5 → 5)
```

Total events in series: **21**  
Cross-file `same_event` auto_supported from generic location: **0**  
`same_series` is explicit and explainable via catalog PDF Pairing / series label.

D077 (AARO analysis update) is catalog-linked to the same series label; it remains source_only analysis and does not create incident rows.

---

## What V1 does

| Module | Role |
|---|---|
| `models.py` | `canonical_event`, `event_member`, `event_source`, `event_series`, `link_decision` |
| `normalize.py` | Specific places vs generic geography; series id; continuity cues |
| `candidate_generation.py` | Candidates only with pairing, series id, specific place, analysis lede |
| `intra_source_episode.py` | `same_episode` / `new_episode` / `uncertain_boundary` |
| `relationship_rules.py` | Deterministic decisions; no LLM merge |
| `audit.py` / `run_v1.py` | Local JSON audit |

### Relationship vocabulary in use

`same_event`, `same_series`, `primary_narrative`, `media_for_event`, `analysis_of_event`, `unrelated`, `needs_review`

### Decision statuses

| Status | Meaning |
|---|---|
| `auto_supported` | Strong deterministic evidence (catalog pairing, series label, lede place match, intra-source continuity) |
| `review_supported` | Medium evidence; not applied as a merge |
| `needs_review` | Secondary place mention or weak signal |
| `rejected` | Explicitly not a link (e.g. generic location alone) |

Nothing is physically merged. `auto_merged` and `incidents_rewritten` stay false.

---

## Episode grouper (D082)

Continuity cues from the source narrative:

| Boundary | Cue examples |
|---|---|
| `same_episode` | “after about 10 minutes”, “later”, “soon thereafter”, “later in the night” |
| `new_episode` | “the next day”, “a few days later”, “some months thereafter” |
| `uncertain_boundary` | no cue — **kept separate** (adjacency alone does not merge) |

D082 result: **12 rows → 5 episodes** (night 1 phases, next day, few days later, next day, months later).

---

## Negative controls

| Signal | Result |
|---|---|
| generic “western United States” | rejected / no place candidate |
| same agency | not a candidate |
| same year alone | not a candidate |
| “UAP” wording alone | not a candidate |
| excerpt similarity alone | not auto merge |
| ICA secondary “Fort Carson” mention | not auto-attached (lede/repeat rule; Cheyenne is primary) |

---

## Full local R3 pass metrics

| Metric | Value |
|---|---:|
| canonical events | 143 |
| event series | 1 |
| candidates | 27 |
| decisions | 18 |
| rejected pairs (sample) | 20 |
| Colorado Springs pass | true |
| Western US pass | true |
| production writes | 0 |
| deploy | 0 |
| GPT-6 | off |
| R4 started | false |

Run: `python -m pipeline.linker.run_v1`  
Tests: `python -m unittest pipeline.tests.linker.test_linker_v1`

---

## Stop-gate checklist

| Requirement | Result |
|---|---|
| Colorado Springs fixture reproduced | **PASS** |
| Western-US series represented safely | **PASS** |
| D082 over-split rows groupable | **PASS** (12 → 5) |
| generic-location overmerge | **0** |
| cross-date overmerge | **0** |
| source-only docs turned into incidents | **0** |
| all relationships explainable | **yes** (evidence arrays on every decision) |
| auto deletion/merge | **0** |
| production writes | **0** |
| Vercel deploy | **0** |
| GPT-6 | **off** |
| R4 | **not started** |

---

## After this

```text
R3_LOCAL_COMPLETE
        ↓
CANONICAL LINKER V1       ← done (READY_FOR_R4_LOCAL)
        ↓
R4 LOCAL
        ↓
linker regression / tune
        ↓
R5 LOCAL → R6 LOCAL → full R1–R6 QA
        ↓
only then production planning
```

V1 is intentionally conservative. Cross-witness same_event linking inside the Western U.S. series (e.g. whether Witness 1 night-1 equals Witness 2 night-1) is left for review-supported work in later linker revisions—not forced here.
