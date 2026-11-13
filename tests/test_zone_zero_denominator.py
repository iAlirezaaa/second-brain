"""Regression tests for issue #60: a zero-proposal zone fence must not pass."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "zone_check.py"


class ZoneZeroDenominatorTests(unittest.TestCase):
    def run_gate(self, payload):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "proposals.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(SCRIPT), "--proposals", str(path)],
                cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
            )

    def test_empty_proposals_refused(self):
        result = self.run_gate({"proposals": []})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("REFUSED", result.stdout)
        self.assertIn("0 proposal", result.stdout)

    def test_nonempty_invalid_proposal_still_rejected(self):
        result = self.run_gate({"proposals": [{"capture": "probe", "target": "__not_a_zone__"}]})
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("REJECTED", result.stdout)

    def test_nonempty_legal_proposal_passes(self):
        config = json.loads((ROOT / "rules" / "zones.json").read_text(encoding="utf-8"))
        target = config["agent_create_only_in"][0]
        result = self.run_gate({"proposals": [{"capture": "probe", "target": target}]})
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
