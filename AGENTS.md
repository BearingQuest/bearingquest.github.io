# Bearing Quest website

Hand-written static site deployed to bearingquest.com by
`.github/workflows/pages.yml`, which publishes only the paths listed in
`site-files.txt`. There is no build step (the workflow only copies files), no
package manager and no npm.

## Layout

- `index.html`, `about.html`, `resume.html`, `404.html` - the pages
- `assets/css/site.css` - the only stylesheet, including light and dark theme tokens
- `assets/js/theme.js` - the only script (theme switch)
- `assets/img/` - images, including the Bearing Quest mark and lockup SVGs
- `tests/test_site.py` - pytest checks for the site
- `tests/test_pages_deploy.py` - pytest checks for `site-files.txt` and `pages.yml`
- `site-files.txt` - the only paths published to the site; every tracked root
  file is either listed there or in the test's not-published list
- `CNAME`, `.nojekyll` - unpublished, kept as the branch-publishing fallback
- `.github/` - CI workflows and Dependabot configuration

## CI

`.github/workflows/ci.yml` runs on every pull request and every push to `main`:

- `test` - `uv sync --locked`, then `uv run pytest`
- `gitleaks` - scans the full git history for secrets with a checksum-pinned gitleaks CLI
- `pip-audit` - audits every package locked in `uv.lock` for known vulnerabilities

All three must pass before merge. `pip-audit-daily.yml` also runs the audit on
`main` every day. Dependabot proposes weekly updates for `uv` and GitHub Actions.

`.github/workflows/pages.yml` copies the `site-files.txt` paths into the Pages
artifact. Its `build` job runs on every pull request and push to `main`; its
`deploy` job runs only on a push to `main` or a manual run on `main`.

## Rules

- Static HTML, CSS and same-origin JavaScript only.
- No frameworks, CDNs, third-party scripts or analytics.
- No inline `<script>` content, `<style>` elements or `style=` attributes.
- Keep the exact Content-Security-Policy meta tag on every page.
- Never invent content for `[TODO: ...]` placeholders. Leave them as they are.
- Bearing Quest is the name of a family of projects. Never present it as a
  company, firm, studio or team.
- Never put a phone number, street address or email address in any page.
- Run `uv run pytest` before opening any PR.
- Work on a branch. Never push to `main` and never merge.
