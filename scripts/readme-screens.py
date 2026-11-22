"""Takes the README screenshots for docs/readme/ (the home page, light and dark).

Run it by hand in a plain Terminal, not in the agent sandbox, which can't start Chromium
on macOS. It serves a built site (the one argument, made by scripts/build-site.sh) on
127.0.0.1 and writes site-home-light.png and site-home-dark.png. Re-run it in any pull
request that changes what the home page's first screen shows. Chromium comes from
`uv run playwright install chromium`.
"""

from __future__ import annotations

import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

README_IMAGES = Path(__file__).resolve().parents[1] / "docs/readme"
VIEWPORT = {"width": 1200, "height": 760}


def main(site: Path) -> None:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for scheme in ("light", "dark"):
            page = browser.new_page(viewport=VIEWPORT, color_scheme=scheme)
            page.goto(base + "/")
            page.wait_for_load_state("networkidle")
            page.screenshot(path=str(README_IMAGES / f"site-home-{scheme}.png"))
            page.close()
        browser.close()
    server.shutdown()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: readme-screens.py BUILT_SITE_DIR")
    main(Path(sys.argv[1]))
