#!/usr/bin/env python
"""Install the second brain into a home folder.

Usage: python scripts/install.py [--target ~/brain]

Copies vault-template/, rules/, scripts/, skills/ and the documents to the target, wires
the skill folders the harnesses read, and lays down the same agent doors the repo ships —
so Cursor, Copilot, Gemini, Windsurf and Claude all land on one law. Nothing here needs
an app: the installed brain is markdown plus Python standard library.
"""
import argparse
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
import memory as memory_mod
from sync_hosts import HOSTS, render

DOCS = ("README.md", "ROADMAP.md", "HANDOFF.md", "CHANGELOG.md")
DOC_DIRS = ("00_START_HERE",)


def copy_into(src, dst, label, log):
    if not src.exists():
        log.append("skipped %s (not in the repo)" % label)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True)
    else:
        shutil.copy2(str(src), str(dst))


def write_doors(repo, target):
    """Reuse the repo's validated bytes; render them here if the repo has none yet."""
    laid = []
    for _key, name, rel, mdc in HOSTS:
        source = repo / rel
        text = source.read_text(encoding="utf-8") if source.is_file() else render(name, mdc)
        door = target / rel
        door.parent.mkdir(parents=True, exist_ok=True)
        door.write_text(text, encoding="utf-8")
        laid.append(rel)
    return laid


def init_machine_plane(repo, target, log):
    """A brain with no shelf and no memory cannot learn from its own mistakes.

    The upstream lessons stay upstream: they are evidence about that repo, and a fresh
    brain has not earned them. So the ledger starts empty and legal -- `NO_ENTRY` is the
    honest first answer -- and the first lesson gets written when this brain makes its own.
    """
    copy_into(repo / "14_CANDIDATES" / "README.md", target / "14_CANDIDATES" / "README.md",
              "candidate shelf contract", log)
    (target / "14_CANDIDATES" / "loop").mkdir(parents=True, exist_ok=True)
    copy_into(repo / "15_SYSTEM" / "config" / "system.json",
              target / "15_SYSTEM" / "config" / "system.json", "zone config", log)
    memory_dir = target / "15_SYSTEM" / "memory"
    copy_into(repo / "15_SYSTEM" / "memory" / "README.md", memory_dir / "README.md",
              "memory README", log)
    ledger = memory_dir / "lessons.jsonl"
    if not ledger.exists():
        ledger.write_text("", encoding="utf-8")
    return memory_mod.render(target, memory_mod.read_lessons(target)[0])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default="~/brain")
    parser.add_argument("--repo", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    repo = Path(args.repo)
    target = Path(args.target).expanduser()
    if target.exists() and any(target.iterdir()):
        parser.error(f"target {target} is not empty — pick a fresh folder")
    log = []
    shutil.copytree(repo / "vault-template", target)
    for name in ("rules", "scripts", "skills"):
        copy_into(repo / name, target / name, name, log)
    for name in DOCS:
        copy_into(repo / name, target / name, name, log)
    for name in DOC_DIRS:
        copy_into(repo / name, target / name, name, log)
    for harness in (".claude", ".opencode"):
        copy_into(repo / "skills", target / harness / "skills", "%s skills" % harness, log)
    doors = write_doors(repo, target)
    index = init_machine_plane(repo, target, log)
    # The copied documents carried the source repo's numbers. A brain that reports somebody
    # else's measurements is lying on principle, so the block is re-measured here, from the
    # installed folder, before the first session reads it.
    remeasure = common.run_utf8(
        [sys.executable, str(target / "scripts" / "doc_report.py"), "--root", str(target),
         "--write"], cwd=str(target))
    measure_line = (remeasure.stdout or remeasure.stderr).strip().splitlines()
    print(f"installed second brain at {target}")
    for line in log:
        print("note: %s" % line)
    print("agent doors written: %s" % ", ".join(doors))
    print("documents re-measured for this home: %s" % measure_line[-1])
    print("empty memory ledger rendered to %s" % index.relative_to(target).as_posix())
    print("next (no app required — Python 3.9+ and the scripts are the whole system):")
    print("  cd %s && python scripts/health.py --vault ." % target)
    print("  python scripts/memory.py --recall \"first session\"")
    print("  open AGENTS.md and follow it; any editor you like is an optional lens "
          "on the same markdown, never a dependency")
    return 0


if __name__ == "__main__":
    sys.exit(main())
