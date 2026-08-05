#!/usr/bin/env python3
"""Temporary guarded patch for watchdog regression tests and version metadata."""
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


tests = "tests/test_cursor_cult.py"
replace_once(
    tests,
    '''    def test_packaged_copies_match_their_sources(self) -> None:''',
    '''    def test_terminal_event_is_recovered_if_state_outlives_journal_append(self) -> None:
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

    def test_packaged_copies_match_their_sources(self) -> None:''',
)

for path in (
    Path("scripts/cursor_cult.py"),
    Path("pyproject.toml"),
    Path(".claude-plugin/plugin.json"),
    Path(".codex-plugin/plugin.json"),
    Path("plugins/cursor-cult/.claude-plugin/plugin.json"),
    Path("plugins/cursor-cult-codex/.codex-plugin/plugin.json"),
):
    content = path.read_text(encoding="utf-8")
    if "0.4.1" not in content:
        raise SystemExit(f"{path}: expected 0.4.1 version anchor")
    path.write_text(content.replace("0.4.1", "0.5.0"), encoding="utf-8")

print("watchdog tests and 0.5.0 metadata anchors applied")
