# UFODOSSIER Build Plan

Ordered checklist: from zip-on-disk to live site. Each step is scoped to a single sitting.

---

## Step 1: Supabase project setup

- [ ] Create a new Supabase project at supabase.com
- [ ] In the SQL editor, paste and run `db/schema.sql` (extensions, tables, views, RPC, RLS policies)
- [ ] Storage: create a bucket named `source-files` (set to public read)
- [ ] Settings > API: copy `Project URL`, `anon key`, `service_role key`
- [ ] Create `.env` in `pipeline/` with `SUPABASE_URL` and `SUPABASE_SERVICE_KEY`
- [ ] Create `.env.local` in `web/` with `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and `SUPABASE_SERVICE_ROLE_KEY`

**Done when**: you can connect to the Supabase dashboard, see all tables empty, and the `v_stats` view returns zeros.

---

## Step 2: Pipeline environment

- [ ] `cd pipeline && pip install -r requirements.txt`
- [ ] Set `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` (or `OPENAI_API_KEY`) in environment
- [ ] Run `python -m pipeline.tests.test_validation` — confirm 5/5 correct
- [ ] Verify `pipeline/db.py` connects to Supabase (quick sanity check)

**Done when**: validation test passes and Supabase client can read from `source_files` (returning empty list).

---

## Step 3: Ingest manifest (smoke test)

- [ ] `python -m pipeline.ingest_manifest --tranche 1 --limit 5`
- [ ] Check Supabase: `releases` table should have 1 row, `source_files` should have 5 rows
- [ ] Check Supabase Storage: `source-files` bucket should have 5 PDFs
- [ ] Inspect a few rows: `url` points to war.gov, `sha256` populated, `filename` makes sense

**Done when**: 5 source files in DB and Storage, no errors in pipeline output.

---

## Step 4: Ingest manifest (full run)

- [ ] `python -m pipeline.ingest_manifest --tranche 1`
- [ ] Expect ~120 PDF rows in `source_files` (idempotent — skips the 5 already done)
- [ ] Spot-check: total byte_size reasonable (~2.4 GB across all files), agencies populated

**Done when**: ~120 PDF source_files in DB with storage_paths.

---

## Step 5: Import OCR text from UFO-USA

- [ ] `python -m pipeline.import_converted --limit 10` (smoke test)
- [ ] Check that those 10 source_files now have `ocr_text` populated, `ocr_method = 'imported_ufo_usa_gemini'`
- [ ] `python -m pipeline.import_converted` (full run)
- [ ] Check: most PDF source_files should now have ocr_text. Log the matched/mismatched counts.

**Done when**: the majority of PDFs have `ocr_text` filled in. Note any mismatched folders for manual review.

---

## Step 6: Extract incidents (smoke test)

- [ ] `python -m pipeline.extract --limit 5`
- [ ] Check `incidents` table: should have rows with `title`, `summary`, `raw_excerpt`, `case_id`
- [ ] Manually verify 2-3 incidents: open the source PDF on war.gov and confirm `raw_excerpt` actually appears in the document
- [ ] Check that `extraction_model = 'claude-haiku-4-5'` and `extraction_version = 'v1.0'`

**Done when**: 5+ valid incidents in DB, manually verified excerpts, Haiku output quality acceptable.

---

## Step 7: Extract incidents (full run)

- [ ] `python -m pipeline.extract`
- [ ] Monitor: should process ~120 files, expect a few hundred incidents total
- [ ] Check API cost in Anthropic dashboard — should be $4-10 for all of Release 01
- [ ] If cost exceeds $10, stop and review chunk sizes / prompt before continuing
- [ ] Spot-check 5-10 incidents across different agencies

**Done when**: all source files processed, incidents table populated, cost within budget.

---

## Step 8: Generate embeddings

- [ ] Embeddings are generated during extraction (in `extract.py`'s `run()` function)
- [ ] Verify: `select count(*) from incidents where embedding is not null` should match total incident count
- [ ] If any are missing: `python -m pipeline.embed` (if a standalone backfill script exists)

**Done when**: every incident has a non-null embedding vector.

---

## Step 9: Web app local dev

- [ ] `cd web && npm install`
- [ ] `npm run dev`
- [ ] Homepage: verify stats populate from DB, recent incidents show, featured case renders
- [ ] `/ask`: type a test question, verify streaming response with citations
- [ ] `/incident/[id]`: click through from homepage, verify case file renders with all metadata
- [ ] `/about`: verify methodology page renders

**Done when**: all four pages render with real data locally. No console errors.

---

## Step 10: Fix placeholders

- [ ] Replace hardcoded sidebar counts in `page.tsx` with a real Supabase group-by query
- [ ] Replace naive `getSimilar()` in `incident/[id]/page.tsx` with vector similarity via `match_incidents` RPC
- [ ] Populate `ip_hash` in the `/api/ask` route for basic rate-limit readiness

**Done when**: sidebar shows real counts, similar incidents are actually similar, ask_log has ip_hash populated.

---

## Step 11: Domain + Vercel deploy

- [ ] Register domain (ufodossier.com or alternative)
- [ ] `cd web && vercel`
- [ ] Add all env vars in Vercel dashboard (Supabase URL, keys, Anthropic key, Voyage key)
- [ ] Deploy, verify production build works
- [ ] Point domain DNS at Vercel
- [ ] Test all four pages + /ask on production

**Done when**: site is live on the registered domain, all pages work, /ask streams responses.

---

## Step 12: Post-launch polish (future sittings)

- [ ] Map view page (use incident lat/lon, schematic style from demo.html)
- [ ] Timeline view
- [ ] Data download page (CSV, JSON, SQL dump)
- [ ] Releases log page
- [ ] Rate limiting on /api/ask
- [ ] OpenGraph / meta tags for social sharing
- [ ] RSS feed
- [ ] Tranche 2+ ingestion when new files drop on war.gov
