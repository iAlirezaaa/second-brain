#!/usr/bin/env python
"""Phase 49 (continued): the pre-push loop can now see the v3 battery.

`15_SYSTEM/scripts/test_hades.py` is the judge that talks to the MCP door over stdio. Until
`scripts/battery_check.py` existed, nothing but GitHub Actions ran it — which is how commit
`c889ee5` went public-red while `python scripts/health.py` and the unittest suite stayed green.
These tests are the reason that gap is closed: a gate that runs nothing, or that calls an
unmeasured battery green, is the same silence in a new costume.

Each case drives the gate with `--battery PATH` at a synthetic battery, so the verdicts are
proved in milliseconds instead of the battery's own ~30 seconds. The real battery is still run
by the gate itself inside `health.py`; here it is only named, never executed.

The last class judges `health.py --fast` instead of the gate: `scripts/base.py --save` runs that
loop once per save, and a session that saves a dozen bases must not pay for a dozen batteries.
Those cases build a whole source tree of two-line gate stand-ins, so the OK-line law and the
red-house refusal are measured in milliseconds too.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "scripts" / "battery_check.py"
sys.path.insert(0, str(ROOT / "scripts"))


def run(argv):
    """The gate as a child process, with stdout read back as utf-8."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(GATE)] + argv, cwd=str(ROOT), env=env,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")


class TestTheGateIsWiredIn(unittest.TestCase):
    """The gate has to be inside the loop it was built to join, exactly once."""

    def test_health_runs_the_battery_gate_once_and_does_not_pass_it_a_vault(self):
        import health
        entries = [g for g in health.GATES if g.split()[0] == "battery_check.py"]
        self.assertEqual(entries, ["battery_check.py"],
                         "the battery gate must appear exactly once in GATES, got %r" % entries)
        self.assertIn("battery_check.py", health.ROOT_ONLY_GATES,
                      "the battery judges the source tree, not a --vault argument")

    def test_it_points_at_the_real_v3_battery_and_that_file_exists(self):
        sys.path.insert(0, str(GATE.parent))
        import battery_check
        target = ROOT / battery_check.BATTERY
        self.assertTrue(target.is_file(), "the gate names %s, which is not in the tree" % target)
        self.assertEqual(battery_check.BATTERY, "15_SYSTEM/scripts/test_hades.py")

    def test_the_law_of_this_gate_is_written_in_its_own_docstring(self):
        doc = GATE.read_text(encoding="utf-8")
        self.assertIn("rumour about a gate", doc,
                      "the gate must state why it exists: an unrun test is not a gate")
        self.assertIn("installed brain home", doc,
                      "and how it behaves where there is no source repo to judge")


