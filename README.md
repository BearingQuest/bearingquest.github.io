# Bearing Quest website

[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/BearingQuest/bearingquest.github.io/badge)](https://scorecard.dev/viewer/?uri=github.com/BearingQuest/bearingquest.github.io)

This repository contains the static website for Bearing Quest, a family of
personal software projects by Dusten Harrison.

The site is hand-written HTML5, CSS and a small same-origin JavaScript file for
theme selection. It has no build step, package manager, external dependencies,
analytics or trackers. A GitHub Actions workflow (`.github/workflows/pages.yml`)
publishes only the paths listed in `site-files.txt` to GitHub Pages.

## Local preview

Serve the repository root with any static HTTP server, then open `index.html`
through that server. The site does not require compilation.

## Tests

With [uv](https://docs.astral.sh/uv/) installed:

```text
make check   # ruff lint, ruff format check, then pytest
make audit   # pip-audit every package locked in uv.lock
make hooks   # once per clone: pre-push runs gitleaks on the pushed commits
```

The pre-push hook needs gitleaks (`brew install gitleaks`).

## Licensing

The site code is available under the MIT License. Site text is © TODO year
Dusten Harrison, all rights reserved.

The self-hosted fonts (Inter, IBM Plex Mono and Cinzel) are licensed under the
SIL Open Font License 1.1; see `assets/fonts/OFL-*.txt`.
