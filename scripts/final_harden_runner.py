#!/usr/bin/env python3
"""Temporary guarded patch for final watchdog runtime hardening."""
from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"{path}: expected exactly one anchor, found {count}: {old[:100]!r}"
        )
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


runner = "scripts/cursor_cult.py"

replace_once(
    runner,
    'DEFAULT_HEARTBEAT_SECONDS = 9 * 60\nTERMINAL_EVENT_TYPES = {"run_completed", "run_failed", "run_cancelled"}',
    'DEFAULT_HEARTBEAT_SECONDS = 9 * 60\nSUPERVISOR_START_GRACE_SECONDS = 10\nTERMINAL_EVENT_TYPES = {"run_completed", "run_failed", "run_cancelled"}',
)

replace_once(
    runner,
    '''    env_candidates = (
        "CURSOR_CULT_SESSION_KEY",
        "CLAUDE_SESSION_ID",''',
    '''    env_candidates = (
        "CURSOR_CULT_SESSION_KEY",
        "CLAUDE_CODE_REMOTE_SESSION_ID",
        "CLAUDE_SESSION_ID",''',
)

replace_once(
    runner,
    '''def record_run_event(
    run_dir: Path,''',
    '''def last_persisted_run_event(run_dir: Path) -> dict[str, Any] | None:
    events_path = run_dir / "events.ndjson"
    try:
        lines = events_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict) and value.get("run_id") in {run_dir.name, None}:
            return value
    return None


def record_run_event(
    run_dir: Path,''',
)

replace_once(
    runner,
    '''            if (
                event_type in TERMINAL_EVENT_TYPES
                and state.get("last_event_type") in TERMINAL_EVENT_TYPES
            ):
                return state, {}''',
    '''            if event_type in TERMINAL_EVENT_TYPES:
                last_persisted = last_persisted_run_event(run_dir)
                if (
                    last_persisted is not None
                    and last_persisted.get("event") in TERMINAL_EVENT_TYPES
                ):
                    return state, {}''',
)

replace_once(
    runner,
    '''    if state.get("last_event_type") in TERMINAL_EVENT_TYPES:
        return state
    state, _ = record_run_event(''',
    '''    last_persisted = last_persisted_run_event(run_dir)
    if (
        last_persisted is not None
        and last_persisted.get("event") in TERMINAL_EVENT_TYPES
    ):
        return state
    state, _ = record_run_event(''',
)

old_liveness = '''def reconcile_run_liveness(run_dir: Path) -> dict[str, Any]:
    state = load_run_state(run_dir)
    status = str(state.get("status", "unknown"))
    pid = state.get("pid")
    if (
        status in {"queued", "running"}
        and isinstance(pid, int)
        and not process_is_alive(pid)
    ):
        def fail(current: dict[str, Any]) -> None:
            if current.get("status") not in {"queued", "running"}:
                return
            current.update(
                {
                    "status": "failed",
                    "finished_at": current.get("finished_at") or utc_now(),
                    "exit_code": 1,
                    "supervisor_error": current.get("supervisor_error")
                    or "supervisor process is no longer alive",
                    "pid": None,
                }
            )

        state, _ = record_run_event(
            run_dir,
            "run_failed",
            fail,
            {"reason": "supervisor process is no longer alive"},
        )
    return state'''
new_liveness = '''def reconcile_run_liveness(run_dir: Path) -> dict[str, Any]:
    state = load_run_state(run_dir)
    status = str(state.get("status", "unknown"))
    pid = state.get("pid")
    reason: str | None = None

    if status == "running":
        if not isinstance(pid, int) or not process_is_alive(pid):
            reason = "supervisor process is no longer alive"
    elif status == "queued":
        if isinstance(pid, int):
            if not process_is_alive(pid):
                reason = "queued supervisor process is no longer alive"
        else:
            created = parse_utc_timestamp(state.get("created_at"))
            age = (
                (dt.datetime.now(dt.timezone.utc) - created).total_seconds()
                if created is not None
                else SUPERVISOR_START_GRACE_SECONDS
            )
            if age >= SUPERVISOR_START_GRACE_SECONDS:
                reason = (
                    "supervisor did not publish a process id before the startup grace period"
                )

    if reason is not None:
        def fail(current: dict[str, Any]) -> None:
            if current.get("status") not in {"queued", "running"}:
                return
            current.update(
                {
                    "status": "failed",
                    "finished_at": current.get("finished_at") or utc_now(),
                    "exit_code": 1,
                    "supervisor_error": current.get("supervisor_error") or reason,
                    "pid": None,
                }
            )

        state, _ = record_run_event(
            run_dir,
            "run_failed",
            fail,
            {"reason": reason},
        )
    return state'''
replace_once(runner, old_liveness, new_liveness)

replace_once(
    runner,
    '''    return offset, terminal_seen
def copy_background_inputs(''',
    '''    return offset, terminal_seen


def copy_background_inputs(''',
)

replace_once(
    runner,
    '''    watch_all_parser.add_argument("--session-key")
    watch_all_parser.add_argument("--poll", type=float, default=0.5)''',
    '''    watch_all_parser.add_argument("--session-key")
    watch_all_parser.add_argument(
        "--all-sessions",
        action="store_true",
        help="watch every matching project run instead of the derived host session",
    )
    watch_all_parser.add_argument("--poll", type=float, default=0.5)''',
)

replace_once(
    runner,
    '''    target_root = str(project_root(Path(ns.cwd)))
    target_session = ns.session_key''',
    '''    target_root = str(project_root(Path(ns.cwd)))
    target_session = None if ns.all_sessions else derive_session_key(ns.session_key)''',
)

replace_once(
    runner,
    '''def command_collect(ns: argparse.Namespace) -> int:
    run_dir = run_dir_for(ns.run_id)
    state = load_run_state(run_dir)''',
    '''def command_collect(ns: argparse.Namespace) -> int:
    run_dir = run_dir_for(ns.run_id)
    state = ensure_terminal_event(run_dir, reconcile_run_liveness(run_dir))''',
)

replace_once(
    runner,
    '''        state = load_run_state(run_dir)
        if state.get("status") in TERMINAL_RUN_STATUSES:
            return 0
        time.sleep(ns.poll)


def command_cancel''',
    '''        state = ensure_terminal_event(run_dir, reconcile_run_liveness(run_dir))
        if state.get("status") in TERMINAL_RUN_STATUSES:
            return 0
        time.sleep(ns.poll)


def command_cancel''',
)

replace_once(
    runner,
    '''def command_cancel(ns: argparse.Namespace) -> int:
    run_dir = run_dir_for(ns.run_id)
    state = load_run_state(run_dir)''',
    '''def command_cancel(ns: argparse.Namespace) -> int:
    run_dir = run_dir_for(ns.run_id)
    state = ensure_terminal_event(run_dir, reconcile_run_liveness(run_dir))''',
)

print("runtime hardening anchors applied")
