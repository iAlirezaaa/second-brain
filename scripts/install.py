#!/usr/bin/env python
"""Install the second brain into a home folder.

Usage: python scripts/install.py [--target ~/brain]

A brain has one shape wherever it lives: the sixteen zones `system.json` declares, the same
scripts, the same doors, the same eight-plane map. This lays that shape down -- zones first,
then the machine plane (`15_SYSTEM/scripts`, `backend`, schemas, integrations), then the
human documents and the agent doors -- so a fresh home can answer its own gates instead of
inheriting the source repo's map. Nothing needs an app: an installed brain is markdown plus
Python standard library.

The upstream memory stays upstream: the lesson ledger starts empty and the eight planes are
proved by the installed `tests/test_installed_home.py`, not by the source repo's tests.
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common
import memory as memory_mod
from sync_hosts import HOSTS, render

DOCS = ("README.md", "ROADMAP.md", "HANDOFF.md", "CHANGELOG.md", "AGENTS.md", ".gitignore")
DOC_DIRS = ("00_START_HERE",)
# the executable plane: gates, registry door, backend readers
CODE_DIRS = ("scripts", "rules", "skills")
SYSTEM = ("scripts", "schemas", "memory", "integrations", "migrations", "templates")
STARTER = ("index.md", "_templates")
IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", "lessons.jsonl")
PROOF = "tests/test_installed_home.py"


def copy_into(src, dst, label, log):
    if not src.exists():
        log.append("skipped %s (not in the repo)" % label)
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(str(src), str(dst), dirs_exist_ok=True, ignore=IGNORED)
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


def load_config(repo):
    return json.loads((repo / "15_SYSTEM" / "config" / "system.json").read_text(encoding="utf-8"))


def lay_zones(target, cfg, log):
    """The same sixteen zones as the source, empty ones kept by `.gitkeep`."""
    zones = cfg.get("zones") or []
    for zone in zones:
        path = target / zone["dir"]
        path.mkdir(parents=True, exist_ok=True)
        if not any(path.iterdir()):
            (path / ".gitkeep").write_text("", encoding="utf-8")
    log.append("%d zone(s) laid" % len(zones))


def lay_plane_stores(target, cfg):
    """Every tracked store the home's map will claim must be openable in the home."""
    laid = 0
    for spec in (cfg.get("memory_planes") or {}).values():
        for rel in spec.get("tracked_store") or []:
            path = target / rel
            if path.suffix:
                path.parent.mkdir(parents=True, exist_ok=True)
                if not path.exists():
                    path.write_text("", encoding="utf-8")
                    laid += 1
            else:
                path.mkdir(parents=True, exist_ok=True)
                if not any(path.iterdir()):
                    (path / ".gitkeep").write_text("", encoding="utf-8")
                    laid += 1
    return laid


def write_home_config(repo, target, log):
    """The map the home can prove: its own stores and readers, one installed test for all.

    The source document names the source repo's tests. A home has none of them, so copying
    that map would be a claim it cannot keep; the installed proof is the file that ships here.
    """
    cfg = load_config(repo)
    cfg["home"] = True
    planes = cfg.get("memory_planes") or {}
    for spec in planes.values():
        spec["test"] = PROOF
    dst = target / "15_SYSTEM" / "config" / "system.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    log.append("home config: %d kinds, %d zones, %d planes proved by %s"
               % (len(cfg.get("kinds") or []), len(cfg.get("zones") or []), len(planes), PROOF))


def init_machine_plane(repo, target, log):
    """A brain with no shelf and no memory cannot learn from its own mistakes.

    The upstream lessons stay upstream: they are evidence about that repo, and a fresh
    brain has not earned them. So the ledger starts empty and legal -- `NO_ENTRY` is the
    honest first answer -- and the first lesson gets written when this brain makes its own.
    """
    copy_into(repo / "14_CANDIDATES" / "README.md", target / "14_CANDIDATES" / "README.md",
              "candidate shelf contract", log)
    (target / "14_CANDIDATES" / "loop").mkdir(parents=True, exist_ok=True)
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
    cfg = load_config(repo)
    target.mkdir(parents=True, exist_ok=True)
    for name in STARTER:
        copy_into(repo / "vault-template" / name, target / name, "starter %s" % name, log)
    for name in CODE_DIRS:
        copy_into(repo / name, target / name, name, log)
    for name in SYSTEM:
        copy_into(repo / "15_SYSTEM" / name, target / "15_SYSTEM" / name,
                  "15_SYSTEM/%s" % name, log)
    copy_into(repo / "15_SYSTEM" / "README.md", target / "15_SYSTEM" / "README.md",
              "15_SYSTEM README", log)
    copy_into(repo / "02_WIKI" / "reference_maps",
              target / "02_WIKI" / "reference_maps", "eight-plane map", log)
    for name in DOCS:
        copy_into(repo / name, target / name, name, log)
    for name in DOC_DIRS:
        copy_into(repo / name, target / name, name, log)
    for harness in (".claude", ".opencode"):
        copy_into(repo / "skills", target / harness / "skills", "%s skills" % harness, log)
    copy_into(repo / PROOF, target / PROOF, "installed-home proof", log)
    zones = len(cfg.get("zones") or [])
    lay_zones(target, cfg, log)
    stores = lay_plane_stores(target, cfg)
    doors = write_doors(repo, target)
    index = init_machine_plane(repo, target, log)
    write_home_config(repo, target, log)
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
    print("layout: %d zone(s), %d plane store(s) laid, same shape as the source repo" % (zones, stores))
    print("agent doors written: %s" % ", ".join(doors))
    print("documents re-measured for this home: %s" % measure_line[-1])
    print("empty memory ledger rendered to %s" % index.relative_to(target).as_posix())
    print("next (no app required — Python 3.9+ and the scripts are the whole system):")
    print("  cd %s && python scripts/health.py --vault ." % target)
    print("  python -m unittest discover -s tests")
    print("  python 15_SYSTEM/scripts/hades.py doctor")
    print("  python scripts/memory.py --recall \"first session\"")
    print("  open AGENTS.md and follow it; any editor you like is an optional lens "
          "on the same markdown, never a dependency")
    return 0


if __name__ == "__main__":
    sys.exit(main())
