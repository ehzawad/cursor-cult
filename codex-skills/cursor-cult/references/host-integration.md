# Host integration

Use foreground execution for normal completion-oriented work. Use managed background execution only when explicitly requested. The host owns reconciliation, final verification, and any Git or PR action.

Codex installs this skill under `${CODEX_HOME:-$HOME/.codex}/skills/cursor-cult`, or as the packaged Codex plugin, which requires `codex plugin add cursor-cult@cursor-cult` after `codex plugin marketplace add`.
