"""Phase 44 item 3 — `kb.py --related <note>`: neighbours from the index that already exists.

Obsidian's "linked notes" pane, Basic Memory's relations and Smart Connections' embedding
sidebar all answer the same question — "what else is about this?" — and the usual answer is a
vector store. Charter §2 keeps embeddings behind a flag this repo has not earned yet
(`tests/test_phase29_vector_seam.py` holds that seam shut), so what ships here is the honest
half: the terms the FTS5 index already stores, intersected.

The rule, stated before the code:

  * a neighbour is another indexed note sharing at least one distinct term (title + body, folded
    exactly the way `search` folds a query) with the note you named;
  * the two term sets are compared as IDF-weighted vectors: a shared word counts by how rare it
    is in this index (`log(notes / notes carrying it)` — the document-frequency idea bm25 already
    uses for `search`), so a word every note carries weighs nothing. Measured here before the
    weighting went in: an unweighted overlap ratio answered "what is near the memory-planes map?"
    with AGENTS.md, MEMORY.md and HANDOFF.md — three notes sharing its 300 commonest words and
    nothing else. A list of noise is the other way to dress an empty answer up as success;
  * the ranking is that cosine; a pair whose shared words are all words every indexed note
    carries scores zero and is dropped as undistinguished rather than listed; ties break on
    `(-shared, path)` once the cosine itself ties; and every line prints the shared terms with how
    many indexed notes carry each, rarest first — the answer names its own evidence;
  * **a note the index does not hold is refused, not answered with an empty list.** An empty
    list reads exactly like "no neighbours" to whatever parses it, and output that cannot be
    told apart from a lie is not a gate;
  * a note the index *does* hold, with nothing distinguishing to share, gets an empty answer and
    exit 0 — that is a measurement, and it says so in words;
  * the pool is notes, not the repo's own surface: a document with no folder (README, ROADMAP,
    CHANGELOG, HANDOFF, AGENTS) mentions every word, so it is "near" everything and about nothing.
    It is never a neighbour, naming one is refused, and the answer says how many were skipped.
    `search` still returns them — that question is "where is this written", not "what resembles
    this note".

No embedding, no model, no new dependency, no network: `kb.py`'s import set is stdlib plus the
two siblings it already had, and `test_no_socket_is_opened_to_answer` proves the answer costs no
connection.
"""
import ast
import math
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import kb  # noqa: E402
from common import run_utf8  # noqa: E402

KB = str(SCRIPTS / "kb.py")

# Six notes whose term sets are hand-countable, so the ranking is proven against arithmetic
# written in this file rather than against a number the implementation printed first. `ingest`
# stores the body including its H1, so a title term is already in the body set.
#
#   term            notes carrying it   weight log(6/df)
#   gate, refuse            5           0.1823   (almost everyone — nearly free)
#   twin, run, check,       2 or 1      1.0986 / 1.7918
#   print, ledger, fills…
#
#   q     = {q, gate, refuse, run, check, ledger, print}   -> 7 terms, norm 3.1794
#   x     = {x, gate, refuse, print}                       -> 3 shared with q, cosine 0.1892
#   y     = {y, gate, refuse, run, check, fill01..fill12}  -> 17 terms, 4 shared, cosine 0.1173
#   t1/t2 = {twin, gate, refuse}                           -> 2 shared, cosine 0.0185 (tie -> path)
#   z     = {z, island, vapor, quorum}                     -> 0 shared, never a neighbour
#
# x outranks y on one fewer shared word: y's fourth word is `check`, and x's third is `print`,
# which weigh the same, while y's own 12 filler words inflate its norm and dilute the score.
FILLERS = " ".join("fill%02d" % i for i in range(1, 13))
NOTES = {
    "02_WIKI/q.md": "# Q\ngate refuse run check ledger print\n",
    "02_WIKI/x.md": "# X\ngate refuse print\n",
    "02_WIKI/y.md": "# Y\ngate refuse run check " + FILLERS + "\n",
    "02_WIKI/t1.md": "# Twin\ngate refuse\n",
    "02_WIKI/t2.md": "# Twin\ngate refuse\n",
    "02_WIKI/z.md": "# Z\nisland vapor quorum\n",
}
# The corpus, declared here as sets rather than as prose, so every expectation below is computed
# from it. `test_the_index_holds_exactly_the_terms_declared_here` checks the fold against this.
EXPECTED_TERMS = {
    "02_WIKI/q.md": {"q", "gate", "refuse", "run", "check", "ledger", "print"},
    "02_WIKI/x.md": {"x", "gate", "refuse", "print"},
    "02_WIKI/y.md": {"y", "gate", "refuse", "run", "check"} | {"fill%02d" % i for i in range(1, 13)},
    "02_WIKI/t1.md": {"twin", "gate", "refuse"},
    "02_WIKI/t2.md": {"twin", "gate", "refuse"},
    "02_WIKI/z.md": {"z", "island", "vapor", "quorum"},
}
ORDER = ["02_WIKI/x.md", "02_WIKI/y.md", "02_WIKI/t1.md", "02_WIKI/t2.md"]


