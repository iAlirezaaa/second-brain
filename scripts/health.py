#!/usr/bin/env python
"""Composite health check — the one command to run before anything ships.

Usage: python scripts/health.py [--vault path]
Runs every gate in GATES, in order: link_check, link_check --readout, frontmatter_check,
plane_check, candidate_check, memory, sync_hosts, doc_report, vector_check, issues, version,
ci_floor, goldfish_check, schema_stamp, roadmap_check. Exit 0 only if all green.

The first three judge the vault; the rest judge the machine plane — the memory-plane map, the
quarantine shelf, the lesson ledger, the host doors, the numbers in the documents, the embedder
seam, the issue ledger, the release number, the python floor CI installs, the goldfish review
artifacts, the `schema_version` stamp inside every generated JSON file, and the paths the
roadmap cites. Five of them judge paperwork an installed brain home does not keep (`version.py`,
`ci_floor.py`, `goldfish_check.py`, `issues.py` and `roadmap_check.py`): a release number, a CI
matrix, review artifacts, an issue ledger and a plan are promises the repo that builds them made,
so in a home each prints one OK line naming what is absent and why the promise is not its own to
keep, rather than crashing or inventing a defect. `schema_stamp.py` has the same problem in a
different shape — in a home it judges the JSON files the home actually carries, so its
denominator changes while its verdict does not. `tests/test_phase16_host_independence.py`
counts the OK lines against this list, so a gate cannot go quiet and a skip cannot be silent.
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
ROOT_ONLY_GATES = {"plane_check.py": [], "candidate_check.py": [], "memory.py": ["--check"],
                   "sync_hosts.py": ["--check"], "doc_report.py": ["--check"],
                   "vector_check.py": [], "issues.py": ["--check"],
                   "version.py": ["--check"], "ci_floor.py": [], "goldfish_check.py": [],
                   "schema_stamp.py": ["--check"], "roadmap_check.py": ["--check"]}

# the gate list is a measure: doc_report.py counts it instead of typing a number.
# an entry may carry its own flags -- "link_check.py --readout" runs the same script a second
# way, because the broken-link verdict and the graph-shape verdict are different claims
GATES = ["link_check.py", "link_check.py --readout", "frontmatter_check.py", "plane_check.py",
         "candidate_check.py", "memory.py", "sync_hosts.py", "doc_report.py", "vector_check.py",
         "issues.py", "version.py", "ci_floor.py", "goldfish_check.py",
         "schema_stamp.py --check", "roadmap_check.py --check"]


def gate_argv(script, vault_args):
    parts = script.split()
    here = str(Path(__file__).parent / parts[0])
    extra = parts[1:]
    if parts[0] in ROOT_ONLY_GATES:
        return [sys.executable, here] + extra + ROOT_ONLY_GATES[parts[0]]
    return [sys.executable, here] + extra + vault_args


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
