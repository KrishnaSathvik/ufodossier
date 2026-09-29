# UFO Dossier

A searchable, source-grounded archive of publicly released U.S. government UAP records from the PURSUE releases at [war.gov/UFO](https://war.gov/UFO). Every published claim is tied to a verified quote. Fragments, canonical events, and source records are counted separately.

**Live site:** [www.ufodossier.com](https://www.ufodossier.com) still serves the earlier published case files. The V2 local catalog covers all six PURSUE releases and has not been deployed.

---

## About

The local V2 catalog is computed from the source inventory and the linker graph, not from a hardcoded total. It distinguishes:

- official source records
- verified incident fragments
- canonical events
- event series

A fragment is a validated excerpt. Several fragments can belong to one event. A series is a group of events.

We are not affiliated with the U.S. government.

## Features

- **Archive** — Published case files, plus the local catalog of fragments and events
- **Releases and sources** — PURSUE Release 01 through Release 06, with per-file processing state
- **Map, collections, media, audio** — Geolocated published cases, curated sets, images and video, and official audio metadata
- **Ask the Archive** — Evidence-grounded answers. Provider and model come from environment variables (`RAG_PROVIDER`, `RAG_MODEL`, `ANTHROPIC_RAG_MODEL`). Extraction stays on Claude Haiku 4.5.

## How It Works

Official discovery, file preservation, SHA-256 when the bytes are cached, text or OCR, document classification, extraction, verbatim quote checks, an evidence gate, then canonical-event linking. If a quote is not in the source, the fragment is dropped.

## Tech

Next.js, Supabase, Claude Haiku for extraction, a provider-agnostic Ask path (Anthropic Messages and OpenAI Responses), Voyage embeddings, MapLibre. Production deployment is a separate step from this local gate.

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
