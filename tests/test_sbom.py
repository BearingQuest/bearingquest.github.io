"""R22: the build SBOM of the locked site group (CycloneDX 1.5) carries no dev-only package."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml
from _proc import run
from test_workflows import PAGES, ROOT, locked_version

UPLOAD = "actions/upload-artifact@cf430e030ddbb5b0abf93d22962f4752f3646cd9"


def normalize(requirement: str) -> str:
    name = re.match(r"[A-Za-z0-9][A-Za-z0-9._-]*", requirement.strip())
    assert name, requirement
    return re.sub(r"[-_.]+", "-", name.group()).lower()


def group(name: str) -> set[str]:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return {normalize(r) for r in pyproject["dependency-groups"][name]}


def recipe(target: str) -> list[str]:
    """The command lines of one Makefile target."""
    text = (ROOT / "Makefile").read_text(encoding="utf-8")
    block = re.search(rf"^{target}:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert block, target
    return [line.strip() for line in block.group(1).splitlines()]


def sbom(tmp_path: Path) -> dict[str, Any]:
    out = tmp_path / "sbom-site.cdx.json"
    (command,) = [line for line in recipe("sbom") if line.startswith("uv export")]
    args = command.replace("_build/sbom-site.cdx.json", str(out)).split()
    run(args, cwd=ROOT, check=True, capture_output=True)
    return json.loads(out.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_sbom_is_cyclonedx_1_5_and_lists_pelican_at_the_locked_version(tmp_path: Path) -> None:
    data = sbom(tmp_path)
    assert data["bomFormat"] == "CycloneDX"
    assert data["specVersion"] == "1.5"
    versions = {normalize(c["name"]): c["version"] for c in data["components"]}
    assert versions["pelican"] == locked_version("pelican")


def test_sbom_has_no_package_from_the_dev_group(tmp_path: Path) -> None:
    """A package listed in the dev group must not reach the SBOM, even through the site group."""
    dev = group("dev")
    assert "defusedxml" in dev  # the list comes from pyproject.toml, not from here
    names = {normalize(c["name"]) for c in sbom(tmp_path)["components"]}
    assert not names & dev
    assert group("site") <= names


def test_pages_build_runs_the_makefile_sbom_command_and_uploads_it_for_90_days() -> None:
    build = yaml.safe_load(PAGES.read_text(encoding="utf-8"))["jobs"]["build"]
    step_runs = [s["run"] for s in build["steps"] if "run" in s]
    assert [line.strip() for line in step_runs[1].splitlines()] == recipe("sbom")
    (upload,) = [s for s in build["steps"] if s.get("uses", "").startswith(UPLOAD)]
    assert upload["with"]["name"] == "sbom-site"
    assert upload["with"]["retention-days"] == 90
    assert upload["with"]["path"] == "_build/sbom-site.cdx.json"
    order = [s for s in build["steps"] if "run" in s or "uses" in s]
    assert order.index(upload) > order.index(next(s for s in order if "run" in s))
