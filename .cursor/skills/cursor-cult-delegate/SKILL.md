---
name: cursor-cult-delegate
description: Delegate task-specific roles from Cursor Agent to authenticated Codex CLI and Claude Code CLI workers, then reconcile their evidence in Cursor. Use only when explicitly invoked.
disable-model-invocation: true
argument-hint: "<task and any requested Codex/Claude lenses>"
---

# Cursor Cult Delegate

Cursor is the host and control plane. Codex and Claude are external, task-specific workers. Do not use a fixed committee or a canned architect-to-reviewer pipeline. Build only the roles justified by the user's current request and the live workspace.

Everything after `/cursor-cult-delegate` is authoritative invocation payload. Preserve explicit providers, roles, constraints, non-goals, output requirements, and authority boundaries.

## 1. Reconstruct the live task

Inspect the current conversation, repository, branch, diff, failures, relevant files, and existing tests. Preserve unrelated work. Decide whether delegation creates material independent evidence; deterministic mechanical work should remain in Cursor.

## 2. Stage one private invocation

Create a fresh private directory and keep both inputs inside it:

```zsh
RUN="$(mktemp -d "${TMPDIR:-/tmp}/cursor-cult-delegate.XXXXXX")"
chmod 700 "$RUN"
```

Write `roles.json` as a non-empty array. Each role has this shape:

```json
{
  "id": "runtime-evidence",
  "provider": "codex",
  "label": "Runtime evidence",
  "instruction": "Trace the exact failing path and cite files, symbols, commands, and observed output.",
  "mode": "ask"
}
```

Rules:

- `provider` is `codex` or `claude`.
- `mode` is `ask`, `plan`, or `agent`.
- `agent` means write-capable and is invalid unless that exact role is also selected with `--writer`.
- Use at most one writer in a shared worktree.
- Reusing a role ID with the same `--session-key` resumes that provider conversation.
- A role may include a provider-specific `model`, but omit it unless the user requests one or evidence requires an override.

Write `context.md` with exactly this stable contract:

```markdown
# Intent Capsule

## Verbatim request
<the user's operative request, including the slash-command payload>

## Authorized outcome
<what may be produced or changed>

## Hard constraints and non-goals
<constraints, compatibility requirements, exclusions, unrelated work to preserve>

## Explicit lenses or panel requests
<user-selected providers/roles, or None>

## Authority boundaries
<read-only or the one exact writer; no remote side effects unless explicitly authorized>

## Acceptance evidence
<tests, commands, files, behavior, citations, or artifacts proving completion>

# Current Phase Brief
<current repository evidence, failures, hypotheses, and the exact questions delegated now>
```

The Intent Capsule remains immutable across rounds. Update only the Current Phase Brief.

## 3. Preflight before consuming provider quota

Use a stable session key for this Cursor task. Prefer an available Cursor session identifier; otherwise synthesize one from the current project and task.

```zsh
cursor-cult delegate check \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd . \
  --session-key "cursor:<stable-task-key>"
```

For one authorized writer, append:

```zsh
--writer exact-role-id
```

Do not launch when preflight reports missing authentication, invalid staging, ambiguous writer authority, or nested delegation.

## 4. Run the fleet in the foreground

```zsh
cursor-cult delegate run \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd . \
  --session-key "cursor:<stable-task-key>" \
  --format markdown
```

The default is concurrent execution with no artificial role-count ceiling. Use `--max-parallel N` only when deliberate throttling is useful.

Provider API-key and custom-base-URL environment variables are stripped by default so authenticated CLI account routing wins. Use `--keep-provider-api-env` only when the user explicitly wants those alternate billing/routing variables.

## 5. Reconcile in Cursor

Treat every worker report as evidence, not truth. After the run:

1. Compare claims and disagreements.
2. Re-open cited files and inspect the live diff.
3. Verify commands and tests directly in Cursor.
4. Decide whether a narrower follow-up round is justified.
5. Return one coherent answer tied to the Intent Capsule and acceptance evidence.

A successful subprocess exit is not proof that the user's task is complete. Cursor owns final verification and all Git, PR, deployment, publication, or remote-system actions.

## Safety invariants

- No nested Cursor → Codex/Claude → Cursor delegation loops.
- No more than one writer in a shared worktree.
- Read-only is the default.
- Delegated writers may change local files only within the Intent Capsule.
- Delegated workers may not commit, push, open or merge PRs, deploy, publish, or mutate remote systems unless the user explicitly authorizes that exact side effect.
- Do not claim a provider or test ran unless its output was observed.
