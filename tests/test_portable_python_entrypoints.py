"""Prevent onboarding docs from pinning an interpreter the user may not have.

Issue #46: the Windows launcher pin py -3.10 failed on a machine with
supported Python versions but no 3.10. The tested floor is 3.9, not a pin.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sync_hosts  # noqa: E402

PUBLIC_ENTRYPOINTS = (
    "AGENTS.md",
    "README.md",
    "00_START_HERE/START.md",
    "CONTRIBUTING.md",
    "skills/first-session/SKILL.md",
    "skills/self-audit/SKILL.md",
    "scripts/sync_hosts.py",
)


class PortablePythonEntrypoints(unittest.TestCase):
    def test_no_uninstalled_python_pin_in_public_entrypoints(self):
        """A current installation of Python >=3.9 must work without 3.10."""
        for rel in PUBLIC_ENTRYPOINTS:
            with self.subTest(path=rel):
                content = (ROOT / rel).read_text(encoding="utf-8")
                self.assertNotIn("py -3.10", content, rel)
        start = (ROOT / "00_START_HERE/START.md").read_text(encoding="utf-8")
        self.assertIn("python scripts/first_success.py --repeat 3", start)
        self.assertIn("python 15_SYSTEM", start)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("python scripts/health.py", readme)

    def test_every_agent_host_projection_is_fresh_and_portable(self):
        """Host files are rendered, not independently edited into another law."""
        for _key, host, rel, needs_mdc in sync_hosts.HOSTS:
            with self.subTest(host=host):
                projection = (ROOT / rel).read_text(encoding="utf-8")
                self.assertEqual(projection, sync_hosts.render(host, needs_mdc))
                self.assertNotIn("py -3.10", projection)


if __name__ == "__main__":
    unittest.main()
