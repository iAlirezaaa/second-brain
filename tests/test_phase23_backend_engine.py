"""Phase 23 tests — the backend package: engine, toolkits, workflows, schedules, LTM.

SuperAGI's backend logic is ported here as a stdlib package (`15_SYSTEM/scripts/backend/`):
the AgentExecution state machine and step loop (`engine`), the BaseTool contract with
per-actor allowlists and double write-gating (`tools_kit`), declarative workflows
(`workflows`), pure schedule math (`schedules`) and an FTS5 long-term memory (`ltm`).
Everything deterministic; an LLM step is a human decision, so none exists here.
"""
import json
import subprocess
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "15_SYSTEM" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))

from backend import engine as engine_mod  # noqa: E402
from backend import ltm, schedules  # noqa: E402
from backend import workflows as wf_mod  # noqa: E402
from backend.engine import Engine, can_transition  # noqa: E402
from backend.tools_kit import Context, ToolError, default_registry  # noqa: E402
from test_phase22_harness_bridge import TempVault  # noqa: E402


class TestStateMachine(unittest.TestCase):
    """SuperAGI's AgentExecution statuses: the same moves, or nothing moves."""

    def test_only_legal_moves(self):
        legal = [("created", "running"), ("created", "terminated"), ("running", "paused"),
                 ("running", "completed"), ("running", "failed"), ("running", "terminated"),
                 ("paused", "running"), ("paused", "terminated")]
        for old, new in legal:
            self.assertTrue(can_transition(old, new), (old, new))
        illegal = [("created", "completed"), ("created", "failed"), ("created", "paused"),
                   ("completed", "running"), ("failed", "running"),
                   ("terminated", "running"), ("completed", "failed")]
        for old, new in illegal:
            self.assertFalse(can_transition(old, new), (old, new))

    def test_terminal_states_are_terminal(self):
        for status in ("completed", "failed", "terminated"):
            self.assertEqual(frozenset(), engine_mod.TRANSITIONS[status], status)


class TestWorkflowValidate(unittest.TestCase):
    @staticmethod
    def base(**over):
        wf = {"name": "w", "steps": [
            {"name": "a", "type": "tool_call", "tool": "core.fs_read"},
            {"name": "b", "type": "done"}]}
        wf.update(over)
        return wf

    def test_legal(self):
        self.assertEqual([], wf_mod.validate(self.base()))

    def test_refusals(self):
        cases = [
            (self.base(name=""), "name: required"),
            (self.base(steps=[]), "steps: a non-empty list"),
            (self.base(steps=[{"name": "a", "type": "meditate"}]), "type must be one of"),
            (self.base(steps=[{"name": "a", "type": "tool_call"}]), "tool_call needs a tool"),
            (self.base(steps=[{"name": "a", "type": "done"}, {"name": "a", "type": "done"}]),
             "duplicate step names"),
            (self.base(max_steps=0), "max_steps: positive int"),
            (self.base(max_steps=True), "max_steps: positive int"),
            ("not a dict", "workflow must be a JSON object"),
        ]
        for wf, needle in cases:
            problems = wf_mod.validate(wf)
            self.assertTrue(problems, wf)
            self.assertTrue(any(needle in p for p in problems),
                            (needle, problems))


