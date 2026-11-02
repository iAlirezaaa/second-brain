"""Phase 44 item 1 — every tool the doors expose says what kind of act it is.

Basic Memory answers "what can this harness call, and what will it do" with progressive tool
discovery: a client reads the tool list and decides what to touch. The discovery machinery is
AGPL code this repo refuses; the *tag* is the useful part and costs nothing. So every tool the
MCP door (`15_SYSTEM/scripts/mcp_server.py`) and the engine toolkit
(`15_SYSTEM/scripts/backend/tools_kit.py`) expose now carries one closed-set behaviour tag —
`read_only`, `idempotent`, `destructive` — and a new audit cross-checks the tags against the
actor registry: an agent's `tool_allowlist` in `11_CONTROL/agents/*/agent.json` may not name a
tool no door declares, and may not grant a `destructive` tool the harness door carries no tag
for. A tool reachable with a missing or invented tag is a refusal, never a silent pass.

Every refusal below is proven by breaking a fixture on purpose and reading the refusal.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))

import mcp_server  # noqa: E402
from backend import tools_kit  # noqa: E402
from backend.tools_kit import Tool, ToolError, default_registry  # noqa: E402
from common import run_utf8  # noqa: E402

SERVER = str(ROOT / "15_SYSTEM" / "scripts" / "mcp_server.py")
CLOSED = ("destructive", "idempotent", "read_only")


def door_rows():
    return [{"name": t["name"], "behavior": t.get("behavior")} for t in mcp_server.TOOLS]


def engine_rows():
    return default_registry().rows()


def agents_of(pairs):
    return [{"id": cid, "tool_allowlist": list(names)} for cid, names in pairs]


def audit(door=None, funcs=None, engine=None, agents=None):
    return mcp_server.audit_tags(door if door is not None else door_rows(),
                                 funcs if funcs is not None else set(mcp_server.TOOL_FUNCS),
                                 engine if engine is not None else engine_rows(),
                                 agents if agents is not None else [])


class TheClosedSetIsClosed(unittest.TestCase):
    """The vocabulary is one tuple, read from one place, and nothing else is legal."""

    def test_the_tag_vocabulary_is_exactly_the_three_named_behaviours(self):
        self.assertEqual(sorted(CLOSED), sorted(mcp_server.BEHAVIOR_TAGS))
        self.assertEqual(mcp_server.BEHAVIOR_TAGS, tools_kit.BEHAVIOR_TAGS,
                         "the door and the engine must read one vocabulary, not two")

    def test_every_door_tool_declares_a_tag_from_the_closed_set(self):
        for tool in mcp_server.TOOLS:
            self.assertIn("behavior", tool,
                          "%s is exposed with no behaviour tag" % tool["name"])
            self.assertIn(tool["behavior"], mcp_server.BEHAVIOR_TAGS,
                          "%s carries invented tag %r" % (tool["name"], tool["behavior"]))

    def test_every_engine_tool_declares_a_tag_from_the_closed_set(self):
        for row in engine_rows():
            self.assertIn(row["behavior"], mcp_server.BEHAVIOR_TAGS,
                          "%s carries tag %r" % (row["name"], row["behavior"]))

    def test_an_engine_tool_that_writes_is_never_tagged_read_only(self):
        for row in engine_rows():
            if row["writes"]:
                self.assertNotEqual("read_only", row["behavior"],
                                    "%s writes but calls itself read_only" % row["name"])
            else:
                self.assertEqual("read_only", row["behavior"],
                                 "%s changes nothing but is tagged %s"
                                 % (row["name"], row["behavior"]))

    def test_the_shipped_doors_carry_no_destructive_tool(self):
        """Measured, not asserted in prose: 0 of 13 door tools and 0 of 6 engine tools destroy
        state today. The day one is added, this row goes red and the allowlist cross-check
        becomes load-bearing instead of decorative."""
        problems = audit(agents=[{"id": "AGT-MEASURE", "tool_allowlist": []}])
        self.assertEqual([], problems, problems)
        self.assertEqual([], mcp_server.destructive_names(mcp_server.TOOLS, engine_rows()))


class TagsReachTheClient(unittest.TestCase):
    """A tag a client cannot read is a comment. tools/list must carry it on the wire."""

    def test_tools_list_tags_every_tool(self):
        responses = []
        mcp_server.handle(ROOT, {"jsonrpc": "2.0", "id": 1, "method": "tools/list",
                                 "params": {}}, responses)
        tools = responses[0]["result"]["tools"]
        self.assertEqual(len(mcp_server.TOOLS), len(tools))
        for tool in tools:
            self.assertIn(tool.get("behavior"), mcp_server.BEHAVIOR_TAGS,
                          "the wire offered %s with tag %r" % (tool.get("name"),
                                                               tool.get("behavior")))

    def test_the_writes_gate_and_the_tag_agree_on_the_engine_toolkit(self):
        """core.ltm_store is the one engine tool the write gate bites on; it must be the one
        tool that is not read_only -- a tag that disagrees with the gate is the second truth."""
        row = [r for r in engine_rows() if r["name"] == "core.ltm_store"][0]
        self.assertTrue(row["writes"])
        self.assertEqual("idempotent", row["behavior"])
        for other in engine_rows():
            if other["name"] != "core.ltm_store":
                self.assertEqual("read_only", other["behavior"], other["name"])


class TheAuditRefuses(unittest.TestCase):
    """Each refusal is proven by breaking the fixture on purpose and reading the refusal."""

    def test_a_missing_tag_is_named_as_untagged(self):
        broken = [dict(t) for t in door_rows()]
        for row in broken:
            if row["name"] == "vault_search":
                del row["behavior"]
        problems = audit(door=broken)
        self.assertTrue(any("vault_search" in p and "no behaviour tag" in p
                            for p in problems), problems)

    def test_an_invented_tag_is_refused_with_the_closed_set(self):
        broken = [dict(t) for t in door_rows()]
        for row in broken:
            if row["name"] == "candidate_propose":
                row["behavior"] = "read_mostly"
        problems = audit(door=broken)
        self.assertTrue(any("read_mostly" in p and "candidate_propose" in p
                            for p in problems), problems)
        self.assertTrue(any("destructive" in p and "idempotent" in p and "read_only" in p
                            for p in problems),
                        "the refusal must name the vocabulary it refused: %s" % problems)

    def test_a_reachable_tool_that_was_never_declared_carries_no_tag(self):
        problems = audit(funcs=set(mcp_server.TOOL_FUNCS) | {"registry_apply"})
        self.assertTrue(any("registry_apply" in p for p in problems), problems)

    def test_a_declared_tool_with_nothing_behind_it_is_refused(self):
        funcs = set(mcp_server.TOOL_FUNCS)
        funcs.discard("runs_list")
        problems = audit(funcs=funcs)
        self.assertTrue(any("runs_list" in p for p in problems), problems)

    def test_an_untagged_engine_tool_is_refused(self):
        broken = [dict(r) for r in engine_rows()]
        broken[0]["behavior"] = None
        problems = audit(engine=broken)
        self.assertTrue(any(broken[0]["name"] in p and "no behaviour tag" in p
                            for p in problems), problems)

    def test_an_engine_tool_that_invented_a_tag_is_refused_at_registration(self):
        """The closed set is closed at the door of the registry, not only in the audit."""
        class Invented(Tool):
            name = "core.invented"
            behavior = "read_mostly"

            def run(self, root, ctx, args):
                return "never runs"

        with self.assertRaises(ToolError) as caught:
            default_registry().register(Invented())
        self.assertIn("read_mostly", str(caught.exception))

    def test_an_engine_tool_whose_tag_contradicts_its_write_gate_is_refused(self):
        broken = [dict(r) for r in engine_rows()]
        for row in broken:
            if row["writes"]:
                row["behavior"] = "read_only"
        problems = audit(engine=broken)
        self.assertTrue(any("write gate" in p for p in problems), problems)

    def test_a_door_and_engine_that_tag_the_same_capability_differently_are_refused(self):
        broken = [dict(r) for r in engine_rows()]
        for row in broken:
            if row["name"] == "core.vault_search":
                row["behavior"] = "idempotent"
        problems = audit(engine=broken)
        self.assertTrue(any("vault_search" in p and "TAG DRIFT" in p for p in problems), problems)

    def test_an_allowlist_naming_a_tool_no_door_declares_is_refused(self):
        problems = audit(agents=agents_of([("AGT-DEADBEEF", ["registry_delete"])]))
        self.assertTrue(any("AGT-DEADBEEF" in p and "registry_delete" in p for p in problems),
                        problems)

    def test_a_destructive_grant_the_door_carries_no_tag_for_is_refused(self):
        """The phase's own words: an allowlist may not allow a destructive tool whose tag the
        door does not carry. The engine holds the destructive tool; the harness door is silent."""
        engine = engine_rows() + [{"name": "core.fs_delete", "behavior": "destructive",
                                   "writes": True}]
        problems = audit(engine=engine,
                         agents=agents_of([("AGT-CAFE0001", ["core.fs_delete"])]))
        self.assertTrue(any("core.fs_delete" in p and "destructive" in p and "AGT-CAFE0001" in p
                            for p in problems), problems)

    def test_a_destructive_tool_the_door_does_tag_is_not_refused_for_being_tagged(self):
        """The other direction, so the rule is a cross-check and not a blanket ban: the door
        carries the tag, so the grant is at least legible to the client that would use it."""
        door = door_rows() + [{"name": "core.fs_delete", "behavior": "destructive"}]
        engine = engine_rows() + [{"name": "core.fs_delete", "behavior": "destructive",
                                   "writes": True, "declared": True}]
        funcs = set(mcp_server.TOOL_FUNCS) | {"core.fs_delete"}
        problems = audit(door=door, funcs=funcs, engine=engine,
                         agents=agents_of([("AGT-CAFE0002", ["core.fs_delete"])]))
        self.assertEqual([], [p for p in problems if "core.fs_delete" in p], problems)

    def test_a_tool_that_never_declared_a_tag_is_carried_as_the_worst_case_and_named(self):
        """The toolkit's BaseTool has no way to be 'unspecified' safely: an undeclared tool is
        carried as `destructive` (worst case, never a silent read_only) and the audit names it,
        so a legacy or fixture tool cannot hide behind a missing tag."""
        class Untagged(Tool):
            name = "core.untagged"

            def run(self, root, ctx, args):
                return "never runs"

        reg = default_registry()
        reg.register(Untagged())                      # a fixture tool still registers
        self.assertEqual("destructive", reg.get("core.untagged").behavior)
        rows = reg.rows()
        row = [r for r in rows if r["name"] == "core.untagged"][0]
        self.assertFalse(row["declared"], "the registry must say the tag was inherited")
        problems = audit(engine=rows)
        self.assertTrue(any("core.untagged" in p and "no behaviour tag" in p
                            for p in problems), problems)


class TheGateRunsOnTheRealHouse(unittest.TestCase):
    """Not a fixture: the shipped doors and the shipped actor records must satisfy the audit."""

    def test_check_tools_is_green_on_this_repo(self):
        result = run_utf8([sys.executable, SERVER, "--root", str(ROOT), "--check-tools"],
                          cwd=str(ROOT))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)
        self.assertIn("tool(s) tagged", result.stdout)

    def test_the_shipped_agent_allowlists_are_all_tagged_by_a_door(self):
        rows = mcp_server.agent_rows(ROOT)
        names = {str(tool["name"]) for tool in mcp_server.TOOLS} | set(engine_names())
        self.assertTrue(rows, "the audit would pass an empty registry by accident")
        for row in rows:
            for tool in row["tool_allowlist"]:
                self.assertIn(tool, names, "%s grants %s, which no door declares"
                              % (row["id"], tool))


class TheGateRefusesARealActorRecord(unittest.TestCase):
    """The reviewer's command: break one agent record and read the refusal from the CLI."""

    def fixture(self, allowlist):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        agents = root / "11_CONTROL" / "agents" / "AGT-11111111-tampered"
        agents.mkdir(parents=True)
        (agents / "agent.json").write_text(json.dumps({
            "kind": "agent", "id": "AGT-11111111", "name": "tampered",
            "tool_allowlist": list(allowlist)}), encoding="utf-8")
        return root

    def test_an_allowlist_of_a_tool_no_door_carries_is_refused_by_the_command(self):
        root = self.fixture(["registry_delete"])
        result = run_utf8([sys.executable, SERVER, "--root", str(root), "--check-tools"],
                          cwd=str(ROOT))
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("registry_delete", result.stdout)
        self.assertIn("AGT-11111111", result.stdout)

    def test_a_clean_fixture_record_is_green(self):
        root = self.fixture(["candidate_propose"])
        result = run_utf8([sys.executable, SERVER, "--root", str(root), "--check-tools"],
                          cwd=str(ROOT))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("1 agent record(s)", result.stdout)

    def test_a_root_with_no_actor_plane_states_that_instead_of_passing_silently(self):
        """An installed home ships no 11_CONTROL/agents: the audit says so out loud rather than
        reporting a cross-check over zero records as a clean house."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        result = run_utf8([sys.executable, SERVER, "--root", tmp.name, "--check-tools"],
                          cwd=str(ROOT))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("no agent records", result.stdout)


def engine_names():
    return default_registry().names()


if __name__ == "__main__":
    unittest.main()
