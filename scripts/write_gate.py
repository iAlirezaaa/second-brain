#!/usr/bin/env python
"""Write gate — pre-write lint for anything an agent copies into the vault.

Blocks: model-injection phrases, zero-width/invisible characters, obvious secrets,
credit-card-like numbers. Git history is forever; keep it clean.

Usage: python scripts/write_gate.py [--file path | --text "..."]
Exit 0 = clean, exit 1 = blocked, exit 2 = refused (the input could not be
inspected). Refusal is never reported as clean: a gate that says "OK" about a
file it never read is worse than no gate.
"""
import argparse
import re
import sys
from pathlib import Path

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"disregard\s+(all\s+)?(previous|prior|your)\s+(instructions|rules)",
    r"you\s+are\s+now\s+(a|an)\s+(different|new|unrestricted)",
    r"system\s*prompt\s*:",
    r"reveal\s+your\s+(instructions|system\s+prompt)",
]
ZERO_WIDTH_RE = re.compile("[\u200b\u200c\u200d\u200e\u200f\u2060\ufeff]")
SECRET_PATTERNS = [
    r"sk-[A-Za-z0-9]{20,}",
    r"gh[pousr]_[A-Za-z0-9]{30,}",
    r"xox[bpao]-[A-Za-z0-9-]{10,}",
    r"AKIA[0-9A-Z]{16}",
    r"\b\d{13,19}\b(?=.*\b(?:card|cc)\b)",
]
COMPILED = [(re.compile(p, re.IGNORECASE), "injection") for p in INJECTION_PATTERNS] + [
    (re.compile(p), "secret") for p in SECRET_PATTERNS] + [
    (ZERO_WIDTH_RE, "invisible-characters")]


def check_text(text):
    violations = []
    lines = text.splitlines()
    for regex, kind in COMPILED:
        for number, line in enumerate(lines, start=1):
            if regex.search(line):
                preview = "".join(ch if ch.isprintable() else "?" for ch in line.strip()[:60])
                violations.append(f"line {number}: {kind}: …{preview}…")
    return violations


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows pipe safety
    except AttributeError:
        pass
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--file")
    group.add_argument("--text")
    args = parser.parse_args()
    if args.file is not None:
        path = Path(args.file)
        if not path.is_file():
            print("REFUSED  not a readable file: %s" % args.file)
            return 2
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print("REFUSED  cannot read %s: %s" % (args.file, exc))
            return 2
    else:
        text = args.text
    violations = check_text(text)
    if violations:
        for violation in violations:
            print(f"BLOCKED  {violation}")
        return 1
    print("OK — clean.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
