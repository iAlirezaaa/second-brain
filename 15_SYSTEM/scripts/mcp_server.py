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
resources/list, resources/read, single messages and batched arrays. `tools/list` reports each
tool's behaviour tag, so a harness can read what a call costs before it makes one.

Read tools answer inside the boundary `backend/access.py` draws: a plane that file denies to
agents is refused here too, and the refusal names the rule instead of a sentence about it.
`candidate_propose` writes where an
agent's writes belong under this repo's law: a registered row on the quarantine shelf --
the human merges. Agent run history is a separate disposable-plane script (runs.py); runs
die at the git boundary, evidence is promoted to the shelf, never stranded in machine state.
`lesson_propose` writes private proposals in .brain-data; only a local human can approve them.
`source_import` records one explicitly named file from inside the brain as a private source
(raw bytes kept, provenance recorded); it refuses any path outside the brain or in a denied zone.
`source_search` answers with the citation and a bounded excerpt, never the whole body.

Phase 44 — behaviour tags. Every tool this door exposes declares one tag from a closed set
(`read_only` / `idempotent` / `destructive`, the vocabulary declared once in
`backend/tools_kit.py`), and `tools/list` carries it on the wire, so a harness decides what to
touch by reading the door instead of guessing: Basic Memory's progressive tool discovery reduced
to the one part worth stealing, none of its AGPL code. The tags are a gate, not a comment.
`--check-tools` audits them and cross-checks them against the actor registry: a tool reachable
with a missing or invented tag, a tool declared with nothing behind it, a door and an engine that
tag the same capability differently, and an agent `tool_allowlist` naming a tool no door carries a
tag for are each a refusal. Exit 0 means every reachable tool is legible; it does not mean the
house is healthy (that is scripts/health.py).

  python 15_SYSTEM/scripts/mcp_server.py --check-tools [--root DIR]   # the audit, no stdio
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
from backend.tools_kit import BEHAVIOR_TAGS, default_registry  # noqa: E402

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
from backend.access import denial, readable  # noqa: E402


# --------------------------------------------------------------------------- tools
class ToolRefused(Exception):
    """A tool refused its arguments -- surfaces as isError, never as a crash."""


# The private source plane keeps the whole body for the human reader; the door answers with the
# citation plus a bounded excerpt (constitution section 7: retrieval is not "send everything").
SOURCE_FIELDS = ("id", "kind", "origin", "filename", "imported_at")
SOURCE_EXCERPT_CHARS = 400


def _plane_law(root, *parts):
    """Ask the access law whether this door may open a plane, and get back the rule's name.

    Nothing here hard-codes a denied directory. The door asks `backend/access.py`, so that file
    stays the one place the boundary is written down, and a refusal quotes the rule actually in
    force instead of a sentence about it that can drift. Returns None when the plane is open.
    """
    return denial(root, Path(root).joinpath(*parts))


RUNS_PLANE = ("12_RUNTIME", "agent_runs")


def _runs_refused(blocked):
    raise ToolRefused(
        "the run plane is closed at this door: %s is denied to agents by "
        "15_SYSTEM/scripts/backend/access.py, and agent run history lives inside it. "
        "This is another actor's trail, not the brain's knowledge: the human view is "
        "`python 15_SYSTEM/scripts/runs.py list` / `show`, and a harness that needs its own "
        "history keeps its own." % blocked)


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
        lines.append("%s [verdict %s, confidence %s]%s" % (row.get("id"), row.get("verdict"),
                                                           row.get("confidence"),
                                                           memory_ledger.recall_mark(row)))
        lines.append("  cue: %s" % row.get("cue"))
        lines.append("  lesson: %s" % row.get("lesson"))
    return text_result("\n".join(lines))


