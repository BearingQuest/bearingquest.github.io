"""The built site, shared by the tests that check pages.

built_site() runs scripts/build-site.sh, the script pages.yml runs, once per test
session into a temporary directory, so the tests see the Pelican blog pages as well
as the copied ones.
"""

from __future__ import annotations

import atexit
import functools
import shutil
import tempfile
from pathlib import Path

from _proc import run

ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = ROOT / "scripts" / "build-site.sh"


@functools.cache
def built_site() -> Path:
    parent = Path(tempfile.mkdtemp(prefix="bq-site-"))
    atexit.register(shutil.rmtree, parent, ignore_errors=True)
    out = parent / "_site"
    result = run(["bash", str(BUILD_SCRIPT), str(out)], capture_output=True, text=True)
    assert result.returncode == 0, f"build-site.sh failed:\n{result.stdout}\n{result.stderr}"
    return out


def built_pages() -> list[Path]:
    """Every built .html file, root pages and blog pages."""
    return sorted(built_site().rglob("*.html"))
