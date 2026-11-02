"""Pure Twin World 1a file overlay contract; the real filesystem remains unchanged."""
import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import twin_world  # noqa: E402


class TwinWorldFilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "02_WIKI").mkdir()
        self.path = self.root / "02_WIKI" / "notes.md"
        self.path.write_text("First idea\n", encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def test_existing_file_changes_in_preview_only(self):
        before = self.path.read_bytes()
        result = twin_world.simulate(self.root, [
            {"op": "write", "path": "02_WIKI/notes.md", "text": "Second idea\n"}])
        row = result["files"][0]
        self.assertEqual("changed", row["outcome"])
        self.assertIn("-First idea", row["diff"])
        self.assertIn("+Second idea", row["diff"])
        self.assertEqual(hashlib.sha256(before).hexdigest(), row["before_sha256"])
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(0, result["files_written"])

    def test_multiple_operations_share_in_memory_overlay(self):
        result = twin_world.simulate(self.root, [
            {"op": "append", "path": "02_WIKI/notes.md", "text": "New line\n"},
            {"op": "append", "path": "02_WIKI/notes.md", "text": "Final line\n"}])
        self.assertIn("+New line", result["files"][0]["diff"])
        self.assertIn("+Final line", result["files"][0]["diff"])
        self.assertEqual("First idea\n", self.path.read_text(encoding="utf-8"))

    def test_virtual_delete_does_not_delete_file(self):
        result = twin_world.simulate(self.root, [
            {"op": "delete", "path": "02_WIKI/notes.md"}])
        self.assertEqual("deleted", result["files"][0]["outcome"])
        self.assertTrue(self.path.is_file())

    def test_virtual_file_create_does_not_write_file(self):
        target = self.root / "03_PROJECTS" / "plan.md"
        result = twin_world.simulate(self.root, [
            {"op": "write", "path": "03_PROJECTS/plan.md", "text": "Plan"}])
        self.assertEqual("added", result["files"][0]["outcome"])
        self.assertFalse(target.exists())

    def test_traversal_and_absolute_paths_rejected(self):
        for value in ("../secrets.md", "/etc/passwd"):
            with self.subTest(path=value):
                with self.assertRaisesRegex(twin_world.TwinRefused, "absolute/traversal"):
                    twin_world.simulate(self.root, [{"op": "write", "path": value, "text": "x"}])

    def test_private_system_paths_rejected(self):
        for value in ("12_RUNTIME/history.txt", ".brain-data/x",
                      "09_OPERATIONS/record.md", "15_SYSTEM/generated/cache.json",
                      "15_SYSTEM/backups/test.md"):
            with self.subTest(path=value):
                with self.assertRaisesRegex(twin_world.TwinRefused, "private"):
                    twin_world.simulate(self.root, [{"op": "write", "path": value, "text": "x"}])

    def test_symlink_target_into_secret_is_rejected(self):
        secret_dir = self.root / ".secrets"
        secret_dir.mkdir()
        target = secret_dir / "private.md"
        target.write_text("SECRET", encoding="utf-8")
        link = self.root / "02_WIKI" / "alias.md"
        try:
            link.symlink_to(target)
        except OSError:
            self.skipTest("symlink unavailable")
        with self.assertRaisesRegex(twin_world.TwinRefused, "protected"):
            twin_world.simulate(self.root, [
                {"op": "append", "path": "02_WIKI/alias.md", "text": "x"}])

    def test_binary_and_large_file_refused(self):
        (self.root / "02_WIKI" / "binary.md").write_bytes(b"\xff\xfe")
        with self.assertRaisesRegex(twin_world.TwinRefused, "UTF-8"):
            twin_world.simulate(self.root, [
                {"op": "delete", "path": "02_WIKI/binary.md"}])
        with self.assertRaisesRegex(twin_world.TwinRefused, "too large"):
            twin_world.simulate(self.root, [
                {"op": "write", "path": "02_WIKI/notes.md", "text": "x" * 140000}])

    def test_unknown_operation_and_empty_plan_refused(self):
        for plan in ([], [{"op": "shell", "path": "02_WIKI/notes.md"}]):
            with self.assertRaises(twin_world.TwinRefused):
                twin_world.simulate(self.root, plan)

    def test_repeated_plan_is_deterministic(self):
        plan = [{"op": "append", "path": "02_WIKI/notes.md", "text": "Same\n"}]
        first = twin_world.simulate(self.root, plan)
        second = twin_world.simulate(self.root, plan)
        self.assertEqual(first, second)
        self.assertEqual(0, first["network_requests"])

    def test_append_to_nonexistent_file_refused(self):
        with self.assertRaisesRegex(twin_world.TwinRefused, "absent"):
            twin_world.simulate(self.root, [
                {"op": "append", "path": "02_WIKI/new.md", "text": "x"}])

    def test_simulated_write_does_not_mutate_any_directory(self):
        before = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        twin_world.simulate(self.root, [
            {"op": "write", "path": "02_WIKI/new.md", "text": "Hello"},
            {"op": "delete", "path": "02_WIKI/notes.md"}])
        after = sorted(p.relative_to(self.root) for p in self.root.rglob("*"))
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