class TestEngine(TempVault, unittest.TestCase):
    """The step loop: read tools open, refusals become failed runs, the feed is told."""

    def outcome(self, wf, ctx, max_steps=None):
        events = []
        eng = Engine(default_registry(), max_steps=max_steps)
        out = eng.run(wf, ctx, feed=lambda status, text: events.append((status, text)))
        return out, events

    def test_happy_path_reads_then_done(self):
        wf = {"name": "w", "steps": [
            {"name": "read", "type": "tool_call", "tool": "core.fs_read",
             "args": {"path": "15_SYSTEM/config/system.json"}},
            {"name": "stop", "type": "done", "note": "feed ready for the human"}]}
        out, events = self.outcome(wf, Context(self.root, actor_id="AGT-X"))
        self.assertEqual("completed", out["status"], out)
        self.assertEqual(1, out["steps"])          # done is a decision, not a step
        self.assertTrue(any(e[0] == "ok" and "core.fs_read" in e[1] for e in events))
        self.assertTrue(any("feed ready" in e[1] for e in events))

    def test_unknown_tool_fails_the_run(self):
        wf = {"name": "w", "steps": [{"name": "x", "type": "tool_call", "tool": "nope.nada"}]}
        out, events = self.outcome(wf, Context(self.root))
        self.assertEqual("failed", out["status"])
        self.assertIn("unknown tool", out["reason"])
        self.assertTrue(any(e[0] == "fail" for e in events))

    def test_fail_step_and_unknown_type_fail(self):
        out, _ = self.outcome({"name": "w", "steps": [
            {"name": "give up", "type": "fail", "reason": "nothing worked"}]},
            Context(self.root))
        self.assertEqual("failed", out["status"])
        self.assertIn("nothing worked", out["reason"])
        out, _ = self.outcome({"name": "w", "steps": [
            {"name": "weird", "type": "meditate"}]}, Context(self.root))
        self.assertEqual("failed", out["status"])
        self.assertIn("unknown step type", out["reason"])

    def test_max_steps_guard(self):
        step = {"name": "again", "type": "tool_call", "tool": "core.fs_read",
                "args": {"path": "15_SYSTEM/config/system.json"}}
        wf = {"name": "w", "max_steps": 2,
              "steps": [dict(step, name="s%d" % i) for i in range(1, 4)]}
        out, events = self.outcome(wf, Context(self.root))
        self.assertEqual("failed", out["status"])
        self.assertIn("max_steps (2)", out["reason"])
        self.assertEqual(2, out["steps"])
        self.assertTrue(any("max_steps" in e[1] for e in events))
        # an explicit engine cap works even when the workflow carries none
        capped = {key: wf[key] for key in ("name", "steps")}
        out, _ = self.outcome(capped, Context(self.root), max_steps=2)
        self.assertEqual("failed", out["status"])
        self.assertIn("max_steps (2)", out["reason"])

    def test_write_tool_refused_inside_a_workflow(self):
        wf = {"name": "w", "steps": [
            {"name": "remember", "type": "tool_call", "tool": "core.ltm_store",
             "args": {"text": "unapproved memory"}}]}
        out, _ = self.outcome(wf, Context(self.root, actor_id="AGT-X"))
        self.assertEqual("failed", out["status"])
        self.assertIn("not approved", out["reason"])


class TestToolkitGates(TempVault, unittest.TestCase):
    """Read tools open; writes need --approve AND the actor's allowlist. Default deny."""

    def test_reads_are_open(self):
        text = default_registry().execute(Context(self.root), "core.fs_read",
                                          {"path": "15_SYSTEM/config/system.json"})
        self.assertIn("zones", text)

    def test_traversal_refused(self):
        with self.assertRaises(ToolError):
            default_registry().execute(Context(self.root), "core.fs_read",
                                       {"path": "../../outside.txt"})

    def test_writes_are_double_gated(self):
        reg = default_registry()
        args = {"text": "the gate held"}
        with self.assertRaises(ToolError):        # no --approve
            reg.execute(Context(self.root, actor_id="AGT-1"), "core.ltm_store", args)
        with self.assertRaises(ToolError):        # approved but no actor
            reg.execute(Context(self.root, allow_writes=True), "core.ltm_store", args)
        with self.assertRaises(ToolError):        # approved actor, empty allowlist
            reg.execute(Context(self.root, actor_id="AGT-1", allow_writes=True),
                        "core.ltm_store", args)
        out = reg.execute(Context(self.root, actor_id="AGT-1", allow_writes=True,
                                  allowlist=["core.ltm_store"]), "core.ltm_store", args)
        self.assertIn("stored as row 1", out)
        back = reg.execute(Context(self.root), "core.ltm_fetch", {"query": "gate"})
        self.assertIn("the gate held", back)

    def test_registry_tools_see_records(self):
        agt = self.new_record("agent", "Toolkit Actor")
        out = default_registry().execute(Context(self.root), "core.registry_show",
                                         {"id": agt})
        self.assertIn(agt, out)
        listing = default_registry().execute(Context(self.root), "core.registry_list",
                                             {"kind": "agent"})
        self.assertIn(agt, listing)


class TestSchedules(unittest.TestCase):
    """Pure due-math, UTC everywhere, both spec forms."""

    def test_every_minutes(self):
        last = datetime(2026, 10, 28, 10, 0, tzinfo=timezone.utc)
        self.assertTrue(schedules.is_due({"every_minutes": 30}, last,
                                         last + timedelta(minutes=30)))
        self.assertFalse(schedules.is_due({"every_minutes": 30}, last,
                                          last + timedelta(minutes=29, seconds=59)))
        self.assertTrue(schedules.is_due({"every_minutes": 30}, None,
                                         datetime.now(timezone.utc)))  # never ran

    def test_daily_at(self):
        spec = {"daily_at": "09:30"}
        last = datetime(2026, 10, 28, 9, 0, tzinfo=timezone.utc)      # ran before 09:30
        self.assertFalse(schedules.is_due(spec, last,
                                          datetime(2026, 10, 28, 9, 29)))
        self.assertTrue(schedules.is_due(spec, last, datetime(2026, 10, 28, 9, 30)))
        yesterday = datetime(2026, 10, 27, 9, 30, tzinfo=timezone.utc)
        self.assertFalse(schedules.is_due(spec, yesterday,
                                          datetime(2026, 10, 28, 9, 29)))  # rolls over
        self.assertTrue(schedules.is_due(spec, yesterday,
                                         datetime(2026, 10, 28, 9, 30)))
        self.assertEqual("2026-10-29T09:30:00Z",
                         schedules.next_run_after(spec, datetime(2026, 10, 28, 10, 0,
                                                                 tzinfo=timezone.utc)))

    def test_bad_spec_and_utc_parse(self):
        with self.assertRaises(ValueError):
            schedules.is_due({"cron": "* * * * *"}, None, datetime.now(timezone.utc))
        dt = schedules.parse_utc("2026-10-28T10:00:00Z")
        self.assertEqual(timezone.utc, dt.tzinfo)
        self.assertEqual(10, dt.hour)


