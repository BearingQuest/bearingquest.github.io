"""R17-R21: the blog index, the post pages, their images and the Atom feed.

Every check runs against the built site (tests/_site.py), so it sees what deploys.
"""

from __future__ import annotations

import re
import tomllib
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from _site import built_site
from defusedxml import ElementTree

ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "content/blog"
IMAGES_DIR = ROOT / "assets/img/blog"
FEED_PREFIX = "https://bearingquest.com/blog/"
ATOM = "{http://www.w3.org/2005/Atom}"
MAX_RASTER_BYTES = 400 * 1024


def read_post(path: Path) -> dict[str, str]:
    """The metadata block (up to the first blank line) and the body of a post."""
    head, _, body = path.read_text(encoding="utf-8").partition("\n\n")
    post = {"body": body}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        post[key.strip().lower()] = value.strip()
    return post


def posts() -> list[dict[str, str]]:
    found = [read_post(path) for path in sorted(POSTS_DIR.glob("*.md"))]
    assert found, "content/blog has no posts"
    return found


def blog_dir() -> Path:
    return built_site() / "blog"


def post_pages() -> list[Path]:
    return sorted(path for path in blog_dir().glob("*.html") if path.name != "index.html")


class Elements(HTMLParser):
    """Start tags with their attributes, plus each img's enclosing figcaption text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self.images: list[tuple[dict[str, str | None], str]] = []
        self._figure_images: list[dict[str, str | None]] = []
        self._caption: str | None = None
        self._in_figure = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        self.tags.append((tag, attributes))
        if tag == "figure":
            self._in_figure, self._figure_images = True, []
        elif tag == "img" and self._in_figure:
            self._figure_images.append(attributes)
        elif tag == "img":
            self.images.append((attributes, ""))
        elif tag == "figcaption":
            self._caption = ""

    def handle_data(self, data: str) -> None:
        if self._caption is not None:
            self._caption += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "figcaption":
            for attributes in self._figure_images:
                self.images.append((attributes, self._caption or ""))
            self._figure_images, self._caption = [], None
        elif tag == "figure":
            for attributes in self._figure_images:
                self.images.append((attributes, ""))
            self._in_figure, self._figure_images = False, []


def parse(path: Path) -> Elements:
    parser = Elements()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def visible_text(path: Path) -> str:
    class Text(HTMLParser):
        def __init__(self) -> None:
            super().__init__(convert_charrefs=True)
            self.parts: list[str] = []

        def handle_data(self, data: str) -> None:
            self.parts.append(data)

    text = Text()
    text.feed(path.read_text(encoding="utf-8"))
    # Joined without a separator: an inline tag (code, strong) adds no space of its own,
    # and the newlines between blocks are already in the text nodes.
    return re.sub(r"\s+", " ", "".join(text.parts))


def test_blog_images_have_alt_text_and_same_origin_sources() -> None:
    """R19: every img on a blog page has non-empty alt and a src under /assets/img/."""
    pages = [blog_dir() / "index.html", *post_pages()]
    assert len(pages) >= 2
    for page in pages:
        for tag, attrs in parse(page).tags:
            if tag != "img" or attrs.get("role") == "presentation":
                continue
            assert (attrs.get("alt") or "").strip(), f"{page.name}: img without alt: {attrs}"
            src = attrs.get("src") or ""
            assert src.startswith("/assets/img/"), f"{page.name}: img src outside assets/img: {src}"
            assert (built_site() / src.lstrip("/")).is_file(), f"{page.name}: {src} is missing"


def test_raster_images_are_small_jpeg_or_png_with_dimensions() -> None:
    """R19: a raster image is a JPEG or PNG of 400 KB or less, with width and height set."""
    rasters = [p for p in IMAGES_DIR.iterdir() if p.suffix.lower() != ".svg"]
    assert rasters, "no raster image to check"
    for path in rasters:
        data = path.read_bytes()
        assert data.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")), (
            f"{path.name}: not JPEG/PNG"
        )
        assert len(data) <= MAX_RASTER_BYTES, f"{path.name}: {len(data)} bytes"
    used = set()
    for page in post_pages():
        for attrs, _ in parse(page).images:
            src = attrs.get("src") or ""
            if Path(src).suffix.lower() not in {".svg", ""}:
                used.add(Path(src).name)
                for dimension in ("width", "height"):
                    assert (attrs.get(dimension) or "").isdigit(), f"{src}: no {dimension}"
    assert used == {path.name for path in rasters}, (
        "a raster is unused, or one is not in assets/img/blog"
    )


def test_ai_generated_images_have_a_caption_naming_the_tool() -> None:
    """R19: an image whose file name contains "hero" has a visible figcaption naming Gemini."""
    seen = 0
    for page in post_pages():
        for attrs, caption in parse(page).images:
            if "hero" in Path(attrs.get("src") or "").name.lower():
                seen += 1
                assert "gemini" in caption.lower(), f"{page.name}: hero image caption: {caption!r}"
    assert seen


def test_built_blog_has_only_the_index_the_posts_and_the_feed() -> None:
    """R20: no author, category, tag, archive or other output."""
    expected = {"index.html", "feed.xml", *(f"{post['slug']}.html" for post in posts())}
    found = {path.relative_to(blog_dir()).as_posix() for path in blog_dir().rglob("*")}
    assert found == expected


# The page parts that must match about.html: the head, the skip link and header, the footer.
def page_parts(path: Path) -> dict[str, str]:
    html = path.read_text(encoding="utf-8")
    url = "/" + path.relative_to(built_site()).as_posix()

    def absolute(match: re.Match[str]) -> str:
        target = match.group(2)
        if urlsplit(target).scheme or target.startswith("#"):
            return match.group(0)
        return f'{match.group(1)}="{urljoin(url, target)}"'

    html = re.sub(r'\b(href|src)="([^"]*)"', absolute, html).replace(' aria-current="page"', "")
    head = re.search(r"<head>.*?</head>", html, re.DOTALL)
    top = re.search(r"<body>.*?</header>", html, re.DOTALL)
    foot = re.search(r"<footer.*?</footer>", html, re.DOTALL)
    assert head and top and foot, path
    return {"head": head.group(0), "top": top.group(0), "footer": foot.group(0)}


FEED_LINK = re.compile(
    r'\n *<link rel="alternate" type="application/atom\+xml" title="Bearing Quest blog" '
    r'href="/blog/feed\.xml">'
)
PAGE_SPECIFIC = (
    re.compile(r"\n *<title>.*?</title>"),
    re.compile(r'\n *<meta name="description" content="[^"]*">'),
)


def test_blog_pages_match_about_in_head_navigation_and_footer() -> None:
    """R20: same CSP, head, skip link, header, navigation and footer as about.html, apart
    from aria-current, the title, the description and the one feed link."""
    about = page_parts(built_site() / "about.html")
    for pattern in PAGE_SPECIFIC:
        assert pattern.search(about["head"])
    about_head = about["head"]
    for pattern in PAGE_SPECIFIC:
        about_head = pattern.sub("", about_head)
    assert not FEED_LINK.search(about_head)
    for page in [blog_dir() / "index.html", *post_pages()]:
        parts = page_parts(page)
        assert len(FEED_LINK.findall(parts["head"])) == 1, f"{page.name}: feed link"
        head = FEED_LINK.sub("", parts["head"])
        for pattern in PAGE_SPECIFIC:
            assert pattern.search(head), f"{page.name}: {pattern.pattern}"
            head = pattern.sub("", head)
        assert head == about_head, f"{page.name}: head differs from about.html"
        assert parts["top"] == about["top"], f"{page.name}: header or navigation differs"
        assert parts["footer"] == about["footer"], f"{page.name}: footer differs"
        assert '<a href="/blog/" aria-current="page">' not in parts["top"]
        raw = page.read_text(encoding="utf-8")
        assert raw.count('aria-current="page"') == 1
        assert re.search(r'<a href="/blog/" aria-current="page">Blog</a>', raw), page.name


def test_uv_lock_and_pyproject_pin_pelican_4_12_0() -> None:
    """R20: Pelican is pinned in pyproject.toml and locked at 4.12.0 in uv.lock."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    versions = {pkg["name"]: pkg["version"] for pkg in lock["package"]}
    assert versions["pelican"] == "4.12.0"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "pelican==4.12.0" in project["dependency-groups"]["site"]
    assert "site" in project["tool"]["uv"]["default-groups"]


