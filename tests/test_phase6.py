"""Phase 6 tests: installer wiring."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestInstall(unittest.TestCase):
    def test_install_creates_vault_and_agent_wiring(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "brain"
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "install.py"),
                 "--target", str(target)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue((target / "AGENTS.md").is_file())
            self.assertTrue((target / "rules" / "zones.json").is_file())
            self.assertTrue((target / ".claude" / "skills" / "inbox-triage" / "SKILL.md").is_file())
            self.assertTrue((target / ".opencode" / "skills" / "kb-search" / "SKILL.md").is_file())
            self.assertTrue((target / "scripts" / "health.py").is_file())

    def test_install_refuses_nonempty_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "brain"
            target.mkdir()
            (target / "junk.md").write_text(" occupied", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "install.py"),
                 "--target", str(target)],
                capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)  # argparse error
        self.assertIn("not empty", result.stderr)


if __name__ == "__main__":
    unittest.main()
