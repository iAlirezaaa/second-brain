"""Phase 45 — every path the roadmap cites is a path a stranger can open.

Why this is a gate and not a rule in a document: on 2026-11-02 three phase-36 rows still read
`- [ ]` while the code they described had already shipped and been released (`git tag --contains
3cb54da` answers `v0.1.0 v0.2.0`). Hand-checking those rows also turned up citations that were
simply wrong — a command written with flags it does not take, and a function described as
returning a list when it returns a verdict dict. That is the same defect class `link_check.py`
reports for prose: a document stating something the filesystem disagrees with. So the roadmap
got its own refusing script.

The starting state was measured before the rule was written, over the shipped `ROADMAP.md`: 8
backticked paths in closed rows were abbreviated to `backend/…` — true as names, unopenable as
citations, because the repo holds them under `15_SYSTEM/scripts/backend/`. After those rows were
rewritten repo-relative, the gate's line on 2026-11-02 read (quoted as a dated measurement, not as
a fact to repeat elsewhere — every row added to the roadmap moves these numbers, and a document
that types them becomes the second truth this gate exists to refuse):

    OK — 80 row(s) in ROADMAP.md (71 closed, 9 open); 77 path citation(s) checked:
         DECLARED 3, EXISTS 73, FOREIGN 1; 29 closed row(s) carry no path citation at all …

The gate found two defects in itself while these tests were written, and both are pinned below:
a bare folder name (`reference_maps/`) resolved to an empty basename, which every file "declares",
so a folder existing nowhere read as evidence; and a directory's last word (`maps`) was accepted as
a declared witness. `TestWhatIsNotAPath` holds both.

The distinction the whole file turns on is **closed versus open**: a closed row claims work is
done, so a path it cites must resolve; an open row is a plan, and a plan punished for naming the
file it intends to write would only learn to be vaguer.

Every class below is red on the commit before `scripts/roadmap_check.py` exists.

What each class holds the change to:
  * TestClosedRowsMustResolve -- a closed row citing a path that is not here is refused, and a
    closed row citing one that is here passes with the counts printed.
  * TestOpenRowsMayPlan -- the same missing path in an open row is a plan, not a defect.
  * TestAbbreviatedCitations -- `backend/vector.py` is refused *with the real path in the advice*,
    because a citation a stranger cannot open from a clone is not evidence.
  * TestAnchorsAndMembers -- `file.py:999` past the end of the file, and `file.py::no_such_thing`,
    are refused even in an open row: those are stated as observations, not intentions.
  * TestWhatIsNotAPath -- bare folder names, flags, slugs and URLs are never treated as citations,
    so the gate cannot invent defects out of prose.
  * TestStateAndUpstream -- a journal a script declares, and a path belonging to an upstream repo,
    are NAMED and not refused: the gate reports what it cannot see instead of calling it green.
  * TestTheGateIsWired -- health's one-OK-line-per-gate invariant, and the installed home that
    inherits the plan rather than making one.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

import health  # noqa: E402
import roadmap_check as roadmap  # noqa: E402

GATE = str(SCRIPTS / "roadmap_check.py")


class Fixture:
    """A repo-shaped folder: a packaging manifest (so it reads as a checkout), one source tree,
    one roadmap. No git -- the gate must fall back to walking the folder, and a test that needs
    git truth is written against the real repo instead."""

    def __init__(self, plan):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
        backend = self.dir / "15_SYSTEM" / "scripts" / "backend"
        backend.mkdir(parents=True)
        (backend / "vector.py").write_text(
            "class Embedder:\n    pass\n\nEVIDENCE = 'state/activation.json'\n", encoding="utf-8")
        (backend / "schedules.py").write_text(
            "def is_due(spec):\n    return True\n", encoding="utf-8")
        (self.dir / "scripts").mkdir()
        (self.dir / "scripts" / "loop.py").write_text(
            "JOURNAL = '14_CANDIDATES/loop/recovery.jsonl'\n", encoding="utf-8")
        (self.dir / "state").mkdir()
        (self.dir / "state" / "activation.json").write_text("{}", encoding="utf-8")
        (self.dir / "02_WIKI").mkdir()
        (self.dir / "02_WIKI" / "a-map.md").write_text("note\n", encoding="utf-8")
        (self.dir / "02_WIKI" / "b-map.md").write_text("note\n", encoding="utf-8")
        self.plan = self.dir / "ROADMAP.md"
        self.plan.write_text(plan, encoding="utf-8")

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def run(self, expect_rc=0):
        result = subprocess.run([sys.executable, GATE, "--root", str(self.dir), "--check"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", cwd=str(ROOT))
        if expect_rc is not None and result.returncode != expect_rc:
            raise AssertionError("expected rc %d, got %d\nstdout:\n%s\nstderr:\n%s"
                                 % (expect_rc, result.returncode, result.stdout,
                                    result.stderr[-2000:]))
        return result.stdout


class TestClosedRowsMustResolve(unittest.TestCase):
    def test_a_closed_row_citing_a_path_that_is_not_here_is_refused(self):
        fix = Fixture("- [x] **S** The splitter lives in `scripts/split.py` and ships green.\n")
        try:
            out = fix.run(1)
            self.assertIn("REFUSED", out)
            self.assertIn("scripts/split.py", out)
            self.assertIn("closed row", out)
        finally:
            fix.close()

    def test_a_closed_row_citing_a_real_path_passes_and_counts_it(self):
        fix = Fixture("- [x] **S** `scripts/loop.py` runs the nightly loop.\n")
        try:
            out = fix.run(0)
            self.assertIn("OK", out)
            self.assertIn("1 path citation(s) checked", out)
            self.assertIn("EXISTS 1", out)
        finally:
            fix.close()

    def test_a_citation_on_a_continuation_line_belongs_to_its_row(self):
        """Folded rows are one claim: the refusal must name the row that opened, not stray text."""
        fix = Fixture("- [x] **S** The seam is wired:\n      and lives at `scripts/absent.py` today.\n")
        try:
            out = fix.run(1)
            self.assertIn("ROADMAP.md:1", out, out)
            self.assertIn("scripts/absent.py", out)
        finally:
            fix.close()


class TestOpenRowsMayPlan(unittest.TestCase):
    def test_an_open_row_may_name_a_file_it_has_not_written_yet(self):
        fix = Fixture("- [ ] **S** Split the reader out into `scripts/split.py` next phase.\n")
        try:
            out = fix.run(0)
            self.assertIn("OK", out)
            self.assertIn("PLANNED 1", out, out)
        finally:
            fix.close()

    def test_a_wrong_observation_is_refused_even_in_an_open_row(self):
        """`file.py:999` is stated as a fact about bytes that exist, so intent does not excuse it."""
        fix = Fixture("- [ ] **S** See `scripts/loop.py:999` for the door.\n")
        try:
            out = fix.run(1)
            self.assertIn("open row", out)
            self.assertIn("is not a line anyone can open", out)
        finally:
            fix.close()


class TestAbbreviatedCitations(unittest.TestCase):
    def test_a_short_name_for_a_real_file_is_refused_with_the_real_path(self):
        fix = Fixture("- [x] **S** `backend/vector.py` ships the Embedder seam.\n")
        try:
            out = fix.run(1)
            self.assertIn("15_SYSTEM/scripts/backend/vector.py", out, out)
            self.assertIn("repo-relative", out)
        finally:
            fix.close()

    def test_a_module_and_function_name_resolves_to_the_file_it_means(self):
        fix = Fixture("- [x] **S** `scripts/loop.py` calls `backend/schedules.is_due` first.\n")
        try:
            out = fix.run(1)
            self.assertIn("backend/schedules.is_due", out)
            self.assertIn("schedules.py", out, out)
        finally:
            fix.close()

    def test_the_canonical_form_with_a_member_passes(self):
        fix = Fixture("- [x] **S** `15_SYSTEM/scripts/backend/schedules.py::is_due` is the seam.\n")
        try:
            self.assertIn("EXISTS 1", fix.run(0))
        finally:
            fix.close()


class TestAnchorsAndMembers(unittest.TestCase):
    def test_a_line_anchor_inside_the_file_passes(self):
        fix = Fixture("- [x] **S** The door is at `scripts/loop.py:1`.\n")
        try:
            self.assertIn("EXISTS 1", fix.run(0))
        finally:
            fix.close()

    def test_a_member_the_file_does_not_define_is_refused(self):
        fix = Fixture("- [x] **S** `15_SYSTEM/scripts/backend/vector.py::NotThere` is the door.\n")
        try:
            out = fix.run(1)
            self.assertIn("does not contain", out)
        finally:
            fix.close()

    def test_a_member_the_file_does_define_passes(self):
        fix = Fixture("- [x] **S** `15_SYSTEM/scripts/backend/vector.py::Embedder` is the seam.\n")
        try:
            self.assertIn("EXISTS 1", fix.run(0))
        finally:
            fix.close()


class TestGlobs(unittest.TestCase):
    def test_a_glob_with_a_hit_counts_and_a_glob_with_none_is_refused(self):
        good = Fixture("- [x] **S** The maps live under `02_WIKI/*.md`.\n")
        bad = Fixture("- [x] **S** The maps live under `02_WIKI/maps/*.md`.\n")
        try:
            self.assertIn("EXISTS 1", good.run(0))
        finally:
            good.close()
        try:
            self.assertIn("REFUSED", bad.run(1))
        finally:
            bad.close()


class TestWhatIsNotAPath(unittest.TestCase):
    """Prose must not be mistaken for evidence, or the gate's first act is to invent defects."""

    def test_bare_folder_names_flags_slugs_urls_and_placeholders_are_not_citations(self):
        fix = Fixture(
            "- [x] **S** `scripts/loop.py` ships `reference_maps/` but not `indexes/`, runs "
            "`--check`, cites `Graphify-Labs/graphify`, `https://example.com/a/b.md`, "
            "`02_WIKI/<topic>.md` and version `v1.2.3`.\n")
        try:
            out = fix.run(0)
            self.assertIn("1 path citation(s) checked", out, out)
            self.assertIn("EXISTS 1", out)
        finally:
            fix.close()

    def test_a_directory_citation_is_judged_as_a_directory(self):
        """A nested folder is a location claim; a bare folder name is prose (see the class above)."""
        good = Fixture("- [x] **S** Every backend reader sits in `15_SYSTEM/scripts/`.\n")
        bad = Fixture("- [x] **S** Every map sits in `02_WIKI/maps/`.\n")
        try:
            self.assertIn("EXISTS 1", good.run(0))
        finally:
            good.close()
        try:
            self.assertIn("REFUSED", bad.run(1))
        finally:
            bad.close()

    def test_a_bare_folder_name_is_not_a_citation_and_cannot_be_declared_by_anything(self):
        """The empty-basename trap: `reference_maps/` judged as a path would ask code to declare the
        empty string, which every file does -- so a folder that exists nowhere reads as evidence."""
        fix = Fixture("- [x] **S** The maps live in `reference_maps/` and nothing else here.\n")
        try:
            out = fix.run(0)
            self.assertIn("0 path citation(s) checked", out, out)
        finally:
            fix.close()


