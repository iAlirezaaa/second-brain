"""Phase 18 tests — a number in a document is a claim, so the document measures itself (issues #4, #10).

The README once carried a hand-typed "tests: 39 green" badge while the suite had grown far
past it, and HANDOFF/START quoted a live-looking "zones present: 16/16 | registry records: 0"
that had been read off the owner's seeded folder. A fresh clone reproduced neither. These
tests judge the fix: the numbers are generated, and a stale one fails a gate.

  1. `--check` is a gate: a number that no longer matches reality exits 1;
  2. `--write` is idempotent and owns only the bytes between the markers;
  3. a document that never carries a block, or opens one it never closes, is refused;
  4. the measures come from code that is running, not from a remembered integer;
  5. HANDOFF §1 is stamped from the same measurement, so two documents cannot hold two truths.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import doc_report  # noqa: E402
from common import find_root, run_utf8  # noqa: E402

REPORT = str(SCRIPTS / "doc_report.py")
HANDOFF_SCRIPT = str(SCRIPTS / "handoff.py")


def run(root, *args):
    return run_utf8([sys.executable, REPORT, "--root", str(root)] + list(args), cwd=str(ROOT))


class Fixture(unittest.TestCase):
    """A repo-shaped folder: what the measurement reads has to exist, but it can be small."""

    def make(self, docs=("README.md", "HANDOFF.md", "00_START_HERE/START.md")):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "rules").mkdir()
        (self.root / "rules" / "zones.json").write_text(
            json.dumps({"zones": {"00_START_HERE": "start"}}), encoding="utf-8")
        config = {"zones": [{"dir": "00_START_HERE"}, {"dir": "12_RUNTIME"}],
                  "kinds": {"project": {}, "skill": {}},
                  "relations": {"depends_on": [], "parent_ids": []}}
        (self.root / "15_SYSTEM" / "config").mkdir(parents=True)
        (self.root / "15_SYSTEM" / "config" / "system.json").write_text(
            json.dumps(config), encoding="utf-8")
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "health.py").write_text("", encoding="utf-8")
        (self.root / "15_SYSTEM" / "memory").mkdir(parents=True)
        (self.root / "14_CANDIDATES" / "loop").mkdir(parents=True)
        for rel in docs:
            path = self.root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# %s\n\nprose that the report must not touch\n" % rel,
                            encoding="utf-8")
        return self.root


class TestTheGateIsReal(Fixture):
    def test_a_stale_number_fails_the_check(self):
        root = self.make()
        self.assertEqual(run(root, "--write").returncode, 0)
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if line.startswith("| health gates"))
        label = [cell.strip() for cell in row.strip().strip("|").split("|")][0]
        # forged by hand, exactly the way the old badge was: same label, invented number
        readme.write_text(text.replace(row, "| %s | 99 |" % label), encoding="utf-8")
        result = run(root, "--check")
        self.assertEqual(result.returncode, 1, "an invented number passed as measured")
        self.assertIn("STALE", result.stdout)
        self.assertIn("README.md", result.stdout)

    def test_a_missing_block_is_refused_then_written(self):
        root = self.make()
        result = run(root, "--check")
        self.assertEqual(result.returncode, 1, "a document with no measured block looked clean")
        self.assertIn("no measured block", result.stdout)
        self.assertEqual(run(root, "--write").returncode, 0)
        for rel in doc_report.DOCS:
            self.assertIn(doc_report.BEGIN, (root / rel).read_text(encoding="utf-8"))
        self.assertEqual(run(root, "--check").returncode, 0)
        self.assertIn("matches the state of this folder", run(root, "--check").stdout)

    def test_writing_twice_changes_nothing(self):
        """Idempotence is the difference between a generated block and a diff generator."""
        root = self.make()
        run(root, "--write")
        before = {rel: (root / rel).read_text(encoding="utf-8") for rel in doc_report.DOCS}
        self.assertEqual(run(root, "--write").returncode, 0)
        for rel, text in before.items():
            self.assertEqual((root / rel).read_text(encoding="utf-8"), text,
                             "%s moved on a second write" % rel)

    def test_the_markers_own_the_block_and_nothing_else(self):
        root = self.make()
        run(root, "--write")
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertIn("prose that the report must not touch", readme)
        self.assertLess(readme.index("# README.md"), readme.index(doc_report.BEGIN))

    def test_a_block_that_never_closes_is_refused_not_eaten(self):
        root = self.make()
        run(root, "--write")
        readme = root / "README.md"
        text = readme.read_text(encoding="utf-8").replace(doc_report.END, "")
        readme.write_text(text + "\nthe rest of the document\n", encoding="utf-8")
        result = run(root, "--write")
        self.assertEqual(result.returncode, 1,
                         "an unclosed marker swallowed the tail of the file")
        self.assertIn("never closes", result.stdout)
        self.assertIn("the rest of the document", readme.read_text(encoding="utf-8"))


class TestNumbersComeFromRunningCode(Fixture):
    def test_the_gate_count_is_the_list_in_health_py(self):
        """A remembered integer would have passed while the real gate list grew."""
        root = self.make()
        rows = dict((label.split(" (")[0], value)
                    for label, value in doc_report.measures(root))
        import health
        self.assertEqual(int(rows["health gates"]), len(health.GATES))
        self.assertGreaterEqual(len(health.GATES), 6)

    def test_the_test_count_is_discovered_not_typed(self):
        loader_cases = doc_report.collected_tests(ROOT)
        self.assertGreaterEqual(loader_cases, 150)
        self.assertEqual(loader_cases, doc_report.collected_tests(ROOT))

    def test_a_folder_without_tests_measures_zero_instead_of_crashing(self):
        root = self.make()
        self.assertEqual(doc_report.collected_tests(root), 0)
        self.assertEqual(run(root, "--write").returncode, 0)
        self.assertIn("| tests collected (`python -m unittest discover -s tests`) | 0 |",
                      (root / "README.md").read_text(encoding="utf-8"))

    def test_a_root_missing_its_config_is_named_not_silent(self):
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: __import__("shutil").rmtree(str(empty), ignore_errors=True))
        (empty / "rules").mkdir()
        (empty / "rules" / "zones.json").write_text('{"zones": {}}', encoding="utf-8")
        result = run(empty, "--check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("UNMEASURABLE", result.stdout)
        self.assertIn("15_SYSTEM/config/system.json", result.stdout)


class TestOneTruthPerNumber(Fixture):
    def test_handoff_section_one_carries_the_same_measurement(self):
        """handoff.py stamps §1 from doc_report; two documents cannot hold two counts."""
        root = self.make()
        self.assertEqual(run(root, "--write").returncode, 0)
        result = run_utf8([sys.executable, HANDOFF_SCRIPT, "--root", str(root),
                           "--head", "abc1234"], cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        text = (root / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn(doc_report.BEGIN, text)
        self.assertEqual(run(root, "--check").returncode, 0,
                         "the handoff and the doc report disagree about this repo")
        self.assertEqual(text.count(doc_report.BEGIN), 1, "two blocks in one document")

    def test_handoff_survives_a_root_it_cannot_measure(self):
        """A handoff is how the next session resumes; a failed measurement may not kill it."""
        root = self.make()
        (root / "15_SYSTEM" / "config" / "system.json").write_text("{ not json", encoding="utf-8")
        result = run_utf8([sys.executable, HANDOFF_SCRIPT, "--root", str(root),
                           "--head", "abc1234"], cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, "the handoff crashed instead of reporting")
        text = (root / "HANDOFF.md").read_text(encoding="utf-8")
        self.assertIn("FAILED", text)

    def test_the_shipped_documents_are_stamped_today(self):
        """Not a fixture: the real README, HANDOFF and START must pass their own gate."""
        real = find_root(Path(__file__))
        for rel in doc_report.DOCS:
            self.assertIn(doc_report.BEGIN, (real / rel).read_text(encoding="utf-8"),
                          "%s carries no measured block" % rel)
        self.assertEqual(run(real, "--check").returncode, 0,
                         "a number in the shipped documents is stale")

    def test_no_hand_typed_test_badge_survives_anywhere(self):
        """The old shields badge was the bug: a number with no measurement behind it."""
        for rel in list(doc_report.DOCS) + ["ROADMAP.md", "CHANGELOG.md", "AGENTS.md"]:
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("img.shields.io/badge/tests", text,
                             "%s pins a test count to a badge" % rel)


if __name__ == "__main__":
    unittest.main()
