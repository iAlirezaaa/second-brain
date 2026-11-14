#!/usr/bin/env python3
"""Print a local MCP host config; never read or modify host settings.

Usage:
  python scripts/mcp_config.py --client claude-desktop
  python scripts/mcp_config.py --client opencode  # V2, disabled by default

The JSON contains absolute paths for this checkout and the Python interpreter
running this script. Re-run it if either moves; do not commit machine-local JSON.
"""
import argparse
import json
import sys
from pathlib import Path

SERVER = Path("15_SYSTEM") / "scripts" / "mcp_server.py"
CLIENTS = ("claude-desktop", "opencode")


def generate(client, root, python_executable):
    """Return a minimal host config, or refuse a non-repository server path."""
    if client not in CLIENTS:
        raise ValueError("unknown client: %s" % client)
    root = Path(root).expanduser().resolve()
    server = root / SERVER
    if not (root / "AGENTS.md").is_file() or server.is_symlink() or not server.is_file():
        raise ValueError("not a Second Brain OS checkout: expected AGENTS.md and a regular " 
                         "15_SYSTEM/scripts/mcp_server.py under --root")
    executable = Path(python_executable).expanduser().absolute()
    if not executable.is_file():
        raise ValueError("Python interpreter is not an executable file; use Python 3.9+")
    if client == "claude-desktop":
        return {"mcpServers": {"second-brain": {
            "command": str(executable), "args": [str(server)]}}}
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
    # JSON ASCII escaping keeps Unicode filesystem paths safe even under Windows
    # legacy cp1252/console encodings; JSON clients decode the path normally.
    print(json.dumps(configuration, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
