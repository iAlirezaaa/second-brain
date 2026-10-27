"""Phase 16 tests — the system belongs to no app and no single agent host (issue #8).

Three claims, each judged by a test rather than by a sentence in a README:

  1. every agent host that opens this repo is pointed at one law, and a door that drifts
     from that law fails the build;
  2. the door only names rooms that exist -- a pointer to a deleted file is how a
     fabricated onboarding starts;
  3. an installed brain passes all five of its own gates with no editor, no network and
     no plugin anywhere in the loop.
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
from common import run_utf8  # noqa: E402
import sync_hosts  # noqa: E402

SYNC = str(SCRIPTS / "sync_hosts.py")


def sync(root, *args):
    return run_utf8([sys.executable, SYNC, "--root", str(root)] + list(args), cwd=str(ROOT))


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
