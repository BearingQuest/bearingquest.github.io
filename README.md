# Bearing Quest website

This repository contains the static website for Bearing Quest, a family of
personal software projects by Dusten Harrison.

The site is hand-written HTML5, CSS and a small same-origin JavaScript file for
theme selection. It has no build step, package manager, external dependencies,
analytics or trackers. GitHub Pages serves the files from the repository root.

## Local preview

Serve the repository root with any static HTTP server, then open `index.html`
through that server. The site does not require compilation.

## Tests

With [uv](https://docs.astral.sh/uv/) installed:

```text
uv run pytest
```

## Licensing

The site code is available under the MIT License. Site text is © TODO year
Dusten Harrison, all rights reserved.

The self-hosted fonts (Inter, IBM Plex Mono and Cinzel) are licensed under the
SIL Open Font License 1.1; see `assets/fonts/OFL-*.txt`.
