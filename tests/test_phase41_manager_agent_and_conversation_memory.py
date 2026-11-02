"""Phase 41 tests — the charter's manager is a record, and conversation memory is a path.

Two open criteria from the charter meet here, and both are the same kind of claim: a governed
thing described only in prose does not exist.

Issue #21 (charter section 7) asked for a management agent that creates and classifies projects,
tasks, agents and skills. Until these tests ran, the only agents in `11_CONTROL/agents/` were an
auditor and a loop runner, and the manager lived in one Persian sentence. So it is a registered
record now -- and the record must be a *proposer*, not a second door: it may file a plan, it may
not sign one. `tool_allowlist` is the field the engine already gates writes on
(`backend/tools_kit.py::Registry.execute`), so the assertion is made against the shipped actor.

Issue #20's last criterion asked that conversation-memory extraction get a defined path stated in
`AGENTS.md`. The machinery already existed (`backend/sources.py`, `backend/learning.py`); what was
missing was the named path and an audit of it. `skills/conversation-memory/SKILL.md` and
`02_WIKI/reference_maps/conversation-memory-path.md` are that path, and these tests refuse a
document that promises a mechanism the shipped doors do not have -- or that quietly forgets a
refusal the doors really enforce.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "15_SYSTEM" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "scripts"))

import mcp_server  # noqa: E402
import orchestrator  # noqa: E402
from backend import sources  # noqa: E402
from backend.tools_kit import Context, Registry, Tool, ToolError, default_registry  # noqa: E402
from common import run_utf8  # noqa: E402
from hades_fixture import Vault  # noqa: E402

SKILL = ROOT / "skills" / "conversation-memory" / "SKILL.md"
MAP = ROOT / "02_WIKI" / "reference_maps" / "conversation-memory-path.md"
FIRST_SESSION = ROOT / "skills" / "first-session" / "SKILL.md"
AGENTS_MD = ROOT / "AGENTS.md"
SOURCES_PY = SCRIPTS / "sources.py"

# the tools a structure manager is allowed to hold: each one files a proposal a human decides
PROPOSAL_TOOLS = ("candidate_propose", "lesson_propose", "capabilities")

# AC2 wants the absence asserted against an EXPLICIT deny list, so the day somebody adds
# `apply` to this record -- or gives the engine a tool by that name -- a gate goes red instead
# of nodding. These are the names a future write tool would plausibly take.
WRITE_TOOL_NAMES = ("apply", "approve", "set", "link", "new", "promote", "write", "delete",
                    "remove", "grant", "sign", "execute", "publish", "index", "sync",
                    "hades_apply", "registry_apply", "core.registry_apply", "core.registry_write",
                    "core.fs_write", "core.ltm_write", "lesson_approve", "dataset_share",
                    "candidate_approve", "record_apply")
WRITE_TOOL_STEMS = ("apply", "approve", "write", "delete", "remove", "promote", "grant",
                    "publish", "sign")


def is_manager(rec):
    """The machine-readable form of "whose role is structure management".

    The `agent` kind has no `role` field, and `hades.py set` refuses a field no record and no
    schema has ever carried, so inventing one would fork the contract. `tags` and `name` are
    real fields the door validates: a tag of `manager` plus a name carrying `manager` is the
    predicate, and the shipped record satisfies both.
    """
    if rec.get("kind") != "agent":
        return False
    tags = [str(t).strip().lower() for t in (rec.get("tags") or [])]
    return "manager" in tags or "manager" in str(rec.get("name") or "").lower()


def registry_records():
    out = []
    for path in sorted((ROOT / "11_CONTROL").rglob("*.json")):
        try:
            out.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except ValueError:
            out.append((path, {}))
    return out


def manager_records():
    return [(p, r) for p, r in registry_records() if is_manager(r)]


def forbidden_tools(allowlist):
    """Names in `allowlist` that a proposer must never hold: an explicit deny-list name, or a
    name carrying a write stem. Empty means the allowlist is proposal-only."""
    out = []
    for raw in allowlist or ():
        name = str(raw).strip()
        low = name.lower()
        if name in WRITE_TOOL_NAMES or low in WRITE_TOOL_NAMES:
            out.append(name)
        elif any(stem in low for stem in WRITE_TOOL_STEMS):
            out.append(name)
    return out


def door_tool_names():
    return {str(t["name"]) for t in mcp_server.TOOLS}


def run_sources(root, *args):
    proc = run_utf8([sys.executable, str(SOURCES_PY), "--root", str(root)] + [str(a) for a in args])
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


class _RegistryApplyStub(Tool):
    """A registry write tool, which the shipped engine does not have.

    It is registered per-test on a private Registry and writes only into this list, so the real
    repo is never touched -- but `Registry.execute` treats it exactly like a real write tool,
    which is what makes the refusal below a refusal rather than a tautology.
    """
    name = "core.registry_apply"
    description = "stub write tool used to prove the actor's allowlist gates writes"
    writes = True

    def __init__(self):
        self.calls = []

    def run(self, root, ctx, args):
        self.calls.append({"actor": ctx.actor_id, "args": dict(args or {})})
        return {"applied": True}


class TestTheManagerIsARecord(unittest.TestCase):
    """Issue #21 acceptance criteria 1 and 4: the sentence became a record, and there is one."""

    def test_the_shipped_registry_holds_exactly_one_manager_role_agent(self):
        managers = manager_records()
        self.assertEqual(1, len(managers),
                         "charter section 7 asks for one manager; %d records claim the role, so "
                         "the next agent has two definitions to choose between"
                         % len(managers))
        path, rec = managers[0]
        self.assertEqual("agent", rec.get("kind"))
        self.assertEqual(["manager"], [t for t in rec.get("tags") or () if t == "manager"])
        self.assertIn("structure", str(rec.get("name")))
        self.assertTrue((path.parent / "OVERVIEW.md").is_file(),
                        "%s is a record with no body" % rec.get("id"))

    def test_the_manager_body_carries_its_id_and_no_kind(self):
        """A body is a note, not a twin: id yes, kind no (AGENTS.md, 'what apply writes')."""
        _path, rec = manager_records()[0]
        body = (_path.parent / "OVERVIEW.md").read_text(encoding="utf-8")
        head = body.split("---")[1] if body.count("---") >= 2 else body
        self.assertIn("id: %s" % rec.get("id"), head)
        self.assertNotIn("kind:", head)

    def test_the_manager_proposes_structural_changes_it_cannot_sign(self):
        _path, rec = manager_records()[0]
        notes = str(rec.get("notes") or "") + str(( _path.parent / "OVERVIEW.md").read_text(encoding="utf-8"))
        for covers in ("project", "task", "agent", "skill"):
            self.assertIn(covers, notes.lower(),
                          "a structure manager that never names %ss does not manage structure"
                          % covers)
        self.assertIn("section 7", notes)
        self.assertRegex(notes.replace("**", ""), r"(never|cannot) approves? its own|never approves")

    def test_the_manager_has_no_write_scope_and_only_promotes_memory(self):
        _path, rec = manager_records()[0]
        self.assertEqual([], list(rec.get("write_scope") or ()),
                         "a proposer with a write scope is a second door, not an agent")
        self.assertEqual("promote-only", rec.get("memory_policy"))
        self.assertEqual([], list(rec.get("approved_for_harness_ids") or ()))

    def test_its_capabilities_are_registered_skills_it_actually_reads(self):
        _path, rec = manager_records()[0]
        registered = {r.get("name") for _p, r in registry_records() if r.get("kind") == "skill"}
        for capability in rec.get("capabilities") or ():
            self.assertIn(capability, registered,
                          "%s names a capability no skill provides" % capability)
        self.assertTrue(set(("kb-search", "inbox-triage")) <= set(rec.get("capabilities")),
                        "classification without search and triage is guessing")


