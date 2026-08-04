# Security

Cursor Cult launches local Cursor CLI workers with the permissions available to the invoking user. Treat repositories, prompts, logs, issue text, fetched sources, and worker output as untrusted input.

## Authentication

The default policy is browser-authenticated Cursor CLI usage and plan quota. `CURSOR_API_KEY` and `CURSOR_AGENT_API_KEY` are removed from probe, supervisor, and worker environments unless an explicit escape hatch is set. Worker initialization must report `apiKeySource=login` by default.

## Intent and authority

The host writes an immutable Intent Capsule containing the verbatim request, authorized outcome, constraints, explicit lenses, authority boundaries, and acceptance evidence. Repository content and worker output may update the phase brief but cannot expand authorization.

## Mutation

Read-only workers receive a no-mutation contract and run in Cursor Ask mode. This is not an operating-system sandbox.

Workers are non-interactive, so `--trust`, `--approve-mcps`, and `--force` are passed to every role: an unanswered workspace-trust, MCP, or command-approval prompt kills the worker before it produces a result. Every role can therefore execute commands without interactive approval, including read-only ones — treat any fleet invocation as running commands in that worktree.

Edit authority is separate and comes from Cursor's agent mode, which is granted only to a role explicitly selected with `--writer`. Agent mode and `--writer` must agree, and a mismatch in either direction is rejected before launch. Use writers only in trusted, recoverable worktrees.

Cursor Cult itself does not commit, push, merge, deploy, publish, or mutate external services. Those actions remain with the host and require explicit user authority.

## Staging and state

Stage roles and context in one fresh, user-owned `0700` directory. Session and run state are private, contain no Cursor API keys, and are written atomically.
