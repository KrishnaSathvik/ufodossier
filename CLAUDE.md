# UFODOSSIER

## Project

UFO Dossier is a searchable public archive of every UAP incident in the U.S. government's declassified PURSUE files (war.gov/UFO). The pipeline downloads PDFs from war.gov, imports community-OCR'd text from the UFO-USA GitHub mirror, extracts structured incident rows via Claude Haiku with substring-validated verbatim excerpts, embeds them with Voyage, and serves everything through a Next.js site with a RAG "ask the archive" feature powered by Claude Sonnet. The goal is trust: every claim ties to a verified quote from the source document, and every incident page links to the original file on war.gov.

## Stack

- **Web**: Next.js 15 (App Router) + Tailwind CSS, deployed on Vercel
- **DB**: Supabase (Postgres + pgvector + Storage). Schema in `db/schema.sql`
- **Pipeline**: Python 3. `pipeline/ingest_manifest.py` -> `pipeline/import_converted.py` -> `pipeline/extract.py` -> `pipeline/embed.py`
- **Extraction model**: Claude Haiku (`claude-haiku-4-5`) for structured extraction
- **RAG model**: Claude Sonnet (`claude-sonnet-4-7`) for answering user questions with streaming
- **Embeddings**: Voyage AI (`voyage-3`, 1536d) with OpenAI `text-embedding-3-small` fallback

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

## Pipeline status (Release 01)

Full extraction complete. Stats:
- **117** source files with OCR text (imported from UFO-USA community mirror)
- **94** source files yielded incidents
- **497** structured incidents extracted (substrate-validated excerpts)
- **497/497** have Voyage-3 embeddings (1024d, zero-padded to 1536)
- **Agencies**: FBI (88), USAF (116), USN (31), NASA (16), DoD mission reports, State Dept cables
- **Date range**: 1890 to 2025-04-11
- **Resolution**: 389 unresolved, 59 insufficient data, 49 identified
- Haiku extraction cost: ~$6 (well within $10 budget)

Key pipeline improvements applied:
- **Batch embeddings**: `embed_batch()` sends all incidents per file in 1 Voyage API call (was 1 call per incident). Reduced Voyage calls from ~500 to ~94.
- **Case ID collision handling**: `upsert_incident` catches duplicate case_id (23505) and extends the hash suffix.
- **Chunking fix**: oversized paragraphs (>60K chars) are now hard-split instead of becoming 1M-char chunks.
- **Rate limit resilience**: exponential backoff (5×2^n seconds, max 8 retries) + 1.5s inter-call delay.

## Web app status

All core routes verified working:
- `/` — homepage with live stats (497 incidents, 38 countries, sidebar breakdowns)
- `/incident/[id]` — case file with metadata, verbatim excerpt, similar incidents via vector search
- `/ask` — RAG query terminal (Voyage embed → `match_incidents` RPC → stream Sonnet)
- `/about` — methodology page
- `/images`, `/videos` — gallery pages (show "pipeline pending" until migration runs)

Navigation links: only archive, images, videos, ask, about (removed dead links to unbuilt map/timeline/data/releases pages).

## Open questions

1. `import_converted.py` sets `processed_at` to the string `"now()"` — does Supabase PostgREST evaluate that as SQL `now()`, or does it store the literal string? Needs verification.
2. ~~The `v_stats` view counts all incidents including flagged ones.~~ Currently no flagged incidents exist, so this is academic.
3. ~~Sidebar filter counts on `page.tsx` are hardcoded placeholder values.~~ Fixed — dynamic counts query.
4. ~~`getSimilar()` uses naive query.~~ Fixed — uses `match_incidents` RPC with embedding fallback.
5. ~~`ip_hash` not populated.~~ Fixed — `/api/ask` now hashes IP with salt.
6. No rate limiting on `/api/ask` beyond a 500-char question cap. `ip_hash` is now populated but not checked for throttling.
7. ~~`import_converted.py` matching over-matches FBI sections.~~ Fixed — Git Trees API, improved `_normalize_name`, match against all source_files with skip logic.
8. **BLOCKED**: Schema migration `db/migrations/001_add_media_columns.sql` needs to be run in Supabase SQL Editor (requires Postgres password, not the service key). This adds `image_url`/`video_url` columns and `v_media_incidents` view. After running, execute `python -m pipeline.extract --link-media` to link 14 existing media source files to incidents.
9. ~~Timezone bug in homepage year range.~~ Fixed — `parseInt(date.split("-")[0])` instead of `new Date(date).getFullYear()`.
10. ~~Dead nav links to unbuilt pages.~~ Fixed — removed map/timeline/data/releases links from TopBar and Footer.
