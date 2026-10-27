#!/usr/bin/env python
"""The disposable runtime ledger for agent runs -- SuperAGI's execution model, at git scale.

SuperAGI kept AgentExecution / AgentExecutionStep / AgentExecutionFeed rows in Postgres
behind a server farm. Here the actor is a registry record (11_CONTROL -- the plane of
definitions) and what the actor *did* is machine state:

  12_RUNTIME/agent_runs/<RUN-XXXXXXXX>/run.json      identity, status, goal
  12_RUNTIME/agent_runs/<RUN-XXXXXXXX>/steps.jsonl   append-only feed

Commands:
  python 15_SYSTEM/scripts/runs.py start --agent AGT-... --goal "..." [--agent-kind agent]
  python 15_SYSTEM/scripts/runs.py step  --run RUN-... --text "..." [--status ok|fail|note]
  python 15_SYSTEM/scripts/runs.py finish --run RUN-... --status completed|failed [--summary "..."]
  python 15_SYSTEM/scripts/runs.py list [--agent AGT-...]
  python 15_SYSTEM/scripts/runs.py show RUN-... [--tail 10]

Everything here lives inside 12_RUNTIME, so it dies at the git boundary by design: runs
are not evidence. When a run matters, promote what it produced to the shelf
(candidates) or the human plane (promote.py) -- knowledge stranded in machine state is
the exact defect this layout exists to prevent.

A run of an actor the registry has never heard of is refused: an unaccounted actor is
how a registry starts lying.
"""
import argparse
import importlib.util
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SRC = Path(__file__).resolve().parent          # 15_SYSTEM/scripts
DEFAULT_ROOT = SRC.parents[1]                  # the repo this file lives in

HADES_PATH = SRC / "hades.py"


