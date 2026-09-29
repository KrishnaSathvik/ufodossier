# Homepage editorial hierarchy

Scope: homepage only, local only. Current composition supersedes the earlier stacked-desktop homepage screenshots.

## Changes

- Desktop hero keeps the existing headline and description together on the left. A restrained archive index on the right uses `getCorpusStats()` for official files, checked passages, sightings, and releases. Latest release comes from the same `listReleases()` catalog used by the update strip. No counts or release numbers are hardcoded.
- Featured case has a desktop-only paper tint, thin border, top metadata/status rail and bottom action rail. Existing title, summary, excerpt, date, agency and media remain intact. Typography and color tokens are unchanged.
- Homepage renders the first 10 results from the unchanged query/order with the existing `IncidentRow`. Shared `IncidentList`, `/incidents`, pagination, data and retrieval are untouched. Empty-state text is retained.
- Desktop column headings align with the existing date/title/release/agency/status grid. Hover/focus adds a subtle title underline; existing paper tint and accent behavior remain.
- Actions lead to the full archive and the dynamic latest release. The archive CTA says “case files,” matching the destination's canonical wording; the index says “checked passages,” matching the introduction.
- Global shell, header/footer, routes, SEO metadata, models and data pipelines are unchanged.

## Verification

The displayed 10 records match the baseline's first 10 hrefs and text exactly, in the same order. Browser navigation confirmed `/incidents` still lists 583 published case files with pagination, and the release CTA opens `/releases/06` using current catalog data.

At 390px, the first 1200px of the homepage (hero, featured case and beginning of the list) is pixel-identical to baseline. The index and new file-panel styling are desktop-only. Mobile changes below that point are the explicitly requested 10-row preview and browse actions. No horizontal overflow at any tested width.

| Viewport | Before | After | Result |
| --- | --- | --- | --- |
| 390×844 | [PNG](desktop-layout/homepage-hierarchy/before-390.png) | [PNG](desktop-layout/homepage-hierarchy/after-390.png) | Preserved stacked layout, 10 rows |
| 1280×800 | [PNG](desktop-layout/homepage-hierarchy/before-1280.png) | [PNG](desktop-layout/homepage-hierarchy/after-1280.png) | Pass |
| 1440×900 | [PNG](desktop-layout/homepage-hierarchy/before-1440.png) | [PNG](desktop-layout/homepage-hierarchy/after-1440.png) | Pass |
| 1728×1117 | [PNG](desktop-layout/homepage-hierarchy/before-1728.png) | [PNG](desktop-layout/homepage-hierarchy/after-1728.png) | Pass |
| 1920×1080 | [PNG](desktop-layout/homepage-hierarchy/before-1920.png) | [PNG](desktop-layout/homepage-hierarchy/after-1920.png) | Pass |

Screenshots use Chromium/light theme and contain the local Next.js development indicator. The media-bearing featured-case branch is preserved but the current live featured record has no media.

Validation: `npx tsc --noEmit` — PASS; `npm run build` from `web/` — PASS; `git diff --check` — PASS. Existing typedRoutes and edge-runtime build warnings are unrelated to this pass.

Verdict: **HOMEPAGE_HIERARCHY_READY**. No deployment or production writes.
