from __future__ import annotations

import math
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest


ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = sorted(ROOT.glob("*.html"))
CSP = """<meta http-equiv="Content-Security-Policy"
          content="default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'">"""
EXTERNAL_SCHEMES = {"http", "https"}


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.start_tags: list[tuple[str, dict[str, str | None]]] = []
        self.inline_script_text: list[str] = []
        self._in_inline_script = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        self.start_tags.append((tag, attributes))
        if tag == "script" and not attributes.get("src"):
            self._in_inline_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._in_inline_script = False

    def handle_data(self, data: str) -> None:
        if self._in_inline_script and data.strip():
            self.inline_script_text.append(data)


def parse_html(path: Path) -> SiteParser:
    parser = SiteParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


@pytest.mark.parametrize("path", HTML_FILES, ids=lambda path: path.name)
def test_exact_csp_meta_tag(path: Path) -> None:
    assert CSP in path.read_text(encoding="utf-8")


def test_external_urls_only_appear_in_anchor_hrefs() -> None:
    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    assert not re.search(r"url\(\s*['\"]?https?://", css, re.IGNORECASE)

    for path in HTML_FILES:
        parser = parse_html(path)
        for tag, attrs in parser.start_tags:
            for attribute in ("src", "href"):
                value = attrs.get(attribute)
                if not value:
                    continue
                scheme = urlsplit(value).scheme.lower()
                if scheme in EXTERNAL_SCHEMES:
                    assert tag == "a" and attribute == "href", (
                        f"{path.name}: external URL in {tag}[{attribute}]"
                    )


@pytest.mark.parametrize("path", HTML_FILES, ids=lambda path: path.name)
def test_no_inline_script_or_style(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    parser = parse_html(path)
    assert not parser.inline_script_text
    assert "<style" not in text.lower()
    assert not re.search(r"\sstyle\s*=", text, re.IGNORECASE)


@pytest.mark.parametrize("path", HTML_FILES, ids=lambda path: path.name)
def test_internal_links_and_assets_resolve(path: Path) -> None:
    parser = parse_html(path)
    for tag, attrs in parser.start_tags:
        for attribute in ("href", "src"):
            value = attrs.get(attribute)
            if not value or value.startswith(("#", "data:")):
                continue
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc:
                continue
            target_path = unquote(parsed.path)
            if not target_path:
                continue
            target = ROOT / target_path.lstrip("/")
            if target.is_dir():
                target /= "index.html"
            assert target.is_file(), (
                f"{path.name}: {tag}[{attribute}] does not resolve: {value}"
            )


@pytest.mark.parametrize("path", HTML_FILES, ids=lambda path: path.name)
def test_images_have_accessible_alt_text(path: Path) -> None:
    parser = parse_html(path)
    for tag, attrs in parser.start_tags:
        if tag != "img":
            continue
        assert "alt" in attrs, f"{path.name}: image is missing alt"
        assert attrs["alt"] or attrs.get("role") == "presentation"


@pytest.mark.parametrize("path", HTML_FILES, ids=lambda path: path.name)
def test_one_h1_and_a_title(path: Path) -> None:
    parser = parse_html(path)
    tags = [tag for tag, _ in parser.start_tags]
    assert tags.count("h1") == 1
    assert tags.count("title") == 1


def test_no_phone_numbers_or_email_addresses_in_html() -> None:
    phone = re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")
    email = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    for path in HTML_FILES:
        text = path.read_text(encoding="utf-8")
        assert not phone.search(text), f"{path.name}: phone number found"
        assert not email.search(text), f"{path.name}: email address found"


def test_bearing_quest_is_not_presented_as_an_organization() -> None:
    prohibited = r"(?:company|firm|studio|our\s+team|employer)"
    for path in HTML_FILES:
        text = re.sub(r"<[^>]+>", " ", path.read_text(encoding="utf-8"))
        normalized = re.sub(r"\s+", " ", text)
        assert not re.search(
            rf"Bearing Quest.{{0,80}}\b{prohibited}\b|\b{prohibited}\b.{{0,80}}Bearing Quest",
            normalized,
            re.IGNORECASE,
        )


def test_github_pages_files() -> None:
    assert (ROOT / "CNAME").read_text(encoding="utf-8") == "bearingquest.com\n"
    assert (ROOT / ".nojekyll").is_file()


def css_block(css: str, selector: str) -> str:
    start = css.index(selector)
    opening = css.index("{", start) + 1
    depth = 1
    cursor = opening
    while depth:
        if css[cursor] == "{":
            depth += 1
        elif css[cursor] == "}":
            depth -= 1
        cursor += 1
    return css[opening : cursor - 1]


def tokens_from_block(block: str) -> dict[str, str]:
    return dict(
        re.findall(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", block)
    )


def declarations_from_block(block: str) -> dict[str, str]:
    return {
        name: re.sub(r"\s+", " ", value.strip())
        for name, value in re.findall(r"([\w-]+)\s*:\s*([^;{}]+);", block)
    }


def relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92
        if channel <= 0.04045
        else math.pow((channel + 0.055) / 1.055, 2.4)
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted(
        (relative_luminance(first), relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def test_token_contrast_in_both_themes() -> None:
    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    themes = {
        "light": tokens_from_block(css_block(css, '[data-theme="light"]')),
        "dark": tokens_from_block(css_block(css, '[data-theme="dark"]')),
    }
    checks = (
        ("text", "ground", 4.5),
        ("text", "surface", 4.5),
        ("heading", "surface", 4.5),
        ("muted", "ground", 4.5),
        ("accent", "surface", 4.5),
        ("accent", "ground", 4.5),
        ("control", "ground", 3.0),
        ("control", "surface", 3.0),
        ("focus", "ground", 3.0),
        ("focus", "surface", 3.0),
    )

    for theme_name, tokens in themes.items():
        for foreground, background, minimum in checks:
            ratio = contrast_ratio(tokens[foreground], tokens[background])
            assert ratio >= minimum, (
                f"{theme_name}: {foreground}/{background} contrast "
                f"{ratio:.2f} is below {minimum:.1f}"
            )


def test_theme_token_blocks_match() -> None:
    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    media = css_block(css, "@media (prefers-color-scheme: dark)")
    auto_dark = declarations_from_block(css_block(media, ":root:not([data-theme])"))
    explicit_dark = declarations_from_block(css_block(css, '[data-theme="dark"]'))
    light_root = declarations_from_block(css_block(css, ":root {"))
    explicit_light = declarations_from_block(css_block(css, '[data-theme="light"]'))

    assert auto_dark
    assert auto_dark == explicit_dark
    assert light_root
    assert light_root == explicit_light


def test_404_internal_references_are_root_absolute() -> None:
    parser = parse_html(ROOT / "404.html")
    for tag, attrs in parser.start_tags:
        for attribute in ("href", "src"):
            value = attrs.get(attribute)
            if not value or value.startswith(("#", "data:")):
                continue
            parsed = urlsplit(value)
            if parsed.scheme or parsed.netloc:
                continue
            assert value.startswith("/"), (
                f"404.html: {tag}[{attribute}] is not root-absolute: {value}"
            )


def test_theme_option_labels_show_keyboard_focus() -> None:
    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    block = css_block(css, ".theme-options label:has(input:focus-visible)")
    declarations = declarations_from_block(block)
    assert declarations.get("outline") == "3px solid var(--focus)"
    assert declarations.get("outline-offset") == "2px"
