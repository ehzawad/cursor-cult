# Changelog

## 0.4.0 — 2026-08-03

- Fix a crash where one role emitting a single stream-json line past asyncio's default 64KiB `readline()` limit (`LimitOverrunError`) took down the entire fleet, discarding every other role's already-finished work. The subprocess stdout/stderr streams now use a 32MiB line limit.
- Isolate role crashes: an unexpected exception in one role's execution is now caught and reported as that role's own failure instead of propagating out of `asyncio.gather` and cancelling every sibling task.
- `run` (foreground) now persists each role's result to a run directory the instant that role finishes -- the same durability `start` (detached) already had -- so a crash, a kill, or a host-side timeout loses at most the still-in-flight roles, never the ones already done. The run directory path is printed on the first stderr line; on an unexpected crash, `run` reconstructs and prints whatever partial results made it to disk instead of exiting with nothing.
- Remove the artificial default concurrency ceiling: `--max-parallel` (and `CURSOR_CULT_MAX_PARALLEL`) now default to `0`, meaning uncapped -- every requested role runs concurrently unless a positive value is explicitly passed to deliberately throttle. The prior default silently capped any fleet larger than 6 roles to sequential waves.
- Document that the host's own foreground tool-call timeout is independent of this runner (which imposes none) and recommend backgrounding `run` for larger or longer fleets.

## 0.3.0 — 2026-08-03

- Make Claude Code and Codex the explicit control planes for operative-intent preservation, live workspace inspection, dynamic role synthesis, multi-round recomposition, and final reconciliation.
- Add a machine-checked Intent Capsule and task-specific opaque role identities.
- Enforce browser-login routing and strip Cursor API-key environment variables by default.
- Scope persistent Cursor role conversations by project, host session, and role ID; recover confirmed stale sessions once.
- Add foreground and managed-background execution with `status`, `tail`, `wait`, `collect`, and `cancel`.
- Enforce one writer per shared worktree and prohibit implicit Git, PR, deployment, publishing, and external-system authority.
- Add self-contained Claude Code and Codex plugin/skill packaging, CI, documentation, and a fake-transport test suite.

## 0.2.0 — 2026-08-02

- Replace the original Cursor SDK/editor design with a local Cursor CLI fleet hosted by Codex or Claude Code.