class TestTheAllowlistIsProposalOnly(unittest.TestCase):
    """Issue #21 acceptance criterion 2: proposal tools only, denied against an explicit list."""

    def test_the_allowlist_names_proposal_tools_the_shipped_doors_declare(self):
        _path, rec = manager_records()[0]
        allowlist = list(rec.get("tool_allowlist") or ())
        self.assertTrue(allowlist, "an empty allowlist would pass any absence test by accident")
        declared = door_tool_names() | set(default_registry().names())
        for name in allowlist:
            self.assertIn(name, declared,
                          "%s is not a tool any shipped door offers -- an allowlist of fictions "
                          "governs nothing" % name)
        self.assertEqual([], [n for n in allowlist if n not in PROPOSAL_TOOLS],
                          "a structure manager may propose; anything else is a write tool")

    def test_the_allowlist_holds_no_write_apply_or_approve_tool(self):
        _path, rec = manager_records()[0]
        self.assertEqual([], forbidden_tools(rec.get("tool_allowlist")),
                         "the manager's allowlist carries a write tool: it can sign its own plan")

    def test_the_deny_list_actually_bites(self):
        """The gate is checked against a tampered actor, so a red light is a real red light."""
        self.assertEqual(["apply"], forbidden_tools(["candidate_propose", "apply"]))
        self.assertEqual(["core.registry_apply"], forbidden_tools(["core.registry_apply"]))
        self.assertEqual(["lesson_approve"], forbidden_tools(["lesson_approve"]))
        self.assertEqual(["promote"], forbidden_tools(["promote"]))
        offenders = forbidden_tools(["candidate_propose", "lesson_propose", "capabilities"])
        self.assertEqual([], offenders, "the checker itself must pass on the shipped list")

    def test_the_record_states_the_engine_limit_it_could_not_enforce(self):
        """Honesty clause: with no write tool in the engine, an allowlist cannot express a
        refusal, so the refusal lives here -- a repo-level check over the shipped record."""
        engine_names = set(default_registry().names())
        self.assertEqual([], sorted(n for n in engine_names
                                    if any(s in n.lower() for s in WRITE_TOOL_STEMS)),
                         "the engine now has a write tool: this record's limit text and the "
                         "allowlist gate must be replaced by an engine-level refusal")
        self.assertEqual([], sorted(n for n in door_tool_names()
                                    if any(s in n.lower() for s in WRITE_TOOL_STEMS)))
        _path, rec = manager_records()[0]
        notes = str(rec.get("notes") or "")
        self.assertIn("no registry write tool", notes.lower().replace("-", " "),
                      "the record must say out loud what the engine cannot enforce")


