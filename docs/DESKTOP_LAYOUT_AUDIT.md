## Ask page integration follow-up

Ask now uses the shared site-shell, page padding, normal document scrolling, and standard footer flow. Removed its separate 1080px cap and viewport-locked frame. Kept the page heading visible during conversations, aligned question/answer sections with the page, and placed the labeled composer inline below the content. Suggested questions use a responsive two-column grid. Answer prose remains readable at a bounded measure.

Validated at 390, 1024, and 1920px: aligned header/content gutters, no overflow. Visually reviewed 1440px screenshot. A locally intercepted API response verified first-question and follow-up rendering without calling the live answer service. TypeScript and diff whitespace checks passed.

## Shared layout consistency follow-up

Audited all page templates after the header/footer enlargement. Shared navigation and footer were already 18px on desktop; differences came from content wrappers, title sizes, top spacing, and fixed header spacer heights.

- Replaced the fixed header plus guessed spacer with an in-flow sticky header, including the legacy TopBar wrapper. Header height now follows its content and banner naturally.
- Standardized interior desktop page titles to 2.25rem (40.5px). The archive hero retains its larger headline.
- Aligned source, incident, and About outer containers with the shared desktop gutters. Long-form text remains bounded to 760px within the outer canvas.
- Normalized desktop top spacing on Collections, About, incident detail, and Ask. Increased undersized Ask labels, input, and question text.
- Browser audit: 15 routes at 390, 1024, and 1920px (45 checks), with one shared header/footer, expected desktop font sizes, no horizontal overflow, no heading overlap, and Ask/Map footers within the viewport. Media redirects and invalid legacy incident route also retain shared chrome. Sticky header remains at viewport top after scroll.
- TypeScript check and diff whitespace check passed. Collections desktop screenshot visually reviewed.

# Desktop layout audit

## Latest follow-up: desktop readability

At 1024px and above, the root type scale increases from 16px to 18px, consistently enlarging rem-based text, controls and their spacing. Fixed-size case summaries, excerpts and row titles now use 18px desktop text; the intro uses 20.25px. Incident dates/agencies use the darker existing secondary-ink color. Metadata tracks increase from 310px to 350px to accommodate larger labels. Footer and long-form fixed-size text receive matching desktop sizing. Mobile typography is unchanged.

Home passed overflow checks at 390, 1024, 1280, 1440 and 1920px; the 390px image is pixel-identical to the previous pass. Ten additional routes passed overflow checks at 1024 and 1920px, including Ask/Map with their footers inside the viewport. [Desktop text preview](desktop-layout/readability/preview.png).

## Latest follow-up: fluid desktop shell

The TrailVerse screenshot comparison identified the remaining outer-margin issue: the shared shell stopped at 1440px, producing 240px margins at a 1920px viewport. The cap is now removed for desktop shells. Gutters are `clamp(24px, 3.2vw, 64px)`; at 1920px the shared content width is 1797px and each gutter is 61px. At 2560px it grows to 2432px with 64px gutters. Header, banner, content and footer share the same alignment. Document/answer/prose measures remain bounded independently. No content or brand changes were made.

Home was checked at 390, 768, 1024, 1280, 1440, 1728, 1920 and 2560px; no horizontal overflow. The 390px homepage is pixel-identical to the preceding hierarchy pass. Incidents, Collections, Media, Audio, Sources, Releases and Ask also passed a 1920px overflow check. [Current screenshot](desktop-layout/fluid-shell/home-1920.png), [ultrawide screenshot](desktop-layout/fluid-shell/home-2560.png). Earlier width-cap descriptions below are historical.

Latest homepage composition and validation: [Homepage hierarchy audit](HOMEPAGE_HIERARCHY_AUDIT.md). Earlier homepage observations below are historical.

## Follow-up: stacked archive introduction and featured case

The introduction and text-only featured case retain the mobile reading order at every width. Desktop headline/featured surfaces can grow to 1240px; introduction prose uses 80ch and summary/excerpt prose uses 90ch. This removes the old 608/640px caps without placing text beside the headline or excerpt beside the summary. Latest releases and shared navigation are unchanged. All seven requested viewport widths pass the horizontal overflow check; 390px and 768px screenshots are pixel-identical to the pre-change baseline. [Current desktop preview](desktop-layout/archive-composition/preview-1920.png) and [full-page captures](desktop-layout/archive-composition/) supersede the earlier archive composition.

## Follow-up: consistent header/footer on every page

The subsequent request to keep every page's header/footer the same is implemented through `SiteFrame` in the root layout. Individual pages no longer render their own navigation/footer. Ask, Map, error and 404 states now inherit the same shared components. Homepage release-banner content remains server-rendered and contextual to the homepage.

