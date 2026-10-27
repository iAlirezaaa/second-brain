#!/usr/bin/env python
"""Zero-broken-links enforcer (AGENTS.md rule 1).

Usage: python scripts/link_check.py [--vault path]
Exit 0 = clean, exit 1 = broken links found.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import WIKILINK_RE, find_root, iter_markdown, iter_notes


# prose contract files are not notes; their example links are documentation, not data
# the name list lives in common.is_prose so both vault gates agree on what a note is


def resolve_target(target, files_by_stem, files_by_rel):
    """A link resolves if it matches a file stem (case-insensitive) or a path."""
    target = target.strip()
    if not target:
        return False
    if target.lower() in files_by_stem:
        return True
    normalized = target.replace("\\", "/").lower()
    if not normalized.endswith(".md"):
        normalized += ".md"
    return normalized in files_by_rel


def check_vault(vault):
    # every markdown file is a possible link target, prose included; only notes are judged
    targets = list(iter_markdown(vault))
    files_by_stem = {p.stem.lower(): p for p in targets}
    files_by_rel = {p.relative_to(vault).as_posix().lower(): p for p in targets}
    broken = []
    for path in iter_notes(vault):
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in WIKILINK_RE.finditer(text):
            target = match.group(1).split("|")[0].strip()
            if not resolve_target(target, files_by_stem, files_by_rel):
                broken.append((path, target))
    return broken


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None, help="vault dir (default: repo's vault-template)")
    args = parser.parse_args()
    root = find_root(Path(__file__))
    vault = Path(args.vault) if args.vault else root / "vault-template"
    broken = check_vault(vault)
    if broken:
        for path, target in broken:
            print(f"BROKEN  {path}: [[{target}]]")
        print(f"\n{len(broken)} broken link(s) — fix before anything else ships.")
        return 1
    print(f"OK — 0 broken links in {vault}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