def now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_hades(root):
    """Load hades bound to the served root (the same trick the tests use)."""
    spec = importlib.util.spec_from_file_location("hades_runs_bridge", HADES_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.ROOT = root
    module.CONFIG_PATH = root / "15_SYSTEM/config/system.json"
    module.SCHEMA_PATH = root / "15_SYSTEM/schemas/manifest.schema.json"
    module.GEN = root / "15_SYSTEM/generated"
    module.PLANS = module.GEN / "plans"
    module.KIND_NAMES = None
    module.MANIFEST_NAMES = None
    return module


def runs_dir(root):
    return root / "12_RUNTIME" / "agent_runs"


def run_path(root, run_id):
    return runs_dir(root) / run_id / "run.json"


def load_run(root, run_id):
    path = run_path(root, run_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_run(root, run):
    path = run_path(root, run["run_id"])
    path.write_text(json.dumps(run, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                    encoding="utf-8")


def cmd_start(root, args):
    hades = load_hades(root)
    hit = None
    for p, r in hades.iter_records(hades.config()):
        if str(r.get("id")) == str(args.agent):
            hit = (p, r)
            break
    if not hit:
        print("REFUSED: no registry record %s -- a run of an unaccounted actor is how a "
              "registry starts lying (see `hades.py list --kind agent`)" % args.agent)
        return 2
    kind = hit[1].get("kind")
    if kind not in ("agent", "subagent"):
        print("REFUSED: %s is a %s record -- runs are started for actors (agent/subagent), "
              "not for %s" % (args.agent, kind, kind))
        return 2
    run_id = "RUN-" + uuid.uuid4().hex[:8].upper()
    target = runs_dir(root) / run_id
    target.mkdir(parents=True, exist_ok=True)
    run = {"run_id": run_id, "agent": str(args.agent), "kind": kind,
           "goal": str(args.goal or ""), "status": "running",
           "started_utc": now_utc(), "ended_utc": "", "steps": 0, "summary": ""}
    save_run(root, run)
    print("RUN %s started | actor %s (%s) | goal: %s" % (run_id, args.agent, kind, run["goal"]))
    print("append steps:  runs.py step --run %s --text \"...\"" % run_id)
    print("close it:      runs.py finish --run %s --status completed|failed" % run_id)
    return 0


def cmd_step(root, args):
    run = load_run(root, args.run)
    if run is None:
        print("REFUSED: no such run %s under %s" % (args.run, runs_dir(root).name))
        return 2
    if run.get("status") != "running":
        print("REFUSED: run %s is %s -- a finished run's feed is history, not a place to "
              "append" % (args.run, run.get("status")))
        return 2
    text = str(args.text or "").strip()
    if not text:
        print("REFUSED: step needs --text (an unnamed step is not a feed entry)")
        return 2
    status = args.status if args.status in ("ok", "fail", "note") else "ok"
    entry = {"utc": now_utc(), "status": status, "text": text}
    with (runs_dir(root) / args.run / "steps.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    run["steps"] = int(run.get("steps") or 0) + 1
    save_run(root, run)
    print("STEP %s #%d [%s] %s" % (args.run, run["steps"], status, text))
    return 0


def cmd_finish(root, args):
    run = load_run(root, args.run)
    if run is None:
        print("REFUSED: no such run %s" % args.run)
        return 2
    if run.get("status") != "running":
        print("REFUSED: run %s is already %s -- finishing twice is a second truth"
              % (args.run, run.get("status")))
        return 2
    if args.status not in ("completed", "failed"):
        print("REFUSED: finish wants --status completed|failed (a run ends in one of two "
              "states, like its evidence or its excuse)")
        return 2
    run["status"] = args.status
    run["ended_utc"] = now_utc()
    if args.summary:
        run["summary"] = str(args.summary)
    save_run(root, run)
    print("RUN %s %s | steps: %d | summary: %s"
          % (args.run, args.status, run["steps"], run["summary"] or "(none)"))
    return 0


def cmd_list(root, args):
    base = runs_dir(root)
    if not base.is_dir():
        print("runs: 0")
        return 0
    rows = []
    for d in sorted(base.iterdir()):
        run = load_run(root, d.name)
        if run is None:
            continue
        if args.agent and str(run.get("agent")) != str(args.agent):
            continue
        rows.append(run)
    print("runs: %d" % len(rows))
    for run in rows:
        print("%s | %s [%s] | steps %d | %s" % (run["run_id"], run.get("agent"),
                                                run.get("status"), run.get("steps"),
                                                (run.get("goal") or "")[:60]))
    return 0


def cmd_show(root, args):
    run = load_run(root, args.run)
    if run is None:
        print("REFUSED: no such run %s" % args.run)
        return 2
    print(json.dumps(run, ensure_ascii=False, indent=1, sort_keys=True))
    feed = runs_dir(root) / args.run / "steps.jsonl"
    if feed.is_file():
        lines = feed.read_text(encoding="utf-8").splitlines()
        tail = lines[-max(1, args.tail):] if lines else []
        print("steps: %d total, showing last %d" % (len(lines), len(tail)))
        for line in tail:
            print("  %s" % line)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description="HADES agent-run ledger (disposable plane)")
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("start")
    p.add_argument("--agent", required=True)
    p.add_argument("--goal", default="")
    p = sub.add_parser("step")
    p.add_argument("--run", required=True)
    p.add_argument("--text", default="")
    p.add_argument("--status", default="ok")
    p = sub.add_parser("finish")
    p.add_argument("--run", required=True)
    p.add_argument("--status", default="completed")
    p.add_argument("--summary", default="")
    p = sub.add_parser("list")
    p.add_argument("--agent", default=None)
    p = sub.add_parser("show")
    p.add_argument("--run", required=True)
    p.add_argument("--tail", type=int, default=10)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else DEFAULT_ROOT
    if args.cmd == "start":
        return cmd_start(root, args)
    if args.cmd == "step":
        return cmd_step(root, args)
    if args.cmd == "finish":
        return cmd_finish(root, args)
    if args.cmd == "list":
        return cmd_list(root, args)
    return cmd_show(root, args)


def find_root():
    return DEFAULT_ROOT


if __name__ == "__main__":
    sys.exit(main())
