from __future__ import annotations

import hashlib
import math
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from _site import built_pages, built_site

ROOT = Path(__file__).resolve().parents[1]
# The built site, so the Pelican blog pages get the same checks as the hand-written ones.
HTML_FILES = built_pages()
# The exact tag, line break and indent included, as it appears in every page.
CSP = (
    '<meta http-equiv="Content-Security-Policy"\n'
    "          content=\"default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'\">"
)
EXTERNAL_SCHEMES = {"http", "https"}


def page_id(path: Path) -> str:
    return path.relative_to(built_site()).as_posix()


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


@pytest.mark.parametrize("path", HTML_FILES, ids=page_id)
def test_exact_csp_meta_tag(path: Path) -> None:
    """R15: every page carries the exact Content-Security-Policy meta tag."""
    assert CSP in path.read_text(encoding="utf-8")


def test_external_urls_only_appear_in_anchor_hrefs() -> None:
    """R15: no third-party script, font or stylesheet URL; external URLs only in anchors."""
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


@pytest.mark.parametrize("path", HTML_FILES, ids=page_id)
def test_no_inline_script_or_style(path: Path) -> None:
    """R15: no inline script, style block or style attribute."""
    text = path.read_text(encoding="utf-8")
    parser = parse_html(path)
    assert not parser.inline_script_text
    assert "<style" not in text.lower()
    assert not re.search(r"\sstyle\s*=", text, re.IGNORECASE)


@pytest.mark.parametrize("path", HTML_FILES, ids=page_id)
def test_internal_links_and_assets_resolve(path: Path) -> None:
    """R3, R20: every local link and asset on every built page, blog pages included, resolves."""
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
            site = built_site()
            target = (
                site / target_path.lstrip("/")
                if target_path.startswith("/")
                else path.parent / target_path
            )
            if target.is_dir():
                target /= "index.html"
            assert target.is_file(), f"{path.name}: {tag}[{attribute}] does not resolve: {value}"


@pytest.mark.parametrize("path", HTML_FILES, ids=page_id)
def test_images_have_accessible_alt_text(path: Path) -> None:
    """R14: every image has alt text or a presentation role."""
    parser = parse_html(path)
    for tag, attrs in parser.start_tags:
        if tag != "img":
            continue
        assert "alt" in attrs, f"{path.name}: image is missing alt"
        assert attrs["alt"] or attrs.get("role") == "presentation"


@pytest.mark.parametrize("path", HTML_FILES, ids=page_id)
def test_one_h1_and_a_title(path: Path) -> None:
    """R14: one h1 per page."""
    parser = parse_html(path)
    tags = [tag for tag, _ in parser.start_tags]
    assert tags.count("h1") == 1
    assert tags.count("title") == 1


def test_no_phone_numbers_or_email_addresses_in_html() -> None:
    """R7: no phone number or email address on any page."""
    phone = re.compile(r"\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}")
    email = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
    for path in HTML_FILES:
        text = path.read_text(encoding="utf-8")
        assert not phone.search(text), f"{path.name}: phone number found"
        assert not email.search(text), f"{path.name}: email address found"


