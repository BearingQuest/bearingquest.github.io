# Bearing Quest site: product requirements (v1.1)

Version 1.1, 19 Nov 2026; v1.1 adds the blog section (R17–R23) and edits R9, §3, §4, §8 and §9. Version 1.0, 14 Nov 2026. Replaces the design brief v0.1 (5 Nov 2026) kept in Dusten's Claude project. Written by Claude from the brief, the decisions in `docs/decisions.md` and the site as merged at d0853e5 (PR #16); approved by Dusten through the pull request that adds this file.

Requirement IDs are stable: a later change edits a requirement in place and adds a `docs/decisions.md` row; a removed requirement keeps its ID, marked withdrawn. Pull requests cite these IDs in the template's Requirements line. The v0.1 brief's IDs map as shown in the last column.

## 1. Purpose

A public showcase for the Bearing Quest project family at https://bearingquest.com: one card per project, an About page for the person behind the projects, a resume page, and links to the GitHub organization, the blog, LinkedIn and X. It supports Dusten's career record, instructor pivot and blog. Bearing Quest is a personal project family, never a company.

## 2. Requirements

EARS style: "The site shall …" for always-true rules, "When …, the site shall …" for event-driven ones.

### Hosting and publishing

| ID | Requirement | Was |
|---|---|---|
| R1 | The site shall be served over HTTPS only at bearingquest.com, with www.bearingquest.com redirecting to it, from GitHub Pages with Cloudflare DNS records set to DNS only. | S1 |
| R2 | The site shall publish only the paths listed in `site-files.txt`, deployed by `.github/workflows/pages.yml` from `main`; every other repo file shall return 404 on the site. | new (10 Nov) |
| R3 | When a page is requested at a path that doesn't exist, at any depth, the site shall return `404.html` with its styles and links working. | new (8 Nov) |

### Content

| ID | Requirement | Was |
|---|---|---|
| R4 | The home page shall show one card per Bearing Quest project, in the order of the approved content file, each with its name, a one-line description, a maturity label taken from Dusten's career record and a link to its repo; a project with no repo yet shall show no links. | S2 |
| R5 | When a project has a public live address, its card shall link to it as well as to the repo. | S3 |
| R6 | The About page shall describe Bearing Quest as a personal project family and Dusten as the person who specifies and directs the projects, with the implementation AI-generated under his review. | S4 |
| R7 | The resume page shall be HTML, shall take every claim, figure and date from the approved content file drawn from Dusten's career record (`dustenatx/career-record`), shall show a "Last updated" date, shall keep extra detail in closed-by-default `<details>` sections, and shall show no phone number, street address or email address; contact goes through LinkedIn and X. | S5 |
| R8 | When Dusten's career record changes materially, a refresh issue shall be opened in this repo, and the resume and About text shall be updated only from approved content. | S5a |
| R9 | Every page shall link to the BearingQuest GitHub organization, the blog (`/blog/`, in the header navigation and footer) and LinkedIn; the About and resume pages shall also link to X; a YouTube link shall be added when the channel exists. | S11 |
| R10 | No page shall describe Bearing Quest as a company, firm, studio, business or employer, or use a phrase on the career record's avoid list. | S9 |
| R11 | When published text changes, tests shall fail if a content placeholder appears, a resume figure differs from the approved content, or a link to LinkedIn or X differs from its approved address. | new (14 Nov) |

### Design and accessibility

| ID | Requirement | Was |
|---|---|---|
| R12 | The site shall follow `docs/design.md`: Bearing Quest tokens hand-written in `assets/css/site.css` and checked by a test against `docs/design/tokens.json` (and `docs/design/site-layer.json` for site-only tokens) in light and dark; fonts self-hosted from pinned upstream releases with their OFL licences and hash-pinned; logo SVGs hash-pinned with an SVG safety test. | S7 |
| R13 | The site shall offer Auto, Light and Dark themes, default Auto (follows the device): the switch is progressive enhancement, a same-origin script sets the theme before first paint, and stored choices are read and written inside try/catch. | S12 |
| R14 | Every page shall meet WCAG 2.2 AA: text contrast of 4.5:1 or better and focus rings and control edges of 3:1 or better in both themes, a visible focus ring on every interactive element, alt text or a presentation role on every image, one h1 per page, keyboard operation of every control including each `<details>` section, and no horizontal scroll at 320 px wide. | S8 |

### Security and change control

| ID | Requirement | Was |
|---|---|---|
| R15 | Every page shall carry the same Content-Security-Policy `<meta>` tag allowing only same-origin scripts, styles, fonts and images, with no inline script, style block or style attribute, and shall load no third-party script, analytics, tracker or font. | S6 |
| R16 | When a pull request is opened or updated, the six required checks (`check`, `gitleaks`, `semgrep`, `pip-audit`, `zizmor`, `e2e`) shall run against a branch up to date with `main`, and the pull request shall not merge until all pass and every conversation is resolved; only Dusten merges. | S10 |

### Blog (v1.1)

