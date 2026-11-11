from __future__ import annotations

import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import yaml
from _proc import run

ROOT = Path(__file__).resolve().parents[1]
SITE_FILES = ROOT / "site-files.txt"
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
    "docs",
    "LICENSE",
    "Makefile",
    "README.md",
    "pyproject.toml",
    "site-files.txt",
    "tests",
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
    "docs",
    "pyproject.toml",
    "tests",
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
    pages = {path.name for path in ROOT.glob("*.html")}
    assert pages
    assert pages <= set(site_entries())


def test_every_root_entry_is_classified() -> None:
    root_entries = {PurePosixPath(name).parts[0] for name in tracked_files()}
    listed = {PurePosixPath(entry).parts[0] for entry in site_entries()}
    assert not listed & NOT_PUBLISHED
    unclassified = root_entries - listed - NOT_PUBLISHED
    assert not unclassified, f"add to site-files.txt or NOT_PUBLISHED: {sorted(unclassified)}"
    stale = NOT_PUBLISHED - root_entries
    assert not stale, f"NOT_PUBLISHED names untracked entries: {sorted(stale)}"


def test_repo_files_are_never_published() -> None:
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


def test_published_links_resolve_inside_the_published_set() -> None:
    published = published_files()
    pages = sorted(name for name in published if name.endswith(".html"))
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
    assert set(JOBS) == {"build", "deploy"}
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
    assert JOBS["deploy"]["permissions"] == {"pages": "write", "id-token": "write"}
    for grant in ("pages", "id-token"):
        assert re.search(rf"^\s+{grant}: write # \S", WORKFLOW_TEXT, re.MULTILINE), (
            f"{grant}: write has no comment"
        )


def test_deploys_are_serialized_and_never_cancelled() -> None:
    assert "concurrency" not in WORKFLOW
    assert JOBS["deploy"]["concurrency"] == {"group": "pages", "cancel-in-progress": False}
    assert JOBS["build"]["concurrency"]["group"] != "pages"


def test_build_copies_only_site_files_and_uploads_the_artifact() -> None:
    steps = JOBS["build"]["steps"]
    copy = [step for step in steps if "run" in step]
    assert len(copy) == 1
    assert "done < site-files.txt" in copy[0]["run"]
    assert "set -euo pipefail" in copy[0]["run"]
    upload = [
        step for step in steps if step.get("uses", "").startswith("actions/upload-pages-artifact@")
    ]
    assert len(upload) == 1
    assert upload[0]["with"] == {"path": "_site/"}
    deploy_uses = [step.get("uses", "") for step in JOBS["deploy"]["steps"]]
    assert len(deploy_uses) == 1
    assert deploy_uses[0].startswith("actions/deploy-pages@")


def test_jobs_are_pinned_timed_and_on_a_fixed_image() -> None:
    for name, job in JOBS.items():
        assert job["runs-on"] == "ubuntu-24.04", name
        assert 0 < job["timeout-minutes"] <= 5, name
        for step in job["steps"]:
            if step.get("uses", "").startswith("actions/checkout@"):
                assert step["with"]["persist-credentials"] is False, name
    uses_lines = re.findall(r"uses:\s*(\S+)(.*)", WORKFLOW_TEXT)
    assert len(uses_lines) == 3
    for action, comment in uses_lines:
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@[0-9a-f]{40}", action), action
        assert re.fullmatch(r"\s*# v\d+\.\d+\.\d+", comment), action
