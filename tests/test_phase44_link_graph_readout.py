"""Phase 44 item 2 — the link-graph readout: degree-0 notes, bridge notes, god nodes.

The ROADMAP row says "a page nothing points to is a page retrieval cannot reach". That last
clause is wrong and this file corrects it: full-text retrieval (`scripts/kb.py`, FTS5) returns
every indexed note whether or not anything links it, so a degree-0 note is not unreachable by
*search*. The honest defect is navigation — a degree-0 note is one a reader or agent following
wikilinks from anywhere else can never arrive at. The readout's own wording says which it is.

Everything here is computed from the wikilinks the vault already has, with a dict and a BFS:
no NetworkX, no Leiden, no embeddings, no new dependency. The graph is undirected over the
vault's *notes*, and an `ambiguous` edge is excluded from it — an uncertain relation is
escalated by name, never folded into the structure as if it were a healthy connection.

`graph_readout(root)` names the file behind every measurement (the notes it scanned, each
degree-0 / bridge / hub path), so a clean number always says what it looked at: "0 degree-0
notes" over a scanned denominator of dozens is a measurement, but "0" over 0 scanned is silence
wearing a health badge — which is exactly what a phase-16 style invisible file would do.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import link_check  # noqa: E402
from common import run_utf8  # noqa: E402

LINK_CHECK = str(SCRIPTS / "link_check.py")
# the one human-written index over `02_WIKI/reference_maps/`; a class body cannot see its own
# attribute from inside a comprehension, so the vault's hub is named at module level
INDEX = "02_WIKI/indexes/reference-maps.md"
MAP_STEMS = ("superagi-to-hades-map", "harness2-to-hades-map", "claude-obsidian-to-hades-map",
             "elephant-goldfish-to-hades-map", "graphify-to-hades-map", "eight-memory-planes",
             "conversation-memory-path")
# every wikilink the shipped vault holds: the human index and the maps it links. The vault's whole
# link graph is this table, which is why `inferred` is zero everywhere else.
INDEX_LINKS = {(INDEX, "02_WIKI/reference_maps/%s.md" % stem) for stem in MAP_STEMS}


def _rel(value):
    """Repo-relative posix path, whether the gate handed back an absolute or a relative one."""
    path = Path(str(value).replace("\\", "/"))
    return (ROOT / path if not path.is_absolute() else path).resolve().relative_to(ROOT).as_posix()


def build_vault(tmp, files):
    for name, content in files.items():
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp


def note(*links):
    return "links: " + " ".join("[[%s]]" % s for s in links) + "\n"


class TestDegreeZero(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_an_unlinked_note_is_degree_zero_and_named(self):
        build_vault(self.vault, {
            "hub.md": note("leaf"),
            "leaf.md": "a leaf",
            "island.md": "nobody links this and it links nothing",
        })
        data = link_check.graph_readout(self.vault)
        self.assertEqual(data["degree0"], ["island.md"])
        # it is judged, so it is on the list of scanned notes — not skipped
        self.assertIn("island.md", data["notes_scanned"])

    def test_a_degree_zero_note_is_degree_zero_even_when_linked_to_nothing_healthy(self):
        # a note whose ONLY link points at a candidate row is escalated and excluded, so it is
        # still degree-0: an ambiguous edge never buys a page a way to be reached.
        build_vault(self.vault, {
            "hub.md": note("cand-one"),
            "14_CANDIDATES/cand-one.md": "a row awaiting a verdict",
        })
        data = link_check.graph_readout(self.vault)
        self.assertEqual(data["degree0"], ["hub.md"])
        self.assertEqual(len(data["ambiguous"]), 1)        # ...and it is escalated, not hidden


class TestBridges(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _two_triangles(self, joined):
        # two dense clusters (triangles, so no interior edge is a bridge); when `joined`, one
        # single link a1 -> b1 is the only thing holding the two clusters together.
        a1 = note("a2", "a3") + (note("b1") if joined else "")
        files = {
            "a1.md": a1,
            "a2.md": note("a1", "a3"),
            "a3.md": note("a1", "a2"),
            "b1.md": note("b2", "b3"),
            "b2.md": note("b1", "b3"),
            "b3.md": note("b1", "b2"),
        }
        build_vault(Path(self.vault), files)

    def test_one_link_joining_two_clusters_is_a_bridge(self):
        self._two_triangles(joined=True)
        data = link_check.graph_readout(self.vault)
        self.assertEqual(data["components"], 1)
        self.assertEqual(data["bridges"], [("a1.md", "b1.md")])       # exactly the join
        self.assertEqual(data["bridge_notes"], ["a1.md", "b1.md"])     # the two it joins
        self.assertEqual(data["degree0"], [])

    def test_separate_clusters_have_no_bridge_between_them(self):
        self._two_triangles(joined=False)
        data = link_check.graph_readout(self.vault)
        self.assertEqual(data["components"], 2)
        self.assertEqual(data["bridges"], [])                          # nothing joins them
        self.assertEqual(data["bridge_notes"], [])
        # interior triangle edges are NOT bridges — removing one leaves the cluster connected
        for left, right in data["bridges"]:
            self.assertNotIn({left, right}, ({"a1.md", "a2.md"}, {"b1.md", "b2.md"}))


class TestGodNodeAndEnumeration(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_the_most_connected_note_is_the_god_node(self):
        build_vault(self.vault, {
            "hub.md": note("a", "b", "c"),
            "a.md": "x", "b.md": "x", "c.md": "x",
        })
        data = link_check.graph_readout(self.vault)
        self.assertEqual(data["god_nodes"], ["hub.md"])
        self.assertEqual(data["god_degree"], 3)

    def test_the_readout_enumerates_every_page_it_judged(self):
        build_vault(self.vault, {
            "hub.md": note("leaf"),
            "leaf.md": "x",
            "orphan.md": "isolated",
        })
        data = link_check.graph_readout(self.vault)
        # every degree-0 / bridge / god path must be one of the scanned notes, and the scanned
        # set is exactly the notes iter_notes found — the denominator that makes "0" mean "0".
        judged = set(data["notes_scanned"])
        for path in data["degree0"]:
            self.assertIn(path, judged)
        self.assertEqual(judged, {"hub.md", "leaf.md", "orphan.md"})

    def test_scanning_nothing_is_reported_as_scanning_nothing(self):
        # a vault of only-prose files has no notes to judge; an honest readout says so with an
        # empty scanned list rather than a "0 degree-0" that reads like health.
        build_vault(self.vault, {
            "README.md": "documentation, [[not-a-note]]",
        })
        data = link_check.graph_readout(self.vault)
        self.assertEqual(data["notes_scanned"], [])
        self.assertEqual(data["degree0"], [])


class TestReadoutCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_readout_mode_says_navigation_not_search_and_names_files(self):
        build_vault(self.vault, {
            "hub.md": note("leaf"),
            "leaf.md": "x",
            "island.md": "isolated",
        })
        result = run_utf8([sys.executable, LINK_CHECK, "--vault", str(self.vault), "--readout"])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        out = result.stdout
        self.assertIn("notes scanned: 3", out)
        self.assertIn("degree-0 notes: 1", out)
        self.assertIn("island.md", out)
        # correction #1: the line names navigation, not retrieval
        self.assertIn("following links", out)
        self.assertIn("full-text search", out)
        self.assertIn("god-node", out)


class TestRealTreeMeasurement(unittest.TestCase):
    """The claim is a measurement over THIS repo — pinned to what writing a page cannot move.

    An earlier draft of this class froze every tally the readout printed (notes scanned,
    components, degree-0). That test failed the day the repo registered its own project record,
    because a new note legitimately adds a note and an island — and a test that goes red for
    honest growth trains the next author to bump the number instead of reading the tree. What is
    pinned here is what growth cannot change silently: the exact set of wikilinks the vault holds,
    the absence of deduced and escalated edges, the house rule the index states about its own maps,
    and the relations *between* the counts. Every failure message prints the live measurement.
    """

    INDEX = INDEX
    INDEX_LINKS = INDEX_LINKS

    def setUp(self):
        self.data = link_check.graph_readout(ROOT)

    def edges(self):
        """(source, resolved target) as repo-relative paths — the only form a citation may take."""
        found, _broken = link_check.classify_links(ROOT)
        return {(_rel(e.source), _rel(e.path)) for e in found}

    def test_no_edge_in_the_shipped_vault_was_deduced_or_left_ambiguous(self):
        """Every real link names exactly one file literally, so nothing here needed a guess."""
        self.assertEqual(self.data["label_counts"]["inferred"], 0, self.data["label_counts"])
        self.assertEqual(self.data["ambiguous"], [], self.data["ambiguous"])
        self.assertEqual(self.data["broken"], [], self.data["broken"])

    def test_the_graph_is_the_links_the_index_writes_and_nothing_else(self):
        self.assertEqual(self.edges(), self.INDEX_LINKS,
                         "the vault's wikilinks changed: %r" % sorted(self.edges()))

    def test_the_human_index_is_the_only_hub(self):
        self.assertEqual(self.data["god_nodes"], [self.INDEX], self.data["god_nodes"])
        self.assertEqual(self.data["god_degree"], len(self.INDEX_LINKS), self.data["god_degree"])

    def test_no_reference_map_is_a_note_nobody_links(self):
        """`reference-maps.md` states its own law — "no map is a note nobody links" — and this is
        that law as a gate. It was false the day it was written: `conversation-memory-path.md` sat
        in the folder unlinked while the index claimed otherwise. The fix was a row in the index,
        not an exception here."""
        orphans = [n for n in self.data["degree0"] if n.startswith("02_WIKI/reference_maps/")]
        self.assertEqual(orphans, [],
                         "a map the index does not link is unreachable by following links: %r"
                         % orphans)

    def test_the_counts_agree_with_each_other(self):
        # one linked cluster (the index and its maps) plus one island per degree-0 note
        self.assertEqual(self.data["components"], len(self.data["degree0"]) + 1,
                         "readout: %r" % self.data)
        self.assertTrue(set(self.data["degree0"]) <= set(self.data["notes_scanned"]))
        # a bridge is an edge, so the bridge set cannot be larger than the edge set
        self.assertLessEqual(len(self.data["bridges"]), sum(self.data["label_counts"].values()),
                             self.data["bridges"])

    def test_the_denominator_is_notes_and_not_contract_documents(self):
        """A prose contract file is not a note: its example links are documentation, not data."""
        scanned = set(self.data["notes_scanned"])
        self.assertIn(self.INDEX, scanned, sorted(scanned))
        for prose in ("README.md", "ROADMAP.md", "CHANGELOG.md", "AGENTS.md", "HANDOFF.md"):
            self.assertNotIn(prose, scanned, "%s is not a note: %r" % (prose, sorted(scanned)))
        self.assertGreater(len(scanned), len(self.INDEX_LINKS) + 1,
                           "the pass only saw the linked notes: a degree-0 count over a denominator "
                           "of nothing is silence wearing a health badge")


if __name__ == "__main__":
    unittest.main()
