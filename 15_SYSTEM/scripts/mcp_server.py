#!/usr/bin/env python
"""The harness door -- a Model Context Protocol (MCP) server over stdio, stdlib-only.

SuperAGI answered "how do agents reach the system" with a server farm: FastAPI, a
SQLAlchemy/Postgres core, Celery workers on Redis, and a Next.js GUI in front of it.
Every one of those is a machine the owner has to run and patch, and none of them is what
a harness actually reads. A harness (OpenCode, Claude Desktop, Cursor, ...) already speaks
one protocol for reaching a brain: MCP over stdio. So the backend here is one script:

  python 15_SYSTEM/scripts/mcp_server.py             # serve the repo this file lives in
  python 15_SYSTEM/scripts/mcp_server.py --root DIR  # serve another checkout (tests)

Wire format: newline-delimited JSON-RPC 2.0 on stdin/stdout (MCP stdio transport),
logs on stderr only. Supported: initialize, ping, tools/list, tools/call,
resources/list, resources/read, single messages and batched arrays.

Read tools are open. `candidate_propose` writes where an
agent's writes belong under this repo's law: a registered row on the quarantine shelf --
the human merges. Agent run history is a separate disposable-plane script (runs.py); runs
die at the git boundary, evidence is promoted to the shelf, never stranded in machine state.
`lesson_propose` writes private proposals in .brain-data; only a local human can approve them.
"""
import argparse
import contextlib
import importlib.util
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))                    # hades lives next door
sys.path.insert(0, str(_HERE.parents[1] / "scripts"))  # common / memory / candidate_check

import common  # noqa: E402
import memory as memory_ledger  # noqa: E402
import candidate_check  # noqa: E402

HADES_PATH = _HERE / "hades.py"
PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "hades-second-brain", "version": "1.0.0"}


