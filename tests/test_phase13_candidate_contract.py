"""Phase 13 tests — the candidate contract: a shelf row is a claim, claims carry evidence.

rules/candidate.schema.json is the law, scripts/candidate_check.py is the fence, and
promote.py refuses to file a row the fence rejected. Every case plants the defect a real
candidate could have; a gate that never refuses is decoration.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECK = str(ROOT / "scripts" / "candidate_check.py")
PROBE = str(ROOT / "scripts" / "probe.py")
PROMOTE = str(ROOT / "scripts" / "promote.py")

QUIET_SCRIPT = 'import sys\nprint("checked 3 files, nothing to fix")\n'
FAILING_SCRIPT = 'import sys\nprint("found a problem")\nsys.exit(1)\n'

FIELDS = {
    "id": "cand-001",
    "type": "note",
    "title": "Contract fixture",
    "status": "raw",
    "owner": "agent",
    "topics": "[loop, candidate]",
    "created": "2026-01-01",
    "updated": "2026-01-01",
    "dimension": "domain",
    "cue": "the loop claimed an improvement nobody measured",
    "lesson": "run the declared probe before writing a verdict",
    "confidence": "0.9",
    "verdict": "helped",
    "probe": "scripts/quiet.py",
    "evidence": ["scripts/quiet.py"],
}


def frontmatter(**overrides):
    """Emit frontmatter; a value of None drops the key, a list becomes block items."""
    fields = dict(FIELDS)
    fields.update(overrides)
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            lines.append("%s:" % key)
            lines.extend("  - %s" % item for item in value)
        else:
            lines.append("%s: %s" % (key, value))
    lines.append("---")
    return "\n".join(lines) + "\n\nThe body of the claim.\n"


class Harness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        (self.tmp / "rules").mkdir()
        shutil.copy(ROOT / "rules" / "candidate.schema.json", self.tmp / "rules")
        shutil.copy(ROOT / "rules" / "zones.json", self.tmp / "rules")
        scripts = self.tmp / "scripts"
        scripts.mkdir()
        (scripts / "quiet.py").write_text(QUIET_SCRIPT, encoding="utf-8")
        (scripts / "fails.py").write_text(FAILING_SCRIPT, encoding="utf-8")
        for zone in ("00_Inbox", "20_Notes", "90_Agent_Output"):
            (self.tmp / "vault-template" / zone).mkdir(parents=True)
        self.shelf = self.tmp / "14_CANDIDATES" / "loop"
        self.shelf.mkdir(parents=True)

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, text, name="cand-001.md"):
        path = self.shelf / name
        path.write_text(text, encoding="utf-8")
        return path

    def check(self, *extra):
        return subprocess.run([sys.executable, CHECK, "--root", str(self.tmp)] + list(extra),
                              capture_output=True, text=True)

    def probe(self, path):
        return subprocess.run([sys.executable, PROBE, "--root", str(self.tmp),
                               "--candidate", str(path)], capture_output=True, text=True)

    def promote(self, item, extra_fields=None):
        proposals = {"proposals": [dict(
            {"capture": item, "target": "20_Notes",
             "destination": "20_Notes/promoted.md", "approved": True, "reason": "test"},
            **(extra_fields or {}))]}
        # proposals go where the contract says they live: the agent output shelf, which
        # is paperwork and therefore outside the measured state of the brain
        sink = self.tmp / "vault-template" / "90_Agent_Output" / "proposals"
        sink.mkdir(parents=True, exist_ok=True)
        path = sink / "proposals.json"
        path.write_text(json.dumps(proposals), encoding="utf-8")
        return subprocess.run([sys.executable, PROMOTE, "--root", str(self.tmp),
                               "--proposals", str(path), "--item", item],
                              capture_output=True, text=True)


class TestContractValidation(Harness):
    def test_a_measured_candidate_passes(self):
        path = self.write(frontmatter())
        self.assertEqual(self.probe(path).returncode, 0, "the probe itself must pass first")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 shelf candidate", result.stdout)

    def test_behaviour_claim_without_a_probe_is_refused(self):
        self.write(frontmatter(probe=None))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no execution behind it", result.stdout)

    def test_a_probe_that_never_ran_is_not_evidence(self):
        self.write(frontmatter())
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no probe has ever been run", result.stdout)

    def test_a_probe_taken_on_an_older_tree_is_stale(self):
        """Freshness is content-addressed: the measurement describes the bytes it saw."""
        path = self.write(frontmatter())
        self.assertEqual(self.probe(path).returncode, 0)
        (self.tmp / "later_edit.md").write_text("the tree moved after the measurement\n",
                                                encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("stale", result.stdout)

    def test_a_helped_verdict_cannot_be_backed_by_a_failing_probe(self):
        path = self.write(frontmatter(probe="scripts/fails.py"))
        self.assertEqual(self.probe(path).returncode, 1)
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("needs a probe with outcome in", result.stdout)

    def test_a_hurt_verdict_is_legitimate_when_a_probe_failed(self):
        """Learning what hurts is the point of the shelf — it just has to be measured."""
        path = self.write(frontmatter(probe="scripts/fails.py", verdict="hurt"))
        self.assertEqual(self.probe(path).returncode, 1)
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_path_that_starts_with_a_dot_is_opened_not_mangled(self):
        """.kb/kb.sqlite is real state; "./x" is the same file written two ways. Stripping a
        leading character class instead of a leading ./ used to turn both into nothing."""
        hidden = self.tmp / ".kb"
        hidden.mkdir(exist_ok=True)
        (hidden / "kb.sqlite").write_text("sqlite\n", encoding="utf-8")
        self.write(frontmatter(evidence=[".kb/kb.sqlite"]))
        result = self.check()
        self.assertNotIn("evidence path does not exist", result.stdout, result.stdout)
        self.write(frontmatter(evidence=["./.kb/kb.sqlite"]))
        result = self.check("--file", "14_CANDIDATES/loop/cand-001.md")
        self.assertNotIn("evidence path does not exist", result.stdout, result.stdout)

    def test_evidence_pointing_at_nothing_is_a_fabrication(self):
        path = self.write(frontmatter(evidence=["does/not/exist.md"]))
        self.assertEqual(self.probe(path).returncode, 0)
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("evidence path does not exist", result.stdout)

    def test_empty_evidence_is_refused(self):
        path = self.write(frontmatter(evidence=[]))
        self.assertEqual(self.probe(path).returncode, 0)
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("evidence is empty", result.stdout)

    def test_confidence_outside_zero_one_is_refused(self):
        path = self.write(frontmatter(confidence="1.7"))
        self.assertEqual(self.probe(path).returncode, 0)
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("outside 0..1", result.stdout)

    def test_an_unknown_dimension_or_verdict_is_refused(self):
        for overrides in ({"dimension": "vibes"}, {"verdict": "felt_better"}):
            path = self.write(frontmatter(**overrides))
            self.probe(path)
            result = self.check()
            self.assertEqual(result.returncode, 1, str(overrides) + result.stdout)
            self.assertIn("is not one of", result.stdout)

    def test_invariant_candidates_always_need_a_run(self):
        """Changing the measuring apparatus without executing is the worst failure mode."""
        self.write(frontmatter(dimension="invariant", verdict="keep_base", probe=None))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("no execution behind it", result.stdout)

    def test_reports_are_not_candidates(self):
        """The loop writes reports; only rows that make a claim are judged as candidates."""
        (self.shelf / "report-2026-01-01.md").write_text(frontmatter(
            dimension=None, cue=None, lesson=None, verdict=None, confidence=None, probe=None),
            encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("0 shelf candidate", result.stdout)


class TestNoEntry(Harness):
    def test_no_entry_is_legal_and_needs_no_evidence(self):
        self.write(frontmatter(cue="NO_ENTRY", lesson=None, evidence=None,
                               confidence=None, verdict=None, probe=None, dimension=None))
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_no_entry_cannot_also_teach(self):
        self.write(frontmatter(cue="NO_ENTRY", lesson=None, evidence=None,
                               confidence=None, verdict=None, probe=None, dimension=None,
                               title="Contract fixture"))
        path = self.shelf / "cand-001.md"
        path.write_text(path.read_text(encoding="utf-8").replace(
            "cue: NO_ENTRY", "cue: NO_ENTRY\nlesson: a lesson smuggled into an empty row"),
            encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("cannot also teach", result.stdout)


class TestPromoteGate(Harness):
    def test_a_measured_candidate_promotes_and_leaves_the_shelf(self):
        path = self.write(frontmatter())
        self.assertEqual(self.probe(path).returncode, 0)
        result = self.promote("14_CANDIDATES/loop/cand-001.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PROMOTED", result.stdout)
        self.assertFalse(path.exists(), "the promoted row stayed on the shelf")
        filed = self.tmp / "vault-template" / "20_Notes" / "promoted.md"
        self.assertIn("verdict: helped", filed.read_text(encoding="utf-8"))
        self.assertTrue((self.tmp / "14_CANDIDATES" / "loop" / "probes" / "index.jsonl").is_file(),
                        "the evidence vanished with the candidate")

    def test_promoting_without_a_probe_is_refused(self):
        self.write(frontmatter())
        result = self.promote("14_CANDIDATES/loop/cand-001.md")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("no probe has ever been run", result.stdout)

    def test_low_confidence_is_refused_even_when_measured(self):
        path = self.write(frontmatter(confidence="0.2"))
        self.assertEqual(self.probe(path).returncode, 0)
        result = self.promote("14_CANDIDATES/loop/cand-001.md")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("below the promote floor", result.stdout)

    def test_keep_base_stays_on_the_shelf(self):
        """KEEP_BASE is a real answer: nothing gets filed, nothing is pretend-measured."""
        self.write(frontmatter(verdict="keep_base", probe=None, dimension="domain"))
        result = self.promote("14_CANDIDATES/loop/cand-001.md")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("keep_base", result.stdout)
        self.assertTrue((self.shelf / "cand-001.md").is_file())

    def test_confounded_is_recorded_not_promoted(self):
        path = self.write(frontmatter(verdict="confounded",
                                      evidence=["scripts/quiet.py"], probe=None))
        result = self.promote("14_CANDIDATES/loop/cand-001.md")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("confounded", result.stdout)

    def test_no_entry_is_not_promotable(self):
        self.write(frontmatter(cue="NO_ENTRY", lesson=None, evidence=None,
                               confidence=None, verdict="keep_base", probe=None, dimension=None))
        result = self.promote("14_CANDIDATES/loop/cand-001.md")
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("NO_ENTRY", result.stdout)

    def test_a_plain_capture_is_unaffected_by_the_contract(self):
        """The gate bites candidates only; ordinary inbox traffic keeps its old rules."""
        capture = ("---\nid: cap-1\ntype: capture\ntitle: A clip\nstatus: inbox\nowner: agent\n"
                   "topics: [testing]\ncreated: 2026-01-01\nupdated: 2026-01-01\n---\nBody.\n")
        (self.tmp / "vault-template" / "00_Inbox" / "clip.md").write_text(capture, encoding="utf-8")
        result = self.promote("00_Inbox/clip.md")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PROMOTED", result.stdout)


class TestStateIsTheBrainNotItsPaperwork(Harness):
    """Freshness has to survive ordinary filing, or every gate gets switched off."""

    def test_paperwork_moves_do_not_invalidate_a_measurement(self):
        path = self.write(frontmatter())
        self.assertEqual(self.probe(path).returncode, 0)
        (self.shelf / "report-2026-01-02.md").write_text("a report lands on the shelf\n",
                                                         encoding="utf-8")
        runtime = self.tmp / "12_RUNTIME" / "index"
        runtime.mkdir(parents=True)
        (runtime / "generated.md").write_text("the runtime plane rebuilds itself\n",
                                              encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_real_change_does_invalidate_it(self):
        path = self.write(frontmatter())
        self.assertEqual(self.probe(path).returncode, 0)
        (self.tmp / "scripts" / "quiet.py").write_text(
            'import sys\nprint("the measured thing itself changed")\n', encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stdout)

    def test_editing_the_claim_after_the_run_does_not_inherit_its_evidence(self):
        path = self.write(frontmatter())
        self.assertEqual(self.probe(path).returncode, 0)
        path.write_text(frontmatter(verdict="hurt"), encoding="utf-8")
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("edited after it was measured", result.stdout)


class TestSchemaIsTheSingleSource(Harness):
    def test_shipped_schema_declares_every_field_the_fence_reads(self):
        schema = json.loads((ROOT / "rules" / "candidate.schema.json").read_text(encoding="utf-8"))
        for field in ("dimension", "cue", "lesson", "evidence", "confidence", "verdict"):
            self.assertIn(field, schema["required"], field)
        self.assertEqual(schema["promote_floor"]["confidence"], 0.6)
        for verdict in ("helped", "hurt", "no_observed_effect", "confounded", "keep_base"):
            self.assertIn(verdict, schema["required"]["verdict"]["enum"], verdict)

    def test_the_shipped_shelf_meets_the_contract(self):
        result = subprocess.run([sys.executable, CHECK, "--root", str(ROOT)],
                                capture_output=True, text=True, cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
