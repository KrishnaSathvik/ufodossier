# V2 R2 Complete Local Exercise

**Date:** 2026-09-25  
**Mode:** Local / test-only — **no production writes, no deploy, no GPT-6**

## Verdict

**R2 = 6/6 PDFs exercised locally.**

| External ID | Class | contains_incidents | Action | Notes |
|-------------|----------------------|--------------------|--------|-------|
| CIA-UAP-D001 | historical_case_file | true | extract | OCR hardening recovered Sary Shagan green-circle incident |
| DOE-UAP-D001 | incident_report | true | extract→**source/media** | Thin caption; evidence-sufficiency gate |
| DOE-UAP-D002 | correspondence | false | source_only | Topic letter, not encounter |
| DOE-UAP-D003 | administrative | false | source_only | Club invitation |
| DOW-UAP-D017 | historical_case_file | true | extract | Selective OCR; multiple green-fireball incidents |
| **ODNI-UAP-D001** | **transcript** | **true** | **extract** | Senior USIC narrative; **4 accepted**, 1 evidence-drop |

## ODNI-UAP-D001 (final R2 PDF)

- **Cache:** `.cache/files/pursue/r2/ODNI-UAP-D001.pdf` (58,516 bytes)
- **Text:** born-digital native_good (2 pages, 5,728 chars) — no OCR needed
- **Class:** `transcript` / incident-bearing
- **Extraction report:** `pipeline/reports/r2_complete/odni_extraction.json`

| Outcome | Count |
|---------|------:|
| Accepted incidents | 4 |
| Quote-rejected | 0 |
| Evidence-insufficient | 1 |
| Dedupe vs 480 prod | all `new_event` |

Accepted (local only):

1. Mountain Range Helicopter Investigation with Multiple Orb Encounters  
2. Stationary Orb Formation Near Helicopter Rotor Disk  
3. Orbs Matching Fighter Jet Flight Path  
4. Orange Orbs Forming Triangle Formation  

## Prior R2 smoke (OCR hardening)

See `docs/V2_R2_OCR_HARDENING.md` — V1→V2 on first 5 PDFs: quote-valid 1→11, accepted 1→8, Pantex correctly gated.

## Safety checks (R2 local)

```text
fabricated accepted incidents       0 observed
thin captions accepted              0 (Pantex gated)
quote tolerance weakened            NO
production writes                   0
```

## Explicitly not done

- No full R2 production ingest  
- No Supabase / Vercel / GPT-6 changes  

## Next

18-document R3 readiness sample (`docs/V2_R3_READINESS_SAMPLE.md`).
