"""Phase 46: an installed brain moves to a new engine without losing what was written in it.

The starting state, measured rather than remembered. Before this phase, on 2026-11-02, this was
the whole upgrade story a home had:

    $ python scripts/install.py --target <a folder that is already a brain>
    [argparse] error: target <folder> is not empty — pick a fresh folder

`scripts/install.py` refused a non-empty home and offered nothing else, so staying current meant
installing beside the old brain and merging by hand — and the human plane (notes, the lesson
ledger, `12_RUNTIME/`, `14_CANDIDATES/`) is exactly the part a merge can lose. The refusal was
right for a flat copy; the flat copy was the limitation.

The fix is a record, not a smarter overwrite. An install now hashes every path it laid into
`15_SYSTEM/generated/install.json` (`files` = the bytes the home ended up holding, `engine_bytes` =
the bytes the repo's source carried), under the `install-manifest` contract in
`scripts/schema_stamp.py`. `--upgrade` compares three hashes per path — the record's, the home's,
the engine's — and can therefore tell an edit from an outdated file. The tests below pin the eight
verdicts, the protection of the brain's own folders, the self-proving `--dry-run`, and the one
property that matters most: after any act, the bytes a person wrote are still those bytes.

The fast classes build a miniature repo (a real `system.json`, a handful of shipped files) so the
installer's arithmetic runs in milliseconds; the last class installs a real home and proves the
installed gates still go green over the record.
"""
import json
import sys
import tempfile
import unittest
from datetime import date as _date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from common import run_utf8, tree_fingerprint  # noqa: E402
import health  # noqa: E402
import install as install_mod  # noqa: E402
import schema_stamp  # noqa: E402

INSTALL = str(SCRIPTS / "install.py")
MANIFEST_REL = install_mod.MANIFEST_REL
JOURNAL_REL = install_mod.JOURNAL_REL
MINI_CONFIG = json.loads((ROOT / "15_SYSTEM" / "config" / "system.json").read_text(encoding="utf-8"))