class TestVerdictsFromSyntheticBatteries(unittest.TestCase):
    """Every way a battery can fail to certify itself must come out of the gate as INVALID."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hades-battery-gate-")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def battery(self, name, body):
        path = Path(self.tmp) / (name + ".py")
        path.write_text(body, encoding="utf-8")
        return str(path)

    def assert_invalid(self, result, phrase):
        self.assertEqual(result.returncode, 1,
                         "expected exit 1, got %d with stdout %r" % (result.returncode,
                                                                      result.stdout))
        self.assertIn("INVALID battery", result.stdout)
        self.assertIn(phrase, result.stdout, "stdout was %r" % result.stdout)

    def test_a_red_battery_is_invalid_and_its_failures_are_echoed(self):
        path = self.battery("red", "import sys\n"
                                  "print('FAIL harness: the door leaked a run id')\n"
                                  "print('checks: 3 | passed: 2 | failed: 1')\n"
                                  "sys.exit(1)\n")
        result = run(["--battery", path])
        self.assert_invalid(result, "must not ship")
        self.assertIn("FAIL harness: the door leaked a run id", result.stdout,
                      "a red gate that hides which check broke is not a report")
        self.assertIn("1 failed", result.stdout)

    def test_a_battery_that_prints_no_summary_measured_nothing(self):
        # exit code 0 and no count line: the loudest fake pass a silent suite can produce
        path = self.battery("quiet", "print('all good, trust me')\n")
        result = run(["--battery", path])
        self.assert_invalid(result, "without printing a `checks:` summary")

    def test_a_missing_battery_file_is_refused_not_skipped(self):
        result = run(["--battery", str(Path(self.tmp) / "nowhere.py")])
        self.assert_invalid(result, "a gate that runs nothing is not a pass")

    def test_a_nonzero_exit_under_a_zero_fail_count_is_still_red(self):
        # a crash after the summary: the count says green, the process says otherwise
        path = self.battery("crash", "import sys\n"
                                    "print('checks: 3 | passed: 3 | failed: 0')\n"
                                    "sys.exit(2)\n")
        result = run(["--battery", path])
        self.assert_invalid(result, "must not ship")

    def test_a_green_battery_passes_and_prints_its_own_count(self):
        path = self.battery("green", "print('checks: 7 | passed: 7 | failed: 0')\n")
        result = run(["--battery", path])
        self.assertEqual(result.returncode, 0, "stdout was %r stderr %r"
                         % (result.stdout, result.stderr))
        self.assertIn("OK battery: 7 checks | 7 passed | 0 failed", result.stdout)

    def test_a_battery_that_never_finishes_is_timed_out_by_name(self):
        path = self.battery("hang", "import time\ntime.sleep(30)\n")
        result = run(["--battery", path, "--timeout", "1"])
        self.assert_invalid(result, "did not finish in 1 seconds")
        self.assertLess(result.returncode, 2)

    def test_the_summary_parser_reads_the_last_line_not_the_first(self):
        sys.path.insert(0, str(GATE.parent))
        import battery_check
        text = ("checks: 1 | passed: 0 | failed: 1\n"
                "FAIL something\n"
                "checks: 122 | passed: 122 | failed: 0\n")
        self.assertEqual(battery_check.parse_summary(text),
                         {"checks": 122, "passed": 122, "failed": 0})
        self.assertIsNone(battery_check.parse_summary("no counts here"))
        self.assertIsNone(battery_check.parse_summary("checks: x | failed: y"))


class TestAnInstalledHomeSkipsItStatedly(unittest.TestCase):
    """A home carries no source scripts to battery, so the gate says so in one line."""

    def build_home(self, tmp):
        home = Path(tmp) / "home"
        (home / "scripts").mkdir(parents=True)
        (home / "rules").mkdir()
        # find_root() walks up to rules/zones.json; a home has one and has no .git or pyproject
        (home / "rules" / "zones.json").write_text('{"zones": []}\n', encoding="utf-8")
        for name in ("common.py", "battery_check.py"):
            (home / "scripts" / name).write_text(
                (ROOT / "scripts" / name).read_text(encoding="utf-8"), encoding="utf-8")
        return home

    def test_the_installed_gate_prints_one_ok_skip_line_and_exits_zero(self):
        with tempfile.TemporaryDirectory(prefix="hades-home-") as tmp:
            home = self.build_home(tmp)
            env = dict(os.environ, PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, str(home / "scripts" / "battery_check.py")],
                                    cwd=str(home), env=env, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode, 0,
                             "stdout %r stderr %r" % (result.stdout, result.stderr))
            lines = [line for line in result.stdout.splitlines() if line.strip()]
            self.assertEqual(len(lines), 1,
                             "a gate owes health.py exactly one line, got %r" % lines)
            self.assertTrue(lines[0].startswith("OK battery — skipped in "), lines[0])
            self.assertIn("installed brain home", lines[0])


class TestFastIsAScheduleNotABypass(unittest.TestCase):
    """`base.py --save` now runs the health loop with `--fast`, which skips the battery.

    That is only honest if two things stay true: the skipped gate still owes its one line, and
    a red house is still red under the flag. Both are judged here against a source tree whose
    gates are two-line stand-ins, so the verdicts cost milliseconds and the loop's own logic is
    what is under test -- not the seconds of the real judges.
    """

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hades-fast-")

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def house(self, red=None):
        root = Path(self.tmp) / ("red" if red else "green")
        (root / "rules").mkdir(parents=True, exist_ok=True)
        (root / "rules" / "zones.json").write_text('{"zones": []}\n', encoding="utf-8")
        scripts = root / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        import health
        for entry in health.GATES:
            name = entry.split()[0]
            if (scripts / name).is_file():
                continue
            label = name.replace(".py", "")
            if name == red:
                body = ("import sys\n"
                        "print('INVALID %s stand-in: the house is red')\n"
                        "sys.exit(1)\n" % label)
            else:
                body = "print('OK %s stand-in')\n" % label
            (scripts / name).write_text(body, encoding="utf-8")
        # the battery is the one stand-in that leaves a trace of having been executed at all
        (scripts / "battery_check.py").write_text(
            "import pathlib\n"
            "pathlib.Path('battery-ran.txt').write_text('yes')\n"
            "print('OK battery: 3 checks | 3 passed | 0 failed')\n", encoding="utf-8")
        for name in ("common.py", "health.py"):
            (scripts / name).write_text((ROOT / "scripts" / name).read_text(encoding="utf-8"),
                                         encoding="utf-8")
        return root

    def health(self, root, *flags):
        env = dict(os.environ, PYTHONIOENCODING="utf-8")
        return subprocess.run([sys.executable, str(root / "scripts" / "health.py")] + list(flags),
                              cwd=str(root), env=env, capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    @staticmethod
    def ok_lines(result):
        return [line for line in result.stdout.splitlines() if line.startswith("OK")]

    def test_fast_prints_the_batterys_line_without_running_the_battery(self):
        import health
        root = self.house()
        result = self.health(root, "--fast")
        self.assertEqual(result.returncode, 0, "stdout %r stderr %r"
                         % (result.stdout, result.stderr))
        self.assertFalse((root / "battery-ran.txt").exists(),
                         "--fast executed the battery anyway, so it skipped nothing")
        skip = [line for line in result.stdout.splitlines() if "battery" in line]
        self.assertEqual(len(skip), 1, "the battery owes the loop exactly one line, got %r" % skip)
        self.assertTrue(skip[0].startswith("OK battery — skipped by --fast"), skip[0])
        self.assertIn("scripts/health.py", skip[0],
                      "a skip must name the command that does run the judge it skipped")

    def test_a_fast_loop_still_owes_one_OK_line_per_gate(self):
        import health
        fast = self.health(self.house(), "--fast")
        full = self.health(self.house())
        self.assertEqual(len(self.ok_lines(fast)), len(health.GATES),
                         "a skipped gate silenced itself instead of stating the skip: %r"
                         % self.ok_lines(fast))
        self.assertEqual(len(self.ok_lines(full)), len(health.GATES))
        self.assertTrue((self.house_of(full)), "the plain loop did not run the battery")

    @staticmethod
    def house_of(result):
        return "OK battery: 3 checks | 3 passed | 0 failed" in result.stdout

    def test_a_red_gate_still_refuses_the_fast_loop(self):
        import health
        root = self.house(red="frontmatter_check.py")
        result = self.health(root, "--fast")
        self.assertEqual(result.returncode, 1,
                         "--fast turned a red house green: %r" % result.stdout)
        self.assertIn("INVALID frontmatter_check stand-in", result.stdout)
        self.assertEqual(len(self.ok_lines(result)), len(health.GATES) - 1,
                         "every gate that ran still owes its line, red included")

    def test_the_base_preflight_is_fast_and_still_refuses_a_red_house(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        import base
        code, output = base.gates(self.house())
        self.assertEqual(code, 0, output)
        self.assertIn("skipped by --fast", output,
                      "the base pre-flight was expected to use the fast loop: %r" % output)
        red = self.house(red="link_check.py")
        code, output = base.gates(red)
        self.assertEqual(code, 1, "a base was saved on a red house: %r" % output)
        self.assertIn("INVALID link_check stand-in", output,
                      "the pre-flight must show which gate refused, not only that one did")

    def test_both_files_state_the_law_in_their_own_words(self):
        health_doc = (ROOT / "scripts" / "health.py").read_text(encoding="utf-8")
        self.assertIn("schedule, not a way to make a red house look green", health_doc,
                      "health.py must say what --fast is for and what it cannot do")
        base_doc = (ROOT / "scripts" / "base.py").read_text(encoding="utf-8")
        self.assertIn("battery gate is the one exception", base_doc,
                      "base.py must name the one gate its pre-flight does not measure")


if __name__ == "__main__":
    unittest.main()
