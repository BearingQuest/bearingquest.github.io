#!/usr/bin/env bash
# Builds the blog (content/blog to _build/blog) with Pelican, from the locked "site"
# dependency group. build-site.sh and `make blog` both call this. Any Pelican warning
# fails the build. Pass --no-dev (the Pages build does) to leave the test tools out.
set -euo pipefail

cd "$(dirname "$0")/.."
uv run --locked "$@" pelican content -s pelicanconf.py --fatal warnings --delete-output-directory
