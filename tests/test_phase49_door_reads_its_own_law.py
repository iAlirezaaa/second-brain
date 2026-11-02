"""Phase 49 — the harness door asks the access law, instead of restating a claim about it.

Constitution §8 sets two of its own requirements in words this repo had already written down and
then ignored: "policy must not rely on ... a check of folder names", and least privilege /
default deny "at the service, file, process and tool level". `15_SYSTEM/scripts/backend/access.py`
is this repo's answer -- one file that names the planes an agent may not read. The door
(`15_SYSTEM/scripts/mcp_server.py`) is the service that actually serves reads. Until now the two
had never been compared.

Measured on commit 4a71da4, on this repo's own tree, with the law imported and called directly:

    denial(root, "12_RUNTIME/agent_runs")   -> "12_RUNTIME"      (denied)
    readable(root, "12_RUNTIME/agent_runs") -> False             (denied)

and with the door's own tools called over its stdio wire:

    runs_list  -> not an error; printed the run ids and statuses of every actor
    runs_show  -> not an error; printed every step line of one actor's trail
    doctor_status -> printed the run directory's contents as a count of runs

`tests/test_phase22_harness_bridge.py` pinned exactly that behaviour, and its assertions all
passed -- which is the honest way to say the leak had a contract. The door's module docstring
went further and promised it: "Read tools are open." Three other read tools reach the private
source plane (`.brain-data`, also denied by the same table) and `tool_source_search` returned the
whole stored body of every match -- one query, one copy of the owner's private notes, in the
context of whichever harness asked (§7: retrieval is not "send everything").

The fix is one law with two answers. `access.denial()` returns the *name of the rule* that stopped
a path, `access.readable()` is that answer compared to None, and the door calls the law rather
than carrying its own copy of the boundary: a refusal quotes the rule in force, so the sentence
cannot drift from the file. Where a plane is denied and the tool has no other purpose -- the run
plane is another actor's trail, not the brain's knowledge -- the door refuses and points the human
at the human view (`15_SYSTEM/scripts/runs.py`). Where the read is legitimate but the *body* is not
-- a query over private sources -- the door answers with the citation, the body's length and a
bounded excerpt.

Two directions of failure are tested. The refusals must be real: the rule they name must be one
`access.DENIED` actually declares (a door that invents its own reason can invent its own
permission), and no content from a denied plane may reach the wire. And the refusals must not
overreach: a permitted path still reads, `lesson_recall` still answers, and `source_search` still
returns a hit the asking harness can cite -- silence is not security.
"""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "15_SYSTEM" / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(ROOT / "tests"))

from backend import access  # noqa: E402
from test_phase22_harness_bridge import (McpClient, RUNS, TempVault,  # noqa: E402
                                        initialize, load_by_path)

DENIED_NAMES = set("/".join(parts) for parts in access.DENIED)
# The rules the law states without naming a plane: they are refusals too, and a test that only
# knew the plane names would fail on a correct answer.
OTHER_RULES = {"an empty path", ".git/.secrets", "a secret-bearing filename",
               "outside the brain this door serves"}
EXCERPT_CHARS = 400


class TestOneLawTwoAnswers(unittest.TestCase):
    """`readable()` is `denial() is None`, and the name it returns is the rule in force."""

    PLANES = [("12_RUNTIME", "agent_runs"), ("13_LAB",), ("14_CANDIDATES", "loop"), (".kb",),
              (".brain-data", "sources"), ("15_SYSTEM", "generated", "plans"),
              ("15_SYSTEM", "backups", "known-good"),
              ("09_OPERATIONS", "clients_metadata_only")]
    # The planes a read is legitimately served from; the fixture makes three of them.
    OPEN = [("01_INBOX",), ("02_WIKI", "concepts"), ("03_PROJECTS",)]

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        for parts in self.PLANES + self.OPEN:
            self.root.joinpath(*parts).mkdir(parents=True, exist_ok=True)

    def paths(self):
        for parts in self.PLANES + self.OPEN:
            yield parts, self.root.joinpath(*parts).joinpath("item.md")

    def test_readable_is_exactly_denial_compared_to_none(self):
        for parts, path in list(self.paths()) + [((".git",), self.root / ".git" / "config"),
                                                 (("",), self.root / ".env"),
                                                 (("",), self.root / "server.key")]:
            blocked = access.denial(self.root, path)
            self.assertEqual(access.readable(self.root, path), blocked is None, str(path))

    def test_every_denied_plane_names_itself(self):
        for parts, path in self.paths():
            if parts in self.OPEN:
                continue
            blocked = access.denial(self.root, path)
            self.assertIn(blocked, DENIED_NAMES, str(path))
            self.assertTrue(str(path).startswith(str(self.root / parts[0])), str(path))

    def test_the_rules_that_are_not_planes_are_named_as_rules(self):
        self.assertEqual(access.denial(self.root, self.root / ".git" / "config"), ".git/.secrets")
        self.assertEqual(access.denial(self.root, self.root / ".env"),
                         "a secret-bearing filename")
        self.assertEqual(access.denial(self.root, self.root.parent / "elsewhere.md"),
                         "outside the brain this door serves")

    def test_a_path_the_law_allows_still_reads(self):
        note = self.root / "02_WIKI" / "concepts" / "item.md"
        note.write_text("# a live note\n", encoding="utf-8")
        self.assertIsNone(access.denial(self.root, note))
        self.assertTrue(access.readable(self.root, note))


