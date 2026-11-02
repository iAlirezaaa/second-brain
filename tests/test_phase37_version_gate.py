"""Phase 37 — the version stops being a hand-typed number (the owner's brief).

`VERSION` and `pyproject.toml` agreed, and that agreement was the only check the repo had, so
three places that a human actually reads were free to disagree: the README opened with
`HADES OS v0.01` while `VERSION` said `0.0.3`, the badge said something else again, and nothing
compared either of them to the changelog or to the tag the clone carries. Issue #4 removed the
hand-typed test-count badge for exactly this reason; the version was the last one left.

Every class below is red on the commit before the gate exists.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import version as gate  # noqa: E402
import common  # noqa: E402

GOOD_README = """# Second Brain OS v9.9.9

[![version](https://img.shields.io/badge/engine-v9.9.9-blue)](https://github.com/iAlirezaaa/x/releases)

prose
"""

GOOD_CHANGELOG = """# Changelog

## [Unreleased]

### Added
- **a shipped thing** — with its evidence.

## [9.9.9] — 2026-10-01

### Added
- the release that was tagged.
"""


def fixture(root, version="9.9.9", pyproject=None, readme=GOOD_README,
            changelog=GOOD_CHANGELOG):
    """A minimal repo-shaped folder: the four places the number lives, no git needed."""
    (Path(root) / "VERSION").write_text(version + "\n", encoding="utf-8")
    (Path(root) / "pyproject.toml").write_text(
        '[project]\nname = "second-brain"\nversion = "%s"\n'
        % (pyproject if pyproject is not None else version), encoding="utf-8")
    (Path(root) / "README.md").write_text(readme, encoding="utf-8")
    (Path(root) / "CHANGELOG.md").write_text(changelog, encoding="utf-8")
    return Path(root)


class TestBumpLadder(unittest.TestCase):
    """The rule that decides the number is a table, not a feeling."""

    def test_types_map_to_their_level(self):
        for subject, expected in [
            ("feat(mcp): a new door", "minor"),
            ("fix: one refusal message", "patch"),
            ("perf: index reuse", "patch"),
            ("docs(readme): clearer brief", "none"),
            ("test: a new case", "none"),
            ("chore: tidy", "none"),
            ("refactor: no behaviour moved", "none"),
            ("a sentence with no type at all", "none"),
        ]:
            self.assertEqual(gate.classify_commit(subject, ""), expected, subject)

    def test_breaking_wins_from_either_place(self):
        self.assertEqual(gate.classify_commit("feat!: the contract moved", ""), "major")
        self.assertEqual(gate.classify_commit("fix: oops", "BREAKING CHANGE: it did"), "major")

    def test_highest_level_of_a_set(self):
        commits = [("docs: a", ""), ("fix: b", ""), ("feat: c", "")]
        self.assertEqual(gate.highest_level(commits), "minor")
        self.assertEqual(gate.highest_level([("docs: a", "")]), "none")
        self.assertEqual(gate.highest_level([]), "none")

    def test_next_version_arithmetic(self):
        self.assertEqual(gate.next_version("0.0.3", "patch"), "0.0.4")
        self.assertEqual(gate.next_version("0.0.3", "minor"), "0.1.0")
        self.assertEqual(gate.next_version("0.4.7", "minor"), "0.5.0")
        self.assertEqual(gate.next_version("1.2.3", "major"), "2.0.0")
        # SemVer §4: below 1.0 the minor carries the breaking signal, and the jump to 1.0 is
        # the owner's decision, so the gate refuses to make it on an agent's authority.
        self.assertEqual(gate.next_version("0.0.3", "major"), "0.1.0")
        self.assertEqual(gate.next_version("0.0.3", "none"), "0.0.3")

    def test_a_non_semver_version_is_refused_by_name(self):
        with self.assertRaises(ValueError):
            gate.split_semver("0.003")
        with self.assertRaises(ValueError):
            gate.split_semver("v0.0.3")


class TestVersionGate(unittest.TestCase):
    def test_one_number_everywhere_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp)
            self.assertEqual(gate.check(root), [])

    def test_pyproject_drift_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, pyproject="9.9.8")
            problems = gate.check(root)
            self.assertEqual(len(problems), 1)
            self.assertIn("pyproject.toml says 9.9.8", problems[0])

    def test_stale_readme_title_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, readme=GOOD_README.replace("v9.9.9", "v0.01"))
            joined = "\n".join(gate.check(root))
            self.assertIn("README title", joined)
            self.assertIn("badge", joined)

    def test_missing_changelog_section_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, changelog="# Changelog\n\n## [9.9.8] — 2026-09-01\n")
            problems = "\n".join(gate.check(root))
            self.assertIn("no [Unreleased] section", problems)

    def test_unreleased_that_declares_nothing_is_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, changelog="# Changelog\n\n## [Unreleased]\n\n### Added\n")
            problems = "\n".join(gate.check(root))
            self.assertIn("declares nothing", problems)

    def test_malformed_version_is_the_only_problem_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, version="0.003")
            problems = gate.check(root)
            self.assertEqual(len(problems), 1)
            self.assertIn("MAJOR.MINOR.PATCH", problems[0])


class TestBumpWrites(unittest.TestCase):
    def test_explicit_bump_rewrites_both_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, version="0.0.3")
            self.assertEqual(gate.bump(root, "minor"), 0)
            self.assertEqual(gate.declared_version(root), "0.1.0")
            self.assertEqual(gate.pyproject_version(root), "0.1.0")

    def test_a_bump_the_number_already_has_is_refused_not_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, version="0.0.3")
            self.assertEqual(gate.bump(root, "none"), 3)
            self.assertEqual(gate.declared_version(root), "0.0.3")

    def test_bump_hands_the_tag_to_a_human(self):
        """Tagging publishes a promise, so the gate names the command and does not run it."""
        import contextlib
        import io
        with tempfile.TemporaryDirectory() as tmp:
            root = fixture(tmp, version="0.0.3")
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                gate.bump(root, "patch")
            text = out.getvalue()
            self.assertIn("git tag v0.0.4", text)
            self.assertFalse((root / ".git").exists())


class TestShippedRepo(unittest.TestCase):
    def test_this_folder_carries_one_version(self):
        problems = gate.check(ROOT)
        self.assertEqual(problems, [], "the repo disagrees with itself about its own number")

    def test_the_released_number_is_the_owner_baseline(self):
        self.assertEqual(gate.split_semver(gate.declared_version(ROOT)),
                         tuple(int(part) for part in
                               gate.declared_version(ROOT).split(".")))


class TestAnInstalledHomeMakesNoVersionClaim(unittest.TestCase):
    """`VERSION`, `pyproject.toml` and the tag are the repo's release paperwork.

    The gate joined `scripts/health.py`, so every installed brain home met it — and a home keeps
    none of those files. `check()` answered `VERSION: '' is not a MAJOR.MINOR.PATCH version`,
    which is a true sentence about a folder that never claimed a version, and a crash for
    `--bump`. A home now gets a stated skip; a checkout missing one of its places still refuses.
    """

    def run_gate(self, root, *args):
        return common.run_utf8([sys.executable, str(ROOT / "scripts" / "version.py"),
                                "--root", str(root), *args], cwd=str(ROOT))

    def test_a_home_states_the_skip_rather_than_inventing_a_defect(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "brain"
            home.mkdir()
            result = self.run_gate(home, "--check")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(result.stdout.startswith("OK"), result.stdout)
            for reason in ("installed brain home", "not a repo checkout", "no version claim"):
                self.assertIn(reason, result.stdout, "the skip did not say why: %s" % result.stdout)

    def test_a_home_refuses_a_bump_it_cannot_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "brain"
            home.mkdir()
            result = self.run_gate(home, "--bump", "patch")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("REFUSED", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_a_checkout_missing_its_manifest_refuses_by_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = fixture(tmp)
            (repo / "pyproject.toml").unlink()
            (repo / ".git").mkdir()
            result = self.run_gate(repo, "--check")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("pyproject.toml declares no version", result.stdout)

    def test_a_checkout_without_a_version_file_refuses_rather_than_crashing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            result = self.run_gate(root, "--bump", "patch")
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("REFUSED", result.stdout)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
