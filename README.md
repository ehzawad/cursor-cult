# cursor-cult

An adaptive fleet of **Cursor CLI workers** hosted by either **OpenAI Codex** or **Claude Code**.

Cursor Cult is not a Cursor IDE plugin and does not use `@cursor/sdk`. The host synthesizes task-specific roles, stages one shared brief, and invokes authenticated `cursor-agent` processes in bounded parallel. Each role owns a resumable Cursor conversation. Usage is routed through the local Cursor CLI login and plan quota, not an API key.

## Mental model

```text
Codex or Claude Code (host/conductor)
  ├─ reconstructs the live task and unknowns
  ├─ synthesizes N task-specific roles
  ├─ stages roles.json + context.md
  ├─ launches cursor-cult
  │    ├─ cursor-agent role A ── persistent session A
  │    ├─ cursor-agent role B ── persistent session B
  │    └─ cursor-agent role N ── persistent session N
  └─ reconciles evidence, optionally appoints one writer, verifies, and answers
```

Workers do not secretly coordinate. The host is the information bus. Analysis is read-only by default. In one worktree, appoint one writer; multiple writers require isolated worktrees.

## Prerequisites

```zsh
curl https://cursor.com/install -fsS | bash
cursor-agent login
cursor-agent status
```

Cursor Cult uses official CLI print mode, `stream-json`, session resume, modes, and `--force` for an explicitly appointed writer. It strips `CURSOR_API_KEY` and `CURSOR_AGENT_API_KEY` by default so a logged-in CLI session is not silently displaced by API billing. Set `CURSOR_CULT_KEEP_CURSOR_API_ENV=1` only intentionally.

## Install for Codex

```zsh
git clone https://github.com/ehzawad/cursor-cult.git \
  "${CODEX_HOME:-$HOME/.codex}/skills/cursor-cult"
```

Restart Codex, then invoke `$cursor-cult` or ask for “cursor cult”, “cursor fleet”, or “cursor council”.

## Install for Claude Code

```zsh
claude plugin marketplace add ehzawad/cursor-cult
claude plugin install cursor-cult@cursor-cult
```

Then invoke `/cursor-cult:cursor-cult` or ask Claude to use the Cursor fleet.

## Direct CLI

```zsh
RUN=$(mktemp -d "${TMPDIR:-/tmp}/cursor-cult.XXXXXX")
cat > "$RUN/roles.json" <<'JSON'
[
  {"id":"architecture","label":"Architecture","mode":"ask","instruction":"Model boundaries, invariants, and the smallest coherent design."},
  {"id":"failure-analysis","label":"Failure analyst","mode":"ask","instruction":"Attack assumptions and identify concurrency, security, operational, and compatibility failures."}
]
JSON

printf '%s\n' 'Review this repository retry design and find concrete correctness risks.' > "$RUN/context.md"

python3 scripts/cursor_cult.py \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd .
```

Appoint a sole writer by adding `--writer architecture`.

## Guarantees

- No mandatory role catalog; the host composes roles from the actual task.
- Bounded parallelism via `CURSOR_CULT_MAX_PARALLEL`, default 6.
- Per-project/per-role session persistence under `$XDG_STATE_HOME/cursor-cult`.
- Unknown-field-tolerant parsing of Cursor CLI `stream-json`.
- API-key environment stripping to preserve CLI subscription authentication.
- Partial success: one failed role does not erase successful handoffs.
- Cancellation propagates to Cursor CLI process groups.
- No wrapper-level wall-clock timeout.

## Security

`--writer <role-id>` adds Cursor's `--force`, permitting unattended commands and edits. Use it only in trusted repositories. Read-only behavior is a prompt/orchestration contract, not an OS sandbox.

## Test

```zsh
python3 -m unittest discover -s tests -v
```

## License

MIT
