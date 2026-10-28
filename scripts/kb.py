#!/usr/bin/env python
"""Local keyword knowledge base for humans + agents. SQLite FTS5, no server, no vector DB.

Usage:
  python scripts/kb.py ingest [--vault path]   (re)index this brain's markdown
  python scripts/kb.py search "query"          (top 5 hits with zone + title)
  python scripts/kb.py gap "query"             (log a failed search — the gap register)
  python scripts/kb.py gaps                    (show logged gaps → the backlog)

The corpus is the brain's own tracked prose: the human plane, as a fresh clone would see
it. Two layouts, one walk — a home installed by `install.py` keeps its zones at the root,
the repo keeps them in vault-template/ beside its own documents. The machine plane (11–15)
is not corpus: those files are generated, quarantined or run artefacts, and an index that
quotes a local database back as knowledge is worse than no index. `common.clone_readable`
is the second law: a note a clone would not contain is not shared memory.
"""
import argparse
import re
import sqlite3
import sys
import unicodedata
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import clone_readable, DATE_RE, find_root, iter_markdown, parse_frontmatter
from sync_hosts import HOSTS

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows pipe safety
except AttributeError:
    pass

KB = Path(".kb") / "kb.sqlite"
SCHEMA = "2"

# Machine plane: written by tools, not by a person. Indexing it would let generated
# reports and the quarantined shelf outrank the notes they are about.
MACHINE_PLANE = ("11_CONTROL/", "12_RUNTIME/", "13_LAB/", "14_CANDIDATES/", "15_SYSTEM/")
# The template is the shape a note takes, not knowledge this brain has. An installed
# home has already lost the folder: install.py copies it to the root, where its notes
# are ordinary corpus.
NOT_CORPUS = ("vault-template/",)
# Agent doors are rendered copies of AGENTS.md (`sync_hosts.py --check` owns them).
# Indexing the copies would return the same paragraph five times under five names.
DOORS = {rel for _key, _name, rel, _mdc in HOSTS}


def normalise(text):
    """Same folding the measured source engine uses: NFKC, casefold, Persian letters."""
    return unicodedata.normalize("NFKC", str(text)).casefold().translate(
        str.maketrans({"ي": "ی", "ك": "ک"}))


def terms_of(text):
    return list(dict.fromkeys(re.findall(r"\w+", normalise(text), re.UNICODE)))


def db_path(root):
    return Path(root) / KB


def corpus(root):
    """Yield (relative posix path, absolute path) for every note a clone would carry."""
    root = Path(root)
    for path in iter_markdown(root):
        rel = path.relative_to(root).as_posix()
        if rel in DOORS or rel.startswith(NOT_CORPUS) or rel.startswith(MACHINE_PLANE):
            continue
        if any(part.startswith(".") for part in rel.split("/")[:-1]):
            continue  # host folders (.github, .cursor, ...) are configuration, not notes
        if not clone_readable(rel):
            continue
        yield rel, path


def zone_of(rel):
    """Top folder is the zone in both layouts; a root document has none."""
    parts = rel.split("/")[:-1]
    return parts[0] if parts else "root"


def _heading(body):
    """The first H1 is the title a document without frontmatter actually carries."""
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
        if line.strip() and not line.startswith("#"):
            return None
    return None


def open_db(root):
    conn = sqlite3.connect(str(db_path(root)))
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS kb_meta (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute("""CREATE TABLE IF NOT EXISTS notes
                        (path TEXT PRIMARY KEY, title TEXT, zone TEXT, body TEXT,
                         norm TEXT, updated TEXT)""")
        try:
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5"
                         "(path UNINDEXED, title, zone, body)")
        except sqlite3.OperationalError:
            pass  # FTS5 unavailable — the normalised LIKE fallback keeps search working
        conn.execute("""CREATE TABLE IF NOT EXISTS search_gaps
                        (query TEXT, logged TEXT, followed INTEGER DEFAULT 0)""")
    except sqlite3.Error:
        conn.close()
        raise
    return conn


def schema_version(conn):
    row = conn.execute("SELECT value FROM kb_meta WHERE key = 'schema'").fetchone()
    return row[0] if row else None


def reset_tables(conn):
    """The index is derived state: a schema change drops it rather than migrating it."""
    conn.execute("DROP TABLE IF EXISTS fts")
    conn.execute("DROP TABLE IF EXISTS notes")
    try:
        conn.execute("CREATE VIRTUAL TABLE fts USING fts5(path UNINDEXED, title, zone, body)")
    except sqlite3.OperationalError:
        pass
    conn.execute("""CREATE TABLE notes
                    (path TEXT PRIMARY KEY, title TEXT, zone TEXT, body TEXT,
                     norm TEXT, updated TEXT)""")