def is_shelf(path):
    """The same rule `kb.py` states: a document with no folder is the shelf, not a note."""
    return "/" not in str(path).replace("\\", "/")


def weights(terms_by_path):
    """{term: log(N / df)} over the pooled corpus — the same document-frequency idea bm25 uses."""
    total = len(terms_by_path)
    df = {}
    for terms in terms_by_path.values():
        for term in terms:
            df[term] = df.get(term, 0) + 1
    return {term: math.log(total / count) for term, count in df.items()}, df


def rank(terms_by_path, source_path):
    """The expected neighbours, computed from the declared sets: cosine of IDF-weighted vectors
    over the pooled notes, a zero-weight pair dropped, ties broken on (-shared, path) after the
    cosine itself ties. Shelf documents are neither a source nor a candidate."""
    if is_shelf(source_path):
        raise AssertionError("rank() is not asked about shelf documents: " + source_path)
    pool = {path: terms for path, terms in terms_by_path.items()
            if not is_shelf(path) and path != source_path}
    declared = dict(pool)
    declared[source_path] = terms_by_path[source_path]
    weight, df = weights(declared)
    source = declared[source_path]
    norm = {path: math.sqrt(sum(weight[t] ** 2 for t in terms))
            for path, terms in declared.items()}
    rows = []
    for path, terms in pool.items():
        shared = source & terms
        if not shared:
            continue
        score = sum(weight[t] ** 2 for t in shared) / (norm[source_path] * norm[path])
        if score <= 0.0:
            continue
        ordered = sorted(shared, key=lambda term: (-weight[term], term))
        rows.append({"path": path, "shared": len(shared), "score": score,
                     "terms": [[term, df[term]] for term in ordered]})
    rows.sort(key=lambda row: (-round(row["score"], 12), -row["shared"], row["path"]))
    return rows


