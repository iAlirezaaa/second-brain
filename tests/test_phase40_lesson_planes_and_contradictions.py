"""Phase 40 — charter section 5, lessons typed by plane and contradictions caught (issues #25, #24).

Two gaps the eight-plane map named honestly and did not close:

  * #25 — a row in `15_SYSTEM/memory/lessons.jsonl` carried `cue, lesson, evidence, verdict,
    topics, source` but no `plane`, so the map's claim that the error plane holds lessons was
    honest-but-weak: a lesson from a failed run looked identical to a lesson from a design choice
    until you read the prose. The fix types every row by a `plane` from the vocabulary already
    declared in `system.json -> memory_planes`, refuses a missing or unmapped plane at the DOOR
    and in `--check`, and migrates the rows that predate the field deterministically from their
    own `source`/`topics` (`--migrate-planes`, additive, dry-run by default, states `unclassified`
    where the evidence does not decide).
  * #24 — no plane compared two memories. The fix is a MEASURED definition first: two ACTIVE
    lessons contradict when same plane + shared topic + cue-overlap (Jaccard on the repo's own
    folded tokens) >= 0.50 + opposite verdict (helped vs hurt). The threshold is measured on the
    shipped ledger (closest agreeing pair 0.31, zero opposite pairs), so the number is evidence.
    `--check` refuses an active conflict; a pair linked by `supersedes` is reported resolved.

Each class is red on the commit before its fix; the two directions of the contradiction rule are
proven by the refusal in one fixture and the pass in the same fixture with `--supersedes`.
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
import memory  # noqa: E402
from common import run_utf8  # noqa: E402

MEMORY = str(SCRIPTS / "memory.py")
ALL_PLANES = ("project", "repository", "agent", "task", "error", "decision", "knowledge",
              "conversation")


def run_memory(root, *args):
    return run_utf8([sys.executable, MEMORY, "--root", str(root)] + list(args), cwd=str(ROOT))


class PlaneFixture(unittest.TestCase):
    """A repo-shaped folder whose config declares the eight planes, so the vocabulary is real."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "README.md").write_text("evidence the gate can open\n", encoding="utf-8")
        (self.root / "rules").mkdir()
        shutil.copy(ROOT / "rules" / "memory.schema.json", self.root / "rules")
        cfg = {"memory_planes": dict((p, {}) for p in ALL_PLANES)}
        (self.root / "15_SYSTEM" / "config").mkdir(parents=True)
        (self.root / "15_SYSTEM" / "config" / "system.json").write_text(
            json.dumps(cfg), encoding="utf-8")

    def add(self, cid, *extra):
        return run_memory(self.root, "--add", "--id", cid, "--cue", "the fence refused a run",
                          "--lesson", "print the row and the reason", "--evidence", "README.md",
                          "--confidence", "0.8", *extra)

    def ledger(self):
        path = self.root / "15_SYSTEM" / "memory" / "lessons.jsonl"
        return [json.loads(line) for line in
                path.read_text(encoding="utf-8").splitlines() if line.strip()] \
            if path.is_file() else []


