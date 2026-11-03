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


class MemoryWriteProbe(Tool):
    name = "test.memory_write_probe"
    description = "Mock idempotent write tool used to verify permission refusals."
    behavior = "idempotent"
    writes = True

    def __init__(self):
        self.calls = 0

    def run(self, root, ctx, args):
        self.calls += 1
        return "PRIVATE_WRITE_RESULT"


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
            '{"id":"AGT-ABCD1234","kind":"agent","status":"draft",'
            '"tool_allowlist":[]}',
            encoding="utf-8")
        self.sid = brain.start(self.root, ACTOR, "inspect a task")["session"]
        self.tasks = brain.view(self.root, self.sid)["tasks"]
        self.work_id = self.tasks[2]["id"]
        self.probe = MemoryProbe()
        self.registry = Registry()
        self.registry.register(self.probe)

    def tearDown(self):
        self.tmp.cleanup()

    def ctx(self, session=None, actor=ACTOR, task_id=None, allow_writes=False,
            allowlist=(), actor_kind="agent"):
        return Context(self.root, actor_id=actor, actor_kind=actor_kind,
                        allow_writes=allow_writes, allowlist=allowlist,
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

    def test_preflight_reports_draft_status_and_configured_access(self):
        self.ready()
        result = brain.preflight(self.root, self.sid, ACTOR, self.work_id)
        self.assertEqual("draft", result["actor_status"])
        self.assertEqual([], result["registered_tool_allowlist"])
        self.assertEqual("valid", result["allowlist_state"])
        self.assertEqual("preflight grants no writes; host tool gates apply",
                         result["write_access"])

    def test_preflight_reports_malformed_allowlist_without_granting_access(self):
        self.ready()
        agent = next((self.root / "11_CONTROL" / "agents").glob("*/agent.json"))
        agent.write_text('{"id":"AGT-ABCD1234","kind":"agent","status":"draft",'
                         '"tool_allowlist":"not-a-list"}', encoding="utf-8")
        result = brain.preflight(self.root, self.sid, ACTOR, self.work_id)
        self.assertEqual("draft", result["actor_status"])
        self.assertEqual([], result["registered_tool_allowlist"])
        self.assertEqual("invalid", result["allowlist_state"])

    def test_preflight_reports_missing_actor_record_without_changing_preflight(self):
        self.ready()
        for path in (self.root / "11_CONTROL" / "agents").glob("*/agent.json"):
            path.unlink()
        result = brain.preflight(self.root, self.sid, ACTOR, self.work_id)
        self.assertEqual("unknown", result["actor_status"])
        self.assertEqual([], result["registered_tool_allowlist"])
        self.assertEqual("missing", result["allowlist_state"])

    def test_write_denial_without_approval_is_audited_without_payload(self):
        self.ready()
        tool = MemoryWriteProbe()
        self.registry = Registry()
        self.registry.register(tool)
        with self.assertRaisesRegex(ToolError, "not approved \(--approve\)"):
            self.registry.execute(self.ctx(), tool.name, {"secret": "PRIVATE_ARGUMENT"})
        events = brain.timeline(self.root, self.sid)["events"]
        denied = [event for event in events if event["kind"] == "tool_denied"]
        self.assertEqual(1, len(denied))
        self.assertEqual({"tool": tool.name, "task_id": self.work_id,
                          "reason": "approval_missing"}, denied[0]["details"])
        self.assertEqual(0, tool.calls)
        self.assertNotIn("PRIVATE_ARGUMENT", str(events))
        self.assertNotIn("PRIVATE_WRITE_RESULT", str(events))
        self.assertFalse(any(event["kind"] in ("tool_attempt", "tool_failed")
                             for event in events))

    def test_write_denial_for_missing_allowlist_is_audited(self):
        self.ready()
        tool = MemoryWriteProbe()
        self.registry = Registry()
        self.registry.register(tool)
        with self.assertRaisesRegex(ToolError, "tool_allowlist"):
            self.registry.execute(self.ctx(allow_writes=True), tool.name,
                                  {"secret": "PRIVATE_ARGUMENT"})
        event = brain.timeline(self.root, self.sid)["events"][-1]
        self.assertEqual("tool_denied", event["kind"])
        self.assertEqual({"tool": tool.name, "task_id": self.work_id,
                          "reason": "allowlist_missing"}, event["details"])
        self.assertEqual(0, tool.calls)
        self.assertNotIn("PRIVATE_ARGUMENT", str(event))

    def test_write_denial_for_missing_actor_is_audited_in_human_session(self):
        human_sid = brain.start(self.root, "human", "human-owned write refusal") ["session"]
        human_tasks = brain.view(self.root, human_sid)["tasks"]
        brain.finish(self.root, human_sid, human_tasks[0]["id"], "skills/inspect/SKILL.md")
        brain.finish(self.root, human_sid, human_tasks[1]["id"], "02_WIKI/evidence.md")
        work_id = human_tasks[2]["id"]
        tool = MemoryWriteProbe()
        self.registry = Registry()
        self.registry.register(tool)
        with self.assertRaisesRegex(ToolError, "context has no actor"):
            self.registry.execute(self.ctx(session=human_sid, actor="", task_id=work_id,
                                            allow_writes=True), tool.name, {})
        event = brain.timeline(self.root, human_sid)["events"][-1]
        self.assertEqual("tool_denied", event["kind"])
        self.assertEqual({"tool": tool.name, "task_id": work_id,
                          "reason": "actor_missing"}, event["details"])
        self.assertEqual(0, tool.calls)

    def test_agent_missing_actor_is_preflight_refusal_not_audited(self):
        self.ready()
        before = len(brain.timeline(self.root, self.sid)["events"])
        tool = MemoryWriteProbe()
        self.registry = Registry()
        self.registry.register(tool)
        with self.assertRaisesRegex(ToolError, "actor does not own"):
            self.registry.execute(self.ctx(actor=""), tool.name, {})
        events = brain.timeline(self.root, self.sid)["events"]
        self.assertEqual(before, len(events))
        self.assertEqual(0, tool.calls)

    def test_denial_audit_failure_preserves_policy_error_and_never_executes(self):
        self.ready()
        tool = MemoryWriteProbe()
        self.registry = Registry()
        self.registry.register(tool)
        with patch.object(session_bridge, "audit", side_effect=ValueError("audit unavailable")):
            with self.assertRaisesRegex(ToolError, "not approved \(--approve\)") as caught:
                self.registry.execute(self.ctx(), tool.name, {})
        self.assertEqual("tool %s writes; this context is not approved (--approve)" % tool.name,
                         str(caught.exception))
        self.assertEqual(0, tool.calls)

    def test_denial_audit_rejects_unbounded_reason_and_payload(self):
        before = len(brain.timeline(self.root, self.sid)["events"])
        with self.assertRaisesRegex(brain.Refused, "reason is invalid"):
            brain.audit_tool(self.root, self.sid, ACTOR, "test.write", "denied", "",
                             self.work_id, reason="PRIVATE_REASON")
        with self.assertRaisesRegex(brain.Refused, "cannot include a payload"):
            brain.audit_tool(self.root, self.sid, ACTOR, "test.write", "denied",
                             "PRIVATE_ARGUMENT", self.work_id,
                             reason="allowlist_missing")
        self.assertEqual(before, len(brain.timeline(self.root, self.sid)["events"]))

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

    def test_storage_and_handoff_are_private_on_posix(self):
        if os.name == "nt":
            self.skipTest("Windows ACLs require a separate permission test")
        brain.handoff(self.root, self.sid, "private notes", "resume", "none")
        paths = [self.root / ".brain-data",
                 self.root / ".brain-data" / "operator",
                 self.root / ".brain-data" / "operator" / "sessions.sqlite3",
                 self.root / ".brain-data" / "operator" / "handoffs" / (self.sid + ".md")]
        for path in paths:
            self.assertEqual(0, path.stat().st_mode & 0o077,
                             "%s must not be accessible by group/other users" % path)

    def test_skill_draft_is_private_on_posix(self):
        if os.name == "nt":
            self.skipTest("Windows ACLs require a separate permission test")
        self.ready()
        brain.handoff(self.root, self.sid, "private notes", "resume", "")
        result = brain.close(self.root, self.sid, "partial")
        path = self.root / result["draft_skill"]
        self.assertTrue(path.is_file())
        self.assertEqual(0, path.stat().st_mode & 0o077)

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
