from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "cursor_delegate.py"
FAKE_CODEX = ROOT / "tests" / "fake_codex.sh"
FAKE_CLAUDE = ROOT / "tests" / "fake_claude.sh"
SPEC = importlib.util.spec_from_file_location("cursor_delegate", RUNNER)
assert SPEC and SPEC.loader
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)

CAPSULE = """# Intent Capsule

## Verbatim request
Delegate this exact task from Cursor.

## Authorized outcome
Return evidence and only authorized local changes.

## Hard constraints and non-goals
No remote side effects. Preserve unrelated work.

## Explicit lenses or panel requests
One Codex lens and one Claude lens.

## Authority boundaries
Read-only unless one exact writer is selected. No commit, push, PR, deploy, or publish.

## Acceptance evidence
Concrete paths, commands, outputs, risks, and unknowns.

# Current Phase Brief
Inspect the fixture repository.
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
                "FAKE_TRACE": str(self.trace),
                "FAKE_EXPECT_STRIPPED": "1",
                "OPENAI_API_KEY": "must-not-leak",
                "OPENAI_BASE_URL": "https://example.invalid",
                "CODEX_API_KEY": "must-not-leak",
                "ANTHROPIC_API_KEY": "must-not-leak",
                "ANTHROPIC_AUTH_TOKEN": "must-not-leak",
                "ANTHROPIC_BASE_URL": "https://example.invalid",
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
            "--codex-bin",
            str(FAKE_CODEX),
            "--claude-bin",
            str(FAKE_CLAUDE),
            "--session-key",
            "cursor:test",
            *extra,
        ]

    def close(self) -> None:
        self.stack.cleanup()


class UnitTests(unittest.TestCase):
    def test_dynamic_mixed_roles_parse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "roles.json"
            path.write_text(json.dumps([
                {"id": "runtime", "provider": "codex", "label": "Runtime", "instruction": "Trace it"},
                {"id": "design", "provider": "claude", "label": "Design", "instruction": ["Review", "Cite evidence"], "mode": "plan"},
            ]))
            roles = M.parse_roles(path)
            self.assertEqual([role.provider for role in roles], ["codex", "claude"])
            self.assertIn("Cite evidence", roles[1].instruction)

    def test_writer_authority_is_bidirectional(self) -> None:
        reader = M.DelegateRole("reader", "codex", "Reader", "Inspect")
        writer = M.DelegateRole("writer", "claude", "Writer", "Implement", "agent")
        with self.assertRaises(M.UsageError):
            M.validate_write_authority([writer], set())
        with self.assertRaises(M.UsageError):
            M.validate_write_authority([reader], {"reader"})
        M.validate_write_authority([reader, writer], {"writer"})

    def test_provider_commands_use_safe_modes(self) -> None:
        root = Path("/tmp/repo")
        codex = M.DelegateRole("c", "codex", "C", "Inspect")
        args = M.build_codex_args("codex", root, codex, None, False)
        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
        self.assertEqual(args[args.index("--ask-for-approval") + 1], "never")
        writer = M.DelegateRole("w", "claude", "W", "Write", "agent")
        args = M.build_claude_args("claude", root, writer, None, True, "system")
        self.assertEqual(args[args.index("--permission-mode") + 1], "bypassPermissions")

    def test_api_environment_is_stripped_per_provider(self) -> None:
        with mock.patch.dict(os.environ, {
            "OPENAI_API_KEY": "x", "OPENAI_BASE_URL": "y", "CODEX_API_KEY": "z",
            "ANTHROPIC_API_KEY": "a", "ANTHROPIC_AUTH_TOKEN": "b", "ANTHROPIC_BASE_URL": "c",
        }, clear=False):
            codex = M.sanitized_provider_env("codex", False)
            claude = M.sanitized_provider_env("claude", False)
        self.assertNotIn("OPENAI_API_KEY", codex)
        self.assertIn("ANTHROPIC_API_KEY", codex)
        self.assertNotIn("ANTHROPIC_API_KEY", claude)
        self.assertIn("OPENAI_API_KEY", claude)

    def test_delegation_depth_parsing_is_strict(self) -> None:
        with mock.patch.dict(os.environ, {"CURSOR_CULT_DELEGATION_DEPTH": "1"}, clear=False):
            self.assertEqual(M.delegation_depth(), 1)
        with mock.patch.dict(os.environ, {"CURSOR_CULT_DELEGATION_DEPTH": "bad"}, clear=False):
            with self.assertRaises(M.UsageError):
                M.delegation_depth()
        with mock.patch.dict(os.environ, {"CURSOR_CULT_DELEGATION_DEPTH": "-1"}, clear=False):
            with self.assertRaises(M.UsageError):
                M.delegation_depth()


class IntegrationTests(unittest.TestCase):
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

    def mixed_roles(self) -> list[dict[str, object]]:
        return [
            {"id": "codex-lens", "provider": "codex", "label": "Codex lens", "instruction": "Trace runtime evidence"},
            {"id": "claude-lens", "provider": "claude", "label": "Claude lens", "instruction": "Review architecture", "mode": "plan"},
        ]

    def test_check_probes_only_requested_authenticated_providers(self) -> None:
        self.fixture.write_roles(self.mixed_roles())
        result = self.run_cli(*self.fixture.command("check"))
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(set(payload["providers"]), {"codex", "claude"})
        self.assertEqual(payload["roles"], 2)

    def test_mixed_fleet_runs_and_strips_provider_env(self) -> None:
        self.fixture.write_roles(self.mixed_roles())
        result = self.run_cli(*self.fixture.command("run"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("codex handoff role=codex-lens", result.stdout)
        self.assertIn("claude handoff role=claude-lens", result.stdout)
        trace = self.fixture.trace.read_text()
        self.assertIn("--sandbox read-only", trace)
        self.assertIn("--permission-mode plan", trace)

    def test_one_writer_translates_to_provider_write_mode(self) -> None:
        self.fixture.write_roles([
            {"id": "reader", "provider": "codex", "label": "Reader", "instruction": "Inspect"},
            {"id": "writer", "provider": "claude", "label": "Writer", "instruction": "Implement", "mode": "agent"},
        ])
        result = self.run_cli(*self.fixture.command("run", "--writer", "writer"))
        self.assertEqual(result.returncode, 0, result.stderr)
        trace = self.fixture.trace.read_text()
        self.assertIn("claude|writer|", trace)
        self.assertIn("--permission-mode bypassPermissions", trace)

    def test_partial_failure_preserves_sibling_handoff(self) -> None:
        self.fixture.write_roles(self.mixed_roles())
        result = self.run_cli(
            *self.fixture.command("run"),
            env=self.fixture.env(FAKE_FAIL_ROLES="claude-lens"),
        )
        self.assertEqual(result.returncode, 3)
        self.assertIn("Fleet status: **partial**", result.stdout)
        self.assertIn("codex handoff role=codex-lens", result.stdout)
        self.assertIn("forced failure for claude-lens", result.stdout)

    def test_sessions_resume_and_stale_resume_retries_fresh(self) -> None:
        self.fixture.write_roles([
            {"id": "codex-lens", "provider": "codex", "label": "Codex", "instruction": "Inspect"},
            {"id": "claude-lens", "provider": "claude", "label": "Claude", "instruction": "Inspect"},
        ])
        first = self.run_cli(*self.fixture.command("run"))
        self.assertEqual(first.returncode, 0, first.stderr)
        second = self.run_cli(
            *self.fixture.command("run"),
            env=self.fixture.env(FAKE_STALE_ON_RESUME_ROLES="codex-lens,claude-lens"),
        )
        self.assertEqual(second.returncode, 0, second.stderr)
        trace = self.fixture.trace.read_text()
        self.assertGreaterEqual(trace.count("codex|codex-lens|"), 3)
        self.assertGreaterEqual(trace.count("claude|claude-lens|"), 3)

    def test_default_concurrency_is_uncapped(self) -> None:
        roles = [
            {"id": "codex-a", "provider": "codex", "label": "A", "instruction": "Inspect"},
            {"id": "claude-b", "provider": "claude", "label": "B", "instruction": "Inspect"},
        ]
        self.fixture.write_roles(roles)
        started = time.monotonic()
        result = self.run_cli(
            *self.fixture.command("run"),
            env=self.fixture.env(FAKE_SLEEP_ROLES="codex-a,claude-b", FAKE_SLEEP_SECS="2"),
            timeout=10,
        )
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertLess(elapsed, 3.5)

    def test_private_staging_and_recursion_gate(self) -> None:
        self.fixture.write_roles(self.mixed_roles())
        os.chmod(self.fixture.stage, 0o755)
        unsafe = self.run_cli(*self.fixture.command("check"))
        self.assertEqual(unsafe.returncode, 2)
        self.assertIn("mode 0700", unsafe.stderr)
        os.chmod(self.fixture.stage, 0o700)
        nested = self.run_cli(
            *self.fixture.command("check"),
            env=self.fixture.env(CURSOR_CULT_DELEGATION_DEPTH="1"),
        )
        self.assertEqual(nested.returncode, 2)
        self.assertIn("nested delegation is blocked", nested.stderr)

    def test_cursor_skill_installer_copy_mode(self) -> None:
        destination = self.fixture.root / "cursor-home" / "skills" / "cursor-cult-delegate"
        result = self.run_cli(
            str(ROOT / "scripts" / "install_cursor.sh"),
            "--copy",
            "--dest",
            str(destination),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((destination / "SKILL.md").exists())
        self.assertFalse(destination.is_symlink())

    def test_bin_wrapper_routes_delegate_subcommand(self) -> None:
        result = self.run_cli(str(ROOT / "bin" / "cursor-cult"), "delegate", "--version")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), M.VERSION)


if __name__ == "__main__":
    unittest.main()
