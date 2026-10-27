"""Phase 12 tests — probe: behaviour claims are measured by an execution, not a checkbox.

Borrowed from google-research/harness2 (Propose -> Probe -> Compose). Every case here
plants the defect a real candidate could have and requires probe.py to refuse it; a
gate that never refuses is decoration.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROBE = str(ROOT / "scripts" / "probe.py")

QUIET_SCRIPT = 'import sys\nprint("checked 3 files, nothing to fix")\n'
FAILING_SCRIPT = 'import sys\nprint("found a problem")\nsys.exit(1)\n'
SILENT_SCRIPT = "import sys\n"
MUTATING_SCRIPT = ('import pathlib\n'
                   'pathlib.Path("scratch_note.md").write_text("the probe wrote into the vault", '
                   'encoding="utf-8")\nprint("done")\n')
WRITER_SCRIPT = ('import pathlib\n'
                 'p = pathlib.Path("out"); p.mkdir(exist_ok=True)\n'
                 '(p / "report.md").write_text("# produced\\n", encoding="utf-8")\n'
                 'print("wrote out/report.md")\n')


def candidate(text, tmp, name="cand-001.md"):
    shelf = tmp / "14_CANDIDATES" / "loop"
    shelf.mkdir(parents=True, exist_ok=True)
    path = shelf / name
    path.write_text(text, encoding="utf-8")
    return path


def fm(probe="scripts/quiet.py", extra=""):
    return ("---\nid: cand-001\ntype: note\ntitle: Probe fixture\ncreated: 2026-01-01\n"
            "updated: 2026-01-01\nowner: agent\nstatus: raw\ntopics: [loop]\n"
            "probe: %s\n%s---\n\nThe body.\n" % (probe, extra))


def run_probe(tmp, cand, extra=None):
    return subprocess.run([sys.executable, PROBE, "--root", str(tmp),
                           "--candidate", str(cand)] + (extra or []),
                          capture_output=True, text=True)


class TestProbe(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "quiet.py").write_text(QUIET_SCRIPT, encoding="utf-8")
        (scripts / "fails.py").write_text(FAILING_SCRIPT, encoding="utf-8")
        (scripts / "silent.py").write_text(SILENT_SCRIPT, encoding="utf-8")
        (scripts / "mutates.py").write_text(MUTATING_SCRIPT, encoding="utf-8")
        (scripts / "writes_declared.py").write_text(WRITER_SCRIPT, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def read_records(self):
        index = self.tmp / "14_CANDIDATES" / "loop" / "probes" / "index.jsonl"
        return [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines()] \
            if index.is_file() else []

    def test_clean_probe_passes_and_is_recorded(self):
        result = run_probe(self.tmp, candidate(fm(), self.tmp))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("outcome=pass", result.stdout)
        records = self.read_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["outcome"], "pass")
        self.assertEqual(len(records[0]["fingerprint_at"]), 16)
        shelf = self.tmp / "14_CANDIDATES" / "loop" / "probes"
        self.assertTrue(list(shelf.glob("cand-001-*.md")), "no human-readable record")

    def test_a_failing_command_is_fail_not_silence(self):
        result = run_probe(self.tmp, candidate(fm("scripts/fails.py"), self.tmp))
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.read_records()[-1]["outcome"], "fail")

    def test_producing_nothing_is_unsafe_not_unproven(self):
        """harness2: an edit whose rollout produced nothing is treated as UNSAFE."""
        result = run_probe(self.tmp, candidate(fm("scripts/silent.py"), self.tmp))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("outcome=undelivered", result.stdout)
        self.assertIn("UNSAFE", result.stdout)

    def test_a_declared_expectation_that_was_not_delivered_is_refused(self):
        result = run_probe(self.tmp, candidate(
            fm("scripts/quiet.py", "probe_expects: [out/*.md]\n"), self.tmp))
        self.assertEqual(result.returncode, 1)
        self.assertIn("undelivered", result.stdout)

    def test_declared_writer_can_pass(self):
        cand = candidate(fm("scripts/writes_declared.py",
                            "probe_writes: [out]\nprobe_expects: [out/report.md]\n"), self.tmp)
        result = run_probe(self.tmp, cand)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("outcome=pass", result.stdout)

    def test_writing_where_the_candidate_said_nothing_is_unsafe(self):
        result = run_probe(self.tmp, candidate(fm("scripts/mutates.py"), self.tmp))
        self.assertEqual(result.returncode, 1)
        self.assertIn("outcome=unsafe-mutating", result.stdout)
        self.assertIn("scratch_note.md", result.stdout)

    def test_commands_outside_the_allowlisted_dirs_are_refused(self):
        for declared in ("../scripts/outside.py", "skills/loop/SKILL.md", "15_SYSTEM/scripts/x.py",
                         "scripts/does_not_exist.py"):
            result = run_probe(self.tmp, candidate(fm(declared), self.tmp, "cand-%s.md" % abs(hash(declared))))
            self.assertEqual(result.returncode, 1, declared)
            self.assertIn("REFUSED", result.stdout, declared)

    def test_the_installer_is_reserved_because_it_writes_outside_the_repo(self):
        scripts = self.tmp / "scripts"
        (scripts / "install.py").write_text(QUIET_SCRIPT, encoding="utf-8")
        result = run_probe(self.tmp, candidate(fm("scripts/install.py"), self.tmp))
        self.assertEqual(result.returncode, 1)
        self.assertIn("reserved", result.stdout)

    def test_a_candidate_with_no_probe_declaration_is_refused_not_skipped(self):
        bare = candidate("---\nid: cand-001\ntype: note\ntitle: No probe\ncreated: 2026-01-01\n"
                         "updated: 2026-01-01\nowner: agent\nstatus: raw\ntopics: [loop]\n---\n"
                         "A claim with nothing executed behind it.\n", self.tmp, "cand-bare.md")
        result = run_probe(self.tmp, bare)
        self.assertEqual(result.returncode, 1)
        self.assertIn("REFUSED", result.stdout)


class TestMeasurementFreshness(unittest.TestCase):
    """A measurement describes the tree it was taken on.

    Two things had to be true before a probe could be used as evidence for promotion:
    filing paperwork (another candidate, a report, a proposal) must not invalidate an
    honest measurement -- otherwise the discipline gets switched off -- and editing the
    claim after the run must be visible, or a verdict can inherit someone else's run.
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        scripts = self.tmp / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        (scripts / "quiet.py").write_text(QUIET_SCRIPT, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def read_records(self):
        index = self.tmp / "14_CANDIDATES" / "loop" / "probes" / "index.jsonl"
        return [json.loads(line) for line in index.read_text(encoding="utf-8").splitlines()] \
            if index.is_file() else []

    def test_the_ledger_records_after_and_the_candidate_digest(self):
        run_probe(self.tmp, candidate(fm(), self.tmp))
        record = self.read_records()[-1]
        for field in ("fingerprint_at", "fingerprint_after", "candidate_digest"):
            self.assertEqual(len(record.get(field) or ""), 16, "%s missing from the ledger" % field)

    def test_filing_paperwork_does_not_invalidate_a_measurement(self):
        """The shelf grows on every cycle; the identity of the brain must not move."""
        first = run_probe(self.tmp, candidate(fm(), self.tmp, "cand-001.md"))
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        candidate(fm("scripts/quiet.py"), self.tmp, "cand-002.md")
        (self.tmp / "14_CANDIDATES" / "loop" / "report-2026-01-02-c1.md").write_text(
            "# report\n", encoding="utf-8")
        second = run_probe(self.tmp, candidate(fm(), self.tmp, "cand-001.md"))
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        records = self.read_records()
        self.assertEqual(records[0]["fingerprint_at"], records[-1]["fingerprint_at"],
                         "ordinary filing moved the state fingerprint")

    def test_editing_the_claim_after_the_run_is_visible(self):
        run_probe(self.tmp, candidate(fm(), self.tmp))
        measured = self.read_records()[-1]["candidate_digest"]
        edited = candidate(fm() + "\nverdict: helped\n", self.tmp)   # typed after the run
        run_probe(self.tmp, edited)
        self.assertNotEqual(measured, self.read_records()[-1]["candidate_digest"])

    def test_state_fingerprint_ignores_paperwork_and_sees_the_brain(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        from common import state_fingerprint
        baseline = state_fingerprint(self.tmp)
        (self.tmp / "12_RUNTIME").mkdir(parents=True, exist_ok=True)
        (self.tmp / "12_RUNTIME" / "x").write_text("cache\n", encoding="utf-8")
        self.assertEqual(baseline, state_fingerprint(self.tmp), "runtime writes are paperwork")
        (self.tmp / "20_Notes").mkdir(exist_ok=True)
        (self.tmp / "20_Notes" / "a.md").write_text("---\nid: a\n---\nreal\n", encoding="utf-8")
        self.assertNotEqual(baseline, state_fingerprint(self.tmp),
                            "a real note is not paperwork")


if __name__ == "__main__":
    unittest.main()
