"""Phase 1 test: vault template structure + contract files are present and consistent."""
import json
import os
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT = ROOT / "vault-template"


class TestStructure(unittest.TestCase):
    def test_required_contract_files_exist(self):
        for name in ["AGENTS.md", "CLAUDE.md", "index.md"]:
            self.assertTrue((VAULT / name).is_file(), f"missing {name}")

    def test_all_zones_exist_on_disk(self):
        zones_file = ROOT / "rules" / "zones.json"
        zones = json.loads(zones_file.read_text(encoding="utf-8"))["zones"]
        for zone in zones:
            self.assertTrue((VAULT / zone).is_dir(), f"zone folder missing: {zone}")

    def test_zones_json_valid_and_nonempty(self):
        data = json.loads((ROOT / "rules" / "zones.json").read_text(encoding="utf-8"))
        self.assertIn("zones", data)
        self.assertIn("agent_create_only_in", data)
        for zone in data["agent_create_only_in"]:
            self.assertIn(zone, data["zones"])

    def test_schema_json_valid(self):
        schema = json.loads((ROOT / "rules" / "schema.json").read_text(encoding="utf-8"))
        fields = schema["required_fields"]
        for field in ["id", "type", "title", "status", "owner", "topics", "created", "updated"]:
            self.assertIn(field, fields)

    def test_no_broken_wikilinks_in_templates(self):
        # rule 1 proof: shipped template itself must be clean
        import subprocess, sys
        script = ROOT / "scripts" / "link_check.py"
        if not script.exists():  # Phase 2 not started yet
            self.skipTest("link_check.py not implemented yet")
        result = subprocess.run([sys.executable, str(script), "--vault", str(VAULT)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
