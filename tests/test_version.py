"""Version consistency: VERSION, pyproject.toml and README all agree."""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestVersion(unittest.TestCase):
    def test_version_sources_agree(self):
        version_file = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertRegex(version_file, r"^\d+\.\d+\.\d+$")
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
        self.assertIsNotNone(match, "pyproject.toml has no version")
        self.assertEqual(match.group(1), version_file)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn(version_file, readme, "version not referenced in README title")


if __name__ == "__main__":
    unittest.main()
