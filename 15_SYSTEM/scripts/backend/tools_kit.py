"""SuperAGI's toolkit logic, ported: the BaseTool contract, a registry with per-actor
allowlists, and the core toolkit the engine ships with.

SuperAGI gave every agent an AgentConfig with a `tools` list and gave every tool a
name/description/args-schema/execute tuple; the model filled the args. Here the actor is
a registry record, the allowlist is its real `tool_allowlist` field (not decoration),
and the args are deterministic JSON. Write-gating is double: a writes-tool needs an
APPROVED context (CLI `--approve`) AND its qualified name in the actor's allowlist.
An actor with an empty allowlist gets zero write tools -- default deny, like everywhere
else in this repo. Read tools stay open.

Phase 44 adds the third thing a client needs to know about a tool, which the `writes` flag
alone never said: its *behaviour* (`read_only` / `idempotent` / `destructive`, one closed
vocabulary declared here and read by the MCP door's `--check-tools` audit). `writes` says
whether the gate bites; the tag says what a call can cost.
"""
import importlib.util
import json
from pathlib import Path
from .access import readable
from . import session_bridge

_HAD = Path(__file__).resolve().parent.parent / "hades.py"
_HADES = None


class ToolError(Exception):
    """A tool refused its arguments or failed -- surfaces as a failed step, never a crash."""


# Phase 44: every tool says what kind of act it is, from one closed vocabulary. Basic Memory
# answers "what may a harness call" with progressive tool discovery; the useful part of that is
# the tag, not the AGPL code around it. The three names are read by `mcp_server.py --check-tools`
# and cross-checked against the actor registry, so they are a gate and not a comment:
#   read_only    -- cannot change any state; safe to call at any time, any number of times.
#   idempotent   -- writes, and what it writes is fixed by its arguments: calling it again cannot
#                   overwrite or remove state that already exists (it either dedupes by content
#                   or appends a row nothing else points at). The tag never claims byte-identical
#                   results: a second `core.ltm_store` call is a second row, which is still not a
#                   destructive act.
#   destructive  -- writes that can overwrite or remove state the caller did not create in this
#                   same call. Nothing in the shipped toolkit is tagged destructive today.
# A class that declares no tag at all is carried as the worst case (`destructive`) rather than
# silently reading as harmless, and the audit names it for inheriting instead of declaring.
BEHAVIOR_TAGS = ("destructive", "idempotent", "read_only")
UNDECLARED_TAG = "destructive"


class Tool:
    """The BaseTool contract: a qualified name, a description, a JSON args schema,
    a `writes` flag, a behaviour tag, and one deterministic `run`."""
    name = ""
    description = ""
    writes = False
    behavior = UNDECLARED_TAG          # each tool declares its own; the default is worst case
    args_schema = {"type": "object", "properties": {}}

    def run(self, root, ctx, args):
        raise NotImplementedError("%s.run" % type(self).__name__)


class Context:
    """Who is acting, and what they are allowed to do. `allow_writes` comes from an
    explicit human `--approve`; `allowlist` comes from the actor's registry record."""

    def __init__(self, root, actor_id="", actor_kind="", allow_writes=False, allowlist=(),
                 session_id="", task_id=None):
        self.root = root
        self.actor_id = str(actor_id or "")
        self.actor_kind = str(actor_kind or "")
        self.allow_writes = bool(allow_writes)
        self.allowlist = set(allowlist or ())
        self.session_id = str(session_id or "")
        self.task_id = task_id


