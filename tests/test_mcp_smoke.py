"""Exercise the shipped MCP server over stdio with no real user data."""
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mcp_smoke.py"


class MCPSmokeTests(unittest.TestCase):
    def test_real_door_handshake_source_and_denied_write(self):
        run = subprocess.run([sys.executable, str(SCRIPT)], cwd=str(ROOT),
                             capture_output=True, text=True, encoding="utf-8",
                             errors="replace", timeout=60)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        report = json.loads(run.stdout)
        self.assertEqual(report["status"], "ok")
        self.assertEqual(report["transport"], "stdio-newline-jsonrpc")
        self.assertEqual(report["protocol"], "2025-06-18")
        self.assertGreaterEqual(report["tools_listed"], 2)
        self.assertEqual(report["source_path"], "02_WIKI/mcp-smoke-note.md")
        self.assertTrue(report["strict_write_refused"])
        self.assertTrue(report["no_candidate_written"])
        self.assertTrue(report["synthetic"])

    def test_missing_server_is_refused_before_launch(self):
        spec = importlib.util.spec_from_file_location("mcp_smoke", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileNotFoundError):
                module.run_probe(server=Path(td) / "missing-mcp.py", timeout=2)


if __name__ == "__main__":
    unittest.main()
