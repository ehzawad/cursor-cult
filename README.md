# cursor-cult

Cursor Cult lets **Claude Code or OpenAI Codex summon a fleet of Cursor CLI workers** without turning the fleet into a fixed committee.

The host reconstructs the user's operative intent and the live workspace, creates task-specific roles and context at that moment, launches authenticated `cursor-agent` processes, reconciles their evidence, and may compose a completely different fleet for the next round.

```text
Claude Code or Codex
  │
  ├─ preserves the user's exact intent and authority boundaries
  ├─ inspects the current conversation + codebase + diff + errors
  ├─ synthesizes role α, role β, ... for this decision point
  ├─ writes roles.json + an Intent Capsule
  │
  └─ Cursor Cult runner
       ├─ cursor-agent process for role α
       ├─ cursor-agent process for role β
       └─ cursor-agent process for role N
             ↓
       structured terminal handoffs
             ↓
  host reconciles evidence, inspects the new state,
  and dynamically decides whether another round is useful
```

There is no permanent architecture role, failure role, specialist role, implementer role, reviewer role, or verifier role. Any of those may be synthesized when the task warrants it; none is mandatory. User-specified roles and lenses remain authoritative.

## What Cursor Cult is

- A reusable **Codex skill/plugin** and **Claude Code plugin skill**.
- A pure-Python process runner for authenticated Cursor CLI workers.
- A host-mediated collaboration pattern: workers do not secretly communicate with one another.
- A multi-round system: the host can create fresh roles after seeing handoffs and actual workspace changes.
- Analysis-only by default, with at most one explicitly appointed writer in a shared worktree.
- Browser-login oriented: Cursor API-key environment variables are stripped by default.

## What it is not

- Not a Cursor IDE plugin.
- Not built on `@cursor/sdk`.
- Not a hard-coded software-engineering panel.
- Not a majority-voting system.
- Not a multi-writer free-for-all in one worktree.
- Not proof of completion merely because every subprocess exited.

## Prerequisites

Install Cursor CLI and authenticate with the browser flow:

```zsh
curl https://cursor.com/install -fsS | bash
cursor-agent login
cursor-agent status
```

Cursor documents browser login as the recommended authentication path. Cursor Cult removes `CURSOR_API_KEY` and `CURSOR_AGENT_API_KEY` from worker environments unless `CURSOR_CULT_KEEP_CURSOR_API_ENV=1` is deliberately set. When the Cursor stream reports `apiKeySource`, the runner requires `login` by default.

Python 3.10 or newer is required. The implementation is POSIX-oriented because session serialization uses `fcntl`; Linux and macOS are supported.

## Summon from Claude Code

Add the marketplace and install the plugin:

```text
/plugin marketplace add ehzawad/cursor-cult
/plugin install cursor-cult@cursor-cult
/reload-plugins
```

Then invoke it with your intent:

```text
/cursor-cult:cursor-cult find the actual cause of duplicate webhook processing; preserve my uncommitted work and do not edit yet
```

Or explicitly provide desired lenses:

```text
/cursor-cult:cursor-cult use one PostgreSQL locking lens, one distributed-systems adversary, and one minimal-migration lens; then implement only after reconciling them
```

Claude Code passes everything after the skill name through `$ARGUMENTS`, and the skill uses `${CLAUDE_SKILL_DIR}` to locate its bundled runner. Resumable Cursor threads are scoped by a host-session key derived from the first of `CURSOR_CULT_SESSION_KEY`, `CLAUDE_CODE_SESSION_ID`, `CLAUDE_CODE_REMOTE_SESSION_ID`, `CLAUDE_SESSION_ID`, `CODEX_THREAD_ID`, or a terminal fallback that is present — falling back to the literal `project`, which every session in that project then shares. Set `CURSOR_CULT_SESSION_KEY` explicitly, and identically for the runner and any watcher, whenever session isolation actually matters.

For local plugin development:

```zsh
claude --plugin-dir /absolute/path/to/cursor-cult
```

## Summon from Codex

Codex offers two independent install paths. Use one.

### Codex plugin package

The repository ships `.codex-plugin/plugin.json` and a marketplace entry at `.agents/plugins/marketplace.json` pointing to `./plugins/cursor-cult-codex`.

Registering the marketplace only makes the plugin *available*; it does not install it. Both steps are required:

```zsh
codex plugin marketplace add ehzawad/cursor-cult
codex plugin add cursor-cult@cursor-cult
```

Verify before restarting Codex:

```zsh
codex plugin list | grep cursor-cult
```

Expect `installed, enabled`. If it still reads `not installed`, the second command did not run and Codex will not surface the skill.