class TestStateAndUpstream(unittest.TestCase):
    def test_a_journal_a_script_declares_is_accepted_and_named(self):
        """`recovery.jsonl` appears on the first recovery; the code naming it is the evidence."""
        fix = Fixture("- [x] **S** Each fall back is journalled in "
                      "`14_CANDIDATES/loop/recovery.jsonl`.\n")
        try:
            out = fix.run(0)
            self.assertIn("DECLARED 1", out, out)
        finally:
            fix.close()

    def test_a_path_from_an_upstream_repo_is_named_not_refused(self):
        # the file name below is invented rather than copied from upstream's real docs path,
        # because this test file is tracked source: quoting the path here would make the real gate
        # report upstream's own file as "declared by this repo" -- the observer effect the
        # DECLARED class has to be read with.
        fix = Fixture("- [x] **S** Taken from upstream's `docs/confidence-tagging-table.md`.\n")
        try:
            out = fix.run(0)
            self.assertIn("NOTED", out)
            self.assertIn("outside this clone", out, out)
            self.assertIn("FOREIGN 1", out)
        finally:
            fix.close()

    def test_a_path_outside_the_repo_boundary_is_refused(self):
        fix = Fixture("- [x] **S** The vault mirror lives at `/etc/brain/config.json`.\n")
        try:
            out = fix.run(1)
            self.assertIn("cannot be opened from a clone", out)
        finally:
            fix.close()


