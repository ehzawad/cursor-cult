# Changelog

## 0.5.0 — 2026-08-05

- Add the public `cursor-cult.event.v1` JSONL journal for detached runs, with per-run sequence numbers, role lifecycle records, configurable heartbeats, and terminal outcome events.
- Add `watch <run-id>` to replay and follow one run, and `watch-all` for long-lived project/session monitoring. `start --json` now returns the run directory, event path, schema, configured heartbeat interval, and an exact watcher argv.
- Add best-effort detached-run liveness reconciliation for dead or never-published supervisor PIDs, and recovery of a wholly absent terminal journal record from terminal state.
- Add a host-owned mode-selection contract for choosing `ask`, `plan`, or authorized `agent` per role, an optional per-role `mode_reason` surfaced by `check`, detached state, and event records, and a warning before foreground or detached execution of an authorized agent-mode writer. This builds on 0.4.1, which already fixed the invalid `--mode agent` argv mapping and bound agent mode to `--writer`.
- Fix read-only roles failing open to agent mode when Cursor CLI capability detection failed. `supports_mode` is the only capability without a permissive empty-help fallback, so a `--help` probe that timed out, raised, or returned nothing dropped `--mode` while still passing `--trust`, `--approve-mcps`, and `--force` — launching an `ask` or `plan` role with argv identical to an authorized writer. Read-only roles are now refused before launch when `--mode` was not positively detected.
- Fix every `role_started` and `role_completed` event losing its `mode`, `role_status`, `duration_ms`, and `error`. `record_run_event` snapshotted the caller's `details` before running the `mutate` closure that populates it, so role events carried only `role_id` and every completion message read "status unknown". The snapshot now happens after the mutation.
- Fix `watch-all` re-announcing a project's entire run archive every time it starts. The packaged monitor starts on each skill invocation and replayed every matching run from sequence 1, so a long-lived state directory delivered thousands of stale notifications into the live session; nothing prunes the run root. Runs that are live, or that finished within two minutes of the watcher starting, still replay in full — that is the just-missed-a-fast-run case the watcher exists for — and older runs now start at end-of-journal. The watcher also drops bookkeeping for run directories that have been deleted.
- Fix `derive_session_key` not reading `CLAUDE_CODE_SESSION_ID`, the variable current Claude Code builds actually export. Runs silently fell back to a terminal-scoped key, so two sessions sharing a terminal shared a key and each `watch-all` streamed the other's runs. The older `CLAUDE_CODE_REMOTE_SESSION_ID` and `CLAUDE_SESSION_ID` are still honored.
- Fix an unusable `CURSOR_CULT_MAX_PARALLEL` crashing every subcommand, the same defect as the heartbeat variable and in the same function: both are parsed while building the parser, which runs before argument dispatch for every command.
- Fix an unusable `CURSOR_CULT_HEARTBEAT_SECONDS` crashing every subcommand. The value was parsed eagerly as an argparse default inside `build_parser()`, which runs for all commands, so `export CURSOR_CULT_HEARTBEAT_SECONDS=` raised an unhandled `ValueError` from `--version`, `--help`, `watch`, and the packaged plugin monitor alike. An unusable value now falls back to the default; an explicit non-positive `--heartbeat-seconds` is still rejected.
- Fix a watcher permanently losing an event when it observed a partially appended journal line. The reader advanced its offset past the newline-less fragment, then read the remainder as a second unparseable fragment. Offsets are now committed only for newline-terminated records.
- Fix every remaining run artifact being left to the ambient umask. `events.ndjson`, `supervisor.log`, and the per-role `*.stdout.ndjson`/`*.stderr.log` are now created `0600` like the rest of the run directory, and the `cursor-cult` and `cursor-cult/runs` parents are now `0700` — `mkdir(parents=True, mode=...)` applies its mode only to the leaf, so both were left world-readable and let any local user enumerate run IDs, project names, and timing.
- Gate the release metadata in CI. The version-consistency test now derives everything from the runner's `VERSION`, compares parsed manifest fields instead of substrings, and requires the top `CHANGELOG.md` entry to match — the gap that let `0.5.0` reach a tagged head with no changelog entry at all.
- Fix a suppressed duplicate or post-terminal heartbeat still applying the caller's state mutation and returning it. The suppression guards now run before the mutation, so a caller can no longer act on state that was never written to disk.
- Fix a heartbeat failure ending all liveness reporting silently. `emit_heartbeats` had no exception handling, so one transient state or journal error stopped the beat for the rest of the run — suppressing exactly the signal the watchdog exists to provide — and then surfaced when the supervisor awaited the task, letting a dead heartbeat override an otherwise successful run.
- Emit report paths on the recovered, cancelled, and liveness-failure terminal events, not only the supervisor's own, so a host reacting to any terminal event knows where to collect from. Reconciled-failed runs now also sweep role states out of `queued`/`running`, and a successful terminal state no longer keeps a stale `supervisor_error`.
- Fix `watch` spinning forever when a run is terminal but no terminal event is deliverable to that watcher, such as when the terminal sequence is at or below `--after-sequence` or the journal tail is inconsistent. `watch` now exits after one post-terminal drain pass.
- Fix an explicitly requested cancellation being reported as a failure. `cancel` signals and returns, trusting the supervisor to append `run_cancelled`; when the supervisor died first, reconciliation resolved the run to `failed`/exit 1. The supervisor now installs its cancellation handlers *before* publishing `running` — previously a `cancel` racing that window killed it under the default disposition with no event at all — and `cancel` records the intent before signalling, so reconciliation resolves to `cancelled`/exit 130 regardless of whether the supervisor survived to report it.
- Fix a supervisor that lost the startup-grace race resurrecting a run already reconciled to `failed`. Terminal status is now absorbing: such a supervisor exits instead of flipping the run back to `running` and appending post-terminal lifecycle events.
- Fix `watch-all` reconciling and appending recovery events for every run under the state root before applying its project and session filters, so one project's monitor mutated other projects' runs.
- Package a Claude Code `watch-all` monitor definition and document how supported Claude Code and Codex hosts can attach watcher output. Notification availability depends on the host facility and is not guaranteed by this runner.
- Extend package synchronization checks and CI manifest validation to cover the monitor files.

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
