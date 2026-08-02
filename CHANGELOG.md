# Changelog

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
