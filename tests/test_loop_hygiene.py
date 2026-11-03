"""Regression coverage: actionable hygiene is not source-string coincidence."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import loop  # noqa: E402


class HygieneSignalTests(unittest.TestCase):
    def test_python_docstrings_and_regex_literals_do_not_count_as_debt(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "scripts"
            folder.mkdir()
            (folder / "run.py").write_text(
                '"""A documentation-only example with TODO and FIXME words."""\n'
                'import re\n'
                'PATTERN = re.compile(r"TODO|FIXME|XXX")\n'
                'print(PATTERN)\n', encoding="utf-8")
            signal = loop.hygiene(root)
            self.assertEqual(0, signal["todo_hygiene"])
            self.assertEqual(1, signal["files_scanned"])

    def test_explicit_python_comment_and_skill_task_are_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "scripts").mkdir()
            (root / "skills" / "demo").mkdir(parents=True)
            (root / "scripts" / "run.py").write_text(
                "# TODO: test migration\n"
                'TEXT = "TODO is just prose"\n'
                "# FIXME: add rollback\n", encoding="utf-8")
            (root / "skills" / "demo" / "SKILL.md").write_text(
                "- TODO: verify expected output\n", encoding="utf-8")
            signal = loop.hygiene(root)
            self.assertEqual(3, signal["todo_hygiene"])
            self.assertEqual(2, signal["files_scanned"])


if __name__ == "__main__":
    unittest.main()
