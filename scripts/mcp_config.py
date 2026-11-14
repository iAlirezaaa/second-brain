#!/usr/bin/env python3
"""Print a local MCP host config; never read or modify host settings.

Usage:
  python scripts/mcp_config.py --client claude-desktop
  python scripts/mcp_config.py --client claude-code  # for --mcp-config; no host settings changed
  python scripts/mcp_config.py --client opencode  # V2, disabled by default
  python scripts/mcp_config.py --client codex     # TOML, disabled by default

The snippet contains absolute paths for this checkout and the Python interpreter
running this script. Re-run it if either moves; do not commit machine-local JSON.
"""
import argparse
import json
import sys
from pathlib import Path

SERVER = Path("15_SYSTEM") / "scripts" / "mcp_server.py"
CLIENTS = ("claude-desktop", "claude-code", "opencode", "codex")


def _toml_string(value):
    """Encode a TOML basic string, including supplementary Unicode and Windows paths."""
    quoted = json.dumps(str(value), ensure_ascii=False)
    # JSON escapes ASCII controls like TOML, but JSON's \u surrogate pairs
    # for emoji are invalid TOML. Emit actual TOML \UXXXXXXXX escapes.
    def escape(char):
        point = ord(char)
        if point > 0xFFFF:
            return "\\U%08X" % point
        if point > 0x7F:
            return "\\u%04X" % point
        return char
    return "".join(escape(char) for char in quoted)


def generate(client, root, python_executable):
    """Return a minimal host config, or refuse a non-repository server path."""
    if client not in CLIENTS:
        raise ValueError("unknown client: %s" % client)
    root = Path(root).expanduser().resolve()
    server = root / SERVER
    # Checking only the final file misses a symlinked scripts/ directory: an
    # apparently valid host snippet could then launch code outside the checkout.
    # Reject any symlinked component and resolve again for Windows junctions.
    components = (root / "15_SYSTEM", root / "15_SYSTEM" / "scripts", server)
    if (not (root / "AGENTS.md").is_file()
            or any(component.is_symlink() for component in components)
            or not server.resolve().is_relative_to(root)
            or not server.is_file()):
        raise ValueError("not a Second Brain OS checkout: expected AGENTS.md and a regular " 
                         "15_SYSTEM/scripts/mcp_server.py under --root")
    executable = Path(python_executable).expanduser().absolute()
    if not executable.is_file():
        raise ValueError("Python interpreter is not an executable file; use Python 3.9+")
    # Claude Code --mcp-config accepts the same stdio mcpServers JSON.
    # Merely emitting JSON is not permission to invoke this server's write tools.
    if client in ("claude-desktop", "claude-code"):
        return {"mcpServers": {"second-brain": {
            "command": str(executable), "args": [str(server)]}}}
    if client == "codex":
        # Codex CLI's local stdio server shape; users decide whether to enable.
        # No client config is read or written and no process is started.
        return ("[mcp_servers.second-brain]\n"
                "command = " + _toml_string(executable) + "\n"
                "args = [" + _toml_string(server) + "]\n"
                "enabled = false\n")
    # Prefer the native OpenCode V2 mcp.servers shape. V2 still accepts
    # supported V1 config for migration. Leave this entry disabled pending
    # human review of the server's existing write-capable tools
    # because this server currently advertises write-capable tools.
    return {"mcp": {"servers": {"second-brain": {"type": "local",
             "command": [str(executable), str(server)], "disabled": True}}}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", choices=CLIENTS, required=True)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1],
                        help="repo path (defaults to checkout containing this script)")
    args = parser.parse_args(argv)
    try:
        configuration = generate(args.client, args.root, sys.executable)
    except ValueError as exc:
        parser.error(str(exc))
    # Both JSON and TOML stay ASCII even when the paths contain non-ASCII,
    # so legacy Windows console encodings cannot corrupt a copied snippet.
    if isinstance(configuration, str):
        print(configuration, end="")
    else:
        print(json.dumps(configuration, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
