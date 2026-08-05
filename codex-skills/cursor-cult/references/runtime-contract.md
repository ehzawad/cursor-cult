# Runtime contract

`roles.json` is a non-empty array of host-created role objects with `id`, `label`, `instruction`, optional `mode`, optional `model`, and optional `mode_reason`. `context.md` must contain the required Intent Capsule headings and a Current Phase Brief. Both files share one private user-owned `0700` staging directory.

The runner strips Cursor API-key variables by default, probes Cursor CLI browser login, tolerates unknown NDJSON fields, and requires a non-empty terminal result for success. Role sessions are scoped by canonical project, host session key, and role ID. Confirmed stale resumes retry fresh once.

Detached `start` owns one supervisor process and persists `state.json`, per-role results, reports, and `events.ndjson`. The event schema is `cursor-cult.event.v1`. The default heartbeat is 540 seconds; tests or operators may override it with `--heartbeat-seconds` or `CURSOR_CULT_HEARTBEAT_SECONDS`. The supervisor schedules one heartbeat after each 540-second interval while it is running; operating-system suspension can delay delivery, so this is a liveness cadence rather than a hard real-time deadline. Heartbeats report run age and role counts but do not falsely claim task progress. Role transitions and terminal outcomes emit immediately. A dead recorded supervisor is reconciled to one persisted `run_failed` event.

`watch` is a read-only event transport for one run. `watch-all` is a session-length transport filtered by project and optional host session key. Both flush one JSON object per line; terminal state is carried in the event rather than conflated with watcher transport failure.

Exit codes: `0` success, `3` partial success, `1` failure, `2` invalid invocation/precondition, `130` cancellation. `watch` exits `0` after observing any terminal run event; inspect the event's `status` and `details` for the run outcome.
