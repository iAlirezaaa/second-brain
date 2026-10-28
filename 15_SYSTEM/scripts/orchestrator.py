#!/usr/bin/env python
"""The thin driver over the backend package -- SuperAGI's executors as one stdlib CLI.

SuperAGI answered "who walks the steps" with AgentExecutor + Celery workers + an
APScheduler daemon. This brain answers it with one argparse file over `backend/`:

  workflow validate --file WF.json
  workflow run     --file WF.json --agent AGT-... [--approve] [--max-steps N]
  tool list
  tool call       --tool core.vault_search --args '{"query": "gate"}' [--agent AGT-...] [--approve]
  schedule due    --spec '{"every_minutes": 30}' [--last-run ISO] [--now ISO]
  ltm store --text "..." [--source s]
  ltm fetch --query "..." [--k 5]

A workflow run opens a run in the disposable ledger (runs.py), feeds every engine event
into its append-only steps.jsonl, and closes the run completed|failed -- the run dir is
the transcript; promote it if it earned evidence.

Deterministic steps only: an LLM step is a human-gated decision, never engine work.
Writes need --approve AND the actor's tool_allowlist -- the same gate everywhere.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SRC = Path(__file__).resolve().parent
DEFAULT_ROOT = SRC.parents[1]
sys.path.insert(0, str(SRC))          # backend/ and runs.py live next door

from backend import engine as engine_mod  # noqa: E402
from backend import ltm, schedules  # noqa: E402
from backend import workflows as wf_mod  # noqa: E402
from backend.tools_kit import Context, bind_hades, default_registry  # noqa: E402
from backend.tools_kit import ToolError  # noqa: E402
import runs as runs_ledger  # noqa: E402
from runs import RunRefused  # noqa: E402


def _fail(message):
    print("REFUSED: %s" % message)
    return 2


def _load_json(text, what):
    try:
        return json.loads(text)
    except ValueError as exc:
        raise ValueError("%s is not valid JSON: %s" % (what, exc))


def _actor_record(root, actor_id):
    h = bind_hades(root)
    for _p, r in h.iter_records(h.config()):
        if str(r.get("id")) == str(actor_id):
            return r
    return None


def _context_for(root, actor_id, approve):
    """A Context for the actor: its registry record carries the real tool_allowlist.
    No actor -> a context with no actor and an empty allowlist (reads still work)."""
    rec = _actor_record(root, actor_id) if actor_id else None
    if actor_id and (rec is None or rec.get("kind") not in ("agent", "subagent")):
        raise RunRefused("no actor record %s -- tool calls run for agent/subagent records"
                         % actor_id)
    return Context(root, actor_id=str(actor_id or ""),
                   actor_kind=str((rec or {}).get("kind") or ""),
                   allow_writes=approve, allowlist=(rec or {}).get("tool_allowlist") or ())


def cmd_workflow_validate(root, args):
    try:
        wf = _load_json(Path(args.file).read_text(encoding="utf-8"), args.file)
    except OSError as exc:
        return _fail("cannot read %s (%s)" % (args.file, exc))
    except ValueError as exc:
        return _fail(str(exc))
    problems = wf_mod.validate(wf)
    if problems:
        print("REFUSED: %s is not a legal workflow --" % args.file)
        for problem in problems:
            print("  - %s" % problem)
        return 2
    print("VALID: %s | %d step(s) | max_steps %d"
          % (wf.get("name"), len(wf["steps"]), wf.get("max_steps", wf_mod.DEFAULT_MAX_STEPS)))
    return 0


def cmd_workflow_run(root, args):
    try:
        wf = _load_json(Path(args.file).read_text(encoding="utf-8"), args.file)
    except OSError as exc:
        return _fail("cannot read %s (%s)" % (args.file, exc))
    except ValueError as exc:
        return _fail(str(exc))
    problems = wf_mod.validate(wf)
    if problems:
        print("REFUSED: %s is not a legal workflow --" % args.file)
        for problem in problems:
            print("  - %s" % problem)
        return 2
    try:
        ctx = _context_for(root, args.agent, args.approve)
        run = runs_ledger.start_run(root, args.agent,
                                    goal="workflow: %s" % wf.get("name", ""))
    except RunRefused as refused:
        return _fail(str(refused))
    print("WORKFLOW %s | run %s | actor %s (%s) | writes %s"
          % (wf.get("name"), run["run_id"], args.agent, ctx.actor_kind,
             "APPROVED" if ctx.allow_writes else "off"))
    reg = default_registry()
    eng = engine_mod.Engine(reg, max_steps=args.max_steps or None)
    outcome = eng.run(wf, ctx, feed=lambda status, text:
                      runs_ledger.append_step(root, run["run_id"], status, text))
    runs_ledger.close_run(root, run["run_id"], outcome["status"],
                          summary=outcome["reason"])
    print("WORKFLOW %s -> %s | run %s | steps executed: %d | %s"
          % (wf.get("name"), outcome["status"].upper(), run["run_id"],
             outcome["steps"], outcome["reason"]))
    print("the transcript is 12_RUNTIME/agent_runs/%s -- promote it if it earned evidence"
          % run["run_id"])
    return 0 if outcome["status"] == "completed" else 1


def cmd_tool_list(root, args):
    reg = default_registry()
    print("tools: %d" % len(reg.names()))
    for name in reg.names():
        tool = reg.get(name)
        print("%-22s %-6s %s" % (name, "writes" if tool.writes else "read",
                                 tool.description))
    return 0


def cmd_tool_call(root, args):
    try:
        call_args = _load_json(args.args or "{}", "--args")
        if not isinstance(call_args, dict):
            raise ValueError("--args must be a JSON object")
        ctx = _context_for(root, args.agent, args.approve)
        text = default_registry().execute(ctx, args.tool, call_args)
    except (ValueError, RunRefused, ToolError) as exc:
        return _fail(str(exc))
    print(text)
    return 0


def cmd_schedule_due(root, args):
    try:
        spec = _load_json(args.spec, "--spec")
        if args.last_run:
            schedules.parse_utc(args.last_run)
        if args.now:
            schedules.parse_utc(args.now)
        now_dt = schedules.parse_utc(args.now) if args.now else \
            datetime.now(timezone.utc)
        due = schedules.is_due(spec, args.last_run, now_dt)
    except ValueError as exc:
        return _fail(str(exc))
    print("DUE" if due else "NOT DUE")
    print("next run after now: %s" % schedules.next_run_after(spec, now_dt))
    return 0


def cmd_ltm_store(root, args):
    text = str(args.text or "").strip()
    if not text:
        return _fail("ltm store needs --text")
    row = ltm.store(root, text, source=args.source or "human")
    print("stored as row %d in .kb/ltm.sqlite (disposable plane; promote to keep)" % row)
    return 0


def cmd_ltm_fetch(root, args):
    query = str(args.query or "").strip()
    if not query:
        return _fail("ltm fetch needs --query")
    rows = ltm.fetch(root, query, k=args.k)
    if not rows:
        print("nothing in long-term memory matches %r" % query)
        return 0
    for r in rows:
        print("%s [%s] %s" % (r["stored_at"], r["source"], r["text"][:200]))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="HADES backend driver (deterministic)")
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    sub = parser.add_subparsers(dest="cmd")

    p = sub.add_parser("workflow")
    wsub = p.add_subparsers(dest="wcmd")
    q = wsub.add_parser("validate")
    q.add_argument("--file", required=True)
    q = wsub.add_parser("run")
    q.add_argument("--file", required=True)
    q.add_argument("--agent", required=True)
    q.add_argument("--approve", action="store_true")
    q.add_argument("--max-steps", type=int, default=0)

    p = sub.add_parser("tool")
    tsub = p.add_subparsers(dest="tcmd")
    tsub.add_parser("list")
    q = tsub.add_parser("call")
    q.add_argument("--tool", required=True)
    q.add_argument("--args", default="{}")
    q.add_argument("--agent", default="")
    q.add_argument("--approve", action="store_true")

    p = sub.add_parser("schedule")
    ssub = p.add_subparsers(dest="scmd")
    q = ssub.add_parser("due")
    q.add_argument("--spec", required=True)
    q.add_argument("--last-run", default=None)
    q.add_argument("--now", default=None)

    p = sub.add_parser("ltm")
    lsub = p.add_subparsers(dest="lcmd")
    q = lsub.add_parser("store")
    q.add_argument("--text", required=True)
    q.add_argument("--source", default="human")
    q = lsub.add_parser("fetch")
    q.add_argument("--query", required=True)
    q.add_argument("--k", type=int, default=5)

    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else DEFAULT_ROOT
    dispatch = {
        ("workflow", "validate"): cmd_workflow_validate,
        ("workflow", "run"): cmd_workflow_run,
        ("tool", "list"): cmd_tool_list,
        ("tool", "call"): cmd_tool_call,
        ("schedule", "due"): cmd_schedule_due,
        ("ltm", "store"): cmd_ltm_store,
        ("ltm", "fetch"): cmd_ltm_fetch,
    }
    fn = dispatch.get((args.cmd, getattr(args, "wcmd", None) or getattr(args, "tcmd", None)
                       or getattr(args, "scmd", None) or getattr(args, "lcmd", None)))
    if fn is None:
        parser.print_usage()
        return 2
    return fn(root, args)


if __name__ == "__main__":
    sys.exit(main())
