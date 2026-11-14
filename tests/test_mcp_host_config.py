"""MCP host config must be copyable, safe, and independent of client cwd."""
import ast
import importlib.util
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
        # Windows TemporaryDirectory can yield an 8.3 RUNNER~1 alias; the
        # generator correctly resolves --root before emitting the server path.
        self.assertEqual(cfg["args"], [str(self.server.resolve())])
        self.assertTrue(Path(cfg["args"][0]).is_absolute())

        # Claude Code's explicit --mcp-config file accepts the same stdio
        # mcpServers JSON; generation must not register or enable tools.
        code_run = self.invoke("claude-code")
        self.assertEqual(code_run.returncode, 0, code_run.stderr)
        self.assertTrue(code_run.stdout.isascii())
        self.assertEqual(json.loads(code_run.stdout), json.loads(run.stdout))
        # Generated machine-local host configs should not appear in git add -A.
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("second-brain.mcp.local.json", ignored)

    def test_opencode_has_local_mcp_command_and_absolute_paths(self):
        run = self.invoke("opencode")
        self.assertEqual(run.returncode, 0, run.stderr)
        parsed = json.loads(run.stdout)
        # Assert the native OpenCode V2 shape, not just the accepted
        # V1 compatibility syntax that our old test could not distinguish.
        self.assertEqual(set(parsed["mcp"]), {"servers"})
        self.assertEqual(set(parsed["mcp"]["servers"]), {"second-brain"})
        cfg = parsed["mcp"]["servers"]["second-brain"]
        self.assertEqual(cfg["type"], "local")
        self.assertEqual(set(cfg), {"type", "command", "disabled"})
        self.assertIs(cfg["disabled"], True)
        self.assertEqual(cfg["command"], [str(Path(sys.executable).absolute()),
                                           str(self.server.resolve())])
        example = json.loads((ROOT / "15_SYSTEM" / "integrations" /
                              "opencode.example.json").read_text(encoding="utf-8"))
        template = example["mcp"]["servers"]["second-brain"]
        self.assertEqual(set(template), set(cfg))
        self.assertIs(template["disabled"], True)
        self.assertNotIn("enabled", template)

        # Codex uses TOML, not the JSON schemas above; start disabled because
        # this MCP server exposes proposal/import writes.
        run = self.invoke("codex")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.splitlines()[0], "[mcp_servers.second-brain]")
        self.assertIn("enabled = false\n", run.stdout)
        # TOML basic strings escape non-ASCII as \\u/\\U with case-insensitive
        # hexadecimal digits. Comparing to JSON serialization spuriously fails
        # on valid uppercase escapes, as seen on every OS in CI #43537155432.
        # ast.literal_eval round-trips the two string fields on Python 3.9;
        # Python 3.11+ additionally checks the complete TOML using tomllib.
        lines = run.stdout.splitlines()
        self.assertEqual(len(lines), 4)
        self.assertTrue(run.stdout.isascii())
        self.assertEqual(ast.literal_eval(lines[1].split(" = ", 1)[1]),
                         str(Path(sys.executable).absolute()))
        self.assertEqual(ast.literal_eval(lines[2].split(" = ", 1)[1]),
                         [str(self.server.resolve())])
        self.assertEqual(lines[3], "enabled = false")
        # TOML needs \UXXXXXXXX for emoji; JSON's surrogate-pair escape is invalid.
        spec = importlib.util.spec_from_file_location("mcp_host_config", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(module._toml_string("brain فارسی 🚀"),
                         '"brain \\u0641\\u0627\\u0631\\u0633\\u06CC \\U0001F680"')
        try:
            import tomllib
        except ImportError:  # Python 3.9: stdlib TOML reader is not available
            tomllib = None
        if tomllib:
            parsed = tomllib.loads(run.stdout)["mcp_servers"]["second-brain"]
            self.assertEqual(parsed["command"], str(Path(sys.executable).absolute()))
            self.assertEqual(parsed["args"], [str(self.server.resolve())])
            self.assertIs(parsed["enabled"], False)

    def test_missing_server_refuses_without_printing_a_config(self):
        self.server.unlink()
        for client in ("claude-desktop", "claude-code", "opencode", "codex"):
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
        for client in ("claude-desktop", "claude-code", "opencode", "codex"):
            with self.subTest(client=client):
                run = self.invoke(client)
                self.assertNotEqual(run.returncode, 0)
                self.assertEqual(run.stdout, "")

        # A regular mcp_server.py behind a symlinked PARENT directory
        # must also be refused. is_symlink() on the final file alone
        # returns False for this external-target escape.
        self.server.unlink()
        self.server.parent.rmdir()
        outside_scripts = Path(self.tmp.name) / "outside-scripts"
        outside_scripts.mkdir()
        (outside_scripts / "mcp_server.py").write_text("# synthetic external target\\n",
                                                        encoding="utf-8")
        try:
            self.server.parent.symlink_to(outside_scripts, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("directory symlinks are restricted by this platform")
        self.assertFalse(self.server.is_symlink())
        self.assertTrue(self.server.is_file())
        self.assertFalse(self.server.resolve().is_relative_to(self.repo.resolve()))
        for client in ("claude-desktop", "claude-code", "opencode", "codex"):
            with self.subTest(parent_symlink=True, client=client):
                run = self.invoke(client)
                self.assertNotEqual(run.returncode, 0, run.stdout)
                self.assertEqual(run.stdout, "")
                self.assertIn("not a Second Brain OS checkout", run.stderr)

    def test_generator_never_writes_to_a_host_settings_file(self):
        fake_config = Path(self.tmp.name) / "claude_desktop_config.json"
        fake_config.write_text('{"keep":true}\n', encoding="utf-8")
        fake_codex = Path(self.tmp.name) / "config.toml"
        fake_codex.write_text('# KEEP THIS FILE\n', encoding="utf-8")
        for client in ("claude-desktop", "claude-code", "opencode", "codex"):
            with self.subTest(client=client):
                run = self.invoke(client)
                self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(fake_config.read_text(encoding="utf-8"), '{"keep":true}\n')
        self.assertEqual(fake_codex.read_text(encoding="utf-8"), '# KEEP THIS FILE\n')


if __name__ == "__main__":
    unittest.main()
