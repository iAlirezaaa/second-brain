"""Onboarding contract: a fresh clone is navigable and local recall really works.

The integration test uses an isolated, synthetic vault and no network or model.
"""
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ONBOARDING = ("README.md", "skills/first-session/SKILL.md")


def clone_block(text):
    fence = chr(96) * 3
    blocks = re.findall(r"(?ms)^" + fence + r"[^\n]*\n(.*?)^" +
                        fence + r"[ \t]*$", text)
    return next((block for block in blocks if
                 "git clone https://github.com/iAlirezaaa/second-brain-os" in block), None)


class FirstSessionOnboarding(unittest.TestCase):
    def test_every_onboarding_clone_enters_its_actual_directory(self):
        for document in ONBOARDING:
            with self.subTest(document=document):
                text = (ROOT / document).read_text(encoding="utf-8")
                block = clone_block(text)
                self.assertIsNotNone(block, "Onboarding needs a copyable git clone block")
                clone = re.search(
                    r"(?m)^git clone https://github\.com/iAlirezaaa/"
                    r"(?P<repo>[a-zA-Z0-9_.-]+?)(?:\.git)?"
                    r"(?:\s+(?P<destination>[a-zA-Z0-9_.-]+))?\s*$", block)
                self.assertIsNotNone(clone, "Document the exact repository clone")
                cd = re.search(r"(?m)^cd ([a-zA-Z0-9_.-]+)\s*$", block)
                self.assertIsNotNone(cd, "Onboarding must enter the cloned directory")
                self.assertEqual(cd.group(1), clone.group("destination") or clone.group("repo"),
                                 "git clone without a destination creates the repo-named folder")

    def test_first_recall_works_from_synthetic_markdown_without_an_account(self):
        for document in ONBOARDING:
            text = (ROOT / document).read_text(encoding="utf-8")
            with self.subTest(document=document):
                self.assertIn("python scripts/kb.py ingest", text)
                self.assertIn('python scripts/kb.py search "memory"', text)
        self.assertIn(".kb/", (ROOT / ".gitignore").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            notes = home / "02_WIKI"
            notes.mkdir()
            (notes / "example.md").write_text(
                "# Memory example\nA local memory note records source provenance.\n",
                encoding="utf-8")
            script = str(ROOT / "scripts" / "kb.py")
            build = subprocess.run([sys.executable, script, "ingest", "--vault", str(home)],
                                   capture_output=True, text=True, timeout=30)
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            self.assertTrue((home / ".kb" / "kb.sqlite").is_file())
            recall = subprocess.run([sys.executable, script, "search", "memory",
                                     "--vault", str(home)],
                                    capture_output=True, text=True, timeout=30)
            self.assertEqual(recall.returncode, 0, recall.stdout + recall.stderr)
            self.assertIn("02_WIKI/example.md", recall.stdout)


if __name__ == "__main__":
    unittest.main()