class TestTheUncitedCountIsMeasured(unittest.TestCase):
    def test_a_closed_row_with_no_citation_is_counted_not_refused(self):
        """The honest gap in a roadmap is evidence never written down; it is shown as a number
        that can only go down, not hidden behind a refusal that would be paid for in invention."""
        fix = Fixture("- [x] **S** Filed every gap as an issue and closed it.\n")
        try:
            out = fix.run(0)
            self.assertIn("1 closed row(s) carry no path citation at all", out, out)
            self.assertIn("OK", out)
        finally:
            fix.close()


class TestTheRealRepoAndTheRealGate(unittest.TestCase):
    def test_the_shipped_roadmap_passes_its_own_gate(self):
        result = subprocess.run([sys.executable, GATE, "--root", str(ROOT), "--check"],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", cwd=str(ROOT))
        self.assertEqual(result.returncode, 0,
                         "the roadmap is not telling the truth about its own paths:\n%s%s"
                         % (result.stdout[-4000:], result.stderr[-1500:]))
        self.assertTrue(result.stdout.strip().splitlines()[-1].startswith("OK"), result.stdout)

    def test_the_gate_ships_inside_health_with_one_ok_line_per_gate(self):
        self.assertTrue([entry for entry in health.GATES
                         if entry.split()[0] == "roadmap_check.py"],
                        "a capability no gate runs is a capability nobody keeps: %r"
                        % health.GATES)
        result = subprocess.run([sys.executable, str(SCRIPTS / "health.py")],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", cwd=str(ROOT))
        ok_lines = [line for line in result.stdout.splitlines() if line.startswith("OK")]
        self.assertEqual(result.returncode, 0, result.stdout[-4000:])
        self.assertEqual(len(ok_lines), len(health.GATES),
                         "health ran %d gate(s) but printed %d OK line(s)"
                         % (len(health.GATES), len(ok_lines)))
        self.assertNotIn("\ufffd", result.stdout, "a gate writing cp1252 bytes arrives as mojibake")

    def test_an_installed_home_inherits_the_plan_instead_of_making_one(self):
        home = Path(tempfile.mkdtemp())
        try:
            (home / "ROADMAP.md").write_text(
                "- [x] **S** cites `tests/test_that_a_home_never_receives.py`\n", encoding="utf-8")
            result = subprocess.run([sys.executable, GATE, "--root", str(home), "--check"],
                                    capture_output=True, text=True, encoding="utf-8",
                                    errors="replace", cwd=str(ROOT))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len([l for l in result.stdout.splitlines() if l.startswith("OK")]), 1)
            self.assertIn("installed brain home", result.stdout, result.stdout)
        finally:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
