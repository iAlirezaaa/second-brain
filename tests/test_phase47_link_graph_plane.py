"""Phase 47 stage 0 — a recorded known-good base is a copy of the vault, not a second file.

`scripts/base.py --save` writes a full snapshot of the tree under `SNAPSHOT_ROOT`
(`15_SYSTEM/backups/known-good/<stamp>/`). That plane is gitignored, so a fresh clone never has
one — which is exactly why this defect only appears on the machine that is *using* the brain: as
soon as the owner records a base, every note exists twice inside the directory the link gate
walks.

`classify_links` builds its target index with `iter_markdown`, which is deliberately unfiltered
(a candidate row is not a note but is still a legitimate link target). The snapshot copies
therefore entered the stem index, each live stem gained a second file, and `resolve_link` hit its
own collision rule — the rule that exists to refuse *guessing* which of two real files the author
meant. The result: the same vault the author wrote became `ambiguous`, every edge was dropped
from the graph, and the graph readout reported a vault of 22 notes with 0 edges, no hub and 22
islands. Recording a base reddened the suite.

The law this test pins: a file inside a recorded base is a copy of a note the tool already knows
about, so it is not a candidate target for a link the author could have written. The exclusion is
computed *vault-relative* — judge a base as its own vault and its own links still resolve — and
it is scoped to `SNAPSHOT_ROOT` only, because the collision law must stay armed for two live
notes that genuinely share a stem.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import link_check  # noqa: E402
from common import SNAPSHOT_ROOT  # noqa: E402

BASE_STAMP = "20261102T000000Z"


def write(vault, rel, text):
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def record_base(vault, names):
    """Copy live notes into a recorded base, the way `base.py --save` copies the tree."""
    for name in names:
        write(vault, "%s/%s/%s" % (SNAPSHOT_ROOT, BASE_STAMP, name),
              (vault / name).read_text(encoding="utf-8"))


class TestRecordedBaseIsNotACollision(unittest.TestCase):
    """The regression: one note, one link, one recorded copy of that note."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_a_recorded_copy_does_not_make_the_original_link_ambiguous(self):
        write(self.vault, "hub.md", "See [[leaf]] for detail.\n")
        write(self.vault, "leaf.md", "A leaf note.\n")
        record_base(self.vault, ["leaf.md"])

        edges, broken = link_check.classify_links(self.vault)
        mine = [e for e in edges if e.source.name == "hub.md"]
        self.assertEqual(1, len(mine), "the hub's single link must still be one edge: %r" % edges)
        self.assertEqual("extracted", mine[0].label,
                         "a recorded base added a second file with the stem `leaf`; the author "
                         "still pointed at the one note they wrote. reason: %s" % mine[0].reason)
        self.assertEqual([], broken)

    def test_the_graph_shape_is_unchanged_by_recording_a_base(self):
        write(self.vault, "hub.md", "Two ways out: [[leaf]] and [[other]].\n")
        write(self.vault, "leaf.md", "A leaf note.\n")
        write(self.vault, "other.md", "Another leaf.\n")
        write(self.vault, "orphan.md", "Nothing links here.\n")

        before = link_check.graph_readout(self.vault)
        record_base(self.vault, ["hub.md", "leaf.md", "other.md", "orphan.md"])
        after = link_check.graph_readout(self.vault)

        self.assertEqual(before["notes_scanned"], after["notes_scanned"],
                         "recording a base must not add or remove a node from the graph")
        self.assertEqual(before["label_counts"], after["label_counts"])
        self.assertEqual(before["components"], after["components"])
        self.assertEqual(before["degree0"], after["degree0"])
        self.assertEqual(before["god_nodes"], after["god_nodes"])
        # and the shape itself is the one the author drew: a hub of degree 2, one orphan
        self.assertEqual(2, after["label_counts"]["extracted"])
        self.assertEqual(["orphan.md"], after["degree0"])
        self.assertEqual(["hub.md"], after["god_nodes"])
        self.assertEqual(2, after["god_degree"])
        self.assertEqual(2, after["components"], "the hub island plus the orphan")
        self.assertEqual([], [e.target for e in after["ambiguous"]])

    def test_a_live_stem_collision_is_still_ambiguous(self):
        """The negative: the exclusion must not disarm the collision law for real notes."""
        write(self.vault, "hub.md", "Which one? [[twin]]\n")
        write(self.vault, "one/twin.md", "First twin.\n")
        write(self.vault, "two/twin.md", "Second twin.\n")

        edges, _broken = link_check.classify_links(self.vault)
        mine = [e for e in edges if e.source.name == "hub.md"]
        self.assertEqual("ambiguous", mine[0].label,
                          "two live files share the stem, so the text cannot say which was meant")
        self.assertIsNone(mine[0].path)

    def test_a_base_judged_as_its_own_vault_still_resolves_its_links(self):
        """Vault-relative, not absolute: the recorded copy is a vault when asked to be one."""
        inner = "%s/%s" % (SNAPSHOT_ROOT, BASE_STAMP)
        write(self.vault, "%s/hub.md" % inner, "See [[leaf]].\n")
        write(self.vault, "%s/leaf.md" % inner, "A leaf note.\n")

        edges, broken = link_check.classify_links(self.vault / inner)
        self.assertEqual([], broken)
        self.assertEqual(1, len(edges))
        self.assertEqual("extracted", edges[0].label,
                          "the exclusion is computed against the vault being judged; a snapshot "
                          "opened as its own vault is the notes it contains")


class TestRealTreeWithARecordedBase(unittest.TestCase):
    """The measured tree, with a base recorded into it, must read the way it reads without one."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.mkdtemp(prefix="sb-real-tree-")
        cls.clone = Path(cls._tmp) / "repo"
        shutil.copytree(ROOT, cls.clone, ignore=shutil.ignore_patterns(".git", "__pycache__"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._tmp, ignore_errors=True)

    def test_recording_a_base_into_the_real_tree_leaves_the_readout_settled(self):
        tree = self.clone / "02_WIKI" / "indexes" / "reference-maps.md"
        self.assertTrue(tree.is_file(), "the real tree is expected to carry the reference map")
        before = link_check.graph_readout(self.clone)
        self.assertEqual([], before["ambiguous"], "the unamended tree is the baseline")

        # copy the whole 02_WIKI plane into a recorded base, the way --save copies it
        for note in sorted((self.clone / "02_WIKI").rglob("*.md")):
            rel = note.relative_to(self.clone).as_posix()
            (self.clone / SNAPSHOT_ROOT / BASE_STAMP / rel).parent.mkdir(
                parents=True, exist_ok=True)
            shutil.copyfile(note, self.clone / SNAPSHOT_ROOT / BASE_STAMP / rel)

        after = link_check.graph_readout(self.clone)
        self.assertEqual([], after["ambiguous"],
                         "recording a base turned %d settled edges into guesses: %s"
                         % (len(before["notes_scanned"]),
                            [e.target for e in after["ambiguous"]]))
        self.assertEqual([], after["broken"])
        self.assertEqual(before["label_counts"], after["label_counts"])
        self.assertEqual(before["god_nodes"], after["god_nodes"])
        self.assertEqual(before["components"], after["components"])
        self.assertEqual(len(before["degree0"]) + 1, after["components"],
                         "the readout's own invariant: islands = orphan notes + 1")


if __name__ == "__main__":
    unittest.main()