def load_hades():
    spec = importlib.util.spec_from_file_location("hades_mcp_bridge", HADES_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


HADES = load_hades()


def bind(root):
    """Point every hades path constant at the served root (same trick the tests use)."""
    HADES.ROOT = root
    HADES.CONFIG_PATH = root / "15_SYSTEM/config/system.json"
    HADES.SCHEMA_PATH = root / "15_SYSTEM/schemas/manifest.schema.json"
    HADES.GEN = root / "15_SYSTEM/generated"
    HADES.PLANS = HADES.GEN / "plans"
    HADES.REGISTRY_KINDS = None
    HADES.MANIFEST_NAMES = None


# --------------------------------------------------------------------------- search
# moved verbatim into the backend package (single source of truth): the MCP door and
# the toolkit's core.vault_search must never drift apart.
from backend.search import snippet, tokenize, vault_search  # noqa: E402,F401
from backend.access import readable  # noqa: E402


# --------------------------------------------------------------------------- tools
class ToolRefused(Exception):
    """A tool refused its arguments -- surfaces as isError, never as a crash."""


def text_result(text):
    return text


def tool_vault_search(root, args):
    query = str(args.get("query") or "").strip()
    if not query:
        raise ToolRefused("vault_search needs a query")
    limit = int(args.get("limit") or 5)
    hits = vault_search(root, query, limit=limit)
    if not hits:
        return text_result("no hits for %r -- try fewer or different words" % query)
    wanted = tokenize(query)
    lines = []
    for score, d in hits:
        lines.append("%s  [%s]  %s" % (d["path"], d["zone"], d["title"]))
        lines.append("    %s" % snippet(d, wanted))
    return text_result("\n".join(lines))


def tool_memory_recall(root, args):
    query = str(args.get("query") or "").strip()
    if not query:
        raise ToolRefused("memory_recall needs a query")
    limit = int(args.get("limit") or 5)
    rows = memory_ledger.recall(root, query, limit=max(1, min(20, limit)))
    if not rows:
        return text_result("no lesson matched %r" % query)
    lines = []
    for row in rows:
        lines.append("%s [verdict %s, confidence %s]" % (row.get("id"), row.get("verdict"),
                                                         row.get("confidence")))
        lines.append("  cue: %s" % row.get("cue"))
        lines.append("  lesson: %s" % row.get("lesson"))
    return text_result("\n".join(lines))


def tool_source_search(root, args):
    from backend import sources
    try:
        return json.dumps(sources.search(root, args.get('query', ''),
                                         int(args.get('limit', 10))), ensure_ascii=False)
    except (ValueError, OSError) as exc:
        raise ToolRefused(str(exc))


def tool_lesson_propose(root, args):
    from backend import learning
    try:
        result = learning.propose(root, args.get('source_id'), args.get('quote'),
                                  args.get('lesson'), args.get('query'))
        return json.dumps(result, ensure_ascii=False)
    except (ValueError, OSError, KeyError) as exc:
        raise ToolRefused(str(exc))


def tool_lesson_recall(root, args):
    from backend import learning
    try:
        return json.dumps(learning.recall(root, args.get('query'), int(args.get('limit', 10))),
                          ensure_ascii=False)
    except (ValueError, OSError, KeyError) as exc:
        raise ToolRefused(str(exc))


def tool_capabilities(root, args):
    from backend import capabilities
    try:
        task = str(args.get('task') or '').strip()
        harness = str(args.get('harness_id') or '').strip()
        result = (capabilities.suggest(root, task, harness, int(args.get('limit', 10)))
                  if task else capabilities.inventory(root, harness))
        return json.dumps(result, ensure_ascii=False)
    except (ValueError, OSError, KeyError) as exc:
        raise ToolRefused(str(exc))


def tool_registry_list(root, args):
    cfg = HADES.config()
    recs = list(HADES.iter_records(cfg))
    kind = str(args.get("kind") or "").strip()
    sup = HADES.superseded_by(recs)
    rows = []
    for p, r in recs:
        rid = str(r.get("id"))
        if kind and r.get("kind") != kind:
            continue
        rows.append({"id": rid, "kind": r.get("kind"), "name": r.get("name"),
                     "status": r.get("status"), "path": HADES.rel(p),
                     "active": rid not in sup})
    return text_result(json.dumps({"count": len(rows), "records": rows},
                                  ensure_ascii=False, indent=1))


def tool_registry_show(root, args):
    rid = str(args.get("id") or "").strip()
    if not rid:
        raise ToolRefused("registry_show needs an id")
    cfg = HADES.config()
    for p, r in HADES.iter_records(cfg):
        if str(r.get("id")) == rid:
            body = json.dumps(r, ensure_ascii=False, indent=1, sort_keys=True)
            return text_result("%s\npath: %s" % (body, HADES.rel(p)))
    raise ToolRefused("no record %s -- registry_show only sees what the registry enumerates" % rid)


def tool_doctor_status(root, args):
    """A status readout, not the gate itself -- the gate is scripts/health.py."""
    cfg = HADES.config()
    recs = list(HADES.iter_records(cfg))
    sup = HADES.superseded_by(recs)
    gi = HADES.gitignore_lines()
    zones = HADES.zone_dirs(cfg)
    missing = [z for z in zones if not (root / z).exists() and not HADES.absent_by_boundary(cfg, z, gi)]
    lessons, _problems = memory_ledger.read_lessons(root)
    runs_root = root / "12_RUNTIME" / "agent_runs"
    runs = sorted([d.name for d in runs_root.iterdir() if d.is_dir()]) if runs_root.is_dir() else []
    out = {"records": len(recs),
           "active_records": len([1 for _p, r in recs if str(r.get("id")) not in sup]),
           "zones_declared": len(zones),
           "zones_missing": missing,
           "lessons": len(list(memory_ledger.active(lessons))),
           "runs": len(runs),
           "note": "facts only; the gate itself is scripts/health.py"}
    return text_result(json.dumps(out, ensure_ascii=False, indent=1))


def tool_runs_list(root, args):
    """What the actors did -- the disposable plane, read-only through the door."""
    import runs as runs_ledger
    base = runs_ledger.runs_dir(root)
    rows = []
    if base.is_dir():
        for d in sorted(base.iterdir()):
            run = runs_ledger.load_run(root, d.name)
            if run is None:
                continue
            if args.get("agent") and str(run.get("agent")) != str(args["agent"]):
                continue
            rows.append({"run_id": run.get("run_id"), "agent": run.get("agent"),
                         "kind": run.get("kind"), "status": run.get("status"),
                         "steps": run.get("steps"), "goal": run.get("goal"),
                         "promoted": run.get("promoted") or ""})
    return text_result(json.dumps({"runs": len(rows), "items": rows},
                                  ensure_ascii=False, indent=1))


def tool_runs_show(root, args):
    import runs as runs_ledger
    run_id = str(args.get("run") or "").strip()
    if not run_id:
        raise ToolRefused("runs_show needs a run id (see runs_list)")
    run = runs_ledger.load_run(root, run_id)
    if run is None:
        raise ToolRefused("no such run %s -- runs are disposable plane state, absent in "
                          "a fresh clone" % run_id)
    feed = runs_ledger.read_feed(runs_ledger.runs_dir(root) / run_id)
    body = json.dumps(run, ensure_ascii=False, indent=1, sort_keys=True)
    lines = ["%s" % body, "feed: %d step(s)" % len(feed)]
    for i, s in enumerate(feed, 1):
        lines.append("  %d. [%s] %s" % (i, s.get("status"), s.get("text")))
    return text_result("\n".join(lines))


SHELF_ROW = """---
id: {cid}
type: note
title: 'Loop candidate: proposed by an agent over MCP'
status: raw
owner: agent
topics: [mcp, proposal]
created: {today}
updated: {today}
dimension: {dimension}
cue: {cue}
lesson: {lesson}
confidence: {confidence}
verdict: proposed
evidence:
  - 15_SYSTEM/scripts/mcp_server.py
---

# {cid}

**Proposed by an agent through the harness door** (`candidate_propose`), {today}.
This row is a proposal, not a decision: `verdict: proposed` is legal on the shelf and
never promotable. The human reviews, probes and disposes it.
"""


def tool_candidate_propose(root, args):
    """The only write this door offers: an agent proposes, the human decides."""
    dimension = str(args.get("dimension") or "domain").strip()
    cue = str(args.get("cue") or "").strip()
    lesson = str(args.get("lesson") or "").strip()
    if dimension not in ("invariant", "domain"):
        raise ToolRefused("dimension must be 'invariant' or 'domain', got %r" % dimension)
    if not cue or not lesson:
        raise ToolRefused("candidate_propose needs both cue and lesson -- an unstateable "
                          "proposal is not a proposal")
    try:
        confidence = float(args.get("confidence") if args.get("confidence") is not None else 0.6)
    except (TypeError, ValueError):
        raise ToolRefused("confidence must be a number in 0..1")
    if not (0.0 <= confidence <= 1.0):
        raise ToolRefused("confidence must be in 0..1, got %s" % confidence)
    shelf = root / "14_CANDIDATES" / "loop"
    shelf.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seq = 1 + len(list(shelf.glob("cand-%s-mcp-*.md" % today)))
    cid = "cand-%s-mcp-%02d" % (today, seq)
    if (shelf / (cid + ".md")).exists():
        raise ToolRefused("row id %s already exists -- refusing to overwrite a proposal" % cid)
    row = SHELF_ROW.format(cid=cid, today=today, dimension=dimension, cue=cue,
                           lesson=lesson, confidence=confidence)
    path = shelf / (cid + ".md")
    path.write_text(row, encoding="utf-8")
    # candidate_check.register prints; its stdout must never touch the protocol channel
    with contextlib.redirect_stdout(io.StringIO()) as _captured:
        rc = candidate_check.register(root, str(path))
    if rc != 0:
        raise ToolRefused("row written but the ledger refused it -- the shelf is out of "
                          "balance; a human should look")
    return text_result("PROPOSED %s -> %s (registered in the ledger; a human decides)\n"
                       "cue: %s" % (cid, HADES.rel(path), cue))


TOOLS = [
    {"name": "capabilities", "description": "List or suggest registered capabilities; never installs or grants permissions.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"},
                     "harness_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}}},
    {"name": "lesson_propose", "description": "Propose a private lesson with an exact source quote; human approval is separate.",
     "inputSchema": {"type": "object", "properties": {"source_id": {"type": "string"},
                     "quote": {"type": "string"}, "lesson": {"type": "string"},
                     "query": {"type": "string"}}, "required": ["source_id", "quote", "lesson", "query"]}},
    {"name": "lesson_recall", "description": "Recall approved private lessons with their source evidence.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                     "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["query"]}},
    {"name": "source_search",
     "description": "Search explicitly imported private sources, including their origin and import time.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                       "limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                     "required": ["query"]}},
    {"name": "vault_search",
     "description": "Keyword search (BM25) over the brain's own prose: zones, wiki, skills, "
                    "the shelf, root documents. Rebuilt per call, never stale.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
         "required": ["query"]}},
    {"name": "memory_recall",
     "description": "Recall the repo's own lessons (cue/lesson/evidence/confidence) for a "
                    "situation. Read this before repeating a mistake.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
         "required": ["query"]}},
    {"name": "registry_list",
     "description": "List registry records (optionally by kind), with the active/superseded "
                    "split the index enforces.",
     "inputSchema": {"type": "object", "properties": {
         "kind": {"type": "string"}}}},
    {"name": "registry_show",
     "description": "One registry record by id, as the registry enumerates it.",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "string"}}, "required": ["id"]}},
    {"name": "doctor_status",
     "description": "A structured status readout (records, zones, lessons, runs). Facts "
                    "only -- the gate itself is scripts/health.py.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "runs_list",
     "description": "Agent runs from the disposable plane (12_RUNTIME/agent_runs): who ran, "
                    "status, step count, whether the run was promoted to the shelf.",
     "inputSchema": {"type": "object", "properties": {
         "agent": {"type": "string"}}}},
    {"name": "runs_show",
     "description": "One agent run by id: identity plus its append-only step feed.",
     "inputSchema": {"type": "object", "properties": {
         "run": {"type": "string"}}, "required": ["run"]}},
    {"name": "candidate_propose",
     "description": "File a proposal as a registered row on the quarantine shelf "
                    "(14_CANDIDATES/loop). The only write tool; a human disposes it.",
     "inputSchema": {"type": "object", "properties": {
         "dimension": {"type": "string", "enum": ["invariant", "domain"]},
         "cue": {"type": "string"},
         "lesson": {"type": "string"},
         "confidence": {"type": "number", "minimum": 0, "maximum": 1}},
         "required": ["cue", "lesson"]}},
]
TOOL_FUNCS = {
    "capabilities": tool_capabilities,
    "lesson_propose": tool_lesson_propose,
    "lesson_recall": tool_lesson_recall,
    "source_search": tool_source_search,
    "vault_search": tool_vault_search,
    "memory_recall": tool_memory_recall,
    "registry_list": tool_registry_list,
    "registry_show": tool_registry_show,
    "doctor_status": tool_doctor_status,
    "runs_list": tool_runs_list,
    "runs_show": tool_runs_show,
    "candidate_propose": tool_candidate_propose,
}

