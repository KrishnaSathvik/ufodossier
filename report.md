# UFO Dossier -- Pre-Production Verification Report

**Date:** 2026-05-09
**Domain:** ufodossier.com
**Stack:** Next.js 15, Supabase, Tailwind CSS, Vercel

---

## Top-Level Summary

| Section | Verdict | Critical Issues |
|---------|---------|-----------------|
| 1. Data Integrity | **PASS (with notes)** | 497 incidents (above expected 400-450 range); geocoding at 58.4% (below 60% target) |
| 2. Build Health | **PASS** | Zero TS errors; MapLibre contained to /map chunk |
| 3. Page Rendering | **PASS (with gaps)** | All 7 routes render; no not-found.tsx, error.tsx, or loading.tsx |
| 4. SEO Infrastructure | **PASS (partial)** | Sitemap has 396/497 incidents; homepage missing canonical; some pages lack og overrides |
| 5. Pipeline & Validation | **PASS** | Validator 5/5; random sample clean; source URLs well-formed |
| 6. Operational Readiness | **FAIL** | .env.example contains real API keys; no rate limiting on /api/ask |
| 7. Performance | **FAIL** | Homepage HTML 568 KB (all 497 incidents inline); no next/image usage; no dynamic imports |
| 8. Pre-launch Checklist | **FAIL** | No .gitignore in web/; no favicon; no security headers; no error pages |

---

## Section 1: Data Integrity

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 1.1 | Total incident count | **PASS** | 497 incidents. Above user's expected 400-450 range but verified legitimate (multi-incident PDFs like FBI HQ case files). |
| 1.2 | Duplicate case_ids | **PASS** | 0 duplicates. 497/497 unique case_ids. |
| 1.3 | Missing slugs | **PASS** | 0 missing. 497/497 slugs populated. |
| 1.4 | "null" string branches | **PASS** | 0 found. All branch values are proper strings or SQL NULL. |
| 1.5 | Missing/short excerpts | **PASS** | 0 incidents with missing or < 20 char excerpts. |
| 1.6 | Pre-Roswell incidents (<1947) | **PASS** | 12 found. Historically legitimate (1890 airship wave, 1940s wartime sightings). |
| 1.7 | Max incidents per PDF | **TODO** | Top source: 66 incidents from one FBI HQ file. Exceeds threshold of 10, but these are legitimate multi-case compendiums. Needs review. |
| 1.8 | Geocoding coverage | **TODO** | 58.4% geocoded (290/497). Below 60% target by 1.6 percentage points. |
| 1.9 | Cover image coverage | **TODO** | 372/497 incidents have cover_image_url. Not every PDF-sourced incident has one. |

---

## Section 2: Build Health

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 2.1 | `npm run build` | **PASS** | Succeeds clean. Zero TypeScript errors. |
| 2.2 | Route sizes < 200 KB | **PASS (exception)** | /map at 321 KB (expected for MapLibre GL). All other routes under 200 KB. |
| 2.3 | MapLibre containment | **PASS** | MapLibre JS + CSS only in /map chunk. Not leaked to other routes. |
| 2.4 | ESLint | **TODO** | No .eslintrc config file. ESLint not configured for the project. |
| 2.5 | Hydration warnings | **PASS** | No hydration mismatches detected. |

---

## Section 3: Page Rendering Smoke Tests

| # | Route | Status | Detail |
|---|-------|--------|--------|
| 3.1 | `/` (homepage) | **PASS** | Exports default, all imports resolve, client/server boundaries correct. Missing own metadata export (relies on layout defaults -- no page-level canonical/description). |
| 3.2 | `/incident/[slug]` | **PASS** | generateMetadata with dynamic title/description/canonical/OG. Calls notFound() on missing slug. UUID redirect works. Next.js 15 async params pattern correct. |
| 3.3 | `/map` | **PASS** | Static metadata export. Empty-state fallback for zero geolocated incidents. No Footer (intentional for full-viewport map). |
| 3.4 | `/media` | **PASS** | Static metadata export. Suspense wrapping for useSearchParams. Per-tab empty states. |
| 3.5 | `/about` | **PASS** | Static metadata. Static page, no data fetching. |
| 3.6 | `/ask` | **PASS** | Static metadata with robots noindex. Server/client split correct. AskForm has internal loading state and error catch. |
| 3.7 | `/i/[id]` (redirect) | **PASS** | robots noindex/nofollow. Always redirects or calls notFound(). No JSX rendered. |
| 3.8 | `not-found.tsx` exists | **FAIL** | Does not exist. notFound() calls on /incident and /i routes fall through to Next.js default 404 page (unstyled). |
| 3.9 | `error.tsx` exists | **FAIL** | Does not exist. Runtime errors show Next.js default error UI. |
| 3.10 | `loading.tsx` exists | **FAIL** | Does not exist anywhere. No loading indicators during server-side data fetching on navigation. |

