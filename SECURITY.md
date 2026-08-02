# Security

## Trust boundary

Cursor agents can read files, run commands, contact configured services, and—when permitted—modify the workspace. Use Cursor Cult only with repositories, task text, tools, MCP servers, and fetched content you are prepared to expose to the selected Cursor runtime and model providers.

Repository content is not trusted merely because it is local. Source files, documentation, issue text, test fixtures, generated files, and dependency output may contain prompt injection. Role prompts explicitly tell agents to treat such content as evidence rather than instructions, but prompt-level defenses are not a complete security boundary.

## Native mode

Native analysis agents declare `readonly: true` where appropriate. The builder and verifier are workspace-capable because implementation and command-backed validation require tools. Review the effective Cursor permissions, sandbox policy, network access, MCP configuration, and team policy in the environment where the plugin runs.

## SDK mode

The local SDK runner creates multiple top-level agents against one `cwd`. The one-writer policy is enforced by orchestration prompts, not by filesystem permissions. A compromised or disobedient analysis agent could still attempt a mutation.

For stronger isolation:

- run analysis roles in disposable read-only copies or isolated worktrees;
- configure Cursor permissions to block write and dangerous shell operations;
- use local auto-review/custom policy for tool calls;
- keep secrets out of the agent process environment;
- use short-lived, least-privilege credentials;
- inspect the final git diff and untracked files before committing.

`--allow-edits` deliberately grants the integrator a write mandate. It should be used only in a clean, recoverable worktree. Cursor Cult never performs `git reset --hard`, force pushes, or automatic commits itself.

## API keys and billing

`CURSOR_API_KEY` is required only for programmatic SDK mode. Do not commit it, print it, place it in task text, or pass it through role handoffs. Local and cloud SDK calls may incur token-based charges; panel size multiplies model calls.

## Reporting vulnerabilities

Open a private security advisory on the GitHub repository when possible. Do not include live credentials, proprietary source, or exploit payloads that expose third-party systems in a public issue.