The frame gives ordinary pages a minimum viewport height, and divides the available viewport between header, application content and footer on Ask/Map. It measures naturally through flex layout, including the taller wrapped mobile footer; no fixed footer-height subtraction is used. The footer now wraps on narrow screens. Sources controls can shrink, and long source/release titles wrap without truncation, resolving the mobile overflow documented in the original audit below.

Follow-up verification: 15 routes at 390, 768, 1024 and 1920px (60 route/viewport combinations), including collection detail, incident detail and 404. Every final capture has exactly one site header and one footer, identical footer links, and no horizontal document overflow. Ask/Map footer stays inside the viewport. [Follow-up measurements](desktop-layout/shared-frame/metrics.json) and [screenshots](desktop-layout/shared-frame/) supersede earlier screenshots for header/footer placement. Error UI inherits the frame by construction; a runtime fault was not artificially induced. Typecheck and production build were rerun after the changes.

The original audit below describes the earlier desktop-width work and preserves its before/after evidence.

## Root cause (recorded before implementation)

The working tree already contains a shared `.site-shell`; it applies `max-w-content` (1120px including 48px desktop padding). RootLayout itself imposes no width. Header, banner, footer and most index pages correctly share the shell, but its reading-oriented cap leaves 800px outside the shell at 1920px.

Ask independently uses `max-w-prose` (640px including padding) for both conversation and composer. Source detail and About use the same narrow article wrapper. IncidentRow fixes dates to `w-28` (112px) and reserves an unbounded nonshrinking metadata group, squeezing titles and long date descriptions. Media/Audio stop at three columns and Collections at two. Map already fills the viewport and should retain that application layout.

Existing uncommitted design changes are preserved. This audit compares against the working tree at task start, not HEAD. Scope is layout only; no content, data, request, retrieval, SEO or environment changes.

## Shared layout changes

Desktop-only tokens in `web/src/app/globals.css` separate the 1440px page canvas, 1240px document/content region, 760px reading measure, and 1080px Ask surface. Gutters use `clamp(20px, 4vw, 64px)` within a centered, capped width. The existing 16px mobile and 24px tablet padding is retained. Header, banner, index pages and footer inherit the shared shell automatically; no root-layout or navigation markup change was necessary.

Media and collection grid rules are centralized alongside the width primitives. Tailwind adds one named `wide` breakpoint at 1440px. Existing fonts, colors, rules, accents, heading sizes, card styling and vertical spacing remain unchanged.

| Viewport | Page content width | Ask surface | Media/Audio columns | Collections columns |
| --- | ---: | ---: | ---: | ---: |
| 390 | 358 | 358 | 1 | 1 |
| 768 | 720 | 592 | 2 | 2 |
| 1024 | 942 | 942 | 3 | 2 |
| 1280 | 1178 | 1080 | 3 | 2 |
| 1440 | 1325 | 1080 | 4 | 3 |
| 1728 | 1440 | 1080 | 4 | 3 |
| 1920 | 1440 | 1080 | 4 | 3 |

Widths are rounded interior widths, excluding mobile/tablet padding. The primary changes start at 1024px; the denser grids start at 1440px. Existing 640px media and 768px collection two-column transitions are preserved.

## Page-specific changes and observations

- **Home:** hero copy retains its original narrow measure. The list now spans the desktop shell. Featured cases with media use a capped 1240px two-column region; the current text-only featured case remains prose-width. No stats, copy, sorting or data changes.
- **Incidents and Latest releases:** desktop rows use a flexible title, a date track of at least 160px (19% of available row width), and compact release/agency/status tracks. At 1440px the date track measures approximately 252px, versus 112px before. Long date descriptions wrap in several readable lines, without truncating titles. Desktop gaps are 24px; mobile rows are unchanged.
- **Ask:** conversation and composer share a 1080px cap (previously 640px including padding). Suggested questions fill that surface. Answer prose is capped at 760px. Typing a multiline question at 390px and 1920px keeps the growing composer visible. No question was submitted; retrieval, prompts, citations and streaming logic are untouched.
- **Audio and Media:** shared 1/2/3/4-column layout; desktop cards remain practical sizes (313px at 1440px, 342px at 1920px). All three Media tabs use the same grid; Videos and Documents were also checked at 1920px. Existing players and status text are unchanged.
- **Collections:** two readable columns through ordinary desktop, three at 1440px and above; no typography reduction.
- **Releases, release detail, Sources:** existing shared shell provides wider lists, filters and metadata. No page-specific width patches were needed.
- **Source detail:** 1240px document surface, 760px narrative, three-column metadata and two-column related cases/sightings on desktop. The representative record has a long title, substantial prose, and both kinds of related records.
- **About:** 760px reading surface on desktop; prose stays intentionally narrower than archive lists.
- **Map:** already uses the viewport beneath the header. Kept its map canvas, controls, legend and behavior intact; header gains the shared shell alignment.
- **Collection and incident detail audit:** collection detail already inherits the shared shell with narrow narrative children. Incident detail remains a deliberate long-form reading page; no global prose token was enlarged.