| ID | Requirement | Was |
|---|---|---|
| R17 | The site shall have a blog index at `/blog/` listing each post published on the site, newest first, with its title, publication date and summary line, followed by the earlier posts on Blogger with links to them until they are migrated. | new in v1.1 |
| R18 | Each post shall be published at `/blog/<slug>.html`, generated by Pelican from `content/blog/<slug>.md`, whose text Dusten has approved through a pull request, and shall show its publication date. | new in v1.1 |
| R19 | Images in a post shall be same-origin files under `assets/img/blog/`, each with alt text. SVG images shall be hash-pinned and carry no script, event handler, `foreignObject` or non-fragment link. A raster image shall be a JPEG or PNG of 400 KB or less, with `width` and `height` set. An AI-generated image shall have a visible caption saying which tool made it. | new in v1.1 |
| R20 | Pelican, its dependencies and its configuration shall be pinned in `uv.lock` and the repo; the build shall generate only the blog index, the post pages and one Atom feed (no author, category, tag or archive pages); and the built blog pages shall meet R10, R11, R14 and R15 and use the same header, navigation, footer and CSP as the other pages. | new in v1.1 |
| R21 | The site shall publish an Atom feed of the blog's posts at `/blog/feed.xml`, with absolute links to `https://bearingquest.com/blog/…`. | new in v1.1 |
| R22 | Each Pages deploy shall carry a CycloneDX build SBOM of the locked `site` dependency group, as a workflow artifact, containing no development-only package. | new in v1.1 |
| R23 | After each deploy and once a day, a read-only check shall fetch `https://bearingquest.com/`, `/blog/`, the newest post, `/blog/feed.xml` and one blog image, and fail unless each returns HTTP 200 over HTTPS with its expected title or content type, and each HTML page carries the CSP meta tag. | new in v1.1 |

## 3. Non-goals (v1.1)

Migrating the Blogger posts and handling their old addresses (v1.2); audio or video, which needs a CSP change and a transcript requirement; contact forms, comments, analytics, search, a CMS, any build step beyond copying files and the Pelican blog build (R20), server-side code, and serving project demos from this repo.

## 4. Threat model

| Asset | Threat | Control |
|---|---|---|
| bearingquest.com | Subdomain or domain takeover after a repo or Pages change | Org-level domain verification (TXT kept); no wildcard records; DNS-only records for GitHub; Pages kept off in other BearingQuest repos unless Dusten turns it on (not yet confirmed repo by repo) |
| bearingquest.com | Certificate issued by an unexpected CA | CAA `0 issue "letsencrypt.org"` (added 14 Nov 2026) |
| bearingquest.com | Registrar or Cloudflare account takeover, DNS hijack | 2FA on both accounts, registrar lock and DNSSEC: recommended, not yet confirmed (open question 1) |
| Domain reputation | Email spoofing as @bearingquest.com | Mail is hosted by iCloud: its SPF, DKIM and DMARC (`p=quarantine`) records stay |
| Site content | Defacement through a malicious or mistaken commit | R16; agent permission rules in `.claude/settings.json`; Claude apps limited to selected repos |
| Site content | Repo files exposed on the site | R2 |
| Visitors | Injected or third-party script | R15; zizmor and semgrep in CI; SHA-pinned actions |
| Dusten's privacy | Personal data on a public page or in history | R7; tests for phone and email patterns; gitleaks in CI and the pre-push hook; public history is permanent |
| Career credibility | Overstated claims on the About, resume or project pages | R6, R7, R10, R11, R18; the career record wins any conflict |
| Site build | A compromised Pelican or dependency release | R20 pins with hashes in uv.lock; pip-audit and Dependabot review; the R22 SBOM; only generated HTML ships, no third-party code |
| Availability | The domain, DNS or certificate lapses between deploys | R23's daily check; registrar lock and 2FA (open question 1) |

Limitation: GitHub Pages can't set custom response headers, so the CSP is a `<meta>` tag; it can't set `frame-ancestors`, and there is no HSTS preload control. Adding headers would need the Cloudflare proxy, which conflicts with GitHub's certificate renewal. Accepted for v1.

## 5. Cost

| Item | Cost | How it could stop being free |
|---|---|---|
| GitHub Pages | $0 (public repo, GitHub Free for organizations) | GitHub changes plan terms; soft limits of 100 GB a month and 1 GB published; no commercial use |
| GitHub Actions | $0 (public repo) | GitHub changes free minutes for public repos |
| Cloudflare DNS | $0 (Free plan) | Cloudflare changes the Free plan |
| Claude review workflow | Counts against Dusten's Claude subscription, no API billing | The subscription's terms change |
| bearingquest.com | Annual renewal, paid by Dusten | Existing cost, outside this project's $0 budget |

## 6. Privacy

Everything in the repo is public, including its history. The resume and About text come from approved content with no phone number, street address or email address. The site collects no visitor data: no analytics, cookies or forms. The theme choice is stored only in the visitor's own browser.

## 7. Design

`docs/design.md` records the site's layer on the Bearing Quest design system: the base as the site's own accent, the compass motif, and each project card edged in that project's own accent.

## 8. Definition of done

**v1 (done 14 Nov 2026):** R1–R16 met; four pages live (home, About, resume, 404) with approved content (PR #16); baseline 2.0 audit passed except the waiting rows recorded in `docs/decisions.md`.

**v1.1 (blog section):** R17–R23 met; `/blog/` and the first post live; R9's blog link points to `/blog/`.

**v1.2 (blog migration):** the Blogger posts moved here, with their old links handled; requirements added before the work starts.

## 9. Open questions

1. Which registrar holds the domain; are 2FA, registrar lock and DNSSEC on; is Pages off in every other BearingQuest repo? (Threat model.)
2. Blog migration approach (v1.2).
