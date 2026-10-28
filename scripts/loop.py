#!/usr/bin/env python
"""Continuous improvement loop — one cycle per run (ratchet, not treadmill).

Usage:
  python scripts/loop.py [--vault path] [--no-tests] [--root path]
  python scripts/loop.py --due [--target scripts/loop.py] [--now ISO] [--last-run ISO]

A cycle:
  1. Collects improvement signals: integrity failures, test failures,
     knowledge gaps, stale inbox items, proposals awaiting approval,
     hygiene debt (TODO/FIXME), orphan notes.
  2. Compares against the previous run (ratchet: regressions are loud,
     improvements are counted).
  3. Writes a candidate report the HUMAN promotes or rejects.
     (machine plane output -> 14_CANDIDATES/loop/, never edits the human plane)

Whether a cycle is *due* is not decided here: it is a registry record
(`11_CONTROL/schedules/*.json`, kind `schedule`) and the pure due-math in
`15_SYSTEM/scripts/backend/schedules.py`. The cron in .github/workflows/loop.yml
is the alarm; the record is the rule.
"""
import argparse
import datetime
import glob
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import candidate_check
from common import (DATE_RE, clone_readable, find_root, iter_markdown, load_json,
                   parse_frontmatter, run_utf8, state_fingerprint)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BACKEND_SCRIPTS = Path(__file__).parent.parent / "15_SYSTEM" / "scripts"
SCHEDULE_DIR = "11_CONTROL/schedules"
HISTORY = Path("14_CANDIDATES") / "loop" / "history.json"
SCHEDULE_KIND = "schedule"

TODO_RE = re.compile(r"\b(TODO|FIXME|XXX)\b", re.IGNORECASE)


def _schedules():
    """The one due-math in the house. Imported, never re-implemented here."""
    if str(BACKEND_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(BACKEND_SCRIPTS))
    from backend import schedules
    return schedules


