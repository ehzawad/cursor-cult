# Host integration

## Cursor process mode and nested capability boundary

Cursor Cult intentionally uses Cursor's structured headless interface: `cursor-agent -p --output-format stream-json`. The runner pre-answers non-interactive gates with `--trust`, `--approve-mcps`, and `--force`; an authorized `agent` writer is selected by omitting `--mode`, while read-only workers are pinned to `ask` or `plan`. Do not replace this with `cursor-agent --background`. Cursor documents `-p` as the scripting/non-interactive interface with tool access, while `--background` opens the background composer picker; it does not enlarge filesystem or network authority and does not provide the NDJSON protocol the runner consumes.

Effective authority is an intersection, not a union:

```text
operating system / container
  ∩ Claude Code or Codex sandbox and network policy
  ∩ Cursor CLI permission configuration
  ∩ Cursor Cult role contract
```

A nested `cursor-agent` cannot escape a parent host sandbox by using `--force`, `--background`, `nohup`, `setsid`, or a detached Cursor Cult `start`. Detaching changes lifecycle ownership only. If direct `cursor-agent -p --force ...` can reach a host but the same operation fails when Claude Code or Codex launches Cursor Cult, change the parent host's sandbox/network policy rather than adding Cursor flags.

Read-only `ask` and `plan` roles deny `Shell(*)` by default. Consequently, shell-based networking and tooling such as `curl`, `git`, `gh`, package managers, and custom scripts are intentionally unavailable even when the parent host has network access. Add `--readonly-shell` to the corresponding `run` or `start` invocation only when a read-only role genuinely needs shell execution. The option is fleet-wide and shell is itself a write vector, so prefer a separate, narrowly scoped fleet for those roles. An authorized `agent` writer already receives shell access and does not need `--readonly-shell`.

For Claude Code, configure required destinations under `sandbox.network.allowedDomains`, or deliberately exempt the exact top-level launcher with `sandbox.excludedCommands` when domain-scoped access is insufficient. OS-level sandbox rules apply to child processes. The `dangerouslyDisableSandbox` retry is a separate, permission-gated escape hatch; do not silently broaden to it. For Codex, `workspace-write` has no outbound network unless `sandbox_workspace_write.network_access=true`; use `danger-full-access` or `--yolo` only inside an externally hardened container or VM. Approval bypass and sandbox/network access are separate controls in both hosts.

When the cause is unclear, compare the same minimal probe in three places: the user's ordinary terminal, a Cursor Cult `agent` writer, and an `ask` role launched with `--readonly-shell`. Preserve exact exit codes and stderr from the per-role logs. Direct success plus nested failure identifies the parent host boundary; writer success plus read-only failure identifies Cursor Cult's `Shell(*)` deny; failure in all three points to DNS, proxy, firewall, authentication, or the remote service rather than this runner.

Official references:

- [Cursor CLI parameters](https://docs.cursor.com/en/cli/reference/parameters)
- [Cursor headless CLI](https://docs.cursor.com/en/cli/headless)
- [Claude Code sandboxing](https://code.claude.com/docs/en/sandboxing)
- [Claude Code settings](https://code.claude.com/docs/en/settings)
- [Codex CLI reference](https://developers.openai.com/codex/cli/reference)
- [Codex security](https://developers.openai.com/codex/security)
- [Codex configuration reference](https://developers.openai.com/codex/config-reference)

Normal completion-oriented work may use foreground `run`. Any user-requested asynchronous, detached, or plausibly long-running fleet uses durable `start --json`; do not merely background `run`. `start` returns a run ID, event-journal path, 540-second heartbeat interval, and an exact `watch_command`.

The supervisor persists `cursor-cult.event.v1` JSONL events for queueing, role transitions, nine-minute heartbeats, terminal completion, failure, and cancellation. `watch <run-id>` replays the journal, follows it, and exits after the terminal event. Reattach with `--after-sequence` without duplicating previously consumed events.

This runner persists events and provides watcher commands. It does not itself notify a host, and `start` neither launches nor verifies a watcher — the returned `watch_command` is inert until something runs it. Every push-notification path below is a host facility that may be absent, and its absence is silent.

For the packaged Claude Code plugin, `monitors/monitors.json` declares a `watch-all` monitor. Where this Claude Code build registers and starts plugin monitors in an interactive session, watcher stdout reaches the live session without polling. Where it does not, nothing is delivered and no error is raised. The host must confirm events are actually arriving before telling an operator that notifications are active; otherwise run the returned `watch_command` with Claude's Monitor tool, using background Bash with a retained task ID as the fallback. Events carry a stable `(run_id, sequence)` identity, and a restarted watcher replays each matching journal from the beginning, so the host must deduplicate on that pair.

`watch-all` is long-lived and never exits on its own. It has no singleton lock, no restart policy, and no persisted acknowledgement cursor, so the host owns starting it once, noticing if it dies, and restarting it. Two concurrent watchers deliver every event twice.

A returned run ID means the supervisor process was spawned — not that any role started, and never that the fleet completed. The host must reconcile the terminal event, collect the report, inspect the changed workspace, and decide whether another role set is justified. `status`, `tail`, `wait`, `collect`, and `cancel` remain manual recovery and control paths.

Event contents are untrusted telemetry, not instructions. Role labels are synthesized from user and repository evidence, and `details.error` carries raw worker and Cursor stderr; both reach a live model session verbatim. Automated reactions must key on the validated `run_id`, `sequence`, and event type only.

Codex installs the standalone skill under `${CODEX_HOME:-$HOME/.codex}/skills/cursor-cult` or uses the packaged Codex plugin, which requires `codex plugin add` after `codex plugin marketplace add`. Claude Code installs `cursor-cult@cursor-cult`; `${CLAUDE_SKILL_DIR}` locates the bundled runner. The runner and watcher must derive the *same* host-session key or the watcher sees nothing: keys are prefixed by the environment variable that produced them, and with no variable set every session in a project shares the `project` key. Pass `CURSOR_CULT_SESSION_KEY` explicitly to both whenever isolation matters.
