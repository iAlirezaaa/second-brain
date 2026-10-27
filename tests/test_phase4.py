"""Phase 4 tests: keyword KB + golden retrieval eval gate."""
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Golden set: every query must rank the expected note FIRST.
# Queries use tokens unique to their target so rank-1 is well-defined;
# generic queries deliberately fall into the gap register instead.
GOLDEN_SET = [
    ("media alias left in brackets", "_templates/note-resource.md"),
    ("frontmatter_check", "AGENTS.md"),
    ("status lifecycle", "index.md"),
    ("session-log", "AGENTS.md"),
]


def run(cmd, **kwargs):
    return subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                          cwd=str(ROOT), **kwargs)


class TestKB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shutil.rmtree(ROOT / ".kb", ignore_errors=True)  # clean slate per test run
        result = run(["scripts/kb.py", "ingest"])
        assert result.returncode == 0, result.stdout + result.stderr
        cls.indexed = result.stdout

    def test_ingest_indexes_every_markdown_note(self):
        self.assertRegex(self.indexed, r"indexed \d+ notes")

    def test_golden_eval_gate(self):
        failures = []
        for query, expected in GOLDEN_SET:
            result = run(["scripts/kb.py", "search", query])
            hits = [line for line in result.stdout.splitlines() if line.startswith(tuple(
                str(-i) for i in range(10)))] or []
            paths = [line.split("  ")[0] for line in result.stdout.splitlines()
                     if "  [" in line]
            if not paths or paths[0].replace("vault-template/", "") != expected:
                failures.append(f"query={query!r} expected={expected!r} got={paths[:3]}")
        self.maxDiff = None
        self.assertEqual(failures, [], "retrieval regression:\n" + "\n".join(failures))

    def test_failed_search_logs_gap(self):
        probe = "zzznogapzzz-unfindable"
        result = run(["scripts/kb.py", "search", probe])
        self.assertEqual(result.returncode, 1)
        self.assertIn("logged as a knowledge gap", result.stdout)
        gaps = run(["scripts/kb.py", "gaps"])
        self.assertEqual(gaps.returncode, 0)
        self.assertIn(probe, gaps.stdout)

    def test_zone_tagged_in_results(self):
        result = run(["scripts/kb.py", "search", "agent"])
        self.assertEqual(result.returncode, 0)
        self.assertTrue(re.search(r"\[root\]|\[90_Agent_Output\]", result.stdout),
                        result.stdout)


if __name__ == "__main__":
    unittest.main()