def tool_source_search(root, args):
    from backend import sources
    try:
        rows = sources.search(root, args.get('query', ''), int(args.get('limit', 10)))
    except (ValueError, OSError) as exc:
        raise ToolRefused(str(exc))
    # The stored body is the human's to read; the door hands back the citation and a bounded
    # excerpt, so a query cannot become a copy of the private plane. `sources.py` keeps the
    # full text for the local reader that asked for it by name.
    bounded = []
    for row in rows:
        body = str(row.get('text') or '')
        item = dict((key, row.get(key)) for key in SOURCE_FIELDS)
        item['chars'] = len(body)
        item['excerpt'] = body[:SOURCE_EXCERPT_CHARS]
        item['excerpt_truncated'] = len(body) > SOURCE_EXCERPT_CHARS
        bounded.append(item)
    return json.dumps(bounded, ensure_ascii=False)


def tool_source_import(root, args):
    from backend import access, sources
    path = str(args.get('path') or '').strip()
    kind = str(args.get('kind') or '').strip()
    origin = str(args.get('origin') or '').strip()
    source_format = str(args.get('format') or 'text').strip()
    if not path or not kind or not origin:
        raise ToolRefused('source_import needs path, kind and origin -- an unnamed file '
                          'cannot be cited later')
    candidate = Path(path) if Path(path).is_absolute() else Path(root) / path
    if not access.readable(root, candidate):
        raise ToolRefused('path is outside the brain or inside a denied zone -- this door '
                          'imports only files the human placed in the brain')
    try:
        meta = sources.ingest(root, candidate, kind, origin, source_format)
    except (ValueError, OSError) as exc:
        raise ToolRefused(str(exc))
    try:
        sources.rebuild(root)
    except (ValueError, OSError) as exc:
        raise ToolRefused('source stored as %s but the index rebuild refused: %s -- the raw '
                          'record is authoritative and a later rebuild can index it'
                          % (meta.get('id'), exc))
    return json.dumps(meta, ensure_ascii=False)


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
        row = {"id": rid, "kind": r.get("kind"), "name": r.get("name"),
               "status": r.get("status"), "path": HADES.rel(p),
               "active": rid not in sup}
        if rid in sup:
            row["superseded_by"] = sup[rid]
        rows.append(row)
    retired = sum(1 for row in rows if not row["active"])
    return text_result(json.dumps({"count": len(rows), "retired": retired, "records": rows},
                                  ensure_ascii=False, indent=1))


def tool_registry_show(root, args):
    rid = str(args.get("id") or "").strip()
    if not rid:
        raise ToolRefused("registry_show needs an id")
    cfg = HADES.config()
    recs = list(HADES.iter_records(cfg))
    sup = HADES.superseded_by(recs)
    for p, r in recs:
        if str(r.get("id")) == rid:
            body = json.dumps(r, ensure_ascii=False, indent=1, sort_keys=True)
            text = "%s\npath: %s" % (body, HADES.rel(p))
            if rid in sup:
                text += "\nretired by: %s" % sup[rid]
            return text_result(text)
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
    blocked = _plane_law(root, *RUNS_PLANE)
    out = {"records": len(recs),
           "active_records": len([1 for _p, r in recs if str(r.get("id")) not in sup]),
           "zones_declared": len(zones),
           "zones_missing": missing,
           "lessons": len(list(memory_ledger.active(lessons))),
           "runs": {"read": blocked is None,
                    "denied_by": blocked,
                    "human_view": "python 15_SYSTEM/scripts/runs.py list"},
           "note": "facts only; the gate itself is scripts/health.py"}
    return text_result(json.dumps(out, ensure_ascii=False, indent=1))


def tool_runs_list(root, args):
    """What the actors did -- refused while the plane that holds it is denied (see _plane_law)."""
    _runs_refused(_plane_law(root, *RUNS_PLANE))


