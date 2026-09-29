# UFO Dossier v2 — R01 Reconciliation Audit

**Date:** 2026-09-25  
**Canonical snapshot:** official war.gov `uap-data.csv` (fetched via curl_cffi)  
**SHA-256:** `c3f8209ef5f53a124bf3f30c4a36106ffaa63ea9770ad2d33e2ba5c4fec347c7`  
**Report JSON:** `pipeline/reports/r01_reconciliation.json`

---

## Answers

| Question | Answer |
|----------|--------|
| How many official R01 records exist? | **158** |
| How many exist in production (`source_files`)? | **176** (all releases mixed; R01-era corpus) |
| How many successfully linked? | **155** (127 exact URL + 28 DVIDS id) |
| How many production files have no official R01 match? | **21** (see local-only) |
| How many official R01 records aren't in production? | **3** PDFs (URL drift) |
| How many changed URLs? | Covered by DVIDS remaps (28) + 3 unresolved PDF URL drifts |
| How many deprecated official rows? | **0** in active official CSV |
| How many ambiguous mappings? | **0** |

---

## Match breakdown

```text
PURSUE R01 RECONCILIATION

canonical records:     158
production records:    176

exact matches:         127
normalized matches:    28   (all dvids_id)
missing locally:       3
local-only:            21
ambiguous:             0

writes (apply):
  source_records_upserted: 158
  source_files_linked:     155
  incident_sources:        476
```

### Missing locally (3 PDFs — not auto-linked)

Official URL ≠ production URL (title/path drift). Left for manual review:

1. `59_64634_711.5612[7-2852.pdf` (official) vs different FBI path in production  
2. `65_hs1-..._serial_153.pdf` (official) vs garbled `+M5+M11` production URL  
3. `DOW-UAP-D020` iraq-2023 (official) vs southern-united-states-2020 (production) — **different documents**, do not merge

### Local-only (21)

| Kind | Count | Notes |
|------|------:|-------|
| Slideshow JPGs | 17 | `/portals/.../Slideshow/` — not primary CSV asset rows |
| PDF URL-drift | 4 | counterparts of the 3 missing + NASA Gemini path variant |

---

## Gate status

| Gate | Result |
|------|--------|
| 0 unexplained ambiguous mappings | **PASS** |
| 0 unexpected incident changes | **PASS** (still 480 / 380 unflagged / 100 flagged) |
| 0 current source files accidentally duplicated | **PASS** (R01 link-only; no re-ingest of R01 binaries) |

---

## Official vs community snapshot

| | Community (SeeingBlue 2026-09-18) | Official (war.gov live 2026-09-25) |
|--|--:|--:|
| Records | 447 | **450** |
| PDF | 267 | **270** |
| Video | 134 | 134 |
| Image | 30 | 30 |
| Audio | 16 | 16 |
| R06 | 72 | **75** |

Diff: **+3** new LLE transcript PDFs (`LLE-UAP-D002/D003/D004`); **5** metadata modifications; **0** deprecated.  
One upstream external_id collision: `FBI-UAP-D014` used for both a PDF and an image — disambiguated as `pursue:FBI-UAP-D014:image`.

**Canonical source of truth:** official war.gov fetch.
