"""MCP host config must be copyable, safe, and independent of client cwd."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mcp_config.py"


class HostConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sbo-mcp-config-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / "brain space فارسی"
        server = self.repo / "15_SYSTEM" / "scripts" / "mcp_server.py"
        server.parent.mkdir(parents=True)
        server.write_text("# Synthetic MCP server; not started\n", encoding="utf-8")
        (self.repo / "AGENTS.md").write_text("# Synthetic checkout\n", encoding="utf-8")
        self.server = server

    def invoke(self, client):
        return subprocess.run([sys.executable, str(SCRIPT), "--client", client,
                               "--root", str(self.repo)], cwd=self.tmp.name,
                              capture_output=True, encoding="utf-8", errors="replace",
                              text=True, timeout=15)

    def test_claude_has_absolute_script_and_interpreter_even_outside_repo(self):
        run = self.invoke("claude-desktop")
        self.assertEqual(run.returncode, 0, run.stderr)
        cfg = json.loads(run.stdout)["mcpServers"]["second-brain"]
        self.assertEqual(cfg["command"], str(Path(sys.executable).absolute()))
        self.assertEqual(cfg["args"], [str(self.server)])
        self.assertTrue(Path(cfg["args"][0]).is_absolute())

    def test_opencode_has_local_mcp_command_and_absolute_paths(self):
        run = self.invoke("opencode")
        self.assertEqual(run.returncode, 0, run.stderr)
        cfg = json.loads(run.stdout)["mcp"]["second-brain"]
        self.assertEqual(cfg["type"], "local")
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["command"], [str(Path(sys.executable).absolute()), str(self.server)])

    def test_missing_server_refuses_without_printing_a_config(self):
        self.server.unlink()
        for client in ("claude-desktop", "opencode"):
            with self.subTest(client=client):
                run = self.invoke(client)
                self.assertNotEqual(run.returncode, 0)
                self.assertEqual(run.stdout, "")
                self.assertIn("not a Second Brain OS checkout", run.stderr)

    def test_symlinked_server_refuses_if_supported(self):
        outside = Path(self.tmp.name) / "not-the-server.py"
        outside.write_text("# fixture\n", encoding="utf-8")
        self.server.unlink()
        try:
            self.server.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("creating symlinks is restricted by this platform")
        run = self.invoke("opencode")
        self.assertNotEqual(run.returncode, 0)
        self.assertEqual(run.stdout, "")

    def test_generator_never_writes_to_a_host_settings_file(self):
        fake_config = Path(self.tmp.name) / "claude_desktop_config.json"
        fake_config.write_text('{"keep":true}\n', encoding="utf-8")
        run = self.invoke("claude-desktop")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(fake_config.read_text(encoding="utf-8"), '{"keep":true}\n')


if __name__ == "__main__":
    unittest.main()
