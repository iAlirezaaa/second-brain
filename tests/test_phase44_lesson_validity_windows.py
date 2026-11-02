"""Phase 44 item 2 — a lesson says how long it is certain for, or it says nothing.

Graphiti keeps bi-temporal edges: a fact has a validity interval as well as a discovery time.
The LLM that builds those edges is exactly what this repo refuses, but the *window* is free:
two optional date fields on a lesson row.

  `verified_at`  the day a person last re-checked the row's evidence (optional);
  `expires`      the last day the claim still counts as certain (optional).

The semantics, stated before the code and written into `rules/memory.schema.json` and
`02_WIKI/reference_maps/eight-memory-planes.md`:

  * no `expires`  -> **evergreen**: the row claims nothing dated, so nothing can go stale.
  * `expires` >= today -> **current**.
  * `expires`  < today -> **stale**: a clone cannot re-check the claim, and a gate that reported
    that as merely OK is the silent certainty this item exists to remove. The gate REFUSES the
    row by name; it never deletes, rewrites or hides it (the ledger is append-only, and a stale
    lesson is still a lesson someone measured).
  * a window field that is not a `YYYY-MM-DD` day, that says it was verified in the future, or
    that closed before it opened -> **invalid**, refused.

`--recall` marks a stale row instead of dropping it, `--windows` reports the measured counts, and
the MCP door's `memory_recall` marks the row with the same helper — one rule, two readers.

Measured on this repo's shipped ledger before the rule was chosen: not one row carried either
field, so not one was stale and the default is `absent = evergreen`. No date was invented to
make a number appear. The row *count* is deliberately not frozen anywhere below or in the plane
map: a lesson landing is normal business here, and a typed count would go false on the next
commit while saying nothing about the rule.
"""
import json
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import memory  # noqa: E402
from common import run_utf8  # noqa: E402

MEMORY = str(SCRIPTS / "memory.py")
SCHEMA = ROOT / "rules" / "memory.schema.json"
MAP = ROOT / "02_WIKI" / "reference_maps" / "eight-memory-planes.md"
TODAY = date(2026, 11, 2)


def day(offset):
    return (TODAY + timedelta(days=offset)).isoformat()