def write(path, text):
    """Bytes with one newline shape, so a hash in a test means the same on every platform.

    `write_text` on Windows turns every "\n" into "\r\n"; a fixture whose bytes depend on the
    platform it was built on cannot test a hash comparison honestly.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


class MiniRepo(object):
    """A repository small enough to install in a tenth of a second, shaped like the real one."""

    def __init__(self, folder):
        self.root = Path(folder)
        write(self.file("VERSION"), "9.9.9\n")
        write(self.file("15_SYSTEM/config/system.json"), json.dumps(MINI_CONFIG, indent=2))
        write(self.file("15_SYSTEM/README.md"), "# machine plane\n")
        write(self.file("15_SYSTEM/memory/README.md"), "# the ledger\n")
        write(self.file("15_SYSTEM/scripts/hades.py"), "# the registry door\n")
        write(self.file("scripts/health.py"), "print('the engine')\n")
        write(self.file("scripts/common.py"), "VERSION = 1\n")
        write(self.file("rules/zones.json"), "{}\n")
        write(self.file("skills/weekly-ritual/SKILL.md"), "# ritual\n")
        for name in install_mod.DOCS:
            write(self.file(name), "# %s\n\nbody\n" % name)
        write(self.file("00_START_HERE/START.md"), "# start\n")
        write(self.file("02_WIKI/reference_maps/eight-memory-planes.md"), "# map\n")
        write(self.file("vault-template/index.md"), "# starter\n")
        write(self.file("vault-template/_templates/note.md"), "# template\n")
        write(self.file("14_CANDIDATES/README.md"), "# the shelf contract\n")
        write(self.file(install_mod.PROOF), "# the installed proof\n")

    def file(self, rel):
        return self.root / rel

    def write(self, rel, text):
        return write(self.file(rel), text)

    def config(self):
        return json.loads((self.file("15_SYSTEM/config/system.json")).read_text(encoding="utf-8"))

    def plan(self):
        return install_mod.ship_plan(self.root, self.config())

    def run(self, *args):
        return run_utf8([sys.executable, INSTALL, "--repo", str(self.root)] + list(args),
                        cwd=str(ROOT))


class Home(object):
    """An installed brain: a folder, its record, and the bytes its owner wrote into it."""

    def __init__(self, folder):
        self.root = Path(folder)

    def file(self, rel):
        return self.root / rel

    def write(self, rel, text):
        return write(self.file(rel), text)

    def manifest(self):
        return json.loads(self.file(MANIFEST_REL).read_text(encoding="utf-8"))

    def journal(self):
        return [json.loads(line) for line in
                self.file(JOURNAL_REL).read_text(encoding="utf-8").splitlines() if line.strip()]

    def install(self, repo):
        return repo.run("--target", str(self.root))


class TestShipPlan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = MiniRepo(Path(self._tmp.name) / "repo")
        self.addCleanup(self._tmp.cleanup)
        self.plan = self.repo.plan()

    def test_the_plan_is_the_install(self):
        """One list decides both acts, or the upgrade judges files the installer never wrote."""
        self.assertIn("README.md", self.plan)
        self.assertIn("scripts/common.py", self.plan)
        self.assertIn("02_WIKI/reference_maps/eight-memory-planes.md", self.plan)
        self.assertIn("15_SYSTEM/config/system.json", self.plan)
        self.assertIn("15_SYSTEM/memory/lessons.jsonl", self.plan)
        for zone in MINI_CONFIG.get("zones") or []:
            self.assertIn("%s/.gitkeep" % zone["dir"], self.plan)

    def test_a_door_the_repo_has_not_rendered_is_still_shipped_as_a_render(self):
        """No CLAUDE.md in the mini repo, so the door's bytes are computed here, not copied."""
        entry = self.plan["CLAUDE.md"]
        self.assertEqual("render", entry.kind)
        self.assertIn("AGENTS.md", entry.source.decode("utf-8"))

    def test_the_lesson_ledger_never_arrives_with_the_repos_lessons_in_it(self):
        """Upstream memory stays upstream: the home's ledger is created empty or left alone."""
        self.repo.write("15_SYSTEM/memory/lessons.jsonl", '{"id": "upstream"}\n')
        self.assertEqual("touch", self.repo.plan()["15_SYSTEM/memory/lessons.jsonl"].kind)

    def test_a_plan_that_names_the_brains_own_state_is_a_bug_in_this_script(self):
        """`protected()` guards the plan itself, so a future line cannot ship into 12_RUNTIME."""
        for rel in ("12_RUNTIME/cache.bin", "13_LAB/x.md", "14_CANDIDATES/loop/run.json",
                    ".kb/index.sqlite", "15_SYSTEM/memory/lessons.jsonl"):
            entry = install_mod.Entry(rel, rel, "copy")
            self.assertTrue(install_mod.protected(rel) and entry.moves_bytes, rel)
            self.assertEqual([rel], [r for r in install_mod.plan_refusals({rel: entry})])

    def test_the_shelf_contract_is_the_one_file_laid_inside_a_protected_folder(self):
        entry = self.plan["14_CANDIDATES/README.md"]
        self.assertTrue(entry.moves_bytes)
        self.assertFalse(install_mod.protected(entry.rel))
        self.assertEqual([], list(install_mod.plan_refusals(self.plan)))


