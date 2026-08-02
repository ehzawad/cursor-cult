import importlib.util, json, os, sys, tempfile, unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location("cursor_cult", Path(__file__).parents[1] / "scripts/cursor_cult.py")
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)

class CultTests(unittest.TestCase):
    def test_roles(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            p.write_text(json.dumps([{"id":"risk","label":"Risk","instruction":["Find failures.","Report evidence."],"mode":"ask"}]))
            roles = M.parse_roles(p)
            self.assertEqual(roles[0].id, "risk")
            self.assertIn("evidence", roles[0].instruction)

    def test_duplicate_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "r.json"
            p.write_text(json.dumps([{"id":"x","label":"X","instruction":"a"},{"id":"x","label":"Y","instruction":"b"}]))
            with self.assertRaises(ValueError):
                M.parse_roles(p)

    def test_stream_parser(self):
        data = (json.dumps({"type":"assistant","message":{"content":[{"type":"text","text":"hello"}]},"session_id":"s1"}) + "\n" + json.dumps({"type":"result","result":"done","session_id":"s1"})).encode()
        text, sid = M.parse_stream(data)
        self.assertEqual(text, "hello")
        self.assertEqual(sid, "s1")

    def test_env_strips_api_keys(self):
        os.environ["CURSOR_API_KEY"] = "secret"
        os.environ.pop("CURSOR_CULT_KEEP_CURSOR_API_ENV", None)
        self.assertNotIn("CURSOR_API_KEY", M.clean_env())

    def test_prompt_postures(self):
        role = M.Role("a", "A", "inspect")
        self.assertIn("Do not modify files", M.build_prompt(role, "task", False))
        self.assertIn("sole authorized writer", M.build_prompt(role, "task", True))

if __name__ == "__main__":
    unittest.main()
