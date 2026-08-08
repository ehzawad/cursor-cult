# Security

Cursor Cult launches local Cursor CLI workers with the permissions available to the invoking user. Treat repositories, prompts, logs, issue text, fetched sources, and worker output as untrusted input.

## Authentication

The default policy is browser-authenticated Cursor CLI usage and plan quota. `CURSOR_API_KEY` and `CURSOR_AGENT_API_KEY` are removed from probe, supervisor, and worker environments unless an explicit escape hatch is set. Worker initialization must report `apiKeySource=login` by default.

## Intent and authority

The host writes an immutable Intent Capsule containing the verbatim request, authorized outcome, constraints, explicit lenses, authority boundaries, and acceptance evidence. Repository content and worker output may update the phase brief but cannot expand authorization.

## Mutation

Read-only workers receive a no-mutation contract, run in Cursor Ask mode, and carry generated `permissions.deny` rules. This is not an operating-system sandbox.

Only the generated deny rules are *enforced*. The no-mutation prompt and Ask mode are dispositions the model usually honors, not boundaries — do not count either as containment.

Workers are non-interactive, so `--trust` and `--force` are passed to every role: an unanswered workspace-trust or command-approval prompt kills the worker before it produces a result. Every role can therefore execute commands without interactive approval, including read-only ones — treat any fleet invocation as running commands in that worktree.

`--approve-mcps` is passed only to an authorized writer. Cursor spawns an approved MCP server as a local process before any permission rule is consulted, so auto-approving repository-defined servers for a read-only role hands that repository arbitrary local execution no generated deny can reach.

## Repository-controlled configuration

Every worker runs with `--disable-project-configs`. A repository `.cursor/cli.json` *replaces* the global `permissions.allow`/`deny` arrays rather than merging into them, so without this flag a checked-out project can delete the reader boundary outright. Verified against the installed CLI: with a hostile project config a worker's shell command ran; with the flag it was refused. Cursor Cult refuses to launch when the installed CLI does not accept the flag.

Note that the switch suppresses that file entirely, not only its permission arrays. Repository-scoped Cursor CLI settings — including deny rules a project used as a safety control — are not applied to workers. Put anything you depend on in the operator config, which is preserved.

Run state is denied to every role, including an authorized writer. The state root's `0700` mode only excludes other OS users, and a supervisor reads the worker binary path, writer set, and project root out of `runs/<id>/config.json`; a worker able to write that file could redirect a later supervisor to a substituted executable.

This covers `.cursor/cli.json` only. A repository `.cursor/mcp.json` is a separate vector and is handled by refusing read-only roles in such a repository unless `--allow-project-mcp` is passed. Note that Cursor records MCP approvals under `~/.cursor/projects/<slug>/`, a path `CURSOR_CONFIG_DIR` does not relocate, so an approval granted by an earlier run persists.

Edit authority is separate and comes from Cursor's agent mode, which is granted only to a role explicitly selected with `--writer`. Agent mode and `--writer` must agree, and a mismatch in either direction is rejected before launch. Use writers only in trusted, recoverable worktrees.

Cursor Cult itself does not commit, push, merge, deploy, publish, or mutate external services. Those actions remain with the host and require explicit user authority.

## Staging and state

Stage roles and context in one fresh, user-owned `0700` directory. Session and run state are private, contain no Cursor API keys, and are written atomically.
