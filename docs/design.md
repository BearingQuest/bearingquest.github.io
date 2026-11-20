# Bearing Quest site: design

How bearingquest.com uses the Bearing Quest design system. UI work in this repo follows this file (baseline UI-01). Written 14 Nov 2026 by Claude in Dusten's Claude project; approved by Dusten through the pull request that adds it.

## Source

- Design system: "Bearing Quest" design system artifact in Dusten's Claude account (private), version of 6 Nov 2026.
- `docs/design/tokens.json` is a byte-for-byte snapshot of that system's `tokens.json` (SHA-256 `18086c9cd35e6abf6429ff76b84cc28547a897b23d84176629651d06a4a8890c`, taken 14 Nov 2026). Don't edit it here; when the design system changes, replace the snapshot in its own pull request and record the new hash.
- `docs/design/reference/bundle.css` is the design system's component stylesheet, for reference only. The site doesn't load it.
- `docs/design/logos/` holds the four logo SVGs the site uses, identical to `assets/img/`. A test keeps the two copies equal.
- `docs/design/screens/` holds the accepted screens: home, About, resume and 404 at 1280 px in light and dark, and home at 390 px in both themes, rendered from d0853e5 (PR #16), which Dusten reviewed live on 14 Nov 2026.
- The blog index and the first post at 1280 px in both themes (`blog-desktop-*` and `blog-post-desktop-*`) are added with the blog (R17-R21). `scripts/blog-screens.py` takes them; Dusten runs it in a plain Terminal because the agent sandbox can't start Chromium.
- The screens predate this pull request's card-edge change, so they show Bearing Register in `accent` and DossierNexus in `muted`; the next screens refresh updates them.

## The site's layer

Every other app in the family adds one accent and one motif to the shared base. This site is the family's home, so it doesn't.

- **Accent:** none of its own. The base `accent` (burnt orange) is the site's link and call-to-action color.
- **Motif:** the compass: the Bearing Quest lockup in the header, the compass mark on the 404 page and as the favicon.
- **Family identity:** the lockup in the header on every page (light and dark versions swapped by theme), and Cinzel only in the footer wordmark.
- **Project cards:** each card has a thin left edge in that project's own accent, so the family relationships show. The edge is decoration; the project name and label carry the meaning.

| Card | Edge token | Light | Dark | Source |
|---|---|---|---|---|
| Risk Trainer | `risk-accent` (site layer) | #006A7A | #4FD6E8 | Risk Trainer's Blueprint accent, kept by its light-path decision (29 Oct 2026) |
| Bearing Register | `primary` | #1B365D | #C9D3DF | The design system names `primary` as Bearing Register's default action color; `accent` is kept out of its data views |
| QuestVector | `qv-accent` | #1F68A8 | #7DB8F0 | QuestVector's Horizon blue (29 Oct 2026) |
| QuestCast | `accent` | #B4501F | #E8894F | CLI only, so no app accent of its own |
| DossierNexus | `dnx-accent` | #8A3B7A | #E3A1D6 | DossierNexus's Archive plum (6 Nov 2026) |

Status: Claude proposed this layer on 5 Nov 2026 and applied it to this file on 14 Nov 2026, when Dusten asked for the design pack. Dusten confirms or changes it in this file's pull request. Until that PR, the live site edges Bearing Register in `accent` and DossierNexus in `muted`; the PR moves them to `primary` and `dnx-accent`.

## Tokens on the site

`assets/css/site.css` writes its tokens by hand (no build step, decision of 5 Nov 2026; baseline UI-04 as amended 10 Nov 2026). A test checks every color token in both themes, in both the device-preference block and the explicit `data-theme` blocks, against these sources:

| CSS custom property | Source | Token |
|---|---|---|
| `--ground`, `--surface`, `--text`, `--heading`, `--muted`, `--accent`, `--control`, `--border`, `--focus`, `--error`, `--primary`, `--dnx-accent` | `docs/design/tokens.json` | same name |
| `--brand-accent` | `docs/design/tokens.json` | `brand-orange` |
| `--vector-accent` | `docs/design/tokens.json` | `qv-accent` |
| `--risk-accent` | `docs/design/site-layer.json` | `risk-accent` |

A new color token in `site.css` needs a row here and a source in one of those two files, or the test fails.

## Recorded departures from the design system

- **Focus ring:** 3px with a 2px offset (the design system says 2px). Thicker passes the same contrast rule and is easier to see on the dark theme.
- **Weights:** the site ships Inter 400 and 700, IBM Plex Mono 400 and 500, and Cinzel as a variable font. IBM Plex Mono rules ask for no weight above 500, so the browser never fakes a bold (8 Nov 2026); Inter rules at 650 render with the shipped 700.
- **Font files:** downloaded from the upstream releases (Inter v4.1, IBM Plex Mono 2.5.0 Latin1, Cinzel from google/fonts at 3dd7884), not the design system's copies (Dusten, 8 Nov 2026).

## Blog

- Post text column at most 70 characters wide.
- Figures span the full column width (`max-width: 100%`, `height: auto`), with a caption below in the muted colour at body size.
- The post title (h1) is `clamp(2rem, 1.4rem + 2.5vw, 2.75rem)` with line-height 1.1; a post h2 is `clamp(1.4rem, 1.15rem + 1vw, 1.75rem)` with 3rem above. Both rules sit under `.post`, so the home page's larger h1 is unchanged. Headings stay in `--heading`.
- The hero figure (class `post-hero`) shows as a banner strip: the image fills the column, `min(280px, 40vw)` tall, `object-fit: cover` and `object-position: center` so the compass stays in view. Its `width` and `height` attributes stay (R19); this is the one figure that doesn't use `height: auto`.
- The publication date sits under the title, in the muted colour.
- Orange (`--brand-accent`) is used only as decoration or for display text 24 px and up, as now.
- Figures are drawn on a white card with a border, so they read in both themes and need no dark versions.
- SVG images can't use the page's self-hosted fonts, so their text falls back to the system sans-serif; accepted.
- The blog templates reuse `assets/css/site.css` and `assets/js/theme.js`; no new colours.

## Rules for UI changes

- Use tokens, never raw hex, in rules outside the token blocks.
- Text 4.5:1 or better and focus rings and control edges 3:1 or better in both themes; the contrast test enforces it.
- Color is never the only signal: labels, words or icons carry meaning.
- No inline script, style block or style attribute (the CSP forbids them).
- New screens or a changed layout get new PNGs in `docs/design/screens/` in the same pull request.
