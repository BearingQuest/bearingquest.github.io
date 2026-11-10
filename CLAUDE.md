@AGENTS.md

## Context and usage budget
- Use the `Explore` subagent for searches spanning 3+ files; do single-file lookups directly.
- Run tests through the `test-runner` subagent; never pull full test output into the main context.
- Keep code edits and judgment calls in the main session; subagents only search, run tests, and read logs.
