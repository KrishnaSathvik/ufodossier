# UFODOSSIER

## Project

UFO Dossier is a searchable, source-grounded archive of publicly released U.S. government UAP records from the PURSUE files (war.gov/UFO). The pipeline preserves original files, extracts structured incident fragments with Claude Haiku and substring-validated verbatim excerpts, links fragments into canonical events, embeds published rows with Voyage, and serves a Next.js site. Ask the Archive is provider-configurable. Extraction stays on Haiku. The goal is trust: a claim stays tied to a verified quote, and a fragment is not described as an event unless the linker says so.

## Stack

- **Web**: Next.js 15 (App Router) + Tailwind CSS, deployed on Vercel
- **DB**: Supabase (Postgres + pgvector + Storage). Schema in `db/schema.sql`
- **Pipeline**: Python 3. `pipeline/ingest_manifest.py` -> `pipeline/import_converted.py` -> `pipeline/extract.py` -> `pipeline/embed.py`
- **Extraction model**: Claude Haiku (`claude-haiku-4-5`) for structured extraction
- **RAG**: environment-selected. Historical production baseline is `claude-sonnet-4-5-20250929`. The evaluated V2 chain, applied only after `RAG_PROVIDER=openai`, is `gpt-6-sol` at medium, then the same model at low, then `claude-sonnet-5-5` if OpenAI fails. The unset default remains the historical Anthropic model so a process start does not flip production. See `docs/V2_RAG_MODEL_EVAL.md`.
- **Embeddings**: Voyage AI (`voyage-3`, 1024-d zero-padded to 1536). `EMBEDDING_PROVIDER=voyage` and `EMBEDDING_MODEL=voyage-3`. A Voyage failure does not switch to OpenAI embeddings.

## The non-negotiable

The substring-validated verbatim excerpt mechanism in `pipeline/extract.py` is the single most important piece of this project. Here is what it does and why:

- **What**: Every incident Haiku extracts must include a `raw_excerpt` field containing 1-3 sentences copied verbatim from the source document. The `_validate_incident` function checks that this excerpt actually appears in the source text (exact normalized substring match, or 90% word overlap in a sliding window). If validation fails, the entire incident is dropped.
- **Why**: Without this, Haiku will occasionally fabricate incidents (e.g., inventing Roswell crash details from its training data). A single hallucinated row on a public archive destroys credibility. The validator is the line between a trustworthy dataset and garbage.
- **Where the test lives**: `pipeline/tests/test_validation.py`
- **How to re-run**: `cd pipeline && python -m pipeline.tests.test_validation` (no API keys needed, no network). Expects 5/5 correct: 3 real verbatim quotes kept, 1 fabricated quote dropped, 1 paraphrased quote dropped.
- **When to re-run**: Every time you change `SYSTEM_PROMPT` or `_validate_incident` in `extract.py`. If this test breaks, stop and fix it before doing anything else.

## Aesthetic

Declassified-archive feel. Late 1970s government reading room. See `demo.html` for the canonical visual reference — it is the target, not a draft.

- **Type**: Special Elite (typewriter/hero/display), JetBrains Mono (technical text, UI, data tables), Newsreader (editorial prose, body copy on about/incident pages)
- **Palette**: near-black `#0a0a0a` background, off-white `#e8e6e0` ink, amber `#ff9933` accent, red `#c8302a` stamps, muted rules `#2a2925`
- **Effects**: scan-line overlay (`body::before`), radial vignette (`body::after`), blinking cursor dot, pulsing map dots
- **Components**: stamp borders, redaction bars (`background: ink; color: ink`), tag pills with `border: 1px solid currentColor`, verbatim-excerpt blocks with amber left border, document mockups, featured-case cards
- **DO NOT**: use emoji, rounded corners on stamps, gradient backgrounds, purple/neon/synthwave colors, glow effects, "spooky alien" imagery, Lottie animations, or Wingdings

## Data flow

```
ingest_manifest.py   Pull CSV from UFO-USA mirror, download PDFs from war.gov,
                     register in source_files table, upload to Supabase Storage

import_converted.py  Fetch page-by-page Markdown from UFO-USA converted/ tree,
                     match to source_files rows, write ocr_text column

extract.py           For each source_file with ocr_text but no incidents:
                     call Haiku -> parse JSON -> _validate_incident (substring
                     check on raw_excerpt) -> write to incidents table

embed.py             Generate Voyage embeddings for title+summary+excerpt,
                     write to incidents.embedding column

Site reads from      v_incident_full view (joins incidents + source_files +
Supabase via         releases), v_stats view, match_incidents RPC for /ask
```

## Cost ceiling

