# UFODOSSIER Design Tokens

Reference doc for the declassified-archive visual system. Sources: `demo.html`, `web/src/app/globals.css`, `web/tailwind.config.js`.

---

## Color tokens

| Token | Hex | CSS var | Intended use | When NOT to use |
|-------|-----|---------|-------------|----------------|
| `bg` | `#0a0a0a` | `--bg` | Page background, stat cells, input fields | Never use pure `#000` |
| `bg-elev` | `#111110` | `--bg-elev` | Elevated surfaces (ask CTA section) | Not for cards — use `bg-paper` |
| `bg-paper` | `#15140f` | `--bg-paper` | Cards, featured case, response panels, doc mockups | Not for full-page backgrounds |
| `ink` | `#e8e6e0` | `--ink` | Primary text, headings, table data, excerpt text | Not for labels or metadata |
| `ink-dim` | `#a8a59c` | `--ink-dim` | Secondary text, editorial prose, nav links, doc mockup body | Not for faint/disabled states |
| `ink-faint` | `#6b685f` | `--ink-faint` | Tertiary text, labels, section headers, filter counts, metadata | Not for body copy |
| `amber` | `#ff9933` | `--amber` | Accent: active nav, hover states, excerpt borders, blinking dot, section labels, tag highlights | Not for backgrounds (use `amber/5` or `amber/10` for subtle bg) |
| `amber-dim` | `#b36b1f` | `--amber-dim` | Date column in incident table | Rarely used elsewhere |
| `stamp` | `#c8302a` | `--stamp` | Stamp borders and stamp text ("DECLASSIFIED", "UNCLASS//FOUO") | Never for non-stamp elements |
| `rule` | `#2a2925` | `--rule` | Borders, dividers, section separators, table row borders | Not for strong separators |
| `rule-strong` | `#3d3b35` | `--rule-strong` | Emphasized borders: table header bottom, input borders, card borders | Not for subtle dividers |
| `redaction` | `#000` | `--redaction` | Redaction bars (set as both `background` and `color` on `ink` text) | Only for redacted content |

### Tag-specific colors (not tokenized as CSS vars)

| Color | Hex | Used for |
|-------|-----|----------|
| Unresolved | `#ff5544` | Unresolved status tag, unresolved map dots |
| Identified | `#5588cc` | Identified status tag, identified map dots |
| Radar | `#66cc88` | Radar sensor tag |
| Infrared | `#d4a868` | Infrared sensor tag |
| Eyewitness | `#ff9933` (amber) | Eyewitness sensor tag |
| Photo/video | `ink-dim` | Photo and video sensor tags |
| Insufficient | `ink-faint` | Insufficient data status tag |

---

## Typography

### Special Elite (`--font-type` / `font-type` in Tailwind)

Typewriter face. Used for display/hero text and stat values. Conveys the declassified-document feel.

| Context | Size | Weight | Other |
|---------|------|--------|-------|
| Hero title (`h1`) | `clamp(48px, 8vw, 96px)` | 400 | `uppercase`, `leading-[0.95]`, `tracking-tight` (`-0.02em`) |
| Stat values | `38px` (demo) / `text-4xl` (Tailwind) | 400 | `leading-none`, `tracking-tight` |
| Featured case `h2` | `28px` (demo) / `text-3xl` (Tailwind) | 400 | `leading-[1.2]` |
| Ask CTA heading | `36px` (demo) / `text-4xl` (Tailwind) | 400 | |
| About section headings | `text-2xl` | 400 | `mt-8` above |
| Incident page title | `text-4xl md:text-5xl` | 400 | `leading-tight` |

### JetBrains Mono (`--font-mono` / `font-mono` in Tailwind)

Technical monospace. Default body font. Used for all UI text, labels, navigation, metadata, tables, inputs, tags.