class Registry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        if not tool.name:
            raise ToolError("a tool needs a qualified name (e.g. core.fs_read)")
        if tool.behavior not in BEHAVIOR_TAGS:
            raise ToolError("tool %s declares behaviour %r, which is not one of the closed set "
                            "%s -- an invented tag cannot be cross-checked against an actor's "
                            "tool_allowlist" % (tool.name, tool.behavior, list(BEHAVIOR_TAGS)))
        if tool.behavior == "read_only" and tool.writes:
            raise ToolError("tool %s is tagged read_only but its write gate bites (writes=True) "
                            "-- one tool, two truths about what it does" % tool.name)
        if tool.name in self._tools:
            raise ToolError("duplicate tool %s" % tool.name)
        self._tools[tool.name] = tool

    def names(self):
        return sorted(self._tools)

    def rows(self):
        """What the audit reads: name, declared tag, write flag, and whether the class declared
        the tag itself or inherited the worst-case default."""
        out = []
        for name in self.names():
            tool = self._tools[name]
            out.append({"name": name, "behavior": tool.behavior, "writes": bool(tool.writes),
                        "declared": "behavior" in vars(type(tool))})
        return out

    def get(self, qualified):
        if qualified not in self._tools:
            raise ToolError("unknown tool %r -- see `orchestrator.py tool list`" % qualified)
        return self._tools[qualified]

    def execute(self, ctx, qualified, args):
        tool = self.get(qualified)
        try:
            session_bridge.require(ctx.root, ctx.session_id, ctx.actor_id, ctx.task_id)
        except ValueError as exc:
            raise ToolError(str(exc))
        if tool.writes:
            if not ctx.allow_writes:
                raise ToolError("tool %s writes; this context is not approved (--approve)"
                                % qualified)
            if not ctx.actor_id:
                raise ToolError("tool %s writes; this context has no actor (--agent)"
                                % qualified)
            if qualified not in ctx.allowlist:
                raise ToolError("tool %s is not in actor %s's tool_allowlist "
                                "(an empty list means zero write tools)"
                                % (qualified, ctx.actor_id or "(none)"))
        if ctx.session_id:
            try:
                session_bridge.audit(ctx.root, ctx.session_id, ctx.actor_id,
                                     qualified, "attempt", "", ctx.task_id)
            except ValueError as exc:
                raise ToolError(str(exc))
        try:
            result = tool.run(ctx.root, ctx, args or {})
        except Exception as exc:
            if ctx.session_id:
                try:
                    session_bridge.audit(ctx.root, ctx.session_id, ctx.actor_id,
                                         qualified, "failed", type(exc).__name__, ctx.task_id)
                except ValueError:
                    pass  # preserve the underlying tool error; attempt was already recorded
            raise
        if ctx.session_id:
            try:
                session_bridge.audit(ctx.root, ctx.session_id, ctx.actor_id,
                                     qualified, "ok", result, ctx.task_id)
            except ValueError as exc:
                raise ToolError("tool returned but session completion audit failed: %s" % exc)
        return result


def hades_module():
    global _HADES
    if _HADES is None:
        spec = importlib.util.spec_from_file_location("hades_backend", _HAD)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _HADES = module
    return _HADES


def bind_hades(root):
    """Point every hades path constant at `root` (same rebinding mcp_server.bind does),
    so the registry tools work on any vault: the real repo, a temp copy, a clone."""
    h = hades_module()
    h.ROOT = root
    h.CONFIG_PATH = root / "15_SYSTEM/config/system.json"
    h.SCHEMA_PATH = root / "15_SYSTEM/schemas/manifest.schema.json"
    h.GEN = root / "15_SYSTEM/generated"
    h.PLANS = h.GEN / "plans"
    h.REGISTRY_KINDS = None
    h.MANIFEST_NAMES = None
    return h


class FsRead(Tool):
    name = "core.fs_read"
    behavior = "read_only"
    description = ("Read a file inside this vault (first 2000 chars). Paths outside the "
                   "root are refused -- the guard is the tool's, not the caller's.")
    args_schema = {"type": "object",
                   "properties": {"path": {"type": "string"}},
                   "required": ["path"]}

    def run(self, root, ctx, args):
        rel = str(args.get("path") or "").strip().replace("\\", "/")
        if not rel:
            raise ToolError("fs_read needs a path relative to the vault root")
        target = (root / rel).resolve()
        if root.resolve() not in target.parents:
            raise ToolError("path %r escapes the vault" % rel)
        if not readable(root, root / rel):
            raise ToolError("path %r is outside the default read scope" % rel)
        if not target.is_file():
            raise ToolError("no such file: %s" % rel)
        return target.read_text(encoding="utf-8", errors="replace")[:2000]


class VaultSearch(Tool):
    name = "core.vault_search"
    behavior = "read_only"
    description = "BM25 keyword search over the brain's prose (the same index the MCP door uses)."
    args_schema = {"type": "object",
                   "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}},
                   "required": ["query"]}

    def run(self, root, ctx, args):
        from .search import snippet, tokenize, vault_search
        query = str(args.get("query") or "").strip()
        if not query:
            raise ToolError("vault_search needs a query")
        hits = vault_search(root, query, limit=int(args.get("limit") or 5))
        if not hits:
            return "no hits for %r -- try fewer or different words" % query
        wanted = tokenize(query)
        lines = []
        for _score, d in hits:
            lines.append("%s  [%s]  %s" % (d["path"], d["zone"], d["title"]))
            lines.append("    %s" % snippet(d, wanted))
        return "\n".join(lines)


