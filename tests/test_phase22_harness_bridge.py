"""Phase 22 tests — the harness door (MCP over stdio) and the agent-run ledger.

The config described an `mcp` kind and a `harness` kind for a long time while nothing
let a harness actually call the brain, and nothing recorded what an agent run did. Phase
22 closes both gaps the SuperAGI research pointed at: the backend is the protocol the
harnesses already speak (MCP over stdio, stdlib-only — no server farm), and runs live in
the disposable plane (12_RUNTIME/agent_runs) behind a refusal for unaccounted actors.

Also exercised: the doctor law an MCP record teaches — an `endpoint_or_command` ending in
`.py` is a file pointer, and a pointer to nothing is a rumour, not a capability.
"""
import contextlib
import importlib.util
import io
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import common  # noqa: E402

HADES = ROOT / "15_SYSTEM" / "scripts" / "hades.py"
RUNS = ROOT / "15_SYSTEM" / "scripts" / "runs.py"
SERVER = ROOT / "15_SYSTEM" / "scripts" / "mcp_server.py"


def load_by_path(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TempVault:
    """A throwaway registry: real config, schema and scripts, zero real records."""

    def setUp(self):
        self.hades = load_by_path("hades_phase22", HADES)
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(ROOT / "15_SYSTEM" / "config", self.root / "15_SYSTEM" / "config")
        shutil.copytree(ROOT / "15_SYSTEM" / "schemas", self.root / "15_SYSTEM" / "schemas")
        shutil.copytree(ROOT / "15_SYSTEM" / "scripts", self.root / "15_SYSTEM" / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        (self.root / "02_WIKI" / "concepts").mkdir(parents=True)
        (self.root / "14_CANDIDATES" / "loop").mkdir(parents=True)
        cfg = json.loads((ROOT / "15_SYSTEM/config/system.json").read_text(encoding="utf-8"))
        (self.root / ".gitignore").write_text("\n".join(cfg["gitignore_required_paths"]) + "\n",
                                              encoding="utf-8")
        for z in cfg["zones"]:
            if z["dir"] in ("12_RUNTIME", "13_LAB"):
                continue  # absent at the documented git boundary by design
            d = self.root / z["dir"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "README.md").write_text("# zone %s\n" % z["dir"], encoding="utf-8")
        h = self.hades
        self._saved = (h.ROOT, h.CONFIG_PATH, h.SCHEMA_PATH, h.GEN, h.PLANS,
                       h.REGISTRY_KINDS, h.MANIFEST_NAMES)
        h.ROOT = self.root
        h.CONFIG_PATH = self.root / "15_SYSTEM/config/system.json"
        h.SCHEMA_PATH = self.root / "15_SYSTEM/schemas/manifest.schema.json"
        h.GEN = self.root / "15_SYSTEM/generated"
        h.PLANS = h.GEN / "plans"
        h.REGISTRY_KINDS = None
        h.MANIFEST_NAMES = None

    def tearDown(self):
        h = self.hades
        (h.ROOT, h.CONFIG_PATH, h.SCHEMA_PATH, h.GEN, h.PLANS,
         h.REGISTRY_KINDS, h.MANIFEST_NAMES) = self._saved
        self._tmp.cleanup()

    def cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = self.hades.main(list(argv))
        return code, buf.getvalue()

    def new_record(self, kind, name, extra=()):
        code, out = self.cli("new", "--kind", kind, "--name", name,
                             "--description", "body", "--approve", *extra)
        self.assertEqual(0, code, out)
        row = [ln for ln in out.splitlines() if ln.startswith("APPLIED ")][0]
        return row.split()[1]


class McpClient:
    """A tiny MCP wire client: newline-delimited JSON-RPC over the child's stdio.

    Output is decoded with an explicit encoding (the house lesson about subprocesses on
    Windows), replies arrive on a reader thread so a chatty child can never wedge a test.
    """

    def __init__(self, root):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER), "--root", str(root)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.replies = queue.Queue()
        self.reader = threading.Thread(target=self._pump, daemon=True)
        self.reader.start()

    def _pump(self):
        for raw in self.proc.stdout:
            line = raw.decode("utf-8", errors="replace").strip()
            if line:
                self.replies.put(json.loads(line))
        self.replies.put(None)

    def send(self, obj):
        self.proc.stdin.write((json.dumps(obj) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def send_raw(self, text):
        self.proc.stdin.write(text.encode("utf-8"))
        self.proc.stdin.flush()

    def reply(self, timeout=30):
        got = self.replies.get(timeout=timeout)
        if got is None:
            stderr = self.proc.stderr.read().decode("utf-8", errors="replace")
            raise AssertionError("server closed stdout; stderr:\n%s" % stderr[-2000:])
        return got

    def call(self, method, params=None, mid=None):
        self.send({"jsonrpc": "2.0", "id": mid if mid is not None else 99,
                   "method": method, "params": params or {}})
        return self.reply()

    def result_text(self, method, params=None):
        r = self.call(method, params)
        return r["result"]["content"][0]["text"], r["result"].get("isError", False)

    def close(self, timeout=30):
        try:
            self.proc.stdin.close()
        except OSError:
            pass
        rc = self.proc.wait(timeout=timeout)
        for stream in (self.proc.stdout, self.proc.stderr):
            try:
                stream.close()
            except OSError:
                pass
        return rc


def initialize(client):
    r = client.call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                   "clientInfo": {"name": "phase22-test", "version": "0"}}, mid=1)
    client.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
    return r["result"]


class TestHarnessDoor(TempVault, unittest.TestCase):
    """The MCP server: what a harness sees when it opens the brain."""

    def setUp(self):
        TempVault.setUp(self)

    def tearDown(self):
        TempVault.tearDown(self)

    def client(self):
        c = McpClient(self.root)
        self.addCleanup(c.close)
        return c

    def test_initialize_echoes_protocol_and_lists_the_eight_tools(self):
        c = self.client()
        result = initialize(c)
        self.assertEqual("hades-second-brain", result["serverInfo"]["name"])
        self.assertEqual("2025-06-18", result["protocolVersion"])
        r = c.call("tools/list", mid=2)
        names = [t["name"] for t in r["result"]["tools"]]
        self.assertEqual(["vault_search", "memory_recall", "registry_list", "registry_show",
                          "doctor_status", "runs_list", "runs_show", "candidate_propose"],
                         names)

    def test_registry_is_visible_through_the_door(self):
        wid = self.new_record("wiki_note", "Door Law")
        c = self.client()
        initialize(c)
        text, is_err = c.result_text("tools/call", {"name": "registry_list", "arguments": {}})
        self.assertFalse(is_err, text)
        self.assertIn(wid, text)
        text, is_err = c.result_text("tools/call", {"name": "registry_show",
                                                    "arguments": {"id": wid}})
        self.assertFalse(is_err, text)
        self.assertIn("Door Law", text)
        text, is_err = c.result_text("tools/call", {"name": "registry_show",
                                                    "arguments": {"id": "WIK-nope"}})
        self.assertTrue(is_err, text)
        self.assertIn("no record WIK-nope", text)

    def test_vault_search_finds_seeded_prose_and_refuses_an_empty_query(self):
        token = "quixoticlatchneedle"
        (self.root / "02_WIKI" / "concepts" / "needle.md").write_text(
            "---\nid: map-needle\ntype: resource\ntitle: needle\nstatus: evergreen\n"
            "owner: agent\ntopics: []\ncreated: 2026-10-28\nupdated: 2026-10-28\n---\n\n"
            "The %s hides here.\n" % token, encoding="utf-8")
        c = self.client()
        initialize(c)
        text, is_err = c.result_text("tools/call", {"name": "vault_search",
                                                    "arguments": {"query": token}})
        self.assertFalse(is_err, text)
        self.assertIn("02_WIKI/concepts/needle.md", text)
        text, is_err = c.result_text("tools/call", {"name": "vault_search",
                                                    "arguments": {"query": ""}})
        self.assertTrue(is_err, text)

    def test_memory_recall_reads_the_lessons_ledger(self):
        (self.root / "15_SYSTEM" / "memory").mkdir(parents=True, exist_ok=True)
        (self.root / "15_SYSTEM" / "memory" / "lessons.jsonl").write_text(json.dumps({
            "id": "mem-latch-test", "confidence": 0.8,
            "cue": "the horse is gone in the morning", "date": "2026-10-28T00:00:00Z",
            "evidence": ["02_WIKI/concepts/needle.md"],
            "lesson": "check the latch before blaming the horse",
            "source": "phase22 test", "topics": ["test"], "verdict": "helped"}) + "\n",
            encoding="utf-8")
        c = self.client()
        initialize(c)
        text, is_err = c.result_text("tools/call", {"name": "memory_recall",
                                                    "arguments": {"query": "latch horse"}})
        self.assertFalse(is_err, text)
        self.assertIn("mem-latch-test", text)
        self.assertIn("check the latch", text)

    def test_candidate_propose_files_a_registered_row(self):
        c = self.client()
        initialize(c)
        text, is_err = c.result_text("tools/call", {"name": "candidate_propose", "arguments": {
            "dimension": "invariant", "cue": "the door is open",
            "lesson": "a read door still needs a write shelf", "confidence": 0.75}})
        self.assertFalse(is_err, text)
        cid = text.split()[1]
        self.assertTrue(cid.startswith("cand-"))
        row = self.root / "14_CANDIDATES" / "loop" / (cid + ".md")
        self.assertTrue(row.is_file(), text)
        ledger = (self.root / "14_CANDIDATES" / "loop" / "ledger.jsonl").read_text(encoding="utf-8")
        self.assertIn(cid, ledger)
        self.assertIn('"proposed"', ledger)
        # and the door refuses to propose nonsense
        text, is_err = c.result_text("tools/call", {"name": "candidate_propose", "arguments": {
            "cue": "only a cue"}})
        self.assertTrue(is_err, text)
        text, is_err = c.result_text("tools/call", {"name": "candidate_propose", "arguments": {
            "cue": "c", "lesson": "l", "confidence": 1.5}})
        self.assertTrue(is_err, text)
        self.assertIn("0..1", text)

    def test_resources_list_read_and_traversal_guard(self):
        (self.root / "AGENTS.md").write_text("# canon\n\nStay on the shelf.\n", encoding="utf-8")
        c = self.client()
        initialize(c)
        r = c.call("resources/list", mid=3)
        uris = [x["uri"] for x in r["result"]["resources"]]
        self.assertIn("file://AGENTS.md", uris)
        r = c.call("resources/read", {"uri": "file://AGENTS.md"}, mid=4)
        self.assertIn("Stay on the shelf.", r["result"]["contents"][0]["text"])
        r = c.call("resources/read", {"uri": "file://../../outside/secret.md"}, mid=5)
        self.assertEqual(-32602, r["error"]["code"])
        r = c.call("resources/read", {"uri": "file://GHOST.md"}, mid=6)
        self.assertEqual(-32602, r["error"]["code"])

    def test_ping_unknown_method_parse_error_and_clean_eof(self):
        c = self.client()
        initialize(c)
        self.assertEqual({}, c.call("ping", mid=7)["result"])
        r = c.call("no/such/method", mid=8)
        self.assertEqual(-32601, r["error"]["code"])
        c.send_raw("this is not json\n")
        r = c.reply()
        self.assertEqual(-32700, r["error"]["code"])
        self.assertIsNone(r["id"])
        self.assertEqual(0, c.close())

    def test_runs_tools_expose_the_disposable_plane_readonly(self):
        self.runs = load_by_path("runs_phase22b", RUNS)

        def runs_cli(*argv):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = self.runs.main(["--root", str(self.root)] + list(argv))
            return code, buf.getvalue()

        agt = self.new_record("agent", "Feed Runner")
        code, out = runs_cli("start", "--agent", agt, "--goal", "feed the door")
        run_id = [ln.split()[1] for ln in out.splitlines() if ln.startswith("RUN ")][0]
        runs_cli("step", "--run", run_id, "--text", "knock knock")
        runs_cli("finish", "--run", run_id, "--status", "completed")
        c = self.client()
        initialize(c)
        text, is_err = c.result_text("tools/call", {"name": "runs_list", "arguments": {}})
        self.assertFalse(is_err, text)
        self.assertIn(run_id, text)
        self.assertIn("completed", text)
        text, is_err = c.result_text("tools/call", {"name": "runs_show",
                                                    "arguments": {"run": run_id}})
        self.assertFalse(is_err, text)
        self.assertIn("knock knock", text)
        text, is_err = c.result_text("tools/call", {"name": "runs_show",
                                                    "arguments": {"run": "RUN-00000000"}})
        self.assertTrue(is_err, text)
        self.assertIn("no such run", text)

    def test_doctor_status_is_facts_not_a_gate(self):
        c = self.client()
        initialize(c)
        text, is_err = c.result_text("tools/call", {"name": "doctor_status", "arguments": {}})
        self.assertFalse(is_err, text)
        facts = json.loads(text)
        self.assertEqual(0, facts["records"])
        self.assertIn("note", facts)


class TestDoctorMcpEndpointLaw(TempVault, unittest.TestCase):
    """An mcp record's `.py` endpoint is a file pointer; pointing at nothing is an error."""

    def setUp(self):
        TempVault.setUp(self)

    def tearDown(self):
        TempVault.tearDown(self)

    def doctor_report(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.hades.cmd_doctor(self.hades.config(), self.hades.schema(), as_json=True)
        return json.loads(buf.getvalue())

    def test_missing_endpoint_is_an_error_and_a_real_one_passes(self):
        self.new_record("mcp", "ghost door",
                        extra=("--transport", "stdio", "--endpoint", "15_SYSTEM/scripts/ghost.py"))
        report = self.doctor_report()
        self.assertEqual(1, len(report["errors"]), report["errors"])
        self.assertIn("mcp endpoint", report["errors"][0])
        real_id = self.new_record("mcp", "real door",
                                  extra=("--transport", "stdio",
                                         "--endpoint", "15_SYSTEM/scripts/mcp_server.py"))
        report = self.doctor_report()
        self.assertEqual(1, len(report["errors"]), report["errors"])
        self.assertNotIn(real_id, report["errors"][0])


class TestAgentRuns(TempVault, unittest.TestCase):
    """The run ledger: SuperAGI's execution model, disposable, refusing ghosts."""

    def setUp(self):
        TempVault.setUp(self)
        self.runs = load_by_path("runs_phase22", RUNS)
        self.agent_id = self.new_record("agent", "Bridge Runner")

    def tearDown(self):
        TempVault.tearDown(self)

    def runs_cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = self.runs.main(["--root", str(self.root)] + list(argv))
        return code, buf.getvalue()

    def start_run(self, goal="prove the bridge"):
        code, out = self.runs_cli("start", "--agent", self.agent_id, "--goal", goal)
        self.assertEqual(0, code, out)
        return [ln for ln in out.splitlines() if ln.startswith("RUN ")][0].split()[1]

    def test_full_lifecycle_start_step_finish_list_show(self):
        run_id = self.start_run()
        d = self.root / "12_RUNTIME" / "agent_runs" / run_id
        self.assertTrue((d / "run.json").is_file())
        code, out = self.runs_cli("step", "--run", run_id, "--text", "opened the door")
        self.assertEqual(0, code, out)
        code, out = self.runs_cli("step", "--run", run_id, "--status", "fail",
                                  "--text", "stumbled, wrote it down anyway")
        self.assertEqual(0, code, out)
        steps = [json.loads(ln) for ln in
                 (d / "steps.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(["opened the door", "stumbled, wrote it down anyway"],
                         [s["text"] for s in steps])
        code, out = self.runs_cli("finish", "--run", run_id, "--status", "completed",
                                  "--summary", "door proven")
        self.assertEqual(0, code, out)
        run = json.loads((d / "run.json").read_text(encoding="utf-8"))
        self.assertEqual("completed", run["status"])
        self.assertEqual(2, run["steps"])
        code, out = self.runs_cli("list")
        self.assertEqual(0, code)
        self.assertIn(run_id, out)
        code, out = self.runs_cli("show", "--run", run_id)
        self.assertEqual(0, code)
        self.assertIn("opened the door", out)

    def test_refusals(self):
        code, out = self.runs_cli("start", "--agent", "AGT-ghost", "--goal", "?")
        self.assertEqual(2, code)
        self.assertIn("no registry record AGT-ghost", out)
        wid = self.new_record("wiki_note", "Not An Actor")
        code, out = self.runs_cli("start", "--agent", wid, "--goal", "?")
        self.assertEqual(2, code)
        self.assertIn("runs are started for actors", out)
        run_id = self.start_run()
        code, out = self.runs_cli("step", "--run", "RUN-00000000", "--text", "x")
        self.assertEqual(2, code)
        code, out = self.runs_cli("step", "--run", run_id, "--text", "")
        self.assertEqual(2, code)
        self.assertIn("step needs text", out)
        code, out = self.runs_cli("finish", "--run", run_id, "--status", "completed")
        self.assertEqual(0, code, out)
        code, out = self.runs_cli("step", "--run", run_id, "--text", "too late")
        self.assertEqual(2, code)
        self.assertIn("finished run's feed is history", out)
        code, out = self.runs_cli("finish", "--run", run_id, "--status", "failed")
        self.assertEqual(2, code)
        self.assertIn("finishing twice", out)
        code, out = self.runs_cli("finish", "--run", run_id, "--status", "paused")
        self.assertEqual(2, code)

    def test_promote_exports_the_feed_into_a_registered_row(self):
        run_id = self.start_run(goal="learn the latch")
        self.runs_cli("step", "--run", run_id, "--text", "the latch was open")
        self.runs_cli("step", "--run", run_id, "--status", "note",
                      "--text", "wrote the check down")
        self.runs_cli("finish", "--run", run_id, "--status", "completed")
        # a running run cannot promote, and an empty feed has nothing to say
        other = self.start_run(goal="still running")
        code, out = self.runs_cli("promote", "--run", other)
        self.assertEqual(2, code)
        self.assertIn("still running", out)
        empty = self.start_run(goal="never stepped")
        self.runs_cli("finish", "--run", empty, "--status", "failed")
        code, out = self.runs_cli("promote", "--run", empty)
        self.assertEqual(2, code)
        self.assertIn("empty feed", out)
        # the real promotion
        code, out = self.runs_cli("promote", "--run", run_id)
        self.assertEqual(0, code, out)
        cid = out.split()[1]
        self.assertTrue(cid.startswith("cand-"), out)
        row = self.root / "14_CANDIDATES" / "loop" / (cid + ".md")
        self.assertTrue(row.is_file(), out)
        text = row.read_text(encoding="utf-8")
        self.assertIn("the latch was open", text)          # the feed is embedded
        self.assertIn("11_CONTROL/agents/", text)          # evidence cites the actor record
        self.assertNotIn("12_RUNTIME/", text.split("evidence:")[1].split("---")[0])
        ledger = (self.root / "14_CANDIDATES" / "loop" / "ledger.jsonl").read_text(encoding="utf-8")
        self.assertIn(cid, ledger)
        run = json.loads((self.root / "12_RUNTIME" / "agent_runs" / run_id / "run.json")
                         .read_text(encoding="utf-8"))
        self.assertEqual(cid, run["promoted"])
        code, out = self.runs_cli("promote", "--run", run_id)
        self.assertEqual(2, code)
        self.assertIn("promoting twice", out)

    def test_list_filters_by_agent_and_absent_plane_is_empty_not_broken(self):
        code, out = self.runs_cli("list")
        self.assertEqual(0, code)
        self.assertIn("runs: 0", out)
        run_id = self.start_run()
        code, out = self.runs_cli("list", "--agent", self.agent_id)
        self.assertIn(run_id, out)
        code, out = self.runs_cli("list", "--agent", "AGT-nope")
        self.assertIn("runs: 0", out)


if __name__ == "__main__":
    unittest.main()
