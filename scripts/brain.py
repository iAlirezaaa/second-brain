#!/usr/bin/env python3
"""Brain CLI vNext: private, auditable agent sessions (Python 3.9+, stdlib).

This is a human-invoked coordination kernel, not a shell agent. It cannot execute
tasks, approve itself, send data to models or silently publish a skill.
"""
import argparse
import json
import re
import sqlite3
import sys
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

STEPS = (
    ("skills", "Inspect available skills and select reusable procedures"),
    ("plan", "Write task breakdown, success criteria and risk limits"),
    ("work", "Execute approved, bounded work; add newly discovered tasks"),
    ("verify", "Verify results with reproducible evidence"),
    ("handoff", "Write handoff and a draft skill proposal"),
)
HUMAN_ZONES = ("01_INBOX", "02_WIKI", "03_PROJECTS", "04_INTELLIGENCE",
               "05_WORKS", "06_CHANNELS", "07_PRODUCTS", "08_LEARNING")
TOKEN = re.compile(r"(?u)\b\w{2,}\b")
MAX_TASKS = 256
MAX_SCAN_FILES = 300


class Refused(ValueError):
    pass


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def require_text(text, label, limit=2000):
    if not isinstance(text, str) or not text.strip() or len(text) > limit:
        raise Refused("%s must contain 1-%d characters" % (label, limit))
    return text.strip()


def _storage(root, create=False):
    base = Path(root) / ".brain-data"
    directory = base / "operator"
    for item in (base, directory):
        if item.is_symlink():
            raise Refused("private storage cannot be a symlink")
    if create:
        directory.mkdir(parents=True, exist_ok=True)
    return directory / "sessions.sqlite3"


