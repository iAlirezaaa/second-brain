"""Shared helpers for second-brain scripts. stdlib-only, Python 3.9+."""
import hashlib
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
            existing = fm.get(current_key)
            if existing is None:
                existing = []                     # a bare "key:" followed by block items
            elif not isinstance(existing, list):
                existing = [str(existing)]        # "key: value" then items: keep both
            existing.append(stripped[2:].strip())
            fm[current_key] = existing
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


# Volatile names that must never enter a content fingerprint: caches, VCS internals,
# and the probe shelf itself (a probe writes there, so including it would make every
# probe report "the probe mutated the vault").
FINGERPRINT_SKIP_DIRS = {"__pycache__", ".git", ".kb", ".obsidian", "node_modules"}
FINGERPRINT_SKIP_PATHS = ("14_CANDIDATES/loop/probes",)


def tree_inventory(root, extra_skip_paths=()):
    """{relative posix path: sha1(bytes)} for every file under root that counts.

    The inventory is what makes a mutation *nameable*: a hash alone says the tree
    changed, not what changed, and "something moved" is not an actionable refusal.
    Cheap on a vault, not on a disk -- pass a bounded root.
    """
    root = Path(root)
    skip_paths = list(FINGERPRINT_SKIP_PATHS) + list(extra_skip_paths)
    inventory = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in FINGERPRINT_SKIP_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        rel = path.relative_to(root).as_posix()
        if any(rel.startswith(p) for p in skip_paths):
            continue
        inventory[rel] = hashlib.sha1(path.read_bytes()).hexdigest()
    return inventory


def fingerprint_of_inventory(inventory):
    """The same digest tree_fingerprint returns, from an inventory you already hold."""
    digest = hashlib.sha1()
    for rel in sorted(inventory):
        digest.update(rel.encode("utf-8"))
        digest.update(b"\0")
        digest.update(inventory[rel].encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()[:16]


def tree_fingerprint(root, extra_skip_paths=()):
    """SHA-1 over the sorted inventory, first 16 hex: content-addressed state.

    Two runs that saw the same bytes agree; any edit anywhere breaks the match. That
    is what makes an old measurement unusable as evidence for the current tree --
    freshness becomes provable, not assumed.
    """
    return fingerprint_of_inventory(tree_inventory(root, extra_skip_paths))


def inventory_diff(before, after):
    """[(path, added|removed|changed)] — the honest name for "the tree moved"."""
    moves = []
    for rel in sorted(set(before) | set(after)):
        if rel not in after:
            moves.append((rel, "removed"))
        elif rel not in before:
            moves.append((rel, "added"))
        elif before[rel] != after[rel]:
            moves.append((rel, "changed"))
    return moves
