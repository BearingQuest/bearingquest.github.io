from __future__ import annotations

import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import yaml
from _proc import run
from _site import built_site

ROOT = Path(__file__).resolve().parents[1]
SITE_FILES = ROOT / "site-files.txt"
BUILD_SCRIPT = ROOT / "scripts/build-site.sh"
WORKFLOW_PATH = ROOT / ".github/workflows/pages.yml"
WORKFLOW_TEXT = WORKFLOW_PATH.read_text(encoding="utf-8")
WORKFLOW = yaml.safe_load(WORKFLOW_TEXT)
# YAML 1.1 reads the bare key `on` as the boolean True.
TRIGGERS = WORKFLOW.get("on", WORKFLOW.get(True))
JOBS = WORKFLOW["jobs"]

# Tracked root entries that stay in the repo but are never published. A new
# root file or folder fails test_every_root_entry_is_classified until it is
# added here or to site-files.txt.
NOT_PUBLISHED = {
    ".claude",
    ".githooks",
    ".github",
    ".gitignore",
    ".nojekyll",
    ".python-version",
    "AGENTS.md",
    "CLAUDE.md",
    "CNAME",
    "content",
    "docs",
    "LICENSE",
    "Makefile",
    "README.md",
    "pelicanconf.py",
    "plugins",
    "pyproject.toml",
    "scripts",
    "site-files.txt",
    "tests",
    "theme",
    "uv.lock",
}
# Repo files that must never reach the site, whether or not they exist yet.
NEVER_PUBLISHED = {
    ".claude",
    ".githooks",
    ".github",
    "AGENTS.md",
    "CLAUDE.md",
    "Makefile",
    "README.md",
    "content",
    "docs",
    "pelicanconf.py",
    "pyproject.toml",
    "scripts",
    "tests",
    "theme",
    "uv.lock",
}


def site_entries() -> list[str]:
    entries = []
    for line in SITE_FILES.read_text(encoding="utf-8").splitlines():
        entry = line.split("#", 1)[0].strip()
        if entry:
            entries.append(entry)
    return entries


def tracked_files() -> list[str]:
    """Tracked files plus untracked ones that aren't ignored, so a new file is
    classified before it is committed."""
    result = run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    )
    return [name for name in result.stdout.decode("utf-8").split("\0") if name]


def published_files() -> set[str]:
    """The files the build job copies, minus hidden files, which
    upload-pages-artifact leaves out by default."""
    published = set()
    for entry in site_entries():
        entry = entry.rstrip("/")
        for name in tracked_files():
            if name != entry and not name.startswith(f"{entry}/"):
                continue
            if any(part.startswith(".") for part in PurePosixPath(name).parts):
                continue
            published.add(name)
    return published


def test_site_files_entries_are_safe_and_exist() -> None:
    """R2: site-files.txt lists only safe paths that exist."""
    entries = site_entries()
    assert entries
    assert len(entries) == len(set(entries)), "site-files.txt has duplicates"
    for entry in entries:
        parts = PurePosixPath(entry).parts
        assert not entry.startswith("/"), f"absolute path: {entry}"
        assert not any(part.startswith(".") for part in parts), f"hidden or '..' path: {entry}"
        target = ROOT / entry.rstrip("/")
        assert target.exists(), f"listed path is missing: {entry}"
        assert not target.is_symlink(), f"listed path is a symlink: {entry}"


def test_every_root_html_page_is_listed() -> None:
    """R2: every root HTML page is published."""
    pages = {path.name for path in ROOT.glob("*.html")}
    assert pages
    assert pages <= set(site_entries())


def test_every_root_entry_is_classified() -> None:
    """R2: every tracked root file is published or on the not-published list."""
    root_entries = {PurePosixPath(name).parts[0] for name in tracked_files()}
    listed = {PurePosixPath(entry).parts[0] for entry in site_entries()}
    assert not listed & NOT_PUBLISHED
    unclassified = root_entries - listed - NOT_PUBLISHED
    assert not unclassified, f"add to site-files.txt or NOT_PUBLISHED: {sorted(unclassified)}"
    stale = NOT_PUBLISHED - root_entries
    assert not stale, f"NOT_PUBLISHED names untracked entries: {sorted(stale)}"


