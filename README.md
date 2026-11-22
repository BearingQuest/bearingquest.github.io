<p align="center">
  <a href="https://bearingquest.com">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="docs/readme/bearing-quest-lockup-on-dark.svg">
      <img alt="Bearing Quest" src="docs/readme/bearing-quest-lockup-on-light.svg" width="220">
    </picture>
  </a>
</p>

<h1 align="center">Bearing Quest website</h1>

<p align="center">
  The source of <a href="https://bearingquest.com">bearingquest.com</a>.<br>
  Part of the <a href="https://bearingquest.com">Bearing Quest</a> project family.
</p>

<p align="center">
  <a href="https://github.com/BearingQuest/bearingquest.github.io/actions/workflows/ci.yml"><img alt="CI status" src="https://github.com/BearingQuest/bearingquest.github.io/actions/workflows/ci.yml/badge.svg?branch=main"></a>
  <a href="https://scorecard.dev/viewer/?uri=github.com/BearingQuest/bearingquest.github.io"><img alt="OpenSSF Scorecard" src="https://api.scorecard.dev/projects/github.com/BearingQuest/bearingquest.github.io/badge"></a>
  <a href="LICENSE"><img alt="License: MIT for the code" src="https://img.shields.io/badge/license-MIT_(code)-1B365D"></a>
</p>

This repository contains the static website for Bearing Quest, a family of
personal software projects by Dusten Harrison.

The pages are hand-written HTML5 and CSS, with a small same-origin JavaScript
file for theme selection. The blog under `/blog/` is built from `content/blog`
by Pelican, which is locked in `uv.lock` (the `site` dependency group). The
published site loads nothing from other domains and has no analytics or
trackers. A GitHub Actions workflow (`.github/workflows/pages.yml`) publishes
only the paths listed in `site-files.txt`, plus the built blog, to GitHub Pages.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/readme/site-home-dark.png">
  <img alt="The bearingquest.com home page: Building toward true north, with the Projects, About, Resume and Blog links and the theme switch." src="docs/readme/site-home-light.png" width="720">
</picture>

```mermaid
flowchart LR
  PRQ["Pull request"] --> RC["Required checks<br/>check, gitleaks, semgrep,<br/>pip-audit, zizmor, e2e"]
  RC --> H{"Owner merges"}
  H --> B["pages.yml copies only the paths<br/>in site-files.txt and builds<br/>the blog with Pelican"]
  B --> GHP["GitHub Pages"] --> DOM["bearingquest.com"]
  DOM --> SM["Read-only smoke checks<br/>after each deploy and daily"]
```

## Local preview

Build the site the way the deploy does, then serve the folder with any static
HTTP server (needs [uv](https://docs.astral.sh/uv/); the folder must not exist yet):

```text
bash scripts/build-site.sh /tmp/bq-site
python3 -m http.server --directory /tmp/bq-site 8000
```

Then open http://localhost:8000. `make blog` builds only the blog, into
`_build/blog`.

## Tests

With [uv](https://docs.astral.sh/uv/) installed:

```text
make check   # ruff lint, ruff format check, then pytest
make audit   # pip-audit every package locked in uv.lock
make blog    # build the blog with Pelican into _build/blog
make sbom    # CycloneDX SBOM of the locked site group, into _build
make smoke   # read-only check of the live site (needs network)
make hooks   # once per clone: pre-push runs gitleaks on the pushed commits
```

The pre-push hook needs gitleaks (`brew install gitleaks`).

## Licensing

The site code is available under the MIT License. Site text is © 2026
Dusten Harrison, all rights reserved.

The self-hosted fonts (Inter, IBM Plex Mono and Cinzel) are licensed under the
SIL Open Font License 1.1; see `assets/fonts/OFL-*.txt`.
