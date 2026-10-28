#!/usr/bin/env python
"""Frontmatter validator (AGENTS.md rule 2).

Usage: python scripts/frontmatter_check.py [--vault path]
Validates required fields per rules/schema.json. Exits 1 on violations.

One file, one contract. `apply` writes a `wiki_note` or `news` record as markdown into a human
zone, and an installed brain scans its own root, so that file sits in the note gate's path --
but it is a definition, not a note. Judging it by the note schema is not a defect in the file,
it is a gate calling a healthy thing broken; and the obvious "fix" (write a `title`, a `type`
and a note `status` next to the record's own `name`, `kind` and `status`) is worse, because then
one field has two names whose values nobody keeps in step. So the gate asks the file what it is,
using the recognizer the registry already uses (a registry-shaped `id` *and* a declared `kind`),
and holds it to the contract it claims -- read from the registry's own config and schema, so the
two cannot drift apart. That is a stricter gate, not a looser one: a record with a status its
kind does not allow, or without its identity fields, is still refused.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import DATE_RE, find_root, iter_notes, load_json, parse_frontmatter


def registry_contract(root):
    """The record contract, assembled from the registry's own files.

    None when this repo has no registry plane (or no declared branch in the schema): a brain
    installed without `15_SYSTEM` still has to judge its notes.
    """
    schema = load_json(Path(root) / "rules" / "schema.json")
    branch = schema.get("record_contract")
    if not branch:
        return None
    cfg_path = Path(root) / branch["config"]
    sch_path = Path(root) / branch["schema"]
    if not (cfg_path.is_file() and sch_path.is_file()):
        return None
    cfg, sch = load_json(cfg_path), load_json(sch_path)
    return {
        "kinds": {k["kind"] for k in cfg["kinds"]},
        "id_pattern": sch[branch["id_pattern_from"]],
        "common_required": sch[branch["required_fields_from"]],
        "by_kind": sch.get("by_kind", {}),
        "status_sets": cfg[branch["status_sets_from"]],
    }


def is_registry_record(fm, registry):
    """The same recognizer `iter_records` uses: content, not filename (phase 21's law)."""
    if not registry or not fm:
        return False
    return (fm.get("kind") in registry["kinds"]
            and bool(re.match(registry["id_pattern"], str(fm.get("id") or ""))))


def claims_a_kind(fm, registry):
    """True when the file declares a registry kind, whether or not its id is record-shaped.

    A file in that state belongs to neither contract: the registry cannot enumerate it and the
    note schema would bless a definition that is missing its identity. That is issue #13 seen
    from the other side, so it is refused rather than judged twice by two wrong contracts.
    """
    return bool(registry) and bool(fm) and fm.get("kind") in registry["kinds"]



def validate_record(fm, registry):
    """Problems with a file that claims to be a registry record, judged as one."""
    problems = []
    kind = fm.get("kind")
    for field in registry["common_required"]:
        if fm.get(field) in (None, ""):
            problems.append("record missing required field: %s" % field)
    for field in (registry["by_kind"].get(kind) or {}).get("required", []):
        if fm.get(field) in (None, ""):
            problems.append("record kind %s requires: %s" % (kind, field))
    status = fm.get("status")
    allowed = registry["status_sets"].get(kind, registry["status_sets"].get("default", []))
    if status and status not in allowed:
        problems.append("invalid status: %r for record kind %s (allowed: %s)"
                        % (status, kind, allowed))
    return problems


def validate_note(fm, schema):
    problems = []
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


def validate_file(path, schema):
    text = path.read_text(encoding="utf-8", errors="replace")
    fm, _ = parse_frontmatter(text)
    if not fm:
        return ["missing frontmatter block"]
    return validate_note(fm, schema)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None)
    args = parser.parse_args()
    root = find_root(Path(__file__))
    vault = Path(args.vault) if args.vault else root / "vault-template"
    schema = load_json(root / "rules" / "schema.json")
    registry = registry_contract(root)
    failures = 0
    records = 0
    for path in iter_notes(vault):
        text = path.read_text(encoding="utf-8", errors="replace")
        fm, _ = parse_frontmatter(text)
        if is_registry_record(fm, registry):
            problems = validate_record(fm, registry)
            records += 1
        elif claims_a_kind(fm, registry):
            problems = ["declares registry kind %r with an id the registry cannot enumerate (want %s)"
                        % (fm.get("kind"), registry["id_pattern"])]
        else:
            problems = validate_note(fm, schema) if fm else ["missing frontmatter block"]
        if problems:
            failures += 1
            for problem in problems:
                print(f"INVALID  {path}: {problem}")
    if failures:
        print(f"\n{failures} file(s) with frontmatter problems.")
        return 1
    print(f"OK — frontmatter valid in {vault} ({records} record(s) judged by the registry contract)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
