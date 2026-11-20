"""Takes the blog screens for docs/design/screens/ (1280 px wide, light and dark).

Run it by hand in a plain Terminal, not in the agent sandbox, which can't start Chromium
on macOS. It serves a built site (the one argument, made by scripts/build-site.sh) on
127.0.0.1 and writes blog-desktop-* and blog-post-desktop-* PNGs. Chromium comes from
`uv run playwright install chromium`.
"""

from __future__ import annotations

import functools
import sys
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

SCREENS = Path(__file__).resolve().parents[1] / "docs/design/screens"
PAGES = {"blog-desktop": "/blog/", "blog-post-desktop": "/blog/baseline-rollout.html"}


def main(site: Path) -> None:
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        for scheme in ("light", "dark"):
            page = browser.new_page(viewport={"width": 1280, "height": 800}, color_scheme=scheme)
            for name, path in PAGES.items():
                page.goto(base + path)
                page.wait_for_load_state("networkidle")
                page.screenshot(path=str(SCREENS / f"{name}-{scheme}.png"), full_page=True)
            page.close()
        browser.close()
    server.shutdown()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: blog-screens.py BUILT_SITE_DIR")
    main(Path(sys.argv[1]))
