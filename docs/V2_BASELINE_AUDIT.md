# UFO Dossier v2 — Baseline Audit

**Audit date:** 2026-09-25T01:49:03Z  
**Auditor:** automated production freeze (Phase 1)  
**Status:** production state understood; **DB backup not yet verified** — ingestion gated

---

## Snapshot

| Field | Value |
|-------|-------|
| Git commit (local `main`) | `4cc4c90a1ba51b3263439c09b78c6efefe78dc49` |
| Deployment SHA (Vercel production) | `4cc4c90` (matches `main`) |
| Deployment ID | `dpl_EbVeNoYxz2iPuZuJ2k3VKDGxh8fW` |
| Production URL | https://www.ufodossier.com |
| Deploy created | 2026-05-11 (≈136d before audit; no newer production cutover) |
| Supabase project ref | `whyrlabwefasmmebtzja` |
| Last known PURSUE release in DB | **Release 01 only** (`releases.tranche_number=1`, `captured_at=2026-05-08`) |
| Incident count (all rows) | **480** |
| Published / unflagged | **380** |
| Flagged | **100** (`flag_reason=duplicate_excerpt`) |
| Source files (all types) | **176** |
| PDF source files (`v_stats.source_file_count`) | **117** |
| Embeddings present | **480 / 480** |
| Media on incidents | image_url **21**, video_url **9**, cover_image_url **480** |
| Slugs | **480 / 480** |
| Collections | **7** |
| RAG model (code + `ask_log`) | `claude-sonnet-4-5-20250929` |
| Extraction model (code) | `claude-haiku-4-5` |
| Embedding model | Voyage `voyage-3` (1024d, zero-padded to 1536) |

### `v_stats` (live)

```json
{
  "incident_count": 480,
  "source_file_count": 117,
  "unresolved_count": 385,
  "country_count": 38,
  "earliest": "1890-01-01",
  "latest": "2025-04-11",
  "last_tranche": "2026-05-08T21:25:03.638006+00:00"
}
```

### Source file breakdown

| file_type | count |
|-----------|------:|
| pdf | 117 |
| mp4 | 28 |
| jpg | 23 |
| png | 8 |
| **total** | **176** |

OCR text: 117 · Transcripts: 28

### Resolution (all incidents)

| status | count |
|--------|------:|
| unresolved | 385 |
| identified | 49 |
| insufficient_data | 46 |

---

## 497 vs 480 — explained

| Claim | Source | Reality |
|-------|--------|---------|
| “497 incidents” | `CLAUDE.md`, `README.md` | **Stale documentation** from pre-cleanup extraction |
| “480 incidents” | Live homepage + `v_stats` | **Correct current DB total** |

Root cause (commit `7030f8f`, 2026-05-10):

> Delete 17 incidents from photo-only FBI Photo PDFs (captions, not document narratives).  
> **480 incidents remain**, all backed by real document narratives.

```
497 extracted − 17 photo-caption deletions = 480
```

**Secondary quality issue (not reflected in homepage count):**

- 100 of the remaining 480 are `flagged=true` with `flag_reason=duplicate_excerpt`
- Homepage / `v_stats` / `v_incident_full` queries **do not filter** `flagged=false`
- Effective curated corpus if flags were honored: **380**

---

## Schema / migration status

| Migration | Repo file | Production status |
|-----------|-----------|-------------------|
| Media columns (`image_url`, `video_url`) | `db/migrations/001_add_media_columns.sql` | **Applied** (live site renders media; columns queryable) |
| Slug column | `db/migrations/002_add_slug_column.sql` | **Applied** (480/480) |
| Cover image URL | `db/migrations/003_add_cover_image_url.sql` | **Applied** (480/480) |
| Source registry / media_assets / canonical | *(v2 — not yet)* | **Absent** |

`CLAUDE.md` still marks migration 001 as **BLOCKED** — that note is obsolete.

---

## RAG / Ask the Archive

| Item | Value |
|------|-------|
| Code path | `web/src/app/api/ask/route.ts` |
| Provider | Anthropic |
| Model | `claude-sonnet-4-5-20250929` |
| Docs claim | `claude-sonnet-4-7` — **wrong** |
| GPT-5.4 / GPT-6 | **Not used** in `main` or production |
| Rate limit | In-memory Map (10 req / 60s / ip_hash) — not durable |
| Citation validation post-gen | **None** |
| Env keys on web | `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`, `SUPABASE_*`, `IP_HASH_SALT` — **no `OPENAI_API_KEY` / `RAG_*`** |