class TestAPlanCannotBeAppliedByItsAuthor(unittest.TestCase):
    """The door, not the prose: a plan an actor produced is inert until a human flags it."""

    def test_apply_refuses_without_the_human_flag_and_writes_with_it(self):
        vault = Vault()
        self.addCleanup(vault.close)
        code, planned = vault.hades("plan", "--kind", "task", "--name", "proposal-target")
        self.assertEqual(0, code, planned)
        plan_id = re.search(r"(PLAN-[0-9A-F]+)", planned).group(1)
        rel_path = re.search(r"\| path (\S+)", planned).group(1)
        self.assertFalse((vault.root / rel_path).exists(),
                         "a plan must not write; only an approved apply may")

        code, refused = vault.hades("apply", "--plan", plan_id)
        self.assertEqual(2, code, refused)
        self.assertIn("REFUSED: apply needs --approve", refused)
        self.assertFalse((vault.root / rel_path).exists(),
                         "the refusal said nothing was written and something was written")

        code, applied = vault.hades("apply", "--plan", plan_id, "--approve")
        self.assertEqual(0, code, applied)
        self.assertTrue((vault.root / rel_path).is_file())

    def test_the_manager_actor_is_refused_the_write_tool_by_its_own_allowlist(self):
        """Same shape as an approved plan with a human flag: even with --approve, the actor's
        record is the second gate, and it does not name a registry write tool."""
        _path, rec = manager_records()[0]
        ctx = orchestrator._context_for(ROOT, str(rec.get("id")), True)
        self.assertEqual(str(rec.get("id")), ctx.actor_id)
        self.assertTrue(ctx.allow_writes, "the engine path needs an approved context to bite")
        self.assertEqual(set(rec.get("tool_allowlist")), ctx.allowlist)

        registry = Registry()
        stub = _RegistryApplyStub()
        registry.register(stub)
        with self.assertRaises(ToolError) as caught:
            registry.execute(ctx, "core.registry_apply", {"plan_id": "PLAN-SAMPLE"})
        self.assertIn("tool_allowlist", str(caught.exception))
        self.assertEqual([], stub.calls, "the write ran for an actor that never held the tool")

    def test_the_stub_is_a_real_write_tool_so_the_refusal_is_not_a_tautology(self):
        registry = Registry()
        stub = _RegistryApplyStub()
        registry.register(stub)
        holder = Context(ROOT, actor_id="AGT-00000000", actor_kind="agent",
                         allow_writes=True, allowlist=("core.registry_apply",))
        registry.execute(holder, "core.registry_apply", {"plan_id": "PLAN-SAMPLE"})
        self.assertEqual(1, len(stub.calls))
        denied = Context(ROOT, actor_id="AGT-00000000", actor_kind="agent",
                         allow_writes=True, allowlist=())
        with self.assertRaises(ToolError):
            registry.execute(denied, "core.registry_apply", {})


