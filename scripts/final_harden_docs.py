#!/usr/bin/env python3
"""Temporary guarded patch for host/session documentation hardening."""
from pathlib import Path

monitor_path = Path("monitors/monitors.json")
monitor = monitor_path.read_text(encoding="utf-8")
old_monitor = (
    '--cwd \\"${CLAUDE_PROJECT_DIR}\\" '
    '--session-key \\"claude:${CLAUDE_SESSION_ID}\\" --format jsonl'
)
new_monitor = '--cwd \\"${CLAUDE_PROJECT_DIR}\\" --format jsonl'
if monitor.count(old_monitor) != 1:
    raise SystemExit("monitors/monitors.json: session-id anchor missing")
monitor_path.write_text(monitor.replace(old_monitor, new_monitor), encoding="utf-8")

claude_skill = Path("skills/cursor-cult/SKILL.md")
text = claude_skill.read_text(encoding="utf-8")
text = text.replace(
    '  --cwd "$PROJECT_ROOT" \\\n  --session-key "claude:${CLAUDE_SESSION_ID}"',
    '  --cwd "$PROJECT_ROOT"',
)
text = text.replace(
    '  --cwd "$PROJECT_ROOT" \\\n  --session-key "claude:${CLAUDE_SESSION_ID}" \\\n  > "$RUN/out.md"',
    '  --cwd "$PROJECT_ROOT" \\\n  > "$RUN/out.md"',
)
text = text.replace(
    '  --cwd "$PROJECT_ROOT" \\\n  --session-key "claude:${CLAUDE_SESSION_ID}")"',
    '  --cwd "$PROJECT_ROOT")"',
)
if "CLAUDE_SESSION_ID" in text:
    raise SystemExit("skills/cursor-cult/SKILL.md still depends on CLAUDE_SESSION_ID")
staging_anchor = (
    "Create a private staging directory, write `roles.json` and `context.md`, "
    "and preflight:\n"
)
staging_replacement = (
    staging_anchor
    + "\nThe runner derives a host-session key from the environment shared by "
      "Claude Code and its plugin monitor. Set `CURSOR_CULT_SESSION_KEY` "
      "explicitly when an operator needs a stable custom key; do not depend "
      "on undocumented Claude variables.\n"
)
if text.count(staging_anchor) != 1:
    raise SystemExit("Claude skill staging anchor missing")
claude_skill.write_text(
    text.replace(staging_anchor, staging_replacement, 1),
    encoding="utf-8",
)

host_doc = Path("skills/cursor-cult/references/host-integration.md")
text = host_doc.read_text(encoding="utf-8")
text = text.replace(
    "For the packaged Claude Code plugin, `monitors/monitors.json` starts "
    "`watch-all` on the first `cursor-cult` skill invocation. Claude Code "
    "plugin monitors deliver every stdout line into the live interactive "
    "session, so heartbeats and terminal completion reach the main harness "
    "without polling.",
    "For the packaged Claude Code plugin, `monitors/monitors.json` starts "
    "`watch-all` on the first `cursor-cult` skill invocation. On Claude Code "
    "v2.1.105 or later, in an interactive CLI session where the experimental "
    "Monitor facility is available, plugin monitors deliver every stdout line "
    "into the live session, so heartbeats and terminal completion reach the "
    "main harness without polling.",
)
text = text.replace(
    "Claude Code installs `cursor-cult@cursor-cult`; `${CLAUDE_SKILL_DIR}` "
    "locates the bundled runner and `${CLAUDE_SESSION_ID}` scopes persistent "
    "role threads.",
    "Claude Code installs `cursor-cult@cursor-cult`; `${CLAUDE_SKILL_DIR}` "
    "locates the bundled runner. The runner and monitor derive the same "
    "host-session key from their shared environment; "
    "`CURSOR_CULT_SESSION_KEY` is the explicit override.",
)
host_doc.write_text(text, encoding="utf-8")

runtime_doc = Path("skills/cursor-cult/references/runtime-contract.md")
text = runtime_doc.read_text(encoding="utf-8")
text = text.replace(
    "A dead recorded supervisor is reconciled to one persisted `run_failed` "
    "event.",
    "A dead recorded supervisor, including a launch that never publishes its "
    "PID within a ten-second grace period, is reconciled to one persisted "
    "`run_failed` event. If state reached a terminal status but the process "
    "died before appending the matching journal line, the next watcher/status "
    "operation reconstructs the missing terminal event.",
)
text = text.replace(
    "`watch` is a read-only event transport for one run. `watch-all` is a "
    "session-length transport filtered by project and optional host session "
    "key.",
    "`watch` is a read-only event transport for one run. `watch-all` is a "
    "session-length transport filtered by project and, by default, the derived "
    "host-session key; pass `--all-sessions` only for deliberate project-wide "
    "observation.",
)
runtime_doc.write_text(text, encoding="utf-8")

readme = Path("README.md")
text = readme.read_text(encoding="utf-8")
old_watch = '''WATCH_COMMAND="$(printf '%s' "$LAUNCH" | python3 -c 'import json, shlex, sys; print(shlex.join(json.load(sys.stdin)["watch_command"]))')"

# Attach this command through the host's managed background-process primitive.
eval "$WATCH_COMMAND"'''
new_watch = '''# Attach this watcher through the host's managed background-process primitive.
# Running it directly is the portable foreground/recovery form.
python3 scripts/cursor_cult.py watch "$RUN_ID" --format jsonl'''
if text.count(old_watch) != 1:
    raise SystemExit("README watcher/eval anchor missing")
text = text.replace(old_watch, new_watch, 1)
text = text.replace(
    "Claude Code plugin installs include a session monitor that starts on the "
    "first skill invocation and delivers every watchdog line to the live "
    "Claude harness.",
    "Claude Code plugin installs include a session monitor that starts on the "
    "first skill invocation and delivers every watchdog line to the live "
    "Claude harness when Claude Code is v2.1.105 or later, the session is "
    "interactive, and the experimental Monitor facility is available.",
)
readme.write_text(text, encoding="utf-8")

print("host/session documentation anchors applied")
