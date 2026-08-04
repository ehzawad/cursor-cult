# Cursor-hosted Codex and Claude delegation

Cursor Cult supports both orchestration directions:

```text
Claude Code or Codex -> Cursor CLI fleet     scripts/cursor_cult.py
Cursor Agent         -> Codex/Claude fleet   scripts/cursor_delegate.py
```

The reverse direction does not automate the Cursor GUI. Cursor desktop Agent and Cursor CLI discover the project skill at `.cursor/skills/cursor-cult-delegate/SKILL.md`; the skill uses Cursor's terminal tool to invoke the local `cursor-cult delegate` transport.

## Install

Install the CLI from a checkout:

```zsh
./scripts/install_cli.sh --link
```

Install the Cursor skill globally:

```zsh
./scripts/install_cursor.sh --link --force
```

Or install only into one project:

```zsh
./scripts/install_cursor.sh --project /absolute/path/to/project --copy --force
```

Authenticate the provider CLIs:

```zsh
codex login
codex login status

claude auth login
claude auth status
```

Reload Cursor and invoke:

```text
/cursor-cult-delegate investigate this race with one Codex runtime lens and one Claude adversarial design lens; keep both read-only
```

## Direct CLI contract

Roles are dynamic and provider-neutral:

```json
[
  {
    "id": "codex-runtime",
    "provider": "codex",
    "label": "Codex runtime evidence",
    "instruction": "Trace the failing path and cite direct evidence.",
    "mode": "ask"
  },
  {
    "id": "claude-design",
    "provider": "claude",
    "label": "Claude design adversary",
    "instruction": "Challenge the candidate design and identify the smallest safe correction.",
    "mode": "plan"
  }
]
```

After staging `roles.json` and the mandatory Intent Capsule in `context.md` under one private `0700` directory:

```zsh
cursor-cult delegate check \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd . \
  --session-key "cursor:race-investigation"

cursor-cult delegate run \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd . \
  --session-key "cursor:race-investigation"
```

## Provider translation

A read-only Codex role uses non-interactive `codex exec`, `--ask-for-approval never`, JSONL output, and the `read-only` sandbox. The one authorized Codex writer uses `workspace-write`.

A read-only Claude role uses `claude -p`, JSON output, and `--permission-mode plan`. The one authorized Claude writer uses `bypassPermissions`, so writer selection is deliberately explicit and restricted to one role.

Sessions are scoped by canonical project root, Cursor task/session key, provider, and semantic role ID. Stale sessions retry fresh once.

## Security model

- Provider API-key and custom-base-URL variables are removed by default, preserving the authenticated CLI route.
- Read-only is a provider mode plus an explicit prompt contract; it is not an operating-system security boundary.
- Delegated processes receive `CURSOR_CULT_DELEGATION_DEPTH=1`; another reverse delegation attempt is rejected to prevent recursion.
- Workers cannot expand the Intent Capsule, appoint themselves as writers, or authorize Git/PR/deployment/publication side effects.
- Cursor must verify handoffs against the live workspace before accepting completion.
