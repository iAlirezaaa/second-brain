"""Shared helpers for second-brain scripts. stdlib-only, Python 3.9+."""
import hashlib
import json
import re
import subprocess
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


def run_utf8(argv, cwd=None):
    """Run a child and read it as UTF-8 whatever the console code page is.

    text=True alone decodes with the locale codec, and these gates print em dashes and
    Persian -- on a cp1252 Windows console that raises inside the *parent*, and a crashed
    parent looks exactly like a gate that produced no output. Encoding is stated, not
    inherited.
    """
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def iter_markdown(vault):
    for path in sorted(Path(vault).rglob("*.md")):
        yield path


# Prose is not a note. Contract files, generated indexes, agent-host doors and doc folders
# quote example links ([[target]]) and carry a frontmatter shape of their own; judging them
# by the note schema produces a false alarm, and a gate that cries wolf gets switched off.
# Each of these has its own judge instead: memory.py --check for MEMORY.md,
# candidate_check.py for the shelf, sync_hosts.py --check/--lint for the doors.
# The list only ever covered files outside the scanned vault; an installed brain puts them
# inside the vault root, so the exemption is by name and by folder, not by position.
PROSE_NAMES = {"AGENTS.md", "CLAUDE.md", "GEMINI.md", "copilot-instructions.md",
               "agents.mdc", "README.md", "MEMORY.md", "ROADMAP.md", "HANDOFF.md",
               "CHANGELOG.md", "SECURITY.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md",
               "AUTHORS.md", "SKILL.md", "index.md"}
PROSE_DIRS = {"00_START_HERE", "skills", "rules", "docs", "scripts", "14_CANDIDATES",
              "15_SYSTEM", ".cursor", ".windsurf", ".github", ".claude", ".opencode"}


def is_prose(path):
    """True when this markdown is documentation rather than knowledge."""
    path = Path(path)
    if any(part in PROSE_DIRS for part in path.parts[:-1]):
        return True
    return path.name in PROSE_NAMES


def iter_notes(vault):
    """The markdown under a folder that the note schema and the link fence own."""
    vault = Path(vault)
    for path in iter_markdown(vault):
        if not is_prose(path.relative_to(vault)):
            yield path


# Volatile names that must never enter a content fingerprint: caches, VCS internals,
# and the probe shelf itself (a probe writes there, so including it would make every
# probe report "the probe mutated the vault").
FINGERPRINT_SKIP_DIRS = {"__pycache__", ".git", ".kb", ".obsidian", "node_modules"}
FINGERPRINT_SKIP_PATHS = ("14_CANDIDATES/loop/probes",)
# Paperwork is not the state of the brain. The quarantine shelf, the disposable runtime
# plane and the proposal sink all grow while nothing being measured moves; if they sat
# inside the identity, every gate would demand a re-probe after ordinary filing and the
# discipline would get switched off. The candidate's own digest is checked separately, so
# excluding the shelf cannot be used to rewrite a claim after it was measured.
PAPERWORK_SKIP_PATHS = ("14_CANDIDATES/", "12_RUNTIME/",
                        "vault-template/90_Agent_Output/proposals/")

# The documented git boundary, restated for one question: could a reader who cloned this
# repository open this path? A laptop-only file is not evidence -- it is a rumour the author
# happens to be able to check. .gitignore is the law; this mirrors the parts of it that a
# citation could land in, and tests/test_phase19 keeps the two from drifting apart.
BOUNDARY_PREFIXES = (".kb/", "12_RUNTIME/", "13_LAB/", "14_CANDIDATES/",
                     "15_SYSTEM/generated/", "15_SYSTEM/backups/", "15_SYSTEM/logs/",
                     ".secrets/", ".obsidian/", "node_modules/")
BOUNDARY_EXCEPTIONS = ("14_CANDIDATES/loop/", "14_CANDIDATES/README.md")
BOUNDARY_SUFFIXES = (".sqlite", ".sqlite3", ".db", ".pem", ".key", ".token", ".env",
                     ".safetensors", ".ckpt", ".gguf", ".onnx", ".zip", ".rar")
BOUNDARY_SEGMENTS = ("__pycache__/", "/secrets/", ".git/")
# the probe shelf is where a run writes its scratch: it is deliberately outside the
# fingerprint, so a citation there says even less about the repo than a citation of a
# local database -- a clone has nothing at that path, ever
PROBE_SHELF = "14_CANDIDATES/loop/probes"


def clone_readable(rel):
    """True when a fresh clone of this repo would contain the path `rel` names."""
    text = str(rel).replace("\\", "/")
    if text.startswith("./"):
        text = text[2:]
    text = text.lstrip("/")
    if not text:
        return False
    if text.startswith(PROBE_SHELF):
        return False
    if text.startswith(BOUNDARY_EXCEPTIONS):
        return True
    if text.startswith(BOUNDARY_PREFIXES):
        return False
    if any(segment in ("/" + text) for segment in BOUNDARY_SEGMENTS):
        return False
    return not text.endswith(BOUNDARY_SUFFIXES)


def state_fingerprint(root, extra_skip_paths=()):
    """Content identity of the brain itself: the tree minus its paperwork."""
    return tree_fingerprint(root, list(PAPERWORK_SKIP_PATHS) + list(extra_skip_paths))


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
