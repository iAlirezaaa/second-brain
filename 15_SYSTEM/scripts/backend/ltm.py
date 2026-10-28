"""SuperAGI's long-term memory, ported: store facts, fetch them by relevance.

SuperAGI put LTM in a vector database (Pinecone/Chroma/...) behind an embeddings call.
The *logic* -- an actor stores what it learned, later fetches what relates to the
situation -- is kept here over SQLite FTS5, which the stdlib already carries. The vector
upgrade stays behind the documented `vector_search: false` flag (an optional-dependency
decision the owner makes); the store/fetch seam is the same either way.

The database lives at `.kb/ltm.sqlite` -- the disposable plane, like every index here.
Anything that must survive a clone goes to the shelf, not to this file.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_REL = Path(".kb") / "ltm.sqlite"


def _connect(root):
    path = root / DB_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS ltm "
                     "USING fts5(text, source, stored_at)")
    except sqlite3.OperationalError:
        # a sqlite build without FTS5 still deserves a working store: LIKE fallback
        conn.execute("CREATE TABLE IF NOT EXISTS ltm "
                     "(text TEXT, source TEXT, stored_at TEXT)")
    return conn


def store(root, text, source="agent"):
    """Append one memory; returns its rowid."""
    body = str(text or "").strip()
    if not body:
        raise ValueError("ltm.store needs text")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = _connect(root)
    try:
        cur = conn.execute("INSERT INTO ltm (text, source, stored_at) VALUES (?, ?, ?)",
                           (body, str(source or "agent"), now))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def fetch(root, query, k=5):
    """The rows most relevant to `query`, newest first as a tiebreak."""
    want = str(query or "").strip()
    if not want:
        return []
    conn = _connect(root)
    try:
        try:
            rows = conn.execute("SELECT text, source, stored_at FROM ltm "
                                "WHERE ltm MATCH ? ORDER BY rank LIMIT ?",
                                (want, int(k))).fetchall()
        except sqlite3.OperationalError:
            like = "%" + want + "%"
            rows = conn.execute("SELECT text, source, stored_at FROM ltm "
                                "WHERE text LIKE ? ORDER BY rowid DESC LIMIT ?",
                                (like, int(k))).fetchall()
        return [{"text": r[0], "source": r[1], "stored_at": r[2]} for r in rows]
    finally:
        conn.close()