class TestTheThreeWayJudgement(unittest.TestCase):
    """Each verdict, decided by a hash rather than by a guess about what the home means."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = MiniRepo(Path(self._tmp.name) / "repo")
        self.home = Home(Path(self._tmp.name) / "brain")
        self.home.root.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)
        self.rel = "scripts/common.py"
        self.entry = install_mod.Entry(self.rel, self.repo.file("scripts/common.py"), "copy")
        self.plan = {self.rel: self.entry}

    def record(self, home_text, engine_text, files_text=None):
        """A manifest holding the hashes an act would have written for these bytes."""
        def digest(text):
            import hashlib
            return hashlib.sha256(text.encode("utf-8")).hexdigest()
        return {"files": {self.rel: digest(files_text or home_text)},
                "engine_bytes": {self.rel: digest(engine_text)}}

    def judge(self, manifest, home_text=None):
        if home_text is not None:
            self.home.write(self.rel, home_text)
        return install_mod.judge(self.plan, manifest, self.home.root)[0]

    def test_an_untouched_home_and_a_still_engine_is_unchanged(self):
        self.home.write(self.rel, "VERSION = 1\n")
        row = self.judge(self.record("VERSION = 1\n", "VERSION = 1\n"))
        self.assertEqual(install_mod.UNCHANGED, row.verdict)

    def test_a_moved_engine_file_is_updated_and_carries_the_new_bytes(self):
        self.home.write(self.rel, "VERSION = 1\n")
        self.repo.write(self.rel, "VERSION = 2\n")
        row = self.judge(self.record("VERSION = 1\n", "VERSION = 1\n"))
        self.assertEqual(install_mod.UPDATED, row.verdict)
        self.assertEqual(b"VERSION = 2\n", row.candidate)

    def test_a_record_and_a_home_that_disagree_is_an_edit_made_here(self):
        """The one distinction the whole feature exists for, decided by bytes, not by mtime."""
        self.home.write(self.rel, "VERSION = 1\n# my own change\n")
        self.repo.write(self.rel, "VERSION = 2\n")
        row = self.judge(self.record("whatever the home holds", "VERSION = 1\n",
                                     files_text="VERSION = 1\n"))
        self.assertEqual(install_mod.KEPT, row.verdict)

    def test_a_file_the_home_lost_and_the_record_named_is_restored(self):
        row = self.judge(self.record("VERSION = 1\n", "VERSION = 1\n"))
        self.assertEqual(install_mod.ABSENT, row.verdict)

    def test_a_path_this_engine_newly_ships_to_a_home_that_has_nothing_there_is_added(self):
        row = self.judge({"files": {}, "engine_bytes": {}})
        self.assertEqual(install_mod.ADDED, row.verdict)

    def test_a_home_file_with_no_record_is_yours_and_is_never_overwritten(self):
        self.home.write(self.rel, "the owner wrote this at a path the engine later shipped")
        row = self.judge({"files": {}, "engine_bytes": {}})
        self.assertEqual(install_mod.YOURS, row.verdict)
        self.assertIn("records no hash", row.why)

    def test_a_source_that_vanished_from_the_repo_is_named_not_guessed_at(self):
        self.home.write(self.rel, "a file the home still needs")
        self.repo.file("scripts/common.py").unlink()
        row = self.judge(self.record("a file the home still needs", "VERSION = 1\n"))
        self.assertEqual(install_mod.NOT_IN_REPO, row.verdict)

    def test_a_ledger_that_exists_is_present_and_is_never_truncated(self):
        rel = "15_SYSTEM/memory/lessons.jsonl"
        entry = install_mod.Entry(rel, b"", "touch")
        self.home.write(rel, '{"id": "learned-here"}\n')
        row = install_mod.judge({rel: entry}, {"files": {}, "engine_bytes": {}},
                                self.home.root)[0]
        self.assertEqual(install_mod.PRESENT, row.verdict)

    def test_a_marker_is_skipped_when_the_folder_holds_this_brains_own_notes(self):
        rel = "01_INBOX/.gitkeep"
        entry = install_mod.Entry(rel, b"", "marker")
        write(self.home.file("01_INBOX/my-note.md"), "# mine\n")
        row = install_mod.judge({rel: entry}, {"files": {}, "engine_bytes": {}},
                                self.home.root)[0]
        self.assertEqual(install_mod.PRESENT, row.verdict)
        self.assertIn("this brain's own files", row.why)


class TestRecordedState(unittest.TestCase):
    """The record is the only thing an upgrade trusts, so it cannot be allowed to lie."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = MiniRepo(Path(self._tmp.name) / "repo")
        self.home = Home(Path(self._tmp.name) / "brain")
        self.home.root.mkdir(parents=True)
        self.addCleanup(self._tmp.cleanup)

    def test_the_record_is_the_file_the_schema_stamp_gate_already_owns(self):
        """No new, unjudged JSON in a home: the contract row makes this file a known shape."""
        entry = install_mod.Entry("scripts/common.py", self.repo.file("scripts/common.py"),
                                  "copy")
        row = install_mod.Row(entry, install_mod.LAID, "", b"VERSION = 1\n")
        path, parsed = install_mod.write_manifest(self.repo.root, self.home.root, [row],
                                                  "install", None)
        self.assertIsNotNone(parsed, "the record did not read back as written")
        self.assertEqual("1", parsed["schema_version"])
        contract = schema_stamp.CONTRACT_BY_NAME["install-manifest"]
        self.assertTrue(contract.holds(parsed), "the contract does not hold the fields it names")
        judged = schema_stamp.judge(install_mod.MANIFEST_REL, path, self.home.root)
        self.assertEqual(schema_stamp.STAMPED, judged["state"], judged["why"])
        self.assertEqual([], schema_stamp.refusal_lines([judged]))

    def test_an_edited_file_keeps_the_hash_of_the_bytes_the_installer_wrote(self):
        """If the record learned to call the person's bytes its own, the next upgrade eats them."""
        entry = install_mod.Entry("scripts/common.py", self.repo.file("scripts/common.py"), "copy")
        row = install_mod.Row(entry, install_mod.KEPT, "edited here", b"VERSION = 1\n")
        self.home.write("scripts/common.py", "# rewritten by hand\n")
        prior = {"files": {"scripts/common.py": install_mod.sha256_of(b"VERSION = 1\n")},
                 "engine_bytes": {"scripts/common.py": install_mod.sha256_of(b"VERSION = 1\n")}}
        files, engine = install_mod.final_state([row], prior, self.home.root, [])
        self.assertEqual(prior["files"], files)
        self.assertEqual(prior["engine_bytes"], engine)