### Standalone user skill

From a checkout of this repository:

```zsh
./scripts/install_codex.sh --link
```

This installs the self-contained `codex-skills/cursor-cult` tree to:

```text
${CODEX_HOME:-$HOME/.codex}/skills/cursor-cult
```

`${CODEX_HOME:-$HOME/.codex}/skills` is the global skill root Codex scans. Codex also reads a project-local `<repo>/.agents/skills`, but there is no `$HOME/.agents/skills` root — under your home directory, `.agents` holds plugin marketplace manifests, not skills. Pass `--dest` to install elsewhere, `--copy` to copy instead of symlink, and `--force` to replace an existing install.

Verify, then restart Codex:

```zsh
ls "${CODEX_HOME:-$HOME/.codex}/skills/cursor-cult/SKILL.md"
```

Invoke it with your intent:

```text
$cursor-cult trace this cache invalidation bug from the current branch and create only the roles that the evidence requires
```

Codex can also select the skill implicitly when the task matches its description.

## The intent-preservation contract

Every invocation stages an **Intent Capsule** with required headings:

```markdown
# Intent Capsule

## Verbatim request
## Authorized outcome
## Hard constraints and non-goals
## Explicit lenses or panel requests
## Authority boundaries
## Acceptance evidence

# Current Phase Brief
```

The runner rejects context that omits the capsule. The original request, explicit roles, exclusions, authority, and acceptance criteria therefore remain a machine-checked input rather than a vague prompting convention.

The capsule is immutable across rounds. The host updates only the current phase brief with new workspace evidence, handoffs, and remaining unknowns.

Repository files, issue bodies, logs, web material, and prior worker output are treated as untrusted evidence. They cannot override the capsule or expand permissions.

## Dynamic role synthesis

The host creates `roles.json` at runtime:

```json
[
  {
    "id": "duplicate-delivery-linearizability",
    "label": "Duplicate-delivery linearizability",
    "instruction": "Trace the exact concurrent execution paths and determine whether the claimed idempotency invariant holds. Cite paths, symbols, and a reproducible interleaving.",
    "mode": "ask"
  },
  {
    "id": "migration-observability",
    "label": "Migration observability",
    "instruction": "Determine the minimum telemetry and rollback evidence needed to deploy the candidate change safely. Do not edit files.",
    "mode": "ask"
  }
]
```

Those are examples, not built-in roles. A research task, mathematical proof, product-flow audit, documentation task, or deployment diagnosis should produce different ownership.

After a round, the host reconciles the handoffs and inspects the actual workspace again. It may continue one semantic role by reusing its ID, retire every previous role, or create new roles around newly discovered uncertainty.

## Mode and fleet selection

Claude Code or Codex chooses a mode **per role** from the current user prompt, conversation, live repository evidence, and authority boundaries; the runner validates and executes that decision. Explicit user direction wins. `ask` is read-only investigation, explanation, diagnosis, or review. `plan` is a structured read-only strategy. `agent` is reserved for authorized edits or locally mutating commands. Every role may record a `mode_reason` for auditability.

Multi-agent is fleet topology, not a fourth Cursor mode. Independent `ask` and `plan` roles can fan out concurrently, and a fleet can include one authorized `agent` writer in a shared worktree. Concurrent agent writers use isolated worktrees and separate Cursor Cult invocations, which the host may run and watch in parallel. Roles are recomposed after material evidence; there is no compulsory ask → plan → agent pipeline.

## Writer model

Read-only workers receive an explicit no-mutation contract. A single role can be appointed as writer, and that role must declare `"mode": "agent"`:

```zsh
cursor-cult run ... --writer exact-role-id
```

Workers are non-interactive, so `--trust`, `--approve-mcps`, and `--force` are passed to every role — an unanswered prompt would otherwise kill the worker before it produced anything. Write authority is *declared* through Cursor's agent mode, and the two directions are bound together and checked before launch: a role declaring `"mode": "agent"` without `--writer` is rejected, and a `--writer` role that is not in agent mode is rejected rather than running silently read-only.

Be precise about what `--force` does, because it is not just a prompt suppressor. Cursor's headless documentation states that you "combine `--print` with `--force` (or `--yolo`) to modify files in scripts" and that "without `--force`, changes are only proposed, not applied" — so in `-p` mode `--force` is the flag that makes edits real.

