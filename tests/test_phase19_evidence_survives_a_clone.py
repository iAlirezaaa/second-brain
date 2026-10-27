"""Phase 19 — evidence a fresh clone cannot open is not evidence.

CI went red on all four matrices while every gate was green on the machine that wrote the
code. The shelf row blamed a local SQLite index: `.kb/kb.sqlite` exists on the laptop that
ran the loop, is gitignored by design, and simply is not there in a clone. The gate was
right and the evidence was the lie — a claim pointed at a file only one reader could ever
open.

  1. `common.clone_readable` knows the documented git boundary, and knows the one shelf
     exception the boundary grants;
  2. `candidate_check` refuses a row whose evidence lives behind that boundary, even when
     the file exists right here;
  3. the loop stops writing such rows and exports the gap register as a tracked snapshot,
     so the next cycle's evidence is readable from a clone;
  4. nothing currently on the shelf repeats the mistake.
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402
from common import run_utf8  # noqa: E402

CHECK = str(SCRIPTS / "candidate_check.py")


class TestTheBoundaryIsKnown(unittest.TestCase):
    def test_the_helper_and_gitignore_agree_on_the_named_folders(self):
        """Two lists that describe one law will drift; this test is the tie between them."""
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for folder in (".kb/", "12_RUNTIME/", "13_LAB/"):
            self.assertIn(folder, ignore, "%s is ignored but the helper does not name it" % folder)
            self.assertTrue(common.clone_readable(folder + "x.md") is False,
                            "%s must not read as clone-safe" % folder)

    def test_a_file_that_exists_here_can_still_be_unreadable_there(self):
        tmp = Path(tempfile.mkdtemp())
        (tmp / ".kb").mkdir()
        db = tmp / ".kb" / "kb.sqlite"
        db.write_text("local state", encoding="utf-8")
        self.assertTrue(db.is_file(), "the fixture must reproduce the laptop case")
        self.assertFalse(common.clone_readable(".kb/kb.sqlite"))
        self.assertFalse(common.clone_readable("12_RUNTIME/notes.md"))
        self.assertFalse(common.clone_readable("some/dir/kb.sqlite"),
                         "an ignored suffix anywhere in the tree is still ignored")

    def test_the_tracked_shelf_exception_is_readable(self):
        self.assertTrue(common.clone_readable("14_CANDIDATES/loop/cand-x.md"))
        self.assertTrue(common.clone_readable("14_CANDIDATES/README.md"))
        self.assertFalse(common.clone_readable("14_CANDIDATES/scratch.md"),
                         "the rest of the quarantine folder is not in the clone")

    def test_ordinary_tracked_paths_pass(self):
        for rel in ("scripts/loop.py", "README.md", "vault-template/20_Notes/x.md",
                    "tests/", "rules/zones.json"):
            self.assertTrue(common.clone_readable(rel), "%s is tracked" % rel)

    def test_the_law_is_written_where_an_agent_reads_it(self):
        """A rule that lives only inside a helper is a rule one machine can see.

        The gate refused, CI went red on four matrices, and nothing in the entrypoint told
        the next agent why -- so the boundary is stated in the canon, and the canon is what
        every host projection points at.
        """
        canon = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("clone_readable", canon, "the helper is named nowhere an agent reads")
        self.assertIn("survive a clone", canon, "the evidence law itself is undocumented")
        for rel in ("CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md",
                    ".cursor/rules/agents.mdc", ".windsurf/rules/agents.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("AGENTS.md", text, "%s does not point at the canon" % rel)


class TestTheGateRefusesUnopenableEvidence(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "rules").mkdir()
        (self.root / "rules" / "zones.json").write_text('{"zones": {}}', encoding="utf-8")
        shutil.copy(str(ROOT / "rules" / "candidate.schema.json"), str(self.root / "rules"))
        shelf = self.root / "14_CANDIDATES" / "loop"
        shelf.mkdir(parents=True)
        (self.root / ".kb").mkdir()
        (self.root / ".kb" / "kb.sqlite").write_text("exists only here", encoding="utf-8")
        (shelf / "report-2026-01-01.md").write_text("# report\n", encoding="utf-8")
        (shelf / "ledger.jsonl").write_text("", encoding="utf-8")
        self.row = shelf / "cand-2026-01-01-t-01.md"

    def write_row(self, evidence):
        self.row.write_text(
            "---\nid: cand-2026-01-01-t-01\ntype: note\ntitle: t\nstatus: raw\nowner: agent\n"
            "created: 2026-01-01\nupdated: 2026-01-01\n"
            "dimension: domain\n"
            "cue: c\nlesson: l\nconfidence: 0.5\nverdict: proposed\ntopics: [loop]\n"
            "evidence:\n  - %s\n---\n\nbody\n" %
            evidence, encoding="utf-8")

    def check(self):
        return run_utf8([sys.executable, CHECK, "--root", str(self.root),
                         "--file", str(self.row)], cwd=str(ROOT))

    def test_evidence_behind_the_boundary_is_refused_even_though_the_file_exists(self):
        self.write_row(".kb/kb.sqlite")
        result = self.check()
        self.assertEqual(result.returncode, 1,
                         "a claim about a file that is not in the clone passed the gate")
        self.assertIn("boundary", result.stdout + result.stderr)

    def test_evidence_that_is_in_the_clone_is_accepted(self):
        self.write_row("14_CANDIDATES/loop/report-2026-01-01.md")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class TestTheLoopStopsWritingThem(unittest.TestCase):
    def metrics(self, snapshot):
        """The shape build_metrics actually produces, with only the gap signal lit."""
        quiet = {"script": "x", "returncode": 0, "problems": []}
        return {
            "link_check": dict(quiet), "frontmatter_check": dict(quiet),
            "tests": {"returncode": 0, "summary": "Ran 1 test"},
            "vault": {"stale_inbox": [], "orphans": [], "awaiting_approval": [],
                      "inbox_status_lived": 0},
            "kb_gaps": {"open": 3, "recent": ["x (today)"], "note": "3 unanswered search(es)",
                        "snapshot": snapshot},
            "hygiene": {"todo_hygiene": 0, "files_scanned": 1},
        }

    def test_the_kb_gap_signal_cites_a_snapshot_the_clone_can_read(self):
        import loop as loop_mod
        rows = loop_mod.candidates(self.metrics("14_CANDIDATES/loop/gaps.jsonl"), [])
        gap = [row for row in rows if row["cue"].startswith("a search in the index")]
        self.assertEqual(len(gap), 1, "the gap signal stopped producing a row")
        for item in gap[0]["evidence"]:
            self.assertTrue(common.clone_readable(item),
                            "the loop cites %s, which a clone cannot open" % item)

    def test_write_rows_drops_unreadable_evidence_even_when_the_snapshot_is_missing(self):
        """An index with no rows exports nothing; the row must then cite the report, not `''`."""
        import loop as loop_mod
        rows = loop_mod.candidates(self.metrics(""), [])
        gap = [row for row in rows if row["cue"].startswith("a search in the index")][0]
        tmp = Path(tempfile.mkdtemp())
        shelf = tmp / "14_CANDIDATES" / "loop"
        shelf.mkdir(parents=True)
        written = loop_mod.write_rows(tmp, [("cand-2026-01-01-t-02", gap)],
                                      "14_CANDIDATES/loop/report-2026-01-01.md", "2026-01-01")
        self.assertEqual(len(written), 1)
        text = (shelf / "cand-2026-01-01-t-02.md").read_text(encoding="utf-8")
        self.assertIn("14_CANDIDATES/loop/report-2026-01-01.md", text)
        self.assertNotIn("evidence:\n---", text, "the row was left with no evidence at all")

    def test_write_rows_drops_evidence_a_clone_cannot_open(self):
        import loop as loop_mod
        tmp = Path(tempfile.mkdtemp())
        shelf = tmp / "14_CANDIDATES" / "loop"
        shelf.mkdir(parents=True)
        (tmp / ".kb").mkdir()
        (tmp / ".kb" / "kb.sqlite").write_text("here, not there", encoding="utf-8")
        (shelf / "report-2026-01-01.md").write_text("# r\n", encoding="utf-8")
        row = {"priority": "P2", "dimension": "domain", "cue": "c", "lesson": "l",
               "confidence": 0.5, "detail": [],
               "evidence": [".kb/kb.sqlite", "14_CANDIDATES/loop/report-2026-01-01.md"]}
        written = loop_mod.write_rows(tmp, [("cand-2026-01-01-t-01", row)],
                                      "14_CANDIDATES/loop/report-2026-01-01.md", "2026-01-01")
        self.assertEqual(len(written), 1)
        text = (shelf / "cand-2026-01-01-t-01.md").read_text(encoding="utf-8")
        self.assertNotIn(".kb", text, "the row still cites the local index")
        self.assertIn("14_CANDIDATES/loop/report-2026-01-01.md", text)


class TestTheShelfAsShipped(unittest.TestCase):
    def test_no_committed_row_cites_the_git_boundary(self):
        shelf = ROOT / "14_CANDIDATES" / "loop"
        rows = sorted(shelf.glob("cand-*.md"))
        self.assertGreaterEqual(len(rows), 1, "the shelf is empty, so this proves nothing")
        for path in rows:
            fm, _ = common.parse_frontmatter(path.read_text(encoding="utf-8"))
            evidence = fm.get("evidence") or []
            evidence = evidence if isinstance(evidence, list) else [evidence]
            for item in evidence:
                self.assertTrue(common.clone_readable(str(item)),
                                "%s cites %s, which a fresh clone cannot open" %
                                (path.name, item))

    def test_a_pristine_clone_passes_the_candidate_gate(self):
        """The bug was invisible locally by construction: this sees only what a clone gets.

        Tracked files, copied with their bytes, no `.kb`, no runtime plane, no untracked
        scratch -- exactly the checkout CI runs the gates against.
        """
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        clone = Path(tmp.name)
        listing = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"],
                                 capture_output=True, text=True,
                                 encoding="utf-8", errors="replace")
        if listing.returncode != 0:
            self.skipTest("no git available to enumerate the tracked tree")
        paths = [rel for rel in listing.stdout.split("\0") if rel]
        self.assertGreater(len(paths), 50, "the enumeration found nothing to copy")
        for rel in paths:
            destination = clone / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(ROOT / rel), str(destination))
        self.assertFalse((clone / ".kb").exists(), "the local index leaked into the clone")

        result = run_utf8([sys.executable, str(clone / "scripts" / "candidate_check.py")],
                          cwd=str(clone))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