RESOURCE_FILES = [
    ("AGENTS.md", "text/markdown", "The canon: laws every agent must follow"),
    ("HANDOFF.md", "text/markdown", "The formal session handoff (state snapshot + next actions)"),
    ("README.md", "text/markdown", "What this repo is and how to run it"),
    ("ROADMAP.md", "text/markdown", "The phase roadmap"),
    ("00_START_HERE/SYSTEM_MAP.md", "text/markdown", "Zone map of the brain"),
]


def tool_resources(root):
    out = []
    for rel, mime, desc in RESOURCE_FILES:
        if (root / rel).is_file():
            out.append({"uri": "file://" + rel, "name": Path(rel).name,
                        "description": desc, "mimeType": mime})
    return out


def read_resource(root, uri):
    rel = uri[len("file://"):] if uri.startswith("file://") else uri
    if rel not in {item[0] for item in RESOURCE_FILES}:
        raise ToolRefused("resource is not published: %s" % rel)
    candidate = (root / rel).resolve()
    if root.resolve() not in candidate.parents:
        raise ToolRefused("resource uri %r escapes the vault" % uri)
    if not readable(root, candidate):
        raise ToolRefused("resource is outside the default read scope")
    if not candidate.is_file():
        raise ToolRefused("no such resource: %s" % rel)
    mime = "application/json" if candidate.suffix == ".json" else "text/markdown"
    return {"uri": "file://" + rel, "mimeType": mime,
            "text": candidate.read_text(encoding="utf-8", errors="replace")}


