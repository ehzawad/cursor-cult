# Repository instructions

This repository is both a Cursor plugin and a TypeScript SDK application.

- Treat current first-party Cursor documentation and `cursor/plugins` as the source of truth for SDK, plugin, skill, and subagent behavior.
- Keep native role definitions under `agents/`; the SDK runner must load those same files rather than maintaining a second prompt catalog.
- Preserve the single-writer invariant: parallel roles may inspect, research, review, or verify, but only the builder may edit tracked source files in a shared worktree.
- Keep the SDK runner local-runtime behavior honest. Do not claim local custom `agents:` support until Cursor documents and ships it.
- Run `pnpm check` after changes. Use `pnpm cult -- --task "validate panel" --dry-run` for a no-credential smoke test.
- Never commit `CURSOR_API_KEY`, generated run output, or dependency directories.
