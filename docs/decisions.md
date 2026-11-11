# Decisions

Newest first. Any change to the plan, an approved exception or a new tool gets a row.

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-11-11 | Add semgrep 1.183.0 (released 2026-10-29), run from PyPI with `uvx --exclude-newer 2026-10-30`, public registry packs `p/default`, `p/python` and `p/github-actions`, metrics off, no login. | Static analysis of the repo as a required check, reported to code scanning as SARIF. The newest release at least 7 days old (1.184.0 and 1.185.0 are newer). `--exclude-newer` pins its Python dependencies to a snapshot. The registry rule packs are fetched at run time and change over time; that is accepted. |
| 2026-11-11 | Add zizmor 1.32.0 (released 2026-11-02), run with `uvx --exclude-newer 2026-11-03 zizmor@1.32.0 .github`. | Static analysis of the workflows as a required check; it fails on any finding. The newest release at least 7 days old. `--exclude-newer` pins its dependencies to a snapshot. |
