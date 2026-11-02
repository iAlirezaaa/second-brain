"""Stage 0 — one declared plane: the link graph, the full-text index and the nightly loop must judge the same corpus.

Phase 47 taught the link gate that a known-good base recorded by `scripts/base.py --save` is a
copy of the vault, not a second file the author could have meant. The fix was local to
`link_check.py`: it imported `SNAPSHOT_ROOT` from `base.py` and computed its own exclusion. The
law it implements is not local. Three readers walk the tree, and a reader that has to be told
twice is a reader that will be told once.

Measured on the live tree of this repo on 2026-11-02, with one base recorded
(`20261102T145801Z`) and "inside a base" meaning a vault-relative path under
`SNAPSHOT_ROOT`:

    iter_markdown              189 files,  89 inside a base       <- the raw walk
    link_check.link_targets    100 files,   0 inside a base       <- fixed in phase 47
    kb.corpus                   58 files,   0 inside a base       <- clean already, via MACHINE_PLANE
    loop.vault_signals         174 orphans, 84 inside a base      <- still lying

The last line is the bug this test pins. The loop's nightly report calls a note an orphan when no
component of its path is a zone, and `15_SYSTEM/backups/known-good/...` names no zone -- so every
recorded snapshot contributes one phantom orphan per note. On the machine that actually uses the
brain, 84 of the 174 "orphans the owner should file" were bytes the owner had already filed; the
report was recommending work on copies of work already done.

The law: one predicate owns "is this path inside a recorded base", and it lives in
`scripts/common.py` -- `common.py` because `base.py` already imports `common`, so the constant
cannot live in `base.py` without a cycle. Every reader that judges the vault imports it. And the
exclusion stays scoped: a live note is still in the plane, two live notes sharing a stem are still
an ambiguous link, and a live orphan is still an orphan. Silence is not a fix.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import common  # noqa: E402
import kb  # noqa: E402
import link_check  # noqa: E402
import loop  # noqa: E402

BASE_STAMP = "20261102T000000Z"

LIVE_LINKED = "20_Notes/linked-note.md"
LIVE_ORPHAN = "20_Notes/live-orphan.md"
UNZONED_ORPHAN = "loose-orphan.md"


def write(vault, rel, text):
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class PlaneFixture(unittest.TestCase):
    """One vault: three live notes, then the same three copied into a recorded base."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)
        write(self.vault, LIVE_LINKED, "# Linked note\n\nSee [[live-orphan]].\n")
        write(self.vault, LIVE_ORPHAN, "# Live orphan\n\nNothing links here.\n")
        write(self.vault, UNZONED_ORPHAN, "# Loose orphan\n\nOutside every zone.\n")
        for rel in (LIVE_LINKED, LIVE_ORPHAN, UNZONED_ORPHAN):
            write(self.vault, "%s/%s/%s" % (common.SNAPSHOT_ROOT, BASE_STAMP, rel),
                  (self.vault / rel).read_text(encoding="utf-8"))

    def tearDown(self):
        self._tmp.cleanup()

    def base_rel(self, rel):
        return "%s/%s/%s" % (common.SNAPSHOT_ROOT, BASE_STAMP, rel)

    def assert_none_inside_base(self, rels, reader):
        hits = [r for r in rels if common.is_recorded_base(r)]
        self.assertEqual(hits, [], "%s judged %d file(s) that are copies inside a recorded base"
                         % (reader, len(hits)))


class TestTheLawHasOneHome(PlaneFixture):

    def test_common_declares_the_plane_and_owns_the_predicate(self):
        self.assertEqual(common.SNAPSHOT_ROOT, "15_SYSTEM/backups/known-good")
        self.assertTrue(common.is_recorded_base(self.base_rel(LIVE_ORPHAN)))
        self.assertTrue(common.is_recorded_base(common.SNAPSHOT_ROOT))
        self.assertFalse(common.is_recorded_base(LIVE_ORPHAN))

    def test_the_predicate_is_relative_and_bounded(self):
        # a sibling whose name merely starts with the prefix is not inside the base
        self.assertFalse(common.is_recorded_base("15_SYSTEM/backups/known-good-notes/x.md"))
        # judged by the path's own position, not by a tail that happens to match
        self.assertFalse(common.is_recorded_base("notes/15_SYSTEM/backups/x.md"))

    def test_base_and_link_check_defer_instead_of_redeclaring(self):
        import base
        self.assertIs(base.SNAPSHOT_ROOT, common.SNAPSHOT_ROOT)
        # the graph's own test agrees with the shared law on both sides of the boundary
        self.assertEqual(link_check.in_recorded_base(self.vault / self.base_rel(LIVE_ORPHAN),
                                                     self.vault),
                         common.is_recorded_base(self.base_rel(LIVE_ORPHAN)))
        self.assertEqual(link_check.in_recorded_base(self.vault / LIVE_ORPHAN, self.vault),
                         common.is_recorded_base(LIVE_ORPHAN))


class TestTheThreeReadersJudgeOnePlane(PlaneFixture):

    def test_the_link_graph_names_no_copy(self):
        targets = [p.relative_to(self.vault).as_posix() for p in link_check.link_targets(self.vault)]
        self.assert_none_inside_base(targets, "link_check.link_targets")
        self.assertIn(LIVE_LINKED, targets)

    def test_the_full_text_index_names_no_copy(self):
        rels = [rel for rel, _path in kb.corpus(self.vault)]
        self.assert_none_inside_base(rels, "kb.corpus")

    def test_the_nightly_loop_names_no_copy(self):
        """RED until `loop.py` uses the shared law: each copy currently counts as an orphan."""
        signals = loop.vault_signals(self.vault, str(self.vault / "no-proposals/*.json"))
        self.assert_none_inside_base(signals["orphans"], "loop.vault_signals")
        self.assertIn(UNZONED_ORPHAN, signals["orphans"])

    def test_a_live_note_in_a_zone_is_still_not_an_orphan(self):
        signals = loop.vault_signals(self.vault, str(self.vault / "no-proposals/*.json"))
        self.assertNotIn(LIVE_LINKED, signals["orphans"])
        self.assertNotIn(LIVE_ORPHAN, signals["orphans"])


class TestTheExclusionStaysScoped(PlaneFixture):
    """Guards: the fix must not widen into a general silence."""

    def test_two_live_notes_sharing_a_stem_are_still_ambiguous(self):
        write(self.vault, "30_Resources/live-orphan.md", "# Second live file, same stem\n")
        edges, _broken = link_check.classify_links(self.vault)
        ambiguous = [e for e in edges
                     if e.label == "ambiguous"
                     and e.source.relative_to(self.vault).as_posix() == LIVE_LINKED]
        self.assertTrue(ambiguous, "a real stem collision between two live notes stopped being refused")

    def test_deleting_the_recorded_base_changes_no_live_signal(self):
        with_base = set(loop.vault_signals(self.vault, str(self.vault / "none/*.json"))["orphans"])
        shutil.rmtree(self.vault / common.SNAPSHOT_ROOT)
        without_base = set(loop.vault_signals(self.vault, str(self.vault / "none/*.json"))["orphans"])
        self.assertEqual(with_base, without_base)


if __name__ == "__main__":
    unittest.main()
