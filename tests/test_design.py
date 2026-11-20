"""Checks that the site follows docs/design.md and docs/design/."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import zlib

from test_site import ROOT, css_block

DESIGN = ROOT / "docs/design"
CSS_PATH = ROOT / "assets/css/site.css"

# docs/design.md, "Tokens on the site": a name that differs from its source token.
RENAMED_SOURCE_TOKENS = {
    "brand-accent": ("tokens.json", "brand-orange"),
    "vector-accent": ("tokens.json", "qv-accent"),
    "risk-accent": ("site-layer.json", "risk-accent"),
}
# Colors written as functions or keywords. The site writes hex only.
COLOR_FUNCTION = re.compile(
    r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\(", re.IGNORECASE
)
NAMED_COLORS = set(
    re.findall(
        r"\w+",
        "aliceblue antiquewhite aqua aquamarine azure beige bisque black blanchedalmond blue "
        "blueviolet brown burlywood cadetblue chartreuse chocolate coral cornflowerblue cornsilk "
        "crimson cyan darkblue darkcyan darkgoldenrod darkgray darkgreen darkgrey darkkhaki "
        "darkmagenta darkolivegreen darkorange darkorchid darkred darksalmon darkseagreen "
        "darkslateblue darkslategray darkslategrey darkturquoise darkviolet deeppink deepskyblue "
        "dimgray dimgrey dodgerblue firebrick floralwhite forestgreen fuchsia gainsboro ghostwhite "
        "gold goldenrod gray green greenyellow grey honeydew hotpink indianred indigo ivory khaki "
        "lavender lavenderblush lawngreen lemonchiffon lightblue lightcoral lightcyan "
        "lightgoldenrodyellow lightgray lightgreen lightgrey lightpink lightsalmon lightseagreen "
        "lightskyblue lightslategray lightslategrey lightsteelblue lightyellow lime limegreen "
        "linen magenta maroon mediumaquamarine mediumblue mediumorchid mediumpurple "
        "mediumseagreen mediumslateblue mediumspringgreen mediumturquoise mediumvioletred "
        "midnightblue mintcream mistyrose moccasin navajowhite navy oldlace olive olivedrab "
        "orange orangered orchid palegoldenrod palegreen paleturquoise palevioletred papayawhip "
        "peachpuff peru pink plum powderblue purple rebeccapurple red rosybrown royalblue "
        "saddlebrown salmon sandybrown seagreen seashell sienna silver skyblue slateblue "
        "slategray slategrey snow springgreen steelblue tan teal thistle tomato turquoise violet "
        "wheat white whitesmoke yellow yellowgreen transparent currentcolor",
    )
)
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}")
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXPECTED_SCREENS = {
    f"{page}-desktop-{theme}.png"
    for page in ("home", "about", "resume", "404")
    for theme in ("light", "dark")
} | {
    "home-mobile-light.png",
    "home-mobile-dark.png",
    "blog-desktop-light.png",
    "blog-desktop-dark.png",
    "blog-post-desktop-light.png",
    "blog-post-desktop-dark.png",
}


def design_tokens(filename: str) -> dict[str, dict[str, str]]:
    data = json.loads((DESIGN / filename).read_text(encoding="utf-8"))
    return {token["name"]: token["value"] for token in data["color"]["tokens"]}


def token_blocks(css: str) -> dict[str, tuple[str, str]]:
    """The four token blocks as {label: (theme, block text)}."""
    media = css_block(css, "@media (prefers-color-scheme: dark)")
    return {
        ":root": ("light", css_block(css, ":root {")),
        "prefers-color-scheme dark": ("dark", css_block(media, ":root:not([data-theme])")),
        '[data-theme="light"]': ("light", css_block(css, '[data-theme="light"]')),
        '[data-theme="dark"]': ("dark", css_block(css, '[data-theme="dark"]')),
    }


def is_color_value(value: str) -> bool:
    words = set(re.findall(r"[a-z]+", value.lower()))
    return value.startswith("#") or bool(COLOR_FUNCTION.search(value) or words & NAMED_COLORS)


def color_token_problems(css: str) -> list[str]:
    sources = {
        "tokens.json": design_tokens("tokens.json"),
        "site-layer.json": design_tokens("site-layer.json"),
    }
    problems = []
    for label, (theme, block) in token_blocks(css).items():
        for name, value in re.findall(r"--([\w-]+)\s*:\s*([^;{}]+);", block):
            value = value.strip()
            if not is_color_value(value):
                continue
            if not HEX_COLOR.fullmatch(value):
                problems.append(f"{label}: --{name} is a color but not a six-digit hex: {value}")
                continue
            source_file, token = RENAMED_SOURCE_TOKENS.get(name, ("tokens.json", name))
            expected = sources[source_file].get(token)
            if expected is None:
                problems.append(f"{label}: --{name} has no source ({source_file} {token})")
            elif value.lower() != expected[theme].lower():
                problems.append(
                    f"{label}: --{name} is {value}; "
                    f"{source_file} {token} {theme} is {expected[theme]}"
                )
    return problems


def test_every_css_color_token_matches_its_design_source() -> None:
    """R12: site.css color tokens match docs/design/tokens.json in light and dark."""
    css = CSS_PATH.read_text(encoding="utf-8")
    assert len(token_blocks(css)) == 4
    assert color_token_problems(css) == []


def test_tokens_json_has_the_recorded_hash() -> None:
    """R12: tokens.json matches the hash recorded in docs/design.md."""
    design = (ROOT / "docs/design.md").read_text(encoding="utf-8")
    recorded = re.search(r"tokens\.json`[^\n]*?SHA-256 `([0-9a-f]{64})`", design)
    assert recorded, "docs/design.md records no SHA-256 for tokens.json"
    actual = hashlib.sha256((DESIGN / "tokens.json").read_bytes()).hexdigest()
    assert actual == recorded.group(1)


def test_logos_match_the_site_images() -> None:
    """R12: the site logos are the hash-pinned design logos."""
    logos = {path.name for path in (DESIGN / "logos").iterdir()}
    images = {path.name for path in (ROOT / "assets/img").glob("*.svg")}
    assert images <= logos, (
        f"assets/img SVGs missing from docs/design/logos: {sorted(images - logos)}"
    )
    for name in sorted(logos):
        assert name in images, f"docs/design/logos/{name} is not in assets/img"
        assert (DESIGN / "logos" / name).read_bytes() == (
            ROOT / "assets/img" / name
        ).read_bytes(), name


def png_problem(data: bytes) -> str | None:
    if not data.startswith(PNG_SIGNATURE):
        return "no PNG signature"
    cursor = len(PNG_SIGNATURE)
    first = True
    while cursor + 12 <= len(data):
        length, kind = struct.unpack(">I4s", data[cursor : cursor + 8])
        body = data[cursor + 8 : cursor + 8 + length]
        crc = data[cursor + 8 + length : cursor + 12 + length]
        if len(body) != length or len(crc) != 4:
            return "truncated chunk"
        if struct.unpack(">I", crc)[0] != zlib.crc32(kind + body):
            return f"bad CRC in {kind.decode('ascii', 'replace')}"
        if first:
            if kind != b"IHDR" or length != 13 or 0 in struct.unpack(">II", body[:8]):
                return "bad IHDR"
            first = False
        if kind == b"IEND":
            return None
        cursor += 12 + length
    return "no IEND"


def test_design_screens_are_the_expected_valid_pngs() -> None:
    screens = DESIGN / "screens"
    assert {path.name for path in screens.iterdir()} == EXPECTED_SCREENS
    for name in sorted(EXPECTED_SCREENS):
        assert png_problem((screens / name).read_bytes()) is None, name


def card_class(html: str, project: str) -> str:
    for classes, body in re.findall(
        r'<article class="([^"]*project-card[^"]*)">(.*?)</article>', html, re.DOTALL
    ):
        if f"<h3>{project}</h3>" in body:
            return next(name for name in classes.split() if name.startswith("project-card--"))
    raise AssertionError(f"no project card for {project}")


def test_register_and_dossier_cards_edge_in_primary_and_dnx_accent() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    for project, token in (("Bearing Register", "primary"), ("DossierNexus", "dnx-accent")):
        modifier = card_class(html, project)
        rule = re.search(rf"\.{re.escape(modifier)}\s*\{{([^}}]*)\}}", css)
        assert rule, f".{modifier} has no rule"
        assert re.search(rf"--card-accent:\s*var\(--{token}\)\s*;", rule.group(1)), (
            f"{project} card is not edged in var(--{token})"
        )
        for label, (_, block) in token_blocks(css).items():
            assert re.search(rf"--{token}:\s*#[0-9a-fA-F]+;", block), f"{label} has no --{token}"