| Context | Size | Weight | Other |
|---------|------|--------|-------|
| Body default | `14px` | 400 | `leading-[1.6]` |
| Top bar / nav | `11px` | 400 | `uppercase`, `tracking-[0.1em]` |
| Section headers (sidebar, block) | `11px` | 400 | `uppercase`, `tracking-archive` (`0.15em`) |
| Stat labels | `10px` | 400 | `uppercase`, `tracking-archive` |
| Sidebar filter items | `12px` | 400 | |
| Incident table body | `12px` | 400 | |
| Incident table headers | `10px` | 400 | `uppercase`, `tracking-archive` |
| Tags | `9px` | 400 | `uppercase`, `tracking-wide` (`0.1em`) |
| Stamps | `12px`-`14px` | 700 | `uppercase`, `tracking-archive` |
| Verbatim excerpt label | `10px` | 400 | `tracking-wide` |
| Verbatim excerpt body | `12px`-`13px` | 400 | `leading-[1.8]` |
| Input field | `14px` | 400 | |
| Document mockup | `11px` | 400 | `leading-[1.8]` |

### Newsreader (`--font-serif` / `font-serif` in Tailwind)

Serif editorial face. Used for prose — summaries, the about page body, hero subtitle, ask CTA description.

| Context | Size | Weight | Other |
|---------|------|--------|-------|
| Hero subtitle | `22px` | 400 | `italic`, `leading-[1.5]` |
| Featured case body | `16px` | 400 | `leading-[1.7]` |
| About page body | `17px` | 400 | `leading-[1.7]`, in `.prose` wrapper |
| Ask page intro | `text-lg` (~18px) | 400 | `italic` |
| RAG response text | `17px` | 400 | `leading-[1.7]`, `whitespace-pre-wrap` |
| Incident summary | `text-lg` | 400 | `leading-relaxed` |
| Methodology note | `text-sm` | 400 | `leading-relaxed`, in `ink-dim` |

---

## Spacing and rhythm

### Max width

All main containers: `max-width: 1280px` with `margin: 0 auto` and `padding: 0 24px` (`px-6`).

About page narrower: `max-width: 760px`.

Ask page narrower: `max-width: 860px`.

### Stats grid

The stats strip uses a 1px-gap trick: the parent grid has `background: var(--rule)` and `gap: 1px`. Each stat cell has `background: var(--bg)`, so the rule color shows through the 1px gaps as dividers. Responsive: 4 columns on desktop (`grid-cols-4`), 2 columns on mobile (`grid-cols-2`).

### Main layout

Desktop: `grid-template-columns: 240px 1fr` with `gap: 48px` (`gap-12`). Mobile: single column.

### Sidebar sections

Each sidebar section has:
- `h3`: `margin-top: 24px` (`mt-6`), `margin-bottom: 12px` (`mb-3`), `padding-bottom: 8px` (`pb-2`), `border-bottom: 1px solid var(--rule)`
- First `h3`: `margin-top: 0`
- Filter items: `padding: 4px 0` (`py-1`)

### Content blocks

- `margin-bottom: 48px` (`mb-12`) between blocks
- Block header: `border-bottom: 1px solid var(--rule)`, `padding-bottom: 12px` (`pb-3`), `margin-bottom: 20px` (`mb-5`)

### Section borders

Horizontal `border-rule` dividers between major sections (hero, stats, main, ask CTA, footer). The `border-y` pattern on the ask CTA creates both top and bottom borders.

---

## Component patterns

### Stamp

```html
<span class="stamp absolute -top-5 -right-12 text-[14px] rotate-[-12deg] opacity-90">
  DECLASSIFIED
</span>
```

CSS class (from `globals.css`):
```css
.stamp {
  border: 3px solid var(--stamp);
  color: var(--stamp);
  font-family: var(--font-mono);
  font-weight: 700;
  letter-spacing: 0.15em;
  padding: 6px 14px;
  text-transform: uppercase;
  display: inline-block;
}
```

Variations: hero stamp (14px, rotate -12deg, opacity 0.85-0.90), document stamp (12px, rotate +8deg, opacity 0.70, 2px border instead of 3px).

### Redaction bar

```html
<span class="redaction">secret text here</span>
```

```css
.redaction {
  background: var(--ink);
  color: var(--ink);
  user-select: none;
}
```

The `demo.html` version uses class `.red` with `background: var(--ink-dim); color: var(--ink-dim)` for the document mockup. Both make text invisible by matching background to foreground.

### Tag pill

```html
<span class="tag text-[#ff5544]">unresolved</span>
```

```css
.tag {
  display: inline-block;
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  padding: 3px 8px;
  border: 1px solid currentColor;
}
```

