"""Serves the published file set on 127.0.0.1 for the browser tests.

The files come from scripts/build-site.sh, the script pages.yml runs, so e2e
tests what deploys. Missing paths get 404.html with a 404 status, as on Pages.
"""

from __future__ import annotations

import functools
import threading
from collections.abc import Iterator
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from _proc import run

ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "scripts" / "build-site.sh"


class PagesHandler(SimpleHTTPRequestHandler):
    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        if code != 404:
            super().send_error(code, message, explain)
            return
        body = (Path(self.directory) / "404.html").read_bytes()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def list_directory(self, path: str | Path) -> None:
        # Pages has no directory listings; a folder without an index is a 404.
        self.send_error(404)

    def log_message(self, format: str, *args: object) -> None:
        pass


@pytest.fixture(scope="session")
def site_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("e2e") / "_site"
    run(["bash", str(BUILD_SCRIPT), str(out)], check=True, capture_output=True)
    return out


@pytest.fixture(scope="session")
def base_url(site_dir: Path) -> Iterator[str]:
    handler = functools.partial(PagesHandler, directory=str(site_dir))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)
