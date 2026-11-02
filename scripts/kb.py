#!/usr/bin/env python
"""Local keyword knowledge base for humans + agents. SQLite FTS5, no server, no vector DB.

Usage:
  python scripts/kb.py ingest [--vault path]   (re)index this brain's markdown
  python scripts/kb.py search "query"          (top 5 hits with zone + title)
  python scripts/kb.py --related <note>        (top 5 neighbours of one indexed note)
  python scripts/kb.py gap "query"             (log a failed search — the gap register)
  python scripts/kb.py gaps                    (show logged gaps → the backlog)

The corpus is the brain's own tracked prose: the human plane, as a fresh clone would see
it. Two layouts, one walk — a home installed by `install.py` keeps its zones at the root,
the repo keeps them in vault-template/ beside its own documents. The machine plane (11–15)
is not corpus: those files are generated, quarantined or run artefacts, and an index that
quotes a local database back as knowledge is worse than no index. `common.clone_readable`
is the second law: a note a clone would not contain is not shared memory.

`--related` answers "what else is about this?" from the terms `ingest` already stored, over the
brain's notes and not the repo's own root documents, so a "related notes" pane costs no embedding
and no model (Smart Connections' value, none of its
cost; the seam in `15_SYSTEM/scripts/backend/vector.py` stays closed and unused here). A
neighbour is another indexed note sharing at least one distinct term — title and body, folded
by the same `normalise()` a search uses — and the two term sets are compared as IDF-weighted
vectors: each shared word counts by how rare it is in this index (`log(notes / notes carrying
it)`, the same document-frequency idea bm25 uses for `search`), so a word every note carries
weighs nothing and a word two notes carry decides the ranking. Ties break on `(-shared, path)`,
and every printed line names the shared terms with how many indexed notes carry each.
A note the index does not hold is REFUSED (exit 1), never answered with an empty list: an
empty list reads exactly like "no neighbours" to whatever parses it. A note the index does
hold, with nothing distinguishing to share, gets an empty answer and exit 0 — that is a
measurement, and it says so in words.
"""
import argparse
import math
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


RELATED_TERMS_SHOWN = 8
RELATED_COLUMNS = "SELECT path, title, zone, body FROM notes"


class RelatedError(RuntimeError):
    """A `--related` refusal, in lines.

    `find()` lets a missing index crash; `--related` is asked a question whose tempting wrong
    answer is an empty list. So a refusal is a value here: named, printed, exit 1, and it never
    prints a neighbour line. `search` logs a gap when nothing matches — `--related` does not,
    because "you named a note I never read" is a bad argument, not a hole in the brain.
    """

    def __init__(self, lines):
        RuntimeError.__init__(self, "\n".join(lines))
        self.lines = list(lines)


def note_terms(title, body):
    """The distinct folded words a note is made of: title first, then body.

    The title counts because on a short note it is the only place the subject is written down.
    The fold is the one `search` uses, so the same note written in the Arabic and the Persian
    letter forms still meets itself.
    """
    return set(terms_of(title)) | set(terms_of(body))


def is_shelf(path):
    """True for a document at the repo root: the shelf the notes sit on, not one of the notes.

    `search` keeps answering about these — a person asking for the changelog must get it. This
    distinguishes them for `--related` only, whose question is what a note is *about*.
    """
    return "/" not in str(path).replace("\\", "/")


def clean_ref(ref):
    """'./02_WIKI/x.md', '02_WIKI\\x.md' and 'x' all reach the same relative form."""
    text = str(ref).replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.lstrip("/")


def matches_of(rows, ref):
    """Every indexed row the typed reference could mean: path, then title, then path tail."""
    name = clean_ref(ref)
    stem = name[:-3] if name.endswith(".md") else name
    exact = [row for row in rows if row[0] in (name, name + ".md", stem, stem + ".md")]
    if exact:
        return exact
    titled = [row for row in rows if normalise(row[1]) == normalise(name)]
    if titled:
        return titled
    return [row for row in rows if row[0].rsplit("/", 1)[-1] in (stem, stem + ".md")]


