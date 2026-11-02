"""Phase 44 — the release gate needs a clone that can read its own tags.

Found while cutting v0.1.0. Two runs of the same tree, two answers:

* the **tag-event** run (`push` of `refs/tags/v0.1.0`) was green;
* the **branch** run 1m later, on the very next commit, died in
  `python scripts/health.py` with `INVALID  VERSION 0.1.0 is not tagged and CHANGELOG.md's
  [Unreleased] declares nothing`.

Neither answer was wrong. `actions/checkout@v7` clones at depth 1, and a depth-1 clone of a
commit that is not the tagged one carries **no tags at all** — so after any release, every
branch push arrives at the version gate with its own release invisible, and the gate, which
refuses rather than guesses, says "not tagged". The claim the gate makes is true of the clone it
was handed and false of the repo the clone came from. `git_available()` already knows the tag half
needs history; the workflow was the part that did not.

The rule this file holds, in both directions:

  * every `actions/checkout` step in this repo's workflows fetches the full history, because a
    half-read gate is worse than no gate — it turns a released version into a red build for a
    reason no reader can see;
  * and that is not prose: the shallow clone below really cannot name the tag, really makes
    `scripts/version.py --check` refuse, and the full clone of the same commit really passes.

No network, no GitHub API, no runner: three throwaway repos under a temp dir, cloned over
`file://` like any other local path.
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
import common  # noqa: E402

WORKFLOWS = ("ci.yml", "loop.yml")
GIT_ID = ["-c", "user.name=gate", "-c", "user.email=gate@example.invalid"]
VERSION = "1.2.3"
# an [Unreleased] section that exists and declares nothing, which is the state the branch run hit
CHANGELOG = ("# Changelog\n\n## [Unreleased]\n\nNothing unreleased.\n\n"
             "## [%s] - 2026-11-02\n\n### Added\n- **the release**\n" % VERSION)
README = "# Second Brain OS v%s\n\n[![version](https://img.shields.io/badge/engine-v%s-blue)]\n" % (
    VERSION, VERSION)


def git(*args, cwd=None):
    return subprocess.run(["git"] + list(args), cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def release_repo(root):
    """A real clone: a tagged release commit, then one `docs:` commit on top of it."""
    Path(root).mkdir(parents=True, exist_ok=True)
    git("init", "-q", ".", cwd=root)
    write(root)
    git("add", "-A", cwd=root)
    git(*GIT_ID, "commit", "-qm", "feat: the release", cwd=root)
    git(*GIT_ID, "tag", "v" + VERSION, cwd=root)
    (root / "NOTE.md").write_text("a commit after the release\n", encoding="utf-8")
    git("add", "-A", cwd=root)
    git(*GIT_ID, "commit", "-qm", "docs: paperwork after the tag", cwd=root)
    return root


def write(root):
    (root / "VERSION").write_text(VERSION + "\n", encoding="utf-8")
    (root / "pyproject.toml").write_text('[project]\nname = "second-brain"\nversion = "%s"\n'
                                         % VERSION, encoding="utf-8")
    (root / "README.md").write_text(README, encoding="utf-8")
    (root / "CHANGELOG.md").write_text(CHANGELOG, encoding="utf-8")


def clone(source, dest, *flags):
    url = Path(source).resolve().as_uri()
    result = git("clone", "-q", *flags, url, str(dest), cwd=Path(source).parent)
    assert result.returncode == 0, result.stdout + result.stderr
    return dest


def run_gate(root):
    """`--root`, not cwd: without it `find_root` follows the script's own folder, which is the
    real repo, and the fixture is judged by a history that is not its own."""
    return common.run_utf8([sys.executable, str(SCRIPTS / "version.py"), "--check",
                            "--root", str(root)], cwd=str(ROOT))


def checkout_steps(text):
    """Each `uses: actions/checkout@…` line with the `with:` block that follows it."""
    steps = []
    for index, line in enumerate(text.splitlines()):
        if "uses:" not in line or "actions/checkout" not in line:
            continue
        indent = len(line) - len(line.lstrip())
        block = []
        for following in text.splitlines()[index + 1:]:
            if following.strip() and len(following) - len(following.lstrip()) <= indent:
                break
            block.append(following)
        steps.append("\n".join(block))
    return steps


class TheWorkflowsFetchWhatTheGateJudges(unittest.TestCase):
    def test_every_checkout_step_carries_the_full_history(self):
        for name in WORKFLOWS:
            text = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
            steps = checkout_steps(text)
            self.assertTrue(steps, "%s declares no checkout step at all" % name)
            for step in steps:
                self.assertRegex(step, r"fetch-depth:\s*(0|-1)\b",
                                 "%s checks out at depth 1, so a release made on the "
                                 "branch is invisible to scripts/version.py" % name)


class AShallowCloneCannotSeeARelease(unittest.TestCase):
    """The witness, not the assertion: the failure is reproduced, then repaired by the flag."""

    @classmethod
    def setUpClass(cls):
        if shutil.which("git") is None:
            raise unittest.SkipTest("git is not installed, so this clone test cannot run")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name)
        self.source = release_repo(self.base / "src")

    def test_the_shallow_clone_carries_no_tag(self):
        shallow = clone(self.source, self.base / "shallow", "--depth", "1")
        described = git("describe", "--tags", "--abbrev=0", "HEAD", cwd=shallow)
        self.assertNotEqual(0, described.returncode, described.stdout + described.stderr)
        self.assertIn("No names found", described.stderr, described.stderr)

    def test_the_full_clone_carries_the_tag(self):
        full = clone(self.source, self.base / "full")
        described = git("describe", "--tags", "--abbrev=0", "HEAD", cwd=full)
        self.assertEqual(0, described.returncode, described.stdout + described.stderr)
        self.assertEqual("v" + VERSION, described.stdout.strip(), described.stdout)

    def test_the_gate_refuses_the_shallow_clone_for_a_reason_that_is_not_true(self):
        """What CI did: a released version, refused as untagged, because the clone had no tags."""
        shallow = clone(self.source, self.base / "shallow", "--depth", "1")
        result = run_gate(shallow)
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("is not tagged", result.stdout, result.stdout)

    def test_the_same_commit_passes_the_gate_with_history(self):
        full = clone(self.source, self.base / "full")
        result = run_gate(full)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("one version everywhere", result.stdout, result.stdout)

    def test_the_real_repo_is_checked_out_the_way_the_gate_needs(self):
        """HEAD here is past the tag, exactly like the branch run — so the tag must resolve."""
        described = git("describe", "--tags", "--abbrev=0", "HEAD", cwd=ROOT)
        self.assertEqual(0, described.returncode, described.stdout + described.stderr)
        self.assertEqual(0, run_gate(ROOT).returncode, run_gate(ROOT).stdout)


if __name__ == "__main__":
    unittest.main()
