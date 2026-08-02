---
name: cursor-cult
description: Compose and run an adaptive fleet of Cursor CLI workers for complex implementation, research, debugging, review, architecture, testing, or any task where distinct independent lenses improve the outcome. Use when the user says cursor cult, cursor fleet, cursor council, ultrathink with Cursor, or asks Codex to delegate work to Cursor CLI.
---

# Cursor Cult

You are the host and conductor. Cursor CLI workers are task-specific instruments, not a fixed committee.

## Workflow

1. Reconstruct the live task: goal, repository state, in-flight edits, evidence, errors, hypotheses, constraints, known unknowns, and acceptance criteria.
2. Synthesize the smallest useful panel. Each role must own a distinct question. Prefer task-specific roles over generic titles.
3. Keep investigation workers read-only. In a shared worktree, appoint at most one writer. Use isolated worktrees before authorizing multiple writers.
4. Create one private staging directory with `mktemp -d`. Write `roles.json`, a non-empty array of `{id,label,instruction,mode}`, and `context.md`, a decision-complete shared brief.
5. Locate the installed skill root and run:

```zsh
python3 <skill-root>/scripts/cursor_cult.py \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd "$PROJECT_ROOT" \
  > "$RUN/out.md" 2> "$RUN/err.log"
```

For implementation, add exactly one `--writer <role-id>`. Do not impose an outer timeout. Read both outputs. Normal stderr ends with `CURSOR_CULT_DONE`.
6. Reconcile, do not vote. Compare evidence and assumptions. Run a focused second round when decisive findings should be challenged or verified.
7. The host owns final edits, verification, user communication, and Git/PR actions.

## Role contract

Every role instruction should state its specific question, expected evidence, boundaries, and handoff. Ask workers to report “nothing material” when appropriate rather than manufacturing findings. Thoroughness beats speed.

## Authentication

Require `cursor-agent status` to succeed. Do not request or inject `CURSOR_API_KEY`. The runner strips Cursor API-key environment variables by default so the user's authenticated CLI session and plan quota are used.