class TestTheInstallerActs(unittest.TestCase):
    """End to end on a miniature repo: the refusal, the record, the act, and the proof."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = MiniRepo(Path(self._tmp.name) / "repo")
        self.home = Home(Path(self._tmp.name) / "brain")
        self.addCleanup(self._tmp.cleanup)

    def install(self):
        result = self.home.install(self.repo)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        return result

    def test_an_install_records_every_path_it_laid_and_journals_the_act(self):
        result = self.install()
        self.assertIn("record laid: %s" % MANIFEST_REL, result.stdout)
        self.assertIn("act journaled: %s" % JOURNAL_REL, result.stdout)
        manifest = self.home.manifest()
        self.assertEqual("install", manifest["act"])
        self.assertEqual("9.9.9", manifest["engine_version"])
        self.assertTrue(manifest["files"], "a record with no hashes records nothing")
        for rel, digest in manifest["files"].items():
            self.assertEqual(digest, install_mod.hash_file(self.home.file(rel)),
                             "%s is not the byte the record claims" % rel)

    def test_a_home_with_no_record_is_refused_in_words_that_explain_the_refusal(self):
        self.home.root.mkdir(parents=True)
        result = self.repo.run("--upgrade", str(self.home.root))
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("holds no install manifest", result.stdout)

    def test_a_record_that_cannot_be_parsed_is_refused_not_ignored(self):
        self.install()
        self.home.write(MANIFEST_REL, "not json at all\n")
        result = self.repo.run("--upgrade", str(self.home.root))
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("is not readable JSON", result.stdout)

    def test_dry_run_proves_its_own_innocence_with_a_tree_fingerprint(self):
        self.install()
        before = tree_fingerprint(self.home.root)
        result = self.repo.run("--upgrade", str(self.home.root), "--dry-run")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertIn("0 file(s) would move", result.stdout)
        self.assertEqual(before, tree_fingerprint(self.home.root),
                         "a dry run that writes is not a dry run")
        self.assertEqual(1, len(self.home.journal()), "the journal grew on a read-only act")

    def test_an_upgrade_reates_a_moved_engine_file_and_a_person_edit_differently(self):
        self.install()
        self.home.write("scripts/common.py", "VERSION = 1\n# mine, in my own brain\n")
        self.repo.write("scripts/health.py", "print('the engine, moved forward')\n")
        result = self.repo.run("--upgrade", str(self.home.root))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("UPDATED      scripts/health.py", result.stdout)
        self.assertIn("KEPT         scripts/common.py", result.stdout)
        self.assertIn("# mine, in my own brain",
                      self.home.file("scripts/common.py").read_text(encoding="utf-8"))
        self.assertIn("the engine, moved forward",
                      self.home.file("scripts/health.py").read_text(encoding="utf-8"))

    def test_a_second_upgrade_moves_nothing_at_all(self):
        """No churn: an act that always found work would be switched off within a week."""
        self.install()
        self.repo.write("scripts/health.py", "print('v2')\n")
        self.repo.run("--upgrade", str(self.home.root))
        again = self.repo.run("--upgrade", str(self.home.root), "--dry-run")
        self.assertEqual(0, again.returncode, again.stdout + again.stderr)
        self.assertIn("0 file(s) would move", again.stdout)

    def test_the_brains_own_planes_come_through_an_upgrade_byte_for_byte(self):
        self.install()
        kept = {
            "01_INBOX/my-note.md": "# my note\n\nthinking the repo has never seen\n",
            "12_RUNTIME/state.md": "runtime, disposable, mine\n",
            "14_CANDIDATES/mine.md": "a candidate I am still judging\n",
            "15_SYSTEM/memory/lessons.jsonl": '{"id": "learned-here"}\n',
        }
        for rel, text in kept.items():
            self.home.write(rel, text)
        self.repo.write("scripts/health.py", "print('a new engine')\n")
        result = self.repo.run("--upgrade", str(self.home.root))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        for rel, text in kept.items():
            self.assertEqual(text, self.home.file(rel).read_text(encoding="utf-8"),
                             "%s was moved by an upgrade that had no business there" % rel)

    def test_a_home_file_at_a_newly_shipped_path_is_left_alone_and_the_rest_still_moves(self):
        """YOURS protects the file without holding the whole home hostage to one collision."""
        self.install()
        self.repo.write("02_WIKI/reference_maps/new-map.md", "# a map this engine adds\n")
        self.home.write("02_WIKI/reference_maps/new-map.md", "# mine, written first\n")
        self.repo.write("scripts/health.py", "print('the engine moved on')\n")
        before = install_mod.hash_file(self.home.file("02_WIKI/reference_maps/new-map.md"))
        result = self.repo.run("--upgrade", str(self.home.root))
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("YOURS      02_WIKI/reference_maps/new-map.md", result.stdout)
        self.assertIn("the rest of the home moved", result.stdout)
        self.assertEqual(before, install_mod.hash_file(
            self.home.file("02_WIKI/reference_maps/new-map.md")))
        self.assertIn("the engine moved on",
                      self.home.file("scripts/health.py").read_text(encoding="utf-8"))

    def test_an_unresolved_path_is_never_recorded_so_the_next_act_reports_it_again(self):
        self.install()
        self.repo.write("02_WIKI/reference_maps/new-map.md", "# a map this engine adds\n")
        self.home.write("02_WIKI/reference_maps/new-map.md", "# mine, written first\n")
        self.repo.run("--upgrade", str(self.home.root))
        manifest = self.home.manifest()
        self.assertNotIn("02_WIKI/reference_maps/new-map.md", manifest["files"],
                         "recording a file this act did not write teaches the next act to eat it")
        self.assertEqual(["02_WIKI/reference_maps/new-map.md"], manifest["unresolved"])
        again = self.repo.run("--upgrade", str(self.home.root), "--dry-run")
        self.assertEqual(1, again.returncode, again.stdout + again.stderr)
        self.assertIn("YOURS", again.stdout)
        self.assertEqual(1, len([line for line in self.home.journal()
                                 if line["act"] == "upgrade"]))

    def test_a_file_the_home_deleted_comes_back_because_the_record_named_it(self):
        """Engine scripts are the engine's business: a home missing a gate cannot judge itself."""
        self.install()
        self.home.file("rules/zones.json").unlink()
        result = self.repo.run("--upgrade", str(self.home.root))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("ABSENT       rules/zones.json", result.stdout)
        self.assertTrue(self.home.file("rules/zones.json").is_file())

    def test_a_document_edited_here_holds_the_re_measure_and_says_why(self):
        """The installer will not run a number-filler over a person's prose, and will not lie."""
        self.install()
        self.home.write("README.md", "# README\n\nmy own words, my own numbers\n")
        result = self.repo.run("--upgrade", str(self.home.root))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("not re-measured: README.md is edited here", result.stdout)
        self.assertIn("my own words, my own numbers",
                      self.home.file("README.md").read_text(encoding="utf-8"))

    def test_every_write_lands_as_the_bytes_it_claimed_and_the_record_follows_the_disk(self):
        self.install()
        self.repo.write("scripts/common.py", "VERSION = 42\n")
        result = self.repo.run("--upgrade", str(self.home.root))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        manifest = self.home.manifest()
        self.assertEqual(install_mod.sha256_of(b"VERSION = 42\n"),
                         manifest["files"]["scripts/common.py"])
        self.assertEqual(install_mod.sha256_of(b"VERSION = 42\n"),
                         manifest["engine_bytes"]["scripts/common.py"])
        entry = self.home.journal()[-1]
        self.assertEqual("upgrade", entry["act"])
        self.assertEqual("9.9.9", entry["engine_version"])
        self.assertIn("scripts/common.py", entry["written"])

    def test_the_installer_never_prints_a_replacement_character(self):
        """Windows cp1252 turns an em dash into U+FFFD, and a gate that lies is worse than one that fails."""
        self.install()
        for result in (self.repo.run("--upgrade", str(self.home.root), "--dry-run"),
                       self.repo.run("--upgrade", str(self.home.root))):
            self.assertNotIn("\ufffd", result.stdout + result.stderr)


