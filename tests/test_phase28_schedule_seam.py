"""Phase 28: one clock for the rituals.

Two clocks existed — the GitHub Actions cron and the backend's pure due-math — and each
had its own idea of "nightly". The loop now takes its verdict from a registry `schedule`
record through `backend/schedules.is_due`, and every cycle stamps `ran_at` so the next
question has a real answer. The cron stays the alarm; the record is the rule.

The tests below hold that seam at three levels: the records this repo ships, the verdict
function at fixed clocks, and the CLI contract other rituals (and CI) call.
"""
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
import loop  # noqa: E402
from backend import schedules  # noqa: E402
from common import run_utf8  # noqa: E402

RECORD = {
    "kind": "schedule", "id": "SCH-AAAAAAAA", "name": "test schedule",
    "status": "active", "classification": "internal", "created_at": "2026-10-28",
    "tags": [], "relations": {}, "spec": {"daily_at": "02:00"},
    "target": "scripts/loop.py",
}


def fixture(spec=None, status="active", target="scripts/loop.py", history=None):
    tmp = Path(tempfile.mkdtemp())
    folder = tmp / "11_CONTROL" / "schedules"
    folder.mkdir(parents=True)
    record = dict(RECORD, status=status, target=target)
    if spec is not None:
        record["spec"] = spec
    (folder / "SCH-AAAAAAAA-test.json").write_text(json.dumps(record), encoding="utf-8")
    if history is not None:
        path = tmp / "14_CANDIDATES" / "loop" / "history.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({"runs": history}), encoding="utf-8")
    return tmp


class TheRepoOwnsItsCadence(unittest.TestCase):
    def records(self):
        folder = ROOT / "11_CONTROL" / "schedules"
        return [json.loads(p.read_text(encoding="utf-8"))
                for p in sorted(folder.glob("*.json"))]

    def test_the_improvement_loop_has_a_schedule_record(self):
        loop_record = loop.schedule_record(ROOT, "scripts/loop.py")[0]
        self.assertIsNotNone(loop_record, "no registry record says when the loop is due")
        self.assertEqual("schedule", loop_record["kind"])
        self.assertRegex(loop_record["id"], r"^SCH-[0-9A-F]{8}$")
        self.assertEqual("active", loop_record["status"])

    def test_the_weekly_ritual_is_at_most_weekly(self):
        weekly, _ = loop.schedule_record(ROOT, "skills/weekly/SKILL.md")
        self.assertIsNotNone(weekly, "the weekly ritual has no cadence in the registry")
        self.assertEqual({"every_minutes": 7 * 24 * 60}, weekly["spec"])

    def test_every_spec_is_one_the_backend_can_read_and_governs_a_real_path(self):
        now = schedules.parse_utc("2026-10-28T12:00:00Z")
        for record in self.records():
            self.assertTrue((ROOT / record["target"]).exists(), record["target"])
            schedules.next_run_after(record["spec"], now)  # raises on a spec it cannot read


