# UFO Dossier

A searchable archive of every UAP incident from the U.S. government's declassified PURSUE files. Every claim tied to a verified quote. Every page linked to the original document on war.gov.

**Live:** [ufodossier.com](https://ufodossier.com)

---

## About

UFO Dossier takes the raw declassified documents from [war.gov/UFO](https://war.gov/UFO) and turns them into something you can actually search, browse, and explore. 497 incidents extracted from 117 source documents spanning 1890 to 2025, covering FBI, USAF, USN, NASA, DoD, and State Department files across 38 countries.

We are not affiliated with the U.S. government.

## Features

- **Incident Archive** — Browse all cases with date, location, agency, sensors, resolution status, and a verbatim excerpt from the source document
- **Interactive Map** — Geolocated incidents on a clustered dark-theme map with filters
- **Ask the Archive** — AI-powered Q&A grounded in the documents, with cited case IDs
- **Source Media** — Images, videos, and document covers from the declassified files

## How It Works

Every incident includes a verbatim quote pulled directly from the source PDF. If the quote can't be verified against the original text, the incident is dropped. No fabricated data makes it into the archive.

## Tech

Next.js, Supabase, Claude (extraction + RAG), Voyage AI (embeddings), MapLibre, Vercel.

## Media Mirroring

War.gov blocks server-side image requests (Akamai 403), so OG images and other server-rendered media need local copies. The mirror script uses Playwright to bypass this:

```bash
pip install playwright
playwright install chromium
python -m pipeline.mirror_media          # mirror all war.gov images
python -m pipeline.mirror_media --dry-run  # preview without downloading
python -m pipeline.mirror_media --limit 5  # process first 5 only
```

This downloads war.gov-hosted images via a real Chromium session, uploads them to Supabase Storage, and updates the incident rows to point at the stored copies. The original war.gov URL is preserved in `source_url` for citation.

## License

Code: MIT | Data: CC0
