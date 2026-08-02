# Native Cursor versus SDK runner

## Native path

Use the skill and custom agents inside Cursor Agent mode in the desktop GUI or authenticated Cursor CLI. The parent conversation remains the conductor, and native subagents provide separate contexts and UI-visible progress.

This is the preferred interactive path.

## SDK path

Use `pnpm cult -- ...` for deterministic scripts, CI, experiments, or headless execution. The runner loads the same Markdown role definitions, launches one local Cursor SDK agent per analysis role with bounded concurrency, then launches one integrator and an optional postflight gate.

The local SDK path intentionally creates separate top-level agents. Cursor SDK v1 custom `agents:` definitions are cloud-only; local executors currently ignore them. The runner therefore does not pretend that local SDK subagents exist.

## Behavioral parity

Both paths preserve:

- adaptive role selection;
- decision-complete shared context;
- bounded parallel analysis;
- one writer per worktree;
- independent review and verification;
- explicit partial failure.

They do not share model conversation state. The shared contract is the role prompt and handoff, not a hidden persistent thread.