---

## Section 4: SEO Infrastructure

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 4.1 | sitemap.ts generates valid URLs | **PASS** | Batch pagination (200/batch). 4 static pages + incident pages. Revalidates hourly. |
| 4.2 | Sitemap incident count | **FAIL** | 396/497 incidents in sitemap. Supabase project-level max_rows limits. Pagination added but underlying limit persists. |
| 4.3 | robots.ts correct | **PASS** | Allows /, disallows /api/ and /i/, points to sitemap.xml. |
| 4.4 | Homepage canonical | **FAIL** | Homepage has no page-level metadata export. No canonical URL set. |
| 4.5 | Incident page canonical | **PASS** | generateMetadata sets canonical to /incident/{slug}. |
| 4.6 | /ask noindex | **PASS** | robots: { index: false, follow: true }. AI answers not indexed. |
| 4.7 | /i/[id] noindex | **PASS** | robots: { index: false, follow: false }. Redirect route not indexed. |
| 4.8 | OG image (root) | **PASS** | opengraph-image.tsx at app root. 1200x630 PNG, edge runtime, declassified aesthetic. |
| 4.9 | OG image (incident) | **PASS** | opengraph-image.tsx at incident/[slug]. Dynamic rendering with case details. |
| 4.10 | Twitter card meta | **PASS** | summary_large_image in layout.tsx. |
| 4.11 | /media, /about, /map og overrides | **TODO** | These pages set title/description but don't override og:title/og:description explicitly. They inherit from layout defaults + page title template. Acceptable but not optimal. |
| 4.12 | JSON-LD structured data | **PASS** | Homepage (Dataset), incident (Report), media (CollectionPage), about (WebPage). |

---

## Section 5: Pipeline & Data Validation

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 5.1 | Validator test (5/5) | **PASS** | `python -m pipeline.tests.test_validation` passes 5/5: 3 real quotes kept, 1 fabrication dropped, 1 paraphrase dropped. |
| 5.2 | Random incident sample | **PASS** | 10 random incidents checked: all have proper case_id, title, summary, raw_excerpt, source_file_id, and embedding. |
| 5.3 | Source URLs well-formed | **PASS** | All source_url values are valid war.gov URLs. |
| 5.4 | SYSTEM_PROMPT intact | **PASS** | extract.py SYSTEM_PROMPT and _validate_incident function confirmed unchanged. |

---

## Section 6: Operational Readiness

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 6.1 | .env.example real secrets | **FAIL -- CRITICAL** | `.env.example` contains real Supabase, Anthropic, and Voyage API keys. Not placeholder values. Must rotate immediately. |
| 6.2 | .env.local not committed | **PASS** | Currently untracked. But see 6.3. |
| 6.3 | .gitignore covers .env | **FAIL -- CRITICAL** | No .gitignore in web/ directory. No root .gitignore covering .env patterns. A single `git add .` will commit secrets. |
| 6.4 | Server/client env var separation | **PASS** | NEXT_PUBLIC_ prefix used correctly. Server-only keys (SUPABASE_SERVICE_KEY, ANTHROPIC_API_KEY, VOYAGE_API_KEY) not exposed to client. |
| 6.5 | Rate limiting on /api/ask | **FAIL** | No rate limiting. ip_hash is logged but not checked for throttling. Attacker can spam endpoint and rack up Anthropic/Voyage API costs. |
| 6.6 | RLS policies | **PASS** | Supabase RLS policies intact on all tables. |
| 6.7 | ask_log public read | **TODO** | ask_log table has a public read policy. User questions/answers are world-readable. May be intentional for transparency, but worth confirming. |
| 6.8 | 404 handling | **PASS (partial)** | notFound() calls work but fall through to unstyled default. See 3.8. |
| 6.9 | Question length cap | **PASS** | /api/ask limits questions to 500 chars. |

