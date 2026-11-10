from __future__ import annotations

import hashlib
import math
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = sorted(ROOT.glob("*.html"))
# The exact tag, line break and indent included, as it appears in every page.
CSP = (
    '<meta http-equiv="Content-Security-Policy"\n'
    "          content=\"default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'\">"
)
EXTERNAL_SCHEMES = {"http", "https"}


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.start_tags: list[tuple[str, dict[str, str | None]]] = []
        self.inline_script_text: list[str] = []
        self._in_inline_script = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
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
            assert target.is_file(), f"{path.name}: {tag}[{attribute}] does not resolve: {value}"


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
    return dict(re.findall(r"--([\w-]+)\s*:\s*(#[0-9a-fA-F]{6})\s*;", block))


def declarations_from_block(block: str) -> dict[str, str]:
    return {
        name: re.sub(r"\s+", " ", value.strip())
        for name, value in re.findall(r"([\w-]+)\s*:\s*([^;{}]+);", block)
    }


def relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else math.pow((channel + 0.055) / 1.055, 2.4)
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(first: str, second: str) -> float:
    lighter, darker = sorted((relative_luminance(first), relative_luminance(second)), reverse=True)
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


EXPECTED_ASSET_HASHES = {
    "assets/fonts/Cinzel-wght.woff2": (
        "2ab8b19811f4842ad4c9d168f934ef046355e81a3a6f36e15fe7a4abe38239d3"
    ),
    "assets/fonts/IBMPlexMono-Medium-Latin1.woff2": (
        "41201b658a328b9d00368215c2f1102770f80b15952ab82631e4006255e6365d"
    ),
    "assets/fonts/IBMPlexMono-Regular-Latin1.woff2": (
        "e8993d946649b9d01abb1ed06d574b19d8ea3e66b5c3948602db335c44c18e56"
    ),
    "assets/fonts/Inter-Bold.woff2": (
        "fa888127b6da015b65569f0351f3b5c391ad928904951f1c20e9f8462a8d95ea"
    ),
    "assets/fonts/Inter-Regular.woff2": (
        "e06f6b1bc553aaea4e4668023ed0ab0a147129c3107f511bc7d03d361b0ae085"
    ),
    "assets/fonts/OFL-Cinzel.txt": (
        "f2b3029aba64c378bf0963b62945eee15e564fe4330b934c8f2eb058282b5e83"
    ),
    "assets/fonts/OFL-IBM-Plex-Mono.txt": (
        "7e6b2818edbd8f6a01ae80641cc8f16a51080d08fb4e532be3a0b6f74adb07da"
    ),
    "assets/fonts/OFL-Inter.txt": (
        "262481e844521b326f5ecd053e59b98c8b2da78c8ee1bdbb6e8174305e54935a"
    ),
    "assets/img/bearing-quest-lockup-on-dark.svg": (
        "6a34f44ae1bd1880d9ff1e14628f7c4c3947a90a7113a81934e20ab7d08ea981"
    ),
    "assets/img/bearing-quest-lockup-on-light.svg": (
        "464c80c7ee3124dcd7e9fef0b9fbf216eb23a08b592bd10ffd506bec8388511c"
    ),
    "assets/img/bearing-quest-mark-on-dark.svg": (
        "f6ac1cd9c1a823b85af350979f745b0957ab1e2119b97a5289093f25489da09a"
    ),
    "assets/img/bearing-quest-mark-on-light.svg": (
        "4a62583464ca8a17b62973d9e90f46c7d82afcab89156ca6f30c433cb2ef22ac"
    ),
}
SVG_FILES = sorted((ROOT / "assets/img").glob("*.svg"))


def test_font_and_svg_hashes_are_pinned() -> None:
    present = {
        path.relative_to(ROOT).as_posix()
        for pattern in ("assets/fonts/*.woff2", "assets/fonts/OFL-*.txt", "assets/img/*.svg")
        for path in ROOT.glob(pattern)
    }
    assert present == set(EXPECTED_ASSET_HASHES)
    for name, expected in EXPECTED_ASSET_HASHES.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        assert actual == expected, f"{name}: SHA-256 {actual} is not pinned"


@pytest.mark.parametrize("path", SVG_FILES, ids=lambda path: path.name)
def test_svg_has_no_active_content(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    assert not re.search(r"<script", text, re.IGNORECASE)
    assert not re.search(r"\son[a-z]+\s*=", text, re.IGNORECASE)
    assert not re.search(r"<foreignObject", text, re.IGNORECASE)
    for match in re.finditer(r"\s(?:xlink:)?href\s*=\s*(['\"])(.*?)\1", text, re.IGNORECASE):
        assert re.fullmatch(r"#[\w.-]+", match.group(2)), (
            f"{path.name}: href is not a fragment: {match.group(2)}"
        )


def test_font_faces_resolve_and_have_licenses() -> None:
    css_dir = ROOT / "assets/css"
    css = (css_dir / "site.css").read_text(encoding="utf-8")
    faces = re.findall(r"@font-face\s*\{([^}]*)\}", css)
    assert faces
    families = set()
    for face in faces:
        family = re.search(r"font-family:\s*\"([^\"]+)\"", face).group(1)
        families.add(family)
        urls = re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", face)
        assert urls, f"{family}: @font-face has no url()"
        for url in urls:
            assert (css_dir / url).resolve().is_file(), f"{family}: {url} is missing"
    assert families == {"Inter", "IBM Plex Mono", "Cinzel"}
    for family in families:
        license_file = ROOT / "assets/fonts" / f"OFL-{family.replace(' ', '-')}.txt"
        assert license_file.is_file(), f"{family}: {license_file.name} is missing"


def test_no_references_to_compass_svg() -> None:
    this_file = Path(__file__).resolve()
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part.startswith(".") for part in relative.parts):
            continue
        if not path.is_file() or path.resolve() == this_file:
            continue
        if path.suffix not in {".html", ".css", ".js", ".md", ".txt", ".toml", ".py"}:
            continue
        text = path.read_text(encoding="utf-8")
        assert "compass.svg" not in text, f"{relative}: references compass.svg"


def rule_declarations(css: str, selector: str) -> dict[str, str]:
    match = re.search(rf"^[ \t]*{re.escape(selector)}\s*\{{", css, re.MULTILINE)
    assert match, f"no rule for {selector}"
    return declarations_from_block(css_block(css[match.start() :], selector))


def test_logo_variants_switch_in_both_dark_theme_paths() -> None:
    css = (ROOT / "assets/css/site.css").read_text(encoding="utf-8")
    assert rule_declarations(css, ".theme-dark").get("display") == "none"

    media_blocks = [
        css_block(css[match.start() :], "@media (prefers-color-scheme: dark)")
        for match in re.finditer(r"@media \(prefers-color-scheme: dark\)", css)
    ]
    auto_dark = "".join(media_blocks)
    for scope, source in (
        (":root:not([data-theme])", auto_dark),
        ('[data-theme="dark"]', css),
    ):
        hidden = rule_declarations(source, f"{scope} .theme-light")
        shown = rule_declarations(source, f"{scope} .theme-dark")
        assert hidden.get("display") == "none", scope
        assert shown.get("display") not in (None, "none"), scope
