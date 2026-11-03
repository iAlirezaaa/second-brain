#!/usr/bin/env python
"""Composite health check — the one command to run before anything ships.

Usage: python scripts/health.py [--vault path] [--fast]
Runs every gate in GATES, in order: link_check, link_check --readout, frontmatter_check,
plane_check, candidate_check, memory, sync_hosts, doc_report, vector_check, issues, version,
ci_floor, goldfish_check, schema_stamp, roadmap_check, vault_check, battery_check. Exit 0 only
if all green.

`--fast` prints the battery's one line without spending its seconds; see FAST_SKIPS for what
that is for and for the law it must not break. Every other gate always runs, so `--fast` is a
schedule, not a way to make a red house look green.

The first three judge the vault; the rest judge the machine plane — the memory-plane map, the
quarantine shelf, the lesson ledger, the host doors, the numbers in the documents, the embedder
seam, the issue ledger, the release number, the python floor CI installs, the goldfish review
artifacts, the `schema_version` stamp inside every generated JSON file, the paths the
roadmap cites, the encrypted private vault and its restore evidence, and the v3 battery that
talks to the MCP door over stdio like a real harness. `battery_check.py` exists because the
battery used to be the only judge that nothing but GitHub Actions ran: a commit went public-red
under it while this loop stayed green. Six of them judge paperwork an installed brain home does
not keep (`version.py`, `ci_floor.py`, `goldfish_check.py`, `issues.py`, `roadmap_check.py` and
`battery_check.py`): a release number, a CI matrix, review artifacts, an issue ledger, a plan
and a source-repo test battery are promises the repo that builds them made, so in a home each
prints one OK line naming what is absent and why the promise is not its own to keep, rather
than crashing or inventing a defect. `schema_stamp.py` has the same problem in a different
shape — in a home it judges the JSON files the home actually carries, so its denominator
changes while its verdict does not. `tests/test_phase16_host_independence.py`
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
                   "schema_stamp.py": ["--check"], "roadmap_check.py": ["--check"],
                   "vault_check.py": [], "battery_check.py": []}

# the gate list is a measure: doc_report.py counts it instead of typing a number.
# an entry may carry its own flags -- "link_check.py --readout" runs the same script a second
# way, because the broken-link verdict and the graph-shape verdict are different claims
GATES = ["link_check.py", "link_check.py --readout", "frontmatter_check.py", "plane_check.py",
         "candidate_check.py", "memory.py", "sync_hosts.py", "doc_report.py", "vector_check.py",
         "issues.py", "version.py", "ci_floor.py", "goldfish_check.py",
         "schema_stamp.py --check", "roadmap_check.py --check", "vault_check.py",
         "battery_check.py"]

# `--fast` is about seconds, not about verdicts. The v3 battery re-drives the MCP door over
# stdio, which costs tens of seconds, and `scripts/base.py --save` -- the known-good-base
# pre-flight -- runs the health loop once per save, so a session that saves a dozen bases
# would pay for a dozen batteries it did not need. A base is a claim about the house (the
# vault, the planes, the paperwork), and the battery's claim about the door was already
# measured in the shell minutes earlier by the plain `health.py` the pre-push loop runs.
#
# The rule that keeps this honest: a skipped gate still prints exactly one OK-prefixed line
# naming what was skipped and why, so `len(ok_lines) == len(GATES)` holds in both modes --
# the same law tests/test_phase16_host_independence.py counts. `--fast` cannot silence a gate,
# and it does not touch the exit code of any gate that ran: a red house stays red.
FAST_SKIPS = {"battery_check.py": ("battery",
                                   "skipped by --fast: the door battery spends tens of seconds "
                                   "re-driving the MCP door, and a fast loop is a schedule, not "
                                   "a verdict -- run python scripts/health.py for that")}


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
    parser.add_argument("--fast", action="store_true",
                        help="skip only the gates named in FAST_SKIPS, in their own line")
    args = parser.parse_args()
    root = find_root(Path(__file__))
    vault_args = ["--vault", args.vault] if args.vault else []
    codes = []
    for script in GATES:
        if args.fast and script.split()[0] in FAST_SKIPS:
            label, reason = FAST_SKIPS[script.split()[0]]
            print("OK %s — %s" % (label, reason))
            codes.append(0)
            continue
        result = run_utf8(gate_argv(script, vault_args), cwd=str(root))
        print(result.stdout.strip())
        if result.stderr.strip():
            print("STDERR: %s" % result.stderr.strip())
        codes.append(result.returncode)
    return 0 if all(code == 0 for code in codes) else 1


if __name__ == "__main__":
    sys.exit(main())
