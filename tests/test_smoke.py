"""R23: scripts/smoke.py checks five fixed HTTPS URLs; no test touches the network."""

from __future__ import annotations

import importlib.util
import io
import re
import ssl
import sys
import urllib.error
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
from test_workflows import ROOT

SCRIPT = ROOT / "scripts/smoke.py"
spec = importlib.util.spec_from_file_location("smoke", SCRIPT)
assert spec and spec.loader
smoke = importlib.util.module_from_spec(spec)
sys.modules["smoke"] = smoke  # dataclasses looks its module up here
spec.loader.exec_module(smoke)

PAGE = (
    '<html><head><meta http-equiv="Content-Security-Policy" content="default-src \'self\'">'
    "<title>{title}</title></head></html>"
)


class FakeResponse:
    def __init__(self, status: int, content_type: str, body: str) -> None:
        self.status = status
        self.headers = {"Content-Type": content_type}
        self.body = body.encode()

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self, limit: int = -1) -> bytes:
        return self.body[:limit]


class FakeOpener:
    """Plays back one outcome per call: a FakeResponse, or an exception to raise."""

    def __init__(self, *outcomes: Any) -> None:
        self.outcomes = list(outcomes)
        self.calls = 0

    def open(self, url: str, timeout: int) -> FakeResponse:
        assert timeout == 15
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome  # type: ignore[no-any-return]


def http_error(code: int) -> urllib.error.HTTPError:
    headers = Message()
    return urllib.error.HTTPError("https://bearingquest.com/", code, "x", headers, io.BytesIO())


def newest_post_slug() -> str:
    posts = []
    for path in (ROOT / "content/blog").glob("*.md"):
        meta = dict(re.findall(r"^(Date|Slug): (.+)$", path.read_text(encoding="utf-8"), re.M))
        posts.append((meta["Date"], meta["Slug"]))
    return max(posts)[1]


def test_the_url_list_is_fixed_https_only_and_covers_r23() -> None:
    urls = [t.url for t in smoke.TARGETS]
    assert len(urls) == len(set(urls)) == 5
    assert all(u.startswith("https://bearingquest.com/") for u in urls)
    assert urls[:2] == ["https://bearingquest.com/", "https://bearingquest.com/blog/"]
    assert urls[2] == f"https://bearingquest.com/blog/{newest_post_slug()}.html"
    assert urls[3] == "https://bearingquest.com/blog/feed.xml"
    assert urls[4].startswith("https://bearingquest.com/assets/img/blog/")
    assert (ROOT / urls[4].removeprefix("https://bearingquest.com/")).is_file()


@pytest.mark.parametrize(
    "url",
    [
        "http://bearingquest.com/",
        "https://example.com/",
        "https://www.bearingquest.com/",
        "https://bearingquest.com.evil.example/",
        "https://user@bearingquest.com/",
        "https://bearingquest.com:8443/",
        "ftp://bearingquest.com/",
    ],
)
def test_it_refuses_http_and_other_hosts(url: str) -> None:
    with pytest.raises(ValueError, match="only https"):
        smoke.check_url(url)
    with pytest.raises(ValueError, match="only https"):
        smoke.fetch(url, FakeOpener())
    with pytest.raises(ValueError, match="only https"):
        smoke.SameHostRedirects().redirect_request(None, None, 301, "", {}, url)


def test_the_opener_verifies_certificates_and_never_leaves_the_host() -> None:
    opener = smoke.make_opener()
    https = next(h for h in opener.handlers if hasattr(h, "_context"))
    assert https._context.verify_mode == ssl.CERT_REQUIRED
    assert https._context.check_hostname is True
    assert any(isinstance(h, smoke.SameHostRedirects) for h in opener.handlers)


def test_parsing_checks_status_title_content_type_and_the_csp_tag() -> None:
    page = smoke.Target("https://bearingquest.com/", title="Hello | Bearing Quest")
    good = PAGE.format(title="Hello |\n  Bearing Quest")
    assert smoke.problems(page, 200, "text/html", good) == []
    assert smoke.problems(page, 404, "text/html", good) == ["status 404"]
    assert smoke.problems(page, 200, "text/html", PAGE.format(title="Other")) == ["title 'Other'"]
    no_csp = good.replace("Content-Security-Policy", "x-other")
    assert smoke.problems(page, 200, "text/html", no_csp) == ["no Content-Security-Policy meta tag"]
    feed = smoke.Target("https://bearingquest.com/blog/feed.xml", content_type="xml")
    assert smoke.problems(feed, 200, "application/xml", "<feed/>") == []
    assert smoke.problems(feed, 200, "text/html", "<feed/>") == ["content type 'text/html'"]


def test_it_retries_network_errors_and_server_errors_with_backoff_then_succeeds() -> None:
    ok = FakeResponse(200, "text/html", "body")
    opener = FakeOpener(urllib.error.URLError("boom"), http_error(503), ok)
    sleeps: list[int] = []
    assert smoke.fetch("https://bearingquest.com/", opener, sleeps.append) == (
        200,
        "text/html",
        "body",
    )
    assert opener.calls == smoke.TRIES == 3
    assert sleeps == [2, 4]


def test_it_gives_up_after_three_tries_and_does_not_retry_a_404() -> None:
    opener = FakeOpener(*[TimeoutError()] * 3)
    with pytest.raises(TimeoutError):
        smoke.fetch("https://bearingquest.com/", opener, lambda _: None)
    assert opener.calls == 3
    not_found = FakeOpener(http_error(404))
    assert smoke.fetch("https://bearingquest.com/", not_found, lambda _: None)[0] == 404
    assert not_found.calls == 1


def test_run_prints_one_line_per_url_and_exits_non_zero_on_any_failure() -> None:
    def responses(skip_csp: bool) -> list[FakeResponse]:
        out = []
        for target in smoke.TARGETS:
            if target.title:
                body = PAGE.format(title=target.title)
                if skip_csp and target is smoke.TARGETS[1]:
                    body = body.replace("Content-Security-Policy", "x")
                out.append(FakeResponse(200, "text/html", body))
            else:
                out.append(FakeResponse(200, f"application/{target.content_type}", ""))
        return out

    out = io.StringIO()
    assert smoke.run(FakeOpener(*responses(False)), out, lambda _: None) == 0
    assert [line.split()[0] for line in out.getvalue().splitlines()] == ["ok"] * 5
    out = io.StringIO()
    assert smoke.run(FakeOpener(*responses(True)), out, lambda _: None) == 1
    lines = out.getvalue().splitlines()
    assert len(lines) == 5 and lines[1].startswith("FAIL ") and "Content-Security" in lines[1]


def test_the_script_takes_nothing_from_the_environment_or_arguments_and_compares_no_versions() -> (
    None
):
    text = SCRIPT.read_text(encoding="utf-8")
    for forbidden in ("os.environ", "getenv", "sys.argv", "argparse", "github.event", "ETag"):
        assert forbidden not in text, forbidden
    assert "# noqa" not in text and "nosemgrep" not in text
    assert Path(SCRIPT).read_text(encoding="utf-8").count("http://") == 0