class PlaneFieldAtTheDoor(PlaneFixture):
    """#25 — a plane the door does not recognise never reaches the ledger (issue #17's lesson)."""

    def test_a_missing_empty_plane_is_refused_before_the_write(self):
        code = run_memory(self.root, "--add", "--id", "mem-x", "--cue", "a cue",
                          "--lesson", "a lesson", "--evidence", "README.md",
                          "--verdict", "helped", "--plane", "").returncode
        self.assertEqual(1, code)
        self.assertEqual([], self.ledger(), "a refused plane must not be written")

    def test_an_unknown_plane_is_refused_and_names_the_vocabulary(self):
        result = run_memory(self.root, "--add", "--id", "mem-x", "--cue", "a cue",
                            "--lesson", "a lesson", "--evidence", "README.md",
                            "--verdict", "helped", "--plane", "banana")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("banana", result.stdout)
        self.assertIn("memory_planes", result.stdout,
                      "the refusal must point at where the vocabulary lives: %s" % result.stdout)
        self.assertEqual([], self.ledger())

    def test_a_mapped_plane_is_accepted_and_written(self):
        result = self.add("mem-error", "--verdict", "helped", "--plane", "error")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual("error", self.ledger()[0]["plane"])
        self.assertEqual(0, run_memory(self.root, "--check").returncode)

    def test_no_plane_argument_defaults_the_plane_from_the_source(self):
        # "zones" and "fence" are error-plane provenance; the field is derived, not invented.
        result = self.add("mem-derived", "--verdict", "helped", "--source", "issue #6",
                          "--topics", "zones,fence")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual("error", self.ledger()[0]["plane"],
                         "--add must default the plane from --source when --plane is absent")

    def test_no_source_and_no_plane_states_unclassified_rather_than_a_missing_field(self):
        # the door never leaves the field absent: an undecidable row is typed unclassified,
        # which the gate tolerates -- there is exactly one honest value for "I do not know".
        self.assertEqual(0, self.add("mem-blank", "--verdict", "helped").returncode)
        self.assertEqual("unclassified", self.ledger()[0]["plane"])
        self.assertEqual(0, run_memory(self.root, "--check").returncode)

    def test_the_help_text_names_the_source_default(self):
        result = run_utf8([sys.executable, MEMORY, "--help"], cwd=str(ROOT))
        self.assertIn("--plane", result.stdout)
        self.assertIn("--source", result.stdout,
                      "the help must say the plane defaults from --source when --plane is omitted")


class PlaneFieldInCheck(PlaneFixture):
    """#25 — --check is the second half of the gate: a row that arrives by hand must also be typed."""

    def test_a_row_without_a_plane_is_a_problem(self):
        row = {"id": "mem-ghost", "date": "2026-11-02T00:00:00Z", "cue": "c", "lesson": "l",
               "evidence": ["README.md"], "confidence": 0.5, "verdict": "helped"}
        problems = memory.check_row(row, self.root, set(), memory.plane_ids(self.root))
        self.assertTrue(any("plane" in p and "empty" in p for p in problems), problems)

    def test_an_unmapped_plane_is_a_problem(self):
        row = {"id": "mem-x", "date": "2026-11-02T00:00:00Z", "cue": "c", "lesson": "l",
               "evidence": ["README.md"], "confidence": 0.5, "verdict": "helped",
               "plane": "banana"}
        problems = memory.check_row(row, self.root, set(), memory.plane_ids(self.root))
        self.assertTrue(any("plane" in p and "banana" in p for p in problems), problems)

    def test_unclassified_is_tolerated(self):
        row = {"id": "mem-u", "date": "2026-11-02T00:00:00Z", "cue": "c", "lesson": "l",
               "evidence": ["README.md"], "confidence": 0.5, "verdict": "helped",
               "plane": "unclassified"}
        problems = memory.check_row(row, self.root, set(), memory.plane_ids(self.root))
        self.assertEqual([], [p for p in problems if "plane" in p], problems)


class TheShippedLedgerIsTypedAndClean(unittest.TestCase):
    """Not a fixture: the real repo must already satisfy the plane field and the rule."""

    def test_every_shipped_row_carries_a_mapped_plane(self):
        rows = memory.read_lessons(ROOT)[0]
        allowed = set(memory.plane_ids(ROOT))
        for row in rows:
            self.assertIn(row.get("plane"), allowed,
                          "%s has plane %r outside the vocabulary" % (row.get("id"), row.get("plane")))

    def test_the_shipped_ledger_passes_the_gate(self):
        _rows, problems = memory.check(ROOT)
        self.assertEqual([], problems, problems)
        self.assertEqual(0, run_memory(ROOT, "--check").returncode)

    def test_the_plane_vocabulary_is_read_from_the_config_not_retyped(self):
        cfg = json.loads((ROOT / "15_SYSTEM" / "config" / "system.json").read_text(encoding="utf-8"))
        declared = set(cfg["memory_planes"])
        derived = set(memory.plane_ids(ROOT))
        self.assertTrue(declared <= derived, "every mapped plane must be a legal lesson plane")
        self.assertIn("unclassified", derived,
                      "the one value memory.py adds is the stated 'does not decide'")


