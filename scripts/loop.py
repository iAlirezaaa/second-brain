#!/usr/bin/env python
"""Continuous improvement loop — one cycle per run (ratchet, not treadmill).

Usage: python scripts/loop.py [--vault path] [--no-tests] [--root path]

A cycle:
  1. Collects improvement signals: integrity failures, test failures,
     knowledge gaps, stale inbox items, proposals awaiting approval,
     hygiene debt (TODO/FIXME), orphan notes.
  2. Compares against the previous run (ratchet: regressions are loud,
     improvements are counted).
  3. Writes a candidate report the HUMAN promotes or rejects.
     (machine plane output -> 14_CANDIDATES/loop/, never edits the human plane)
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
from common import DATE_RE, find_root, iter_markdown, parse_frontmatter, run_utf8

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

TODO_RE = re.compile(r"\b(TODO|FIXME|XXX)\b", re.IGNORECASE)


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
    db = root / ".kb" / "kb.sqlite" if (root / ".kb" / "kb.sqlite").is_file() else None
    if db is None:
        return {"open": 0, "recent": [], "note": "no .kb index anywhere — ingest first"}
    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT query, logged FROM search_gaps ORDER BY logged DESC").fetchall()
    conn.close()
    return {"open": len(rows), "recent": [f"{q} ({d})" for q, d in rows[:limit]]}


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
    history["runs"].append({"date": datetime.date.today().isoformat(), "metrics": metrics})
    history_path.write_text(json.dumps(history, indent=1, default=str), encoding="utf-8")
    return verdicts


def candidates(metrics, verdicts):
    out = []
    for check in ("link_check", "frontmatter_check"):
        health = metrics[check]
        if health["returncode"] != 0 or health["problems"]:
            out.append(("P1", f"{check}: {len(health['problems'])} problem(s) — fix now, this is red house",
                        health["problems"][:3]))
    if metrics["tests"]["returncode"] not in (0, None):
        out.append(("P1", f"tests failing: {metrics['tests']['summary']}", []))
    if metrics["vault"]["awaiting_approval"]:
        out.append(("P2", f"{len(metrics['vault']['awaiting_approval'])} proposal(s) waiting on the human",
                    metrics["vault"]["awaiting_approval"][:3]))
    if metrics["vault"]["stale_inbox"]:
        out.append(("P3", f"{len(metrics['vault']['stale_inbox'])} inbox item(s) untouched for 14+ days",
                    metrics["vault"]["stale_inbox"][:3]))
    if metrics["kb_gaps"].get("open"):
        out.append(("P2", f"{metrics['kb_gaps']['open']} unanswered search(es) = the self-driving backlog",
                    metrics["kb_gaps"]["recent"]))
    if metrics["hygiene"]["todo_hygiene"]:
        out.append(("P3", f"{metrics['hygiene']['todo_hygiene']} raw TODO/FIXME marker(s)",
                    ["grep for TODO|FIXME before promising fixes — each one needs a task or deletion"]))
    return out


def write_report(root, metrics, verdicts, candidates_list, cycle):
    today = datetime.date.today().isoformat()
    loop_dir = root / "14_CANDIDATES" / "loop"
    loop_dir.mkdir(parents=True, exist_ok=True)
    suffix = "" if cycle == 1 else f"-c{cycle}"
    report_path = loop_dir / f"report-{today}{suffix}.md"
    lines = [
        f"---\nid: cand-{today}-loop{suffix.strip('-')}",
        "type: note", "title: Improvement loop report",
        "status: raw", "owner: agent", "topics: [loop, improvement]",
        f"created: {today}", f"updated: {today}", "---\n",
        f"# Improvement loop — {today} (cycle {cycle})",
        "*Machine candidate shelf — nothing here changed the vault. Promote or reject.*\n",
        "## Health signals\n",
        f"- tests: {metrics['tests']['summary']} (rc={metrics['tests']['returncode']})",
        f"- link_check: rc={metrics['link_check']['returncode']} problems={len(metrics['link_check']['problems'])}",
        f"- frontmatter_check: rc={metrics['frontmatter_check']['returncode']} problems={len(metrics['frontmatter_check']['problems'])}",
        f"- hygiene: {metrics['hygiene']['todo_hygiene']} TODO markers in {metrics['hygiene']['files_scanned']} files",
    ]
    lines.append("\n## Ratchet (vs previous run)\n")
    if verdicts:
        lines += [f"- {name}: {result}" for name, result in sorted(verdicts.items())]
    else:
        lines.append("- first recorded run — baseline set")
    lines.append("\n## Candidates next cycle could implement\n")
    if candidates_list:
        for priority, title, examples in candidates_list:
            lines.append(f"- **{priority}** {title}")
            for example in examples:
                lines.append(f"  - {example}")
    else:
        lines.append("- none: house is quiet. Try a harder golden query, or ship a Phase-8 idea.")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None)
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))
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
    candidates_list = candidates(metrics, verdicts)
    report_path = write_report(root, metrics, verdicts, candidates_list, cycle)
    hard_fail = any(priority == "P1" for priority, _, _ in candidates_list)
    print(f"cycle {cycle} — report: {report_path.relative_to(root)}")
    for priority, title, _ in candidates_list:
        print(f"{priority}: {title}")
    return 1 if hard_fail else 0


if __name__ == "__main__":
    sys.exit(main())
