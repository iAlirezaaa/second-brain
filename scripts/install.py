#!/usr/bin/env python
"""Install the second brain into a home folder.

Usage: python scripts/install.py [--target ~/brain]

Copies vault-template/, skills/ and scripts/ to the target and wires the agent
folders (.claude/skills, .opencode/skills) so every harness sees the same tree.
"""
import argparse
import shutil
import sys
from pathlib import Path

SYS = argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="~/brain")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    repo = Path(args.repo)
    target = Path(args.target).expanduser()
    if target.exists() and any(target.iterdir()):
        parser.error(f"target {target} is not empty — pick a fresh folder")
    shutil.copytree(repo / "vault-template", target)
    shutil.copytree(repo / "rules", target / "rules")
    (target / "scripts").mkdir(exist_ok=True)
    shutil.copytree(repo / "scripts", target / "scripts", dirs_exist_ok=True)
    for harness in [".claude", ".opencode"]:
        (target / harness / "skills").mkdir(parents=True, exist_ok=True)
        shutil.copytree(repo / "skills", target / harness / "skills", dirs_exist_ok=True)
    print(f"installed second brain at {target}")
    print(f"next: open {target} in Obsidian as a vault, and point your agent at {target}/AGENTS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
