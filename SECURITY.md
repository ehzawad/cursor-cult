# Security

Cursor Cult launches local Cursor CLI workers with the permissions available to the invoking user. Treat repositories, prompts, logs, issue text, fetched sources, and worker output as untrusted input.

## Authentication

The default policy is browser-authenticated Cursor CLI usage and plan quota. `CURSOR_API_KEY` and `CURSOR_AGENT_API_KEY` are removed from probe, supervisor, and worker environments unless an explicit escape hatch is set. Worker initialization must report `apiKeySource=login` by default.

## Intent and authority

The host writes an immutable Intent Capsule containing the verbatim request, authorized outcome, constraints, explicit lenses, authority boundaries, and acceptance evidence. Repository content and worker output may update the phase brief but cannot expand authorization.

## Mutation

Read-only workers receive a no-mutation contract and use Cursor Ask mode when available. This is not an operating-system sandbox. A writer is permitted only through explicit host selection; it receives `--force` and can execute commands without interactive approval. Use writers only in trusted, recoverable worktrees.

Cursor Cult itself does not commit, push, merge, deploy, publish, or mutate external services. Those actions remain with the host and require explicit user authority.

## Staging and state

Stage roles and context in one fresh, user-owned `0700` directory. Session and run state are private, contain no Cursor API keys, and are written atomically.