def resolve_note(rows, ref, root):
    """One indexed row for the named note, or the refusal that says which rule stopped it."""
    matches = matches_of(rows, ref)
    if len(matches) > 1:
        raise RelatedError([
            "REFUSED --related %r: %d indexed notes answer to that name, so the answer would "
            "be a guess wearing a neighbour list" % (ref, len(matches)),
            "  ambiguous: " + ", ".join(sorted(row[0] for row in matches)[:5]),
            "  name the note by its full indexed path instead",
        ])
    if matches:
        return matches[0]
    name = clean_ref(ref)
    lines = ["REFUSED --related %r: the index does not hold that note" % ref]
    if (Path(root) / name).is_file() or (Path(root) / (name + ".md")).is_file():
        lines.append("  the file is here, but the corpus rule does not index it: the machine "
                     "plane (11-15), the agent doors and vault-template/ are not corpus")
        lines.append("  refusing is the honest answer — a note this tool never read cannot "
                     "have measured neighbours")
    else:
        lines.append("  %d note(s) indexed, none of them that one; no neighbour list is "
                     "printed for a note the index does not hold" % len(rows))
        lines.append("  if the note is new, rebuild what it should be in: "
                     "python scripts/kb.py ingest")
    raise RelatedError(lines)


def document_frequency(entries):
    """{term: how many indexed notes carry it} — one pass over the rows `ingest` wrote."""
    df = {}
    for entry in entries:
        for term in entry["terms"]:
            df[term] = df.get(term, 0) + 1
    return df


def term_weight(df, total):
    """log(total / df): 0 for a word every indexed note carries, bigger the rarer the word.

    This is the same document-frequency idea `search` ranks with under bm25, so `--related` and
    `search` agree about what a rare word is. It exists because the plain overlap ratio is not
    enough on prose: measured with an unweighted Jaccard, this repo's `--related` answered
    "what is near the memory-planes map?" with AGENTS.md, MEMORY.md and HANDOFF.md — notes that
    share its 300 most common words and nothing else. A word every note uses says nothing about
    what a note is about, so it must weigh nothing.
    """
    return math.log(total / df)


def related(root, note, limit=5):
    """Deterministic neighbours of one indexed note: shared terms, weighted by how rare they are.

    Reads only the `notes` rows `ingest` wrote — no model, no embedding, no dependency, no
    socket. The similarity of two notes is the cosine of their IDF-weighted term vectors, so a
    short note sharing one rare word beats a long note sharing four common ones; ties break on
    `(-shared, path)` once the cosine itself ties, and every printed line names the terms it stood
    on and how many indexed notes carry each of them, rarest first.

    The pool is the brain's notes, not the repo's own surface: a document with no folder —
    README, ROADMAP, CHANGELOG, HANDOFF, AGENTS — is a shelf the notes sit on, and measured on this
    repo it answered "what is near the memory-planes map?" with ROADMAP.md, CHANGELOG.md and
    HANDOFF.md, because a document that mentions every word shares every note's words. `search`
    still finds them; `--related` refuses to rank them, and refuses when one of them is the note
    you named.

    Raises RelatedError for a note the index does not hold, for a name that reaches two indexed
    notes, for a shelf document, and for an index that is missing or built by an older corpus rule.
    A note the index does hold, with nothing distinguishing to share, returns an empty
    `neighbours` list: that is a measurement, and `show_related` prints it as one.
    """
    limit = int(limit)
    if limit < 1:
        raise RelatedError(["REFUSED --related %r: --limit needs a positive whole number, "
                            "not %d" % (note, limit)])
    if not db_path(root).is_file():
        raise RelatedError([
            "REFUSED --related %r: no index here — %s does not exist"
            % (note, (Path(root) / KB).as_posix()),
            "  build it first: python scripts/kb.py ingest",
        ])
    with closing(open_db(root)) as conn:
        if schema_version(conn) != SCHEMA:
            raise RelatedError([
                "REFUSED --related %r: the index was built by an older corpus rule" % note,
                "  rebuild it: python scripts/kb.py ingest",
            ])
        rows = conn.execute(RELATED_COLUMNS).fetchall()
    path, title, zone, _body = resolve_note(rows, note, root)
    entries = [{"path": row[0], "title": row[1], "zone": row[2],
                "terms": note_terms(row[1], row[3])} for row in rows]
    total = len(entries)
    if is_shelf(path):
        raise RelatedError([
            "REFUSED --related %r: %s is a shelf document — it sits at the repo root and holds "
            "what every note does, so it is about none of them" % (note, path),
            "  related answers what a note is about; name a note inside a zone instead",
            "  the shelf: " + ", ".join(sorted(e["path"] for e in entries if is_shelf(e["path"]))[:6]),
        ])
    pool = [entry for entry in entries if not is_shelf(entry["path"])]
    df = document_frequency(pool)
    norm = {}
    source_terms = set()
    for entry in pool:
        weight = math.sqrt(sum(term_weight(df[t], len(pool)) ** 2 for t in entry["terms"]))
        norm[entry["path"]] = weight
        if entry["path"] == path:
            source_terms = entry["terms"]
    source_norm = norm[path]
    neighbours = []
    undistinguished = 0
    for entry in pool:
        if entry["path"] == path:
            continue
        shared = source_terms & entry["terms"]
        if not shared:
            continue
        bottom = source_norm * norm[entry["path"]]
        score = sum(term_weight(df[t], len(pool)) ** 2 for t in shared) / bottom if bottom else 0.0
        if score <= 0.0:
            undistinguished += 1  # shared words, but only words every pooled note carries
            continue
        # rarest first, and alphabetically inside one weight: the printed evidence must not
        # depend on which order two set literals happened to iterate in.
        ordered = sorted(shared, key=lambda term: (-term_weight(df[term], len(pool)), term))
        neighbours.append({"path": entry["path"], "title": entry["title"], "zone": entry["zone"],
                           "shared": len(shared), "score": score,
                           "terms": [[term, df[term]] for term in ordered]})
    neighbours.sort(key=lambda row: (-round(row["score"], 12), -row["shared"], row["path"]))
    return {"path": path, "title": title, "zone": zone, "indexed": total, "limit": limit,
            "neighbours": neighbours[:limit], "ranked": len(neighbours), "pool": len(pool),
            "shelf": total - len(pool), "shared_undistinguished": undistinguished}


