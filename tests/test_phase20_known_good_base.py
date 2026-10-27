"""Phase 20 -- keep_base as a mechanism: a measured base, and a way back to it.

The spine borrowed from harness2 has one piece still unshipped: when a change measures
worse, the honest move is to fall back to the last state that was measured *good*, and to
say so in the ledger (`fell_back: true`). "Last known good" cannot be a memory -- it has to
be bytes on disk plus a fingerprint that proves those bytes are what the record claims.

What `scripts/base.py` promises, and what these tests hold it to:

  1. a base is *measured*: `--save` runs the gates and refuses to record a red house;
  2. the base is content-addressed: the recorded fingerprint is the tree minus its paperwork,
     so filing a decision never invalidates the thing you can fall back to;
  3. `--recover` restores those bytes, re-verifies the fingerprint, and records the act;
  4. recovery reverts the brain, not the lessons: rows written to the shelf after the base
     survive it, and files added since the base are left where they are and named;
  5. a journal entry is not an artifact: if the bytes the journal names are gone, recovery
     refuses instead of quietly doing nothing;
  6. nothing restores outside the repo, whatever a manifest claims.
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

BASE = str(SCRIPTS / "base.py")
BASES_JOURNAL = "14_CANDIDATES/loop/bases.jsonl"
RECOVERY_JOURNAL = "14_CANDIDATES/loop/recovery.jsonl"
_SNAPSHOT_CACHE = []
_MASTER = None


def tracked_files():
    listing = subprocess.run(["git", "-C", str(ROOT), "ls-files", "-z"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
    return [rel for rel in listing.stdout.split("\0") if rel]


def green_master():
    """One verified clone replica, built once: proving the house is green costs a gate run."""
    global _MASTER
    if _MASTER is None:
        tmp = Path(tempfile.mkdtemp())
        for rel in tracked_files():
            destination = tmp / rel
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(str(ROOT / rel), str(destination))
        result = run_utf8([sys.executable, str(tmp / "scripts" / "health.py")], cwd=str(tmp))
        if result.returncode != 0:
            raise AssertionError("the fixture clone is not green:\n%s%s"
                                 % (result.stdout, result.stderr))
        _MASTER = tmp
    return _MASTER


def green_root():
    """A private copy of that replica: `--save` refuses a red house, so the fixture has to be
    a house that can be saved, and the only honest way to get one is to build the clone and
    run the gates inside it. Each test mutates its own copy, never the master."""
    holder = Path(tempfile.mkdtemp())
    destination = holder / "repo"
    shutil.copytree(str(green_master()), str(destination))
    _SNAPSHOT_CACHE.append(holder)
    return destination


def run(root, *args):
    return run_utf8([sys.executable, BASE, "--root", str(root)] + list(args), cwd=str(root))


def journal(root, name):
    path = root / name
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class TestABaseIsMeasuredNotAssumed(unittest.TestCase):
    def setUp(self):
        self.root = green_root()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_save_refuses_a_house_whose_gates_are_red_and_records_nothing(self):
        # break a gate: a shelf row whose evidence points at nothing
        row = self.root / "14_CANDIDATES" / "loop" / "cand-2026-01-01-t-99.md"
        row.write_text("---\nid: cand-2026-01-01-t-99\ntype: note\ntitle: t\nstatus: raw\n"
                       "owner: agent\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
                       "dimension: domain\ncue: c\nlesson: l\nconfidence: 0.5\n"
                       "verdict: proposed\nevidence:\n  - nowhere/does-not-exist.md\n---\n\nx\n",
                       encoding="utf-8")
        events = self.root / "14_CANDIDATES" / "loop" / "ledger.jsonl"
        with events.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"date": "2026-01-01T00:00:00Z", "id": "cand-2026-01-01-t-99",
                                     "event": "proposed", "priority": "P1", "dimension": "domain",
                                     "cue": "c"}) + "\n")
        result = run(self.root, "--save", "--note", "should not be allowed")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout)
        self.assertEqual(journal(self.root, BASES_JOURNAL), [],
                         "a red house was recorded as a known good base")

    def test_save_records_the_fingerprint_the_gates_just_saw(self):
        result = run(self.root, "--save", "--note", "test base")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = journal(self.root, BASES_JOURNAL)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["fingerprint"], common.state_fingerprint(self.root))
        self.assertEqual(rows[0]["gates"], "green")
        self.assertGreater(rows[0]["files"], 50, "a base of an empty tree proves nothing")
        self.assertTrue((self.root / rows[0]["snapshot"]).is_dir(),
                        "the journal names a snapshot folder that does not exist")
        for rel in list(common.tree_inventory(self.root,
                                              common.PAPERWORK_SKIP_PATHS))[:5]:
            self.assertTrue(common.clone_readable(rel), "%s is in the base but not in a clone" % rel)

    def test_saving_twice_with_nothing_changed_records_one_base(self):
        run(self.root, "--save", "--note", "first")
        result = run(self.root, "--save", "--note", "second")
        self.assertIn("ALREADY", result.stdout)
        self.assertEqual(len(journal(self.root, BASES_JOURNAL)), 1,
                         "the same state was recorded as two bases, so the list lies about history")

    def test_the_backups_folder_is_paperwork_not_the_state_of_the_brain(self):
        """Without this the act of saving would invalidate the thing it saved."""
        before = common.state_fingerprint(self.root)
        run(self.root, "--save", "--note", "measure me")
        self.assertEqual(common.state_fingerprint(self.root), before,
                         "writing a snapshot moved the brain's identity")


class TestRecoveryGoesBack(unittest.TestCase):
    def setUp(self):
        self.root = green_root()
        saved = run(self.root, "--save", "--note", "known good")
        self.assertEqual(saved.returncode, 0, saved.stdout + saved.stderr)
        self.base = journal(self.root, BASES_JOURNAL)[-1]
        self.base_fp = self.base["fingerprint"]

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def victim_path(self):
        """Any file the base actually holds -- the point is that the change is inside the base."""
        manifest = json.loads((self.root / self.base["snapshot"] / "manifest.json")
                              .read_text(encoding="utf-8"))
        notes = [rel for rel in sorted(manifest["files"])
                 if rel.startswith("vault-template/") and rel.endswith(".md")]
        return self.root / (notes[0] if notes else "README.md")

    def break_a_note(self):
        victim = self.victim_path()
        original = victim.read_text(encoding="utf-8")
        victim.write_text(original + "\nthe change that measured worse\n", encoding="utf-8")
        return victim, original

    def test_recover_restores_the_bytes_and_proves_the_fingerprint(self):
        victim, original = self.break_a_note()
        self.assertNotEqual(common.state_fingerprint(self.root), self.base_fp)
        result = run(self.root, "--recover", "--note", "the probe said hurt")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RECOVERED", result.stdout)
        self.assertEqual(victim.read_text(encoding="utf-8"), original,
                         "the file still holds the change recovery was supposed to undo")
        rows = journal(self.root, RECOVERY_JOURNAL)
        self.assertEqual(len(rows), 1)
        self.assertIs(rows[0]["fell_back"], True)
        self.assertEqual(rows[0]["to_fingerprint"], self.base_fp)
        self.assertNotEqual(rows[0]["from_fingerprint"], self.base_fp)
        self.assertTrue(common.state_fingerprint(self.root) == self.base_fp,
                        "recovery claimed success without returning to the recorded state")

    def test_recovery_reverts_the_brain_and_keeps_the_lessons(self):
        """Paperwork is not the brain: a row raised after the base must survive the fall back."""
        self.break_a_note()
        row = self.root / "14_CANDIDATES" / "loop" / "cand-2026-01-02-t-01.md"
        row.write_text("# raised after the base\n", encoding="utf-8")
        result = run(self.root, "--recover")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(row.is_file(), "recovery deleted work it was never given permission to lose")
        manifest = json.loads((self.root / self.base["snapshot"] / "manifest.json")
                              .read_text(encoding="utf-8"))
        self.assertFalse([rel for rel in manifest["files"] if rel.startswith("14_CANDIDATES")],
                         "the shelf is inside the base, so falling back would rewrite the ledger")

    def test_a_file_added_since_the_base_is_left_in_place_and_named(self):
        extra = self.root / "vault-template" / "20_Notes" / "added-later.md"
        extra.parent.mkdir(parents=True, exist_ok=True)
        extra.write_text("---\ntype: note\ntitle: 'Later'\nstatus: raw\nowner: human\n"
                         "created: 2026-01-02\nupdated: 2026-01-02\n---\n\nnew\n", encoding="utf-8")
        self.break_a_note()
        result = run(self.root, "--recover")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(extra.is_file(), "recovery deleted a file it was only supposed to report")
        row = journal(self.root, RECOVERY_JOURNAL)[-1]
        self.assertIn("vault-template/20_Notes/added-later.md", row["added_since"])
        self.assertIs(row["verified"], True,
                      "extras must be excluded from the identity check, not break it")

    def test_recovering_a_state_that_is_already_the_base_does_nothing(self):
        result = run(self.root, "--recover")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NOTHING", result.stdout)
        self.assertEqual(journal(self.root, RECOVERY_JOURNAL), [],
                         "a no-op was written to the journal as a fall back")

    def test_a_base_that_was_never_recorded_refuses(self):
        fresh = green_root()
        result = run(fresh, "--recover")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("base", result.stdout.lower())
        shutil.rmtree(str(fresh), ignore_errors=True)

    def test_a_journal_entry_whose_bytes_are_gone_is_refused_not_faked(self):
        """The record of a base is not the base -- exactly the local-state trap from issue 11."""
        shutil.rmtree(str(self.root / self.base["snapshot"]), ignore_errors=True)
        result = run(self.root, "--recover")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("snapshot", result.stdout.lower())
        self.assertEqual(journal(self.root, RECOVERY_JOURNAL), [],
                         "a recovery that restored nothing was recorded as a fall back")

    def test_a_manifest_cannot_write_outside_the_repo(self):
        manifest_path = self.root / self.base["snapshot"] / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"]["../../../escaped.md"] = "0" * 40
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        self.break_a_note()
        result = run(self.root, "--recover")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout)
        self.assertFalse((self.root.parent / "escaped.md").exists(),
                         "recovery obeyed a manifest that pointed outside the repo")


class TestTheCommandIsDiscoverable(unittest.TestCase):
    def test_status_reports_the_base_and_the_current_state(self):
        root = green_root()
        run(root, "--save", "--note", "for status")
        (root / "vault-template" / "README.md").write_text("changed\n", encoding="utf-8")
        result = run(root, "--status")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        out = result.stdout
        self.assertIn("base", out.lower())
        self.assertIn("current", out.lower())
        self.assertIn("DIFFERS", out)
        shutil.rmtree(str(root), ignore_errors=True)

    def test_the_law_is_written_in_the_canon(self):
        """A mechanism nobody is told about is a mechanism nobody uses."""
        canon = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("base.py", canon)
        self.assertIn("known good", canon)
        for rel in ("CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md",
                    ".cursor/rules/agents.mdc", ".windsurf/rules/agents.md"):
            self.assertIn("AGENTS.md", (ROOT / rel).read_text(encoding="utf-8"),
                          "%s hides the canon" % rel)

    def test_the_journals_are_citable_evidence(self):
        """Issue 11's law, applied to this feature's own output."""
        for rel in (BASES_JOURNAL, RECOVERY_JOURNAL):
            self.assertTrue(common.clone_readable(rel), "%s is behind the boundary" % rel)


if __name__ == "__main__":
    unittest.main()