class MigratePlanesIsAdditive(PlaneFixture):
    """#25 — the rows that predate the field are typed from their own provenance, or said so."""

    def seed(self):
        rows = [
            # provenance that decides: source "chat" + topics registry (a design/registry lesson)
            {"id": "mem-decides", "date": "2026-10-27T00:00:00Z", "cue": "a wrong registry record",
             "lesson": "amend through the plan door", "evidence": ["README.md"],
             "confidence": 0.8, "verdict": "helped", "source": "chat 2026-10-27",
             "topics": ["registry"]},
            # provenance that does not decide -> stated unclassified, not a guess
            {"id": "mem-undecided", "date": "2026-10-27T00:00:00Z", "cue": "a strange thing",
             "lesson": "who knows", "evidence": ["README.md"], "confidence": 0.5,
             "verdict": "keep_base", "source": "", "topics": ["zzzq-nonsense"]},
        ]
        path = self.root / "15_SYSTEM" / "memory"
        path.mkdir(parents=True)
        (path / "lessons.jsonl").write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n", encoding="utf-8")

    def test_dry_run_reports_but_writes_nothing(self):
        self.seed()
        before = (self.root / "15_SYSTEM" / "memory" / "lessons.jsonl").read_text(encoding="utf-8")
        result = run_memory(self.root, "--migrate-planes")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("decision", result.stdout, "the registry/chat row decides to the plane it states")
        self.assertIn("unclassified", result.stdout)
        self.assertEqual(before,
                         (self.root / "15_SYSTEM" / "memory" / "lessons.jsonl").read_text(encoding="utf-8"),
                         "a dry run that writes is not a dry run")

    def test_write_adds_the_plane_deterministically_and_additively(self):
        self.seed()
        result = run_memory(self.root, "--migrate-planes", "--write")
        self.assertEqual(0, result.returncode, result.stdout)
        rows = {r["id"]: r for r in self.ledger()}
        self.assertEqual("decision", rows["mem-decides"]["plane"])
        self.assertEqual("unclassified", rows["mem-undecided"]["plane"],
                         "an undecided row states unclassified rather than being guessed into a plane")
        # additive: every original field survives untouched
        self.assertEqual("a wrong registry record", rows["mem-decides"]["cue"])
        self.assertEqual(["README.md"], rows["mem-decides"]["evidence"])

    def test_migration_is_idempotent(self):
        self.seed()
        run_memory(self.root, "--migrate-planes", "--write")
        first = (self.root / "15_SYSTEM" / "memory" / "lessons.jsonl").read_text(encoding="utf-8")
        result = run_memory(self.root, "--migrate-planes", "--write")
        self.assertIn("NO CHANGE", result.stdout, result.stdout)
        self.assertEqual(first,
                         (self.root / "15_SYSTEM" / "memory" / "lessons.jsonl").read_text(encoding="utf-8"),
                         "a second migration must not rewrite an already-typed ledger")

    def test_a_corrupted_ledger_is_refused_not_migrated_over(self):
        self.seed()
        with (self.root / "15_SYSTEM" / "memory" / "lessons.jsonl").open("a", encoding="utf-8") as h:
            h.write("{not json}\n")
        result = run_memory(self.root, "--migrate-planes", "--write")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("is not JSON", result.stdout)