# --------------------------------------------------------------------------- protocol
def wire(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def ok(mid, result):
    return {"jsonrpc": "2.0", "id": mid, "result": result}


def err(mid, code, message):
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}


def handle_tool_call(root, params):
    name = str(params.get("name") or "")
    fn = TOOL_FUNCS.get(name)
    if fn is None:
        return {"content": [{"type": "text", "text": "unknown tool %r" % name}], "isError": True}
    try:
        text = fn(root, params.get("arguments") or {})
    except ToolRefused as refused:
        return {"content": [{"type": "text", "text": "REFUSED: %s" % refused}], "isError": True}
    except Exception as exc:  # a tool crash is a tool result, not a dead server
        return {"content": [{"type": "text", "text": "ERROR: %s" % exc}], "isError": True}
    return {"content": [{"type": "text", "text": text}]}


def handle(root, msg, responses):
    if not isinstance(msg, dict):
        if isinstance(msg, list):
            for item in msg:
                handle(root, item, responses)
        else:
            responses.append(err(None, -32600, "Invalid Request"))
        return
    method, mid = msg.get("method"), msg.get("id")
    if method is None:
        if mid is not None:
            responses.append(err(mid, -32600, "Invalid Request: no method"))
        return
    if method.startswith("notifications/"):
        return  # a notification gets no reply, by protocol
    if method == "initialize":
        wanted = str((msg.get("params") or {}).get("protocolVersion") or PROTOCOL_VERSION)
        responses.append(ok(mid, {
            "protocolVersion": wanted,
            "capabilities": {"tools": {"listChanged": False},
                             "resources": {"subscribe": False, "listChanged": False}},
            "serverInfo": SERVER_INFO,
            "instructions": "Read AGENTS.md first (it is exposed as a resource). "
                            "Agents may propose candidates and private lessons; humans decide.",
        }))
    elif method == "ping":
        responses.append(ok(mid, {}))
    elif method == "tools/list":
        responses.append(ok(mid, {"tools": TOOLS}))
    elif method == "tools/call":
        responses.append(ok(mid, handle_tool_call(root, msg.get("params") or {})))
    elif method == "resources/list":
        responses.append(ok(mid, {"resources": tool_resources(root)}))
    elif method == "resources/read":
        try:
            responses.append(ok(mid, {"contents": [read_resource(root, (msg.get("params") or {}).get("uri"))]}))
        except ToolRefused as refused:
            responses.append(err(mid, -32602, str(refused)))
    else:
        responses.append(err(mid, -32601, "Method not found: %s" % method))


def serve(root):
    bind(root)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except ValueError:
            wire(err(None, -32700, "Parse error"))
            continue
        responses = []
        with contextlib.redirect_stderr(sys.stderr):  # tool prints never touch the protocol
            handle(root, msg, responses)
        for response in responses:
            wire(response)
    return 0


def main():
    parser = argparse.ArgumentParser(description="HADES second-brain MCP server (stdio)")
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    return serve(root)


if __name__ == "__main__":
    sys.exit(main())