class TestTheRealHome(unittest.TestCase):
    """The shipped installer against the shipped repo: the record cannot break the gates."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.home = Home(Path(cls._tmp.name) / "brain")
        cls.install = run_utf8([sys.executable, INSTALL, "--target", str(cls.home.root)],
                               cwd=str(ROOT))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_a_real_install_lays_a_record_and_still_answers_every_gate(self):
        self.assertEqual(0, self.install.returncode, self.install.stdout + self.install.stderr)
        manifest = self.home.manifest()
        self.assertGreater(len(manifest["files"]), 100,
                           "a real brain ships more than this")
        health_run = run_utf8([sys.executable, str(self.home.file("scripts/health.py")),
                               "--vault", "."], cwd=str(self.home.root))
        self.assertEqual(0, health_run.returncode, health_run.stdout + health_run.stderr)
        self.assertEqual(len(health.GATES),
                         len([line for line in health_run.stdout.splitlines()
                              if line.startswith("OK")]))

    def test_the_record_it_lays_is_the_shape_the_stamped_gate_claims(self):
        judged = schema_stamp.judge(MANIFEST_REL, self.home.file(MANIFEST_REL), self.home.root)
        self.assertEqual(schema_stamp.STAMPED, judged["state"], judged["why"])
        self.assertEqual("install-manifest", judged["contract"])

    def test_a_real_home_up_to_date_moves_nothing(self):
        before = tree_fingerprint(self.home.root)
        result = run_utf8([sys.executable, INSTALL, "--upgrade", str(self.home.root),
                           "--dry-run"], cwd=str(ROOT))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("0 file(s) would move", result.stdout)
        self.assertEqual(before, tree_fingerprint(self.home.root))

    def test_a_real_note_survives_a_real_upgrade(self):
        """A note written in the front-matter shape `rules/schema.json` demands, then upgraded over."""
        today = _date.today().isoformat()
        note = ("---\nid: phase46-survivor\ntype: resource\ntitle: A note written in the home\n"
                "status: raw\nowner: human\ntopics: [upgrade]\ncreated: %s\nupdated: %s\n---\n\n"
                "# kept through the upgrade\n\nThe installer has no business in this file.\n"
                % (today, today))
        write(self.home.file("01_INBOX/hades-note.md"), note)
        before = install_mod.hash_file(self.home.file("01_INBOX/hades-note.md"))
        result = run_utf8([sys.executable, INSTALL, "--upgrade", str(self.home.root)],
                          cwd=str(ROOT))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual(before, install_mod.hash_file(self.home.file("01_INBOX/hades-note.md")))
        health_run = run_utf8([sys.executable, str(self.home.file("scripts/health.py")),
                               "--vault", "."], cwd=str(self.home.root))
        self.assertEqual(0, health_run.returncode, health_run.stdout + health_run.stderr)
        suite = run_utf8([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                         cwd=str(self.home.root))
        self.assertEqual(0, suite.returncode, suite.stdout + suite.stderr)


if __name__ == "__main__":
    unittest.main()