def schedule_record(root, target):
    """(record, path) for the schedule that governs `target`; (None, None) when absent.

    A registry record is the rule. `target` is the thing being governed, not a copy of
    the cadence: two files that both spell "daily at 02:00" would be two clocks again.
    """
    folder = Path(root) / SCHEDULE_DIR
    for path in sorted(folder.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(record, dict) and record.get("kind") == SCHEDULE_KIND \
                and record.get("target") == target:
            return record, path
    return None, None


def last_cycle(root):
    """When the loop last ran, ISO UTC. Rows written before `ran_at` existed carry only
    a date, which is read as that day's midnight — coarse, and true to what was recorded."""
    path = Path(root) / HISTORY
    if not path.is_file():
        return None
    try:
        runs = json.loads(path.read_text(encoding="utf-8")).get("runs", [])
    except (OSError, ValueError):
        return None
    stamps = [str(run.get("ran_at") or (str(run.get("date")) + "T00:00:00Z"))
              for run in runs
              if run.get("ran_at") or DATE_RE.match(str(run.get("date") or ""))]
    return max(stamps) if stamps else None


def due_state(root, target="scripts/loop.py", now=None, last_run=None):
    """Ask the governed schedule whether `target` is due.

    `due` is True or False; it is None only when the question itself is malformed (no
    record, or a spec the backend refuses). A refused schedule is reported, never guessed:
    "I could not read the rule" is not the same answer as "run it".
    """
    record, path = schedule_record(root, target)
    if record is None:
        return {"due": None, "target": target, "reason":
                "no schedule record governs %r — nothing in the registry says when it is due"
                % target}
    if record.get("status") != "active":
        return {"due": False, "target": target, "record": path, "last_run": last_run,
                "reason": "the schedule is %s" % record.get("status")}
    try:
        sched = _schedules()
        now_dt = sched.parse_utc(now) if now else \
            datetime.datetime.now(datetime.timezone.utc)
        return {"due": sched.is_due(record.get("spec"), last_run, now_dt),
                "target": target, "record": path, "spec": record.get("spec"),
                "last_run": last_run, "now": sched.fmt_utc(now_dt),
                "next": sched.next_run_after(record.get("spec"), now_dt)}
    except (TypeError, ValueError) as exc:
        return {"due": None, "target": target, "record": path,
                "reason": "this schedule cannot be read: %s" % exc}


def report_due(root, target, now=None, last_run=None):
    """Print the verdict; 0 = due, 3 = not due, 1 = refused. Cron is the alarm, this is the rule."""
    derived = last_run is None
    state = due_state(root, target, now, last_cycle(root) if derived else (last_run or None))
    if state["due"] is None:
        print("REFUSED — %s: %s" % (state["target"], state["reason"]))
        return 1
    record = ""
    if state.get("record") is not None:
        try:
            record = " [%s]" % Path(state["record"]).relative_to(root).as_posix()
        except ValueError:
            record = " [%s]" % state["record"]
    was = ("never ran" if derived and state["last_run"] is None
           else "last run %s" % state["last_run"])
    if state["due"]:
        print("DUE — %s under %s%s; %s; next run after %s was %s"
              % (state["target"], state.get("spec"), record, was, state["now"], state["next"]))
        return 0
    print("NOT DUE — %s under %s%s; %s; next run %s%s"
          % (state["target"], state.get("spec"), record, was, state["next"],
             "" if state.get("reason") is None else " (%s)" % state["reason"]))
    return 3


def run_health(script, vault_args):
    result = run_utf8([sys.executable, str(Path(__file__).parent / script)] + vault_args)
    problems = [line for line in result.stdout.splitlines()
                if line.startswith(("BROKEN", "INVALID", "missing", "bad date", "invalid "))]
    return {"script": script, "returncode": result.returncode, "problems": problems[:10]}


def run_tests():
    result = run_utf8([sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    tail = result.stderr.strip().splitlines()
    summary = next((line for line in reversed(tail) if line.startswith("Ran ") or
                    line in ("OK", "FAILED")), "no summary")
    return {"returncode": result.returncode, "summary": summary}


def vault_signals(vault, proposals_glob):
    signals = {"stale_inbox": [], "orphans": [], "awaiting_approval": [], "inbox_status_lived": 0}
    zones = None
    rules = Path(__file__).parent.parent / "rules" / "zones.json"
    if rules.is_file():
        zones = set(json.loads(rules.read_text(encoding="utf-8"))["zones"])
    for path in iter_markdown(vault):
        rel = path.relative_to(vault).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = parse_frontmatter(text)
        in_zone = next((p for p in rel.split("/")[:-1] if zones and p in zones), None)
        if not in_zone and not rel.startswith(("_", ".")) and path.name not in ("AGENTS.md", "CLAUDE.md", "index.md"):
            signals["orphans"].append(rel)
        if "00_Inbox/" in rel:
            signals["inbox_status_lived"] += 1
            updated = str(fm.get("updated") or "")
            if DATE_RE.match(updated) and updated < (datetime.date.today() -
                                                     datetime.timedelta(days=14)).isoformat():
                signals["stale_inbox"].append(rel)
    for proposal_file in glob.glob(proposals_glob):
        try:
            data = json.loads(Path(proposal_file).read_text(encoding="utf-8"))
            for proposal in data.get("proposals", []):
                if not proposal.get("approved"):
                    signals["awaiting_approval"].append(
                        f"{Path(proposal_file).name}:{proposal.get('capture', '?')}")
        except (json.JSONDecodeError, OSError):
            signals["awaiting_approval"].append(f"{Path(proposal_file).name}: UNREADABLE")
    return signals


def kb_gaps(root, limit=5):
    """Unanswered searches, and a tracked copy of them a reader somewhere else can open.

    The register itself is a table inside `.kb/kb.sqlite`, which is gitignored state. A
    candidate that cites it rests on a file that exists only on the machine that ran the
    loop -- so the loop exports the rows it read beside the report it wrote.
    """
    out = {"open": 0, "recent": [], "note": "no .kb index anywhere — ingest first",
           "snapshot": ""}
    db = root / ".kb" / "kb.sqlite" if (root / ".kb" / "kb.sqlite").is_file() else None
    if db is None:
        return out
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT query, logged FROM search_gaps ORDER BY logged DESC").fetchall()
    conn.close()
    out["open"] = len(rows)
    out["note"] = "%d unanswered search(es)" % len(rows)
    out["recent"] = ["%s (%s)" % (q, d) for q, d in rows[:limit]]
    if rows:
        shelf = root / "14_CANDIDATES" / "loop"
        shelf.mkdir(parents=True, exist_ok=True)
        (shelf / "gaps.jsonl").write_text(
            "".join(json.dumps({"query": q, "logged": d}, ensure_ascii=False) + "\n"
                    for q, d in rows), encoding="utf-8")
        out["snapshot"] = "14_CANDIDATES/loop/gaps.jsonl"
    return out


def hygiene(root):
    debt = 0
    files_scanned = 0
    for pattern in ["scripts/*.py", "skills/**/SKILL.md"]:
        for path in glob.glob(str(root / pattern), recursive=True):
            files_scanned += 1
            text = Path(path).read_text(encoding="utf-8", errors="replace")
            debt += len(TODO_RE.findall(text))
    return {"todo_hygiene": debt, "files_scanned": files_scanned}


def build_metrics(root, vault, do_tests, proposals_glob):
    vault_args = ["--vault", str(vault)]
    metrics = {
        "link_check": run_health("link_check.py", vault_args),
        "frontmatter_check": run_health("frontmatter_check.py", vault_args),
        "vault": vault_signals(vault, proposals_glob),
        "kb_gaps": kb_gaps(root),
        "hygiene": hygiene(root),
    }
    metrics["tests"] = run_tests() if do_tests else {"returncode": None, "summary": "skipped"}
    return metrics


def ratchet(metrics, history_path):
    """Compare against last recorded run; flag regressions loudly."""
    previous = None
    history = {"reads_the_past": True, "runs": []}
    if history_path.is_file():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
            history.setdefault("runs", [])
            if history["runs"]:
                previous = history["runs"][-1].get("metrics")
        except json.JSONDecodeError:
            previous = None
    verdicts = {}
    if previous:
        def count_health(m):
            return len(m["link_check"]["problems"]) + len(m["frontmatter_check"]["problems"])
        pairs = {
            "integrity_problems": (count_health(previous), count_health(metrics)),
            "stale_inbox": (len(previous["vault"]["stale_inbox"]), len(metrics["vault"]["stale_inbox"])),
            "awaiting_approval": (len(previous["vault"]["awaiting_approval"]),
                                  len(metrics["vault"]["awaiting_approval"])),
            "guided_gaps": (previous["kb_gaps"].get("open", 0), metrics["kb_gaps"].get("open", 0)),
            "hygiene_todo": (previous["hygiene"]["todo_hygiene"], metrics["hygiene"]["todo_hygiene"]),
        }
        for name, (before, after) in pairs.items():
            if after > before:
                verdicts[name] = f"REGRESSED {before} -> {after}"
            elif after < before:
                verdicts[name] = f"improved {before} -> {after}"
            else:
                verdicts[name] = f"stable at {after}"
    history["runs"].append({"date": datetime.date.today().isoformat(),
                            "ran_at": datetime.datetime.now(datetime.timezone.utc)
                                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
                            "metrics": metrics})
    history_path.write_text(json.dumps(history, indent=1, default=str), encoding="utf-8")
    return verdicts


def candidates(metrics, verdicts):
    """Typed shelf rows, not free text: dimension/cue/lesson/evidence/confidence/verdict.

    Every row states the signal that produced it as evidence a reader can open, so
    scripts/candidate_check.py can judge it and scripts/promote.py can refuse it. A row
    the loop writes carries `verdict: proposed` -- naming a change is not measuring it.
    """
    out = []
    for check in ("link_check", "frontmatter_check"):
        health = metrics[check]
        if health["returncode"] != 0 or health["problems"]:
            out.append({
                "priority": "P1", "dimension": "domain",
                "cue": "the %s gate reports problems in the vault" % check,
                "lesson": "fix the %d integrity problem(s) before anything else ships"
                          % len(health["problems"]),
                "evidence": ["vault-template"],
                "detail": health["problems"][:3],
                "confidence": 0.95,
            })
    if metrics["tests"]["returncode"] not in (0, None):
        out.append({
            "priority": "P1", "dimension": "invariant",
            "cue": "the test suite is red",
            "lesson": "run python -m unittest discover -s tests, fix the first failure, "
                      "re-run; never silence a test to make the house look green",
            "evidence": ["tests/"],
            "detail": ["probe: %s" % metrics["tests"]["summary"]],
            "confidence": 0.9,
        })
    if metrics["vault"]["awaiting_approval"]:
        waiting = metrics["vault"]["awaiting_approval"]
        out.append({
            "priority": "P2", "dimension": "domain",
            "cue": "proposals are sitting in the queue with no decision on them",
            "lesson": "ask the human for one verdict per proposal, then run scripts/promote.py "
                      "on the approved ones",
            "evidence": ["vault-template/90_Agent_Output/proposals/"],
            "detail": waiting[:3],
            "confidence": 0.7,
        })
    if metrics["vault"]["stale_inbox"]:
        stale = metrics["vault"]["stale_inbox"]
        out.append({
            "priority": "P3", "dimension": "domain",
            "cue": "inbox items have not been touched in 14+ days",
            "lesson": "promote, merge or delete each one -- an inbox that ages is a filing "
                      "system nobody trusts",
            "evidence": [], "detail": stale[:3],
            "confidence": 0.6,
        })
    if metrics["kb_gaps"].get("open"):
        out.append({
            "priority": "P2", "dimension": "domain",
            "cue": "a search in the index returned nothing",
            "lesson": "write the note the search asked for; an unanswered query is the "
                      "brain telling you what it is missing",
            "evidence": [snapshot for snapshot in
                         [metrics["kb_gaps"].get("snapshot")] if snapshot],
            "detail": metrics["kb_gaps"]["recent"],
            "confidence": 0.65,
        })
    if metrics["hygiene"]["todo_hygiene"]:
        out.append({
            "priority": "P3", "dimension": "invariant",
            "cue": "scripts and skills carry raw TODO/FIXME markers",
            "lesson": "each marker becomes a candidate row with a probe or gets deleted -- "
                      "a TODO nobody can measure is a wish",
            "evidence": ["scripts/", "skills/"],
            "detail": ["%d marker(s) in %d file(s)" % (metrics["hygiene"]["todo_hygiene"],
                                                       metrics["hygiene"]["files_scanned"])],
            "confidence": 0.55,
        })
    return out


def open_cues(shelf):
    """Cues already on the shelf -- proposing the same signal twice is noise, not a ratchet.

    A row that was adopted or dropped stops blocking its cue; a row still being revised, or
    answered with keep_base, does. keep_base is a standing answer, so the signal stays closed
    until the number behind it changes.
    """
    cues = set()
    events, _ = candidate_check.read_ledger(shelf)
    closed = {"adopt", "drop"}
    decided = {cid for cid, row in candidate_check.ledger_state(events).items()
               if row["dispositions"] and set(row["dispositions"]) <= closed}
    for path in sorted(shelf.glob("cand-*.md")):
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        cid = str(fm.get("id") or path.stem)
        if cid in decided:
            continue
        cue = str(fm.get("cue") or "").strip()
        if cue:
            cues.add(cue)
    return cues


def row_text(cid, today, row, evidence):
    lines = [
        "---",
        "id: %s" % cid,
        "type: note",
        "title: 'Loop candidate: %s'" % row["priority"],
        "status: raw",
        "owner: agent",
        "topics: [loop, improvement]",
        "created: %s" % today,
        "updated: %s" % today,
        "dimension: %s" % row["dimension"],
        "cue: %s" % row["cue"],
        "lesson: %s" % row["lesson"],
        "confidence: %s" % row["confidence"],
        "verdict: proposed",
        "evidence:",
    ]
    lines += ["  - %s" % item for item in evidence]
    lines += ["---", "", "# %s" % cid, "",
              "**%s — %s.** %s" % (row["priority"], row["dimension"], row["lesson"]), "",
              "Signal this row was raised from:"]
    lines += ["- %s" % detail for detail in row.get("detail", [])]
    rel = "14_CANDIDATES/loop/%s.md" % cid
    lines += ["", "To take it: set `probe:` to the command that would measure this and edit the",
              "verdict to what a real run supports, then run",
              "`python scripts/probe.py --candidate %s`," % rel,
              "`python scripts/candidate_check.py --file %s`," % rel,
              "and `python scripts/promote.py` once the row is promotable.",
              "To set it down: `python scripts/loop.py --dispose %s drop --note why`." % cid, ""]
    return "\n".join(lines)


def plan_ids(root, rows, today, cycle):
    """Give each row a unique id; skip the ones already open on the shelf."""
    shelf = root / "14_CANDIDATES" / "loop"
    already = open_cues(shelf)
    planned, skipped = [], []
    for index, row in enumerate(rows, 1):
        cid = "cand-%s-c%d-%02d" % (today, cycle, index)
        if row["cue"] in already or (shelf / ("%s.md" % cid)).is_file():
            skipped.append((cid, row))
            continue
        planned.append((cid, row))
    return planned, skipped


def write_rows(root, planned, report_rel, today):
    """One file per row plus one ledger event per file -- the shelf is countable or it is prose."""
    shelf = root / "14_CANDIDATES" / "loop"
    shelf.mkdir(parents=True, exist_ok=True)
    written = []
    for cid, row in planned:
        # exists-here is not readable-there: a row that cites a gitignored artifact passes
        # every check on the machine that wrote it and turns CI red in a fresh clone.
        evidence = [report_rel] + [item for item in row["evidence"]
                                   if item and clone_readable(item) and (root / item).exists()]
        (shelf / ("%s.md" % cid)).write_text(row_text(cid, today, row, evidence), encoding="utf-8")
        candidate_check.append_event(shelf, {
            "date": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "id": cid, "event": "proposed", "priority": row["priority"],
            "dimension": row["dimension"], "cue": row["cue"]})
        written.append((cid, row))
    return written


def dispose(root, cid, label, note):
    """Record a human decision against a row the ledger proposed."""
    shelf = root / "14_CANDIDATES" / "loop"
    events, _ = candidate_check.read_ledger(shelf)
    state = candidate_check.ledger_state(events)
    if label not in candidate_check.DISPOSITIONS:
        print("REFUSED  disposition %r is not one of %s"
              % (label, list(candidate_check.DISPOSITIONS)))
        return 1
    if label == "adopt":
        print("REFUSED  adopt is not typed, it is done: python scripts/promote.py moves the row "
              "and records the disposition itself")
        return 1
    row = state.get(cid)
    if not row or not row["proposed"]:
        print("REFUSED  the ledger never proposed %s — a decision needs a row to be about" % cid)
        return 1
    if row["dispositions"]:
        print("REFUSED  %s is already %s — supersede it with a new row instead of re-deciding"
              % (cid, "/".join(row["dispositions"])))
        return 1
    path = shelf / ("%s.md" % cid)
    candidate_check.append_event(shelf, {
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "id": cid, "event": "disposition", "disposition": label, "note": note or ""})
    if label == "drop" and path.is_file():
        path.unlink()  # dropped means off the shelf; the ledger keeps the reason
    problems, identity = candidate_check.ledger_problems(root, shelf,
                                                         candidate_check.shelf_candidates(
                                                             root, "14_CANDIDATES/loop"))
    for problem in problems:
        print("INVALID  %s" % problem)
    print("DISPOSED %s -> %s | proposed=%d decided=%d open=%d (adopt=%d revise=%d drop=%d "
          "keep_base=%d)" % (cid, label, identity["proposed"], identity["decided"],
                             identity["open"], identity["adopt"], identity["revise"],
                             identity["drop"], identity["keep_base"]))
    if problems:
        return 1
    if label in ("revise", "keep_base"):
        print("KEPT     %s stays on the shelf — %s" % (cid, path.relative_to(root).as_posix()
                                                       if path.is_file() else "the row is gone"))
    return 0


def ledger_section(shelf):
    """The shelf's own arithmetic, printed into every report: a count the reader can re-derive."""
    root = Path(shelf).parents[1]
    events, broken = candidate_check.read_ledger(shelf)
    problems, identity = candidate_check.ledger_problems(
        root, shelf, candidate_check.shelf_candidates(root, "14_CANDIDATES/loop"))
    lines = ["\n## Ledger (count identity)\n"]
    lines.append("- proposed=%d = adopt=%d + revise=%d + drop=%d + keep_base=%d + open=%d"
                 % (identity["proposed"], identity["adopt"], identity["revise"], identity["drop"],
                    identity["keep_base"], identity["open"]))
    lines += ["- INVALID %s" % problem for problem in problems + broken]
    if len(lines) == 2:
        lines.append("- every row the loop raised either has a disposition or is still on the shelf")
    return lines


def write_report(root, metrics, verdicts, planned, skipped, cycle):
    today = datetime.date.today().isoformat()
    loop_dir = root / "14_CANDIDATES" / "loop"
    loop_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if cycle == 1 else f"-c{cycle}"
    report_path = loop_dir / f"report-{today}{suffix}.md"
    lines = [
        "---\nid: cand-%s-loop%s" % (today, suffix.strip("-")),
        "type: note", "title: Improvement loop report",
        "status: raw", "owner: agent", "topics: [loop, improvement]",
        "created: %s" % today, "updated: %s" % today, "---\n",
        "# Improvement loop — %s (cycle %d)" % (today, cycle),
        "*Machine candidate shelf — nothing here changed the vault. Promote or reject.*\n",
        "## Health signals\n",
        "- tests: %s (rc=%s)" % (metrics["tests"]["summary"], metrics["tests"]["returncode"]),
        "- link_check: rc=%s problems=%s" % (metrics["link_check"]["returncode"],
                                             len(metrics["link_check"]["problems"])),
        "- frontmatter_check: rc=%s problems=%s" % (metrics["frontmatter_check"]["returncode"],
                                                    len(metrics["frontmatter_check"]["problems"])),
        "- hygiene: %s TODO markers in %s files" % (metrics["hygiene"]["todo_hygiene"],
                                                    metrics["hygiene"]["files_scanned"]),
    ]
    lines.append("\n## Ratchet (vs previous run)\n")
    if verdicts:
        lines += ["- %s: %s" % (name, result) for name, result in sorted(verdicts.items())]
    else:
        lines.append("- first recorded run — baseline set")
    lines.append("\n## Candidate rows written this cycle\n")
    if planned:
        for cid, row in planned:
            lines.append("- **%s** `%s` (%s) — %s" % (row["priority"], cid, row["dimension"],
                                                      row["cue"]))
            lines.append("  - lesson: %s" % row["lesson"])
            lines.append("  - confidence: %s | verdict: proposed" % row["confidence"])
    else:
        lines.append("- none: house is quiet, or every signal already has a row on the shelf.")
    if skipped:
        lines.append("\n## Already open (not proposed twice)\n")
        lines += ["- `%s` — %s" % (cid, row["cue"]) for cid, row in skipped]
    lines += ledger_section(loop_dir)
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def contract_problems(root):
    """Judge the shelf the way health.py will, before this cycle is called done.

    Returns None when the repo has no contract file (a fixture root, a partial clone):
    the loop must not invent a failure for a fence that is simply not installed here.
    """
    schema_path = root / "rules" / "candidate.schema.json"
    if not schema_path.is_file():
        return None
    schema = load_json(schema_path)
    shelf = root / "14_CANDIDATES" / "loop"
    targets = candidate_check.shelf_candidates(root, shelf.relative_to(root).as_posix())
    digest = state_fingerprint(root)
    problems = [problem for path in targets for problem in
                candidate_check.check_candidate(path, schema, root, digest,
                                                candidate_check.probe_index(root))]
    ledger, _identity = candidate_check.ledger_problems(root, shelf, targets)
    return problems + ledger


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None)
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--no-tests", action="store_true")
    parser.add_argument("--dispose", metavar=("CANDIDATE_ID", "LABEL"), nargs=2, default=None,
                        help="record a decision: --dispose cand-2026-10-27-c1-01 drop --note why")
    parser.add_argument("--note", default="", help="why, in one line")
    parser.add_argument("--due", action="store_true",
                        help="ask the governed schedule whether a cycle is due; writes nothing")
    parser.add_argument("--target", default="scripts/loop.py",
                        help="the thing whose schedule record to read (with --due)")
    parser.add_argument("--now", default=None, help="UTC ISO override for the due check (tests)")
    parser.add_argument("--last-run", default=None,
                        help="UTC ISO last run; an empty value means 'never ran' (tests/rituals)")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    if args.due:
        return report_due(root, args.target, args.now, args.last_run)
    if args.dispose:
        return dispose(root, args.dispose[0], args.dispose[1], args.note)
    vault = Path(args.vault) if args.vault else root / "vault-template"
    if not vault.is_dir():
        print(f"vault not found: {vault}")
        return 1
    proposals_glob = str(vault / "90_Agent_Output" / "proposals" / "*.json")
    history_path = root / "14_CANDIDATES" / "loop" / "history.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)
    cycle = 1
    if history_path.is_file():
        try:
            today = datetime.date.today().isoformat()
            cycle = sum(1 for run in json.loads(history_path.read_text(encoding="utf-8")).get("runs", [])
                        if str(run.get("date")) == today) + 1
        except (json.JSONDecodeError, KeyError):
            cycle = 1
    metrics = build_metrics(root, vault, not args.no_tests, proposals_glob)
    verdicts = ratchet(metrics, history_path)
    today = datetime.date.today().isoformat()
    planned, skipped = plan_ids(root, candidates(metrics, verdicts), today, cycle)
    report_path = write_report(root, metrics, verdicts, planned, skipped, cycle)
    write_rows(root, planned, report_path.relative_to(root).as_posix(), today)
    contract = contract_problems(root)
    red_house = any(metrics[check]["returncode"] != 0 or metrics[check]["problems"]
                    for check in ("link_check", "frontmatter_check"))
    red_house = red_house or metrics["tests"]["returncode"] not in (0, None)
    broken_contract = bool(contract)
    print("cycle %d — report: %s" % (cycle, report_path.relative_to(root).as_posix()))
    for cid, row in planned:
        print("%s: %s [%s]" % (row["priority"], row["cue"], cid))
    for skipped_cid, row in skipped:
        print("already open: %s [%s]" % (row["cue"], skipped_cid))
    for problem in (contract or []):
        print("INVALID  %s" % problem)
    if broken_contract:
        print("REFUSED: the shelf does not meet rules/candidate.schema.json — a proposal "
              "that cannot be judged is not a proposal")
    return 1 if (red_house or broken_contract) else 0


if __name__ == "__main__":
    sys.exit(main())