class TestDoorAsksTheLaw(TempVault, unittest.TestCase):
    """The wire: what a harness gets when it asks the door for a denied plane."""

    def setUp(self):
        TempVault.setUp(self)

    def tearDown(self):
        TempVault.tearDown(self)

    def client(self):
        client = McpClient(self.root)
        self.addCleanup(client.close)
        initialize(client)
        return client

    def one_run_with_a_trail(self):
        """A real run in the real plane, so a refusal cannot be blamed on an empty directory."""
        runs = load_by_path("runs_phase49", RUNS)
        agent = self.new_record("agent", "Feed Runner")

        def runs_cli(*argv):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                runs.main(["--root", str(self.root)] + list(argv))
            return buf.getvalue()

        out = runs_cli("start", "--agent", agent, "--goal", "feed the door")
        run_id = [ln.split()[1] for ln in out.splitlines() if ln.startswith("RUN ")][0]
        runs_cli("step", "--run", run_id, "--text", "knock knock")
        runs_cli("finish", "--run", run_id, "--status", "completed")
        self.assertTrue((self.root / "12_RUNTIME" / "agent_runs").exists())
        return run_id

    def test_run_tools_refuse_and_the_refusal_names_a_real_rule(self):
        run_id = self.one_run_with_a_trail()
        client = self.client()
        for name, args in (("runs_list", {}), ("runs_show", {"run": run_id})):
            text, is_error = client.result_text("tools/call", {"name": name, "arguments": args})
            self.assertTrue(is_error, "%s answered: %s" % (name, text))
            self.assertNotIn(run_id, text, "%s disclosed an id from inside the plane" % name)
            self.assertNotIn("knock knock", text, "%s leaked a step line" % name)
            self.assertNotIn("completed", text, "%s leaked run state" % name)
            named = [rule for rule in DENIED_NAMES | OTHER_RULES if rule in text]
            self.assertTrue(named, "the refusal named no rule the law declares: %s" % text)

    def test_refusal_is_asked_not_restarted(self):
        """The door quotes the law's answer for the plane it guards, word for word."""
        run_id = self.one_run_with_a_trail()
        blocked = access.denial(self.root, self.root / "12_RUNTIME" / "agent_runs")
        self.assertEqual(blocked, "12_RUNTIME")
        text, is_error = self.client().result_text(
            "tools/call", {"name": "runs_list", "arguments": {}})
        self.assertTrue(is_error, text)
        self.assertIn(blocked, text)

    def test_doctor_status_reports_the_law_without_opening_the_plane(self):
        run_id = self.one_run_with_a_trail()
        text, is_error = self.client().result_text(
            "tools/call", {"name": "doctor_status", "arguments": {}})
        self.assertFalse(is_error, text)
        facts = json.loads(text)
        self.assertFalse(facts["runs"]["read"])
        self.assertEqual("12_RUNTIME", facts["runs"]["denied_by"])
        self.assertIn("runs.py", facts["runs"]["human_view"])
        self.assertNotIn(run_id, text, "the doctor opened the plane it reports on")

    def test_a_private_source_query_returns_a_citation_not_the_body(self):
        body = ("zetaloom retrieval notes. " + "filler that the owner stored privately " * 40
                + " TAIL-PRIVATE-MARKER")
        note = self.root / "02_WIKI" / "concepts" / "private.md"
        note.parent.mkdir(parents=True, exist_ok=True)
        note.write_text(body, encoding="utf-8")
        client = self.client()
        text, is_error = client.result_text("tools/call", {"name": "source_import", "arguments": {
            "path": "02_WIKI/concepts/private.md", "kind": "research",
            "origin": "harness:phase49"}})
        self.assertFalse(is_error, text)
        text, is_error = client.result_text("tools/call", {"name": "source_search",
                                                           "arguments": {"query": "zetaloom"}})
        self.assertFalse(is_error, text)
        rows = json.loads(text)
        self.assertTrue(rows, "the read was refused outright -- over-blocking is not the fix")
        row = rows[0]
        self.assertEqual("harness:phase49", row["origin"])
        self.assertEqual(len(body), row["chars"])
        self.assertTrue(row["excerpt_truncated"])
        self.assertLessEqual(len(row["excerpt"]), EXCERPT_CHARS)
        self.assertNotIn("TAIL-PRIVATE-MARKER", text, "the whole body crossed the wire")
        self.assertNotIn("text", row, "the door must answer with an excerpt, not the stored body")

    def test_reads_the_door_is_allowed_to_serve_still_serve(self):
        """Guards against a boundary drawn so wide the brain stops answering."""
        client = self.client()
        for name, args in (("registry_list", {}), ("capabilities", {}), ("doctor_status", {})):
            text, is_error = client.result_text("tools/call", {"name": name, "arguments": args})
            self.assertFalse(is_error, "%s refused a permitted read: %s" % (name, text))
        text, is_error = client.result_text("tools/call", {"name": "lesson_recall",
                                                           "arguments": {"query": "anything"}})
        self.assertFalse(is_error, "lesson_recall was blocked by this change: %s" % text)


if __name__ == "__main__":
    unittest.main()
