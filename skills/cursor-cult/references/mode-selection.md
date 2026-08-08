# Mode and fleet selection contract

Claude Code or Codex, not the Python runner, chooses roles from the user's current prompt, conversation, live repository evidence, and authority boundaries. Apply this precedence for every role:

1. **User intent and explicit mode.** Honor an explicitly requested `ask`, `plan`, `agent`, read-only, implementation, review, or detached/background preference when it is compatible with the hard constraints.
2. **Authority gate.** This is non-overridable: a role may never use `agent` when writes or command execution were not authorized. A contradictory no-write constraint defeats an `agent` label, and ambiguity defaults to read-only.
3. **Role deliverable.** Use `ask` to inspect, explain, diagnose, review, or gather evidence without mutation. Use `plan` to produce a structured implementation or decision plan without mutation. Use `agent` only when the role must edit files or run locally mutating commands to produce an authorized outcome.
4. **Independent context test.** Multi-agent is fleet topology, not a Cursor mode. Create another role only for an independently owned question or deliverable that benefits from a separate context window. One role is valid.
5. **Worktree safety.** A shared worktree permits at most one `agent` writer. Concurrent writers require isolated worktrees and separate Cursor Cult invocations; the host may run and watch those invocations concurrently.
6. **Recomposition.** Re-evaluate roles and modes after each material handoff or workspace change. Do not force every task through a fixed ask → plan → agent pipeline.

Foreground/background is a separate lifecycle choice. The same role set can run synchronously with `run` or durably and asynchronously with `start` plus a host-owned watcher.

Each role should include a concise `mode_reason` so `check`, detached state, and watchdog events make the host's decision auditable.

This precedence is host discipline, but the default read-only half is machine-enforced. Per-role configuration preserves operator allow/deny entries, appends `Write(**)` and `Shell(*)` for non-writers, and disables project CLI configuration so repository arrays cannot replace those boundaries. The runner fails closed on malformed operator permissions, missing `--disable-project-configs`, unavailable read-only modes, authority mismatches, or multiple writers. `--readonly-shell` is an explicit exception: it is accepted only for one isolated `ask`/`plan` role, preserves narrower operator denies, but shell can still mutate. What remains host judgment is which mode and capability a role deserves; an authorized `agent` writer and a shell-elevated reader are genuinely powerful.
