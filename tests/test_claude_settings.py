"""AGENT-01..05: .claude/settings.json keeps every deny and ask rule, and allows nothing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SETTINGS = REPO_ROOT / ".claude" / "settings.json"
SCHEMA = "https://json.schemastore.org/claude-code-settings.json"

MODE_LOCKS = ["disableAutoMode", "disableBypassPermissionsMode"]

REQUIRED_DENY = [
    # gh pr merge
    "Bash(gh pr merge *)",
    "Bash(gh * pr merge)",
    "Bash(gh * pr merge *)",
    # force pushes, plain and option-first
    "Bash(git push --force*)",
    "Bash(git push -f*)",
    "Bash(git push * --force*)",
    "Bash(git push * -f*)",
    "Bash(git push * +*)",
    "Bash(git * push --force*)",
    "Bash(git * push -f*)",
    "Bash(git * push * --force*)",
    "Bash(git * push * -f*)",
    "Bash(git * push * +*)",
    # recursive force deletes
    "Bash(rm -rf *)",
    "Bash(rm -fr *)",
    "Bash(rm -r -f *)",
    "Bash(rm -f -r *)",
    "Bash(rm -Rf *)",
    "Bash(rm -fR *)",
    # terraform
    "Bash(terraform apply *)",
    "Bash(terraform * apply *)",
    "Bash(terraform destroy *)",
    "Bash(terraform * destroy *)",
    # repository, Actions, security and Pages settings, secrets, releases
    "Bash(gh api *rulesets*)",
    "Bash(gh api *actions/permissions*)",
    "Bash(gh api *code-security*)",
    "Bash(gh api *environments*)",
    "Bash(gh api *actions/secrets*)",
    "Bash(gh api *pages*)",
    "Bash(gh secret *)",
    "Bash(gh repo create *)",
    "Bash(gh repo edit *)",
    "Bash(gh release *)",
    # tags
    "Bash(git tag *)",
    "Bash(git * tag)",
    "Bash(git * tag *)",
    "Bash(git push *--tags*)",
    "Bash(git * push *--tags*)",
    "Bash(git push *--follow-tags*)",
    "Bash(git * push *--follow-tags*)",
]

REQUIRED_READ_DENY = [
    "Read(~/.ai_post_env)",
    "Read(~/.aws/**)",
    "Read(~/.ssh/**)",
    "Read(~/.config/gh/**)",
    "Read(~/career-workspace/**)",
    "Read(./.env)",
    "Read(./.env.*)",
]

# Edit rules cover every built-in file-editing tool, Write included; Write(path)
# rules do not match anything, so the settings files are protected with Edit.
REQUIRED_EDIT_DENY = [
    "Edit(/.claude/settings.json)",
    "Edit(/.claude/settings.local.json)",
    "Edit(~/.claude/settings.json)",
    "Edit(//Library/Application Support/ClaudeCode/**)",
]

REQUIRED_ASK = [
    "Bash(git push *)",
    "Bash(git * push)",
    "Bash(git * push *)",
    "Bash(gh pr *)",
    "Bash(gh * pr)",
    "Bash(gh * pr *)",
    "Bash(gh api *)",
    "Bash(gh * api)",
    "Bash(gh * api *)",
    "Bash(python3 *)",
]


@pytest.fixture(scope="module")
def settings() -> dict:
    return json.loads(SETTINGS.read_text(encoding="utf-8"))


def test_schema_is_declared(settings: dict) -> None:
    assert settings["$schema"] == SCHEMA


@pytest.mark.parametrize("key", MODE_LOCKS)
def test_mode_is_disabled(settings: dict, key: str) -> None:
    assert settings["permissions"][key] == "disable"


@pytest.mark.parametrize("rule", REQUIRED_DENY)
def test_deny_rule_present(settings: dict, rule: str) -> None:
    assert rule in settings["permissions"]["deny"]


@pytest.mark.parametrize("rule", REQUIRED_READ_DENY)
def test_read_deny_rule_present(settings: dict, rule: str) -> None:
    assert rule in settings["permissions"]["deny"]


@pytest.mark.parametrize("rule", REQUIRED_EDIT_DENY)
def test_edit_deny_rule_present(settings: dict, rule: str) -> None:
    assert rule in settings["permissions"]["deny"]


@pytest.mark.parametrize("rule", REQUIRED_ASK)
def test_ask_rule_present(settings: dict, rule: str) -> None:
    assert rule in settings["permissions"]["ask"]


def test_no_allow_rules(settings: dict) -> None:
    assert "allow" not in settings
    assert not settings["permissions"].get("allow")