class RegistryList(Tool):
    name = "core.registry_list"
    behavior = "read_only"
    description = "List registry records (optionally by kind), with the active/superseded split."
    args_schema = {"type": "object", "properties": {"kind": {"type": "string"}}}

    def run(self, root, ctx, args):
        h = bind_hades(root)
        recs = list(h.iter_records(h.config()))
        kind = str(args.get("kind") or "").strip()
        sup = h.superseded_by(recs)
        rows = []
        for p, r in recs:
            rid = str(r.get("id"))
            if kind and r.get("kind") != kind:
                continue
            rows.append({"id": rid, "kind": r.get("kind"), "name": r.get("name"),
                         "status": r.get("status"), "path": h.rel(p), "active": rid not in sup})
        return json.dumps({"count": len(rows), "records": rows}, ensure_ascii=False, indent=1)


class RegistryShow(Tool):
    name = "core.registry_show"
    behavior = "read_only"
    description = "One registry record by id, as the registry enumerates it."
    args_schema = {"type": "object",
                   "properties": {"id": {"type": "string"}},
                   "required": ["id"]}

    def run(self, root, ctx, args):
        rid = str(args.get("id") or "").strip()
        if not rid:
            raise ToolError("registry_show needs an id")
        h = bind_hades(root)
        for p, r in h.iter_records(h.config()):
            if str(r.get("id")) == rid:
                return "%s\npath: %s" % (json.dumps(r, ensure_ascii=False, indent=1,
                                                   sort_keys=True), h.rel(p))
        raise ToolError("no record %s -- the registry only sees what it enumerates" % rid)


class LtmFetch(Tool):
    name = "core.ltm_fetch"
    behavior = "read_only"
    description = "Fetch the actor's long-term memory by relevance (FTS5 over .kb/ltm.sqlite)."
    args_schema = {"type": "object",
                   "properties": {"query": {"type": "string"}, "k": {"type": "integer"}},
                   "required": ["query"]}

    def run(self, root, ctx, args):
        from . import ltm
        query = str(args.get("query") or "").strip()
        if not query:
            raise ToolError("ltm_fetch needs a query")
        rows = ltm.fetch(root, query, k=int(args.get("k") or 5))
        if not rows:
            return "nothing in long-term memory matches %r" % query
        return "\n".join("%s [%s] %s" % (r["stored_at"], r["source"], r["text"][:200])
                         for r in rows)


class LtmStore(Tool):
    name = "core.ltm_store"
    writes = True
    behavior = "idempotent"
    description = ("Store a fact/lesson in the actor's long-term memory (.kb/ltm.sqlite -- "
                   "the disposable plane; promote to the shelf to keep it). Writes: needs "
                   "--approve AND a place in the actor's tool_allowlist. Behaviour "
                   "idempotent: it appends a row and overwrites or deletes nothing.")
    args_schema = {"type": "object",
                   "properties": {"text": {"type": "string"}, "source": {"type": "string"}},
                   "required": ["text"]}

    def run(self, root, ctx, args):
        from . import ltm
        text = str(args.get("text") or "").strip()
        if not text:
            raise ToolError("ltm_store needs text")
        source = str(args.get("source") or "").strip() or ctx.actor_id or "agent"
        row = ltm.store(root, text, source=source)
        return "stored as row %d in .kb/ltm.sqlite (disposable plane; promote to keep)" % row


class LayaDecide(Tool):
    """Optional System-1 read-only proposal, never an action executor."""
    name = "core.laya_decide"
    behavior = "read_only"
    description = ("Get typed local Laya decision proposals. Opt-in on Python 3.10+; "
                   "low-confidence answers require review and never trigger tools.")
    args_schema = {"type": "object",
                   "properties": {"state": {}, "questions": {"type": "object"},
                                  "min_confidence": {"type": "number"},
                                  "model": {"type": "string"}},
                   "required": ["state", "questions"]}

    def run(self, root, ctx, args):
        from . import laya_adapter
        if not isinstance(args, dict):
            raise ToolError("laya_decide needs a JSON object")
        try:
            return json.dumps(laya_adapter.decide(
                args.get("state"), args.get("questions"),
                min_confidence=args.get("min_confidence", laya_adapter.DEFAULT_MIN_CONFIDENCE),
                model=args.get("model", "auto")), ensure_ascii=False)
        except laya_adapter.DecisionRefused as exc:
            raise ToolError(str(exc))

def default_registry():
    reg = Registry()
    for tool in (FsRead(), VaultSearch(), RegistryList(), RegistryShow(),
                 LtmFetch(), LtmStore(), LayaDecide()):
        reg.register(tool)
    return reg
