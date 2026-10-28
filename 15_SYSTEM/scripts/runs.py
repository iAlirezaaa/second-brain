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
  python 15_SYSTEM/scripts/runs.py promote --run RUN-... [--dimension domain] [--confidence 0.6]

Everything here lives inside 12_RUNTIME, so it dies at the git boundary by design: runs
are not evidence. When a run matters, promote what it produced to the shelf
(candidates) or the human plane (promote.py) -- knowledge stranded in machine state is
the exact defect this layout exists to prevent.

A run of an actor the registry has never heard of is refused: an unaccounted actor is
how a registry starts lying.
"""
import argparse
import contextlib
import importlib.util
import io
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
    module.REGISTRY_KINDS = None
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


class RunRefused(Exception):
    """A runs-law refusal. The CLI prints it as REFUSED; programmatic callers
    (the backend engine, tests) catch it -- one door, one law, two fronts."""


def start_run(root, actor_id, goal=""):
    """Open a run for a registered actor and return its run dict. The refusal laws:
    an actor the registry never heard of, and a non-actor kind, are both refused."""
    hades = load_hades(root)
    hit = None
    for p, r in hades.iter_records(hades.config()):
        if str(r.get("id")) == str(actor_id):
            hit = (p, r)
            break
    if not hit:
        raise RunRefused("no registry record %s -- a run of an unaccounted actor is how a "
                         "registry starts lying (see `hades.py list --kind agent`)" % actor_id)
    kind = hit[1].get("kind")
    if kind not in ("agent", "subagent"):
        raise RunRefused("%s is a %s record -- runs are started for actors (agent/subagent), "
                         "not for %s" % (actor_id, kind, kind))
    run_id = "RUN-" + uuid.uuid4().hex[:8].upper()
    target = runs_dir(root) / run_id
    target.mkdir(parents=True, exist_ok=True)
    run = {"run_id": run_id, "agent": str(actor_id), "kind": kind,
           "goal": str(goal or ""), "status": "running",
           "started_utc": now_utc(), "ended_utc": "", "steps": 0, "summary": ""}
    save_run(root, run)
    return run


def append_step(root, run_id, status, text):
    """Append one feed line to a RUNNING run and bump its counter; returns the new
    count. A finished run's feed is history, not a place to append."""
    run = load_run(root, run_id)
    if run is None:
        raise RunRefused("no such run %s under %s" % (run_id, runs_dir(root).name))
    if run.get("status") != "running":
        raise RunRefused("run %s is %s -- a finished run's feed is history, not a place to "
                         "append" % (run_id, run.get("status")))
    text = str(text or "").strip()
    if not text:
        raise RunRefused("step needs text (an unnamed step is not a feed entry)")
    status = status if status in ("ok", "fail", "note") else "ok"
    entry = {"utc": now_utc(), "status": status, "text": text}
    with (runs_dir(root) / run_id / "steps.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    run["steps"] = int(run.get("steps") or 0) + 1
    save_run(root, run)
    return run["steps"]


def close_run(root, run_id, status, summary=""):
    """Finish a run once: completed|failed only. Raises RunRefused on repeat finishes."""
    run = load_run(root, run_id)
    if run is None:
        raise RunRefused("no such run %s" % run_id)
    if run.get("status") != "running":
        raise RunRefused("run %s is already %s -- finishing twice is a second truth"
                         % (run_id, run.get("status")))
    if status not in ("completed", "failed"):
        raise RunRefused("finish wants completed|failed (a run ends in one of two "
                         "states, like its evidence or its excuse)")
    run["status"] = status
    run["ended_utc"] = now_utc()
    if summary:
        run["summary"] = str(summary)
    save_run(root, run)
    return run


def cmd_start(root, args):
    try:
        run = start_run(root, args.agent, goal=args.goal)
    except RunRefused as refused:
        print("REFUSED: %s" % refused)
        return 2
    print("RUN %s started | actor %s (%s) | goal: %s" % (run["run_id"], run["agent"],
                                                         run["kind"], run["goal"]))
    print("append steps:  runs.py step --run %s --text \"...\"" % run["run_id"])
    print("close it:      runs.py finish --run %s --status completed|failed" % run["run_id"])
    return 0


def cmd_step(root, args):
    try:
        count = append_step(root, args.run, args.status, args.text)
    except RunRefused as refused:
        print("REFUSED: %s" % refused)
        return 2
    status = args.status if args.status in ("ok", "fail", "note") else "ok"
    print("STEP %s #%d [%s] %s" % (args.run, count, status, str(args.text or "").strip()))
    return 0


def cmd_finish(root, args):
    try:
        run = close_run(root, args.run, args.status, summary=args.summary)
    except RunRefused as refused:
        print("REFUSED: %s" % refused)
        return 2
    print("RUN %s %s | steps: %d | summary: %s"
          % (args.run, run["status"], run["steps"], run["summary"] or "(none)"))
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


PROMOTED_ROW = """---
id: {cid}
type: note
title: 'Loop candidate: an agent run left the disposable plane'
status: raw
owner: agent
topics: [agent-runs, promotion]
created: {today}
updated: {today}
dimension: {dimension}
cue: {cue}
lesson: {lesson}
confidence: {confidence}
verdict: proposed
evidence:
{evidence}
---

# {cid}

**Promoted from `12_RUNTIME/agent_runs/{run_id}` by `runs.py promote`, {today}.**
The run directory is disposable by law (it dies at the git boundary), so the feed is
**embedded here** -- evidence is exported, never cited across the boundary.

- actor: `{agent}` ({kind}, registry record)
- goal: {goal}
- outcome: {status}, {steps} step(s), started {started_utc}, ended {ended_utc}

Feed:

{feed_lines}

This row is a proposal, not a decision: `verdict: proposed` is legal on the shelf and
never promotable. The human reviews, probes and disposes it.
"""


def read_feed(run_id_path):
    feed = run_id_path / "steps.jsonl"
    if not feed.is_file():
        return []
    rows = []
    for line in feed.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def cmd_promote(root, args):
    """Export a finished run's feed into a registered shelf row.

    12_RUNTIME is behind the git boundary, so a run directory can never be evidence --
    the row EMBEDS the feed and cites only tracked files. A run still running has not
    earned a verdict; an empty feed has nothing to say; promoting twice is a second
    truth.
    """
    sys.path.insert(0, str(SRC.parents[1] / "scripts"))
    import candidate_check
    run = load_run(root, args.run)
    if run is None:
        print("REFUSED: no such run %s" % args.run)
        return 2
    if run.get("status") == "running":
        print("REFUSED: run %s is still running -- finish it first (completed|failed); "
              "a run without a verdict has not earned a proposal" % args.run)
        return 2
    if run.get("promoted"):
        print("REFUSED: run %s already promoted %s -- promoting twice is a second truth"
              % (args.run, run["promoted"]))
        return 2
    feed = read_feed(runs_dir(root) / args.run)
    if not feed:
        print("REFUSED: run %s has an empty feed -- an unnamed run has nothing to "
              "promote; write the steps first" % args.run)
        return 2
    dimension = args.dimension if args.dimension in ("invariant", "domain") else "domain"
    try:
        confidence = float(args.confidence if args.confidence is not None else 0.6)
    except (TypeError, ValueError):
        print("REFUSED: confidence must be a number in 0..1")
        return 2
    if not (0.0 <= confidence <= 1.0):
        print("REFUSED: confidence must be in 0..1, got %s" % confidence)
        return 2
    # evidence points only at tracked files: the actor record and the tool itself
    evidence = ["15_SYSTEM/scripts/runs.py"]
    hades = load_hades(root)
    for p, r in hades.iter_records(hades.config()):
        if str(r.get("id")) == str(run.get("agent")):
            evidence.insert(0, hades.rel(p))
            break
    shelf = root / "14_CANDIDATES" / "loop"
    shelf.mkdir(parents=True, exist_ok=True)
    today = now_utc()[:10]
    seq = 1 + len(list(shelf.glob("cand-%s-run-*.md" % today)))
    cid = "cand-%s-run-%02d" % (today, seq)
    if (shelf / (cid + ".md")).exists():
        print("REFUSED: row id %s already exists -- refusing to overwrite a proposal" % cid)
        return 2
    cue = run.get("goal") or "run %s of %s" % (args.run, run.get("agent"))
    lesson = "; ".join("step %d [%s]: %s" % (i, s.get("status"), s.get("text"))
                       for i, s in enumerate(feed, 1))
    lesson = " ".join(str(lesson).split())[:900]
    feed_lines = "\n".join("  %d. `%s` [%s] %s" % (i, s.get("utc"), s.get("status"), s.get("text"))
                           for i, s in enumerate(feed, 1))
    row = PROMOTED_ROW.format(cid=cid, today=today, dimension=dimension, cue=cue,
                              lesson=lesson, confidence=confidence,
                              evidence="\n".join("  - %s" % e for e in evidence),
                              run_id=args.run, agent=run.get("agent"), kind=run.get("kind"),
                              goal=run.get("goal") or "(none)", status=run.get("status"),
                              steps=run.get("steps"), started_utc=run.get("started_utc"),
                              ended_utc=run.get("ended_utc") or "(still open?)",
                              feed_lines=feed_lines)
    path = shelf / (cid + ".md")
    path.write_text(row, encoding="utf-8")
    with contextlib.redirect_stdout(io.StringIO()):
        rc = candidate_check.register(root, str(path))
    if rc != 0:
        print("REFUSED: the row was written but the ledger refused it -- the shelf is out "
              "of balance; a human should look before anything else happens")
        return 2
    run["promoted"] = cid
    save_run(root, run)
    print("PROMOTED %s -> %s (registered in the ledger; a human decides)" % (cid, path))
    print("the feed is embedded in the row; the run dir stays disposable")
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
    p = sub.add_parser("promote")
    p.add_argument("--run", required=True)
    p.add_argument("--dimension", default="domain")
    p.add_argument("--confidence", default=None)
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
    if args.cmd == "promote":
        return cmd_promote(root, args)
    return cmd_show(root, args)


def find_root():
    return DEFAULT_ROOT


if __name__ == "__main__":
    sys.exit(main())