class TestLtm(TempVault, unittest.TestCase):
    def test_store_fetch_roundtrip(self):
        self.assertEqual(1, ltm.store(self.root, "the latch opens on the third try",
                                      source="AGT-1"))
        ltm.store(self.root, "an unrelated note about trees", source="AGT-2")
        rows = ltm.fetch(self.root, "latch", k=5)
        self.assertTrue(rows)
        self.assertIn("latch", rows[0]["text"])
        self.assertEqual("AGT-1", rows[0]["source"])
        self.assertEqual([], ltm.fetch(self.root, ""))
        self.assertEqual([], ltm.fetch(self.root, "nothing-matches-this-zzz"))


class TestOrchestratorCli(TempVault, unittest.TestCase):
    """The CLI end to end on a temp vault: workflow -> run -> feed -> close."""

    def _wf_path(self, wf):
        wdir = self.root / "15_SYSTEM" / "workflows"
        wdir.mkdir(parents=True, exist_ok=True)
        path = wdir / "demo-test.json"
        path.write_text(json.dumps(wf), encoding="utf-8")
        return path

    def _run(self, *argv):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "orchestrator.py"), "--root", str(self.root)]
            + list(argv),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(self.root), timeout=300)

    def test_workflow_run_end_to_end(self):
        agt = self.new_record("agent", "Cli Runner")
        wf_path = self._wf_path({"name": "cli demo", "steps": [
            {"name": "read", "type": "tool_call", "tool": "core.fs_read",
             "args": {"path": "15_SYSTEM/config/system.json"}},
            {"name": "stop", "type": "done", "note": "all good"}]})
        proc = self._run("workflow", "run", "--file", str(wf_path), "--agent", agt)
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("WORKFLOW cli demo -> COMPLETED", proc.stdout)
        runs_root = self.root / "12_RUNTIME" / "agent_runs"
        run_dirs = [d for d in runs_root.iterdir() if d.is_dir()]
        self.assertEqual(1, len(run_dirs), proc.stdout)
        run_json = json.loads((run_dirs[0] / "run.json").read_text(encoding="utf-8"))
        self.assertEqual("completed", run_json["status"])
        self.assertEqual(agt, run_json["agent"])
        feed = (run_dirs[0] / "steps.jsonl").read_text(encoding="utf-8")
        self.assertIn('"ok"', feed)
        self.assertIn("core.fs_read", feed)

    def test_validate_and_run_refusals(self):
        bad = self._wf_path({"name": "", "steps": [
            {"name": "x", "type": "meditate"}]})
        proc = self._run("workflow", "validate", "--file", str(bad))
        self.assertEqual(2, proc.returncode)
        self.assertIn("not a legal workflow", proc.stdout)
        self.assertIn("type must be one of", proc.stdout)
        agt = self.new_record("agent", "Refused Runner")
        wf_path = self._wf_path({"name": "w", "steps": [{"name": "s", "type": "done"}]})
        proc = self._run("workflow", "run", "--file", str(wf_path),
                         "--agent", "AGT-NOSUCH")
        self.assertEqual(2, proc.returncode)
        self.assertIn("no actor record AGT-NOSUCH", proc.stdout)
        # a write tool without --approve is refused even for a real actor
        proc = self._run("tool", "call", "--tool", "core.ltm_store",
                         "--args", json.dumps({"text": "sneaky"}), "--agent", agt)
        self.assertEqual(2, proc.returncode)
        self.assertIn("not approved", proc.stdout)
        # the write goes through with --approve when the allowlist carries the tool
        code, out = self.cli("edit", "--id", agt, "--set", 'tool_allowlist=["core.ltm_store"]')
        self.assertEqual(0, code, out)
        plan_id = [ln.split()[1] for ln in out.splitlines() if ln.startswith("PLAN ")][0]
        code, out = self.cli("apply", "--plan", plan_id, "--approve")
        self.assertEqual(0, code, out)
        proc = self._run("tool", "call", "--tool", "core.ltm_store",
                         "--args", json.dumps({"text": "allowed now"}),
                         "--agent", agt, "--approve")
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("stored as row 1", proc.stdout)


if __name__ == "__main__":
    unittest.main()
