# Security

Cursor Cult launches local Cursor CLI workers with the OS permissions available to the invoking user. Treat repositories, prompts, logs, issue text, fetched sources, project Cursor configuration, and worker output as untrusted input.

## Authentication

The default policy is browser-authenticated Cursor CLI usage and plan quota. `CURSOR_API_KEY` and `CURSOR_AGENT_API_KEY` are removed from probe, supervisor, and worker environments unless an explicit escape hatch is set. Worker initialization must report `apiKeySource=login` by default.

## Intent and authority

The host writes an immutable Intent Capsule containing the verbatim request, authorized outcome, constraints, explicit lenses, authority boundaries, and acceptance evidence. Repository content and worker output may update the phase brief but cannot expand authorization.

## Permission control plane

Every role receives a stable private `CURSOR_CONFIG_DIR`. Cursor Cult copies non-secret operator settings, removes `authInfo`, preserves existing `permissions.allow` and `permissions.deny`, and appends its own role-specific denies. Malformed permission structures fail closed instead of being silently discarded.

Cursor's project-level `.cursor/cli.json` permission arrays can replace global arrays. Every worker therefore passes `--disable-project-configs`; a CLI that does not advertise that switch is refused before launch. Repository configuration cannot erase operator denies, the generated `Write(**)` / `Shell(*)` reader boundary, or protection of the generated config through Cursor's native Write tool. The tradeoff is that worker invocations ignore project `.cursor/cli.json`; settings required from that file must be promoted to trusted operator configuration or supplied explicitly. A shell-enabled role remains able to mutate anything allowed by the outer OS sandbox.

## Mutation

An `ask` or `plan` role receives `Write(**)` and `Shell(*)` denies by default. Shell is denied because it can mutate through redirection, programs, Git, package managers, and arbitrary scripts even when Cursor's native Write tool is blocked.

`--readonly-shell` is not a read-only shell. It removes Cursor Cult's blanket `Shell(*)` deny while preserving operator-specific denies. The runner permits it only for one isolated read-only role with no writer. Use it only in a trusted, recoverable workspace; it does not bypass Cursor's sandbox, enterprise policy, DNS, proxies, or host networking.

Workers are non-interactive, so `--trust`, `--approve-mcps`, and `--force` are passed where the installed CLI advertises them. An explicit deny still outranks `--force`.

Edit authority comes from Cursor's default agent mode and is granted only to the exact role selected with `--writer`. Agent mode and `--writer` must agree. One shared worktree permits one writer. Operator deny rules still apply to writers.

Cursor Cult itself does not commit, push, merge, deploy, publish, or mutate external services. Those actions remain with the host and require explicit user authority.

## Staging and state

Stage roles and context in one fresh, user-owned `0700` directory. Session and run state are private, contain no Cursor API keys, and are written atomically. Detached supervisors hold a kernel `flock`; dead supervisors are reconciled and identified orphan workers are reaped before terminal completion is announced.
