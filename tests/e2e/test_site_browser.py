"""Chromium checks of the built site, served as Pages serves it."""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest
from playwright.sync_api import ConsoleMessage, Page, expect

pytestmark = pytest.mark.e2e

# (path, expected status). /a/b/c is a nested missing path, so it renders 404.html.
PAGES = [
    ("/index.html", 200),
    ("/about.html", 200),
    ("/resume.html", 200),
    ("/a/b/c", 404),
]
NAV_HREFS = {"index.html", "about.html", "resume.html"}
RECORD_CSP_VIOLATIONS = """
window.__csp = [];
document.addEventListener("securitypolicyviolation", (event) => {
  window.__csp.push(event.violatedDirective + " " + event.blockedURI);
});
"""

page_params = pytest.mark.parametrize(("path", "status"), PAGES, ids=[p for p, _ in PAGES])


def background(page: Page) -> str:
    return str(page.evaluate("getComputedStyle(document.body).backgroundColor"))


def theme_attribute(page: Page) -> str | None:
    value = page.evaluate("document.documentElement.getAttribute('data-theme')")
    return None if value is None else str(value)


def choose_theme(page: Page, name: str) -> None:
    page.locator(".theme-options label", has_text=name).click()


@page_params
def test_page_loads_without_console_errors_or_csp_violations(
    page: Page, base_url: str, path: str, status: int
) -> None:
    errors: list[str] = []
    document_url = base_url + path

    def on_console(message: ConsoleMessage) -> None:
        # Chromium logs "Failed to load resource" for a 404 document itself; that is
        # the expected status of the 404 page, not a broken asset on it.
        if message.type == "error" and not (
            status == 404 and message.location["url"] == document_url
        ):
            errors.append(message.text)

    page.on("console", on_console)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.add_init_script(RECORD_CSP_VIOLATIONS)
    response = page.goto(base_url + path)
    assert response is not None
    assert response.status == status
    page.wait_for_load_state("networkidle")
    expect(page.locator("h1")).to_have_count(1)
    assert errors == []
    assert page.evaluate("window.__csp") == []


@page_params
def test_tab_reaches_the_theme_switch_and_every_nav_link_with_a_focus_indicator(
    page: Page, base_url: str, path: str, status: int
) -> None:
    page.goto(base_url + path)
    focused = []
    for _ in range(25):
        page.keyboard.press("Tab")
        focused.append(
            page.evaluate(
                """() => {
                  const el = document.activeElement;
                  // The radios are styled through their label's :has(:focus-visible) rule.
                  const shown = el.tagName === "INPUT" ? el.closest("label") : el;
                  const style = getComputedStyle(shown);
                  return {
                    href: el.tagName === "A" ? el.getAttribute("href") : null,
                    theme: el.matches('input[name="theme"]'),
                    outline: style.outlineStyle,
                    width: parseFloat(style.outlineWidth),
                  };
                }"""
            )
        )
    nav = {item["href"].rsplit("/", 1)[-1]: item for item in focused if item["href"]}
    assert set(nav) >= NAV_HREFS
    theme = [item for item in focused if item["theme"]]
    assert theme, "Tab never reached the theme switch"
    for item in [*(nav[name] for name in NAV_HREFS), *theme]:
        assert item["outline"] != "none"
        assert item["width"] >= 2


@page_params
def test_theme_auto_light_and_dark_apply_and_persist(
    page: Page, base_url: str, path: str, status: int
) -> None:
    page.emulate_media(color_scheme="light")
    page.goto(base_url + path)
    assert theme_attribute(page) is None

    choose_theme(page, "Dark")
    assert theme_attribute(page) == "dark"
    dark_bg = background(page)
    page.reload()
    assert theme_attribute(page) == "dark"
    expect(page.locator('input[name="theme"][value="dark"]')).to_be_checked()
    assert background(page) == dark_bg

    choose_theme(page, "Light")
    assert theme_attribute(page) == "light"
    light_bg = background(page)
    assert light_bg != dark_bg
    page.reload()
    assert theme_attribute(page) == "light"
    expect(page.locator('input[name="theme"][value="light"]')).to_be_checked()

    choose_theme(page, "Auto")
    assert theme_attribute(page) is None
    assert background(page) == light_bg
    page.emulate_media(color_scheme="dark")
    assert background(page) == dark_bg
    page.reload()
    assert theme_attribute(page) is None
    expect(page.locator('input[name="theme"][value="auto"]')).to_be_checked()
    assert background(page) == dark_bg


@page_params
def test_no_horizontal_scroll_at_360px(page: Page, base_url: str, path: str, status: int) -> None:
    page.set_viewport_size({"width": 360, "height": 800})
    page.goto(base_url + path)
    page.wait_for_load_state("networkidle")
    widths = page.evaluate(
        "[document.documentElement.scrollWidth, document.documentElement.clientWidth]"
    )
    assert widths[0] <= widths[1], widths


def test_nested_missing_path_gets_the_styled_404_page(page: Page, base_url: str) -> None:
    responses: dict[str, int] = {}
    page.on("response", lambda r: responses.__setitem__(urlsplit(r.url).path, r.status))
    response = page.goto(base_url + "/a/b/c")
    assert response is not None
    assert response.status == 404
    page.wait_for_load_state("networkidle")
    expect(page.locator("h1")).to_have_text("Page not found")
    assert responses["/assets/css/site.css"] == 200
    assert responses["/assets/js/theme.js"] == 200
    # The stylesheet applied: the page font is not the browser default serif.
    assert page.evaluate("getComputedStyle(document.body).fontFamily") != "Times New Roman"
    # A folder without an index is a 404 as well, not a listing.
    folder = page.goto(base_url + "/assets/")
    assert folder is not None
    assert folder.status == 404


@page_params
def test_no_request_leaves_the_local_origin(
    page: Page, base_url: str, path: str, status: int
) -> None:
    urls: list[str] = []
    page.on("request", lambda r: urls.append(r.url))
    page.goto(base_url + path)
    page.wait_for_load_state("networkidle")
    assert urls
    outside = [u for u in urls if not u.startswith(base_url + "/")]
    assert outside == []