def tool_runs_show(root, args):
    """One actor's full trail -- refused for the same reason, before the run id is even looked up."""
    _runs_refused(_plane_law(root, *RUNS_PLANE))


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
    {"name": "capabilities", "behavior": "read_only", "description": "List or suggest registered capabilities; never installs or grants permissions.",
     "inputSchema": {"type": "object", "properties": {"task": {"type": "string"},
                     "harness_id": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}}}},
    {"name": "lesson_propose", "behavior": "idempotent", "description": "Propose a private lesson with an exact source quote; human approval is separate.",
     "inputSchema": {"type": "object", "properties": {"source_id": {"type": "string"},
                     "quote": {"type": "string"}, "lesson": {"type": "string"},
                     "query": {"type": "string"}}, "required": ["source_id", "quote", "lesson", "query"]}},
    {"name": "lesson_recall", "behavior": "read_only", "description": "Recall approved private lessons with their source evidence.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                     "limit": {"type": "integer", "minimum": 1, "maximum": 100}}, "required": ["query"]}},
    {"name": "source_search", "behavior": "read_only",
     "description": "Search explicitly imported private sources, including their origin and "
                    "import time. Each hit carries the citation plus a bounded excerpt and the "
                    "full body's length -- the door never returns a whole private document.",
     "inputSchema": {"type": "object", "properties": {"query": {"type": "string"},
                       "limit": {"type": "integer", "minimum": 1, "maximum": 100}},
                     "required": ["query"]}},
    {"name": "source_import", "behavior": "idempotent",
     "description": "Import one explicitly named UTF-8 file from inside the brain as a private "
                    "source record: raw bytes kept, origin and import time recorded. Duplicate "
                    "content and origin are idempotent; nothing is scanned or fetched, and paths "
                    "outside the brain or in denied zones are refused.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string"},
         "kind": {"type": "string", "enum": ["document", "research", "conversation", "generated"]},
         "origin": {"type": "string"},
         "format": {"type": "string", "enum": ["text", "codex-jsonl", "claude-stream-json", "cursor-stream-json"]}},
         "required": ["path", "kind", "origin"]}},
    {"name": "vault_search", "behavior": "read_only",
     "description": "Keyword search (BM25) over the brain's own prose: zones, wiki, skills, "
                    "the shelf, root documents. Rebuilt per call, never stale.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
         "required": ["query"]}},
    {"name": "memory_recall", "behavior": "read_only",
     "description": "Recall the repo's own lessons (cue/lesson/evidence/confidence) for a "
                    "situation. Read this before repeating a mistake. A lesson whose validity "
                    "window has passed is still returned and marked STALE, never dropped.",
     "inputSchema": {"type": "object", "properties": {
         "query": {"type": "string"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 20}},
         "required": ["query"]}},
    {"name": "registry_list", "behavior": "read_only",
     "description": "List registry records (optionally by kind), with the active/superseded "
                    "split the index enforces.",
     "inputSchema": {"type": "object", "properties": {
         "kind": {"type": "string"}}}},
    {"name": "registry_show", "behavior": "read_only",
     "description": "One registry record by id, as the registry enumerates it.",
     "inputSchema": {"type": "object", "properties": {
         "id": {"type": "string"}}, "required": ["id"]}},
    {"name": "doctor_status", "behavior": "read_only",
     "description": "A structured status readout (records, zones, lessons, and whether this "
                    "door may read the run plane). Facts only -- the gate itself is "
                    "scripts/health.py.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "runs_list", "behavior": "read_only",
     "description": "Refused: the agent-run plane is denied to every harness by "
                    "15_SYSTEM/scripts/backend/access.py, so no actor can read another's "
                    "trail through this door. The human view is `python "
                    "15_SYSTEM/scripts/runs.py list`. The rule is asked, never restated.",
     "inputSchema": {"type": "object", "properties": {
         "agent": {"type": "string"}}}},
    {"name": "runs_show", "behavior": "read_only",
     "description": "Refused for the same reason as runs_list, before any run id is looked up: "
                    "one actor's full step feed is not the brain's knowledge. The human view "
                    "is `python 15_SYSTEM/scripts/runs.py show RUN-ID`.",
     "inputSchema": {"type": "object", "properties": {
         "run": {"type": "string"}}, "required": ["run"]}},
    {"name": "candidate_propose", "behavior": "idempotent",
     "description": "File a proposal as a registered row on the quarantine shelf "
                    "(14_CANDIDATES/loop). A write tool; a human disposes the row.",
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
    "source_import": tool_source_import,
    "vault_search": tool_vault_search,
    "memory_recall": tool_memory_recall,
    "registry_list": tool_registry_list,
    "registry_show": tool_registry_show,
    "doctor_status": tool_doctor_status,
    "runs_list": tool_runs_list,
    "runs_show": tool_runs_show,
    "candidate_propose": tool_candidate_propose,
}


