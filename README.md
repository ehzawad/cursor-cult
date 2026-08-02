# cursor-cult

A task-adaptive multi-role Cursor team for the desktop GUI, interactive Cursor CLI, and programmatic Cursor SDK.

Cursor Cult does not launch a pile of interchangeable writers. It uses a phased council:

1. independent scouts, architects, specialists, and critics investigate in parallel;
2. one builder reconciles the evidence and owns all workspace edits;
3. an independent reviewer and verifier inspect the resulting diff and runtime evidence;
4. the parent agent or SDK runner returns one reconciled outcome with provenance and explicit uncertainty.

The repository is deliberately dual-surface:

- **Native Cursor plugin and project assets** for Agent mode in the GUI and authenticated CLI.
- **TypeScript SDK runner** for scripts, CI, experiments, and headless local orchestration.

Both paths consume the same role definitions under [`agents/`](agents/).

## Why this architecture

Cursor's native subagents run independently, in parallel, with their own context and configurable prompts/models. Cursor's official plugin format packages skills and agents, so the interactive implementation is a normal Cursor plugin rather than a shell wrapper around the CLI.

The SDK path is intentionally different at the transport layer. As of August 2, 2026, Cursor SDK v1 custom `agents:` definitions are cloud-only; a local executor ignores them. The local runner therefore creates one top-level local SDK agent per role, uses bounded concurrency, and performs integration in a separate single-writer phase. This preserves the council semantics without claiming an API capability that is not there.

See [DESIGN.md](DESIGN.md) for the full model and tradeoffs.

## Roles

| Role | Purpose | Native access |
|---|---|---|
| `scout` | Map relevant code, flows, conventions, and active changes | Read-only, background |
| `architect` | Define invariants, boundaries, tradeoffs, and implementation shape | Read-only, background |
| `specialist` | Adopt a dynamic domain lens supplied by the conductor | Read-only, background |
| `critic` | Attack assumptions, security, migration, and failure modes | Read-only, background |
| `builder` | Reconcile handoffs and act as the sole writer | Workspace-capable |
| `reviewer` | Independently review the actual implementation and diff | Read-only, background |
| `verifier` | Run decisive tests/checks and report observed evidence | Command-capable, no source edits |

The panel is adaptive. A focused bug may need three roles; a cross-cutting production change may need six. More agents are not automatically better.

## Native Cursor installation

### Local plugin installation

```zsh
git clone https://github.com/ehzawad/cursor-cult.git
cd cursor-cult
./scripts/install-plugin.sh --link
```

Reload Cursor. In Agent mode:

```text
/cursor-cult implement idempotent webhook processing and prove duplicate deliveries are safe
```

A copied plugin installation is also available:

```zsh
./scripts/install-plugin.sh --copy
```

### Project-scoped installation for GUI and CLI

Project-scoped assets avoid depending on plugin discovery and travel with the repository:

```zsh
git clone https://github.com/ehzawad/cursor-cult.git ~/src/cursor-cult
~/src/cursor-cult/scripts/install-project.sh ~/src/your-project --copy
```

This installs:

```text
.cursor/skills/cursor-cult/
.cursor/agents/{scout,architect,specialist,critic,builder,reviewer,verifier}.md
```

Reload Cursor or restart the Cursor CLI, then invoke `/cursor-cult` in Agent mode. Existing files are moved to timestamped backups rather than overwritten silently.

For development, `--link` keeps the target project connected to this checkout. Copy mode is more portable and is recommended for normal use.

## Programmatic SDK runner

Requirements:

- Node.js 22.13 or newer
- pnpm 10.9 or newer
- a Cursor user or service-account API key

```zsh
pnpm install
cp .env.example .env
set -a; source .env; set +a
```

Analysis-only council:

```zsh
pnpm cult -- \
  --cwd ~/src/your-project \
  --task "Find why the ingestion worker duplicates records and propose the smallest safe fix"
```

Single-writer implementation plus postflight review and verification:

```zsh
pnpm cult -- \
  --cwd ~/src/your-project \
  --task-file ./examples/idempotency-task.md \
  --roles scout,architect,critic,specialist \
  --allow-edits \
  --max-parallel 4 \
  --out .cursor-cult/latest.md
```

JSON for automation:

```zsh
pnpm cult -- \
  --task "Review the current branch" \
  --roles reviewer,critic \
  --skip-integrator \
  --format json
```

Validate the role catalog and planned graph without an API call:

```zsh
pnpm cult -- --task "validate the design" --dry-run
pnpm cult -- --list-roles
```

Run `pnpm cult -- --help` for all flags.

## Execution semantics

The default SDK graph is:

```text
preflight:  scout + architect + critic     (bounded parallel)
                       |
integration:           builder             (one agent, analysis-only by default)
                       |
postflight: reviewer + verifier            (bounded parallel)
```

`--allow-edits` changes only the integrator's mandate. It does not turn the analysis roles into writers. `--skip-integrator` returns independent handoffs. `--skip-postflight` omits the independent gate.

Transport failure is isolated per role: the runner preserves successful sibling handoffs and reports failed roles explicitly. A role status of `finished` means the Cursor run completed at the transport layer; semantic verdicts such as `changes-required`, `falsified`, or `blocked` remain in the role handoff and are not collapsed into an unreliable majority vote.

Process exit codes are:

- exit `0` for a fully completed run;
- exit `3` for a partial run;
- exit `2` for an agent/run failure that prevents a coherent result;
- exit `130` for cancellation;
- exit `1` for configuration or startup errors.

## Security model

Native `readonly: true` agents provide a real Cursor role constraint. The SDK's local multi-agent path uses separate top-level agents and prompt-level role discipline; that is an orchestration invariant, not an operating-system sandbox. Run SDK mode only against trusted workspaces and prompts, and use Cursor permissions/sandbox controls appropriate to your environment.

Local agents inherit access to the workspace and may see credentials available to the process. Never commit `CURSOR_API_KEY`. Repository, issue, and fetched content can contain prompt injection; every role is instructed to treat it as untrusted data.

See [SECURITY.md](SECURITY.md).

## Development

```zsh
pnpm install
pnpm check
pnpm cult -- --task "validate panel" --dry-run --format json
```

The dependency floor is `@cursor/sdk` 1.0.24, the current npm release verified on August 2, 2026. The SDK requires Node.js 22.13 or newer; this repository uses pnpm 10.9 and keeps the model selection at `auto` unless the caller overrides it.

## Primary references

- [Cursor SDK documentation](https://cursor.com/docs/api/sdk/typescript)
- [Cursor SDK release](https://cursor.com/changelog/sdk-release)
- [Subagents, Skills, and Image Generation](https://cursor.com/changelog/2-4)
- [Multitask, Worktrees, and Multi-root Workspaces](https://cursor.com/changelog/04-24-26)
- [Official Cursor plugins repository](https://github.com/cursor/plugins)
- [Official `orchestrate` plugin](https://github.com/cursor/plugins/tree/main/orchestrate)
- [Official SDK advanced reference](https://github.com/cursor/plugins/blob/main/cursor-sdk/skills/cursor-sdk/references/advanced.md)

## License

MIT