def test_bearing_quest_is_not_presented_as_an_organization() -> None:
    """R10: no page describes Bearing Quest as a company, firm, studio or employer."""
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
    """R14: text 4.5:1 and focus and control edges 3:1 in both themes."""
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
    """R12, R13: the light and dark token blocks define the same tokens."""
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
    """R3: 404.html links and styles work at any path depth."""
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
    """R14: the theme switch shows a visible focus ring."""
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
    "assets/img/blog/baseline-map.svg": (
        "60e72b17ab9b4e698bb26b2de17be4d4e68b46e6697381937d6fcf2804059089"
    ),
    "assets/img/blog/change-loop.svg": (
        "ecebb210e88817eed4e626d0fd3b36cb456143739ad544d63eba8ed114ae5b78"
    ),
    "assets/img/blog/failing-controls.svg": (
        "024bb329377190384fa21f416ad868e3213a3c2ffa0763036046b971bda4ea8d"
    ),
    "assets/img/blog/guardrail-layers.svg": (
        "63aa5ca3182421a9980c529625a1817cc61b0f281d7d39942fea4622121db6c4"
    ),
    "assets/img/blog/rollout-timeline.svg": (
        "3f163253e66a7c8dc4d014fa0efecb7fd1ea0abfc97dbc2b77a6e6b8dbcbb3db"
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
SVG_FILES = sorted((ROOT / "assets/img").glob("**/*.svg"))


def test_font_and_svg_hashes_are_pinned() -> None:
    """R12, R19: fonts, logo SVGs and blog SVGs match their pinned hashes."""
    present = {
        path.relative_to(ROOT).as_posix()
        for pattern in ("assets/fonts/*.woff2", "assets/fonts/OFL-*.txt", "assets/img/**/*.svg")
        for path in ROOT.glob(pattern)
    }
    assert present == set(EXPECTED_ASSET_HASHES)
    for name, expected in EXPECTED_ASSET_HASHES.items():
        actual = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        assert actual == expected, f"{name}: SHA-256 {actual} is not pinned"


@pytest.mark.parametrize("path", SVG_FILES, ids=lambda path: path.name)
def test_svg_has_no_active_content(path: Path) -> None:
    """R12, R15, R19: the logo and blog SVGs carry no script, event handler or foreignObject."""
    text = path.read_text(encoding="utf-8")
    assert not re.search(r"<script", text, re.IGNORECASE)
    assert not re.search(r"\son[a-z]+\s*=", text, re.IGNORECASE)
    assert not re.search(r"<foreignObject", text, re.IGNORECASE)
    for match in re.finditer(r"\s(?:xlink:)?href\s*=\s*(['\"])(.*?)\1", text, re.IGNORECASE):
        assert re.fullmatch(r"#[\w.-]+", match.group(2)), (
            f"{path.name}: href is not a fragment: {match.group(2)}"
        )


def test_font_faces_resolve_and_have_licenses() -> None:
    """R12: fonts are self-hosted with their OFL licences."""
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
    """R12, R13: the logo variant follows the theme."""
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


# --- Approved site copy ---------------------------------------------------------------------
# The resume lines below are copied from the approved content file. They cover every figure,
# so a later edit that changes a number fails test_resume_keeps_the_approved_lines.


class TextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def visible_text(path: Path) -> str:
    parser = TextParser()
    parser.feed(path.read_text(encoding="utf-8"))
    return re.sub(r"\s+", " ", " ".join(parser.parts))


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text)


