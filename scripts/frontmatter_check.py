#!/usr/bin/env python
"""Frontmatter validator (AGENTS.md rule 2).

Usage: python scripts/frontmatter_check.py [--vault path]
Validates required fields per rules/schema.json. Exits 1 on violations.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DATE_RE, find_root, iter_markdown, load_json, parse_frontmatter


def validate_file(path, schema):
    problems = []
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, _ = parse_frontmatter(text)
    if not fm:
        return ["missing frontmatter block"]
    if "title" not in path.name and path.name == "note-resource.md":
        pass  # template files follow same rules
    for field, spec in schema["required_fields"].items():
        if field not in fm or fm[field] in (None, ""):
            problems.append(f"missing field: {field}")
            continue
        value = fm[field]
        kind = spec.get("type")
        if kind == "date" and not DATE_RE.match(str(value)):
            problems.append(f"bad date format in {field}: {value!r} (want YYYY-MM-DD)")
        elif "enum" in spec and value not in spec["enum"]:
            problems.append(f"invalid {field}: {value!r} (allowed: {spec['enum']})")
        elif kind == "string_list" and not isinstance(value, list):
            problems.append(f"{field} must be a list, got {value!r}")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None)
    args = parser.parse_args()
    root = find_root(Path(__file__))
    vault = Path(args.vault) if args.vault else root / "vault-template"
    schema = load_json(root / "rules" / "schema.json")
    failures = 0
    for path in iter_markdown(vault):
        if path.name in ("AGENTS.md", "CLAUDE.md", "index.md"):
            continue  # contract files are prose, not notes
        problems = validate_file(path, schema)
        if problems:
            failures += 1
            for problem in problems:
                print(f"INVALID  {path}: {problem}")
    if failures:
        print(f"\n{failures} file(s) with frontmatter problems.")
        return 1
    print(f"OK — frontmatter valid in {vault}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
