#!/usr/bin/env python
"""Composite health check — the one command to run before anything ships.

Usage: python scripts/health.py [--vault path]
Runs every gate in GATES: link_check + frontmatter_check + candidate_check + memory +
sync_hosts + doc_report. Exit 0 only if all green. All but the first two judge the machine
plane (the quarantine shelf, the lesson ledger, the host doors, the numbers in the documents),
so they take the repo root and stay quiet while those files are empty.
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


# vault gates take --vault; the machine-plane gates take the repo root instead
ROOT_ONLY_GATES = {"candidate_check.py": [], "memory.py": ["--check"],
                   "sync_hosts.py": ["--check"], "doc_report.py": ["--check"]}

# the gate list is a measure: doc_report.py counts it instead of typing a number
GATES = ["link_check.py", "frontmatter_check.py", "candidate_check.py", "memory.py",
         "sync_hosts.py", "doc_report.py"]


def gate_argv(script, vault_args):
    here = str(Path(__file__).parent / script)
    if script in ROOT_ONLY_GATES:
        return [sys.executable, here] + ROOT_ONLY_GATES[script]
    return [sys.executable, here] + vault_args


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None)
    args = parser.parse_args()
    root = find_root(Path(__file__))
    vault_args = ["--vault", args.vault] if args.vault else []
    codes = []
    for script in GATES:
        result = run_utf8(gate_argv(script, vault_args), cwd=str(root))
        print(result.stdout.strip())
        if result.stderr.strip():
            print("STDERR: %s" % result.stderr.strip())
        codes.append(result.returncode)
    return 0 if all(code == 0 for code in codes) else 1


if __name__ == "__main__":
    sys.exit(main())