RESUME_LINES = (
    "Dusten Harrison, CISSP",
    (
        "Senior Engineering Manager \u00b7 SRE \u00b7 Platform Engineering \u00b7 "
        "Cloud Infrastructure \u00b7 DevOps \u00b7 Cybersecurity"
    ),
    (
        "Engineering leader with 20+ years across site reliability, platform "
        "engineering, cloud infrastructure, DevOps and cybersecurity. Has run "
        "distributed teams remotely for most of that career, owned a ~$3M annual SRE "
        "and platform budget, and paired cost discipline with architecture and "
        "executive communication. Works as an AI-augmented practitioner: Python "
        "(AI-assisted) and career-long Linux and Bash."
    ),
    "Drove a 90% reduction in out-of-SLA critical vulnerabilities within 30 days.",
    (
        "Partnered with Risk and GRC so an IL4 environment met its compliance "
        "requirements, including input to POA&M data."
    ),
    ("Initiated NIST CSF 2.0 scanning across the estate, alongside existing CIS scanning."),
    (
        "Owned reliability, platform and infrastructure for the Notary offering: five "
        "direct reports, a ~30-person partner development organization and a ~$3M "
        "annual budget."
    ),
    (
        "Cut the offering's monthly AWS cost 74% ($27K to ~$7K) while evaluating a "
        "multi-region high-availability architecture, with cost modeling presented to "
        "management."
    ),
    (
        "Cut weekly support load ~88% (~160 to ~20 hours) through automation and "
        "operational redesign."
    ),
    (
        "Drove a 600-item vulnerability backlog to zero over six months, across "
        "application code and the infrastructure the team owned."
    ),
    "Remediated 800+ CIS misconfigurations to zero in two months.",
    (
        "Automated PCI quarterly business review reporting from ~8 hours to ~10 "
        "seconds using Google Gemini."
    ),
    (
        "Took on the Operations Center (US, then global; ~15,000 on-premises servers): "
        "cut weekly alert volume from ~15,000 to ~4,000, took asset-inventory coverage "
        "from ~60% to 100%, and restructured staffing to keep 24/7 coverage."
    ),
    (
        "Served as a volunteer Senior Incident Commander for Sev 0\u20132 incidents "
        "(2023\u20132024); lessons from a Sev 0 site failover drove disaster-recovery "
        "testing improvements adopted across all sites."
    ),
    (
        "Managed the SDET team for six months (May\u2013Nov 2022), a first-time scope, "
        "until SDETs moved into the engineering organization."
    ),
    (
        "Added contractor staffing in two new European countries to keep the "
        "Operations Center staffed 24/7."
    ),
    (
        "Took over a stalled asset-inventory deployment and brought it to 100% "
        "coverage of ~15,000 servers across 15 sites, supplying the accurate inventory "
        "that PCI DSS, FedRAMP, IL4 and StateRAMP compliance required."
    ),
    (
        "Created 20+ AI-assisted Python scripts (GitHub Copilot) for PagerDuty "
        "licensing and utilization visibility, multi-level escalation resilience and "
        "cost-to-serve reporting."
    ),
    "Grew an inherited team of two to 12 across the US and UK.",
    (
        "Delivered ~$500K in annual savings from the AWS migrations, mainly by moving "
        "Jira and Confluence off third-party managed hosting."
    ),
    "Maintained PCI and SOC 2 compliance across all managed systems.",
    (
        "Led a 15-person team of Technical Account Managers and L2/L3 support "
        "engineers serving enterprise accounts."
    ),
    (
        "Resolved an at-scale customer escalation (3,000+ servers) and negotiated a "
        "license-compliance expansion after a 10x under-licensing gap was found, "
        "retaining the account."
    ),
    "Designed a mini-TAM program as a career-growth track for L2 engineers.",
    (
        "Led a four-architect team; generated $3.6M+ in annual cost savings by "
        "restructuring and decommissioning redundant infrastructure."
    ),
    ("Maintained zero unplanned downtime while serving 50+ enterprise SAP Cloud clients."),
    (
        "Delivered $1M+ in annual operational savings; managed the Jenkins team and "
        "CI/CD pipelines; introduced Docker and SaltStack."
    ),
    (
        "Grew from a two-person launch team to lead a ~60-person global organization "
        "across the US, China, Costa Rica, India and Poland."
    ),
    (
        "Sustained 99.8\u2013100% monthly availability against a 99.5% SLO on HR and "
        "Finance & Accounting production systems."
    ),
    ("Led a migration to virtualized infrastructure generating $1M+ in annual cost efficiencies."),
    (
        "Delivered $500K+ in annual cost savings by creating an enterprise "
        "knowledge-management system."
    ),
    ("SAP Cloud Services: owned capacity forecasting for 50+ dedicated bare-metal SAP servers."),
    (
        "Global Process Services: met IBM's mandated 10% annual cost-reduction target "
        "every year from about 2010 to 2014; designed a cost-optimized disaster "
        "recovery architecture that ran on existing test infrastructure; led a "
        "site-to-site failover of an enterprise CRM platform during a major incident; "
        "became the organization's go-to ISO 27001 expert."
    ),
    (
        "Helpdesk Tools: led the consolidation of nine incident, problem and change "
        "tools onto IBM's platform (six completed before the client brought the work "
        "back in house); $70K in sustained annual savings from automation."
    ),
    (
        "Volunteer trainer (2014\u20132016): delivered IBM's company-wide New Hire "
        "Training about every two months, full-day sessions for 30\u201360 attendees."
    ),
    (
        "IT leadership roles at JPMorgan Chase, including Vice President, IT "
        "Management: led a 16-person team across the US, UK and Singapore running the "
        "bank's nine incident, problem and change platforms and its helpdesk tooling; "
        "served on the team evaluating outsourcing proposals; ran the Houston data "
        "center (Windows NT, SQL Server, Tivoli); built a remote foreign-exchange "
        "trading solution for branches; started in IT operations supporting the "
        "trading floor and executive offices."
    ),
    (
        ") \u2014 Specified and directed a local-first career-management CLI: "
        "encrypted vault, pluggable LLM backends, a local model chosen by measured "
        "invented-fact rates, and a provenance-attested GitHub release; proof of "
        "concept."
    ),
    (
        ") \u2014 Specified and directed a content-curation tool with draft-only human "
        "review, acceptance tests frozen in CI and drafted by a second AI vendor, and "
        "required secret, static, and dependency scans."
    ),
    (
        ") \u2014 Specified and directed a hosted security risk-prioritization trainer "
        "and an MCP authoring server with no approval tool, keeping publication behind "
        "a human gate."
    ),
    (
        "Bearing Quest \u2014 Owner of this personal project family and the "
        "BearingQuest GitHub organization."
    ),
    (
        "CISSP (ISC2) \u00b7 ITIL v3 Foundation (EXIN) \u00b7 ICAgile Certified "
        "Professional \u2014 Foundations of DevOps \u00b7 PagerDuty Incident Responder"
    ),
)