def test_uv_lock_keeps_pygments_at_2_20_or_newer() -> None:
    """R20: pygments is locked at 2.20.0 or newer, which fixes PYSEC-2026-2987 (CVE-2026-4539,
    a ReDoS in the ADL lexer). Pelican 4.12.0 caps pygments below 2.20, so pyproject.toml's
    [tool.uv] override-dependencies must stay until a Pelican release lifts the cap."""
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    version = next(pkg["version"] for pkg in lock["package"] if pkg["name"] == "pygments")
    major, minor = (int(part) for part in version.split(".")[:2])
    assert (major, minor) >= (2, 20), f"pygments {version} has PYSEC-2026-2987"
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    overrides = project["tool"]["uv"].get("override-dependencies", [])
    assert "pygments>=2.20.0" in overrides, "the pygments override is gone from pyproject.toml"


def test_index_lists_every_post_newest_first_and_every_page_is_listed() -> None:
    """R17: each post is on the index with title, date and summary, newest first, and
    each built post page is listed; the Blogger posts follow."""
    index = blog_dir() / "index.html"
    html = index.read_text(encoding="utf-8")
    listed = re.findall(r'<h3><a href="/blog/([^"]+)">', html)
    ordered = sorted(posts(), key=lambda post: post["date"], reverse=True)
    assert listed == [f"{post['slug']}.html" for post in ordered]
    assert sorted(listed) == [page.name for page in post_pages()]
    text = visible_text(index)
    for post in ordered:
        assert post["title"] in text
        assert post["summary"] in text
        assert re.search(rf'<time datetime="{post["date"]}"', html)
    assert html.index("Earlier posts (on Blogger)") > html.rindex("<h3>")
    blogger = [
        href
        for href in re.findall(r'href="([^"]+)"', html)
        if "dustenharrison.blogspot.com" in href
    ]
    assert len(blogger) == 2