def ingest(root):
    from datetime import date
    root = Path(root)
    db_path(root).parent.mkdir(parents=True, exist_ok=True)
    with closing(open_db(root)) as conn:
        if schema_version(conn) != SCHEMA:
            reset_tables(conn)
        else:
            conn.execute("DELETE FROM notes")
            try:
                conn.execute("DELETE FROM fts")
            except sqlite3.Error:
                reset_tables(conn)
        count = 0
        for rel, path in corpus(root):
            text = path.read_text(encoding="utf-8", errors="replace")
            fm, body = parse_frontmatter(text)
            title = str(fm.get("title") or _heading(body) or path.stem)
            updated = fm.get("updated")
            if not DATE_RE.match(str(updated or "")):
                updated = date.fromtimestamp(path.stat().st_mtime).isoformat()
            zone = zone_of(rel)
            # The frontmatter is the note's shape, not its words: indexing it would make
            # every hit's snippet open on "--- id: ... topics: [...]" instead of the text.
            conn.execute("INSERT OR REPLACE INTO notes VALUES (?,?,?,?,?,?)",
                         (rel, title, zone, body, normalise(body), updated))
            try:
                conn.execute("INSERT INTO fts VALUES (?,?,?,?)",
                             (rel, title, zone, normalise(body)))
            except sqlite3.Error:
                pass
            count += 1
        conn.execute("INSERT OR REPLACE INTO kb_meta VALUES ('schema', ?)", (SCHEMA,))
        conn.commit()
    print(f"indexed {count} notes from the tracked corpus ({db_path(root).as_posix()})")
    return 0


def _snippet(body, terms, width=150):
    """A window of the real text around the first query term — never the folded copy."""
    flat = " ".join(body.split())
    folded = normalise(flat)
    spot = -1
    if len(folded) == len(flat):
        for term in terms:
            found = folded.find(term)
            if found >= 0 and (spot < 0 or found < spot):
                spot = found
    if spot < 0:
        return flat[:width] + ("…" if len(flat) > width else "")
    start = max(0, spot - width // 3)
    end = min(len(flat), start + width)
    return ("…" if start else "") + flat[start:end] + ("…" if end < len(flat) else "")


def _like_fallback(conn, terms, limit):
    pattern = " AND ".join("instr(norm, ?) > 0" for _ in terms)
    rows = conn.execute("SELECT path, title, zone, body FROM notes WHERE " + pattern +
                        " ORDER BY updated DESC LIMIT ?", (*terms, limit)).fetchall()
    return rows


def find(root, query, limit=5):
    """Ranked hits with the snippet taken from the stored original text."""
    query = str(query).strip()
    terms = terms_of(query)
    if not terms:
        return []
    if not db_path(root).is_file():
        raise RuntimeError("no index here; run `python scripts/kb.py ingest` first")
    with closing(open_db(root)) as conn:
        if schema_version(conn) != SCHEMA:
            raise RuntimeError("index was built by an older corpus rule; "
                               "run `python scripts/kb.py ingest`")
        rows = []
        try:
            # Rank from the folded copy in fts; show the original text from notes, so a
            # snippet never lower-cases a name or prints the folded spelling as truth.
            rows = conn.execute(
                "SELECT n.path, n.title, n.zone, n.body FROM fts JOIN notes n "
                "ON n.path = fts.path WHERE fts MATCH ? ORDER BY bm25(fts) LIMIT ?",
                (" AND ".join('"%s"' % t for t in terms), limit)
            ).fetchall()
        except sqlite3.OperationalError:
            rows = _like_fallback(conn, terms, limit)
        if not rows:
            rows = _like_fallback(conn, terms, limit)
    return [{"path": path, "title": title, "zone": zone, "snippet": _snippet(body, terms)}
            for path, title, zone, body in rows]


def search(root, query):
    hits = find(root, query)
    if not hits:
        log_gap(root, query)
        print(f"no hits — logged as a knowledge gap: {query!r}")
        return 1
    for hit in hits:
        print(f"{hit['path']}  [{hit['zone']}]  {hit['title']}")
        print(f"    {hit['snippet']}")
    return 0


def log_gap(root, query):
    import datetime
    with closing(open_db(root)) as conn:
        conn.execute("INSERT INTO search_gaps (query, logged) VALUES (?, ?)",
                     (query, datetime.date.today().isoformat()))
        conn.commit()


def gaps(root):
    with closing(open_db(root)) as conn:
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
    root = Path(args.vault).expanduser() if args.vault else find_root(Path(__file__))
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