INDEX_LINES = (
    "Open-source projects from Dusten Harrison: security training, risk management "
    "and career tools, built with AI under human review.",
    "Browser exercise that teaches security risk prioritization: five findings, "
    "limited fixes, a CISSP risk response for each.",
    "Open-source GRC-as-code risk register: risks as YAML in Git, rules enforced in CI.",
    "Local-first career-management CLI and desktop app that scores job descriptions "
    "against a career record.",
    "Draft-only tool that turns one recent source into X and LinkedIn posts, with "
    "human review before anything posts.",
    "Local desktop tool that turns your own writing into career claims, each tied to "
    "its source passage and approved one by one.",
)
ABOUT_LINES = (
    "Bearing Quest is my personal project family: a set of open-source tools, the "
    "BearingQuest GitHub organization, and this site. It isn't a business.",
    "I'm Dusten Harrison, CISSP, an engineering leader with 20+ years across site "
    "reliability, platform engineering, cloud infrastructure, DevOps and cybersecurity.",
    "The best way to reach me is LinkedIn.",
)
REPOS = "https://github.com/BearingQuest/"
EXPECTED_CARDS = (
    ("Risk Trainer", "Live", ["https://d13b88u8g6wpqx.cloudfront.net/", REPOS + "risk-trainer"]),
    ("Bearing Register", "In design", [REPOS + "risk-register"]),
    ("QuestVector", "Proof of concept", [REPOS + "questvector"]),
    ("QuestCast", "Personal use", [REPOS + "questcast"]),
    ("DossierNexus", "Planned", []),
)
LINKEDIN = "https://www.linkedin.com/in/dustenharrison"
X_PROFILE = "https://x.com/Dusten_atx"
BANNED_STRINGS = ("Director", "founder", "single pane of glass", "e-notarization")


