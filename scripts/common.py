"""Shared helpers for second-brain scripts. stdlib-only, Python 3.9+."""
import json
import re
from pathlib import Path

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WIKILINK_RE = re.compile(r"\[\[([^\]\[]+)\]\]")


def find_root(start):
    """Walk up until a dir containing rules/zones.json is found (repo root)."""
    cur = Path(start).resolve()
    for cand in [cur, *cur.parents]:
        if (cand / "rules" / "zones.json").is_file():
            return cand
    raise RuntimeError("repo root not found (no rules/zones.json above " + str(cur) + ")")


def parse_frontmatter(text):
    """Minimal YAML-less frontmatter parser.

    Supports top-level `key: value` and simple `key: [a, b]` / `- item` lists.
    Returns (dict, rest_of_text).
    """
    lines = text.splitlines()
    fm = {}
    if not lines or lines[0].strip() != "---":
        return fm, text
    i = 1
    current_key = None
    while i < len(lines) and lines[i].strip() != "---":
        line = lines[i]
        stripped = line.strip()
        if stripped.startswith("- ") and current_key:
            fm.setdefault(current_key, []).append(stripped[2:].strip())
        elif ":" in line:
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            current_key = key
            if value.startswith("[") and value.endswith("]"):
                items = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
                fm[key] = items
            elif value == "":
                fm[key] = None
            else:
                fm[key] = value.strip("'\"")
        i += 1
    body = "\n".join(lines[i + 1:])
    return fm, body


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def iter_markdown(vault):
    for path in sorted(Path(vault).rglob("*.md")):
        yield path