# ---------------------------------------------------------------- behaviour-tag audit (phase 44)
def engine_rows():
    """Every tool the engine toolkit reaches, with the tag its own class declared."""
    return default_registry().rows()


def agent_rows(root):
    """The actor registry as the door sees it: its id, its tool_allowlist, the file it came from.

    An unreadable record comes back carrying `error` instead of being skipped: a gate that nods at
    a record it cannot read is a silent gate, not a clean house.
    """
    root = Path(root)
    base = root / "11_CONTROL" / "agents"
    rows = []
    if not base.is_dir():
        return rows
    for path in sorted(base.glob("*/agent.json")):
        rel = path.relative_to(root).as_posix()
        try:
            rec = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except ValueError as exc:
            rows.append({"id": path.parent.name, "tool_allowlist": [], "path": rel,
                         "error": "agent.json is not JSON (%s)" % exc})
            continue
        allow = rec.get("tool_allowlist")
        row = {"id": str(rec.get("id") or path.parent.name),
               "tool_allowlist": [str(n) for n in allow] if isinstance(allow, list) else [],
               "path": rel, "error": ""}
        if not isinstance(allow, list):
            row["error"] = ("tool_allowlist is %s, not a list -- a grant the gate cannot read is "
                            "a refusal, not a deny" % type(allow).__name__)
        rows.append(row)
    return rows


def destructive_names(door, engine):
    """Every tool tagged destructive on either door. The count is a measurement a reviewer can
    re-run, not a sentence in a document: today it is empty, and a test pins that."""
    out = [str(row.get("name")) for row in door if row.get("behavior") == "destructive"]
    out += [str(row.get("name")) for row in engine if row.get("behavior") == "destructive"]
    return sorted(set(out))


