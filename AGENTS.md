# Bearing Quest website

Hand-written static site served by GitHub Pages from `main` at bearingquest.com.
There is no build step, no package manager and no npm.

## Layout

- `index.html`, `about.html`, `resume.html`, `404.html` - the pages
- `assets/css/site.css` - the only stylesheet, including light and dark theme tokens
- `assets/js/theme.js` - the only script (theme switch)
- `assets/img/` - images, including the compass logo
- `tests/test_site.py` - pytest checks for the site
- `CNAME`, `.nojekyll` - GitHub Pages configuration

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
