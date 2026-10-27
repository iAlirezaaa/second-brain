"""Phase 7 tests: the improvement loop ratchet."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

NOTE_BAD = """---
id: note-broken
type: note
title: Missing fields on purpose
status: raw
owner: human
created: 2026-01-01
updated: 2026-01-01
---
Topics field is deliberately absent.
"""


def run_loop(tmp, extra=None):
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "loop.py"), "--root", str(tmp),
         "--no-tests", "--vault", str(tmp / "vault-template")] + (extra or []),
        capture_output=True, text=True)


def build_house(tmp, note_text):
    shutil.copytree(ROOT / "rules", tmp / "rules")
    vault = tmp / "vault-template"
    vault.mkdir(parents=True, exist_ok=True)
    (vault / "keep.md").write_text(note_text, encoding="utf-8")


class TestLoop(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_first_cycle_sets_baseline_and_reports_candidate(self):
        build_house(self.tmp, NOTE_BAD)
        result = run_loop(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)  # P1 = red house
        self.assertIn("P1", result.stdout)
        report_dir = self.tmp / "14_CANDIDATES" / "loop"
        reports = list(report_dir.glob("report-*.md"))
        self.assertTrue(reports, "no report written")
        text = reports[0].read_text(encoding="utf-8")
        self.assertIn("frontmatter_check", text)
        self.assertIn("baseline", text)  # first run recorded

    def test_no_new_failure_is_stable_not_regressed(self):
        build_house(self.tmp, NOTE_BAD)
        run_loop(self.tmp)
        result = run_loop(self.tmp)
        report_files = list((self.tmp / "14_CANDIDATES" / "loop").glob("report-*.md"))
        self.assertEqual(len(report_files), 2)  # cycle 1 + cycle 2 (-c2)
        newest = max(report_files, key=lambda p: p.stat().st_mtime)
        self.assertIn("-c2", newest.name)
        second = newest.read_text(encoding="utf-8")
        self.assertNotIn("REGRESSED", second, second)
        self.assertIn("stable", second)

    def test_regression_detected_when_situation_worsens(self):
        build_house(self.tmp, NOTE_BAD)
        run_loop(self.tmp)
        # worsen: add a second broken note -> more integrity problems
        (self.tmp / "vault-template" / "worse.md").write_text(
            NOTE_BAD.replace("id: note-broken", "id: note-worse"), encoding="utf-8")
        result = run_loop(self.tmp)
        self.assertEqual(result.returncode, 1)
        reports = list((self.tmp / "14_CANDIDATES" / "loop").glob("report-*.md"))
        newest = max(reports, key=lambda p: p.stat().st_mtime)
        third = newest.read_text(encoding="utf-8")
        self.assertIn("REGRESSED", third)
        self.assertIn("integrity_problems", third)

    def test_report_is_a_valid_note_candidate_with_frontmatter(self):
        build_house(self.tmp, NOTE_BAD)
        run_loop(self.tmp)
        report = sorted((self.tmp / "14_CANDIDATES" / "loop").glob("report-*.md"))[0]
        sys.path.insert(0, str(ROOT / "scripts"))
        import importlib
        common = importlib.import_module("common")
        fm, _ = common.parse_frontmatter(report.read_text(encoding="utf-8"))
        self.assertEqual(fm.get("owner"), "agent")
        self.assertEqual(fm.get("status"), "raw")

    def test_shipped_repo_cycle_runs_green(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "loop.py"), "--no-tests",
             "--vault", str(ROOT / "vault-template"), "--root", str(self.tmp)],
            capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