class TestFirstSessionPointsAtTheManager(unittest.TestCase):
    """Issue #21 acceptance criterion 3: the orientation names the manager for classification."""

    def test_the_orientation_sends_classification_questions_to_the_manager(self):
        text = FIRST_SESSION.read_text(encoding="utf-8")
        _path, rec = manager_records()[0]
        self.assertIn(str(rec.get("id")), text,
                      "first-session must point at the record, not at an idea of a manager")
        self.assertIn("structure-manager", text)
        self.assertRegex(text, r"(cannot tell| unsure)".replace(" ", r"\s"),
                         "the pointer has to say which question it answers")
        self.assertIn("classif", text.lower())
        self.assertIn("propose", text.lower())

    def test_the_orientation_never_lets_the_manager_be_read_as_a_door(self):
        text = FIRST_SESSION.read_text(encoding="utf-8")
        _path, rec = manager_records()[0]
        ident = str(rec.get("id"))
        paragraph = [b for b in text.split("\n\n") if ident in b]
        self.assertEqual(1, len(paragraph), "the pointer must be one paragraph, not scattered")
        body = paragraph[0].lower()
        self.assertIn("propose", body, "the manager proposes; the orientation may not say more")
        self.assertIn("plan", body)
        self.assertIn("human", body, "the reader must learn who signs the plan")
        self.assertRegex(body, r"never approves|may not approve|cannot approve")

    def test_the_manager_id_cited_around_the_repo_is_the_registered_one(self):
        _path, rec = manager_records()[0]
        ident = str(rec.get("id"))
        self.assertRegex(ident, r"^AGT-[0-9A-F]{8}$")
        for document in (AGENTS_MD.read_text(encoding="utf-8"),
                         MAP.read_text(encoding="utf-8"),
                         (_path.parent / "OVERVIEW.md").read_text(encoding="utf-8")):
            if ident in document:
                self.assertIn("manager", document.lower(),
                              "%s names the manager id without saying what it is" % ident)