def test_repo_files_are_never_published() -> None:
    """R2: repo files are never in the published set."""
    for entry in site_entries():
        assert PurePosixPath(entry).parts[0] not in NEVER_PUBLISHED, entry
    published = published_files()
    assert published
    for name in published:
        assert PurePosixPath(name).parts[0] not in NEVER_PUBLISHED, name
    assert "CNAME" not in published
    assert ".nojekyll" not in published


class LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"href", "src"} and value:
                self.links.append(value)


def resolve_local(source: str, link: str) -> str | None:
    """The published path a link points at, or None for external links."""
    if link.startswith(("#", "data:")):
        return None
    parsed = urlsplit(link)
    if parsed.scheme or parsed.netloc:
        return None
    target = unquote(parsed.path)
    if not target:
        return None
    if target.startswith("/"):
        resolved = posixpath.normpath(target.lstrip("/"))
    else:
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
    if target.endswith("/") or resolved == ".":
        resolved = posixpath.normpath(posixpath.join(resolved, "index.html"))
    return resolved


def blog_files() -> set[str]:
    """The files Pelican adds under blog/, taken from the built site."""
    site = built_site()
    return {
        path.relative_to(site).as_posix() for path in (site / "blog").rglob("*") if path.is_file()
    }


def test_published_links_resolve_inside_the_published_set() -> None:
    """R2, R9: the hand-written pages' links, blog/ included, resolve inside what deploys."""
    published = published_files() | blog_files()
    pages = sorted(name for name in published_files() if name.endswith(".html"))
    assert pages
    for page in pages:
        parser = LinkParser()
        parser.feed((ROOT / page).read_text(encoding="utf-8"))
        for link in parser.links:
            resolved = resolve_local(page, link)
            if resolved is not None:
                assert resolved in published, f"{page}: {link} is not published"

    for stylesheet in sorted(name for name in published if name.endswith(".css")):
        css = (ROOT / stylesheet).read_text(encoding="utf-8")
        for link in re.findall(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)", css):
            resolved = resolve_local(stylesheet, link)
            if resolved is not None:
                assert resolved in published, f"{stylesheet}: {link} is not published"


def test_workflow_triggers() -> None:
    assert set(TRIGGERS) == {"pull_request", "push", "workflow_dispatch"}
    assert TRIGGERS["push"] == {"branches": ["main"]}


def test_build_runs_everywhere_and_deploy_only_outside_pull_requests() -> None:
    assert set(JOBS) == {"build", "deploy", "smoke"}
    assert "if" not in JOBS["build"]
    assert JOBS["deploy"]["needs"] == "build"
    # The ref check stops a manual run on another branch from deploying, even
    # before the github-pages environment is limited to main.
    assert JOBS["deploy"]["if"] == (
        "github.event_name != 'pull_request' && github.ref == 'refs/heads/main'"
    )
    assert JOBS["deploy"]["environment"] == {
        "name": "github-pages",
        "url": "${{ steps.deployment.outputs.page_url }}",
    }


def test_only_the_deploy_job_has_write_permissions() -> None:
    assert WORKFLOW["permissions"] == {"contents": "read"}
    assert "permissions" not in JOBS["build"]
    # The smoke job inherits contents: read; it never sets its own grant.
    assert "permissions" not in JOBS["smoke"]
    assert JOBS["deploy"]["permissions"] == {"pages": "write", "id-token": "write"}
    for grant in ("pages", "id-token"):
        assert re.search(rf"^\s+{grant}: write # \S", WORKFLOW_TEXT, re.MULTILINE), (
            f"{grant}: write has no comment"
        )


def test_deploys_are_serialized_and_never_cancelled() -> None:
    assert "concurrency" not in WORKFLOW
    assert JOBS["deploy"]["concurrency"] == {"group": "pages", "cancel-in-progress": False}
    assert JOBS["build"]["concurrency"]["group"] != "pages"


def test_smoke_job_keeps_only_the_newest_check() -> None:
    # Only the newest deploy's smoke check matters, so a newer run cancels an older one.
    assert JOBS["smoke"]["concurrency"] == {"group": "pages-smoke", "cancel-in-progress": True}


