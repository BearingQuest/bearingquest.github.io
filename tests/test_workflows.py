"""Checks on every workflow and on the ruleset files that require its jobs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github/workflows"
RULESET_DIR = ROOT / ".github/rulesets"
CI = WORKFLOW_DIR / "ci.yml"
DAILY = WORKFLOW_DIR / "pip-audit-daily.yml"

REQUIRED_CHECKS = {"check", "gitleaks", "semgrep", "pip-audit", "zizmor"}
UPLOAD_JOBS = {"gitleaks", "semgrep"}
# The GitHub Actions app, which reports the required checks.
GITHUB_ACTIONS_APP_ID = 15368
FORK_GUARD = "github.event.pull_request.head.repo.fork != true"


def load(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def workflow_paths() -> list[Path]:
    paths = sorted(WORKFLOW_DIR.glob("*.yml"))
    assert paths
    return paths


def all_jobs() -> list[tuple[Path, str, dict[str, Any]]]:
    return [
        (path, name, job) for path in workflow_paths() for name, job in load(path)["jobs"].items()
    ]


def all_steps() -> list[tuple[Path, str, dict[str, Any]]]:
    return [(path, name, step) for path, name, job in all_jobs() for step in job["steps"]]


def test_ci_has_exactly_the_five_required_jobs() -> None:
    jobs = load(CI)["jobs"]
    assert set(jobs) == REQUIRED_CHECKS
    for key, job in jobs.items():
        assert job["name"] == key


def test_required_checks_in_main_ruleset_match_ci_jobs() -> None:
    ruleset = json.loads((RULESET_DIR / "main.json").read_text(encoding="utf-8"))
    rule = next(r for r in ruleset["rules"] if r["type"] == "required_status_checks")
    checks = rule["parameters"]["required_status_checks"]
    job_names = {job["name"] for job in load(CI)["jobs"].values()}
    contexts = [check["context"] for check in checks]
    assert len(contexts) == len(set(contexts))
    assert set(contexts) == REQUIRED_CHECKS
    assert set(contexts) <= job_names
    assert all(check["integration_id"] == GITHUB_ACTIONS_APP_ID for check in checks)


def test_rulesets_have_the_agreed_shape() -> None:
    main = json.loads((RULESET_DIR / "main.json").read_text(encoding="utf-8"))
    tags = json.loads((RULESET_DIR / "release-tags.json").read_text(encoding="utf-8"))
    assert (main["target"], main["enforcement"], main["bypass_actors"]) == ("branch", "active", [])
    assert main["conditions"]["ref_name"]["include"] == ["~DEFAULT_BRANCH"]
    assert [r["type"] for r in main["rules"]] == [
        "deletion",
        "non_fast_forward",
        "required_linear_history",
        "pull_request",
        "required_status_checks",
        "code_scanning",
    ]
    assert (tags["target"], tags["enforcement"], tags["bypass_actors"]) == ("tag", "active", [])
    assert tags["conditions"]["ref_name"]["include"] == ["refs/tags/v*"]
    assert [r["type"] for r in tags["rules"]] == ["deletion", "non_fast_forward", "update"]


def test_every_uses_is_a_full_commit_sha_with_a_version_comment() -> None:
    count = 0
    for path in workflow_paths():
        text = path.read_text(encoding="utf-8")
        for action, comment in re.findall(r"^\s*(?:- )?uses:\s*(\S+)(.*)$", text, re.MULTILINE):
            count += 1
            assert re.fullmatch(r"[\w.-]+/[\w.-]+(/[\w./-]+)?@[0-9a-f]{40}", action), (
                path.name,
                action,
            )
            assert re.fullmatch(r"\s*# v\d+\.\d+\.\d+", comment), (path.name, action)
    assert count == sum("uses" in step for _, _, step in all_steps())


def test_every_job_has_a_pinned_image_and_a_timeout() -> None:
    for path, name, job in all_jobs():
        assert job["runs-on"] == "ubuntu-24.04", (path.name, name)
        assert isinstance(job.get("timeout-minutes"), int), (path.name, name)
        assert 0 < job["timeout-minutes"] <= 10, (path.name, name)


def test_every_checkout_sets_persist_credentials_false() -> None:
    checkouts = [
        (path, name, step)
        for path, name, step in all_steps()
        if step.get("uses", "").startswith("actions/checkout@")
    ]
    assert checkouts
    for path, name, step in checkouts:
        assert step.get("with", {}).get("persist-credentials") is False, (path.name, name)


def test_only_the_sarif_jobs_can_write_security_events_each_with_a_comment() -> None:
    ci_text = CI.read_text(encoding="utf-8")
    for path, name, job in all_jobs():
        granted = job.get("permissions", {}).get("security-events")
        if path == CI and name in UPLOAD_JOBS:
            assert granted == "write", name
        else:
            assert granted is None, (path.name, name)
    assert load(CI)["permissions"] == {"contents": "read"}
    comments = re.findall(r"^\s+security-events: write # \S.*$", ci_text, re.MULTILINE)
    assert len(comments) == len(UPLOAD_JOBS)


def test_sarif_uploads_skip_fork_pull_requests_and_run_after_a_failed_scan() -> None:
    jobs = load(CI)["jobs"]
    uploads = [
        (name, step)
        for name, job in jobs.items()
        for step in job["steps"]
        if step.get("uses", "").startswith("github/codeql-action/upload-sarif@")
    ]
    assert {name for name, _ in uploads} == UPLOAD_JOBS
    for name, step in uploads:
        assert step["if"] == f"always() && {FORK_GUARD}", name
        assert step["with"]["category"] == name


def test_semgrep_is_pinned_registry_only_and_filters_suppressed_results() -> None:
    steps = load(CI)["jobs"]["semgrep"]["steps"]
    scan = next(step for step in steps if step.get("name") == "Scan")["run"]
    assert re.search(r"uvx --exclude-newer \d{4}-\d{2}-\d{2} semgrep@\d+\.\d+\.\d+ scan", scan)
    for pack in ("p/default", "p/python", "p/github-actions"):
        assert f"--config {pack}" in scan
    assert "--metrics off" in scan
    assert "--error" not in scan
    assert "semgrep/semgrep-action" not in CI.read_text(encoding="utf-8")
    names = [step.get("name") for step in steps]
    assert names.index("Scan") < names.index("Drop results suppressed in source")
    assert names.index("Drop results suppressed in source") < names.index(
        "Upload SARIF to code scanning"
    )
    assert names.index("Upload SARIF to code scanning") < names.index("Fail on findings")


def test_zizmor_is_pinned_and_read_only() -> None:
    job = load(CI)["jobs"]["zizmor"]
    assert job["permissions"] == {"contents": "read"}
    run = next(step["run"] for step in job["steps"] if "run" in step)
    assert re.fullmatch(
        r"uvx --exclude-newer \d{4}-\d{2}-\d{2} zizmor@\d+\.\d+\.\d+ \.github", run.strip()
    )


def test_check_runs_make_check_after_a_locked_sync() -> None:
    runs = [step["run"].strip() for step in load(CI)["jobs"]["check"]["steps"] if "run" in step]
    assert runs == ["uv sync --locked", "make check"]


def test_pip_audit_daily_limits_concurrency() -> None:
    assert load(DAILY)["concurrency"] == {
        "group": "pip-audit-daily",
        "cancel-in-progress": False,
    }


def test_gitleaks_gate_fails_closed() -> None:
    steps = load(CI)["jobs"]["gitleaks"]["steps"]
    scan = next(step for step in steps if step.get("id") == "scan")
    assert scan["continue-on-error"] is True
    final = steps[-1]
    assert final["name"] == "Fail on findings"
    # Runs after a failed scan and judges the scan outcome and the report together.
    assert final["if"] == "always()"
    assert final["env"] == {"SCAN_OUTCOME": "${{ steps.scan.outcome }}"}
    assert 'outcome != "success"' in final["run"]
    names = [step.get("name") for step in steps]
    assert names.index("Upload SARIF to code scanning") < len(steps) - 1