class CardParser(HTMLParser):
    """Collects (title, badge, hrefs) for each article.project-card."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cards: list[tuple[str, str, list[str]]] = []
        self._in_card = False
        self._title = ""
        self._badge = ""
        self._hrefs: list[str] = []
        self._field: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "article" and "project-card" in (attributes.get("class") or "").split():
            self._in_card = True
            self._title, self._badge, self._hrefs = "", "", []
        elif self._in_card:
            if tag == "h3":
                self._field = "title"
            elif tag == "span" and attributes.get("class") == "badge":
                self._field = "badge"
            elif tag == "a" and attributes.get("href"):
                self._hrefs.append(attributes["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag in {"h3", "span"}:
            self._field = None
        elif tag == "article" and self._in_card:
            self.cards.append((self._title, self._badge, self._hrefs))
            self._in_card = False

    def handle_data(self, data: str) -> None:
        if self._field == "title":
            self._title += data
        elif self._field == "badge":
            self._badge += data


def test_no_todo_placeholders_in_published_pages() -> None:
    """R11: no content placeholder appears on a published page."""
    assert HTML_FILES
    for path in HTML_FILES:
        assert "[TODO" not in path.read_text(encoding="utf-8"), f"{path.name}: [TODO placeholder"


def test_every_page_footer_shows_2026() -> None:
    for path in HTML_FILES:
        assert "Site text © 2026 Dusten Harrison, all rights reserved." in visible_text(path)


def test_banned_strings_are_in_no_page() -> None:
    """R10: no avoid-list phrase appears on any page."""
    for path in HTML_FILES:
        text = path.read_text(encoding="utf-8").lower()
        for banned in BANNED_STRINGS:
            assert banned.lower() not in text, f"{path.name}: contains {banned!r}"


def test_resume_keeps_the_approved_lines() -> None:
    """R7, R11: every resume claim, figure and date matches the approved content."""
    text = visible_text(ROOT / "resume.html")
    for line in RESUME_LINES:
        assert normalize(line) in text, f"resume.html is missing: {line}"


def test_resume_has_the_sections_in_order_and_no_education() -> None:
    """R7: the resume has the approved sections in order."""
    html = (ROOT / "resume.html").read_text(encoding="utf-8")
    headings = re.findall(r"<h2[^>]*>(.*?)</h2>", html)
    assert headings == ["Summary", "Experience", "Projects", "Certifications"]
    assert "Last updated: 14 Nov 2026" in visible_text(ROOT / "resume.html")


def test_earlier_career_has_no_four_digit_year() -> None:
    html = (ROOT / "resume.html").read_text(encoding="utf-8")
    start = html.index("<h3>Earlier career</h3>")
    section = re.sub(r"<[^>]+>", " ", html[start : html.index("</div>", start)])
    assert "JPMorgan Chase" in section
    assert not re.search(r"\b\d{4}\b", section)


def test_every_details_has_a_summary_and_is_closed_by_default() -> None:
    """R7, R14: resume details sections are closed by default and have a summary."""
    total = 0
    for path in HTML_FILES:
        html = path.read_text(encoding="utf-8")
        opening = len(re.findall(r"<details\b", html))
        assert not re.search(r"<details\b[^>]*\bopen\b", html), f"{path.name}: details is open"
        assert len(re.findall(r"<details\b[^>]*>\s*<summary>", html)) == opening, path.name
        total += opening
    assert total == 5


def test_social_links_point_exactly_at_the_profiles() -> None:
    """R9, R11: LinkedIn and X links match the approved addresses.

    About and resume link to both.
    """
    allowed = {"linkedin.com": LINKEDIN, "x.com": X_PROFILE, "twitter.com": X_PROFILE}
    for path in HTML_FILES:
        for tag, attrs in parse_html(path).start_tags:
            href = attrs.get("href") or ""
            host = (urlsplit(href).hostname or "").removeprefix("www.")
            if tag == "a" and host in allowed:
                assert href == allowed[host], f"{path.name}: {href}"
    for name in ("about.html", "resume.html"):
        hrefs = [a.get("href") for tag, a in parse_html(ROOT / name).start_tags if tag == "a"]
        assert LINKEDIN in hrefs, name
        assert X_PROFILE in hrefs, name


def test_every_page_links_to_the_blog_the_organization_and_linkedin() -> None:
    """R9: every page, built blog pages included, links to /blog/, the GitHub organization
    and LinkedIn."""
    assert any(page_id(path).startswith("blog/") for path in HTML_FILES)
    for path in HTML_FILES:
        site = built_site()
        hrefs = set()
        for tag, attrs in parse_html(path).start_tags:
            href = attrs.get("href")
            if tag != "a" or not href:
                continue
            if urlsplit(href).scheme:
                hrefs.add(href)
            else:
                resolved = site / href.lstrip("/") if href.startswith("/") else path.parent / href
                hrefs.add(resolved.resolve().relative_to(site.resolve()).as_posix())
        page = page_id(path)
        assert "blog" in hrefs or "blog/index.html" in hrefs, f"{page}: no link to /blog/"
        assert "https://github.com/BearingQuest" in hrefs, f"{page}: no link to the GitHub org"
        assert LINKEDIN in hrefs, f"{page}: no link to LinkedIn"


def test_external_links_use_noopener_noreferrer() -> None:
    for path in HTML_FILES:
        for tag, attrs in parse_html(path).start_tags:
            href = attrs.get("href") or ""
            if tag == "a" and urlsplit(href).scheme in EXTERNAL_SCHEMES:
                assert attrs.get("rel") == "noopener noreferrer", f"{path.name}: {href}"


def test_index_cards_are_in_order_with_the_approved_links() -> None:
    """R4, R5: one card per project, in order, with its approved links."""
    parser = CardParser()
    parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))
    assert parser.cards == list(EXPECTED_CARDS)


def test_index_and_about_keep_the_approved_text() -> None:
    """R4, R6: the home and About text match the approved content."""
    for name, lines in (("index.html", INDEX_LINES), ("about.html", ABOUT_LINES)):
        text = visible_text(ROOT / name)
        for line in lines:
            assert normalize(line) in text, f"{name}: missing {line}"