class TestTheConversationMemoryPathExists(unittest.TestCase):
    """Issue #20: the extraction path is a skill plus a map, and both are cited in the canon."""

    def test_the_skill_is_a_registered_record_whose_body_opens(self):
        bodies = {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")}
        self.assertIn("conversation-memory", bodies)
        recs = [r for _p, r in registry_records() if r.get("kind") == "skill"]
        mine = [r for r in recs if r.get("name") == "conversation-memory"]
        self.assertEqual(1, len(mine), "the pack has a skill the registry does not know")
        self.assertTrue((ROOT / mine[0]["entrypoint"]).is_file())

    def test_the_skill_names_the_eligible_exports_and_the_format_contract(self):
        text = SKILL.read_text(encoding="utf-8")
        for fmt in sources.FORMATS:
            self.assertIn(fmt, text, "%s is a supported export the skill never mentions" % fmt)
        self.assertIn("--kind conversation", text)
        self.assertIn("structured harness source requires conversation kind", text)
        self.assertIn("stream contains more than one session", text)

    def test_the_skill_says_a_session_is_imported_explicitly_and_never_scanned(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertRegex(text.replace("*", ""), r"import(?:ed)? (?:one|explicitly)|explicit import")
        self.assertRegex(text.lower(), r"never (auto-)?scan|no scan|nothing globs")
        self.assertIn("sources.py import", text)

    def test_the_skill_requires_a_source_id_and_an_exact_quote(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("--source-id", text)
        self.assertIn("--quote", text)
        self.assertIn("quote is not present in the source text", text)

    def test_the_skill_names_the_approver_and_says_the_door_has_no_approve_tool(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("explicit human approval is required", text)
        self.assertIn("approve PROPOSAL_ID --approve", text)
        self.assertRegex(text.lower(), r"no approve tool")

    def test_the_skill_says_what_no_entry_means_in_this_plane(self):
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("NO_ENTRY", text)
        self.assertIn("index missing; run rebuild first", text)
        self.assertRegex(text, r"\[\]")
        self.assertIn("gitignored", text)

    def test_the_agents_md_clause_states_the_path_and_cites_both_documents(self):
        text = AGENTS_MD.read_text(encoding="utf-8")
        self.assertIn("skills/conversation-memory/SKILL.md", text)
        self.assertIn("02_WIKI/reference_maps/conversation-memory-path.md", text)
        clause = [p for p in text.split("\n\n") if "Conversation memory" in p]
        self.assertEqual(1, len(clause), "AGENTS.md must state this path exactly once")
        body = clause[0]
        self.assertIn("sources.py import", body)
        self.assertIn("--approve", body)
        self.assertRegex(body.lower(), r"nothing scans|never scans|no scan")

    def test_the_map_has_one_row_per_step_and_names_a_refusal_or_a_no_row(self):
        rows = [line for line in MAP.read_text(encoding="utf-8").splitlines()
                if line.startswith("|") and line.count("|") >= 5
                and "---" not in line and "what it refuses" not in line
                and "what it produces" not in line]
        self.assertGreaterEqual(len(rows), 14,
                                "a path map with fewer rows than steps is a summary")
        self.assertGreaterEqual(sum(1 for r in rows if "NO_ROW" in r), 4,
                                "an honest NO_ROW beats a claim; none present here")
        for verb in ("import", "rebuild", "search", "propose", "evaluate", "approve", "recall",
                     "transfer"):
            self.assertIn(verb, MAP.read_text(encoding="utf-8"),
                          "the map skips the step that runs %s" % verb)

    def test_every_command_and_refusal_the_map_quotes_is_a_real_one(self):
        text = MAP.read_text(encoding="utf-8")
        help_text = run_utf8([sys.executable, str(SOURCES_PY), "--help"]).stdout
        for verb in re.findall(r"sources\.py (\w[\w-]*)", text):
            if verb in ("import", "rebuild", "search", "propose", "evaluate", "approve",
                        "recall", "transfer", "verify-copy", "batch", "benchmark"):
                self.assertIn(verb, help_text, "%s is not a subcommand of the door" % verb)
        code_corpus = "".join((SCRIPTS / rel).read_text(encoding="utf-8") for rel in (
            "sources.py", "mcp_server.py", "backend/sources.py", "backend/learning.py",
            "backend/source_sync.py"))
        quoted = re.findall(r"`ERROR: ([^`]{6,120}?)`", text)
        self.assertGreaterEqual(len(quoted), 12, quoted)
        for message in quoted:
            for part in re.split(r"\.\.\.|%[rs]|\bN\b", message):
                part = part.strip(" ;,")
                if len(part) >= 12:
                    self.assertIn(part, code_corpus,
                                  "the map quotes a refusal nobody can raise: %r" % message)
        memory_corpus = (ROOT / "scripts" / "memory.py").read_text(encoding="utf-8")
        refused = re.findall(r"`REFUSED([^`]{6,120}?)`", text)
        self.assertGreaterEqual(len(refused), 1, refused)
        for message in refused:
            for part in re.split(r"\.\.\.|%r|%s", message):
                part = part.strip(" ;,.")
                if len(part) >= 12:
                    self.assertIn(part, memory_corpus,
                                  "the map quotes a refusal memory.py does not print: %r" % message)

    def test_every_path_the_path_cites_opens(self):
        corpus = SKILL.read_text(encoding="utf-8") + MAP.read_text(encoding="utf-8")
        cited = ["skills/conversation-memory/SKILL.md",
                 "02_WIKI/reference_maps/conversation-memory-path.md",
                 "02_WIKI/reference_maps/eight-memory-planes.md",
                 "15_SYSTEM/scripts/sources.py",
                 "15_SYSTEM/scripts/backend/sources.py",
                 "15_SYSTEM/scripts/backend/learning.py",
                 "15_SYSTEM/scripts/mcp_server.py",
                 "15_SYSTEM/integrations/local-sources.md",
                 "scripts/memory.py", "scripts/plane_check.py", "scripts/health.py",
                 "tests/test_sources.py", "tests/test_learning.py", "tests/test_source_sync.py",
                 "tests/test_phase22_harness_bridge.py", "tests/test_phase15_repo_memory.py",
                 "tests/test_phase26_memory_planes.py",
                 "tests/test_phase41_manager_agent_and_conversation_memory.py",
                 "AGENTS.md"]
        for rel in cited:
            self.assertIn(rel.split("::")[0], corpus, "%s is not cited by the new documents" % rel)
            self.assertTrue((ROOT / rel.split("::")[0]).exists(), "broken citation: %s" % rel)


class TestThePathRuns(unittest.TestCase):
    """One real execution of the documented chain -- a checkbox is not a behaviour proof."""

    def test_the_documented_commands_take_one_named_export_to_one_approved_lesson(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            export = root / "claude-session.txt"
            export.write_text("The deploy failed because the migration ran twice. "
                              "Rerun nothing by hand next time.", encoding="utf-8")
            code, out = run_sources(root, "import", export, "--kind", "conversation",
                                     "--origin", "claude:test-session", "--format", "text")
            self.assertEqual(0, code, out)
            source_id = json.loads(out)["id"]

            self.assertEqual(0, run_sources(root, "rebuild")[0])
            code, out = run_sources(root, "search", "migration")
            self.assertEqual(0, code, out)
            self.assertEqual(source_id, json.loads(out)[0]["id"])

            args = ("propose", "--source-id", source_id, "--quote", "an invented run of words",
                    "--lesson", "Gate the migration behind a dry run", "--query", "migration")
            code, out = run_sources(root, *args)
            self.assertEqual(2, code, out)
            self.assertIn("quote is not present in the source text", out)

            args = ("propose", "--source-id", source_id, "--quote", "migration ran twice",
                    "--lesson", "Gate the migration behind a dry run", "--query", "migration")
            code, out = run_sources(root, *args)
            self.assertEqual(0, code, out)
            proposal_id = json.loads(out)["id"]

            code, out = run_sources(root, "evaluate", proposal_id)
            self.assertEqual(0, code, out)
            report = json.loads(out)
            self.assertTrue(report["passed"], report)
            self.assertIn("limitation", report)

            code, out = run_sources(root, "approve", proposal_id)
            self.assertEqual(2, code, out)
            self.assertIn("explicit human approval is required", out)
            self.assertEqual([], json.loads(run_sources(root, "recall", "migration")[1]))

            code, out = run_sources(root, "approve", proposal_id, "--approve")
            self.assertEqual(0, code, out)
            lessons = json.loads(run_sources(root, "recall", "migration")[1])
            self.assertEqual([proposal_id], [row["id"] for row in lessons])
            self.assertEqual("claude:test-session", lessons[0]["origin"])
            self.assertEqual("migration ran twice", lessons[0]["quote"])

    def test_a_fresh_clone_answers_honestly_instead_of_inventing_a_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            code, out = run_sources(root, "search", "anything")
            self.assertEqual(2, code, out)
            self.assertIn("index missing; run rebuild first", out)
            code, out = run_sources(root, "recall", "anything")
            self.assertEqual(0, code, out)
            self.assertEqual("[]", out.strip())

    def test_the_door_offers_no_way_to_scan_a_harness_history(self):
        """The row the map writes as NO_ROW: nothing here globs a session folder."""
        choices = run_utf8([sys.executable, str(SOURCES_PY), "--help"]).stdout
        for absent in ("scan", "watch", "glob", "autolog", "sync-history", "auto-import"):
            self.assertNotIn(absent, choices)
        help_text = run_utf8([sys.executable, str(SOURCES_PY), "import", "--help"]).stdout
        self.assertIn("--origin", help_text)
        self.assertIn("conversation", help_text)
        self.assertRegex(help_text, r"positional arguments:\s*\n\s+file\s*\n",
                         "the import door takes one named file; anything looser is a scan")

    def test_the_harness_door_exposes_proposals_and_never_an_approval(self):
        names = door_tool_names()
        self.assertIn("source_import", names)
        self.assertIn("lesson_propose", names)
        self.assertEqual([], sorted(n for n in names
                                    if any(s in n.lower() for s in WRITE_TOOL_STEMS)),
                         "the harness door can now approve its own proposal -- close that")


if __name__ == "__main__":
    unittest.main()