Read-only is therefore enforced by Cursor itself rather than inferred from `--mode`. Every non-writer role runs against its own Cursor configuration, supplied through `CURSOR_CONFIG_DIR`, carrying `permissions.deny` of `Write(**)` and `Shell(*)`. Cursor documents that deny rules take precedence over allow rules, and that holds even in agent mode with `--force`: a denied write and a denied shell command are both refused. The generated configuration preserves the operator's existing allow and deny entries and appends role restrictions; malformed permission arrays fail closed. Workers also pass `--disable-project-configs`, because Cursor's project-level `.cursor/cli.json` permission arrays otherwise replace the global arrays and could erase the role boundary. This means worker runs intentionally ignore that project CLI file; move any required settings from it to the operator config or supply them explicitly in the invocation.

Shell is denied because it is itself a write vector — redirection, `sed -i`, `git`, and `rm` all bypass a `Write()` deny — while Cursor's native file-reading tools are unaffected. `--readonly-shell` is therefore an unsafe capability elevation, not a read-only shell. The runner accepts it only for one isolated `ask`/`plan` role with no writer, preserves narrower operator denies, and still cannot guarantee network egress through Cursor's sandbox or the host environment.

The config directory is per role and stable, keyed like the role's session file, and never receives a copy of your credentials. It has to be stable: `CURSOR_CONFIG_DIR` relocates Cursor's `chats/` store as well as its settings, so a fresh directory each run would break `--resume`. Cursor writes its own material there, so the directory is `0700`.

Cursor accepts only `ask` and `plan` as explicit `--mode` values in this CLI interface. Agent mode remains fully supported: Cursor Cult selects Cursor's default agent behavior by omitting `--mode`, never by passing the invalid `--mode agent`. A fleet may mix `ask`, `plan`, and one authorized `agent` writer. Both foreground `run` and detached `start` print a warning naming the agent writer and explaining that it can edit files and run commands; detached run state preserves the same warning.

Because omitting `--mode` *is* how agent mode is selected, a read-only role can only be held read-only when the CLI advertises `--mode`. Capability detection reads `cursor-agent --help`, so a probe that times out, fails, or returns nothing would otherwise drop `--mode` while still passing `--force` — launching an `ask` role with argv identical to an authorized writer. Cursor Cult fails closed instead: if `--mode` was not positively detected, every `ask` and `plan` role is refused before launch with exit `2`.

The writer may mutate the local worktree within the Intent Capsule, but it may not commit, push, open or merge a PR, deploy, publish, or mutate external services unless the capsule explicitly authorizes that exact action.

Multiple writers are rejected in one invocation. Use isolated worktrees and separate fleets when parallel implementation is genuinely safe.

## Foreground by default

A normal skill invocation is completion-oriented. Claude or Codex waits for the fleet, reconciles evidence, dynamically launches any justified follow-up round, verifies the acceptance evidence, and then answers.

Direct foreground execution:

```zsh
RUN="$(mktemp -d "${TMPDIR:-/tmp}/cursor-cult.XXXXXX")"
chmod 700 "$RUN"
# Write $RUN/roles.json and $RUN/context.md.

python3 scripts/cursor_cult.py check \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd . \
  --session-key "manual:example"

python3 scripts/cursor_cult.py run \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd . \
  --session-key "manual:example"
```

The runner emits Markdown by default and ends normal stderr with `CURSOR_CULT_DONE`. Use `--format json` for automation.

## Durable asynchronous execution and watchdog events

For detached or plausibly long work, use `start --json`, not an untracked shell background process. `start` returns the durable run ID, event path, event schema, heartbeat interval, and an exact `watch_command`:

```zsh
LAUNCH="$(python3 scripts/cursor_cult.py start --json \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd . \
  --session-key "manual:example")"
```

Each detached supervisor writes `cursor-cult.event.v1` JSONL records for queueing, run start, role start/finish, heartbeats, completion, failure, and cancellation. The heartbeat interval defaults to `540` seconds (nine minutes). It is a scheduling cadence rather than a delivery deadline — lock waits, filesystem latency, host suspension, and watcher polling all delay observation, and a run shorter than one interval emits no heartbeat at all. It is persisted in run state and can be changed for tests or operations with `--heartbeat-seconds` or `CURSOR_CULT_HEARTBEAT_SECONDS`.

```zsh
python3 scripts/cursor_cult.py watch <run-id>
python3 scripts/cursor_cult.py watch <run-id> --after-sequence 12
```

`watch` replays and follows one journal, flushes each event as it is read, and exits after the terminal event — or, if the run is already terminal and has nothing left to deliver, after one drain pass, so it never polls a finished run forever.