def test_build_calls_the_copy_script_and_uploads_the_artifact() -> None:
    steps = JOBS["build"]["steps"]
    copy = [step for step in steps if "run" in step]
    assert len(copy) == 2  # the site build, then the SBOM (tests/test_sbom.py)
    assert copy[0]["run"].strip() == "bash scripts/build-site.sh _site"
    # The Pages build leaves the dev group (test tools) out of the blog build.
    assert copy[0]["env"] == {"BLOG_NO_DEV": "1"}
    upload = [
        step for step in steps if step.get("uses", "").startswith("actions/upload-pages-artifact@")
    ]
    assert len(upload) == 1
    assert upload[0]["with"] == {"path": "_site/"}
    deploy_uses = [step.get("uses", "") for step in JOBS["deploy"]["steps"]]
    assert len(deploy_uses) == 1
    assert deploy_uses[0].startswith("actions/deploy-pages@")


def test_build_script_reads_only_site_files_and_fails_closed() -> None:
    text = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/bin/bash\n")
    assert "set -euo pipefail" in text
    assert "done < site-files.txt" in text
    # One copy for the site-files.txt paths, one for the Pelican blog output.
    assert text.count("cp -R") == 2
    assert 'cp -R _build/blog "$out/blog"' in text
    # Rejects absolute and hidden paths, missing paths and symlinks.
    for guard in ("/* | .* | */.*)", '[ -L "$path" ] || [ ! -e "$path" ]', 'find "$out" -type l'):
        assert guard in text, guard


BLOG_SCRIPT = ROOT / "scripts/build-blog.sh"


def test_blog_build_script_follows_repo_06_and_is_run_through_its_shebang() -> None:
    """R20, REPO-06: build-blog.sh is portable bash, runs the locked Pelican and fails on
    any warning."""
    text = BLOG_SCRIPT.read_text(encoding="utf-8")
    assert text.startswith("#!/usr/bin/env bash\n")
    assert "set -euo pipefail" in text
    assert BLOG_SCRIPT.stat().st_mode & 0o111, "build-blog.sh is not executable"
    for bash4 in ("declare -A", "mapfile", "readarray", ",,}", "^^}", "|&", "&>>", ";&"):
        assert bash4 not in text, bash4
    assert 'uv run --locked "$@" pelican content -s pelicanconf.py' in text
    assert "--fatal warnings" in text
    site = BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "scripts/build-blog.sh --no-dev" in site and "scripts/build-blog.sh >&2" in site


def test_build_script_output_is_the_published_set_and_no_repo_files(tmp_path: Path) -> None:
    """R2: the build output is exactly the published set."""
    out = tmp_path / "site"
    run(["bash", str(BUILD_SCRIPT), str(out)], cwd=tmp_path, check=True, capture_output=True)
    built = {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()}
    blog = blog_files()
    assert built - {name for name in built if name.startswith("blog/")} == published_files()
    assert {name for name in built if name.startswith("blog/")} == blog
    assert "blog/index.html" in blog and "blog/feed.xml" in blog
    for name in built:
        assert PurePosixPath(name).parts[0] not in NEVER_PUBLISHED | {"CNAME", ".nojekyll"}, name
    # An existing output directory is an error, as the old inline `mkdir _site` was.
    again = run(["bash", str(BUILD_SCRIPT), str(out)], cwd=tmp_path, capture_output=True)
    assert again.returncode != 0
    assert run(["bash", str(BUILD_SCRIPT)], cwd=tmp_path, capture_output=True).returncode == 2


def test_jobs_are_pinned_timed_and_on_a_fixed_image() -> None:
    for name, job in JOBS.items():
        assert job["runs-on"] == "ubuntu-24.04", name
        # The smoke job waits up to 3 minutes for propagation, so it gets 10.
        assert 0 < job["timeout-minutes"] <= (10 if name == "smoke" else 5), name
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False, name
    uses_lines = re.findall(r"uses:\s*(\S+)(.*)", WORKFLOW_TEXT)
    assert len(uses_lines) == 7  # build 4, deploy 1, smoke 2
    for action, comment in uses_lines:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), action
        assert re.fullmatch(r"\s*# v\d+\.\d+\.\d+", comment), action