def write_notes(root, notes):
    for rel, text in notes.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def run_kb(args, cwd=None, env=None):
    return subprocess.run([sys.executable, KB] + [str(a) for a in args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace",
                          cwd=str(cwd or ROOT), env=env)


def neighbours(stdout):
    """The listed paths in printed order — `search` prints the same shape."""
    return [line.split("  ")[0] for line in stdout.splitlines() if "  [" in line]


def counts(stdout):
    """{path: the shared-term count printed under it}, read line by line."""
    lines = stdout.splitlines()
    out = {}
    for index, line in enumerate(lines):
        if "  [" not in line:
            continue
        detail = lines[index + 1] if index + 1 < len(lines) else ""
        found = re.search(r"(\d+) shared term", detail)
        out[line.split("  ")[0]] = int(found.group(1)) if found else None
    return out


def term_sets(root):
    """{path: distinct folded terms} straight from the indexed rows, title included."""
    with closing(sqlite3.connect(str(Path(root) / ".kb" / "kb.sqlite"))) as conn:
        return {path: set(kb.terms_of(title)) | set(kb.terms_of(body))
                for path, title, _zone, body in
                conn.execute("SELECT path, title, zone, body FROM notes")}


class IndexFixture(unittest.TestCase):
    """A vault-shaped folder with a measured corpus, indexed by the real `ingest`."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        write_notes(self.root, NOTES)
        result = run_kb(["ingest", "--vault", self.root])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.vault = ["--vault", self.root]

    def related(self, *extra):
        return run_kb(["--related"] + list(extra) + self.vault)


class TheNeighboursComeFromTheIndex(IndexFixture):
    def test_related_names_the_note_it_answered(self):
        result = self.related("02_WIKI/q.md")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("related to 02_WIKI/q.md", result.stdout, result.stdout)

    def test_the_expected_order_is_printed(self):
        result = self.related("02_WIKI/q.md")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(ORDER, neighbours(result.stdout), result.stdout)

    def test_the_ratio_ranks_above_the_raw_count(self):
        """y shares four terms with q, x shares three — and x still wins, because the weight of a
        shared word is what makes it shared, not its presence in a list."""
        printed = counts(self.related("02_WIKI/q.md").stdout)
        self.assertEqual(4, printed["02_WIKI/y.md"], printed)
        self.assertEqual(3, printed["02_WIKI/x.md"], printed)
        self.assertLess(ORDER.index("02_WIKI/x.md"), ORDER.index("02_WIKI/y.md"))

    def test_the_query_is_never_its_own_neighbour(self):
        self.assertNotIn("02_WIKI/q.md", neighbours(self.related("02_WIKI/q.md").stdout))

    def test_a_note_sharing_no_term_is_never_listed(self):
        self.assertNotIn("02_WIKI/z.md", neighbours(self.related("02_WIKI/q.md").stdout))

    def test_the_shared_terms_are_printed_as_evidence(self):
        """Each line names the words it stood on, rarest first, with how many notes carry them."""
        top = rank(EXPECTED_TERMS, "02_WIKI/q.md")[0]
        expected = ", ".join("%s (%d of %d notes)" % (term, df, len(EXPECTED_TERMS))
                             for term, df in top["terms"])
        self.assertEqual("print (2 of 6 notes), gate (5 of 6 notes), refuse (5 of 6 notes)",
                         expected, expected)
        result = self.related("02_WIKI/q.md")
        self.assertIn(expected, result.stdout, result.stdout)

    def test_limit_caps_the_answer_without_changing_its_order(self):
        result = self.related("02_WIKI/q.md", "--limit", "2")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(ORDER[:2], neighbours(result.stdout), result.stdout)

    def test_both_invocation_forms_agree(self):
        flag = self.related("02_WIKI/q.md")
        command = run_kb(["related", "02_WIKI/q.md"] + self.vault)
        self.assertEqual(0, command.returncode, command.stdout + command.stderr)
        self.assertEqual(flag.stdout, command.stdout)

    def test_a_unique_title_resolves(self):
        result = self.related("Q")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("related to 02_WIKI/q.md", result.stdout, result.stdout)

    def test_a_unique_path_tail_resolves(self):
        result = self.related("x")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("related to 02_WIKI/x.md", result.stdout, result.stdout)
        # From x, q keeps the top place it had from q's side (they share the rare `print`), and the
        # twins fall below it: x-and-twin share only `gate` and `refuse`, words five notes of six
        # carry. The count says 3 shared beats 2; the weighting says why 3 of them are the same 2.
        self.assertEqual([row["path"] for row in rank(EXPECTED_TERMS, "02_WIKI/x.md")],
                         neighbours(result.stdout), result.stdout)
        self.assertEqual(["02_WIKI/q.md", "02_WIKI/t1.md", "02_WIKI/t2.md"],
                         neighbours(result.stdout)[:3], result.stdout)

    def test_the_same_input_prints_the_same_bytes_twice(self):
        self.assertEqual(self.related("02_WIKI/q.md").stdout,
                         self.related("02_WIKI/q.md").stdout)

    def test_the_order_does_not_depend_on_the_hash_seed(self):
        outs = []
        for seed in ("1", "7", "123456"):
            result = run_kb(["--related", "02_WIKI/q.md"] + self.vault,
                            env=dict(os.environ, PYTHONHASHSEED=seed))
            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            outs.append(result.stdout)
        self.assertEqual([outs[0], outs[0], outs[0]], outs)

    def test_no_socket_is_opened_to_answer(self):
        def refuse(*_args, **_kwargs):
            raise AssertionError("kb --related opened a socket")
        with patch.object(socket, "socket", refuse), \
                patch.object(socket, "create_connection", refuse):
            answer = kb.related(self.root, "02_WIKI/q.md")
        self.assertTrue(answer["neighbours"], answer)

    def test_the_index_holds_exactly_the_terms_declared_here(self):
        """The fold, not the fixture, is what the arithmetic below stands on."""
        self.assertEqual(EXPECTED_TERMS, term_sets(self.root))

    def test_the_answer_is_exactly_the_term_math_in_this_file(self):
        """Recomputed from the sets declared at the top of this file, not from what kb printed."""
        answer = kb.related(self.root, "02_WIKI/q.md", limit=50)
        expected = rank(EXPECTED_TERMS, "02_WIKI/q.md")
        self.assertEqual([row["path"] for row in expected],
                         [row["path"] for row in answer["neighbours"]])
        for want, got in zip(expected, answer["neighbours"]):
            self.assertEqual(want["shared"], got["shared"], want["path"])
            self.assertEqual(want["terms"], got["terms"], want["path"])
            self.assertAlmostEqual(want["score"], got["score"], places=9)
        self.assertEqual(ORDER, [row["path"] for row in expected], expected)

    def test_an_indexed_note_with_nothing_to_share_gets_an_honest_empty_answer(self):
        result = self.related("02_WIKI/z.md")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual([], neighbours(result.stdout), result.stdout)
        self.assertIn("shares a term", result.stdout, result.stdout)
        self.assertIn("not a failure", result.stdout, result.stdout)

    def test_related_reports_the_rows_it_had_to_choose_from(self):
        self.assertEqual(len(NOTES), kb.related(self.root, "02_WIKI/q.md")["indexed"])


class TheShelfIsNotANeighbour(IndexFixture):
    """`search` may answer with README.md; `--related` may not rank it.

    Measured on this repo, before the pool was narrowed: the neighbours of the memory-planes map
    came back as ROADMAP.md, CHANGELOG.md and HANDOFF.md. A document that mentions every word is
    near every note, which makes it a correct answer to a question nobody asked.
    """

    SHELF = "# Shelf\ngate refuse print ledger\n"  # three of q's seven terms, all of them shared

    def setUp(self):
        super().setUp()
        (self.root / "SHELF.md").write_text(self.SHELF, encoding="utf-8")
        result = run_kb(["ingest", "--vault", self.root])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_a_shelf_document_is_never_listed(self):
        result = self.related("02_WIKI/q.md", "--limit", "50")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertNotIn("SHELF.md", neighbours(result.stdout), result.stdout)

    def test_the_answer_says_the_shelf_was_skipped(self):
        self.assertIn("shelf document(s) at the repo root were not considered",
                      self.related("02_WIKI/q.md").stdout)

    def test_naming_a_shelf_document_is_refused_not_answered(self):
        result = self.related("SHELF.md")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout, result.stdout)
        self.assertIn("shelf document", result.stdout, result.stdout)
        self.assertIn("SHELF.md", result.stdout, result.stdout)
        self.assertEqual([], neighbours(result.stdout), result.stdout)

    def test_the_index_still_counts_it_and_the_pool_does_not(self):
        answer = kb.related(self.root, "02_WIKI/q.md", limit=50)
        self.assertEqual(len(EXPECTED_TERMS) + 1, answer["indexed"])
        self.assertEqual(1, answer["shelf"])
        self.assertEqual([row["path"] for row in rank(EXPECTED_TERMS, "02_WIKI/q.md")],
                         [row["path"] for row in answer["neighbours"]])

    def test_search_still_answers_from_the_shelf(self):
        result = run_kb(["search", "ledger", "--vault", self.root])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("SHELF.md", result.stdout, result.stdout)


class TheRefusals(IndexFixture):
    def test_a_note_the_index_does_not_hold_is_refused_not_emptied(self):
        result = self.related("02_WIKI/nope.md")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout, result.stdout)
        self.assertIn("02_WIKI/nope.md", result.stdout, result.stdout)
        self.assertIn("does not hold", result.stdout, result.stdout)
        self.assertEqual([], neighbours(result.stdout), result.stdout)
        self.assertNotIn("02_WIKI/x.md", result.stdout, result.stdout)

    def test_a_refusal_does_not_file_a_knowledge_gap(self):
        with closing(sqlite3.connect(str(self.root / ".kb" / "kb.sqlite"))) as conn:
            before = conn.execute("SELECT COUNT(*) FROM search_gaps").fetchone()[0]
        self.assertEqual(1, self.related("02_WIKI/nope.md").returncode)
        with closing(sqlite3.connect(str(self.root / ".kb" / "kb.sqlite"))) as conn:
            self.assertEqual(before, conn.execute("SELECT COUNT(*) FROM search_gaps").fetchone()[0])

    def test_a_file_the_corpus_rule_excludes_is_refused_by_that_rule(self):
        # Machine plane: it is on disk, `ingest` never indexed it, and --related says so instead
        # of answering "no neighbours" about a note it never read.
        write_notes(self.root, {"15_SYSTEM/private.md": "# Hidden\ngate refuse run check print\n"})
        result = self.related("15_SYSTEM/private.md")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout, result.stdout)
        self.assertIn("does not index", result.stdout, result.stdout)
        self.assertEqual([], neighbours(result.stdout), result.stdout)

    def test_an_ambiguous_name_is_refused_not_guessed(self):
        write_notes(self.root, {"02_WIKI/dup/twin.md": "# First twin\nclone shape pair\n",
                                "00_START_HERE/other/twin.md": "# Second twin\nclone shape pair\n"})
        result = run_kb(["ingest", "--vault", self.root])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        result = self.related("twin.md")
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout, result.stdout)
        self.assertIn("ambiguous", result.stdout, result.stdout)
        self.assertIn("02_WIKI/dup/twin.md", result.stdout, result.stdout)
        self.assertIn("00_START_HERE/other/twin.md", result.stdout, result.stdout)
        self.assertEqual([], neighbours(result.stdout), result.stdout)

    def test_no_index_at_all_is_refused_with_the_command_that_fixes_it(self):
        empty = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(empty, ignore_errors=True))
        result = run_kb(["--related", "02_WIKI/q.md", "--vault", empty])
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("no index", result.stdout, result.stdout)
        self.assertIn("ingest", result.stdout, result.stdout)

    def test_an_index_from_an_older_corpus_rule_is_refused(self):
        other = Path(tempfile.mkdtemp())
        self.addCleanup(lambda: shutil.rmtree(other, ignore_errors=True))
        write_notes(other, NOTES)
        self.assertEqual(0, run_kb(["ingest", "--vault", other]).returncode)
        with closing(sqlite3.connect(str(other / ".kb" / "kb.sqlite"))) as conn:
            conn.execute("DELETE FROM kb_meta")
            conn.commit()  # the rows stay, the schema marker does not — and an uncommitted
            # delete would roll back on close and test nothing at all.
        result = run_kb(["--related", "02_WIKI/q.md", "--vault", other])
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("older corpus rule", result.stdout, result.stdout)
        self.assertIn("ingest", result.stdout, result.stdout)

    def test_a_limit_that_is_not_positive_is_refused(self):
        for limit in ("0", "-3"):
            result = self.related("02_WIKI/q.md", "--limit", limit)
            self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertIn("positive", result.stderr, result.stderr)

    def test_related_needs_a_note(self):
        command = run_kb(["related"] + self.vault)      # command form, no note named
        self.assertNotEqual(0, command.returncode, command.stdout + command.stderr)
        self.assertIn("needs a note", command.stderr, command.stderr)
        flag = run_kb(["--related"] + self.vault)        # flag form with nothing to read
        self.assertNotEqual(0, flag.returncode, flag.stdout + flag.stderr)
        self.assertIn("expected one argument", flag.stderr, flag.stderr)

    def test_the_note_is_named_once(self):
        result = run_kb(["related", "02_WIKI/q.md", "--related", "02_WIKI/x.md"] + self.vault)
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("not both", result.stderr, result.stderr)

    def test_the_function_refuses_the_same_bad_limit_the_command_line_does(self):
        """Both entry points refuse, so nothing downstream can call past the gate."""
        with self.assertRaises(kb.RelatedError) as caught:
            kb.related(self.root, "02_WIKI/q.md", limit=0)
        self.assertIn("positive", str(caught.exception))
        self.assertEqual(1, len(caught.exception.lines), caught.exception.lines)

    def test_no_command_at_all_is_refused(self):
        result = run_kb(self.vault)
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("needs a command", result.stderr, result.stderr)

    def test_search_still_works_unchanged(self):
        result = run_kb(["search", "gate", "--vault", self.root])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertTrue(neighbours(result.stdout), result.stdout)


class NoVectorsWereActivated(unittest.TestCase):
    def test_kb_imports_only_the_standard_library_and_its_two_siblings(self):
        tree = ast.parse((SCRIPTS / "kb.py").read_text(encoding="utf-8"))
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imports.add(node.module.split(".")[0])
        self.assertLessEqual(imports, {"argparse", "datetime", "math", "re", "sqlite3", "sys",
                                       "unicodedata", "contextlib", "pathlib", "common",
                                       "sync_hosts"}, sorted(imports))

    def test_related_borrows_nothing_from_the_vector_seam(self):
        source = (SCRIPTS / "kb.py").read_text(encoding="utf-8")
        # grepped as calls/imports, not as words: the refusal messages say "no socket" and
        # "no embedding", and a test that failed on its own prose would be noise.
        for borrowed in ("Embedder", "cosine(", "hashlib", "numpy", "import socket",
                         "urllib", "requests", "openai"):
            self.assertNotIn(borrowed, source, borrowed)
        self.assertIn("no embedding", source, source)


class TheRealHouse(unittest.TestCase):
    NOTE = "02_WIKI/reference_maps/eight-memory-planes.md"

    @classmethod
    def setUpClass(cls):
        shutil.rmtree(ROOT / ".kb", ignore_errors=True)
        result = run_kb(["ingest"])
        assert result.returncode == 0, result.stdout + result.stderr
        cls.indexed = int(re.search(r"indexed (\d+) notes", result.stdout).group(1))

    def test_related_answers_about_a_note_this_repo_actually_carries(self):
        result = run_kb(["--related", self.NOTE])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        hits = neighbours(result.stdout)
        self.assertTrue(hits, result.stdout)
        self.assertLessEqual(len(hits), 5, result.stdout)
        self.assertNotIn(self.NOTE, hits)

    def test_every_neighbour_in_the_real_house_shares_the_terms_it_claims(self):
        result = run_kb(["--related", self.NOTE, "--limit", "10"])
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        terms = term_sets(ROOT)
        source = terms[self.NOTE]
        printed = counts(result.stdout)
        self.assertEqual(sorted(neighbours(result.stdout)), sorted(printed), result.stdout)
        for path, claimed in printed.items():
            self.assertIn(path, terms, "printed a note the index does not hold: " + path)
            real = len(source & terms[path])
            self.assertGreaterEqual(real, 1, path)
            self.assertEqual(real, claimed, "%s printed %d shared, the index says %d"
                             % (path, claimed, real))

    def test_a_note_the_real_index_does_not_hold_is_refused_here_too(self):
        result = run_kb(["--related", "02_WIKI/reference_maps/no-such-map.md"])
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout, result.stdout)
        self.assertEqual([], neighbours(result.stdout), result.stdout)

    def test_the_real_house_prints_no_shelf_document(self):
        """The rule exists because of this repo: unfiltered, the map's neighbours were ROADMAP,
        CHANGELOG and HANDOFF. Every neighbour now has to live inside a zone."""
        for note in (self.NOTE, "02_WIKI/reference_maps/superagi-to-hades-map.md"):
            result = run_kb(["--related", note, "--limit", "10"])
            self.assertEqual(0, result.returncode, note + result.stdout + result.stderr)
            hits = neighbours(result.stdout)
            self.assertTrue(hits, note + result.stdout)
            for path in hits:
                self.assertIn("/", path, "%s answered with a shelf document: %s" % (note, path))

    def test_the_real_house_refuses_its_own_roadmap(self):
        result = run_kb(["--related", "ROADMAP.md"])
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("shelf document", result.stdout, result.stdout)
        self.assertIn("ROADMAP.md", result.stdout, result.stdout)
        self.assertEqual([], neighbours(result.stdout), result.stdout)

    def test_the_real_house_answer_is_the_same_twice(self):
        first = run_kb(["--related", "02_WIKI/reference_maps/superagi-to-hades-map.md"])
        second = run_kb(["--related", "02_WIKI/reference_maps/superagi-to-hades-map.md"])
        self.assertEqual(0, first.returncode, first.stdout + first.stderr)
        self.assertEqual(first.stdout, second.stdout)

    def test_the_index_it_read_is_the_one_ingest_printed(self):
        self.assertEqual(self.indexed, len(term_sets(ROOT)))


if __name__ == "__main__":
    unittest.main()
