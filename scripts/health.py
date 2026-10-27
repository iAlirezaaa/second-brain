#!/usr/bin/env python
"""Composite health check — the one command to run before anything ships.

Usage: python scripts/health.py [--vault path]
Runs: link_check + frontmatter_check + candidate_check. Exit 0 only if all green.
The third gate judges the quarantine shelf, not the vault, so it takes the repo root
and stays quiet while the shelf is empty.
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root, run_utf8

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass


# vault gates take --vault; the shelf gate takes the repo root instead
def gate_argv(script, vault_args):
    here = str(Path(__file__).parent / script)
    if script == "candidate_check.py":
        return [sys.executable, here]
    return [sys.executable, here] + vault_args


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None)
    args = parser.parse_args()
    root = find_root(Path(__file__))
    vault_args = ["--vault", args.vault] if args.vault else []
    codes = []
    for script in ["link_check.py", "frontmatter_check.py", "candidate_check.py"]:
        result = run_utf8(gate_argv(script, vault_args), cwd=str(root))
        print(result.stdout.strip())
        if result.stderr.strip():
            print("STDERR: %s" % result.stderr.strip())
        codes.append(result.returncode)
    return 0 if all(code == 0 for code in codes) else 1


if __name__ == "__main__":
    sys.exit(main())
