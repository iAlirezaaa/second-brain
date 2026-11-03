"""Regression tests for consistent MCP descriptions, gate tables and generated output."""
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
import health  # noqa: E402
import mcp_server  # noqa: E402


class RepoContractTests(unittest.TestCase):
    def test_registered_mcp_surface_equals_live_server(self):
        self.assertEqual([], mcp_server.registry_surface_problems(ROOT))
        data = json.loads((ROOT / "11_CONTROL/mcp/MCP-E1807E50-second-brain-bridge.json")
                          .read_text(encoding="utf-8"))
        self.assertEqual({row["name"] for row in mcp_server.TOOLS},
                         set(data["tools_exposed"]))

    def test_registry_mcp_drift_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "11_CONTROL/mcp/MCP-E1807E50-second-brain-bridge.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"tools_exposed": ["imaginary_tool"]}),
                            encoding="utf-8")
            problems = mcp_server.registry_surface_problems(root)
            self.assertTrue(any("missing" in item for item in problems))
            self.assertTrue(any("phantom" in item for item in problems))

    def test_missing_mcp_registry_is_a_repo_defect_not_a_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "pyproject.toml").write_text("[project]", encoding="utf-8")
            self.assertTrue(mcp_server.registry_surface_problems(root))

    def test_duplicate_mcp_tool_grants_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "11_CONTROL/mcp/MCP-E1807E50-second-brain-bridge.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({"tools_exposed": ["capabilities", "capabilities"]}),
                            encoding="utf-8")
            self.assertTrue(any("duplicate" in row
                                for row in mcp_server.registry_surface_problems(root)))

    def test_contributing_documents_every_health_gate_once(self):
        doc = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
        tick = chr(96)
        section = doc.split("## The gates " + tick + "health.py" + tick + " runs", 1)[1].split(
            "## What a good PR looks like", 1)[0]
        names = re.findall(r'^\| ' + tick + r'scripts/([^' + tick + r']+)' + tick + r' \|',
                           section, flags=re.MULTILINE)
        self.assertEqual(len(health.GATES), len(names))
        normalized = [name if name in health.GATES
                      else name.split(" --check")[0] for name in names]
        self.assertCountEqual(health.GATES, normalized)

    def test_generated_wiki_site_is_ignored(self):
        result = subprocess.run(["git", "check-ignore", "-q", "02_WIKI/_site/index.html"],
                                cwd=ROOT, check=False)
        self.assertEqual(0, result.returncode)

    def test_candidate_rules_no_longer_cite_nonexistent_phase(self):
        doc = (ROOT / "14_CANDIDATES/README.md").read_text(encoding="utf-8")
        self.assertNotIn("Phase 9.5", doc)
        self.assertIn("scripts/probe.py", doc)


if __name__ == "__main__":
    unittest.main()