def show_related(root, note, limit=5):
    """Print the neighbours, or print the refusal — and return the exit code either way."""
    try:
        answer = related(root, note, limit)
    except RelatedError as err:
        for line in err.lines:
            print(line)
        return 1
    total = answer["indexed"]
    found = answer["neighbours"]
    print("related to %s: %d neighbour(s) of %d indexed note(s) — shared terms weighted by how "
          "rare each one is in this index, no embedding" % (answer["path"], len(found), total))
    if answer["shelf"]:
        print("    %d shelf document(s) at the repo root were not considered: a document about "
              "everything is a neighbour of nothing" % answer["shelf"])
    for row in found:
        print("%s  [%s]  %s" % (row["path"], row["zone"], row["title"]))
        shown = ", ".join("%s (%d of %d notes)" % (term, df, answer["pool"])
                          for term, df in row["terms"][:RELATED_TERMS_SHOWN])
        extra = len(row["terms"]) - RELATED_TERMS_SHOWN
        if extra > 0:
            shown += " (+%d more, all commoner)" % extra
        print("    %d shared term(s), similarity %.3f: %s" % (row["shared"], row["score"], shown))
    if not found:
        if answer["shared_undistinguished"]:
            print("no note in the index shares a distinguishing term with %s — %d note(s) share "
                  "only words every indexed note carries; an honest empty answer, not a failure"
                  % (answer["path"], answer["shared_undistinguished"]))
        else:
            print("no note in the index shares a term with %s — %d note(s) indexed; an honest "
                  "empty answer, not a failure" % (answer["path"], total))
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
    parser.add_argument("command", nargs="?", default=None,
                        choices=["ingest", "search", "gap", "gaps", "related"])
    parser.add_argument("query", nargs="?", default=None)
    parser.add_argument("--vault", default=None)
    parser.add_argument("--related", dest="related", metavar="NOTE", default=None,
                        help="top NOTE's neighbours from the keyword index (shared terms, "
                             "no embedding) — the same thing as `related NOTE`")
    parser.add_argument("--limit", type=int, default=5,
                        help="how many neighbours --related prints (default 5)")
    args = parser.parse_args()
    if args.command and args.related is not None:
        parser.error("name the note once: `kb.py related NOTE` or `kb.py --related NOTE`, "
                     "not both")
    command = args.command or ("related" if args.related is not None else None)
    if command is None:
        parser.error("kb.py needs a command (ingest, search, gap, gaps, related) "
                     "or --related NOTE")
    root = Path(args.vault).expanduser() if args.vault else find_root(Path(__file__))
    if command == "ingest":
        return ingest(root)
    if command == "gap":
        log_gap(root, args.query or "")
        print(f"gap logged: {args.query!r}")
        return 0
    if command == "gaps":
        return gaps(root)
    if command == "related":
        note = args.related if args.related is not None else args.query
        if not note:
            parser.error("--related needs a note: kb.py --related 02_WIKI/note.md")
        if args.limit < 1:
            parser.error("--limit needs a positive whole number, not %d" % args.limit)
        return show_related(root, note, args.limit)
    if not args.query:
        parser.error("search needs a query")
    return search(root, args.query)


if __name__ == "__main__":
    sys.exit(main())