Recent `ask_log.model` samples (2026-07 → 2026-08) all = `claude-sonnet-4-5-20250929`.

---

## Ingestion architecture (current)

| Item | Status |
|------|--------|
| Canonical manifest | Community UFO-USA `uap-csv.csv` (Release 01 only) |
| Code | `pipeline/ingest_manifest.py` → `MANIFEST_URL` + hardcoded `WAR_GOV_BASE=.../Release_1` |
| Official combined CSV | `https://www.war.gov/Portals/1/Interactive/2026/UFO/uap-data.csv` — **Akamai 403** to plain curl from this environment |
| Releases indexed | 1 |

This confirms the plan’s Phase 2 diagnosis: Release 07+ cannot be incremental on the current path.

---

## External source verification (2026-09-25)

### Community accelerator (SeeingBlue/uap-corpus-viewer)

- Snapshot `2026-09-18` CSV parses to **447** rows
- Type counts: PDF 261 + `PDF ` (trailing space) 6 = **267**, VID **134**, IMG **30**, AUD **16**
- Release dates: R01 158 · R02 64 · R03 72 · R04 40 · R05 41 · R06 72
- Matches plan inventory (active 447; 5 deprecated R01 rows exist in their full index)

### Official war.gov

- Portal HTML and `uap-data.csv` return **Akamai Access Denied (403)** without TLS impersonation (`curl_cffi` / browser)
- Community docs confirmed; our fetcher must not trust reconstructed `Release_1` URLs

### GPT-6 Sol

- Confirmed at OpenAI docs: model id `gpt-6-sol`, Responses API recommended, 1.05M context, `reasoning.effort` supported
- Safe default for Ask: `reasoning.effort=low`

### Quote validator

- `python3 -m pipeline.tests.test_validation` → **5/5 PASS** (keep verbatim / drop fabricated / drop paraphrase)

---

## Environment inventory (names only — no secrets)

**`web/.env.local`:** `ANTHROPIC_API_KEY`, `IP_HASH_SALT`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `VOYAGE_API_KEY`

**`pipeline/.env`:** `ANTHROPIC_API_KEY`, `SUPABASE_SERVICE_KEY`, `SUPABASE_URL`, `VOYAGE_API_KEY`

**Missing for v2 RAG:** `OPENAI_API_KEY`, `RAG_PROVIDER`, `RAG_MODEL`, `RAG_REASONING_EFFORT`, feature flags `ENABLE_GPT6_RAG`, `ENABLE_NEW_CORPUS`

**Supabase MCP:** project `whyrlabwefasmmebtzja` is **not** in the MCP-linked org list (ApplyTrak / NutriScope / KyneChat). SQL via MCP unavailable; REST with service key works.

---

## Phase 1 gate checklist

| Gate | Status |
|------|--------|
| Production state understood | **PASS** |
| 497 vs 480 explained | **PASS** (17 deletions; docs stale) |
| Database backed up | **FAIL — not verified** (manual Supabase backup / dump required before ingestion) |
| Current release reproducible | **PARTIAL** — R01 pipeline exists; official R06 path / Akamai / checksums not yet in-repo |

**Do not start R02–R06 asset ingestion until backup is confirmed.**

Code scaffolding, schema migrations (unapplied), and feature-flagged RAG work may proceed.

---

## Immediate follow-ups before Phase 6 import

1. Take a Supabase project backup / logical dump of `incidents`, `source_files`, `releases`, `collections`, `ask_log`
2. Fix homepage / `v_stats` to exclude `flagged` (or publish 380 as the curated count)
3. Update `CLAUDE.md` / `README.md` counts (480 total, 380 unflagged, R01 only)
4. Replace UFO-USA manifest with official `uap-data.csv` discovery + snapshots
5. Add `curl_cffi` (or equivalent) for war.gov fetches
6. Feature-flag GPT-6 Sol Ask behind `ENABLE_GPT6_RAG` after golden-set eval
