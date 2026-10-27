#!/usr/bin/env python
"""Local keyword knowledge base for humans + agents. SQLite FTS5, no server, no vector DB.

Usage:
  python scripts/kb.py ingest [--vault path]   (re)index every markdown note
  python scripts/kb.py search "query"          (top 5 hits with zone + title)
  python scripts/kb.py gap "query"             (log a failed search — the gap register)
  python scripts/kb.py gaps                    (show logged gaps → the backlog)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DATE_RE, find_root, iter_markdown, parse_frontmatter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows pipe safety
except AttributeError:
    pass

KB_PATH = Path(".kb/kb.sqlite")


def open_db():
    import sqlite3
    KB_PATH.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(KB_PATH)
    conn.execute("""CREATE TABLE IF NOT EXISTS notes
                    (path TEXT PRIMARY KEY, title TEXT, zone TEXT, body TEXT, updated TEXT)""")
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5"
                     "(path UNINDEXED, title, zone, body)")
    except sqlite3.OperationalError:
        pass  # FTS5 unavailable — plain-LIKE fallback keeps everything working
    conn.execute("""CREATE TABLE IF NOT EXISTS search_gaps
                    (query TEXT, logged TEXT, followed INTEGER DEFAULT 0)""")
    return conn


def ingest(root):
    from datetime import date
    import re
    count = 0
    conn = open_db()
    today = date.today().isoformat()
    count = 0
    vault_root = root / "vault-template"
    zones = json.loads((root / "rules" / "zones.json").read_text(encoding="utf-8"))["zones"]
    for path in iter_markdown(vault_root):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, body = parse_frontmatter(text)
        rel = path.relative_to(vault_root).as_posix()
        zone = next((p for p in rel.split("/")[:-1] if p in zones), "root")
        title = str(fm.get("title") or path.stem)
        conn.execute("INSERT OR REPLACE INTO notes VALUES (?,?,?,?,?)",
                     (rel, title, zone, text[:20000], str(fm.get("updated")) if DATE_RE.match(str(fm.get("updated") or "")) else today))
        try:
            conn.execute("INSERT INTO fts VALUES (?,?,?,?)", (rel, title, zone, text[:20000]))
        except Exception:
            pass
        count += 1
    conn.commit()
    print(f"indexed {count} notes from {vault_root}")
    return 0


def search(root, query):
    conn = open_db()
    hits = []
    try:
        try:
            rows = conn.execute(
                "SELECT path, title, zone, snippet(fts, 3, '>>', '<<', '…', 8) "
                "FROM fts WHERE fts MATCH ? ORDER BY rank LIMIT 5", (query,)).fetchall()
        except Exception:
            rows = conn.execute(
                "SELECT path, title, zone, '' FROM notes WHERE notes.body LIKE ? LIMIT 5",
                ("%" + query + "%",)).fetchall()
    finally:
        hits = rows
    if not hits:
        log_gap(root, query)
        print(f"no hits — logged as a knowledge gap: {query!r}")
        return 1
    for path, title, zone, snippet in hits:
        print(f"{path}  [{zone}]  {title}")
        if snippet:
            print(f"    {snippet}")
    return 0


def log_gap(root, query):
    import datetime
    conn = open_db()
    conn.execute("INSERT INTO search_gaps (query, logged) VALUES (?, ?)",
                 (query, datetime.date.today().isoformat()))
    conn.commit()


def gaps(root):
    conn = open_db()
    rows = conn.execute(
        "SELECT query, logged, followed FROM search_gaps ORDER BY logged DESC").fetchall()
    if not rows:
        print("no gaps logged — retrieval is keeping up.")
    for query, logged, followed in rows:
        print(f"[{logged}] {'DONE ' if followed else 'OPEN '} {query}")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["ingest", "search", "gap", "gaps"])
    parser.add_argument("query", nargs="?", default=None)
    parser.add_argument("--vault", default=None)
    args = parser.parse_args()
    root = find_root(Path(__file__))
    if args.command == "ingest":
        return ingest(root)
    if args.command == "gap":
        log_gap(root, args.query or "")
        print(f"gap logged: {args.query!r}")
        return 0
    if args.command == "gaps":
        return gaps(root)
    if not args.query:
        parser.error("search needs a query")
    return search(root, args.query)


if __name__ == "__main__":
    sys.exit(main())
