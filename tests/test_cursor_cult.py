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
                        }
                    ]
                )
            )
            roles = M.parse_roles(path)
            self.assertEqual(roles[0].id, "user-requested-lens")
            self.assertIn("Cite evidence", roles[0].instruction)

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
        self.assertIn("first-lens|force=0", trace)
        self.assertIn("local-change|force=1", trace)
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
            env=self.fixture.env(FAKE_CURSOR_SLEEP_ROLES=role_ids, FAKE_CURSOR_SLEEP_SECS="1"),
            timeout=30,
        )
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 1.8, "roles did not run concurrently -- max-parallel default regressed")

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

    def test_background_start_wait_collect(self) -> None:
        self.fixture.write_roles([{"id": "background-lens", "label": "Background", "instruction": "Inspect"}])
        started = self.run_cli(*self.fixture.command("start"))
        self.assertEqual(started.returncode, 0, started.stderr)
        run_id = started.stdout.strip()
        self.assertRegex(run_id, r"^\d{8}T\d{6}Z-[0-9a-f]{8}$")

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
        self.assertIn("handoff role=background-lens", collected.stdout)

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
