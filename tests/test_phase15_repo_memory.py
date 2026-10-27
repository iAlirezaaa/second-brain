"""Phase 15 tests — the repo's own memory (issue #7).

Memory that cannot be checked is a diary. Every case here either breaks the ledger in the
way an agent actually would (an evidence path that no longer opens, an id cited twice, a
hand-edit to the generated index) or asks the ledger a question and requires an honest
answer -- including the honest answer being nothing.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from common import run_utf8  # noqa: E402

MEMORY = str(SCRIPTS / "memory.py")


def memory(root, *args):
    return run_utf8([sys.executable, MEMORY, "--root", str(root)] + list(args), cwd=str(ROOT))


class Harness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        (self.tmp / "rules").mkdir()
        shutil.copy(ROOT / "rules" / "memory.schema.json", self.tmp / "rules")
        (self.tmp / "docs").mkdir()
        (self.tmp / "docs" / "proof.md").write_text("# proof\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def add(self, cid="mem-alpha", cue="the gate printed nothing", evidence="docs/proof.md",
            confidence="0.9", verdict="helped", extra=()):
        return memory(self.tmp, "--add", "--id", cid, "--cue", cue,
                      "--lesson", "print the row and the reason", "--evidence", evidence,
                      "--confidence", confidence, "--verdict", verdict, *extra)

    def rows(self):
        path = self.tmp / "15_SYSTEM" / "memory" / "lessons.jsonl"
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()] \
            if path.is_file() else []

    def index(self):
        return self.tmp / "MEMORY.md"


class TestLedger(unittest.TestCase):
    def test_the_shipped_memory_passes_its_own_gate(self):
        """The repo must be able to trust what it wrote down about this session."""
        result = memory(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MEMORY.md matches the ledger", result.stdout)

    def test_the_shipped_memory_is_not_empty(self):
        rows = memory(ROOT, "--list").stdout.strip().splitlines()
        self.assertGreaterEqual(len(rows), 9, "a memory with nothing in it is not a memory")
        for line in rows:
            self.assertTrue(line.startswith("mem-"), line)


class TestRefusals(Harness):
    def test_a_lesson_with_no_evidence_is_a_preference(self):
        result = memory(self.tmp, "--add", "--id", "mem-bare", "--cue", "x", "--lesson", "y",
                        "--confidence", "0.9", "--verdict", "helped")
        self.assertEqual(result.returncode, 1)
        self.assertIn("--evidence", result.stdout)

    def test_evidence_that_does_not_open_is_refused_at_the_door(self):
        result = self.add(evidence="docs/never-written.md")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("does not exist", result.stdout)
        self.assertEqual(self.rows(), [], "a refused lesson must not reach the ledger")

    def test_the_same_id_cannot_hold_two_lessons(self):
        self.assertEqual(self.add().returncode, 0)
        again = self.add(cue="a completely different situation")
        self.assertEqual(again.returncode, 1)
        self.assertIn("supersede", again.stdout)

    def test_an_unknown_verdict_is_refused(self):
        result = self.add(verdict="felt_better")
        self.assertEqual(result.returncode, 1)
        self.assertIn("is not one of", result.stdout)

    def test_confidence_outside_zero_one_is_refused(self):
        result = self.add(confidence="1.4")
        self.assertEqual(result.returncode, 1)
        self.assertIn("outside 0..1", result.stdout)

    def test_a_confidence_that_is_not_a_number_is_refused_without_a_traceback(self):
        result = self.add(confidence="pretty_sure")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("not a number", result.stdout)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.rows(), [])


class TestDrift(Harness):
    def test_a_generated_index_that_is_hand_edited_gets_caught(self):
        self.add()
        text = self.index().read_text(encoding="utf-8")
        self.index().write_text(text.replace("`mem-alpha`", "`mem-ghost`"), encoding="utf-8")
        result = memory(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("not in the ledger", result.stdout)

    def test_an_active_lesson_missing_from_the_index_is_a_problem(self):
        self.add()
        text = self.index().read_text(encoding="utf-8")
        keep = "\n".join(line for line in text.splitlines() if "mem-alpha" not in line)
        self.index().write_text(keep + "\n", encoding="utf-8")
        result = memory(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("does not show", result.stdout)

    def test_evidence_that_stopped_resolving_is_reported(self):
        self.add()
        (self.tmp / "docs" / "proof.md").unlink()
        result = memory(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("does not exist", result.stdout)

    def test_a_corrupted_line_is_not_silently_skipped(self):
        self.add()
        catalog = self.tmp / "15_SYSTEM" / "memory" / "lessons.jsonl"
        with catalog.open("a", encoding="utf-8") as handle:
            handle.write("{not json}\n")
        result = memory(self.tmp)
        self.assertEqual(result.returncode, 1)
        self.assertIn("is not JSON", result.stdout)

    def test_superseding_retires_the_old_row_but_keeps_the_record(self):
        self.add(cid="mem-alpha")
        second = self.add(cid="mem-beta", cue="a later finding about the same thing",
                          extra=["--supersedes", "mem-alpha"])
        self.assertEqual(second.returncode, 0, second.stdout)
        result = memory(self.tmp)
        self.assertEqual(result.returncode, 0, result.stdout)
        text = self.index().read_text(encoding="utf-8")
        self.assertIn("Retired", text)
        self.assertIn("mem-alpha", text, "the record is kept, it is just not active")
        rows = {row["id"]: row for row in self.rows()}
        self.assertEqual(len(rows), 2, "the ledger is append-only")

    def test_superses_must_point_at_a_real_row(self):
        self.add(cid="mem-alpha", extra=["--supersedes", "mem-phantom"])
        result = memory(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("never held", result.stdout)


class TestRecall(Harness):
    def test_recall_finds_the_lesson_that_matches_the_situation(self):
        self.add(cid="mem-encoding", cue="subprocess printed Persian and the parent crashed")
        memory(self.tmp, "--add", "--id", "mem-unicode", "--cue", "the parent crashed on a unicode name",
               "--lesson", "check ids before filing", "--evidence", "docs/proof.md",
               "--confidence", "0.5", "--verdict", "helped")
        result = memory(self.tmp, "--recall", "persian subprocess crashed parent")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("mem-unicode", result.stdout, "a partial match should still be offered")
        self.assertLess(result.stdout.index("mem-encoding"), result.stdout.index("mem-unicode"),
                        "the matching lesson should be the first thing an agent reads")

    def test_a_lesson_with_no_overlap_is_not_shown_as_a_match(self):
        """Retrieval that always answers is retrieval that is lying."""
        self.add(cid="mem-encoding", cue="subprocess printed Persian and the parent crashed")
        result = memory(self.tmp, "--recall", "duplicate note id")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NO_ENTRY", result.stdout)

    def test_an_empty_answer_is_legal_and_says_so(self):
        self.add()
        result = memory(self.tmp, "--recall", "zzznogapqqq bicycle")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NO_ENTRY", result.stdout)

    def test_recall_with_no_ledger_at_all_still_answers_honestly(self):
        result = memory(self.tmp, "--recall", "anything")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NO_ENTRY", result.stdout)


class TestWiredIntoTheHouse(Harness):
    def test_health_runs_the_memory_gate(self):
        self.add()
        result = run_utf8([sys.executable, str(SCRIPTS / "health.py"), "--vault",
                           str(ROOT / "vault-template")], cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("MEMORY.md matches the ledger", result.stdout)

    def test_the_catalog_is_readable_and_greppable_at_once(self):
        """Dual audience: a table for the human, typed json for the agent, same facts."""
        self.add()
        text = self.index().read_text(encoding="utf-8")
        self.assertIn("| `mem-alpha` |", text)
        row = self.rows()[0]
        for field in ("id", "date", "cue", "lesson", "evidence", "confidence", "verdict"):
            self.assertTrue(row.get(field), "%s missing from the machine-readable row" % field)


if __name__ == "__main__":
    unittest.main()
