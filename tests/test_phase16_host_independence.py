"""Phase 16 tests — the system belongs to no app and no single agent host (issue #8).

Three claims, each judged by a test rather than by a sentence in a README:

  1. every agent host that opens this repo is pointed at one law, and a door that drifts
     from that law fails the build;
  2. the door only names rooms that exist -- a pointer to a deleted file is how a
     fabricated onboarding starts;
  3. an installed brain passes every one of its own gates with no editor, no network and
     no plugin anywhere in the loop -- and measures its own numbers instead of copying
     the source repo's.
"""
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from common import run_utf8  # noqa: E402
import health  # noqa: E402  -- the gate list is the measure the assertions use
import sync_hosts  # noqa: E402

SYNC = str(SCRIPTS / "sync_hosts.py")
INSTALL = str(SCRIPTS / "install.py")
HEALTH = str(SCRIPTS / "health.py")

# An instruction that makes an app a step of the workflow. Optional lenses are allowed --
# what is not allowed is a document that turns a lens into a dependency.
FORBIDDEN = (
    re.compile(r"\bopen\s+[^.\n]{0,40}\b(obsidian|vs ?code|cursor|windsurf|zed|idea)\b", re.I),
    re.compile(r"\b(requires?|needs?|must (?:have|install))\s+(obsidian|an editor|a plugin|the app)\b", re.I),
    re.compile(r"install (obsidian|the plugin)\b", re.I),
    re.compile(r"(در\s+obsidian\s+باز کنید|به obsidian نیاز|obsidian الزامی)", re.I),
)
# lines that say the opposite: the app is a choice, not a condition
EXCUSE = re.compile(r"(optional|never a dependency|اختیاری|لنز|not required|example)", re.I)


def sync(root, *args):
    return run_utf8([sys.executable, SYNC, "--root", str(root)] + list(args), cwd=str(ROOT))


def installed_measure(text, row_prefix):
    """Read the number a measured table row claims, straight off the document."""
    for line in text.splitlines():
        if line.startswith("| %s" % row_prefix):
            return int(line.split("|")[-2].strip())
    raise AssertionError("no measured row starting %r in the installed document" % row_prefix)