def paragraphs(body: str) -> list[str]:
    """The text blocks of a post body: paragraphs and list items, inline markup removed."""
    blocks = []
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block or block.startswith(("#", "<")):
            continue
        for item in re.split(r"\n(?=- |\d+\. )", block):
            item = re.sub(r"^(?:- |\d+\. )", "", item.strip())
            item = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", item)
            # Emphasis marks go; a * inside an inline code span is text and stays.
            spans = re.split(r"(`[^`]*`)", item)
            item = "".join(
                span.strip("`") if span.startswith("`") else span.replace("*", "") for span in spans
            )
            blocks.append(re.sub(r"\s+", " ", item))
    return blocks


def test_every_paragraph_of_each_post_is_in_its_built_page() -> None:
    """R18: the built post page shows each paragraph of the approved Markdown."""
    for post in posts():
        text = visible_text(blog_dir() / f"{post['slug']}.html")
        blocks = paragraphs(post["body"])
        assert len(blocks) > 10
        for block in blocks:
            assert block in text, f"{post['slug']}: missing from the page: {block[:80]}"
        assert re.sub(r"\s+", " ", post["title"]) in text


def test_feed_is_atom_with_absolute_blog_links() -> None:
    """R21: feed.xml is Atom, parsed with defusedxml (no entity expansion), and every link
    starts with https://bearingquest.com/blog/."""
    root = ElementTree.fromstring((blog_dir() / "feed.xml").read_bytes())
    assert root.tag == f"{ATOM}feed"
    links = [link.get("href", "") for link in root.iter(f"{ATOM}link")]
    assert links
    for href in links:
        assert href.startswith(FEED_PREFIX), href
    entries = root.findall(f"{ATOM}entry")
    assert len(entries) == len(posts())
    for entry in entries:
        assert entry.find(f"{ATOM}title") is not None
        assert entry.find(f"{ATOM}updated") is not None
        assert entry.find(f"{ATOM}id") is not None
