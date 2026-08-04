# Changelog

## 0.4.1 — 2026-08-04

- Fix Codex never surfacing the skill. `codex plugin marketplace add` only makes a plugin *available*; the README omitted the required `codex plugin add cursor-cult@cursor-cult`, so the plugin stayed `not installed` and its skill never loaded. Both steps are now documented with a verification command.
- Fix `scripts/install_codex.sh` installing to `$HOME/.agents/skills/cursor-cult`, which Codex does not scan. It now installs to `${CODEX_HOME:-$HOME/.codex}/skills/cursor-cult`, the only global skill root Codex reads. The `AGENTS_HOME` and `~/.agents` fallbacks are removed.
- Fix the installer packaging the repository root as the skill directory. `--link` and `--copy` now use the self-contained `codex-skills/cursor-cult` tree, so `references/` resolves and `.git`, tests, and examples are no longer exposed as skill content.
- Fix every role failing in roughly 500ms with `Workspace Trust Required` in any directory the user had not interactively trusted. Workers have no terminal, so `--trust`, `--approve-mcps`, and `--force` are now passed for every role; an unanswered interactive gate killed the role before it produced a result.
- Fix `mode: "agent"` being passed as `--mode agent`, which Cursor rejects — the documented writer path crashed on every invocation. Agent is Cursor's default mode and is now selected by omitting `--mode`.
- Tie write authority to `--writer`: a role declaring `mode: "agent"` without being the authorized writer is now rejected before launch, since commands are auto-approved for every role.
- Correct the false claim that Codex discovers skills under `$HOME/.agents/skills`; `~/.agents` holds plugin marketplace manifests, not skills.
- Resync the packaged plugin skill trees, which had drifted from their sources, and add `scripts/sync_packages.sh --check` as a CI gate.
- Remove the legacy bare-flag argv shim; subcommands are required.

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