---

## Section 7: Performance

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 7.1 | Homepage HTML size | **FAIL** | 568 KB. All 497 incidents server-rendered into initial HTML. getAllIncidents() has no .limit(). |
| 7.2 | Map page HTML size | **FAIL** | 420 KB. Full incident data (summaries, excerpts) embedded as props for MapClient. |
| 7.3 | Other route sizes | **PASS** | about (24 KB), ask (16 KB), images (9 KB), videos (9 KB). Reasonable. |
| 7.4 | next/image usage | **FAIL** | Zero imports of next/image. 8 raw `<img>` tags across page.tsx, incident page, MediaCard, MapPanel. No width/height attributes (causes CLS). |
| 7.5 | next.config image domains | **FAIL** | No images.remotePatterns configured. Cannot use next/image for remote images until added. |
| 7.6 | loading="lazy" | **PASS (partial)** | MediaCard.tsx uses loading="lazy". Missing on page.tsx, incident page, MapPanel. |
| 7.7 | Font loading | **PASS** | next/font/google with font-display: swap. Self-hosted .woff2 files. 4 fonts, proper weight subsetting. |
| 7.8 | Dead preconnect hints | **TODO** | layout.tsx has preconnect links for fonts.googleapis.com and fonts.gstatic.com. Unnecessary since next/font self-hosts. Wasted DNS lookups. |
| 7.9 | MapLibre dynamic import | **FAIL** | MapView uses static top-level `import maplibregl`. Not wrapped in next/dynamic with ssr: false. |
| 7.10 | next/dynamic usage | **FAIL** | Zero uses of next/dynamic anywhere in the codebase. |
| 7.11 | Tailwind purge | **PASS** | content path configured in tailwind.config.js. Unused utilities tree-shaken. |
| 7.12 | globals.css | **PASS** | 61 lines. Extremely lean. |
| 7.13 | select("*") usage | **TODO** | 4-5 instances of select("*"): v_stats (acceptable), getFeatured() (3 cascading queries), incident page. Consider explicit column lists. |
| 7.14 | ISR revalidate settings | **PASS** | Homepage 300s, incident 600s, map 600s, media 600s, sitemap 3600s. Reasonable. |
| 7.15 | Third-party scripts | **PASS** | None present. Only inline dark-mode script. |
| 7.16 | getFeatured() cascading queries | **TODO** | Up to 3 sequential Supabase queries. Could be a single query with COALESCE logic. |

---

## Section 8: Pre-launch Checklist

| # | Check | Status | Detail |
|---|-------|--------|--------|
| 8.1 | metadataBase = ufodossier.com | **PASS** | Correctly set in layout.tsx. |
| 8.2 | sitemap base URL | **PASS** | Uses https://ufodossier.com. |
| 8.3 | vercel.json | **PASS (N/A)** | Not needed for standard Next.js deploy. |
| 8.4 | next.config production settings | **TODO** | Only has experimental.typedRoutes. No security headers, no image domains, no redirects. |
| 8.5 | .gitignore in web/ | **FAIL -- CRITICAL** | Does not exist. See 6.3. |
| 8.6 | .env.example has real secrets | **FAIL -- CRITICAL** | See 6.1. |
| 8.7 | Canonical URLs on key pages | **PASS (partial)** | Set on /about, /media, /map, /incident/[slug]. Missing on /, /ask, /images, /videos. |
| 8.8 | OG images | **PASS** | Root and per-incident opengraph-image.tsx. Twitter card configured. |
| 8.9 | Security headers | **FAIL** | None defined. No X-Frame-Options, X-Content-Type-Options, CSP, HSTS, Referrer-Policy, Permissions-Policy. |
| 8.10 | Security middleware | **FAIL** | No middleware.ts exists. |
| 8.11 | not-found.tsx | **FAIL** | Does not exist. See 3.8. |
| 8.12 | error.tsx | **FAIL** | Does not exist. See 3.9. |
| 8.13 | humans.txt | **PASS** | Present with proper credits. |
| 8.14 | Favicon | **FAIL** | No favicon in app/ or public/. Blank tab icon in browsers. |

---

## Blockers (must fix before launch)

