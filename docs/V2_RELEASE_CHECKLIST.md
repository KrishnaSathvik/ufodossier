# UFO Dossier v2 — Release Checklist

## Gate 0 — Freeze (Phase 1)

- [x] Production audit written → `docs/V2_BASELINE_AUDIT.md`
- [x] 497 vs 480 explained (17 photo-caption deletions)
- [ ] **Supabase backup verified** (BLOCKING for ingestion)
- [x] Quote validation tests pass (5/5)
- [x] Production deploy SHA = `main` (`4cc4c90`)

## Gate 1 — Architecture scaffolding

- [x] `db/migrations/004_source_registry.sql`
- [x] `db/migrations/005_media_assets.sql`
- [x] `pipeline/sources/{base,pursue}.py`
- [x] `pipeline/discover.py` + `pipeline/diff_manifest.py`
- [ ] Apply 004/005 to Supabase (after backup)
- [ ] First official snapshot under `pipeline/snapshots/pursue/`
- [ ] `curl_cffi` in pipeline requirements

## Gate 2 — Data refresh R01–R06

- [ ] Reconcile existing R01 `source_files` → `source_records`
- [ ] Import R02–R06 metadata (no overwrite of R01 narrative rows)
- [ ] Download assets (resumable, checksummed)
- [ ] Text extraction cascade + community OCR cross-check
- [ ] Extract with Haiku + existing quote validator (do not relax)
- [ ] Dedup candidates → human review before merge
- [ ] Embed new incidents
- [ ] Collections / map refresh

## Gate 3 — Ask the Archive (GPT-6 Sol)

- [ ] Env-driven model config (`RAG_*`)
- [ ] Feature flag `ENABLE_GPT6_RAG=false` by default
- [ ] Citation validation after generation
- [ ] Golden-set eval ≥ current Sonnet quality
- [ ] Persistent rate limiting

## Gate 4 — Product surface

- [ ] `/releases` + `/releases/[n]`
- [ ] `/sources` + `/source/[id]`
- [ ] Homepage claims rename + dynamic release count
- [ ] Filter `flagged` from public counts (380 curated today)
- [ ] `/llms.txt` + sitemap updates

## Cutover

```text
deploy code (flags off)
  → verify
  → ENABLE_NEW_CORPUS=true
  → verify
  → ENABLE_GPT6_RAG=true
  → verify
```

## Out of scope for v2.0 (→ v2.1)

- NARA RG 615 provider
- AARO records/resolutions provider
- Full embedding dimension migration (1024→native)
- Advanced resolution-history UI
