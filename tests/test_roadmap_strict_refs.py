"""Adversarial roadmap citation checks."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import roadmap_check as road  # noqa: E402
TICK = chr(96)


class RoadmapCitationHardened(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "pyproject.toml").write_text(
            "[project]\nname='fixture'\n", encoding="utf-8")
        (self.root / "scripts").mkdir()
        (self.root / "scripts" / "version.py").write_text(
            "def main(): pass\n", encoding="utf-8")
        (self.root / "tests").mkdir()

    def run_plan(self, sentence, filename="custom-plan.md"):
        plan = self.root / filename
        plan.write_text(sentence, encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "roadmap_check.py"),
             "--root", str(self.root), "--plan", str(plan)],
            capture_output=True, text=True, encoding="utf-8", errors="replace")

    def cited(self, value):
        return "- [x] " + TICK + value + TICK + "\n"

    def test_script_with_flags_is_a_real_path_citation(self):
        kind, path, *_ = road.shape_of("scripts/version.py --check")
        self.assertEqual("path", kind)
        self.assertEqual("scripts/version.py", path)
        result = self.run_plan(self.cited("scripts/version.py --check"))
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("EXISTS 1", result.stdout)

    def test_codeowners_has_no_extension_but_is_a_path(self):
        self.assertEqual("path", road.shape_of(".github/CODEOWNERS")[0])

    def test_basename_in_source_never_proves_missing_path(self):
        (self.root / "tests" / "example.py").write_text(
            "OUTPUT = 'does-not-exist.md'\n", encoding="utf-8")
        result = self.run_plan(self.cited("02_WIKI/does-not-exist.md"))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("MISSING", result.stdout)

    def test_exact_full_path_is_a_declaration_only(self):
        (self.root / "scripts" / "writer.py").write_text(
            "OUTPUT = '02_WIKI/generated-note.md'\n", encoding="utf-8")
        result = self.run_plan(self.cited("02_WIKI/generated-note.md"))
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("DECLARED 1", result.stdout)

    def test_misspelled_local_root_cannot_be_foreign(self):
        result = self.run_plan(self.cited("scriptsS/version.py"))
        self.assertEqual(1, result.returncode, result.stdout)
        self.assertIn("did you mean scripts", result.stdout)

    def test_noted_label_names_the_supplied_plan(self):
        result = self.run_plan(self.cited("external-project/file.js"))
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("NOTED    custom-plan.md:1", result.stdout)
        self.assertNotIn("NOTED    ROADMAP.md", result.stdout)

    def test_skipped_tokens_are_reported(self):
        result = self.run_plan(
            "- [x] " + TICK + "hello" + TICK + " and " +
            TICK + "scripts/version.py --check" + TICK + "\n")
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertIn("1 skipped non-path token(s)", result.stdout)


if __name__ == "__main__":
    unittest.main()