def connect(root, create=False):
    db = _storage(root, create=create)
    if not create and not db.is_file():
        raise Refused("no sessions yet; run 'brain start' first")
    if db.is_symlink():
        raise Refused("database cannot be a symlink")
    if create:
        conn = sqlite3.connect(str(db), timeout=5)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
              id TEXT PRIMARY KEY, actor TEXT NOT NULL, goal TEXT NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('active','closed')),
              opened_at TEXT NOT NULL, closed_at TEXT, outcome TEXT,
              handoff TEXT, skills_snapshot TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS tasks (
              id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
              category TEXT NOT NULL, summary TEXT NOT NULL,
              state TEXT NOT NULL CHECK(state IN ('todo','done')),
              evidence TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
              FOREIGN KEY(session_id) REFERENCES sessions(id));
            CREATE TABLE IF NOT EXISTS events (
              id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
              kind TEXT NOT NULL, details TEXT NOT NULL, at TEXT NOT NULL);
        """)
    else:
        conn = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True, timeout=5)
        conn.execute("PRAGMA query_only=ON")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def event(conn, sid, kind, details):
    conn.execute("INSERT INTO events(session_id,kind,details,at) VALUES(?,?,?,?)",
                 (sid, kind, json.dumps(details, ensure_ascii=False, sort_keys=True), now()))


def skills(root, query=""):
    folder = Path(root) / "skills"
    words = set(TOKEN.findall(query.casefold()))
    result = []
    if not folder.is_dir() or folder.is_symlink():
        return result
    for file in sorted(folder.glob("*/SKILL.md")):
        if file.is_symlink() or file.parent.is_symlink():
            continue
        try:
            head = file.read_text(encoding="utf-8")[:3000]
        except OSError:
            continue
        name = re.search(r"(?m)^name:\s*(.+)$", head)
        desc = re.search(r"(?m)^description:\s*(.+)$", head)
        title = name.group(1).strip() if name else file.parent.name
        description = desc.group(1).strip() if desc else ""
        score = len(words.intersection(TOKEN.findall((title + " " + description).casefold())))
        result.append({"name": title, "path": file.relative_to(root).as_posix(),
                       "description": description, "score": score})
    result.sort(key=lambda row: (-row["score"], row["name"]))
    return result


def valid_actor(root, actor):
    if actor == "human":
        return True
    if not re.fullmatch(r"AGT-[0-9A-F]{8}", actor):
        return False
    for path in (Path(root) / "11_CONTROL" / "agents").glob("*/agent.json"):
        try:
            row = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if row.get("id") == actor and row.get("kind") == "agent" and row.get("status") != "deprecated":
            return True
    return False


def start(root, actor, goal):
    goal = require_text(goal, "goal")
    if not valid_actor(root, actor):
        raise Refused("actor must be human or an existing registered AGT-XXXXXXXX agent")
    discovered = skills(root, goal)
    sid = "SES-" + uuid.uuid4().hex[:12].upper()
    with closing(connect(root, create=True)) as conn:
        with conn:
            conn.execute("INSERT INTO sessions VALUES (?,?,?,?,?,?,?,?,?)",
                         (sid, actor, goal, "active", now(), None, None, None,
                          json.dumps(discovered, ensure_ascii=False)))
            for category, summary in STEPS:
                conn.execute("""INSERT INTO tasks(session_id,category,summary,state,evidence,created_at,updated_at)
                                VALUES(?,?,?,'todo',NULL,?,?)""",
                             (sid, category, summary, now(), now()))
            event(conn, sid, "started", {"actor": actor, "skills_found": len(discovered),
                                         "initial_tasks": len(STEPS)})
    return {"session": sid, "state": "active", "goal": goal,
            "suggested_skills": discovered[:5],
            "todo_created": len(STEPS),
            "next": "Review existing skills before doing task work."}


def _session(conn, sid, active=False):
    row = conn.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()
    if row is None:
        raise Refused("unknown session %s" % sid)
    if active and row["state"] != "active":
        raise Refused("session is closed")
    return row


def _tasks(conn, sid):
    return [dict(row) for row in conn.execute(
        "SELECT * FROM tasks WHERE session_id=? ORDER BY id", (sid,))]


def view(root, sid):
    with closing(connect(root)) as conn:
        s = dict(_session(conn, sid))
        items = _tasks(conn, sid)
        return {"session": s["id"], "actor": s["actor"], "goal": s["goal"],
                "state": s["state"], "outcome": s["outcome"],
                "completed": sum(t["state"] == "done" for t in items),
                "total": len(items), "tasks": items,
                "skills_at_start": json.loads(s["skills_snapshot"]),
                "handoff_written": bool(s["handoff"])}


def add(root, sid, summary):
    summary = require_text(summary, "task", 500)
    with closing(connect(root, create=True)) as conn:
        with conn:
            _session(conn, sid, active=True)
            if conn.execute("SELECT count(*) FROM tasks WHERE session_id=?", (sid,)).fetchone()[0] >= MAX_TASKS:
                raise Refused("task limit reached")
            cur = conn.execute("""INSERT INTO tasks(session_id,category,summary,state,evidence,created_at,updated_at)
                                  VALUES(?,'work',?,'todo',NULL,?,?)""",
                               (sid, summary, now(), now()))
            event(conn, sid, "task_added", {"task_id": cur.lastrowid, "summary": summary})
            return {"task_id": cur.lastrowid, "state": "todo", "summary": summary}


def evidence_path(root, raw):
    text = require_text(raw, "evidence path", 600).replace("\\", "/")
    path = Path(text)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise Refused("evidence must be a relative path inside the brain")
    if any(part.startswith(".env") or part in (".secrets", "secrets", "14_CANDIDATES") for part in path.parts):
        raise Refused("secret or quarantined file is not durable evidence")
    candidate = (Path(root) / path).resolve()
    canonical = Path(root).resolve()
    if canonical not in candidate.parents or not candidate.is_file():
        raise Refused("evidence file does not exist inside the brain")
    if any(part in (".brain-data", ".kb", ".git", ".secrets", "12_RUNTIME", "13_LAB")
           for part in path.parts):
        raise Refused("private or disposable files cannot be shared as durable evidence")
    return path.as_posix()


def finish(root, sid, task_id, evidence):
    path = evidence_path(root, evidence)
    with closing(connect(root, create=True)) as conn:
        with conn:
            _session(conn, sid, active=True)
            task = conn.execute("SELECT * FROM tasks WHERE id=? AND session_id=?",
                                (task_id, sid)).fetchone()
            if not task or task["state"] != "todo":
                raise Refused("task not found or already completed")
            if task["category"] in ("work", "verify", "handoff"):
                blocking = conn.execute("""SELECT category FROM tasks
                    WHERE session_id=? AND category IN ('skills','plan') AND state='todo'""",
                    (sid,)).fetchall()
                if blocking:
                    raise Refused("discover skills and finish planning before work")
            if task["category"] == "verify":
                pending = conn.execute("""SELECT count(*) FROM tasks
                    WHERE session_id=? AND category='work' AND state='todo'""",
                    (sid,)).fetchone()[0]
                if pending:
                    raise Refused("complete or revise work tasks before verification")
            if task["category"] == "handoff":
                s = _session(conn, sid)
                if not s["handoff"]:
                    raise Refused("write the handoff first")
            conn.execute("UPDATE tasks SET state='done',evidence=?,updated_at=? WHERE id=?",
                         (path, now(), task_id))
            event(conn, sid, "task_completed", {"task_id": task_id, "evidence": path})
    return {"task_id": task_id, "state": "done", "evidence": path}


def handoff(root, sid, summary, next_action, risks):
    summary = require_text(summary, "summary")
    next_action = require_text(next_action, "next action")
    if not isinstance(risks, str) or len(risks) > 2000:
        raise Refused("risks too long")
    with closing(connect(root, create=True)) as conn:
        session = _session(conn, sid, active=True)
        items = _tasks(conn, sid)
        lines = ["# Session handoff: " + sid, "",
                 "- Actor: " + session["actor"],
                 "- Goal: " + session["goal"].replace("\n", " "),
                 "- Summary: " + summary.replace("\n", " "),
                 "- Risks: " + (risks.strip() or "None reported").replace("\n", " "),
                 "- Next action: " + next_action.replace("\n", " "),
                 "", "## Task ledger"]
        for task in items:
            resolved = task["state"] == "done" or task["category"] == "handoff"
            lines.append("- [%s] #%d %s — %s" %
                         ("x" if resolved else " ",
                          task["id"], task["summary"].replace("\n", " "),
                          task["evidence"] or ("this handoff" if task["category"] == "handoff" else "no evidence")))
        body = "\n".join(lines) + "\n"
        directory = _storage(root, create=True) / "handoffs"
        if directory.is_symlink():
            raise Refused("handoff directory cannot be a symlink")
        directory.mkdir(exist_ok=True)
        target = directory / (sid + ".md")
        if target.is_symlink():
            raise Refused("handoff target cannot be a symlink")
        temporary = directory / ("." + sid + "-" + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_text(body, encoding="utf-8")
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink()
        with conn:
            conn.execute("UPDATE sessions SET handoff=? WHERE id=?", (body, sid))
            conn.execute("""UPDATE tasks SET state='done',evidence=?,updated_at=?
                            WHERE session_id=? AND category='handoff' AND state='todo'""",
                         ("private-local-handoff", now(), sid))
            event(conn, sid, "handoff_written",
                  {"open_tasks": sum(t["state"] == "todo" and t["category"] != "handoff" for t in items)})
    return {"session": sid, "handoff": target.relative_to(root).as_posix(),
            "unfinished": sum(t["state"] == "todo" and t["category"] != "handoff" for t in items),
            "handoff_task_completed": True}

def close(root, sid, outcome, owner_approved=False):
    if outcome not in ("success", "partial", "failed"):
        raise Refused("outcome must be success, partial or failed")
    with closing(connect(root, create=True)) as conn:
        session = _session(conn, sid, active=True)
        if not session["handoff"]:
            raise Refused("a handoff is mandatory before closing a session")
        pending = [t for t in _tasks(conn, sid) if t["state"] != "done"]
        if outcome == "success" and pending:
            raise Refused("success requires all tasks completed (%d pending)" % len(pending))
        if outcome == "success" and not owner_approved:
            raise Refused("a successful outcome requires explicit human confirmation --owner-approved")
        folder = _storage(root, create=True) / "skill-proposals"
        if folder.is_symlink():
            raise Refused("skill proposal directory cannot be a symlink")
        folder.mkdir(exist_ok=True)
        file = folder / (sid + ".md")
        if file.is_symlink():
            raise Refused("skill proposal target is a symlink")
        draft = "# Unreviewed skill proposal from " + sid + "\n\n"
        draft += "Status: draft; NOT executable or installed.\n\n"
        draft += "## Goal\n" + session["goal"] + "\n\n"
        draft += "## Observed steps (review for generality)\n"
        for task in _tasks(conn, sid):
            draft += "- %s [%s; evidence: %s]\n" % (
                task["summary"], task["state"], task["evidence"] or "none")
        draft += "\n## Review\nOnly promote when reusable, independently evaluated, and the owner approves.\n"
        tmp = folder / ("." + sid + "-" + uuid.uuid4().hex + ".tmp")
        try:
            tmp.write_text(draft, encoding="utf-8")
            tmp.replace(file)
        finally:
            if tmp.exists():
                tmp.unlink()
        with conn:
            conn.execute("UPDATE sessions SET state='closed',outcome=?,closed_at=? WHERE id=?",
                         (outcome, now(), sid))
            event(conn, sid, "closed", {"outcome": outcome, "owner_approved": owner_approved,
                                       "uncompleted": len(pending)})
    return {"session": sid, "state": "closed", "outcome": outcome,
            "draft_skill": file.relative_to(root).as_posix(),
            "skill_installed": False, "pending_tasks": len(pending)}

def twin(root, sid, steps):
    """Deterministic task-state simulation in RAM: no tools, network or storage writes."""
    if not isinstance(steps, list) or len(steps) > 100:
        raise Refused("twin plan must be a JSON array of at most 100 operations")
    with closing(connect(root)) as conn:
        _session(conn, sid)
        before = _tasks(conn, sid)
    state = {t["id"]: dict(t) for t in before}
    changes = []
    proposed = -1
    for step in steps:
        if not isinstance(step, dict) or step.get("op") not in ("add_task", "complete_task"):
            raise Refused("twin supports only add_task and complete_task")
        if step["op"] == "add_task":
            text = require_text(step.get("summary"), "task", 500)
            state[proposed] = {"id": proposed, "category": "work",
                                "summary": text, "state": "todo"}
            changes.append({"op": "add_task", "temp_id": proposed, "summary": text})
            proposed -= 1
        else:
            task_id = step.get("task_id")
            if isinstance(task_id, bool) or not isinstance(task_id, int) or task_id not in state:
                raise Refused("twin referenced an unknown task")
            if state[task_id]["state"] != "todo":
                raise Refused("twin task is already complete")
            if state[task_id]["category"] in ("work", "verify", "handoff"):
                if any(t["category"] in ("skills", "plan") and t["state"] == "todo"
                       for t in state.values()):
                    raise Refused("twin plan bypasses skill discovery or planning")
            state[task_id]["state"] = "done"
            changes.append({"op": "complete_task", "task_id": task_id})
    return {"world": "in-memory task twin v0", "session": sid, "executed_tools": 0,
            "files_written": 0, "before_open": sum(t["state"] == "todo" for t in before),
            "after_open": sum(t["state"] == "todo" for t in state.values()),
            "changes": changes, "note": "This simulates task transitions only, not AI behavior."}


def adhd(root, query):
    """Evidence-linked cross-zone associations, not fabricated semantic similarity."""
    query = require_text(query, "query", 300)
    terms = set(TOKEN.findall(query.casefold()))
    docs = []
    count = 0
    for zone in HUMAN_ZONES:
        folder = Path(root) / zone
        if not folder.exists() or folder.is_symlink():
            continue
        for path in sorted(folder.rglob("*.md")):
            if count >= MAX_SCAN_FILES:
                break
            if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != root):
                continue
            try:
                if path.stat().st_size > 48000:
                    continue
                tokens = set(TOKEN.findall(path.read_text(encoding="utf-8").casefold()))
            except (OSError, UnicodeError):
                continue
            hit = terms.intersection(tokens)
            if hit:
                docs.append((zone, path.relative_to(root).as_posix(), tokens, hit))
            count += 1
    pairs = []
    for i, left in enumerate(docs[:100]):
        for right in docs[i + 1:100]:
            if left[0] == right[0]:
                continue
            shared = (left[2] & right[2]) - terms
            if not shared:
                continue
            score = len(left[3]) + len(right[3]) + min(len(shared), 10) / 10.0
            pairs.append({"left": left[1], "right": right[1],
                          "shared_terms": sorted(shared, key=len, reverse=True)[:6],
                          "score": round(score, 2), "status": "hypothesis"})
    pairs.sort(key=lambda row: (-row["score"], row["left"], row["right"]))
    return {"name": "ADHD", "expansion": "Associative Discovery across Heterogeneous Domains",
            "query": query, "documents_scanned": count, "bridges": pairs[:10],
            "note": "Lexical cross-domain suggestions; verify meaning manually."}


def main(argv=None):
    parser = argparse.ArgumentParser(prog="brain", description="Human-owned second brain CLI")
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("start")
    p.add_argument("--goal", required=True)
    p.add_argument("--actor", default="human")
    p = sub.add_parser("add")
    p.add_argument("session")
    p.add_argument("--task", required=True)
    p = sub.add_parser("done")
    p.add_argument("session")
    p.add_argument("task_id", type=int)
    p.add_argument("--evidence", required=True)
    p = sub.add_parser("status")
    p.add_argument("session")
    p = sub.add_parser("handoff")
    p.add_argument("session")
    p.add_argument("--summary", required=True)
    p.add_argument("--next", required=True)
    p.add_argument("--risks", default="")
    p = sub.add_parser("close")
    p.add_argument("session")
    p.add_argument("--outcome", required=True, choices=("success", "partial", "failed"))
    p.add_argument("--owner-approved", action="store_true")
    p = sub.add_parser("skills")
    p.add_argument("--query", default="")
    p = sub.add_parser("adhd")
    p.add_argument("--query", required=True)
    p = sub.add_parser("twin")
    p.add_argument("session")
    p.add_argument("--plan", required=True, help="JSON array file; read-only state simulation")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        if args.command == "start":
            result = start(root, args.actor, args.goal)
        elif args.command == "add":
            result = add(root, args.session, args.task)
        elif args.command == "done":
            result = finish(root, args.session, args.task_id, args.evidence)
        elif args.command == "status":
            result = view(root, args.session)
        elif args.command == "handoff":
            result = handoff(root, args.session, args.summary, args.next, args.risks)
        elif args.command == "close":
            result = close(root, args.session, args.outcome, args.owner_approved)
        elif args.command == "skills":
            result = {"skills": skills(root, args.query)}
        elif args.command == "adhd":
            result = adhd(root, args.query)
        else:
            file = Path(args.plan).resolve()
            if not file.is_file() or file.stat().st_size > 30000:
                raise Refused("twin plan must be a file of at most 30 KB")
            result = twin(root, args.session, json.loads(file.read_text(encoding="utf-8")))
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (Refused, OSError, sqlite3.Error, ValueError) as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
