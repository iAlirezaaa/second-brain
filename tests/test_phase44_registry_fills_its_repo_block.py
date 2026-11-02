"""Phase 44 — the registry can finally fill the `repo` block its own zone law demands.

The defect was found by doing the thing the docs tell an agent to do. `03_PROJECTS/README.md`
says code does not live in the brain; the manifest carries the address instead, and names the
three fields: `repo.path`, `repo.remote`, `repo.branch`. So this was run against the real repo:

    $ python 15_SYSTEM/scripts/hades.py set --id PRJ-CEAB904D --field repo.remote --value <url>
    REFUSED: unknown field 'repo.remote' for kind project and the record does not carry it

`set` only knew flat field names, `make_obj` minted `repo` with three empty strings, and
`new --code-repo` was a flag the parser accepted and no line of code ever read. A contract a
tool cannot satisfy is a decorative contract, so these tests hold the fix to five things:

  1. the schema declares the keys inside `repo` (not just "an object"), because a nested
     object nobody enumerates is where a typo hides;
  2. `--code-repo PATH` reads path/remote/branch from that folder's own git, and refuses —
     writing nothing — when the folder has no git, rather than inventing an address;
  3. `set --field repo.<key>` amends through the same plan/approve audit trail as a flat field,
     and refuses a key the schema does not declare;
  4. a nested value of the wrong type fails the record's own contract before anything is written;
  5. `doctor` catches an undeclared key hand-written inside a declared object, so the schema
     bites on the bytes on disk and not only on the bytes the CLI produced.
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hades_fixture import hades_json, seeded  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "15_SYSTEM" / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))


def git(repo_dir, *args):
    return subprocess.run(["git", "-C", str(repo_dir)] + list(args), capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


def git_repo(with_origin=True):
    """A throwaway code repo with one commit on `main`, optionally an origin remote."""
    home = Path(tempfile.mkdtemp(prefix="code-repo-"))
    git(home, "init", "-q", "-b", "main")
    git(home, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
        "commit", "-q", "--allow-empty", "-m", "first")
    if with_origin:
        git(home, "remote", "add", "origin", "https://example.invalid/acme/code.git")
    return home


def project_id(vault):
    _code, out = vault.hades("list", "--kind", "project")
    return re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)


def record_repo(vault, ident):
    shown, _raw = hades_json(vault, "show", "--id", ident)
    return shown.get("repo"), shown


class TestTheRepoBlockIsDeclared(unittest.TestCase):
    """The schema must name the keys, or `repo` is a box anything can be stuffed into."""

    def test_project_declares_the_three_keys_the_zone_readme_names(self):
        readme = (ROOT / "03_PROJECTS" / "README.md").read_text(encoding="utf-8")
        for field in ("repo.path", "repo.remote", "repo.branch"):
            self.assertIn(field, readme, "%s is not promised by the zone law" % field)
        keys = SCHEMA["by_kind"]["project"]["object_keys"]["repo"]
        self.assertEqual(sorted(keys), ["branch", "path", "remote"],
                         "the schema and the zone README disagree about what repo carries")
        self.assertEqual(set(keys.values()), {"string"},
                         "a code address is three strings; anything else is a different field")

    def test_an_app_record_gets_the_same_declaration(self):
        self.assertEqual(sorted(SCHEMA["by_kind"]["app"]["object_keys"]["repo"]),
                         ["branch", "path", "remote"])

    def test_a_new_project_starts_with_an_empty_honest_repo_block(self):
        vault = seeded()
        try:
            ident = project_id(vault)
            repo, _shown = record_repo(vault, ident)
            self.assertEqual(sorted(repo), ["branch", "path", "remote"],
                             "the block must have the declared keys so `set` can fill them")
            self.assertEqual(repo["path"], "", "an unfilled address is empty, never invented")
            _code, doctor = vault.hades("doctor")
            self.assertIn("errors: 0", doctor, doctor)
        finally:
            vault.close()


class TestCodeRepoFillsTheBlockFromGit(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()

    def tearDown(self):
        self.vault.close()

    def test_code_repo_records_what_the_folders_git_says(self):
        code = git_repo()
        try:
            _code, out = self.vault.hades("new", "--kind", "project", "--name", "Demo Service",
                                          "--description", "a program with real code",
                                          "--type", "program", "--status", "active",
                                          "--code-repo", str(code), "--approve")
            self.assertEqual(_code, 0, out)
            ident = re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)
            repo, _shown = record_repo(self.vault, ident)
            self.assertEqual(repo["remote"], "https://example.invalid/acme/code.git", repo)
            self.assertEqual(repo["branch"], "main", repo)
            self.assertEqual(Path(repo["path"]).resolve(), code.resolve(),
                             "repo.path must be the folder that was passed, not a guess")
            self.assertNotIn("\\", repo["path"], "paths in a registry record use forward slashes")
            _code, doctor = self.vault.hades("doctor")
            self.assertIn("errors: 0", doctor, doctor)
        finally:
            shutil.rmtree(code, ignore_errors=True)

    def test_a_folder_with_no_git_is_refused_and_writes_no_record(self):
        plain = Path(tempfile.mkdtemp(prefix="not-a-repo-"))
        before = len(self.vault.paths())
        before_plans = len(self.vault.paths("15_SYSTEM/generated/plans/PLAN-*.json"))
        code, out = self.vault.hades("new", "--kind", "project", "--name", "No Git Here",
                                     "--description", "fixture", "--type", "program",
                                     "--code-repo", str(plain), "--approve")
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED", out, out)
        self.assertEqual(len(self.vault.paths()), before,
                         "`new` applied some other plan after its own was refused")
        self.assertEqual(len(self.vault.paths("15_SYSTEM/generated/plans/PLAN-*.json")), before_plans,
                         "a refused --code-repo left a plan waiting for a later --approve")
        shutil.rmtree(plain, ignore_errors=True)

    def test_a_repo_with_no_origin_still_gets_path_and_branch_and_says_the_rest(self):
        code = git_repo(with_origin=False)
        _code, out = self.vault.hades("new", "--kind", "project", "--name", "Local Only",
                                      "--description", "fixture", "--type", "program",
                                      "--code-repo", str(code), "--approve")
        self.assertEqual(_code, 0, out)
        ident = re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)
        repo, _shown = record_repo(self.vault, ident)
        self.assertEqual(repo["remote"], "", "no origin means no remote, not a invented one")
        self.assertIn("origin", out.lower(), out)
        self.assertIn("repo.remote", out,
                      "the tool has to name the field the operator can still fill with `set`")

    def test_a_kind_without_a_repo_block_is_refused_not_silently_ignored(self):
        code = git_repo()
        before = len(self.vault.paths())
        c, out = self.vault.hades("new", "--kind", "organization", "--name", "No Repo Org",
                                  "--description", "fixture", "--code-repo", str(code),
                                  "--approve")
        self.assertEqual(c, 2, out)
        self.assertIn("REFUSED", out, out)
        self.assertEqual(len(self.vault.paths()), before, out)

    def test_a_brain_whose_code_is_its_own_folder_records_a_relative_path(self):
        """The self-record case: an absolute path is this machine's address, not the project's.

        The repo registers itself, so `--code-repo` gets the vault's own folder. Writing
        `C:/Users/<someone>/...` into a tracked record would be true on one clone and false on
        every other, which is the failure mode this repo calls a silent gate.
        """
        home = self.vault.root
        git(home, "init", "-q", "-b", "main")
        git(home, "remote", "add", "origin", "https://example.invalid/acme/code.git")
        git(home, "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "-q", "--allow-empty", "-m", "the brain commits to itself")
        _code, out = self.vault.hades("new", "--kind", "project", "--name", "This Brain",
                                      "--description", "the engine and the vault are one repo",
                                      "--type", "program", "--code-repo", str(home), "--approve")
        self.assertEqual(_code, 0, out)
        ident = re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)
        repo, _shown = record_repo(self.vault, ident)
        self.assertEqual(repo["path"], ".", repo)
        self.assertEqual(repo["remote"], "https://example.invalid/acme/code.git", repo)
        self.assertIn("main", repo["branch"])


class TestANestedFieldIsAmendable(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()
        self.ident = project_id(self.vault)

    def tearDown(self):
        self.vault.close()

    def test_set_fills_one_key_through_the_audit_trail(self):
        code, out = self.vault.hades("set", "--id", self.ident, "--field", "repo.remote",
                                     "--value", "https://github.com/acme/code.git", "--approve")
        self.assertEqual(code, 0, out)
        self.assertIn("AMENDED", out, out)
        repo, shown = record_repo(self.vault, self.ident)
        self.assertEqual(repo["remote"], "https://github.com/acme/code.git", repo)
        self.assertEqual(repo["path"], "", "amending one key must not rewrite its neighbours")
        trail = shown.get("amendments") or []
        self.assertEqual(len(trail), 1, shown)
        self.assertEqual(trail[0]["field"], "repo.remote", trail)
        _code, doctor = self.vault.hades("doctor")
        self.assertIn("errors: 0", doctor, doctor)

    def test_a_key_the_schema_does_not_declare_is_refused_by_name(self):
        code, out = self.vault.hades("set", "--id", self.ident, "--field", "repo.remo",
                                     "--value", "https://example.invalid", "--approve")
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED", out, out)
        self.assertIn("remote", out, "the refusal must name the keys that do exist")
        repo, _shown = record_repo(self.vault, self.ident)
        self.assertNotIn("repo.remo", str(repo), out)
        self.assertEqual(repo["remote"], "", repo)

    def test_a_nested_value_of_the_wrong_type_is_refused(self):
        code, out = self.vault.hades("set", "--id", self.ident, "--field", "repo.branch",
                                     "--value", '{"name": "main"}', "--approve")
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED", out, out)
        repo, _shown = record_repo(self.vault, self.ident)
        self.assertEqual(repo["branch"], "main", repo)

    def test_a_whole_object_can_be_amended_in_one_value(self):
        code, out = self.vault.hades("set", "--id", self.ident, "--field", "repo",
                                     "--value", json.dumps({"path": "", "remote": "https://x.invalid/a.git",
                                                            "branch": "trunk"}), "--approve")
        self.assertEqual(code, 0, out)
        repo, _shown = record_repo(self.vault, self.ident)
        self.assertEqual(repo["branch"], "trunk", repo)

    def test_a_nested_key_two_levels_deep_is_refused(self):
        code, out = self.vault.hades("set", "--id", self.ident, "--field", "repo.remote.url",
                                     "--value", "x", "--approve")
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED", out, out)

    def test_set_without_approve_only_plans_the_nested_change(self):
        _code, out = self.vault.hades("set", "--id", self.ident, "--field", "repo.path",
                                      "--value", "/srv/code")
        self.assertEqual(_code, 0, out)
        repo, _shown = record_repo(self.vault, self.ident)
        self.assertEqual(repo["path"], "", "an unapproved amendment was written anyway")


class TestTheSchemaBitesOnHandWrittenBytes(unittest.TestCase):
    def test_an_undeclared_key_inside_repo_is_a_doctor_error(self):
        """A record edited by hand is still a record; the declaration has to mean that too."""
        vault = seeded()
        try:
            ident = project_id(vault)
            _code, out = vault.hades("show", "--id", ident)
            path = vault.root / out.split("# file:")[-1].strip()
            rec = json.loads(path.read_text(encoding="utf-8"))
            rec["repo"]["upstream"] = "https://example.invalid/acme/code.git"
            path.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
            code, doctor = vault.hades("doctor")
            self.assertEqual(code, 1, doctor)
            self.assertIn("repo.upstream", doctor, doctor)
        finally:
            vault.close()


if __name__ == "__main__":
    unittest.main()
