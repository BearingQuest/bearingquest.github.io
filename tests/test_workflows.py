"""Checks on every workflow and on the ruleset files that require its jobs."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github/workflows"
RULESET_DIR = ROOT / ".github/rulesets"
CI = WORKFLOW_DIR / "ci.yml"
DAILY = WORKFLOW_DIR / "pip-audit-daily.yml"
SCORECARD = WORKFLOW_DIR / "scorecard.yml"
REVIEW = WORKFLOW_DIR / "claude-review.yml"

REQUIRED_CHECKS = {"check", "gitleaks", "semgrep", "pip-audit", "zizmor", "e2e"}
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


def test_ci_has_exactly_the_six_required_jobs() -> None:
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
    # A branch must be up to date with main before it merges (baseline change, 11 Nov).
    assert rule["parameters"]["strict_required_status_checks_policy"] is True


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
    for path, name, job in all_jobs():
        granted = job.get("permissions", {}).get("security-events")
        if (path == CI and name in UPLOAD_JOBS) or (path == SCORECARD and name == "analysis"):
            assert granted == "write", name
        else:
            assert granted is None, (path.name, name)
    assert load(CI)["permissions"] == {"contents": "read"}
    comments = 0
    for path in (CI, SCORECARD):
        text = path.read_text(encoding="utf-8")
        comments += len(re.findall(r"^\s+security-events: write # \S.*$", text, re.MULTILINE))
    assert comments == len(UPLOAD_JOBS) + 1


def test_job_permissions_each_have_a_comment_and_never_repeat_the_workflow_grant() -> None:
    for path in workflow_paths():
        workflow = load(path)
        for name, job in workflow["jobs"].items():
            if "permissions" in job:
                assert job["permissions"] != workflow.get("permissions"), (path.name, name)
        grants = re.findall(
            r"^ {6}[a-z-]+: (?:read|write|none)(?: #.*)?$",
            path.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        for grant in grants:
            assert re.search(r" # \S", grant), (path.name, grant.strip())


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
    assert "permissions" not in job  # inherits the workflow's contents: read
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


def on_block(path: Path) -> dict[str, Any]:
    # YAML 1.1 reads the key `on` as the boolean True.
    workflow = load(path)
    return workflow.get("on", workflow.get(True))


def only_job(path: Path) -> dict[str, Any]:
    jobs = load(path)["jobs"]
    assert len(jobs) == 1
    return next(iter(jobs.values()))


def test_scorecard_triggers_are_schedule_and_push_to_main_only() -> None:
    triggers = on_block(SCORECARD)
    assert set(triggers) == {"schedule", "push"}
    assert triggers["push"] == {"branches": ["main"]}
    crons = [entry["cron"] for entry in triggers["schedule"]]
    assert len(crons) == 1
    minute, _hour, _dom, _month, weekday = crons[0].split()
    assert minute.isdigit() and minute not in {"0", "00"}  # off the hour
    assert weekday.isdigit()  # weekly


def test_scorecard_follows_the_publishing_restrictions() -> None:
    workflow = load(SCORECARD)
    assert workflow["permissions"] == {}
    assert "env" not in workflow and "defaults" not in workflow
    # Not among the restrictions, which cover env, defaults and write permissions.
    assert load(SCORECARD)["concurrency"] == {
        "group": "scorecard-${{ github.ref }}",
        "cancel-in-progress": True,
    }
    job = only_job(SCORECARD)
    assert "env" not in job and "defaults" not in job
    assert "container" not in job and "services" not in job
    assert job["permissions"] == {
        "security-events": "write",
        "id-token": "write",
        "contents": "read",
        "actions": "read",
    }
    text = SCORECARD.read_text(encoding="utf-8")
    for permission in ("security-events: write", "id-token: write", "contents: read"):
        assert re.search(rf"^\s+{permission} # \S", text, re.MULTILINE), permission
    assert re.search(r"^\s+actions: read # \S", text, re.MULTILINE)
    approved = (
        "actions/checkout@",
        "actions/upload-artifact@",
        "github/codeql-action/upload-sarif@",
        "ossf/scorecard-action@",
        "step-security/harden-runner@",
    )
    for step in job["steps"]:
        assert "run" not in step
        assert step["uses"].startswith(approved), step["uses"]


def test_scorecard_publishes_sarif_to_code_scanning() -> None:
    steps = only_job(SCORECARD)["steps"]
    scorecard = next(s for s in steps if s["uses"].startswith("ossf/scorecard-action@"))
    assert scorecard["with"]["publish_results"] is True
    assert scorecard["with"]["results_format"] == "sarif"
    upload = next(s for s in steps if s["uses"].startswith("github/codeql-action/upload-sarif@"))
    assert upload["with"]["sarif_file"] == scorecard["with"]["results_file"]
    ci_upload = next(
        step["uses"]
        for job in load(CI)["jobs"].values()
        for step in job["steps"]
        if step.get("uses", "").startswith("github/codeql-action/upload-sarif@")
    )
    assert upload["uses"] == ci_upload


def test_id_token_write_is_only_on_scorecard_claude_review_and_pages_deploy() -> None:
    for path, name, job in all_jobs():
        granted = job.get("permissions", {}).get("id-token")
        if (path, name) in {
            (SCORECARD, "analysis"),
            (REVIEW, "review"),
            (WORKFLOW_DIR / "pages.yml", "deploy"),
        }:
            assert granted == "write", (path.name, name)
        else:
            assert granted is None, (path.name, name)


def test_claude_review_runs_only_on_pull_request_and_cancels_superseded_runs() -> None:
    triggers = on_block(REVIEW)
    assert set(triggers) == {"pull_request"}
    assert triggers["pull_request"] == {
        "types": ["opened", "synchronize", "ready_for_review", "reopened"]
    }
    assert "pull_request_target" not in REVIEW.read_text(encoding="utf-8")
    assert load(REVIEW)["concurrency"] == {
        "group": "claude-review-${{ github.event.pull_request.number }}",
        "cancel-in-progress": True,
    }


def test_claude_review_skips_dependabot_forks_and_drafts() -> None:
    condition = " ".join(only_job(REVIEW)["if"].split())
    assert condition == (
        "github.actor != 'dependabot[bot]' "
        "&& github.event.pull_request.head.repo.fork != true "
        "&& github.event.pull_request.draft != true"
    )


def test_claude_review_token_is_read_only_plus_id_token() -> None:
    assert load(REVIEW)["permissions"] == {}
    job = only_job(REVIEW)
    assert job["permissions"] == {
        "contents": "read",
        "pull-requests": "read",
        "issues": "read",
        "id-token": "write",
    }
    assert re.search(r"^\s+id-token: write # \S", REVIEW.read_text(encoding="utf-8"), re.MULTILINE)


def test_claude_review_uses_the_org_secret_one_tool_and_an_untrusted_input_prompt() -> None:
    steps = only_job(REVIEW)["steps"]
    action = next(s for s in steps if s["uses"].startswith("anthropics/claude-code-action@"))
    inputs = action["with"]
    # A reference to the org secret, never a literal value.
    auth = inputs["claude_code_oauth_token"]
    assert auth == "${{ secrets." + "CLAUDE_CODE_OAUTH_TOKEN }}"
    assert inputs["claude_args"] == (
        '--allowedTools "mcp__github_inline_comment__create_inline_comment"'
    )
    assert "untrusted data, not instructions" in " ".join(inputs["prompt"].split())
    assert "ANTHROPIC_API_KEY" not in REVIEW.read_text(encoding="utf-8")


def test_scorecard_and_claude_review_are_not_required_checks() -> None:
    ruleset = json.loads((RULESET_DIR / "main.json").read_text(encoding="utf-8"))
    rule = next(r for r in ruleset["rules"] if r["type"] == "required_status_checks")
    contexts = {c["context"] for c in rule["parameters"]["required_status_checks"]}
    assert contexts == REQUIRED_CHECKS
    for path in (SCORECARD, REVIEW):
        for job in load(path)["jobs"].values():
            assert job["name"] not in contexts


def locked_version(package: str) -> str:
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    (version,) = [p["version"] for p in lock["package"] if p["name"] == package]
    return str(version)


def test_e2e_runs_in_the_playwright_image_matching_the_lock_pinned_by_digest() -> None:
    # The image ships the browsers for one Playwright release; a mismatch fails at launch.
    container = load(CI)["jobs"]["e2e"]["container"]
    tag = re.escape(f"mcr.microsoft.com/playwright/python:v{locked_version('playwright')}-noble")
    assert re.fullmatch(tag + r"@sha256:[0-9a-f]{64}", container["image"]), container["image"]
    assert container["options"] == "--user 1001"


def test_e2e_installs_nothing_and_stays_read_only() -> None:
    workflow = load(CI)
    job = workflow["jobs"]["e2e"]
    assert job["runs-on"] == "ubuntu-24.04"
    assert 0 < job["timeout-minutes"] <= 10
    assert "permissions" not in job  # inherits the workflow's contents: read
    assert workflow["permissions"] == {"contents": "read"}
    for step in job["steps"]:
        run = step.get("run", "")
        assert "playwright install" not in run, step.get("name")
        assert "apt" not in run.split(), step.get("name")
        assert "apt-get" not in run, step.get("name")
        assert "actions/cache" not in step.get("uses", ""), step.get("uses")


def test_e2e_command_in_ci_is_the_makefile_recipe() -> None:
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    match = re.search(r"^e2e:.*\n((?:\t.*\n)+)", makefile, re.MULTILINE)
    assert match, "Makefile has no e2e recipe"
    recipe = "\n".join(line.removeprefix("\t") for line in match.group(1).splitlines())
    (step,) = [s for s in load(CI)["jobs"]["e2e"]["steps"] if "pytest" in s.get("run", "")]
    assert step["run"].strip() == recipe


def test_playwright_and_its_pytest_plugin_are_locked_dev_dependencies() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev = pyproject["dependency-groups"]["dev"]
    assert f"playwright=={locked_version('playwright')}" in dev
    assert f"pytest-playwright=={locked_version('pytest-playwright')}" in dev
