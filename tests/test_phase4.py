"""Phase 4 tests: keyword KB + golden retrieval eval gate.

Phase 27 re-pointed the corpus from `vault-template/` to the brain's own tracked prose,
so the golden set below names the documents this repo actually carries. Every query must
rank its expected note FIRST; the queries use tokens only their target repeats often
enough to win under BM25, and the Persian row proves the Arabic/Persian letter folding.
"""
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

GOLDEN_SET = [
    ("superagi to hades map", "02_WIKI/reference_maps/superagi-to-hades-map.md"),
    ("writer reader proof", "02_WIKI/reference_maps/eight-memory-planes.md"),
    ("charter audit", "00_START_HERE/CHARTER_AUDIT.md"),
    ("plan apply approve", "00_START_HERE/START.md"),
    ("حافظه", "00_START_HERE/PROJECT_CHARTER.md"),
]


def run(cmd, **kwargs):
    # Encoding is stated, not inherited: the Persian golden row crosses a cp1252 console
    # on Windows and a crashed parent reads exactly like a gate with no output.
    return subprocess.run([sys.executable] + cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", cwd=str(ROOT), **kwargs)


class TestKB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shutil.rmtree(ROOT / ".kb", ignore_errors=True)  # clean slate per test run
        result = run(["scripts/kb.py", "ingest"])
        assert result.returncode == 0, result.stdout + result.stderr
        cls.indexed = result.stdout

    def test_ingest_indexes_the_tracked_corpus(self):
        match = re.search(r"indexed (\d+) notes", self.indexed)
        self.assertIsNotNone(match, self.indexed)
        # 43 at phase 27; the floor is what keeps a silent corpus loss from passing.
        self.assertGreaterEqual(int(match.group(1)), 40, self.indexed)

    def test_golden_eval_gate(self):
        failures = []
        for query, expected in GOLDEN_SET:
            result = run(["scripts/kb.py", "search", query])
            paths = [line.split("  ")[0] for line in result.stdout.splitlines() if "  [" in line]
            if not paths or paths[0] != expected:
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
        result = run(["scripts/kb.py", "search", "plan apply approve"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("[00_START_HERE]", result.stdout, result.stdout)


if __name__ == "__main__":
    unittest.main()
