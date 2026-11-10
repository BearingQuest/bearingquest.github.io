# Local gates. Each recipe line runs in bash with -euo pipefail, and make
# stops at the first line that fails.
SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help
.PHONY: help check audit hooks

help: ## List the targets
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{ printf "  %-6s %s\n", $$1, $$2 }'

check: ## Ruff lint, ruff format check, then pytest
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

# The same commands as the pip-audit job in .github/workflows/ci.yml;
# tests/test_hooks.py fails if the two drift apart.
audit: ## pip-audit every package locked in uv.lock
	uv export --locked --format requirements-txt --no-emit-project --quiet --output-file requirements-audit.txt
	uv run --locked pip-audit --strict --disable-pip -r requirements-audit.txt

hooks: ## Use the committed hooks in .githooks (pre-push runs gitleaks)
	git config core.hooksPath .githooks
