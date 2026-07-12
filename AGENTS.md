# AGENTS.md

Project overview and conventions live in `CLAUDE.md` and `README.md`. This file
adds environment/run guidance for agents.

## Cursor Cloud specific instructions

This repo has two independently-runnable components:

- **`pipeline/`** — Python 3 data pipeline (ingest → import → extract → embed).
  Dependencies are installed into a virtualenv at `/workspace/.venv` by the
  startup update script. Run scripts/tests with `/workspace/.venv/bin/python`.
- **`web/`** — Next.js 15 (App Router) site. Dependencies (`web/node_modules`)
  are installed by the update script. Standard scripts are in `web/package.json`
  (`dev`, `build`, `start`, `lint`).

### Pipeline

- Everything is a package module rooted at the repo root. Run from `/workspace`,
  not from inside `pipeline/`, e.g. `./.venv/bin/python -m pipeline.tests.test_validation`
  (running it as `cd pipeline && python -m pipeline.tests...` fails with
  `No module named 'pipeline'`).
- The verbatim-excerpt validation test (`pipeline/tests/test_validation.py`) is
  the core safety mechanism and runs fully offline with no API keys — it is the
  quickest way to prove the pipeline code works. Expect `5/5` correct / exit 0.
  Re-run it after any change to `pipeline/extract.py` (see `CLAUDE.md`).
- All other pipeline scripts (`ingest_manifest`, `import_converted`, `extract`,
  `embed`, etc.) require live credentials: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`,
  `ANTHROPIC_API_KEY`, `VOYAGE_API_KEY`. Copy `pipeline/.env.example` and fill in.
  `mirror_media.py` additionally needs `playwright install chromium` (browser
  binaries are not installed by default).

### Web

- Runtime config comes from `web/.env.local` (gitignored; template in
  `web/.env.example`). The app reads Supabase + Anthropic + Voyage keys.
- **The site has no local database — it talks to a hosted Supabase project.**
  Without real credentials there is no data to serve.
- **`next build` fails without a valid `NEXT_PUBLIC_SUPABASE_URL`**: it compiles
  and type-checks fine, then errors at prerender (`Error: supabaseUrl is
  required`, first hit on `/sitemap.xml`). This is a data/credentials issue, not
  a code issue.
- **`next dev` boots regardless.** Data-fetch helpers swallow query errors and
  fall back (`data ?? []`), so with placeholder Supabase env vars every route
  returns HTTP 200 and the full UI renders — just with zero/empty data
  ("No incidents yet. Pipeline pending."). This is the way to smoke-test the
  frontend without real credentials.
- **Lint is not wired up.** There is no ESLint config or `eslint` dependency, so
  `npm run lint` (`next lint`) only shows the interactive first-time-setup
  prompt and cannot run non-interactively. Static verification is TypeScript
  type-checking, which runs as part of `next build`.