Notification delivery is a host capability, not something this runner provides. `start` returns a durable run and an exact `watch_command`; that command is inert until a host launches it. The packaged Claude Code plugin ships a `watch-all` monitor definition, which delivers watcher lines into a live session only where Claude Code registers and starts plugin monitors. For Codex, the skill instructs the host to attach `watch_command` to a managed background terminal; nothing in this repository performs that attachment, and a host without such a channel gets no push notification. On any unsupported, headless, or monitor-disabled host, confirm the watcher actually started before reporting that notifications are active — otherwise keep `watch`/`wait` attached, or retain the run ID and poll `status`, `tail`, `wait`, `collect`, and `cancel` manually.

## Explicit detached execution

Detached fleets support the same mixed `ask`/`plan`/authorized-`agent` role set as foreground fleets; add `--writer <role-id>` when `roles.json` contains the agent writer. Prefer `start --json` so the host can attach the returned watchdog command:

```zsh
LAUNCH="$(python3 scripts/cursor_cult.py start \
  --json \
  --roles-file "$RUN/roles.json" \
  --context-file "$RUN/context.md" \
  --cwd . \
  --session-key "manual:example")"
RUN_ID="$(printf '%s' "$LAUNCH" | python3 -c 'import json, sys; print(json.load(sys.stdin)["run_id"])')"
# Attach this watcher through the host's managed background-process primitive.
# Running it directly is the portable foreground/recovery form.
python3 scripts/cursor_cult.py watch "$RUN_ID" --format jsonl

python3 scripts/cursor_cult.py status "$RUN_ID"
python3 scripts/cursor_cult.py tail "$RUN_ID" --follow
python3 scripts/cursor_cult.py wait "$RUN_ID"
python3 scripts/cursor_cult.py collect "$RUN_ID"
python3 scripts/cursor_cult.py cancel "$RUN_ID"
```

`start` copies the staged inputs into a private durable run directory under:

```text
$XDG_STATE_HOME/cursor-cult/runs/<run-id>
```

Returning a run ID means the fleet was launched; it does not mean the task is complete.

## Resumable worker identities

Cursor sessions are stored under:

```text
$XDG_STATE_HOME/cursor-cult/sessions
```

The state key is:

```text
canonical project root × host session key × role ID
```

This keeps two Claude/Codex sessions in the same repository from accidentally sharing a Cursor role conversation. Reusing a role ID deliberately continues that semantic lens. A stale resume is cleared and retried fresh once.

## Runner guarantees

- No role catalog and no panel-size ceiling.
- No wall-clock timeout on a role's work, and no artificial concurrency cap: every requested role runs at once by default. Set `--max-parallel`/`CURSOR_CULT_MAX_PARALLEL` positive to deliberately throttle.
- One Cursor process per role.
- Successful sibling handoffs survive another role's failure -- including a role that crashes the process outright (e.g. a stream exceeding the read-buffer limit): its sibling results are still reported, and every role's result is persisted to the run directory the instant it finishes, so a crash or a kill loses at most the still-in-flight roles.
- Cursor terminal `result` is authoritative; exit code `0` without a non-empty terminal result is failure.
- Unknown stream fields are ignored for forward compatibility.
- Browser-login authentication is verified before launch.
- API-key environment variables are stripped by default.
- Process-group cancellation propagates to live Cursor workers.
- No wrapper-level wall-clock timeout.
- Roles/context must be staged together in a user-owned `0700` directory.
- Background state and reports use atomic writes.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Every role returned a usable terminal result |
| `3` | Partial success |
| `1` | All roles or the background supervisor failed |
| `2` | Invalid invocation, staging, authentication, or nonterminal collect |
| `130` | Cancelled |

## Development

```zsh
python3 -m unittest discover -s tests -v
python3 -m py_compile scripts/cursor_cult.py tests/*.py
bash -n bin/cursor-cult scripts/*.sh tests/fake_cursor_agent.sh
```

The test suite uses a fake Cursor CLI; it does not consume Cursor quota.

## Primary references

- [Cursor CLI overview](https://cursor.com/docs/cli/overview)
- [Cursor CLI parameters](https://cursor.com/docs/cli/reference/parameters)
- [Cursor CLI output format](https://cursor.com/docs/cli/reference/output-format)
- [Cursor CLI authentication](https://cursor.com/docs/cli/reference/authentication)
- [Cursor headless mode](https://cursor.com/docs/cli/headless)
- [OpenAI: Build skills](https://developers.openai.com/codex/skills)
- [OpenAI: Package plugins](https://developers.openai.com/codex/plugins/build)
- [Claude Code: Create plugins](https://code.claude.com/docs/en/plugins)
- [Claude Code: Plugin marketplaces](https://code.claude.com/docs/en/plugin-marketplaces)

## License

MIT
