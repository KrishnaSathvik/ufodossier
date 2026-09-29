# Linker V1 — R4 human review

**Date:** 2026-09-28  
**Decision:** **Keep Linker V1 frozen. No V1.1.**

Artifacts reviewed: `pipeline/reports/r4_local/needs_review.json`, `linker_regression.json`, `linker/`.

## Findings

| Check | Result |
|---|---|
| bad `same_event` | none |
| obvious missed strong pairing that should auto-merge | none |
| series overmerge | none (Western US + Colorado fixtures still pass) |
| linker regression failures | 0 |

### CIA-UAP-D020 ↔ D021

Catalog-paired. D020 quote-rejected (OCR garble); D021 accepted one Prague incident. Linker correctly did **not** invent a D020 event member to satisfy the pairing.

### DOE-UAP-D005 ↔ DOE-UAP-D001

D005 quote-rejected; D001 is outside R4 extract set. No synthetic cross-release event member.

### NASA D030 / D031 / D032

Images only — metadata/pairing; **0** synthetic incidents. Good future media-pairing fixture.

### DOE-UAP-D004 (10 accepted)

Distinct green-fireball / meteorite episode rows (different dates/places). High-yield review alarm only — not a linker overmerge.

### R4 vs R2/R3 overlap

Zero R4-involving auto decisions. No obvious “same specific place+date” orphan that should have merged into a prior event.

## Carry-forward regression / watch (for R5+)

1. `CIA-D020/D021` — paired sources, only one accepted incident; never manufacture members for catalog pairs.
2. `DOE-D005/D001` — cross-release correspondence ↔ earlier source.
3. `NASA-D030/031/032` — media pairing only; 0 synthetic incidents.
4. `DOW-UAP-D090` — classifier watch (siblings D089/D091 = transcript/extract; D090 = other/source_only). Observe only; do not retune without evidence.
