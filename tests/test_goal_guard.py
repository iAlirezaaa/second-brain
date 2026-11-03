"""Regression tests for the protected goal and founding-archive gate."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("goal_guard", str(ROOT / "scripts" / "goal_guard.py"))
goal_guard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(goal_guard)


class GoalGuardTests(unittest.TestCase):
    def test_real_repo_has_frozen_origins_and_goal(self):
        self.assertEqual([], goal_guard.audit(ROOT))

    def test_git_blob_hash_is_length_delimited(self):
        self.assertEqual("ce013625030ba8dba906f756967f9e9ca394464a",
                         goal_guard.git_blob_sha(b"hello\n"))

    def test_missing_frozen_original_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            problems = goal_guard.audit(tmp, frozen={"old.snapshot.txt": "a" * 40}, required={})
            self.assertTrue(any("missing or unsafe frozen idea" in p for p in problems))

    def test_any_change_to_frozen_original_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "idea.txt"
            path.write_text("original identity", encoding="utf-8")
            original = goal_guard.git_blob_sha(path.read_bytes())
            self.assertEqual([], goal_guard.audit(tmp, frozen={"idea.txt": original}, required={}))
            path.write_text("changed identity", encoding="utf-8")
            self.assertTrue(any("frozen idea modified" in p for p in
                                goal_guard.audit(tmp, frozen={"idea.txt": original}, required={})))

    def test_goal_references_are_required(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "GOAL.md"
            path.write_text("human and agent", encoding="utf-8")
            problems = goal_guard.audit(tmp, frozen={}, required={"GOAL.md": ("human", "archive")})
            self.assertTrue(any("reference 'archive' missing" in p for p in problems))


if __name__ == "__main__":
    unittest.main()
