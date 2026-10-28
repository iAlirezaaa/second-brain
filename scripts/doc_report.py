#!/usr/bin/env python
"""Measured numbers for the documents — because a typed number is a claim, not a fact.

Issues #4 and #10: the README showed a hand-typed "tests: 39 green" badge while the suite had
already grown past 58, and HANDOFF/START quoted "zones present: 16/16 | registry records: 0"
read from the owner's seeded folder. A fresh clone reproduced none of it. A number in a
document is the kind of thing an agent repeats to a human, so it is now generated.

Every doc carries a block between two markers; this script owns everything inside it and
nothing outside it. `--check` compares the block on disk with a measurement taken right now,
so a stale number fails `health.py` (sixth gate) and CI instead of quietly becoming lore.

Usage:
  python scripts/doc_report.py            # print the measurement
  python scripts/doc_report.py --check    # the gate: exit 1 on a stale or missing block
  python scripts/doc_report.py --write    # refresh the block in every stamped document
"""
import argparse
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import memory as memory_mod
from common import find_root, load_json

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

BEGIN = "<!-- BEGIN measured — written by `python scripts/doc_report.py --write` -->"
END = "<!-- END measured -->"
DOCS = ("README.md", "HANDOFF.md", "00_START_HERE/START.md")
# what a measurement needs in order to mean anything; folders that merely hold counts are
# allowed to be absent -- a brain installed without the test suite measures zero tests,
# which is honest, whereas a gate that crashes looks like a gate that stayed quiet.
REQUIRED = ("15_SYSTEM/config/system.json", "scripts/health.py")
PYTHON_FLOOR = "3.9 (standard library only)"


def collected_tests(root):
    """How many cases `tests/` holds -- discovered, not executed, so this stays fast.

    The count is what a document claims; running them is CI's job. Discovery still has to
    import every module, so a test file that fails to load is counted as a _FailedTest and
    still shows up as a number the gate can move.
    """
    folder = Path(root) / "tests"
    if not folder.is_dir():
        return 0
    loader = unittest.TestLoader()
    return loader.discover(str(folder), pattern="test_*.py").countTestCases()


def gates(root):
    import health
    return len(health.GATES)  # the gate list itself is the measure, not a remembered number


def measures(root):
    root = Path(root)
    records = len(list((root / "11_CONTROL").rglob("*.json")))
    skills = len(list((root / "skills").glob("*/SKILL.md")))
    rows = len(list((root / "14_CANDIDATES" / "loop").glob("cand-*.md")))
    lessons = len(memory_mod.active(memory_mod.read_lessons(root)[0]))
    cfg = load_json(root / "15_SYSTEM" / "config" / "system.json")
    declared = len(cfg["zones"])
    ignored = set(cfg.get("gitignore_required_paths") or ())

    def clone_visible(zone_dir):
        """A fresh clone reproduces this zone's presence only if it is not gitignored.
        Machine-local state (12_RUNTIME appearing on the writing machine) must never
        move a measured number -- that is how a green office becomes a red clone."""
        for entry in ignored:
            entry = str(entry).rstrip("/")
            if entry == zone_dir or entry.startswith(zone_dir + "/"):
                return False
        return True

    present = len([z for z in cfg["zones"]
                   if (root / z["dir"]).exists() and clone_visible(z["dir"])])
    import sync_hosts
    return [
        ("tests collected (`python -m unittest discover -s tests`)", collected_tests(root)),
        ("health gates (`python scripts/health.py`)", gates(root)),
        ("registry records (`11_CONTROL/**/*.json`)", records),
        ("skills in the pack (`skills/*/SKILL.md`)", skills),
        ("agent-host doors (`python scripts/sync_hosts.py --list`)", len(sync_hosts.HOSTS)),
        ("active lessons (`15_SYSTEM/memory/lessons.jsonl`)", lessons),
        ("candidate rows on the shelf (`14_CANDIDATES/loop`)", rows),
        ("kinds in the contract (`15_SYSTEM/config/system.json`)", len(cfg["kinds"])),
        ("relation types in the contract", len(cfg["relations"])),
        ("zones a fresh clone reproduces / declared (`12_RUNTIME`, `13_LAB` are gitignored)",
         "%d / %d" % (present, declared)),
        ("python floor", PYTHON_FLOOR),
    ]


def table(root):
    lines = ["| measure | now |", "| --- | --- |"]
    try:
        rows = measures(root)
    except (OSError, ValueError, KeyError, ImportError) as exc:
        # handoff.py stamps this block into §1 of a folder that may not be measurable (a
        # temp dir in a test, a half-installed brain). A handoff that crashes is worse than
        # a handoff that says it could not measure: the next session loses its resume point.
        # The failure takes the place of the numbers, so it is visible instead of silent.
        rows = [("measurement", "FAILED: %s: %s" % (type(exc).__name__, exc))]
    for label, value in rows:
        lines.append("| %s | %s |" % (label, value))
    return "\n".join(lines)


def block(root, body=None):
    return "%s\n%s\n%s" % (BEGIN, table(root) if body is None else body, END)


def stamped(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    if BEGIN not in text or END not in text:
        return None
    return text.split(BEGIN, 1)[1].split(END, 1)[0].strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--check", action="store_true", help="the gate: stale or missing block")
    parser.add_argument("--write", action="store_true", help="refresh every stamped document")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    absent = [rel for rel in REQUIRED if not (root / rel).exists()]
    if absent:
        # a gate that raises looks exactly like a gate that said nothing; say what is missing
        for rel in absent:
            print("UNMEASURABLE %s is not in this folder, so its number cannot be read" % rel)
        print("REFUSED: the measurement needs inputs that are not here")
        return 1
    body = table(root)          # measured exactly once per run; every branch compares to it
    wanted = block(root, body)

    if not args.check and not args.write:
        print(body)
        return 0

    problems, updated = [], []
    for rel in DOCS:
        path = root / rel
        if not path.is_file():
            problems.append("%s: named by the doc report but not on disk" % rel)
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if BEGIN in text and END not in text:
            # never write into it: the rest of the file would be swallowed as old numbers
            problems.append("%s: a measured block opens here and never closes — everything "
                            "after the marker would be eaten" % rel)
            continue
        if BEGIN not in text:
            if not args.write:
                problems.append("%s: carries no measured block — a typed number is a claim "
                                "nobody re-measures" % rel)
                continue
            path.write_text(text.rstrip() + "\n\n" + wanted + "\n", encoding="utf-8")
            updated.append(rel)
            continue
        if args.write:
            head, rest = text.split(BEGIN, 1)
            _old, tail = rest.split(END, 1)
            path.write_text(head + wanted + tail, encoding="utf-8")
            updated.append(rel)
        elif stamped(path) != table(root):
            problems.append("%s: the block is stale — run python scripts/doc_report.py --write"
                            % rel)
    if problems:
        for problem in problems:
            print("STALE     %s" % problem)
        print("REFUSED: a number in these documents is no longer a measurement")
        return 1
    if updated:
        print("WROTE measured blocks into %d document(s): %s" % (len(updated), ", ".join(updated)))
        return 0
    print("OK — every measured number in %s matches the state of this folder right now." %
          ", ".join(DOCS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