The 1920px side-by-side comparisons are available for [Home](desktop-layout/home-comparison.jpg), [Ask](desktop-layout/ask-comparison.jpg), [Collections](desktop-layout/collections-comparison.jpg), [Audio](desktop-layout/audio-comparison.jpg), and [Source detail](desktop-layout/source-DOW-UAP-D102-comparison.jpg). Comparison images show the first 2150px where a page is longer; full-page originals are linked below.

## Mobile regression gate

All 12 routes were captured before and after at 390×844. Ten are pixel-identical: Home, Incidents, Ask, Collections, Audio, Releases, Release 06, Sources, Source detail, and About. This includes navigation, lists/cards, source metadata, footer and the empty Ask composer. Media differs only within image regions and Map within the dynamically loaded map surface; their screenshot dimensions are unchanged.

Two pre-existing mobile issues remain deliberately outside this desktop-only change:

- The inline footer extends to roughly 392px at a 390px viewport (about 2px of overflow).
- The Sources filter controls expand the full document to 652px at 390px. Its complete before/after screenshots are pixel-identical, confirming this was not introduced here.

All 72 tablet/desktop route captures (768px and above) returned HTTP 200 with no document-level horizontal overflow. All 12 mobile captures also returned HTTP 200. See [recorded geometry](desktop-layout/metrics.json).

## Screenshot matrix

Local Chromium, light theme, real existing application data, full-page screenshots. No mocked content or production writes. Baselines were captured from the original working tree at 390px and 1920px. After captures cover every requested route at every requested viewport (84 captures). Next.js development indicators remain visible. External images and map tiles can differ with loading/network timing.

| Route | 390×844 | 768×1024 | 1024×768 | 1280×800 | 1440×900 | 1728×1117 | 1920×1080 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| / | [PNG](desktop-layout/after/home-390.png) | [PNG](desktop-layout/after/home-768.png) | [PNG](desktop-layout/after/home-1024.png) | [PNG](desktop-layout/after/home-1280.png) | [PNG](desktop-layout/after/home-1440.png) | [PNG](desktop-layout/after/home-1728.png) | [PNG](desktop-layout/after/home-1920.png) |
| /incidents | [PNG](desktop-layout/after/incidents-390.png) | [PNG](desktop-layout/after/incidents-768.png) | [PNG](desktop-layout/after/incidents-1024.png) | [PNG](desktop-layout/after/incidents-1280.png) | [PNG](desktop-layout/after/incidents-1440.png) | [PNG](desktop-layout/after/incidents-1728.png) | [PNG](desktop-layout/after/incidents-1920.png) |
| /ask | [PNG](desktop-layout/after/ask-390.png) | [PNG](desktop-layout/after/ask-768.png) | [PNG](desktop-layout/after/ask-1024.png) | [PNG](desktop-layout/after/ask-1280.png) | [PNG](desktop-layout/after/ask-1440.png) | [PNG](desktop-layout/after/ask-1728.png) | [PNG](desktop-layout/after/ask-1920.png) |
| /collections | [PNG](desktop-layout/after/collections-390.png) | [PNG](desktop-layout/after/collections-768.png) | [PNG](desktop-layout/after/collections-1024.png) | [PNG](desktop-layout/after/collections-1280.png) | [PNG](desktop-layout/after/collections-1440.png) | [PNG](desktop-layout/after/collections-1728.png) | [PNG](desktop-layout/after/collections-1920.png) |
| /media | [PNG](desktop-layout/after/media-390.png) | [PNG](desktop-layout/after/media-768.png) | [PNG](desktop-layout/after/media-1024.png) | [PNG](desktop-layout/after/media-1280.png) | [PNG](desktop-layout/after/media-1440.png) | [PNG](desktop-layout/after/media-1728.png) | [PNG](desktop-layout/after/media-1920.png) |
| /audio | [PNG](desktop-layout/after/audio-390.png) | [PNG](desktop-layout/after/audio-768.png) | [PNG](desktop-layout/after/audio-1024.png) | [PNG](desktop-layout/after/audio-1280.png) | [PNG](desktop-layout/after/audio-1440.png) | [PNG](desktop-layout/after/audio-1728.png) | [PNG](desktop-layout/after/audio-1920.png) |
| /releases | [PNG](desktop-layout/after/releases-390.png) | [PNG](desktop-layout/after/releases-768.png) | [PNG](desktop-layout/after/releases-1024.png) | [PNG](desktop-layout/after/releases-1280.png) | [PNG](desktop-layout/after/releases-1440.png) | [PNG](desktop-layout/after/releases-1728.png) | [PNG](desktop-layout/after/releases-1920.png) |
| /releases/06 | [PNG](desktop-layout/after/releases-06-390.png) | [PNG](desktop-layout/after/releases-06-768.png) | [PNG](desktop-layout/after/releases-06-1024.png) | [PNG](desktop-layout/after/releases-06-1280.png) | [PNG](desktop-layout/after/releases-06-1440.png) | [PNG](desktop-layout/after/releases-06-1728.png) | [PNG](desktop-layout/after/releases-06-1920.png) |
| /sources | [PNG](desktop-layout/after/sources-390.png) | [PNG](desktop-layout/after/sources-768.png) | [PNG](desktop-layout/after/sources-1024.png) | [PNG](desktop-layout/after/sources-1280.png) | [PNG](desktop-layout/after/sources-1440.png) | [PNG](desktop-layout/after/sources-1728.png) | [PNG](desktop-layout/after/sources-1920.png) |
| /source/DOW-UAP-D102 | [PNG](desktop-layout/after/source-DOW-UAP-D102-390.png) | [PNG](desktop-layout/after/source-DOW-UAP-D102-768.png) | [PNG](desktop-layout/after/source-DOW-UAP-D102-1024.png) | [PNG](desktop-layout/after/source-DOW-UAP-D102-1280.png) | [PNG](desktop-layout/after/source-DOW-UAP-D102-1440.png) | [PNG](desktop-layout/after/source-DOW-UAP-D102-1728.png) | [PNG](desktop-layout/after/source-DOW-UAP-D102-1920.png) |
| /about | [PNG](desktop-layout/after/about-390.png) | [PNG](desktop-layout/after/about-768.png) | [PNG](desktop-layout/after/about-1024.png) | [PNG](desktop-layout/after/about-1280.png) | [PNG](desktop-layout/after/about-1440.png) | [PNG](desktop-layout/after/about-1728.png) | [PNG](desktop-layout/after/about-1920.png) |
| /map | [PNG](desktop-layout/after/map-390.png) | [PNG](desktop-layout/after/map-768.png) | [PNG](desktop-layout/after/map-1024.png) | [PNG](desktop-layout/after/map-1280.png) | [PNG](desktop-layout/after/map-1440.png) | [PNG](desktop-layout/after/map-1728.png) | [PNG](desktop-layout/after/map-1920.png) |