Color is set via `currentColor` — the text color also becomes the border color.

### Blink cursor

```html
<span class="blink" aria-hidden></span>
```

```css
.blink {
  display: inline-block;
  width: 8px; height: 8px;
  background: var(--amber);
  animation: blink 1.4s step-end infinite;
}
@keyframes blink { 50% { opacity: 0; } }
```

### Verbatim excerpt block

```html
<div class="border-l-2 border-amber pl-4 py-2 my-4 font-mono text-xs bg-amber/5">
  <div class="text-amber text-[10px] tracking-wide mb-1">VERBATIM EXCERPT //</div>
  <div class="text-ink">"...the object exhibited no observable thermal exhaust signature..."</div>
</div>
```

The `demo.html` version uses `feature-quote` class with explicit CSS. Same visual result.

### Document mockup

```html
<div class="bg-bg border border-rule p-6 font-mono text-[11px] text-ink-dim leading-relaxed relative min-h-[280px]">
  <span class="absolute top-2 right-3 text-[9px] text-ink-faint tracking-wide">
    TYPED REPORT // PAGE 1 of N
  </span>
  <span class="stamp absolute top-6 right-6 rotate-[8deg] text-[12px] opacity-70">
    UNCLASS//FOUO
  </span>
  <p class="mt-8">DEPT OF WAR // INTEL ASSESSMENT</p>
  <p>SUBJ: UAP CONTACT</p>
  <!-- body with <span class="redaction"> bars -->
</div>
```

### Featured case card

```html
<article class="bg-bg-paper border border-rule-strong p-8 mb-12 relative">
  <span class="absolute -top-px left-6 bg-bg px-3 -translate-y-1/2 font-mono text-[10px] tracking-[0.2em] text-amber">
    FEATURED CASE
  </span>
  <div class="grid grid-cols-1 md:grid-cols-2 gap-8">
    <!-- left: metadata, title, summary, excerpt, link -->
    <!-- right: document mockup -->
  </div>
</article>
```

The "FEATURED CASE" label floats on the top border using `absolute -top-px` + `-translate-y-1/2` with a `bg-bg` background to cut through the border.

---

## Effects

### Scan-line overlay

Applied to `body::before`. Fixed-position, covers viewport, `z-index: 100`, `pointer-events: none`, `mix-blend-mode: overlay`.

```css
background-image: repeating-linear-gradient(
  0deg,
  rgba(255,255,255,0.015) 0px,
  rgba(255,255,255,0.015) 1px,
  transparent 1px,
  transparent 3px
);
```

Creates subtle 1px horizontal lines every 3px. Applied globally to every page.

### Vignette

Applied to `body::after`. Fixed-position, `z-index: 99`, `pointer-events: none`.

```css
background: radial-gradient(ellipse at center, transparent 0%, rgba(0,0,0,0.4) 100%);
```

Darkens edges of viewport. Applied globally.

### Pulsing map dots

```css
.map-dot {
  width: 6px; height: 6px;
  background: var(--amber);
  border-radius: 50%;
  box-shadow: 0 0 8px var(--amber);
  animation: pulse 3s ease-in-out infinite;
}
@keyframes pulse-dot {
  0%, 100% { transform: translate(-50%, -50%) scale(1); opacity: 1; }
  50% { transform: translate(-50%, -50%) scale(1.4); opacity: 0.7; }
}
```

Dot colors vary: amber (default), `#ff5544` (unresolved), `#5588cc` at 50% opacity (identified).

### Text selection

```css
::selection {
  background: var(--amber);
  color: var(--bg);
}
```

---

## Don'ts

- No emoji anywhere in the UI
- No rounded corners on stamps (stamps use sharp corners, not `border-radius`)
- No gradient backgrounds (the only gradients are the vignette overlay and the scan-line repeating-linear-gradient, both on `body` pseudo-elements)
- No purple, no neon, no synthwave colors
- No glow effects (the `box-shadow` on map dots is the only glow, and it's subtle amber)
- No "spooky alien" imagery — no aliens, no flying saucers, no green-men illustrations
- No Wingdings-as-alien-language
- No Lottie or complex JS animations
- No bright or saturated full-background colors
- No light mode (the dark archival palette is the entire identity)
