from __future__ import annotations

import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "cursor_cult.py"
FAKE = ROOT / "tests" / "fake_cursor_agent.sh"
SPEC = importlib.util.spec_from_file_location("cursor_cult", RUNNER)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)


CAPSULE = """# Intent Capsule

## Verbatim request
Investigate the live task exactly as requested.

## Authorized outcome
Return source-backed findings and only authorized local changes.

## Hard constraints and non-goals
Preserve unrelated work. No remote side effects.

## Explicit lenses or panel requests
None.

## Authority boundaries
Read-only unless one exact writer role is supplied. No commit, push, PR, deploy, or publish.

## Acceptance evidence
Concrete paths, commands, observed outputs, risks, and unknowns.

# Current Phase Brief
Inspect the current fixture repository.
"""

FULL_CAPS = M.CursorCapabilities(
    supports_mode=True,
    supports_resume=True,
    supports_model=True,
    supports_force=True,
    supports_trust=True,
    supports_approve_mcps=True,
)


class Fixture:
    def __init__(self) -> None:
        self.stack = tempfile.TemporaryDirectory()
        self.root = Path(self.stack.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        (self.repo / ".git").mkdir()
        self.stage = self.root / "stage"
        self.stage.mkdir(mode=0o700)
        os.chmod(self.stage, 0o700)
        self.roles = self.stage / "roles.json"
        self.context = self.stage / "context.md"
        self.context.write_text(CAPSULE)
        self.state = self.root / "state"
        self.trace = self.root / "trace.log"

    def write_roles(self, roles: list[dict[str, object]]) -> None:
        self.roles.write_text(json.dumps(roles))

    def env(self, **extra: str) -> dict[str, str]:
        env = dict(os.environ)
        env.update(
            {
                "XDG_STATE_HOME": str(self.state),
                "FAKE_CURSOR_TRACE": str(self.trace),
                "FAKE_CURSOR_EXPECT_STRIPPED": "1",
                "CURSOR_API_KEY": "must-not-leak",
                "CURSOR_AGENT_API_KEY": "must-not-leak-either",
            }
        )
        env.update(extra)
        return env

    def command(self, subcommand: str = "run", *extra: str) -> list[str]:
        return [
            sys.executable,
            str(RUNNER),
            subcommand,
            "--roles-file",
            str(self.roles),
            "--context-file",
            str(self.context),
            "--cwd",
            str(self.repo),
            "--cursor-bin",
            str(FAKE),
            "--session-key",
            "test-session",
            *extra,
        ]

    def close(self) -> None:
        self.stack.cleanup()


class CursorCultUnitTests(unittest.TestCase):
    def test_roles_are_opaque_and_dynamic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roles.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "id": "user-requested-lens",
                            "label": "Whatever the user requested",
                            "instruction": ["Answer one exact question.", "Cite evidence."],
                            "mode": "ask",
                            "mode_reason": "The role only gathers evidence.",
                        }
                    ]
                )
            )
            roles = M.parse_roles(path)
            self.assertEqual(roles[0].id, "user-requested-lens")
            self.assertIn("Cite evidence", roles[0].instruction)
            self.assertEqual(
                roles[0].mode_reason,
                "The role only gathers evidence.",
            )

    def test_duplicate_role_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roles.json"
            path.write_text(
                json.dumps(
                    [
                        {"id": "same", "label": "A", "instruction": "A"},
                        {"id": "same", "label": "B", "instruction": "B"},
                    ]
                )
            )
            with self.assertRaises(M.UsageError):
                M.parse_roles(path)

    def test_intent_capsule_is_mandatory(self) -> None:
        with self.assertRaises(M.UsageError):
            M.validate_intent_capsule("# Current Phase Brief\nNo capsule")
        M.validate_intent_capsule(CAPSULE)

    def test_private_staging_is_enforced(self) -> None:
        fixture = Fixture()
        try:
            fixture.write_roles([{"id": "x", "label": "X", "instruction": "Inspect"}])
            M.validate_private_staging(fixture.roles, fixture.context)
            os.chmod(fixture.stage, 0o755)
            with self.assertRaises(M.UsageError):
                M.validate_private_staging(fixture.roles, fixture.context)
        finally:
            fixture.close()

    def test_both_api_environment_variables_are_stripped(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"CURSOR_API_KEY": "a", "CURSOR_AGENT_API_KEY": "b"},
            clear=False,
        ):
            env = M.sanitized_cursor_env()
        self.assertNotIn("CURSOR_API_KEY", env)
        self.assertNotIn("CURSOR_AGENT_API_KEY", env)

    def test_writer_prompt_does_not_expand_authority(self) -> None:
        role = M.Role("local-writer", "Local writer", "Implement the authorized local change", "agent")
        prompt = M.build_prompt(role, CAPSULE, True)
        self.assertIn("sole writer authorized for this worktree", prompt)
        self.assertIn("Do not commit, push, open or merge pull requests", prompt)
        reader = M.build_prompt(role, CAPSULE, False)
        self.assertIn("Work read-only", reader)

    def test_terminal_result_is_authoritative_and_unknown_fields_are_ignored(self) -> None:
        accumulator = M.StreamAccumulator()
        accumulator.ingest(json.dumps({"type": "assistant", "message": {"content": [{"type": "text", "text": "delta"}]}}))
        accumulator.ingest(json.dumps({"type": "future", "new": {"field": True}}))
        self.assertFalse(accumulator.terminal_seen)
        accumulator.ingest(json.dumps({"type": "result", "subtype": "success", "is_error": False, "result": "final"}))
        self.assertTrue(accumulator.terminal_seen)
        self.assertEqual(accumulator.terminal_result, "final")

    def test_session_state_is_scoped_by_host_session(self) -> None:
        root = Path("/tmp/example").resolve()
        one = M.role_state_path(root, "claude:one", "same-role")
        two = M.role_state_path(root, "claude:two", "same-role")
        self.assertNotEqual(one, two)

    def test_headless_gates_are_pre_answered(self) -> None:
        role = M.Role("reader", "Reader", "Investigate", "ask")
        args = M.build_cursor_args("cursor-agent", role, "prompt", None, False, FULL_CAPS)
        self.assertIn("--trust", args)
        self.assertIn("--approve-mcps", args)
        self.assertIn("--force", args)

    def test_agent_mode_is_never_passed_as_a_mode_value(self) -> None:
        writer = M.Role("writer", "Writer", "Implement", "agent")
        args = M.build_cursor_args("cursor-agent", writer, "prompt", None, True, FULL_CAPS)
        self.assertNotIn("--mode", args)
        reader = M.Role("reader", "Reader", "Investigate", "ask")
        args = M.build_cursor_args("cursor-agent", reader, "prompt", None, False, FULL_CAPS)
        self.assertEqual(args[args.index("--mode") + 1], "ask")
        planner = M.Role("planner", "Planner", "Plan", "plan")
        args = M.build_cursor_args("cursor-agent", planner, "prompt", None, False, FULL_CAPS)
        self.assertEqual(args[args.index("--mode") + 1], "plan")

    def test_agent_mode_notice_explains_risk_and_cli_compatibility(self) -> None:
        writer = M.Role("writer", "Writer", "Implement", "agent")
        notice = M.agent_mode_notice(
            [writer],
            {"writer"},
            execution="detached/background run",
        )
        self.assertIsNotNone(notice)
        assert notice is not None
        self.assertIn("can edit files and run commands", notice)
        self.assertIn("omitting `--mode`", notice)
        self.assertIn("only `ask` and `plan`", notice)
        self.assertIsNone(
            M.agent_mode_notice(
                [M.Role("reader", "Reader", "Inspect", "ask")],
                set(),
                execution="foreground run",
            )
        )

    def test_agent_mode_requires_writer_authorization(self) -> None:
        import asyncio

        async def fan_out() -> None:
            await M.execute_fleet(
                roles=[M.Role("sneaky", "Sneaky", "Implement", "agent")],
                context=CAPSULE,
                root=Path.cwd(),
                cli="cursor-agent",
                writer_ids=set(),
                max_parallel=0,
                resume=False,
                session_key="test:agent-mode",
                capabilities=FULL_CAPS,
                require_login_auth=True,
            )

        with self.assertRaises(M.UsageError):
            asyncio.run(fan_out())

    def test_writer_must_declare_agent_mode(self) -> None:
        # A writer left in the default read-only mode cannot edit; fail loudly
        # instead of running an appointed writer that silently changes nothing.
        roles = [M.Role("builder", "Builder", "Implement")]
        with self.assertRaises(M.UsageError):
            M.validate_write_authority(roles, {"builder"})
        M.validate_write_authority([M.Role("builder", "Builder", "Implement", "agent")], {"builder"})

    def test_terminal_event_is_recovered_if_state_outlives_journal_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            now = M.utc_now()
            M.atomic_write_json(
                run_dir / "state.json",
                {
                    "run_id": run_dir.name,
                    "status": "succeeded",
                    "created_at": now,
                    "started_at": now,
                    "finished_at": now,
                    "updated_at": now,
                    "event_sequence": 2,
                    "last_event_type": "run_completed",
                    "roles": [],
                },
            )
            M.append_event_line(
                run_dir / "events.ndjson",
                {
                    "schema": M.EVENT_SCHEMA,
                    "sequence": 1,
                    "run_id": run_dir.name,
                    "event": "run_started",
                },
            )
            state = M.ensure_terminal_event(run_dir, M.load_run_state(run_dir))
            events = [
                json.loads(line)
                for line in (run_dir / "events.ndjson").read_text().splitlines()
            ]
            self.assertEqual(state["status"], "succeeded")
            self.assertEqual(events[-1]["event"], "run_completed")
            self.assertTrue(events[-1]["details"]["recovered"])
            self.assertEqual(events[-1]["sequence"], 3)

    def test_queued_run_without_pid_fails_after_startup_grace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            old = (
                M.dt.datetime.now(M.dt.timezone.utc)
                - M.dt.timedelta(seconds=M.SUPERVISOR_START_GRACE_SECONDS + 1)
            ).isoformat()
            M.atomic_write_json(
                run_dir / "state.json",
                {
                    "run_id": run_dir.name,
                    "status": "queued",
                    "created_at": old,
                    "updated_at": old,
                    "event_sequence": 0,
                    "roles": [],
                },
            )
            state = M.reconcile_run_liveness(run_dir)
            self.assertEqual(state["status"], "failed")
            event = M.last_persisted_run_event(run_dir)
            self.assertIsNotNone(event)
            assert event is not None
            self.assertEqual(event["event"], "run_failed")
            self.assertIn("process id", event["details"]["reason"])

    def test_version_metadata_matches_runner(self) -> None:
        self.assertEqual(M.VERSION, "0.5.0")
        for path in (
            ROOT / "pyproject.toml",
            ROOT / ".claude-plugin" / "plugin.json",
            ROOT / ".codex-plugin" / "plugin.json",
            ROOT / "plugins" / "cursor-cult" / ".claude-plugin" / "plugin.json",
            ROOT / "plugins" / "cursor-cult-codex" / ".codex-plugin" / "plugin.json",
        ):
            content = path.read_text(encoding="utf-8")
            self.assertIn(M.VERSION, content, str(path))
            self.assertNotIn("0.4.1", content, str(path))

    def test_packaged_copies_match_their_sources(self) -> None:
        check = subprocess.run(
            [str(ROOT / "scripts" / "sync_packages.sh"), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(check.returncode, 0, check.stderr)


class CursorCultIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = Fixture()

    def tearDown(self) -> None:
        self.fixture.close()

    def run_cli(self, *args: str, env: dict[str, str] | None = None, timeout: float = 20) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(args),
            env=env or self.fixture.env(),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )

    def test_parallel_fleet_and_single_writer(self) -> None:
        self.fixture.write_roles(
            [
                {"id": "first-lens", "label": "First", "instruction": "Inspect first", "mode": "ask"},
                {"id": "local-change", "label": "Local change", "instruction": "Implement locally", "mode": "agent"},
            ]
        )
        result = self.run_cli(*self.fixture.command("run", "--writer", "local-change"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("handoff role=first-lens", result.stdout)
        self.assertIn("handoff role=local-change force=1", result.stdout)
        trace = self.fixture.trace.read_text()
        # Commands are auto-approved for every role; read-only is enforced by --mode,
        # and only the authorized writer runs in Cursor's default (agent) mode.
        self.assertIn("first-lens|force=1|trust=1|mode=ask", trace)
        self.assertIn("local-change|force=1|trust=1|mode=|", trace)
        self.assertIn("WARNING: foreground run includes Cursor agent mode", result.stderr)
        self.assertIn("omitting `--mode`", result.stderr)
        self.assertIn(M.DONE_SENTINEL, result.stderr)

    def test_partial_failure_preserves_success(self) -> None:
        self.fixture.write_roles(
            [
                {"id": "good", "label": "Good", "instruction": "Succeed"},
                {"id": "bad", "label": "Bad", "instruction": "Fail"},
            ]
        )
        result = self.run_cli(
            *self.fixture.command("run"),
            env=self.fixture.env(FAKE_CURSOR_FAIL_ROLES="bad"),
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("Fleet status: **partial**", result.stdout)
        self.assertIn("handoff role=good", result.stdout)
        self.assertIn("forced failure for bad", result.stdout)

    def test_oversized_stream_line_does_not_crash_the_fleet(self) -> None:
        # Regression: a single stream-json line past asyncio's default 64KiB
        # readline() limit used to raise LimitOverrunError and take the whole
        # fleet down with it -- including this sibling's already-good result.
        self.fixture.write_roles(
            [
                {"id": "huge-lens", "label": "Huge", "instruction": "Return a huge line"},
                {"id": "good", "label": "Good", "instruction": "Succeed"},
            ]
        )
        result = self.run_cli(
            *self.fixture.command("run"),
            env=self.fixture.env(FAKE_CURSOR_HUGE_LINE_ROLES="huge-lens"),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Fleet status: **succeeded**", result.stdout)
        self.assertIn("handoff role=good", result.stdout)
        # Proves the line was read intact (not truncated/dropped) past the old limit.
        self.assertIn("END_OF_HUGE_LINE", result.stdout)

    def test_run_persists_role_results_for_recovery(self) -> None:
        self.fixture.write_roles([{"id": "good", "label": "Good", "instruction": "Succeed"}])
        result = self.run_cli(*self.fixture.command("run"))
        self.assertEqual(result.returncode, 0, result.stderr)
        match = re.search(r"role logs and results persisting to: (\S+)", result.stderr)
        self.assertIsNotNone(match, result.stderr)
        run_dir = Path(match.group(1))
        payload = json.loads((run_dir / "roles" / "good.result.json").read_text())
        self.assertTrue(payload["ok"])
        self.assertIn("handoff role=good", payload["text"])
        self.assertTrue((run_dir / "report.md").exists())
        self.assertTrue((run_dir / "report.json").exists())

    def test_max_parallel_defaults_to_uncapped(self) -> None:
        roles = [{"id": f"sleepy-{i}", "label": f"Sleepy {i}", "instruction": "Inspect"} for i in range(8)]
        self.fixture.write_roles(roles)
        role_ids = ",".join(r["id"] for r in roles)
        started = time.monotonic()
        result = self.run_cli(
            *self.fixture.command("run"),
            env=self.fixture.env(FAKE_CURSOR_SLEEP_ROLES=role_ids, FAKE_CURSOR_SLEEP_SECS="3"),
            timeout=60,
        )
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        # One concurrent wave is ~3s; any reintroduced ceiling makes 8 roles take
        # two waves (>=6s). The long sleep keeps process-spawn overhead on a busy
        # CI runner well inside the margin.
        self.assertLess(elapsed, 5.0, "roles did not run concurrently -- max-parallel default regressed")

    def test_max_parallel_explicit_throttle_still_works(self) -> None:
        roles = [{"id": f"throttled-{i}", "label": f"T{i}", "instruction": "Inspect"} for i in range(4)]
        self.fixture.write_roles(roles)
        role_ids = ",".join(r["id"] for r in roles)
        started = time.monotonic()
        result = self.run_cli(
            *self.fixture.command("run", "--max-parallel", "2"),
            env=self.fixture.env(FAKE_CURSOR_SLEEP_ROLES=role_ids, FAKE_CURSOR_SLEEP_SECS="1"),
            timeout=30,
        )
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertGreaterEqual(elapsed, 1.8, "explicit --max-parallel throttle was not honored")

    def test_empty_or_missing_terminal_result_is_failure(self) -> None:
        self.fixture.write_roles([{"id": "empty", "label": "Empty", "instruction": "Return empty"}])
        empty = self.run_cli(
            *self.fixture.command("run"),
            env=self.fixture.env(FAKE_CURSOR_EMPTY_RESULT_ROLES="empty"),
        )
        self.assertEqual(empty.returncode, 1)
        self.assertIn("terminal result was empty", empty.stdout)

        self.fixture.write_roles([{"id": "missing", "label": "Missing", "instruction": "No result"}])
        missing = self.run_cli(
            *self.fixture.command("run", "--session-key", "other"),
            env=self.fixture.env(FAKE_CURSOR_NO_RESULT_ROLES="missing"),
        )
        self.assertEqual(missing.returncode, 1)
        self.assertIn("without a terminal result", missing.stdout)

    def test_browser_login_source_is_required(self) -> None:
        self.fixture.write_roles([{"id": "auth", "label": "Auth", "instruction": "Inspect"}])
        denied = self.run_cli(
            *self.fixture.command("run"),
            env=self.fixture.env(FAKE_CURSOR_AUTH_SOURCE="env"),
        )
        self.assertEqual(denied.returncode, 1)
        self.assertIn("requires browser-login", denied.stdout)

        allowed = self.run_cli(
            *self.fixture.command("run", "--allow-non-login-auth", "--session-key", "override"),
            env=self.fixture.env(FAKE_CURSOR_AUTH_SOURCE="env"),
        )
        self.assertEqual(allowed.returncode, 0, allowed.stderr)

    def test_role_session_resumes_and_stale_session_retries_once(self) -> None:
        self.fixture.write_roles([{"id": "continuing-lens", "label": "Continuing", "instruction": "Continue"}])
        first = self.run_cli(*self.fixture.command("run"))
        second = self.run_cli(*self.fixture.command("run"))
        self.assertEqual(first.returncode, 0)
        self.assertEqual(second.returncode, 0)
        lines = self.fixture.trace.read_text().splitlines()
        self.assertIn("resume=session-continuing-lens", lines[-1])

        with mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(self.fixture.state)}):
            state_path = M.role_state_path(self.fixture.repo.resolve(), "test-session", "continuing-lens")
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({"session_id": "stale"}))
        stale = self.run_cli(*self.fixture.command("run"))
        self.assertEqual(stale.returncode, 0, stale.stderr)
        stale_lines = self.fixture.trace.read_text().splitlines()[-2:]
        self.assertIn("resume=stale", stale_lines[0])
        self.assertIn("resume=", stale_lines[1])

    def test_check_reports_dynamic_roles_and_stripped_auth(self) -> None:
        self.fixture.write_roles([{"id": "odd-task-lens", "label": "Odd task", "instruction": "Inspect"}])
        result = self.run_cli(*self.fixture.command("check"))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["roles"][0]["id"], "odd-task-lens")
        self.assertEqual(set(payload["api_environment_stripped"]), {"CURSOR_API_KEY", "CURSOR_AGENT_API_KEY"})
        self.assertEqual(payload["warnings"], [])

    def test_background_start_wait_collect_with_mixed_modes(self) -> None:
        self.fixture.write_roles(
            [
                {
                    "id": "background-ask",
                    "label": "Background ask",
                    "instruction": "Inspect",
                    "mode": "ask",
                },
                {
                    "id": "background-plan",
                    "label": "Background plan",
                    "instruction": "Plan",
                    "mode": "plan",
                },
                {
                    "id": "background-writer",
                    "label": "Background writer",
                    "instruction": "Implement",
                    "mode": "agent",
                },
            ]
        )
        started = self.run_cli(
            *self.fixture.command("start", "--writer", "background-writer")
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertIn(
            "WARNING: detached/background run includes Cursor agent mode",
            started.stderr,
        )
        self.assertIn("omitting `--mode`", started.stderr)
        run_id = started.stdout.strip()
        self.assertRegex(run_id, r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")

        status = self.run_cli(
            sys.executable,
            str(RUNNER),
            "status",
            run_id,
            "--json",
            env=self.fixture.env(),
        )
        self.assertEqual(status.returncode, 0, status.stderr)
        state = json.loads(status.stdout)
        self.assertTrue(state["warnings"])
        self.assertEqual(
            {role["id"]: role["mode"] for role in state["roles"]},
            {
                "background-ask": "ask",
                "background-plan": "plan",
                "background-writer": "agent",
            },
        )

        wait = self.run_cli(
            sys.executable,
            str(RUNNER),
            "wait",
            run_id,
            "--poll",
            "0.05",
            env=self.fixture.env(),
        )
        self.assertEqual(wait.returncode, 0, wait.stderr)
        self.assertIn("succeeded", wait.stdout)

        collected = self.run_cli(
            sys.executable,
            str(RUNNER),
            "collect",
            run_id,
            env=self.fixture.env(),
        )
        self.assertEqual(collected.returncode, 0)
        self.assertIn("handoff role=background-ask", collected.stdout)
        self.assertIn("handoff role=background-plan", collected.stdout)
        self.assertIn("handoff role=background-writer", collected.stdout)
        trace = self.fixture.trace.read_text()
        self.assertIn("background-ask|force=1|trust=1|mode=ask", trace)
        self.assertIn("background-plan|force=1|trust=1|mode=plan", trace)
        self.assertIn("background-writer|force=1|trust=1|mode=|", trace)


    def test_background_watchdog_emits_heartbeat_and_completion(self) -> None:
        self.fixture.write_roles(
            [
                {
                    "id": "watchdog-lens",
                    "label": "Watchdog",
                    "instruction": "Inspect slowly",
                    "mode": "ask",
                    "mode_reason": "Read-only evidence collection.",
                }
            ]
        )
        started = self.run_cli(
            *self.fixture.command(
                "start",
                "--json",
                "--heartbeat-seconds",
                "0.10",
            ),
            env=self.fixture.env(
                FAKE_CURSOR_SLEEP_ROLES="watchdog-lens",
                FAKE_CURSOR_SLEEP_SECS="0.35",
            ),
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        launch = json.loads(started.stdout)
        self.assertEqual(launch["event_schema"], M.EVENT_SCHEMA)
        self.assertEqual(launch["heartbeat_seconds"], 0.10)
        self.assertEqual(launch["watch_command"][-3:], [launch["run_id"], "--format", "jsonl"])

        watched = self.run_cli(
            sys.executable,
            str(RUNNER),
            "watch",
            launch["run_id"],
            "--poll",
            "0.02",
            env=self.fixture.env(),
            timeout=10,
        )
        self.assertEqual(watched.returncode, 0, watched.stderr)
        events = [json.loads(line) for line in watched.stdout.splitlines() if line.strip()]
        event_names = [event["event"] for event in events]
        self.assertIn("heartbeat", event_names)
        self.assertEqual(event_names[-1], "run_completed")
        sequences = [event["sequence"] for event in events]
        self.assertEqual(sequences, sorted(set(sequences)))
        heartbeat = next(event for event in events if event["event"] == "heartbeat")
        self.assertEqual(heartbeat["details"]["heartbeat_seconds"], 0.10)
        self.assertIn("still running", heartbeat["message"])
        terminal = events[-1]
        self.assertEqual(terminal["status"], "succeeded")
        self.assertTrue(Path(terminal["details"]["report_markdown"]).exists())

        state = json.loads(Path(launch["run_dir"]).joinpath("state.json").read_text())
        self.assertIsNotNone(state["last_heartbeat_at"])
        self.assertEqual(state["last_event_type"], "run_completed")
        self.assertEqual(state["roles"][0]["mode_reason"], "Read-only evidence collection.")

    def test_watch_after_sequence_replays_only_newer_events(self) -> None:
        self.fixture.write_roles([{"id": "quick", "label": "Quick", "instruction": "Inspect"}])
        started = self.run_cli(*self.fixture.command("start", "--json"))
        self.assertEqual(started.returncode, 0, started.stderr)
        launch = json.loads(started.stdout)
        wait = self.run_cli(
            sys.executable,
            str(RUNNER),
            "wait",
            launch["run_id"],
            "--poll",
            "0.02",
            env=self.fixture.env(),
        )
        self.assertEqual(wait.returncode, 0, wait.stderr)
        all_events = [
            json.loads(line)
            for line in Path(launch["events_path"]).read_text().splitlines()
            if line.strip()
        ]
        cutoff = all_events[-2]["sequence"]
        watched = self.run_cli(
            sys.executable,
            str(RUNNER),
            "watch",
            launch["run_id"],
            "--after-sequence",
            str(cutoff),
            "--poll",
            "0.02",
            env=self.fixture.env(),
        )
        replay = [json.loads(line) for line in watched.stdout.splitlines() if line.strip()]
        self.assertEqual([event["sequence"] for event in replay], [all_events[-1]["sequence"]])
        self.assertEqual(replay[0]["event"], "run_completed")

    def test_all_role_failure_emits_run_failed_terminal_event(self) -> None:
        self.fixture.write_roles(
            [{"id": "doomed", "label": "Doomed", "instruction": "Fail"}]
        )
        started = self.run_cli(
            *self.fixture.command("start", "--heartbeat-seconds", "0.05", "--json"),
            env=self.fixture.env(FAKE_CURSOR_FAIL_ROLES="doomed"),
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        launch = json.loads(started.stdout)
        watched = self.run_cli(
            *launch["watch_command"],
            "--poll",
            "0.02",
            env=self.fixture.env(FAKE_CURSOR_FAIL_ROLES="doomed"),
        )
        self.assertEqual(watched.returncode, 0, watched.stderr)
        events = [json.loads(line) for line in watched.stdout.splitlines() if line.strip()]
        self.assertEqual(events[-1]["event"], "run_failed")
        self.assertEqual(events[-1]["status"], "failed")

    def test_background_cancel_terminates_worker(self) -> None:
        self.fixture.write_roles([{"id": "slow-lens", "label": "Slow", "instruction": "Inspect slowly"}])
        started = self.run_cli(
            *self.fixture.command("start"),
            env=self.fixture.env(FAKE_CURSOR_SLEEP_ROLES="slow-lens", FAKE_CURSOR_SLEEP_SECS="10"),
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        run_id = started.stdout.strip()

        deadline = time.time() + 5
        while time.time() < deadline:
            status = self.run_cli(
                sys.executable,
                str(RUNNER),
                "status",
                run_id,
                "--json",
                env=self.fixture.env(),
            )
            payload = json.loads(status.stdout)
            if payload.get("status") == "running":
                break
            time.sleep(0.05)
        else:
            self.fail("background run never entered running state")

        cancelled = self.run_cli(
            sys.executable,
            str(RUNNER),
            "cancel",
            run_id,
            env=self.fixture.env(),
        )
        self.assertEqual(cancelled.returncode, 0)

        terminal = self.run_cli(
            sys.executable,
            str(RUNNER),
            "wait",
            run_id,
            "--poll",
            "0.05",
            env=self.fixture.env(),
        )
        self.assertEqual(terminal.returncode, 130)
        self.assertIn("cancelled", terminal.stdout)


if __name__ == "__main__":
    unittest.main()
