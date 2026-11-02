"""Phase 44 item 1 — confidence on every edge of the link graph.

graphify's edge schema labels each relationship `EXTRACTED | INFERRED | AMBIGUOUS`, and its
own docs say the third label ("Uncertain — flagged in the report for manual review") means an
uncertain edge is escalated, not silently trusted. This repo's "AST" is the wikilink graph, so
the label is checkable straight from the source text — no model, no embedding, no graph library.

The rule the gate now encodes (see the module docstring in `scripts/link_check.py`):

  * extracted — the author's link text names exactly one file literally;
  * inferred  — the resolver had to deduce it (case-fold, slash, appended `.md`);
  * ambiguous — a link whose target is a `14_CANDIDATES/` row (waiting on a human), OR whose
                stem is shared by several files, so the text cannot say which one was meant.

The defect being killed is the old `files_by_stem = {p.stem.lower(): p ...}` dict: when two
files shared a stem it silently bound the link to whichever path sorted first and reported the
link as healthy. That silent first-wins is exactly what `test_a_colliding_stem_is_not_resolved_
by_first_wins` asserts against — it fails the moment a collision is trusted again.
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

# iter_notes judges a file as a note only when it is not prose, so the fixture names below stay
# clear of common.PROSE_NAMES ("README.md", "index.md", ...) and common.PROSE_DIRS ("docs",
# "skills", "14_CANDIDATES", ...). The candidate fixture deliberately uses the real
# 14_CANDIDATES directory: a candidate row is prose (never a judged source) but is still a
# valid link target, which is exactly what makes pointing at one ambiguous.


def build_vault(tmp, files):
    for name, content in files.items():
        path = tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp


def edge_for(vault, source, target):
    """The single classified edge from `source` to `target`, or None if it became `broken`."""
    edges, _broken = link_check.classify_links(vault)
    for edge in edges:
        if edge.source.name == source and edge.target == target:
            return edge
    return None


class TestEdgeConfidence(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    # --- extracted -------------------------------------------------------------

    def test_an_explicit_stem_the_author_named_is_extracted(self):
        build_vault(self.vault, {
            "hub.md": "See [[leaf]] for detail.\n",
            "leaf.md": "A leaf note.\n",
        })
        edge = edge_for(self.vault, "hub.md", "leaf")
        self.assertEqual(edge.label, "extracted")
        # the reason names the mechanism so a reader sees *why*, not just *what*
        self.assertIn("stem", edge.reason)
        self.assertEqual(edge.path.name, "leaf.md")

    def test_an_exact_relative_path_is_extracted(self):
        build_vault(self.vault, {
            "hub.md": "See [[notes/deep/target.md]].\n",
            "notes/deep/target.md": "Deep target.\n",
        })
        edge = edge_for(self.vault, "hub.md", "notes/deep/target.md")
        self.assertEqual(edge.label, "extracted")
        self.assertIn("exact path", edge.reason)

    # --- inferred --------------------------------------------------------------

    def test_a_case_folded_stem_is_inferred_not_extracted(self):
        # the author typed "Leaf"; the file is "leaf.md". Only the resolver's lower-casing
        # bridged them, so a machine deduced the target — inferred, with the fold named.
        build_vault(self.vault, {
            "hub.md": "See [[Leaf]].\n",
            "leaf.md": "A leaf note.\n",
        })
        edge = edge_for(self.vault, "hub.md", "Leaf")
        self.assertEqual(edge.label, "inferred")
        self.assertIn("case-folded", edge.reason)

    def test_a_path_needing_md_appended_is_inferred(self):
        build_vault(self.vault, {
            "hub.md": "See [[notes/deep/target]].\n",
            "notes/deep/target.md": "Deep target.\n",
        })
        edge = edge_for(self.vault, "hub.md", "notes/deep/target")
        self.assertEqual(edge.label, "inferred")
        self.assertIn("normalised", edge.reason)

    # --- ambiguous: a candidate row --------------------------------------------

    def test_a_link_into_the_candidate_shelf_is_ambiguous(self):
        build_vault(self.vault, {
            "hub.md": "Track [[cand-one]].\n",
            "14_CANDIDATES/cand-one.md": "a row awaiting a verdict\n",
        })
        edge = edge_for(self.vault, "hub.md", "cand-one")
        self.assertEqual(edge.label, "ambiguous")
        self.assertIn("candidate", edge.reason)
        self.assertEqual(edge.path.as_posix().split("/")[-2], "14_CANDIDATES")

    # --- ambiguous: the colliding stem (the first-wins defect) -----------------

    def test_a_colliding_stem_is_not_resolved_by_first_wins(self):
        # Two files share the stem "overview". The old dict silently bound [[overview]] to
        # whichever path sorted first (x/overview.md) and reported the link as healthy. The
        # text alone cannot say which file the author meant, so this MUST be ambiguous.
        # Reverting to first-wins would make this edge 'extracted'/'inferred' to one file and
        # fail this assertion — that is the bite.
        build_vault(self.vault, {
            "hub.md": "See [[overview]].\n",
            "x/overview.md": "first\n",
            "y/overview.md": "second\n",
        })
        edge = edge_for(self.vault, "hub.md", "overview")
        self.assertEqual(edge.label, "ambiguous")
        self.assertIsNone(edge.path)                       # bound to no single file
        self.assertIn("colliding stem", edge.reason)
        self.assertIn("x/overview.md", edge.reason)        # names every candidate
        self.assertIn("y/overview.md", edge.reason)

    def test_the_closed_vocabulary_holds_for_every_edge(self):
        build_vault(self.vault, {
            "hub.md": "[[leaf]] [[Leaf2]] [[cand]] [[overview]] [[nowhere]]\n",
            "leaf.md": "x\n", "leaf2.md": "x\n",
            "14_CANDIDATES/cand.md": "x\n",
            "x/overview.md": "x\n", "y/overview.md": "x\n",
        })
        edges, broken = link_check.classify_links(self.vault)
        for edge in edges:
            self.assertIn(edge.label, ("extracted", "inferred", "ambiguous"),
                          "label %r escapes the closed vocabulary" % edge.label)
        # the unresolvable link is a broken link, not an edge at all
        self.assertEqual([t for _s, t in broken], ["nowhere"])

    def test_a_healthy_path_beats_a_colliding_stem(self):
        # writing the full path disambiguates the collision — the path names exactly one file,
        # so it is inferred (`.md` appended), not ambiguous. Ambiguity is about the *stem*.
        build_vault(self.vault, {
            "hub.md": "I mean [[x/overview.md]] specifically.\n",
            "x/overview.md": "first\n", "y/overview.md": "second\n",
        })
        edge = edge_for(self.vault, "hub.md", "x/overview.md")
        self.assertEqual(edge.label, "extracted")          # author named the exact path
        self.assertEqual(edge.path.as_posix().split("/")[-2], "x")


class TestEscalationIsVisible(unittest.TestCase):
    """An uncertain edge is escalated — named in the report, never counted silently healthy."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_confidence_mode_names_every_ambiguous_edge(self):
        build_vault(self.vault, {
            "hub.md": "See [[overview]] and track [[cand-one]].\n",
            "x/overview.md": "a\n", "y/overview.md": "b\n",
            "14_CANDIDATES/cand-one.md": "a\n",
        })
        result = run_utf8([sys.executable, LINK_CHECK, "--vault", str(self.vault), "--confidence"])
        self.assertEqual(result.returncode, 0, result.stdout)
        out = result.stdout
        self.assertIn("ambiguous  2", out)                   # count per label ("  %-10s %d")
        self.assertIn("extracted  0", out)
        # each ambiguous edge is named with source and target path — escalated, not counted
        self.assertIn("hub.md -> [[overview]]", out)
        self.assertIn("hub.md -> [[cand-one]]", out)
        self.assertIn("14_CANDIDATES/cand-one.md", out)      # the candidate's real path
        self.assertIn("x/overview.md, y/overview.md", out)   # both colliding targets named

    def test_the_link_gate_still_passes_a_healthy_vault(self):
        # a link to an existing file is not *broken*, even when it is ambiguous; the gate
        # reports broken links, escalation is the confidence/readout's job.
        build_vault(self.vault, {
            "hub.md": "See [[leaf]] and [[cand]].\n",
            "leaf.md": "a\n", "14_CANDIDATES/cand.md": "a\n",
        })
        result = run_utf8([sys.executable, LINK_CHECK, "--vault", str(self.vault)])
        self.assertEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
