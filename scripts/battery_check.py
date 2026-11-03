#!/usr/bin/env python
"""Battery gate — the loop that guards shipping must be able to see the v3 battery.

Usage: python scripts/battery_check.py [--battery PATH] [--timeout SECONDS]

`15_SYSTEM/scripts/test_hades.py` is the judge that runs the HADES plane over the wire: it
talks to the MCP door through stdio, exactly like a real harness does. Until this gate existed,
nothing but GitHub Actions ran it, and that is how a commit went public-red while `health.py`
and `python -m unittest discover -s tests` stayed green: the battery asserted that the run
plane was readable through the door, phase 49 closed that plane, and the pre-push loop simply
could not see the contradiction. A test nobody runs before pushing is not a gate — it is a
rumour about a gate.

The battery is self-sandboxing. It copies `15_SYSTEM` into a throwaway vault under the system
temp directory and runs every script there, so judging it cannot touch the real records, the
real registry or the real lesson ledger. That is the whole cost of this gate: the battery's own
seconds, traded against shipping blind.

Exit 0 = the battery is green and the gate printed its count.
Exit 1 = it is red, or it did not finish inside the timeout, or the file is missing from a repo
         checkout (a silent zero-test battery would otherwise look like a passing gate).
An installed brain home is not a source repo: it prints one stated-skip line, the same shape the
other repo-only gates use, so `health.py` keeps exactly one line per gate.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root, is_repo_checkout  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

DEFAULT_TIMEOUT = 900
BATTERY = "15_SYSTEM/scripts/test_hades.py"
SUMMARY_KEY = "checks:"
MAX_REPORTED_FAILURES = 12


def parse_summary(text):
    """The battery's own last summary line, or None when it never printed one."""
    found = None
    for line in text.splitlines():
        if SUMMARY_KEY in line and "failed" in line:
            found = line
    if found is None:
        return None
    counts = {}
    for part in found.split("|"):
        head, _, value = part.strip().partition(":")
        digits = "".join(ch for ch in value if ch.isdigit())
        if digits:
            counts[head.strip().lower()] = int(digits)
    if "checks" not in counts or "failed" not in counts:
        return None
    return counts


def failure_lines(text):
    lines = [line.strip() for line in text.splitlines() if line.startswith("FAIL")]
    return lines[:MAX_REPORTED_FAILURES]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--battery", default=None,
                        help="path to a battery script (default: this repo's v3 battery)")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help="seconds to wait for the battery before calling it red")
    args = parser.parse_args()

    root = find_root(Path(__file__))
    script = Path(args.battery) if args.battery else root / BATTERY

    if not is_repo_checkout(root) and not args.battery:
        print("OK battery — skipped in %s: this folder is an installed brain home, not a source "
              "repo, and the v3 battery judges the source scripts of the repo that builds them"
              % root)
        return 0
    if not script.is_file():
        print("INVALID battery: no battery script at %s, and a gate that runs nothing is not a "
              "pass" % script)
        return 1

    started = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        result = subprocess.run([sys.executable, str(script)], cwd=str(root), env=env,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=args.timeout)
    except subprocess.TimeoutExpired:
        print("INVALID battery: %s did not finish in %d seconds, so its verdict is unknown"
              % (script.name, args.timeout))
        return 1
    took = time.time() - started

    body = (result.stdout or "") + (result.stderr or "")
    summary = parse_summary(body)
    if summary is None:
        print("INVALID battery: %s exited %s without printing a `%s` summary, so nothing was "
              "measured" % (script.name, result.returncode, SUMMARY_KEY))
        return 1
    failed = summary["failed"]
    if result.returncode != 0 or failed != 0:
        print("INVALID battery: %s checks | %d passed | %d failed in %.0fs -- the HADES plane "
              "disagrees with itself, so this tree must not ship"
              % (summary["checks"], summary.get("passed", 0), failed, took))
        for line in failure_lines(body):
            print("  %s" % line[:160])
        return 1

    print("OK battery: %d checks | %d passed | 0 failed in %.0fs, every negative gate in the "
          "HADES plane still bites (`%s`)"
          % (summary["checks"], summary.get("passed", summary["checks"]), took, script.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