class WindowFixture(unittest.TestCase):
    """A repo-shaped folder: real plane vocabulary, real schema, evidence the gate can open."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "README.md").write_text("evidence the gate can open\n", encoding="utf-8")
        (self.root / "rules").mkdir()
        shutil.copy(SCHEMA, self.root / "rules")
        cfg = dict((p, {}) for p in ("project", "repository", "agent", "task", "error",
                                     "decision", "knowledge", "conversation"))
        (self.root / "15_SYSTEM" / "config").mkdir(parents=True)
        (self.root / "15_SYSTEM" / "config" / "system.json").write_text(
            json.dumps({"memory_planes": cfg}), encoding="utf-8")

    def memory(self, *args):
        return run_utf8([sys.executable, MEMORY, "--root", str(self.root)] + list(args),
                        cwd=str(ROOT))

    def add(self, cid, *extra):
        return self.memory("--add", "--id", cid, "--cue", "a cue", "--lesson", "a lesson",
                           "--evidence", "README.md", "--confidence", "0.8",
                           "--verdict", "helped", *extra)

    def ledger_path(self):
        return self.root / "15_SYSTEM" / "memory" / "lessons.jsonl"

    def ledger(self):
        if not self.ledger_path().is_file():
            return []
        return [json.loads(line) for line in
                self.ledger_path().read_text(encoding="utf-8").splitlines() if line.strip()]

    def seed(self, *rows):
        path = self.root / "15_SYSTEM" / "memory"
        path.mkdir(parents=True, exist_ok=True)
        path.joinpath("lessons.jsonl").write_text(
            "".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
        # MEMORY.md is part of the row contract, so a seeded ledger gets its rendering; the
        # window tests must not fail for a reason that has nothing to do with windows.
        self.memory("--render")


def row(cid, **extra):
    base = {"id": cid, "date": "2026-10-27T00:00:00Z", "cue": "a cue", "lesson": "a lesson",
            "evidence": ["README.md"], "confidence": 0.8, "verdict": "helped",
            "plane": "error"}
    base.update(extra)
    return base


class TheStatesAreDefined(WindowFixture):
    """The rule is four named states, decided from the row's own text and today's date."""

    def test_no_window_is_evergreen_not_stale(self):
        self.assertEqual("evergreen", memory.window_state(row("mem-a"), TODAY))

    def test_a_window_still_open_is_current_including_its_last_day(self):
        self.assertEqual("current", memory.window_state(row("mem-a", expires=day(30)), TODAY))
        self.assertEqual("current", memory.window_state(row("mem-a", expires=day(0)), TODAY))

    def test_a_window_that_passed_is_stale(self):
        self.assertEqual("stale", memory.window_state(row("mem-a", expires=day(-1)), TODAY))

    def test_a_window_field_that_is_not_a_day_is_invalid(self):
        for value in ("next tuesday", "2026-11", "2026-13-40", "02-11-2026", "yesterday"):
            self.assertEqual("invalid", memory.window_state(row("mem-a", expires=value), TODAY),
                             "%r is not a calendar day" % value)

    def test_a_window_closed_before_it_opened_is_invalid(self):
        state = memory.window_state(row("mem-a", verified_at=day(0), expires=day(-5)), TODAY)
        self.assertEqual("invalid", state)

    def test_a_verification_that_has_not_happened_yet_is_invalid(self):
        self.assertEqual("invalid", memory.window_state(row("mem-a", verified_at=day(2)), TODAY))


class AStaleLessonIsAGateRow(WindowFixture):
    """The named gate row: refuse, name it, and never rewrite the ledger to make the red go away."""

    def test_check_refuses_a_stale_row_by_name(self):
        self.seed(row("mem-expired", expires=day(-3)))
        result = self.memory("--check")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("STALE", result.stdout)
        self.assertIn("mem-expired", result.stdout)
        self.assertIn("REFUSED", result.stdout)

    def test_the_refusal_deletes_and_rewrites_nothing(self):
        self.seed(row("mem-expired", expires=day(-3)), row("mem-evergreen"))
        before = self.ledger_path().read_text(encoding="utf-8")
        self.memory("--check")
        self.assertEqual(before, self.ledger_path().read_text(encoding="utf-8"),
                         "a gate that edits the ledger to go green is not a gate")
        self.assertEqual(0, self.memory("--render").returncode,
                         "rendering a stale row is legal; deleting it is not")
        self.assertIn("mem-expired", (self.root / "MEMORY.md").read_text(encoding="utf-8"))
        self.assertEqual(1, self.memory("--check").returncode,
                         "and the refusal survives the re-render")

    def test_a_current_window_and_no_window_are_both_green(self):
        self.seed(row("mem-open", expires=day(20)), row("mem-evergreen"))
        result = self.memory("--check")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("OK", result.stdout)

    def test_an_unreadable_window_is_refused_not_treated_as_evergreen(self):
        """The whole point: an absent window is a claim of no window, a broken one is a bug."""
        self.seed(row("mem-typo", expires="next tuesday"))
        result = self.memory("--check")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("mem-typo", result.stdout)
        self.assertIn("YYYY-MM-DD", result.stdout)

    def test_a_retired_stale_row_is_reported_not_refused(self):
        """A superseded row is not presented as certainty anywhere, so the gate names it in the
        report and does not refuse the house over a lesson that already left the active table."""
        self.seed(row("mem-old", expires=day(-9), supersedes=None),
                  row("mem-new", supersedes="mem-old"))
        result = self.memory("--check")
        self.assertEqual(0, result.returncode, result.stdout)
        stale = memory.stale_rows(memory.read_lessons(self.root)[0], TODAY)
        self.assertEqual([], [s["id"] for s in stale if s["id"] == "mem-old"],
                          "the helper sees it; the active-only refusal does not")

    def test_windows_reports_the_measured_counts(self):
        self.seed(row("mem-stale", expires=day(-2)), row("mem-open", expires=day(4)),
                  row("mem-evergreen"))
        result = self.memory("--windows")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("1 stale", result.stdout)
        self.assertIn("1 current", result.stdout)
        self.assertIn("1 evergreen", result.stdout)


class RecallMarksTheWindow(WindowFixture):
    """Retrieval must not hand a stale claim to an agent dressed as a certainty."""

    def test_recall_names_the_stale_row_and_still_shows_it(self):
        self.seed(row("mem-expired", expires=day(-1), cue="the fence refused a run",
                      lesson="print the row and the reason"))
        result = self.memory("--recall", "fence refused run")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("mem-expired", result.stdout, "the row is marked, never hidden")
        self.assertIn("STALE", result.stdout)
        self.assertIn("expires", result.stdout)

    def test_recall_of_an_evergreen_row_carries_no_marker(self):
        self.seed(row("mem-live", cue="the fence refused a run", lesson="print the row"))
        result = self.memory("--recall", "fence refused run")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertNotIn("STALE", result.stdout)


class TheDoorMarksTheWindowToo(WindowFixture):
    """The MCP door is the other reader of the ledger, so it marks the same rows the CLI marks.

    One rule, two doors: `memory.py --recall` and `mcp_server.py`'s `memory_recall` both call
    `memory.recall_mark()`, because an agent that asks the memory a question has to see that the
    answer's window has passed — and has to see the row, not a silence.
    """

    def door_recall(self, query):
        sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
        import mcp_server  # imported here, so this file's own `common`/`memory` stay the scripts'
        out = []
        mcp_server.handle(self.root, {"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                                      "params": {"name": "memory_recall",
                                                 "arguments": {"query": query}}}, out)
        result = out[0]["result"]
        text = "\n".join(chunk.get("text", "") for chunk in result["content"])
        return result.get("isError", False), text

    def test_the_door_marks_a_stale_row_and_still_returns_it(self):
        self.seed(row("mem-expired", expires=day(-1), cue="the fence refused a run",
                      lesson="print the row and the reason"))
        is_error, text = self.door_recall("fence refused run")
        self.assertFalse(is_error, text)
        self.assertIn("mem-expired", text, text)
        self.assertIn("print the row and the reason", text, text)
        self.assertIn("STALE", text, text)
        self.assertIn("re-check before applying", text, text)

    def test_the_door_says_nothing_about_a_row_with_no_window(self):
        self.seed(row("mem-live", cue="the fence refused a run", lesson="print the row"))
        is_error, text = self.door_recall("fence refused run")
        self.assertFalse(is_error, text)
        self.assertIn("mem-live", text, text)
        self.assertNotIn("STALE", text, text)

    def test_the_door_announces_the_marking_in_its_tool_list(self):
        sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
        import mcp_server
        tool = [t for t in mcp_server.TOOLS if t["name"] == "memory_recall"][0]
        self.assertIn("STALE", tool["description"], tool)
        self.assertIn("never dropped", tool["description"], tool)


class TheDoorRefusesABrokenWindow(WindowFixture):
    """--add is the first gate: a window that cannot be read never reaches the ledger."""

    def test_a_malformed_expires_is_refused_and_writes_nothing(self):
        result = self.add("mem-x", "--expires", "next tuesday")
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("expires", result.stdout)
        self.assertEqual([], self.ledger(), "a refused window must not be written")

    def test_a_window_closed_before_it_opened_is_refused(self):
        result = self.add("mem-x", "--verified-at", day(0), "--expires", day(-4))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("REFUSED", result.stdout)
        self.assertEqual([], self.ledger())

    def test_a_future_verification_is_refused(self):
        result = self.add("mem-x", "--verified-at", day(3))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("REFUSED", result.stdout)
        self.assertEqual([], self.ledger())

    def test_a_legal_window_is_written_and_green(self):
        result = self.add("mem-x", "--verified-at", day(-1), "--expires", day(29))
        self.assertEqual(0, result.returncode, result.stdout)
        written = self.ledger()[0]
        self.assertEqual(day(-1), written["verified_at"])
        self.assertEqual(day(29), written["expires"])
        self.assertEqual(0, self.memory("--check").returncode)

    def test_no_window_flags_writes_no_window_fields(self):
        """Absent means evergreen, so the door must not invent a date to look complete."""
        self.assertEqual(0, self.add("mem-x").returncode)
        self.assertNotIn("expires", self.ledger()[0])
        self.assertNotIn("verified_at", self.ledger()[0])


class TheShippedLedgerIsMeasured(WindowFixture):
    """The default was chosen from the shipped rows, not from a wish: none carries a window, so
    none is stale. The counts are read from the ledger on every run — a typed row count here would
    go false the next time a lesson lands, which is the silent-gate failure in the other direction:
    a number that was true once and now only proves the test was written before the change."""

    def test_no_shipped_row_carries_an_expired_window(self):
        rows = memory.read_lessons(ROOT)[0]
        self.assertTrue(rows, "an empty ledger measures nothing and cannot back a default")
        self.assertEqual(0, sum(1 for r in rows if r.get("expires") or r.get("verified_at")),
                         "rows now carry windows; re-measure before trusting the default")
        self.assertEqual([], memory.stale_rows(rows, TODAY))

    def test_the_shipped_ledger_is_green_and_the_gate_says_why(self):
        done = run_utf8([sys.executable, MEMORY, "--root", str(ROOT), "--check"], cwd=str(ROOT))
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        done = run_utf8([sys.executable, MEMORY, "--root", str(ROOT), "--windows"], cwd=str(ROOT))
        self.assertEqual(0, done.returncode, done.stdout)
        self.assertIn("0 stale", done.stdout)
        self.assertIn("%d evergreen" % len(memory.read_lessons(ROOT)[0]), done.stdout)

    def test_no_shipped_row_is_rewritten_by_the_gate(self):
        """Byte-for-byte: --check and --windows are readers over the shipped ledger."""
        path = ROOT / "15_SYSTEM" / "memory" / "lessons.jsonl"
        before = path.read_text(encoding="utf-8")
        run_utf8([sys.executable, MEMORY, "--root", str(ROOT), "--check"], cwd=str(ROOT))
        run_utf8([sys.executable, MEMORY, "--root", str(ROOT), "--windows"], cwd=str(ROOT))
        self.assertEqual(before, path.read_text(encoding="utf-8"))


class TheContractIsWrittenDown(WindowFixture):
    """A rule only in a script is a second truth waiting to drift: schema and map must say it."""

    def test_the_schema_declares_both_fields_and_the_window_rule(self):
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        record = schema["record"]
        for field in ("verified_at", "expires"):
            self.assertIn(field, record, "%s is not in the record contract" % field)
            self.assertTrue(record[field].get("optional"), "%s must be optional" % field)
        text = json.dumps(schema)
        for word in ("evergreen", "stale", "YYYY-MM-DD"):
            self.assertIn(word, text, "the schema must state the semantics, not name the field")
        self.assertTrue(any("stale" in line and "never" in line
                            for line in schema["invariants"]),
                        "an invariant must forbid deleting or rewriting a stale row")

    def test_the_memory_plane_map_states_the_semantics_and_points_at_the_measurement(self):
        text = MAP.read_text(encoding="utf-8")
        for phrase in ("verified_at", "expires", "evergreen", "stale", "--windows"):
            self.assertIn(phrase, text, "the map does not state the window rule (%s)" % phrase)
        self.assertIn("zero stale", text,
                      "the map must carry what the gate has always measured, not a bare promise")
        self.assertNotIn("row(s): ", text,
                         "the map froze a row count; a landing lesson makes the prose a liar — "
                         "point the reader at `memory.py --windows` instead")

    def test_the_door_help_lists_the_window_flags(self):
        done = run_utf8([sys.executable, MEMORY, "--help"], cwd=str(ROOT))
        self.assertIn("--verified-at", done.stdout)
        self.assertIn("--expires", done.stdout)
        self.assertIn("--windows", done.stdout)


if __name__ == "__main__":
    unittest.main()
