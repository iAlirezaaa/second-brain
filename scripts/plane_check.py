#!/usr/bin/env python
"""The eight memory planes must each have a store the clone can open.

Charter section 5 names eight planes: project, repository, agent, task, error, decision,
knowledge, conversation. `15_SYSTEM/config/system.json` declares, per plane, which
tracked paths carry it, which disposable paths may be absent by design, and which reader
script, test and mapping document prove it. This gate refuses a mapping that has drifted:
a plane dropped from the config, a tracked store a fresh clone cannot open, a reader, a
test or a map that no longer exists.

Disposable stores (12_RUNTIME, .brain-data, .kb) are reported, never required --
a fresh clone is supposed to lack them (test_phase19_evidence_survives_a_clone.py).

Usage: python scripts/plane_check.py [--vault path]
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# The charter's names, typed here on purpose: a config that forgets a plane must fail,
# so the list cannot be derived from the thing being judged.
PLANES = ("project", "repository", "agent", "task", "error", "decision", "knowledge",
          "conversation")


def load(root):
    path = Path(root) / "15_SYSTEM" / "config" / "system.json"
    return json.loads(path.read_text(encoding="utf-8"))


def judge(root):
    """(problems, summary) -- problems are strings a human can act on."""
    root = Path(root).resolve()
    problems = []
    try:
        cfg = load(root)
    except (OSError, ValueError) as exc:
        return ["cannot read 15_SYSTEM/config/system.json: %s" % exc], {}
    planes = cfg.get("memory_planes")
    if not isinstance(planes, dict):
        return ["system.json has no memory_planes mapping"], {}
    missing = [name for name in PLANES if name not in planes]
    extra = sorted(name for name in planes if name not in PLANES)
    if missing:
        problems.append("planes named by the charter but not mapped: %s" % ", ".join(missing))
    if extra:
        problems.append("mapped names the charter does not name: %s" % ", ".join(extra))
    summary = {"planes": 0, "tracked": 0, "by_design": 0}
    for name in PLANES:
        spec = planes.get(name)
        if not isinstance(spec, dict):
            continue
        summary["planes"] += 1
        tracked = spec.get("tracked_store") or []
        if not tracked:
            problems.append("%s: no tracked store -- a plane with nothing the clone can open"
                            % name)
        for rel in tracked:
            target = (root / rel)
            if not target.exists():
                problems.append("%s: tracked store missing: %s" % (name, rel))
            elif target.is_dir() and not any(target.iterdir()):
                problems.append("%s: tracked store is an empty folder with no .gitkeep: %s"
                                % (name, rel))
            else:
                summary["tracked"] += 1
        for rel in spec.get("disposable_store") or []:
            summary["by_design"] += 0 if (root / rel).exists() else 1
        reader = spec.get("reader_script") or spec.get("reader_doc")
        if not reader:
            problems.append("%s: no reader declared (reader_script or reader_doc)" % name)
        elif not (root / reader).is_file():
            problems.append("%s: reader does not exist: %s" % (name, reader))
        for field in ("test", "map"):
            rel = spec.get(field)
            if not rel:
                problems.append("%s: no %s declared" % (name, field))
            elif not (root / rel).is_file():
                problems.append("%s: %s does not exist: %s" % (name, field, rel))
    return problems, summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--vault", default=None)
    args = parser.parse_args()
    root = Path(args.vault) if args.vault else find_root(Path(__file__))
    problems, summary = judge(root)
    if problems:
        print("FAILED — the eight memory planes are not fully mapped")
        for problem in problems:
            print("  %s" % problem)
        return 1
    print("OK — %d memory planes mapped: %d tracked store(s) present, %d disposable store(s) "
          "absent by design" % (summary["planes"], summary["tracked"], summary["by_design"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