class TestOneLawEveryHost(unittest.TestCase):
    def test_the_shipped_repo_has_no_drift_between_the_canon_and_its_doors(self):
        result = sync(ROOT, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("agree with AGENTS.md", result.stdout)

    def test_every_documented_host_reads_a_door_that_points_at_the_canon(self):
        for _key, _name, rel, _mdc in sync_hosts.HOSTS:
            path = ROOT / rel
            self.assertTrue(path.is_file(), "%s is missing — %s would see no rules" % (rel, _name))
            text = path.read_text(encoding="utf-8")
            self.assertIn("AGENTS.md", text, "%s does not name the canon" % rel)
            self.assertIn("sync_hosts.py", text, "%s does not say how to re-render it" % rel)

    def test_the_cursors_door_carries_the_front_matter_cursor_needs(self):
        text = (ROOT / ".cursor" / "rules" / "agents.mdc").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("---"), "a .mdc without front matter is not a rule")
        self.assertIn("alwaysApply: true", text)

    def test_a_hand_edited_door_is_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            sync(root)  # lay the doors first
            door = root / "CLAUDE.md"
            door.write_text(door.read_text(encoding="utf-8") + "\nExtra house rule.\n",
                           encoding="utf-8")
            result = sync(root, "--check")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("DRIFT", result.stdout)
            self.assertIn("CLAUDE.md", result.stdout)

    def test_a_missing_door_is_named_as_the_host_that_never_sees_the_law(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            sync(root)
            (root / "GEMINI.md").unlink()
            result = sync(root, "--check")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("GEMINI.md", result.stdout)
            self.assertIn("never sees the law", result.stdout)

    def test_rendering_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            first = sync(root).stdout
            again = sync(root)
            self.assertIn("SYNCED", first)
            self.assertEqual(again.returncode, 0, again.stdout)
            self.assertNotIn("SYNCED", again.stdout, "a second render must not rewrite bytes")


class TestDoorsPointAtRealRooms(unittest.TestCase):
    def test_every_path_the_entrypoint_names_exists_in_the_repo(self):
        result = run_utf8([sys.executable, SYNC, "--lint"], cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("every path", result.stdout)

    def test_a_renamed_doc_breaks_the_lint_instead_of_misleading_the_next_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            sync(root)
            (root / "00_START_HERE" / "SYSTEM_MAP.md").unlink()
            result = sync(root, "--lint")
            self.assertEqual(result.returncode, 1, result.stdout)
            self.assertIn("BAD POINTER", result.stdout)
            self.assertIn("00_START_HERE/SYSTEM_MAP.md", result.stdout)

    def test_refusing_to_ship_a_door_that_points_at_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = build_root(Path(tmp))
            (root / "00_START_HERE" / "SYSTEM_MAP.md").unlink()
            result = sync(root)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("points at nothing", result.stdout)
            self.assertFalse((root / "CLAUDE.md").exists(), "no door may be laid on a broken map")


class TestNoAppIsARequirement(unittest.TestCase):
    def files(self):
        """Everything an agent reads at the door: canon, doors, start docs, skills, gates."""
        shipped = [ROOT / "README.md", ROOT / "AGENTS.md", ROOT / "HANDOFF.md",
                   ROOT / "MEMORY.md", ROOT / "ROADMAP.md"]
        shipped += [ROOT / rel for _k, _n, rel, _m in sync_hosts.HOSTS]
        shipped += list((ROOT / "00_START_HERE").glob("*.md"))
        shipped += list((ROOT / "skills").glob("*/SKILL.md"))
        shipped += list(SCRIPTS.glob("*.py"))
        return [path for path in shipped if path.is_file()]

    def test_no_shipped_instruction_turns_an_editor_into_a_dependency(self):
        offenders = []
        for path in self.files():
            for lineno, line in enumerate(path.read_text(encoding="utf-8",
                                                        errors="replace").splitlines(), 1):
                if any(pattern.search(line) for pattern in FORBIDDEN) and not EXCUSE.search(line):
                    offenders.append("%s:%d %s" % (path.name, lineno, line.strip()[:90]))
        self.assertEqual(offenders, [], "an app is a lens here, not a step:\n" +
                         "\n".join(offenders))

    def test_the_installer_does_not_send_the_user_to_an_app(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "brain"
            result = run_utf8([sys.executable, INSTALL, "--target", str(target)], cwd=str(ROOT))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotRegex(result.stdout, FORBIDDEN[0])
            self.assertIn("no app required", result.stdout)


class TestAnInstalledBrainStandsAlone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.target = Path(cls._tmp.name) / "brain"
        cls.install = run_utf8([sys.executable, INSTALL, "--target", str(cls.target)],
                               cwd=str(ROOT))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_the_installed_brain_passes_every_gate_with_no_editor_present(self):
        """The gate list, not a remembered count: a seventh gate is picked up automatically."""
        self.assertEqual(self.install.returncode, 0, self.install.stdout + self.install.stderr)
        result = run_utf8([sys.executable, HEALTH, "--vault", "."], cwd=str(self.target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for gate in ("broken links", "frontmatter valid", "shelf candidate",
                     "MEMORY.md matches", "agree with AGENTS.md",
                     "matches the state of this folder"):
            self.assertIn(gate, result.stdout, "%s did not run in the installed brain" % gate)
        self.assertEqual(len([line for line in result.stdout.splitlines() if line.startswith("OK")]),
                         len(health.GATES), "health ran a different number of gates than it claims")

    def test_the_installed_brain_measures_itself_rather_than_copying_numbers(self):
        """A copied README that still reports the source repo's counts is a borrowed fact."""
        readme = (self.target / "README.md").read_text(encoding="utf-8")
        self.assertIn("doc_report.py --write", readme)
        self.assertEqual(installed_measure(readme, "tests collected"), 0,
                         "the installed brain claims the source repo's test count")
        self.assertEqual(installed_measure(readme, "active lessons"), 0,
                         "the installed brain shipped with somebody else's memory")

    def test_the_installed_brain_ships_its_own_laws_doors_and_gates(self):
        for rel in ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md",
                    ".cursor/rules/agents.mdc", ".windsurf/rules/agents.md",
                    "scripts/health.py", "scripts/sync_hosts.py", "scripts/memory.py",
                    "rules/candidate.schema.json", "rules/memory.schema.json",
                    "14_CANDIDATES/README.md", "15_SYSTEM/memory/README.md",
                    "00_START_HERE/START.md", "skills/loop/SKILL.md"):
            self.assertTrue((self.target / rel).is_file(), "%s is not in the installed brain" % rel)

    def test_a_fresh_brain_answers_honestly_rather_than_with_borrowed_lessons(self):
        """The upstream lessons stay upstream: the installed memory starts at NO_ENTRY."""
        result = run_utf8([sys.executable, str(SCRIPTS / "memory.py"), "--root", str(self.target),
                           "--recall", "first session"], cwd=str(self.target))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NO_ENTRY", result.stdout)
        self.assertNotIn("mem-child-output-encoding", result.stdout)

    def test_a_fresh_brain_can_learn_a_lesson_and_retrieve_it(self):
        proof = self.target / "00_Inbox" / "proof.md"
        proof.write_text("# proof\n", encoding="utf-8")
        added = run_utf8([sys.executable, str(SCRIPTS / "memory.py"), "--root", str(self.target),
                         "--add", "--id", "mem-installed", "--cue", "the gate printed nothing",
                         "--lesson", "print the row and the reason", "--evidence",
                         "00_Inbox/proof.md", "--confidence", "0.9", "--verdict", "helped"],
                         cwd=str(self.target))
        self.assertEqual(added.returncode, 0, added.stdout + added.stderr)
        recalled = run_utf8([sys.executable, str(SCRIPTS / "memory.py"), "--root", str(self.target),
                            "--recall", "gate printed nothing"], cwd=str(self.target))
        self.assertIn("mem-installed", recalled.stdout)
        checked = run_utf8([sys.executable, str(SCRIPTS / "memory.py"), "--root", str(self.target)],
                           cwd=str(self.target))
        self.assertEqual(checked.returncode, 0, checked.stdout)


def build_root(root):
    """A repo-shaped folder holding exactly what the entrypoint is allowed to name.

    The file list is derived from the projection body itself, so the fixture cannot fall
    behind the door: when a new path is quoted in the entrypoint, it gets copied here too.
    """
    for rel in sorted(set(sync_hosts.PATH_IN_BACKTICKS.findall(sync_hosts.body("GitHub Copilot")))):
        src, dst = ROOT / rel, root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy(str(src), str(dst))
    return root


if __name__ == "__main__":
    unittest.main()
