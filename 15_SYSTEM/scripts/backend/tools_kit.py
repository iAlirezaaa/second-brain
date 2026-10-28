"""SuperAGI's toolkit logic, ported: the BaseTool contract, a registry with per-actor
allowlists, and the core toolkit the engine ships with.

SuperAGI gave every agent an AgentConfig with a `tools` list and gave every tool a
name/description/args-schema/execute tuple; the model filled the args. Here the actor is
a registry record, the allowlist is its real `tool_allowlist` field (not decoration),
and the args are deterministic JSON. Write-gating is double: a writes-tool needs an
APPROVED context (CLI `--approve`) AND its qualified name in the actor's allowlist.
An actor with an empty allowlist gets zero write tools -- default deny, like everywhere
else in this repo. Read tools stay open.
"""
import importlib.util
import json
from pathlib import Path
from .access import readable

_HAD = Path(__file__).resolve().parent.parent / "hades.py"
_HADES = None


class ToolError(Exception):
    """A tool refused its arguments or failed -- surfaces as a failed step, never a crash."""


class Tool:
    """The BaseTool contract: a qualified name, a description, a JSON args schema,
    a `writes` flag, and one deterministic `run`."""
    name = ""
    description = ""
    writes = False
    args_schema = {"type": "object", "properties": {}}

    def run(self, root, ctx, args):
        raise NotImplementedError("%s.run" % type(self).__name__)


class Context:
    """Who is acting, and what they are allowed to do. `allow_writes` comes from an
    explicit human `--approve`; `allowlist` comes from the actor's registry record."""

    def __init__(self, root, actor_id="", actor_kind="", allow_writes=False, allowlist=()):
        self.root = root
        self.actor_id = str(actor_id or "")
        self.actor_kind = str(actor_kind or "")
        self.allow_writes = bool(allow_writes)
        self.allowlist = set(allowlist or ())


class Registry:
    def __init__(self):
        self._tools = {}

    def register(self, tool):
        if not tool.name:
            raise ToolError("a tool needs a qualified name (e.g. core.fs_read)")
        if tool.name in self._tools:
            raise ToolError("duplicate tool %s" % tool.name)
        self._tools[tool.name] = tool

    def names(self):
        return sorted(self._tools)

    def get(self, qualified):
        if qualified not in self._tools:
            raise ToolError("unknown tool %r -- see `orchestrator.py tool list`" % qualified)
        return self._tools[qualified]

    def execute(self, ctx, qualified, args):
        tool = self.get(qualified)
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
        return tool.run(ctx.root, ctx, args or {})


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
    description = ("Store a fact/lesson in the actor's long-term memory (.kb/ltm.sqlite -- "
                   "the disposable plane; promote to the shelf to keep it). Writes: needs "
                   "--approve AND a place in the actor's tool_allowlist.")
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


def default_registry():
    reg = Registry()
    for tool in (FsRead(), VaultSearch(), RegistryList(), RegistryShow(),
                 LtmFetch(), LtmStore()):
        reg.register(tool)
    return reg
