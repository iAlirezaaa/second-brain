#!/usr/bin/env python
"""Composite health check — the one command to run before anything ships.

Usage: python scripts/health.py [--vault path]
Runs: link_check + frontmatter_check. Exit 0 only if all green.
"""
import subprocess
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None)
    args = parser.parse_args()
    root = find_root(Path(__file__))
    vault_args = ["--vault", args.vault] if args.vault else []
    codes = []
    for script in ["link_check.py", "frontmatter_check.py"]:
        result = subprocess.run([sys.executable, str(Path(__file__).parent / script)] + vault_args,
                                capture_output=True, text=True)
        print(result.stdout.strip())
        codes.append(result.returncode)
    return 0 if all(code == 0 for code in codes) else 1


if __name__ == "__main__":
    sys.exit(main())
