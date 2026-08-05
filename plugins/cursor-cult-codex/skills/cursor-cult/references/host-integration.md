# Host integration

Normal completion-oriented work may use foreground `run`. Any user-requested asynchronous, detached, or plausibly long-running fleet uses durable `start --json`; do not merely background `run`. `start` returns a run ID, event-journal path, 540-second heartbeat interval, and an exact `watch_command`.

The supervisor persists `cursor-cult.event.v1` JSONL events for queueing, role transitions, nine-minute heartbeats, terminal completion, failure, and cancellation. `watch <run-id>` replays the journal, follows it, and exits after the terminal event. Reattach with `--after-sequence` without duplicating previously consumed events.

In an interactive Codex CLI session, launch the returned `watch_command` as a Codex-managed background terminal, not with an untracked shell `&`. Unified exec streams stdout deltas and emits a terminal process event, so each watchdog line and the final event return to the main Codex harness. Retain the background process identifier and use Codex's process controls if cancellation is needed. If background terminals are unavailable, keep `watch` attached and do not claim asynchronous notification.

A returned run ID means launched, not completed. The host must reconcile the terminal event, collect the report, inspect the changed workspace, and decide whether another role set is justified. `status`, `tail`, `wait`, `collect`, and `cancel` remain manual recovery and control paths.

Codex installs this skill under `${CODEX_HOME:-$HOME/.codex}/skills/cursor-cult`, or as the packaged Codex plugin, which requires `codex plugin add cursor-cult@cursor-cult` after `codex plugin marketplace add`.