class DueVerdict(unittest.TestCase):
    def setUp(self):
        self.tmp = fixture()
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def test_the_hour_decides_not_the_date(self):
        # The loop ran on the 27th at 03:30 — after that day's 02:00 — so the next
        # window is the 28th at 02:00, whichever calendar day the reader looks at.
        early = loop.due_state(self.tmp, now="2026-10-28T01:00:00Z",
                               last_run="2026-10-27T03:30:00Z")
        late = loop.due_state(self.tmp, now="2026-10-28T02:00:00Z",
                              last_run="2026-10-27T03:30:00Z")
        self.assertIs(False, early["due"], early)
        self.assertIs(True, late["due"], late)
        self.assertEqual("2026-10-28T02:00:00Z", early["next"])

    def test_a_schedule_that_never_ran_is_due(self):
        self.assertIs(True, loop.due_state(self.tmp, now="2026-10-28T00:00:01Z")["due"])

    def test_the_verdict_is_the_backends_verdict(self):
        spec = {"daily_at": "02:00"}
        for now, last in [("2026-10-28T01:59:00Z", "2026-10-27T23:00:00Z"),
                          ("2026-10-28T02:00:00Z", "2026-10-27T23:00:00Z"),
                          ("2026-10-28T02:00:00Z", "2026-10-28T02:00:00Z"),
                          ("2026-10-29T09:00:00Z", "2026-10-28T02:00:00Z")]:
            self.assertEqual(schedules.is_due(spec, last, now),
                             loop.due_state(self.tmp, now=now, last_run=last)["due"], now)

    def test_a_paused_schedule_is_never_due(self):
        paused = fixture(status="paused")
        self.addCleanup(shutil.rmtree, paused, True)
        state = loop.due_state(paused, now="2030-01-01T00:00:00Z")
        self.assertIs(False, state["due"])
        self.assertIn("paused", state["reason"])

    def test_a_malformed_spec_is_refused_not_guessed(self):
        broken = fixture(spec={"cron": "30 3 * * *"})
        self.addCleanup(shutil.rmtree, broken, True)
        state = loop.due_state(broken, now="2026-10-28T12:00:00Z")
        self.assertIsNone(state["due"], state)
        self.assertIn("cannot be read", state["reason"])

    def test_no_record_refuses_instead_of_inventing_a_cadence(self):
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, empty, True)
        state = loop.due_state(empty, now="2026-10-28T12:00:00Z")
        self.assertIsNone(state["due"])
        self.assertIn("no schedule record", state["reason"])

    def test_last_cycle_prefers_the_stamp_and_reads_old_rows_as_midnight(self):
        stamped = fixture(history=[{"date": "2026-10-27", "ran_at": "2026-10-27T03:30:00Z"}])
        self.addCleanup(shutil.rmtree, stamped, True)
        self.assertEqual("2026-10-27T03:30:00Z", loop.last_cycle(stamped))

        old = fixture(history=[{"date": "2026-10-27", "metrics": {}}])
        self.addCleanup(shutil.rmtree, old, True)
        self.assertEqual("2026-10-27T00:00:00Z", loop.last_cycle(old))


class TheCommandLineContract(unittest.TestCase):
    def run_due(self, root, *extra):
        return run_utf8([sys.executable, str(ROOT / "scripts" / "loop.py"), "--due",
                         "--root", str(root), "--now", "2026-10-28T02:30:00Z"] + list(extra))

    def test_due_is_zero_and_carries_the_rule_not_just_the_verdict(self):
        tmp = fixture()
        self.addCleanup(shutil.rmtree, tmp, True)
        result = self.run_due(tmp, "--last-run", "2026-10-27T02:30:00Z")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("DUE", result.stdout)
        self.assertIn("daily_at", result.stdout)
        self.assertIn("SCH-AAAAAAAA-test.json", result.stdout)

    def test_not_due_is_three_and_names_the_next_run(self):
        tmp = fixture()
        self.addCleanup(shutil.rmtree, tmp, True)
        result = self.run_due(tmp, "--last-run", "2026-10-28T02:10:00Z")
        self.assertEqual(3, result.returncode, result.stdout + result.stderr)
        self.assertIn("NOT DUE", result.stdout)
        self.assertIn("2026-10-29T02:00:00Z", result.stdout)

    def test_a_refused_schedule_exits_one(self):
        tmp = fixture(spec={"cron": "30 3 * * *"})
        self.addCleanup(shutil.rmtree, tmp, True)
        result = self.run_due(tmp)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout)

    def test_the_due_check_writes_nothing(self):
        tmp = fixture()
        self.addCleanup(shutil.rmtree, tmp, True)
        before = sorted(p.as_posix() for p in tmp.rglob("*"))
        self.run_due(tmp)
        self.assertEqual(before, sorted(p.as_posix() for p in tmp.rglob("*")))


if __name__ == "__main__":
    unittest.main()
