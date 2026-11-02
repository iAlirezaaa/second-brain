"""MCP door session gate tests using fake tool functions and isolated actors.

These tests never create real proposals, import sources or access personal data.
"""
import json
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
import mcp_server  # noqa: E402

AGENT = "AGT-ABCD1234"


class SessionMCPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "02_WIKI").mkdir()
        (self.root / "02_WIKI" / "proof.md").write_text("Evidence", encoding="utf-8")
        (self.root / "skills" / "check").mkdir(parents=True)
        (self.root / "skills" / "check" / "SKILL.md").write_text(
            "---\nname: check\ndescription: inspect task\n---\n", encoding="utf-8")
        self.agent_json = self.root / "11_CONTROL" / "agents" / "tester" / "agent.json"
        self.agent_json.parent.mkdir(parents=True)
        self.set_allowlist([])
        self.sid = brain.start(self.root, AGENT, "inspect task")["session"]
        self.tasks = brain.view(self.root, self.sid)["tasks"]
        self.task_id = self.tasks[2]["id"]

    def tearDown(self):
        self.tmp.cleanup()

    def set_allowlist(self, names):
        self.agent_json.write_text(json.dumps({
            "id": AGENT, "kind": "agent", "status": "draft", "tool_allowlist": names
        }), encoding="utf-8")

    def ready(self):
        brain.finish(self.root, self.sid, self.tasks[0]["id"], "skills/check/SKILL.md")
        brain.finish(self.root, self.sid, self.tasks[1]["id"], "02_WIKI/proof.md")

    def call(self, name="capabilities", sid=None, actor=AGENT, task_id=None, **kwargs):
        args = {"session_id": self.sid if sid is None else sid,
                "actor_id": actor, "task_id": self.task_id if task_id is None else task_id}
        args.update(kwargs)
        with patch.dict(mcp_server.TOOL_FUNCS, {
            "capabilities": lambda root, data: "SAFE_RESULT",
            "candidate_propose": lambda root, data: "PROPOSAL_ONLY"}):
            return mcp_server.handle_tool_call(self.root, {"name": name, "arguments": args})

    def test_strict_mode_blocks_legacy_mcp_call_before_execution(self):
        calls = []
        with patch.dict(os.environ, {"SBO_REQUIRE_SESSION": "1"}):
            with patch.dict(mcp_server.TOOL_FUNCS, {
                    "capabilities": lambda root, args: calls.append(True) or "READ"}):
                out = mcp_server.handle_tool_call(
                    self.root, {"name": "capabilities", "arguments": {}})
        self.assertTrue(out["isError"])
        self.assertIn("requires --session", out["content"][0]["text"])
        self.assertEqual([], calls)

    def test_session_cannot_skip_skill_review(self):
        out = self.call()
        self.assertTrue(out["isError"])
        self.assertIn("skill review", out["content"][0]["text"])

    def test_session_wrong_actor_does_not_cross_boundary(self):
        self.ready()
        out = self.call(actor="AGT-22222222")
        self.assertTrue(out["isError"])
        self.assertIn("actor does not own", out["content"][0]["text"])

    def test_session_read_tool_is_audited_without_its_result_text(self):
        self.ready()
        out = self.call()
        self.assertFalse(out.get("isError"))
        self.assertEqual("SAFE_RESULT", out["content"][0]["text"])
        events = brain.timeline(self.root, self.sid)["events"]
        self.assertEqual(["tool_attempt", "tool_ok"], [x["kind"] for x in events][-2:])
        self.assertEqual("mcp.capabilities", events[-1]["details"]["tool"])
        self.assertNotIn("SAFE_RESULT", str(events))

    def test_mcp_write_denied_if_not_in_actor_allowlist(self):
        self.ready()
        out = self.call(name="candidate_propose")
        self.assertTrue(out["isError"])
        self.assertIn("tool_allowlist", out["content"][0]["text"])

    def test_mcp_write_allowed_for_explicit_registered_actor_grant(self):
        self.ready()
        self.set_allowlist(["candidate_propose"])
        out = self.call(name="candidate_propose")
        self.assertFalse(out.get("isError"))
        self.assertEqual("PROPOSAL_ONLY", out["content"][0]["text"])

    def test_schema_advertises_session_fields_to_clients(self):
        for row in mcp_server.TOOLS:
            self.assertTrue({"session_id", "actor_id", "task_id"}.issubset(
                row["inputSchema"]["properties"].keys()), row["name"])

    def test_mcp_refuses_non_object_arguments(self):
        out = mcp_server.handle_tool_call(
            self.root, {"name": "capabilities", "arguments": ["not", "an", "object"]})
        self.assertTrue(out["isError"])
        self.assertIn("object", out["content"][0]["text"])

    def test_default_mode_still_accepts_legacy_sessionless_call(self):
        with patch.dict(os.environ, {"SBO_REQUIRE_SESSION": "0"}):
            with patch.dict(mcp_server.TOOL_FUNCS, {
                    "capabilities": lambda root, args: "LEGACY_OK"}):
                out = mcp_server.handle_tool_call(
                    self.root, {"name": "capabilities", "arguments": {}})
        self.assertEqual("LEGACY_OK", out["content"][0]["text"])

    def test_private_result_does_not_enter_error_text_after_audit(self):
        self.ready()
        def broken(root, args):
            raise mcp_server.ToolRefused("purposefully refused")
        with patch.dict(mcp_server.TOOL_FUNCS, {"capabilities": broken}):
            out = mcp_server.handle_tool_call(
                self.root, {"name": "capabilities", "arguments": {
                    "session_id": self.sid, "actor_id": AGENT, "task_id": self.task_id}})
        self.assertTrue(out["isError"])
        self.assertEqual("tool_failed", brain.timeline(self.root, self.sid)["events"][-1]["kind"])


if __name__ == "__main__":
    unittest.main()