def audit_tags(door, funcs, engine, agents):
    """Refusal strings for the tag cross-check -- pure over the rows it is handed, so a broken
    fixture and the shipped house are judged by the same code.

    Four families, each with a test that breaks one row on purpose and reads the refusal:
      * the door's own declaration: missing tag, invented tag, duplicate, declared but
        unreachable, reachable but undeclared;
      * the engine toolkit's: missing, inherited instead of declared, or a tag that contradicts
        the `writes` flag that actually gates the call;
      * drift between the two doors over one capability (`core.vault_search` and `vault_search`
        must not disagree about what the same act costs);
      * the actor registry: an allowlist entry no door declares is a grant backed by no tag, and
        an engine tool tagged destructive that the harness door carries no tag for may not be
        granted at all -- a destructive act a client cannot see is not a permission, it is a hole.
    """
    problems = []
    declared = {}
    for row in door:
        name = str(row.get("name") or "")
        tag = row.get("behavior")
        if not name:
            problems.append("UNNAMED TOOL: a door entry with no name carries no tag -- %r" % (row,))
            continue
        if tag is None:
            problems.append("UNTAGGED %s: the harness door exposes it with no behaviour tag -- a "
                            "client cannot tell a read from a write" % name)
        elif tag not in BEHAVIOR_TAGS:
            problems.append("BAD TAG %s: behaviour %r is not one of the closed set %s -- an "
                            "invented tag cannot be cross-checked against an actor's allowlist"
                            % (name, tag, list(BEHAVIOR_TAGS)))
        if name in declared:
            problems.append("DUPLICATE %s: the door declares it twice, so two tags can quietly "
                            "disagree about one tool" % name)
        declared[name] = tag
    reachable = set(str(n) for n in funcs)
    for name in sorted(reachable - set(declared)):
        problems.append("UNDECLARED %s: reachable through the door but never listed, so it "
                        "carries no behaviour tag for the client that calls it" % name)
    for name in sorted(set(declared) - reachable):
        problems.append("PHANTOM %s: declared on the door with no function behind it -- a tool a "
                        "client can list and never call" % name)
    engine_by_name = {}
    for row in engine:
        name = str(row.get("name") or "")
        tag = row.get("behavior")
        writes = bool(row.get("writes"))
        if tag not in BEHAVIOR_TAGS:
            problems.append("ENGINE TAG %s: no behaviour tag the closed set recognises (it "
                            "carries %r)" % (name, tag))
        elif not row.get("declared", True):
            problems.append("ENGINE TAG %s: the class declares no behaviour tag of its own, so it "
                            "is carried as the worst case %r -- declare one of %s"
                            % (name, tag, list(BEHAVIOR_TAGS)))
        if tag == "read_only" and writes:
            problems.append("ENGINE TAG %s: tagged read_only while the write gate bites "
                            "(writes=True) -- the tag and the gate are two truths" % name)
        if tag in ("idempotent", "destructive") and not writes:
            problems.append("ENGINE TAG %s: tagged %s while the write gate never bites "
                            "(writes=False) -- the tag and the gate are two truths"
                            % (name, tag))
        engine_by_name[name] = tag
    for name, tag in sorted(engine_by_name.items()):
        capability = name.split(".", 1)[1] if "." in name else name
        door_tag = declared.get(capability)
        if door_tag is not None and door_tag != tag:
            problems.append("TAG DRIFT %s: the harness door tags it %r, the engine toolkit tags it "
                            "%r -- one capability cannot be two kinds of act"
                            % (capability, door_tag, tag))
    for row in agents:
        cid = str(row.get("id") or "(no id)")
        if row.get("error"):
            problems.append("AGENT %s: %s (%s) -- an actor record the gate cannot read governs "
                            "nothing" % (cid, row["error"], row.get("path", "")))
        for name in row.get("tool_allowlist") or []:
            door_tag = declared.get(name)
            engine_tag = engine_by_name.get(name)
            if door_tag is None and engine_tag is None:
                problems.append("ALLOWLIST %s: %r is not a tool any shipped door declares, so no "
                                "behaviour tag backs the grant" % (cid, name))
            elif engine_tag == "destructive" and door_tag is None:
                problems.append("DESTRUCTIVE GRANT %s: %r is tagged destructive by the engine "
                                "toolkit and the harness door carries no tag for it -- an actor "
                                "may not hold a destructive tool the client cannot see"
                                % (cid, name))
    return problems


def check_tools(root):
    """The door audits itself: print what every reachable tool is, then refuse what cannot be
    cross-checked. Facts first, verdict last -- the shape `doctor_status` already uses."""
    engine = engine_rows()
    agents = agent_rows(root)
    for row in sorted(TOOLS, key=lambda item: item["name"]):
        print("  door    %-18s %s" % (row["name"], row.get("behavior")))
    for row in engine:
        print("  engine  %-18s %s%s" % (row["name"], row["behavior"],
                                        " (writes)" if row["writes"] else ""))
    problems = audit_tags(TOOLS, set(TOOL_FUNCS), engine, agents)
    for problem in problems:
        print("INVALID  %s" % problem)
    if problems:
        print("REFUSED: %d problem(s) in the behaviour tags of the tools these doors expose "
              "(closed set: %s)" % (len(problems), ", ".join(BEHAVIOR_TAGS)))
        return 1
    if not agents:
        print("note: no agent records under 11_CONTROL/agents here -- this brain ships no actor "
              "registry, so the tool_allowlist cross-check has nothing to judge (stated out loud "
              "rather than passed silently)")
    print("OK — %d door tool(s) tagged, %d engine tool(s) tagged, %d agent record(s) "
          "cross-checked, %d destructive tool(s) (%s)"
          % (len(TOOLS), len(engine), len(agents), len(destructive_names(TOOLS, engine)),
             ", ".join(BEHAVIOR_TAGS)))
    return 0


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
    parser.add_argument("--check-tools", action="store_true", dest="check_tools",
                        help="audit the behaviour tag of every tool these doors expose and "
                             "cross-check it against the actor registry, then exit; no stdio "
                             "session is opened")
    args = parser.parse_args()
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    if args.check_tools:
        return check_tools(root)
    return serve(root)


if __name__ == "__main__":
    sys.exit(main())
