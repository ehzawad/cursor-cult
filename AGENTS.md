# Repository instructions

- Cursor Cult is a standalone Cursor CLI fleet runtime used from Codex or Claude Code. It is not a Cursor editor plugin and must not depend on `@cursor/sdk` or Cursor API keys.
- The host owns operative-intent preservation, live workspace inspection, dynamic role synthesis, round planning, and reconciliation. The runner must contain no fixed persona or domain catalog.
- Preserve browser-login routing: strip `CURSOR_API_KEY` and `CURSOR_AGENT_API_KEY`, probe the local Cursor CLI, and require `apiKeySource=login` by default.
- Preserve one writer per shared worktree. Read-only workers use Ask mode; a writer requires explicit host authorization via `--writer`.
- Workers are non-interactive: pass every prompt-suppressing Cursor flag, and keep write authority tied to agent mode rather than to `--force`.
- Keep `scripts/cursor_cult.py` and the skill trees mirrored into the packaged plugin copies; `scripts/sync_packages.sh --check` gates this in CI.
- Reuse a role ID only to continue the same semantic lens in the same host-session scope.
- Keep staging private, state writes atomic, cancellation process-group-safe, and partial failures observable.
- Run the Python tests, compile checks, shell syntax checks, and manifest validation before publishing.
