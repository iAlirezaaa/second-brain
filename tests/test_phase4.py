"""Phase 4 tests: keyword KB + golden retrieval eval gate.

Phase 27 re-pointed the corpus from `vault-template/` to the brain's own tracked prose,
so the golden set below names the documents this repo actually carries. Every query must
rank its expected note FIRST; the queries use tokens only their target repeats often
enough to win under BM25. Persian matching is proven by the last row; Arabic/Persian letter
folding is proven by the shared fixture in `tests/test_phase27_repo_corpus.py`.

Measured 2026-10-28: four of the five cases sat within 0.14 BM25 units of the runner-up
(`plan apply approve` lost by 0.0006 after ordinary doc growth changed the global average
length), which is a coin flip, not a gate. The cases below were re-picked by measured margin
(1.23 to 3.74) and `test_every_case_is_decidable` holds the floor at 0.5.
"""
import re
import shutil
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import kb  # noqa: E402

MARGIN_FLOOR = 0.5
GOLDEN_SET = [
    ("orchestrator agentexecution", "02_WIKI/reference_maps/superagi-to-hades-map.md"),
    ("writer reader proof", "02_WIKI/reference_maps/eight-memory-planes.md"),
    ("charter audit yardstick", "00_START_HERE/CHARTER_AUDIT.md"),
    ("کنسول cp1252", "00_START_HERE/START.md"),
    ("هدف اصلی پروژه", "00_START_HERE/PROJECT_CHARTER.md"),
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

    def test_every_case_is_decidable(self):
        """A case whose runner-up is within the floor is a case defect, not a gate."""
        db = sqlite3.connect(str(ROOT / ".kb" / "kb.sqlite"))
        try:
            for query, expected in GOLDEN_SET:
                terms = kb.terms_of(query)
                rows = db.execute(
                    'SELECT n.path, bm25(fts) FROM fts JOIN notes n ON n.path = fts.path '
                    'WHERE fts MATCH ? ORDER BY bm25(fts) LIMIT 2',
                    (" AND ".join('"%s"' % term for term in terms),)).fetchall()
                self.assertTrue(rows, query)
                self.assertEqual(expected, rows[0][0], query)
                if len(rows) > 1:
                    margin = rows[1][1] - rows[0][1]
                    self.assertGreaterEqual(
                        margin, MARGIN_FLOOR,
                        "%r is a coin flip: %r vs %r (margin %.4f)"
                        % (query, rows[0], rows[1], margin))
        finally:
            db.close()

    def test_failed_search_logs_gap(self):
        probe = "zzznogapzzz-unfindable"
        result = run(["scripts/kb.py", "search", probe])
        self.assertEqual(result.returncode, 1)
        self.assertIn("logged as a knowledge gap", result.stdout)
        gaps = run(["scripts/kb.py", "gaps"])
        self.assertEqual(gaps.returncode, 0)
        self.assertIn(probe, gaps.stdout)

    def test_zone_tagged_in_results(self):
        result = run(["scripts/kb.py", "search", "کنسول cp1252"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("[00_START_HERE]", result.stdout, result.stdout)


if __name__ == "__main__":
    unittest.main()
