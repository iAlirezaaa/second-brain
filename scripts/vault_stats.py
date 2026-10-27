#!/usr/bin/env python
"""Vault statistics for both audiences.

Usage: python scripts/vault_stats.py [--vault path]
Prints notes per zone, status and owner distribution.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root, iter_markdown, load_json, parse_frontmatter

CONTRACT_FILES = {"AGENTS.md", "CLAUDE.md", "index.md"}


def zone_of(rel_path, zones):
    parts = rel_path.split("/")
    for part in parts[:-1]:
        if part in zones:
            return part
    return "root"


def stats(vault):
    zones = load_json(Path(__file__).parent.parent / "rules" / "zones.json")["zones"]
    per_zone = Counter()
    per_status = Counter()
    per_owner = Counter()
    notes = 0
    for path in iter_markdown(vault):
        if path.name in CONTRACT_FILES:
            continue
        notes += 1
        per_zone[zone_of(path.relative_to(vault).as_posix(), zones)] += 1
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        per_status[fm.get("status") or "no-frontmatter"] += 1
        per_owner[fm.get("owner") or "no-frontmatter"] += 1
    return {"total_notes": notes, "per_zone": dict(per_zone),
            "per_status": dict(per_status), "per_owner": dict(per_owner)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = find_root(Path(__file__))
    vault = Path(args.vault) if args.vault else root / "vault-template"
    result = stats(vault)
    if args.json:
        print(json.dumps(result, indent=2))
        return 0
    print(f"vault: {vault}")
    print(f"notes: {result['total_notes']}")
    for key, title in [("per_zone", "zones"), ("per_status", "status"), ("per_owner", "owner")]:
        print(f"{title}:")
        for name, count in sorted(result[key].items()):
            print(f"  {name}: {count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