Release 01 extraction (~120 PDFs, ~4,185 pages) should land between $4 and $10 in Haiku API costs. Embeddings add ~$0.10 (Voyage). If a run quote exceeds $10, stop and check the prompt (chunk sizes, max_tokens, whether you're re-processing already-extracted files) before spending.

## Conventions

- Keep backups before edits: `cp file.tsx file.backup.tsx`
- Prefer targeted str_replace edits over full file rewrites
- Never delete files in `/mnt/user-data/outputs`
- Always smoke-test pipeline scripts with `--limit 5` before full runs
- Run `python -m pipeline.tests.test_validation` after any change to extract.py
- The demo.html is the visual target. Do not redesign the aesthetic.

## Key files

| File | Role |
|------|------|
| `demo.html` | Canonical visual reference (static HTML/CSS) |
| `db/schema.sql` | Full Postgres schema, views, RPC, RLS policies |
| `pipeline/extract.py` | Haiku extraction + substring validation (most important file) |
| `pipeline/tests/test_validation.py` | Safety-mechanism test (must pass 5/5) |
| `web/src/app/page.tsx` | Homepage (stats, sidebar, featured case, recent list) |
| `web/src/app/api/ask/route.ts` | RAG endpoint (embed question -> vector search -> stream Sonnet) |
| `web/tailwind.config.js` | Tailwind theme with all design tokens |
| `web/src/app/globals.css` | CSS variables, scan-line, vignette, component classes |
| `pipeline/seed_collections.py` | Seed 7 curated collections into Supabase |
| `web/src/app/collections/page.tsx` | Collections index (grid of curated sets) |
| `web/src/app/collections/[slug]/page.tsx` | Single collection detail page |
| `web/src/components/ShareRow.tsx` | Copy link / X / Bluesky share buttons |

## Media support (v1)

Video and image support added. Key additions:

- **Schema**: `incidents.image_url` and `incidents.video_url` columns. Migration at `db/migrations/001_add_media_columns.sql`. New `v_media_incidents` view for gallery pages.
- **Pipeline**: `extract.py` now queries both `ocr_text` and `transcript` source files. Video/image source files automatically set `video_url`/`image_url` on extracted incidents. `--link-media` flag does token-based matching of media files to existing incidents.
- **Site**: Incident page renders `<video controls>` or `<img>` when media is available. FeaturedCase shows image/video instead of DocumentMockup. New `/images` and `/videos` gallery pages. OG image meta tags on incident pages.
- **Nav**: TopBar and Footer include images/videos links.

Pipeline usage for media:
```
python -m pipeline.ingest_manifest --tranche 1 --include-non-pdf  # ingest videos/images
python -m pipeline.extract --link-media                            # match media to incidents
```

## Pipeline status (V2 local)

Corpus QA is complete for the official PURSUE inventory of six releases. Counts on the site are computed from `pipeline/reports/corpus_qa/` and the linker graph. Do not treat fragments and canonical events as the same number. R1 production rows were not re-extracted. The reviewed R2–R6 fragments, linker graph, and Voyage embeddings are in the production database as of 2026-09-29. The site has not been redeployed, and `RAG_PROVIDER` stays unset. Details: `docs/V2_R1_R6_CORPUS_QA.md`, `docs/V2_LOCAL_RELEASE_GATE.md`, and `docs/PRODUCTION_MIGRATION_REPORT.md`.

Extraction model remains `claude-haiku-4-5`. Embeddings remain Voyage `voyage-3`, stored as `vector(1536)`.

## Web app status

Local routes include `/`, `/incidents`, `/incident/[slug]`, `/map`, `/collections`, `/releases`, `/releases/[release]`, `/sources`, `/source/[id]`, `/media`, `/audio`, `/ask`, and `/about`.

Ask the Archive lives in `web/src/lib/rag/`. The route does not hardcode the active model. Telemetry defaults to a local JSONL file so this milestone does not write `ask_log` in production. `RAG_TELEMETRY_SINK=supabase` is the later switch.

Navigation: archive, map, collections, releases, sources, media, audio, ask, about.

## Open questions

1. `import_converted.py` sets `processed_at` to the string `"now()"` — does Supabase PostgREST evaluate that as SQL `now()`, or does it store the literal string? Needs verification.
2. ~~Production still needs the reviewed V2 data migration.~~ Data load finished 2026-09-29. Deploy and the RAG provider switch have not been started. See `docs/PRODUCTION_MIGRATION_REPORT.md`.
3. ~~Sidebar filter counts on `page.tsx` are hardcoded placeholder values.~~ Fixed — dynamic counts query.
4. ~~`getSimilar()` uses naive query.~~ Fixed — uses `match_incidents` RPC with embedding fallback.
5. ~~`ip_hash` not populated.~~ Fixed — `/api/ask` now hashes IP with salt.
6. `/api/ask` rate-limits per hashed IP in memory (10 requests per minute) and caps questions at 500 characters. That limiter is single-process only.
7. ~~`import_converted.py` matching over-matches FBI sections.~~ Fixed — Git Trees API, improved `_normalize_name`, match against all source_files with skip logic.
8. Canonical events and source-record ingestion columns are in production via `db/migrations/011_canonical_and_ingestion.sql`. `db/migrations/010_rag_telemetry_DESIGN_ONLY.sql` was not applied. Do not set `RAG_TELEMETRY_SINK=supabase`.
9. ~~Timezone bug in homepage year range.~~ Fixed — `parseInt(date.split("-")[0])` instead of `new Date(date).getFullYear()`.
10. Homepage counts come from the local catalog. Published case-file counts still come from Supabase and are labeled separately.