[Mobile baseline folder](desktop-layout/before/) also contains all 1920px baselines. Review sheets: [390px](desktop-layout/review-390.jpg), [768px](desktop-layout/review-768.jpg), [1024px](desktop-layout/review-1024.jpg), [1280px](desktop-layout/review-1280.jpg), [1440px](desktop-layout/review-1440.jpg), [1728px](desktop-layout/review-1728.jpg), [1920px](desktop-layout/review-1920.jpg).

## Local validation and remaining limitations

- `npx tsc --noEmit` from `web/`: PASS.
- `npm run build` from `web/`: PASS (final verification rerun after the grid-gap adjustment).
- `.venv/bin/python -m unittest discover -s pipeline/tests -q`: 77 passed.
- `.venv/bin/python -m unittest discover -s pipeline/tests/linker -q`: 11 passed.
- `.venv/bin/python -m pipeline.tests.test_validation`: PASS, all 5 expected keep/drop outcomes matched.
- No frontend test script exists in `web/package.json`. Pytest is not installed; the existing unittest suites ran without installing dependencies. The live Haiku extraction script was not run because this task excludes model/extraction operations.
- `git diff --check`: PASS.

Initial typecheck/build was blocked by an ignored stale `web/src/app/map/MapClient.backup.tsx` importing an already-deleted component. The backup was preserved at `.cache/desktop-layout-backups/MapClient.backup.tsx`, outside TypeScript's source tree. No runtime map code was changed for this task.

A build temporarily invalidated the running dev server cache. The server was restarted and all affected failed captures were replaced with successful HTTP 200 captures. The final build ran after stopping the development server.

Pre-existing console warnings include duplicate/null keys on Sources and remote media/tile loading errors. The build reports the existing deprecated `experimental.typedRoutes` configuration and edge-runtime static-generation warning. These are not layout regressions. Screenshot review is Chromium/light-theme only; no cross-browser claim is made. Live Ask answers were not invoked; the answer-width constraint was reviewed in markup/CSS.

## Verdict

**DESKTOP_LAYOUT_READY** — desktop composition and mobile regression gate pass. The existing mobile footer/Sources overflow and unrelated console warnings are recorded above. Local only; no deployment, production writes, environment changes, or changes to data/RAG/SEO content.
