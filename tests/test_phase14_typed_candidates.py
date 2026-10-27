"""Phase 14 tests — typed candidate rows and the ledger that counts them (issue #9).

The loop used to write prose: "P3: 11 raw TODO markers". Prose cannot be judged, cannot be
promoted and cannot be missed, so nobody could say whether the shelf got shorter. Now every
signal becomes a row with dimension/cue/lesson/evidence/confidence/verdict, one line in
14_CANDIDATES/loop/ledger.jsonl, and the arithmetic is checked:

    proposed == adopt + revise + drop + keep_base + open
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from common import parse_frontmatter, run_utf8  # noqa: E402

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

ENUMS = {"dimension": ("invariant", "domain"),
         "verdict": ("proposed", "helped", "hurt", "no_observed_effect", "confounded",
                     "keep_base")}


def build_house(tmp):
    shutil.copytree(ROOT / "rules", tmp / "rules")
    vault = tmp / "vault-template"
    (vault / "00_Inbox").mkdir(parents=True, exist_ok=True)
    (vault / "00_Inbox" / "broken.md").write_text(NOTE_BAD, encoding="utf-8")


def run_loop(tmp, extra=None):
    return run_utf8([sys.executable, str(SCRIPTS / "loop.py"), "--root", str(tmp), "--no-tests",
                     "--vault", str(tmp / "vault-template")] + (extra or []), cwd=str(ROOT))


def run_check(tmp):
    return run_utf8([sys.executable, str(SCRIPTS / "candidate_check.py"), "--root", str(tmp)],
                    cwd=str(ROOT))


def shelf(tmp):
    return tmp / "14_CANDIDATES" / "loop"


def rows(tmp):
    return sorted(path for path in shelf(tmp).glob("cand-*.md"))


def ledger_events(tmp):
    path = shelf(tmp) / "ledger.jsonl"
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


class TestTypedRows(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        build_house(self.tmp)
        run_loop(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_signal_becomes_a_row_not_a_sentence(self):
        written = rows(self.tmp)
        self.assertTrue(written, "the loop wrote prose where it should have written rows")
        for path in written:
            fm, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
            for field in ("id", "type", "title", "status", "owner", "created", "updated",
                          "dimension", "cue", "lesson", "evidence", "confidence", "verdict"):
                self.assertTrue(fm.get(field), "%s: %s is empty" % (path.name, field))
            self.assertIn(fm["dimension"], ENUMS["dimension"])
            self.assertIn(fm["verdict"], ENUMS["verdict"])
            self.assertEqual(fm["verdict"], "proposed",
                             "the loop names a change, it does not measure one")
            self.assertTrue(0.0 <= float(fm["confidence"]) <= 1.0)
            self.assertEqual(fm["owner"], "agent", "the shelf is machine output, not human prose")

    def test_every_row_names_evidence_a_reader_can_open(self):
        for path in rows(self.tmp):
            fm, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
            evidence = fm["evidence"] if isinstance(fm["evidence"], list) else [fm["evidence"]]
            self.assertTrue(any((self.tmp / str(item)).exists() for item in evidence),
                            "%s cites nothing that exists" % path.name)

    def test_the_rows_the_loop_writes_pass_the_fence_it_ships_with(self):
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_ids_are_unique_and_the_ledger_agrees_with_the_shelf(self):
        ids = [path.stem for path in rows(self.tmp)]
        self.assertEqual(len(ids), len(set(ids)), "two rows share a label")
        events = [event for event in ledger_events(self.tmp) if event.get("event") == "proposed"]
        self.assertEqual(sorted(event["id"] for event in events), sorted(ids),
                         "the shelf and its ledger disagree about what was raised")


class TestCountIdentity(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        build_house(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_same_signal_is_not_proposed_twice(self):
        run_loop(self.tmp)
        first = len(rows(self.tmp))
        second = run_loop(self.tmp)
        self.assertIn("already open", second.stdout)
        self.assertEqual(len(rows(self.tmp)), first, "the shelf grew by repeating itself")

    def test_a_row_that_vanishes_without_a_disposition_is_a_lost_measurement(self):
        run_loop(self.tmp)
        victim = rows(self.tmp)[0]
        victim.unlink()
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("left the shelf without a disposition", result.stdout)

    def test_drop_closes_the_row_and_the_arithmetic_still_adds_up(self):
        run_loop(self.tmp)
        victim = rows(self.tmp)[0]
        result = run_loop(self.tmp, ["--dispose", victim.stem, "drop", "--note", "superseded"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("DISPOSED", result.stdout)
        self.assertFalse(victim.is_file(), "a dropped row that stays on the shelf is still a proposal")
        after = run_check(self.tmp)
        self.assertEqual(after.returncode, 0, after.stdout + after.stderr)
        numbers = {key: int(value) for key, value in
                   re.findall(r"(\w+)=(\d+)", result.stdout.split("DISPOSED")[1])}
        self.assertEqual(numbers["proposed"],
                         numbers["adopt"] + numbers["revise"] + numbers["drop"] +
                         numbers["keep_base"] + numbers["open"],
                         "count identity broken: %s" % numbers)
        self.assertEqual(numbers["proposed"], numbers["decided"] + numbers["open"])
        self.assertEqual(numbers["drop"], 1)

    def test_a_decision_cannot_be_re_litigated(self):
        run_loop(self.tmp)
        victim = rows(self.tmp)[0]
        self.assertEqual(run_loop(self.tmp, ["--dispose", victim.stem, "drop"]).returncode, 0)
        again = run_loop(self.tmp, ["--dispose", victim.stem, "revise"])
        self.assertEqual(again.returncode, 1, again.stdout)
        self.assertIn("REFUSED", again.stdout)

    def test_adopt_is_promotes_move_not_a_typed_label(self):
        run_loop(self.tmp)
        victim = rows(self.tmp)[0]
        result = run_loop(self.tmp, ["--dispose", victim.stem, "adopt"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("promote.py", result.stdout)

    def test_an_unknown_disposition_label_is_refused(self):
        run_loop(self.tmp)
        victim = rows(self.tmp)[0]
        result = run_loop(self.tmp, ["--dispose", victim.stem, "maybe"])
        self.assertEqual(result.returncode, 1)
        self.assertIn("is not one of", result.stdout)


class TestProposalsAreNotMeasurements(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        build_house(self.tmp)
        run_loop(self.tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_promote_refuses_a_row_that_was_only_proposed(self):
        victim = rows(self.tmp)[0]
        proposals = self.tmp / "proposals.json"
        proposals.write_text(json.dumps({"proposals": [{
            "capture": "14_CANDIDATES/loop/%s" % victim.name, "target": "20_Notes",
            "approved": True, "reason": "test"}]}, ensure_ascii=False), encoding="utf-8")
        result = run_utf8([sys.executable, str(SCRIPTS / "promote.py"), "--root", str(self.tmp),
                           "--proposals", str(proposals),
                           "--item", "14_CANDIDATES/loop/%s" % victim.name], cwd=str(ROOT))
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("verdict is proposed", result.stdout)
        self.assertTrue(victim.is_file(), "a refused promotion must not move the row")

    def test_the_report_prints_the_arithmetic_it_claims(self):
        report = sorted(shelf(self.tmp).glob("report-*.md"))[0]
        text = report.read_text(encoding="utf-8")
        self.assertIn("Ledger (count identity)", text)
        self.assertIn("proposed=", text)
        self.assertRegex(text, r"proposed=(\d+) = adopt=(\d+) \+ revise=(\d+) \+ drop=(\d+) \+ "
                              r"keep_base=(\d+) \+ open=(\d+)")
        numbers = [int(n) for n in re.search(
            r"proposed=(\d+) = adopt=(\d+) \+ revise=(\d+) \+ drop=(\d+) \+ keep_base=(\d+) \+ "
            r"open=(\d+)", text).groups()]
        self.assertEqual(numbers[0], sum(numbers[1:]), "the printed arithmetic does not add up")


class TestHandAuthoredRows(unittest.TestCase):
    """The loop is not the only author: a row written from the template must be counted too."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        build_house(self.tmp)
        (self.tmp / "14_CANDIDATES" / "loop").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._tmp.cleanup()

    def row(self):
        return (self.tmp / "14_CANDIDATES" / "loop" / "cand-by-hand.md")

    def write_row(self):
        self.row().write_text(
            "---\nid: cand-by-hand\ntype: note\ntitle: Written by an agent\nstatus: raw\n"
            "owner: agent\ntopics: [loop]\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
            "dimension: domain\ncue: a gate crashed in a console code page\n"
            "lesson: state the encoding, do not inherit it\nconfidence: 0.8\n"
            "verdict: keep_base\nevidence:\n  - rules/zones.json\n---\n\nBody.\n",
            encoding="utf-8")

    def test_an_unregistered_row_is_an_unaccounted_row(self):
        self.write_row()
        result = run_check(self.tmp)
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("the ledger never proposed", result.stdout)

    def test_registering_makes_it_countable_and_clean(self):
        self.write_row()
        registered = run_utf8([sys.executable, str(SCRIPTS / "candidate_check.py"),
                               "--root", str(self.tmp), "--register",
                               "14_CANDIDATES/loop/cand-by-hand.md"], cwd=str(ROOT))
        self.assertEqual(registered.returncode, 0, registered.stdout + registered.stderr)
        self.assertIn("REGISTERED", registered.stdout)
        self.assertEqual(run_check(self.tmp).returncode, 0, run_check(self.tmp).stdout)
        twice = run_utf8([sys.executable, str(SCRIPTS / "candidate_check.py"),
                          "--root", str(self.tmp), "--register",
                          "14_CANDIDATES/loop/cand-by-hand.md"], cwd=str(ROOT))
        self.assertIn("ALREADY", twice.stdout)
        self.assertEqual(run_check(self.tmp).returncode, 0,
                         "registering twice must not break the count")

    def test_a_report_is_not_a_candidate_and_cannot_be_registered(self):
        (self.tmp / "14_CANDIDATES" / "loop" / "notes.md").write_text(
            "---\nid: notes-1\ntype: note\ntitle: A report\nstatus: raw\nowner: agent\n"
            "created: 2026-01-01\nupdated: 2026-01-01\n---\n\nprose\n", encoding="utf-8")
        result = run_utf8([sys.executable, str(SCRIPTS / "candidate_check.py"),
                           "--root", str(self.tmp), "--register",
                           "14_CANDIDATES/loop/notes.md"], cwd=str(ROOT))
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a candidate row", result.stdout)


class TestShippedRepo(unittest.TestCase):
    def test_the_real_shelf_is_in_balance(self):
        """The repo must satisfy its own contract -- including the new ledger rules."""
        result = run_check(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