| Priority | Item | Section | Impact |
|----------|------|---------|--------|
| **P0** | .env.example contains real API keys (Supabase, Anthropic, Voyage) | 6.1, 8.6 | Key leak if file is ever committed. Rotate keys immediately. |
| **P0** | No .gitignore in web/ directory | 6.3, 8.5 | `git add .` will commit .env.local with all secrets. |
| **P1** | No rate limiting on /api/ask | 6.5 | Attacker can spam endpoint, burning Anthropic + Voyage API credits with no throttle. |
| **P1** | Homepage HTML is 568 KB (all 497 incidents inline) | 7.1 | Slow initial load, wasted bandwidth. getAllIncidents() needs server-side .limit(). |
| **P1** | No not-found.tsx | 3.8, 8.11 | Bad links show unstyled Next.js default 404, breaking the archive aesthetic. |
| **P1** | No favicon | 8.14 | Blank tab icon looks unprofessional. |

---

## Nice-to-Haves (post-launch improvements)

| Item | Section | Notes |
|------|---------|-------|
| Switch `<img>` to `next/image` (8 tags) | 7.4 | Requires adding images.remotePatterns to next.config. Improves CLS, lazy loading, format negotiation. |
| Add security headers (CSP, HSTS, X-Frame-Options) | 8.9 | Standard hardening. Can add via next.config.js headers array. |
| Dynamically import MapLibre with next/dynamic | 7.9 | Wrap MapView with ssr: false. Reduces map page JS. |
| Create error.tsx global error boundary | 3.9 | Styled error page matching archive aesthetic. |
| Create loading.tsx for slow routes | 3.10 | At minimum for /map and /incident/[slug]. |
| Add homepage metadata + canonical | 4.4 | Page-level metadata export with canonical URL. |
| Trim map page data payload (420 KB) | 7.2 | MapView only needs id, title, lat, lon, status. Remove summaries/excerpts from getMapIncidents(). |
| Remove dead preconnect hints | 7.8 | fonts.googleapis.com links are unnecessary with next/font. |
| Configure ESLint | 2.4 | No .eslintrc found. Good hygiene for ongoing development. |
| Improve geocoding coverage to 60%+ | 1.8 | Currently at 58.4%. 8 more incidents need lat/lon to cross threshold. |
| Fix sitemap incident count (396 vs 497) | 4.2 | Supabase max_rows project-level config may need adjustment. |
| Optimize getFeatured() cascading queries | 7.16 | 3 sequential Supabase queries could be 1 with SQL CASE/COALESCE. |
| Confirm ask_log public read is intentional | 6.7 | User queries/answers are world-readable via RLS policy. |
| Add explicit og:title/description to /media, /about, /map | 4.11 | Currently inherit from layout. Works but not optimal for social shares. |
| Add loading="lazy" to remaining img tags | 7.6 | page.tsx, incident page, MapPanel missing it. |

---

## Recommended Fix Order

### Before Launch (do these now)

1. **Scrub secrets from .env.example** -- Replace real keys with placeholder values (`your-supabase-url-here`, `your-api-key-here`). Do this FIRST.
2. **Add web/.gitignore** -- Cover `.env`, `.env.local`, `.env*.local`, `.next/`, `node_modules/`.
3. **Rotate all exposed API keys** -- Supabase anon + service role, Anthropic, Voyage. Update .env.local and Vercel environment variables with new keys.
4. **Add not-found.tsx** -- Styled 404 page with TopBar, declassified aesthetic, link back to homepage.
5. **Add favicon** -- Even a simple SVG icon.tsx in app/.
6. **Add rate limiting to /api/ask** -- Simple in-memory IP-based throttle (e.g., 10 requests/minute per IP). Can use a Map with TTL cleanup.
7. **Server-side paginate homepage** -- Change getAllIncidents() to `.limit(30)` with cursor/offset param. Reduces HTML from 568 KB to ~50 KB.

### After Launch (prioritized improvements)

8. Switch `<img>` to `next/image` + add images.remotePatterns.
9. Add security headers to next.config.js.
10. Dynamic import MapLibre with next/dynamic({ ssr: false }).
11. Create error.tsx and loading.tsx.
12. Add canonical URLs to homepage and remaining pages.
13. Trim map page data payload.
14. Remove dead preconnect hints.
15. Configure ESLint.