class TheContradictionSimilarity(unittest.TestCase):
    """#24 — the similarity function is Jaccard over the repo's own folded tokens, unit-provable."""

    def test_identical_fully_overlapping_cues_score_one(self):
        self.assertAlmostEqual(1.0, memory.cue_overlap(
            "the fence refused a run", "the fence refused a run"))

    def test_disjoint_cues_score_zero(self):
        self.assertAlmostEqual(0.0, memory.cue_overlap(
            "windows subprocess encoding", "persian hygiene letters"))

    def test_jaccard_is_intersection_over_union(self):
        # {gate, refused, run} vs {gate, refused, note} -> 2/4
        self.assertAlmostEqual(0.5, memory.cue_overlap(
            "the gate refused a run", "the gate refused a note"))

    def test_stopwords_and_short_words_are_folded_away(self):
        self.assertAlmostEqual(1.0, memory.cue_overlap("the a gate", "gate is an a"))

    def test_the_threshold_is_the_measured_number(self):
        self.assertEqual(0.50, memory.CONTRADICTION_JACCARD)
        # and the measured fact behind it: the shipped ledger's closest agreeing pair sits under it
        rows = memory.active(memory.read_lessons(ROOT)[0])
        best = max((memory.cue_overlap(a.get("cue", ""), b.get("cue", ""))
                    for i, a in enumerate(rows) for b in rows[i + 1:]
                    if set(a.get("topics") or []) & set(b.get("topics") or [])
                    and str(a.get("plane")) == str(b.get("plane"))), default=0.0)
        self.assertLess(best, memory.CONTRADICTION_JACCARD,
                        "the chosen threshold must sit above every agreeing pair on the real ledger")


def _pair(root, first_verdict, second_verdict, supersedes_second=False):
    """Two same-plane, shared-topic, identical-cue lessons with opposite verdicts."""
    args = ["--cue", "the fence refused a run", "--lesson", "print it", "--evidence", "README.md",
            "--confidence", "0.8", "--plane", "error", "--topics", "gates"]
    run_memory(root, "--add", "--id", "mem-a", "--verdict", first_verdict, *args)
    extra = ["--supersedes", "mem-a"] if supersedes_second else []
    return run_memory(root, "--add", "--id", "mem-b", "--verdict", second_verdict, *args + extra)


class AnActiveContradictionIsRefused(PlaneFixture):
    """#24, direction one: two ACTIVE lessons that disagree are a refusal, not a note."""

    def test_helped_versus_hurt_on_the_same_thing_is_refused(self):
        result = _pair(self.root, "helped", "hurt")
        self.assertEqual(0, result.returncode, result.stdout)  # the door does not block the second
        check = run_memory(self.root, "--check")
        self.assertEqual(1, check.returncode, check.stdout)
        self.assertIn("CONTRADICTION", check.stdout)
        self.assertIn("mem-a", check.stdout)
        self.assertIn("mem-b", check.stdout)

    def test_contradictions_reports_the_pair_with_its_numbers(self):
        _pair(self.root, "helped", "hurt")
        report = run_memory(self.root, "--contradictions")
        self.assertEqual(1, report.returncode, report.stdout)
        self.assertIn("REFUSED", report.stdout)
        self.assertIn("overlap=1.000", report.stdout, report.stdout)
        self.assertIn("verdicts=helped/hurt", report.stdout, report.stdout)


class AResolvedContradictionPasses(PlaneFixture):
    """#24, direction two: the same pair, one lesson retiring the other, is resolved -- not refused."""

    def test_the_superseded_pair_is_not_an_active_conflict(self):
        result = _pair(self.root, "helped", "hurt", supersedes_second=True)
        self.assertEqual(0, result.returncode, result.stdout)
        check = run_memory(self.root, "--check")
        self.assertEqual(0, check.returncode, check.stdout)

    def test_contradictions_reports_the_pair_as_resolved_and_exits_zero(self):
        _pair(self.root, "helped", "hurt", supersedes_second=True)
        report = run_memory(self.root, "--contradictions")
        self.assertEqual(0, report.returncode, report.stdout)
        self.assertIn("resolved", report.stdout, report.stdout)


class AgreementIsNotContradiction(PlaneFixture):
    """The rule must fire only on a real disagreement, never on lessons that merely share words."""

    def test_same_situation_agreeing_verdicts_is_not_a_conflict(self):
        # identical cue+plane+topic, but BOTH said "helped" -- no disagreement, no refusal
        _pair(self.root, "helped", "helped")
        self.assertEqual(0, run_memory(self.root, "--check").returncode)

    def test_the_shipped_ledger_holds_no_active_contradiction(self):
        self.assertEqual(0, run_memory(ROOT, "--contradictions").returncode)
        active = [p for p in memory.find_contradictions(memory.read_lessons(ROOT)[0])
                  if p["status"] == "active"]
        self.assertEqual([], active)


if __name__ == "__main__":
    unittest.main()
