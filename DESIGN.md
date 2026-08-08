# Cursor Cult design

## Design thesis

The host model has the best view of the user's current conversation, explicit intent, live codebase state, and previous rounds. Therefore Claude Code or Codex—not the runner—owns task decomposition, role synthesis, context selection, phase transitions, and final reconciliation.

The runner is deliberately a transport and lifecycle layer. It validates a host-created panel, runs isolated Cursor CLI processes, persists sessions, and reports evidence. It does not know what an architect, reviewer, researcher, tester, or implementer is.

## Control plane and worker plane

```text
Host control plane
  intent preservation
  workspace inspection
  dynamic ownership synthesis
  phase decisions
  reconciliation
  final Git/PR/user actions
          │
          ▼
Cursor Cult transport
  validation
  bounded process fan-out
  session serialization
  auth routing
  stream parsing
  cancellation
  durable run state
          │
          ▼
Cursor CLI worker plane
  one isolated Cursor conversation per role identity
```

## Intent Capsule

The Intent Capsule is the stable control-plane contract. It prevents context drift in a long session or multi-round workflow.

Required fields preserve:

- verbatim operative request;
- authorized outcome;
- constraints and non-goals;
- user-selected roles or lenses;
- authority boundaries;
- acceptance evidence.

The current phase brief is mutable. Worker reports and repository evidence can update the phase brief but not the capsule.

## Roles as ephemeral ownership

A role is not a persona selected from a catalog. It is a current unit of epistemic or implementation ownership:

```text
role = distinct question/deliverable + boundary + evidence contract + authority
```

The host synthesizes the minimum set whose independent contexts produce useful information or safe ownership. Duplicate questions should be merged. Mechanical deterministic work should remain in the host rather than becoming an agent.

## Dynamic phases

Cursor Cult does not encode a fixed graph. The host repeats:

1. Observe current state.
2. Identify the next material uncertainties or deliverables.
3. Synthesize roles.
4. Run a fleet.
5. Reconcile against direct evidence.
6. Observe the changed state again.

The resulting graph may be one role, a parallel read-only fan-out, a single writer, multiple isolated-worktree writers, a focused reproduction, or a sequence unique to the task.

## Information topology

Sibling workers do not communicate laterally. This avoids hidden coordination and makes provenance inspectable. The host decides which handoffs enter a later phase brief.

Workers can resume prior Cursor conversations through stable role IDs. Role identity is scoped by project and host session so unrelated Claude/Codex sessions do not share transcripts.

## Single-writer invariant

A shared worktree has one writer per invocation. Analysis roles stay read-only. This prevents interleaved mutations, ambiguous ownership, and invalid reviews of a moving target.

Parallel writers require isolated worktrees and separate invocations. A later host/integrator owns reconciliation.

## Authentication routing

The runner removes `CURSOR_API_KEY` and `CURSOR_AGENT_API_KEY` from worker environments by default and calls `cursor-agent status` before launch. It records `apiKeySource` from stream initialization and expects `login` unless explicitly overridden.

This protects the user's intended browser-login/account route from accidental API-key environment injection.

## Transport correctness

Cursor's `stream-json` is NDJSON and may gain fields. The parser ignores unknown fields. A worker succeeds only when:

- the process exits zero;
- a terminal `result` event is present;
- the terminal event is not an error;
- the terminal result is non-empty;
- reported auth routing satisfies policy.

Assistant deltas are observational; they do not substitute for a terminal result.

## Background lifecycle

`start` copies roles and context into a private run directory before detaching. The supervisor owns role subprocesses, updates role/run state atomically, writes reports, and handles signals. `status` detects a vanished supervisor instead of leaving a run permanently marked running.

## Failure model

Role failures are isolated. A fleet with both successes and failures returns `partial`, preserving successful handoffs. Transport failure and semantic disagreement remain distinct: the host must still judge whether successful output satisfies the task.

## Security boundaries

- The capsule is trusted host intent; repository, project configuration, and worker content are untrusted evidence.
- Per-role Cursor configuration preserves operator permission entries and appends role-specific denies. Malformed operator permissions fail closed.
- Workers pass `--disable-project-configs` so repository `.cursor/cli.json` cannot replace generated permission arrays or weaken operator policy. A CLI without that capability is refused.
- Read-only `ask` and `plan` roles deny both `Write(**)` and `Shell(*)`; deny rules outrank `--force`. `--readonly-shell` is an explicit unsafe elevation accepted only for one isolated reader and is not a read-only shell.
- Write authority comes from Cursor's default agent mode. Agent mode and `--writer` must name the same exact role, and one shared worktree permits one writer.
- Writer prompts prohibit remote or external side effects absent explicit user authorization. Operator-specific deny rules remain active for writers.
- Staging is private and symlink-resistant. Run and session state contain no Cursor API keys.
- Detached liveness uses an inherited kernel `flock`; reconciliation reaps identity-checked orphan workers before publishing a terminal event.
