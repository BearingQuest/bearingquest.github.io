# Local gates. Each recipe line runs in bash with -euo pipefail, and make
# stops at the first line that fails.
SHELL := /bin/bash
.SHELLFLAGS := -euo pipefail -c
.DEFAULT_GOAL := help
.PHONY: help check e2e audit hooks blog sbom smoke

help: ## List the targets
	@grep -E '^[a-z0-9]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{ printf "  %-6s %s\n", $$1, $$2 }'

check: ## Ruff lint, ruff format check, then pytest
	uv run ruff check .
	uv run ruff format --check .
	uv run pytest

# CI runs this command in the Playwright container, which has no make;
# tests/test_workflows.py fails if the two drift apart. The tests build the
# site with scripts/build-site.sh and serve it on 127.0.0.1 themselves.
e2e: ## Chromium tests against the built site (needs Playwright's browsers)
	uv run pytest -m e2e tests/e2e

# The same commands as the pip-audit job in .github/workflows/ci.yml;
# tests/test_hooks.py fails if the two drift apart.
audit: ## pip-audit every package locked in uv.lock
	uv export --locked --format requirements-txt --no-emit-project --quiet --output-file requirements-audit.txt
	uv run --locked pip-audit --strict --disable-pip -r requirements-audit.txt

blog: ## Build the blog with Pelican into _build/blog
	scripts/build-blog.sh
	@echo "Built the blog in _build/blog"

# The same commands as the SBOM step in the build job of .github/workflows/pages.yml
# (R22); tests/test_sbom.py fails if the two drift apart.
sbom: ## CycloneDX SBOM of the locked site group into _build
	mkdir -p _build
	uv export --locked --format cyclonedx1.5 --only-group site --no-emit-project --output-file _build/sbom-site.cdx.json

# The live-site check that pages.yml (after a deploy) and smoke.yml (daily) run (R23).
smoke: ## Check the five live URLs on bearingquest.com (needs network)
	uv run --no-project python3 scripts/smoke.py

hooks: ## Use the committed hooks in .githooks (pre-push runs gitleaks)
	git config core.hooksPath .githooks
