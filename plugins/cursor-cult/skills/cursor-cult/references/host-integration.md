# Host integration

Normal completion-oriented work may use foreground `run`. Any user-requested asynchronous, detached, or plausibly long-running fleet uses durable `start --json`; do not merely background `run`. `start` returns a run ID, event-journal path, 540-second heartbeat interval, and an exact `watch_command`.

The supervisor persists `cursor-cult.event.v1` JSONL events for queueing, role transitions, nine-minute heartbeats, terminal completion, failure, and cancellation. `watch <run-id>` replays the journal, follows it, and exits after the terminal event. Reattach with `--after-sequence` without duplicating previously consumed events.

For the packaged Claude Code plugin, `monitors/monitors.json` starts `watch-all` on the first `cursor-cult` skill invocation. Claude Code plugin monitors deliver every stdout line into the live interactive session, so heartbeats and terminal completion reach the main harness without polling. Events carry a stable `(run_id, sequence)` identity so a restarted monitor can replay safely and the host can deduplicate. If plugin monitors are unavailable, the host must run the returned `watch_command` with Claude's Monitor tool; use background Bash only as a fallback and retain its task ID.

A returned run ID means launched, not completed. The host must reconcile the terminal event, collect the report, inspect the changed workspace, and decide whether another role set is justified. `status`, `tail`, `wait`, `collect`, and `cancel` remain manual recovery and control paths.

Codex installs the standalone skill under `${CODEX_HOME:-$HOME/.codex}/skills/cursor-cult` or uses the packaged Codex plugin, which requires `codex plugin add` after `codex plugin marketplace add`. Claude Code installs `cursor-cult@cursor-cult`; `${CLAUDE_SKILL_DIR}` locates the bundled runner and `${CLAUDE_SESSION_ID}` scopes persistent role threads.
