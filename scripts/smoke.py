"""Smoke check of the live site (R23): five fixed URLs, read-only, standard library only.

Run with `uv run --no-project python3 scripts/smoke.py` (make smoke). Each URL must
return 200 over HTTPS with its expected title or content type, and each HTML page must
carry the Content-Security-Policy meta tag. Versions are never compared, because Pages
caches pages for up to about 10 minutes. Nothing comes from arguments, the environment
or workflow event input.
"""

from __future__ import annotations

import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

HOST = "bearingquest.com"
TIMEOUT = 15
TRIES = 3
BACKOFF = 2


@dataclass(frozen=True)
class Target:
    url: str
    title: str | None = None  # expected <title> of an HTML page
    content_type: str | None = None  # expected content type of anything else


TARGETS = (
    Target("https://bearingquest.com/", title="Projects | Bearing Quest"),
    Target("https://bearingquest.com/blog/", title="Blog | Bearing Quest"),
    Target(
        "https://bearingquest.com/blog/baseline-rollout.html",
        title=(
            "One baseline, six repositories: what changed when I stopped asking Claude "
            "for code and started auditing it | Bearing Quest"
        ),
    ),
    Target("https://bearingquest.com/blog/feed.xml", content_type="xml"),
    Target(
        "https://bearingquest.com/assets/img/blog/baseline-rollout-hero.jpg",
        content_type="image/jpeg",
    ),
)


def check_url(url: str) -> str:
    """Return the URL if it is HTTPS on the site's own host; raise otherwise."""
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != HOST or parts.username or parts.port:
        raise ValueError(f"refusing {url!r}: only https://{HOST}/ is allowed")
    return url


class SameHostRedirects(urllib.request.HTTPRedirectHandler):
    """Follow a redirect only if its target also passes check_url."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def make_opener() -> urllib.request.OpenerDirector:
    context = ssl.create_default_context()  # certificate and host name verification on
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context), SameHostRedirects()
    )


def fetch(url, opener, sleep=time.sleep):
    """GET url; return (status, content type, body). Retry network errors and 5xx."""
    check_url(url)
    for attempt in range(1, TRIES + 1):
        try:
            # The scheme and host are fixed by check_url and the URLs are constants.
            with opener.open(url, timeout=TIMEOUT) as response:
                return (
                    response.status,
                    response.headers.get("Content-Type", ""),
                    response.read(2_000_000).decode("utf-8", errors="replace"),
                )
        except urllib.error.HTTPError as error:
            if error.code < 500 or attempt == TRIES:
                return error.code, error.headers.get("Content-Type", ""), ""
        except OSError:  # URLError, timeouts and SSL errors are all OSErrors
            if attempt == TRIES:
                raise
        sleep(BACKOFF**attempt)
    raise AssertionError("unreachable")


TITLE = re.compile(r"<title>(.*?)</title>", re.DOTALL)
CSP = re.compile(r"<meta\s[^>]*http-equiv=[\"']Content-Security-Policy[\"']", re.IGNORECASE)


def problems(target: Target, status: int, content_type: str, body: str) -> list[str]:
    found = []
    if status != 200:
        return [f"status {status}"]
    if target.title is not None:
        match = TITLE.search(body)
        title = " ".join(match.group(1).split()) if match else None
        if title != target.title:
            found.append(f"title {title!r}")
        if not CSP.search(body):
            found.append("no Content-Security-Policy meta tag")
    if target.content_type is not None and target.content_type not in content_type:
        found.append(f"content type {content_type!r}")
    return found


def run(opener, out=sys.stdout, sleep=time.sleep) -> int:
    failures = 0
    for target in TARGETS:
        try:
            result = problems(target, *fetch(target.url, opener, sleep))
        except (ValueError, OSError) as error:
            result = [f"{type(error).__name__}: {error}"]
        failures += bool(result)
        out.write(f"{'FAIL' if result else 'ok'} {target.url} {'; '.join(result)}".rstrip() + "\n")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(run(make_opener()))
