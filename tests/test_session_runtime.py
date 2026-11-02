"""End-to-end session enforcement across Brain CLI and central tool registry.

All writes are in temporary private SQLite stores. No model or network required.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
import brain  # noqa: E402
from backend.tools_kit import Context, Registry, Tool, ToolError  # noqa: E402
from backend import session_bridge  # noqa: E402


ACTOR = "AGT-ABCD1234"


class MemoryProbe(Tool):
    name = "test.memory_probe"
    description = "Mock read tool; it does no IO and returns a private-shaped response."
    behavior = "read_only"

    def __init__(self, fails=False):
        self.calls = 0
        self.fails = fails

    def run(self, root, ctx, args):
        self.calls += 1
        if self.fails:
            raise ToolError("mock failure")
        return "PRIVATE_RESULT_SHOULD_NOT_BE_PERSISTED"


class SessionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "02_WIKI").mkdir()
        (self.root / "02_WIKI" / "evidence.md").write_text("proof", encoding="utf-8")
        (self.root / "skills" / "inspect").mkdir(parents=True)
        (self.root / "skills" / "inspect" / "SKILL.md").write_text(
            "---\nname: inspect\ndescription: inspect work\n---\n",
            encoding="utf-8")
        agent = self.root / "11_CONTROL" / "agents" / "actor"
        agent.mkdir(parents=True)
        (agent / "agent.json").write_text(
            '{"id":"AGT-ABCD1234","kind":"agent","status":"draft"}',
            encoding="utf-8")
        self.sid = brain.start(self.root, ACTOR, "inspect a task")["session"]
        self.tasks = brain.view(self.root, self.sid)["tasks"]
        self.work_id = self.tasks[2]["id"]
        self.probe = MemoryProbe()
        self.registry = Registry()
        self.registry.register(self.probe)

    def tearDown(self):
        self.tmp.cleanup()

    def ctx(self, session=None, actor=ACTOR, task_id=None):
        return Context(self.root, actor_id=actor, actor_kind="agent",
                       session_id=self.sid if session is None else session,
                       task_id=self.work_id if task_id is None else task_id)

    def ready(self):
        brain.finish(self.root, self.sid, self.tasks[0]["id"], "skills/inspect/SKILL.md")
        brain.finish(self.root, self.sid, self.tasks[1]["id"], "02_WIKI/evidence.md")

    def test_preflight_rejects_tool_before_skills(self):
        with self.assertRaisesRegex(ToolError, "skill review"):
            self.registry.execute(self.ctx(), "test.memory_probe", {})
        self.assertEqual(0, self.probe.calls)

    def test_preflight_rejects_tool_after_only_skills(self):
        brain.finish(self.root, self.sid, self.tasks[0]["id"], "skills/inspect/SKILL.md")
        with self.assertRaisesRegex(ToolError, "task plan"):
            self.registry.execute(self.ctx(), "test.memory_probe", {})
        self.assertEqual(0, self.probe.calls)

    def test_preflight_does_not_allow_wrong_actor(self):
        self.ready()
        with self.assertRaisesRegex(ToolError, "actor does not own"):
            self.registry.execute(self.ctx(actor="AGT-22222222"), "test.memory_probe", {})
        self.assertEqual(0, self.probe.calls)

    def test_preflight_rejects_plan_task_as_execution_target(self):
        self.ready()
        with self.assertRaisesRegex(brain.Refused, "open work"):
            brain.preflight(self.root, self.sid, ACTOR, self.tasks[1]["id"])

    def test_tool_audit_never_logs_response_body(self):
        self.ready()
        result = self.registry.execute(self.ctx(), "test.memory_probe", {})
        self.assertEqual("PRIVATE_RESULT_SHOULD_NOT_BE_PERSISTED", result)
        trace = brain.timeline(self.root, self.sid)
        self.assertEqual(["tool_attempt", "tool_ok"], [e["kind"] for e in trace["events"]][-2:])
        self.assertNotIn("PRIVATE_RESULT_SHOULD_NOT_BE_PERSISTED", str(trace))
        self.assertEqual(64, len(trace["events"][-1]["details"]["result_sha256"]))

    def test_failed_tool_is_audited_but_does_not_close_session(self):
        self.ready()
        tool = MemoryProbe(fails=True)
        self.registry = Registry()
        self.registry.register(tool)
        with self.assertRaisesRegex(ToolError, "mock failure"):
            self.registry.execute(self.ctx(), "test.memory_probe", {})
        self.assertEqual("tool_failed", brain.timeline(self.root, self.sid)["events"][-1]["kind"])
        self.assertEqual("active", brain.view(self.root, self.sid)["state"])

    def test_default_legacy_calls_remain_compatible(self):
        with patch.dict(os.environ, {"SBO_REQUIRE_SESSION": "0"}):
            result = self.registry.execute(
                Context(self.root, actor_id=ACTOR, actor_kind="agent"),
                "test.memory_probe", {})
        self.assertIn("PRIVATE_RESULT", result)

    def test_strict_mode_denies_sessionless_calls(self):
        with patch.dict(os.environ, {"SBO_REQUIRE_SESSION": "1"}):
            with self.assertRaisesRegex(ToolError, "requires --session"):
                self.registry.execute(
                    Context(self.root, actor_id=ACTOR, actor_kind="agent"),
                    "test.memory_probe", {})
        self.assertEqual(0, self.probe.calls)

    def test_handoff_is_invalidated_by_discovered_task(self):
        self.ready()
        brain.handoff(self.root, self.sid, "reviewed", "next step", "none")
        self.assertTrue(brain.view(self.root, self.sid)["handoff_written"])
        brain.add(self.root, self.sid, "newly found work")
        state = brain.view(self.root, self.sid)
        self.assertFalse(state["handoff_written"])
        self.assertEqual("todo", next(t for t in state["tasks"] if t["category"] == "handoff")["state"])
        with self.assertRaisesRegex(brain.Refused, "handoff"):
            brain.close(self.root, self.sid, "partial")

    def test_handoff_is_invalidated_when_work_finishes(self):
        self.ready()
        brain.handoff(self.root, self.sid, "draft", "next", "")
        brain.finish(self.root, self.sid, self.work_id, "02_WIKI/evidence.md")
        self.assertFalse(brain.view(self.root, self.sid)["handoff_written"])

    def test_handoff_is_invalidated_by_tool_execution(self):
        self.ready()
        brain.handoff(self.root, self.sid, "draft", "next", "")
        self.registry.execute(self.ctx(), "test.memory_probe", {})
        self.assertFalse(brain.view(self.root, self.sid)["handoff_written"])

    def test_symlink_to_secret_inside_root_is_not_evidence(self):
        directory = self.root / ".secrets"
        directory.mkdir()
        secret = directory / "key.md"
        secret.write_text("secret", encoding="utf-8")
        link = self.root / "02_WIKI" / "linked.md"
        try:
            link.symlink_to(secret)
        except OSError:
            self.skipTest("symlink unavailable")
        with self.assertRaisesRegex(brain.Refused, "protected or private"):
            brain.evidence_path(self.root, "02_WIKI/linked.md")

    def test_timeline_limit_and_validation(self):
        self.ready()
        self.registry.execute(self.ctx(), "test.memory_probe", {})
        self.assertEqual(1, len(brain.timeline(self.root, self.sid, limit=1)["events"]))
        with self.assertRaisesRegex(brain.Refused, "1-1000"):
            brain.timeline(self.root, self.sid, limit=0)

    def test_no_open_work_task_means_no_execution(self):
        self.ready()
        brain.finish(self.root, self.sid, self.work_id, "02_WIKI/evidence.md")
        with self.assertRaisesRegex(brain.Refused, "create or reopen"):
            brain.preflight(self.root, self.sid, ACTOR)

    def test_closed_session_denies_tool_even_if_preflight_was_done(self):
        self.ready()
        brain.handoff(self.root, self.sid, "done", "next", "")
        brain.close(self.root, self.sid, "partial")
        with self.assertRaisesRegex(ToolError, "closed"):
            self.registry.execute(self.ctx(), "test.memory_probe", {})


if __name__ == "__main__":
    unittest.main()
