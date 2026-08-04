# Runtime contract

`roles.json` is a non-empty array of host-created role objects with `id`, `label`, `instruction`, optional `mode`, and optional `model`. `context.md` must contain the required Intent Capsule headings and a Current Phase Brief. Both files share one private user-owned `0700` staging directory.

The runner strips Cursor API-key variables by default, probes Cursor CLI browser login, tolerates unknown NDJSON fields, and requires a non-empty terminal result for success. Role sessions are scoped by canonical project, host session key, and role ID. Confirmed stale resumes retry fresh once.

Exit codes: `0` success, `3` partial success, `1` failure, `2` invalid invocation/precondition, `130` cancellation.
