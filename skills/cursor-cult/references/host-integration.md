# Host integration

Normal skill invocations use foreground `run`: the host waits, reconciles, and may dynamically compose a follow-up round. Use `start` only when the user explicitly requests detached/background execution. A returned run ID means launched, not completed; inspect with `status`, `tail`, `wait`, `collect`, and `cancel`.

Codex installs the standalone root skill under `$HOME/.agents/skills/cursor-cult` or uses the packaged Codex plugin. Claude Code installs `cursor-cult@cursor-cult`; `${CLAUDE_SKILL_DIR}` locates the bundled runner and `${CLAUDE_SESSION_ID}` scopes persistent role threads.
