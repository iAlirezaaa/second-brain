#!/usr/bin/env python
"""Known-good base — the mechanism behind `keep_base`, and the way back when a change hurts.

harness2's rule, kept in stdlib form: when a change measures worse, fall back to the last
state that was *measured good*, and record that you fell back. The phrase "last known good"
only means something if two things exist on disk: the bytes, and a fingerprint that proves
those bytes are the state the record describes. A memory of "it worked yesterday" is a rumour.

Three promises, each with a test in tests/test_phase20_known_good_base.py:

  * a base is measured, not assumed -- `--save` runs the health gates first and refuses a red
    house, so nothing that could not pass becomes the thing everybody falls back to;
  * the base is the brain, not its paperwork -- the snapshot covers the same inventory as
    `common.state_fingerprint` (so the quarantine shelf, the runtime plane and the backups
    folder itself are outside it). Recovery reverts content; it never rewrites the ledger,
    and it never deletes a file you added afterwards, it names those and leaves them;
  * a record is not an artifact -- if the journal names a snapshot whose bytes are gone,
    `--recover` refuses out loud rather than reporting a successful fall back.

Usage:
  python scripts/base.py --save [--note why]        # measure the house, then record its base
  python scripts/base.py --status                   # base vs current, by fingerprint
  python scripts/base.py --list                     # every base recorded here
  python scripts/base.py --recover [--stamp X] [--note why] [--candidate 14_CANDIDATES/loop/cand-x.md]

Exit 0 = the tree is the recorded base (or nothing had to be done), 1 = refused or unverified.
"""
import argparse
import datetime
import json
import re
import shutil
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).parent))
from common import (PAPERWORK_SKIP_PATHS, find_root, run_utf8, state_fingerprint,
                    tree_inventory)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

STAMP_RE = re.compile(r"^\d{8}T\d{6}Z$")
SNAPSHOT_ROOT = "15_SYSTEM/backups/known-good"
BASES_JOURNAL = "14_CANDIDATES/loop/bases.jsonl"
RECOVERY_JOURNAL = "14_CANDIDATES/loop/recovery.jsonl"
KEEP = 5          # bases on disk; the journal keeps every line, the bytes get rotated


def now():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def stamp():
    return datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def journal_rows(root, name):
    path = root / name
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.strip():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                rows.append({"_broken": line[:80]})
    return rows


def append_row(root, name, row):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def gates(root):
    """Run the house's own health command inside this root -- the only honest pre-flight."""
    script = root / "scripts" / "health.py"
    if not script.is_file():
        return 1, "scripts/health.py is not here, so nothing can be called measured"
    result = run_utf8([sys.executable, str(script)], cwd=str(root))
    return result.returncode, (result.stdout + result.stderr).strip()


def inventory(root):
    """The base's scope: exactly what `state_fingerprint` counts, nothing else."""
    return tree_inventory(root, PAPERWORK_SKIP_PATHS)


def safe_rel(rel):
    """A manifest is data. Data that names a path outside the repo is refused, not obeyed."""
    text = str(rel).replace("\\", "/")
    if text.startswith("/") or text.startswith("~/"):
        return None
    pure = PurePosixPath(text)
    if pure.is_absolute() or ".." in pure.parts or not text or text != str(pure):
        return None
    return text


def save(root, note):
    code, output = gates(root)
    if code != 0:
        print("REFUSED  the house is not green, so this state cannot become a known good base")
        for line in output.splitlines()[-6:]:
            print("  | %s" % line)
        print("REFUSED  fix the gate, then save: a base you cannot trust is a way to lose work twice")
        return 1
    digest = state_fingerprint(root)
    rows = [r for r in journal_rows(root, BASES_JOURNAL) if "fingerprint" in r]
    if rows and rows[-1].get("fingerprint") == digest:
        print("ALREADY  state %s is the recorded base (%s) -- nothing to re-measure"
              % (digest, rows[-1].get("stamp")))
        return 0
    files = inventory(root)
    where = "%s/%s" % (SNAPSHOT_ROOT, stamp())
    snapshot = root / where
    snapshot.mkdir(parents=True, exist_ok=False)
    total = 0
    for rel, _digest in sorted(files.items()):
        source = root / rel
        destination = snapshot / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(destination))
        total += source.stat().st_size
    manifest = {"stamp": snapshot.name, "fingerprint": digest, "files": files,
                "created": now(), "note": note, "gates": "green"}
    (snapshot / "manifest.json").write_text(json.dumps(manifest, indent=1, sort_keys=True),
                                            encoding="utf-8")
    append_row(root, BASES_JOURNAL, {"date": now(), "event": "base", "stamp": snapshot.name,
                                     "fingerprint": digest, "files": len(files), "bytes": total,
                                     "gates": "green", "note": note, "snapshot": where})
    pruned = prune(root)
    print("BASE %s | state %s | %d file(s) | %.1f KB | gates green%s"
          % (snapshot.name, digest, len(files), total / 1024.0,
             (" | %d older base(s) rotated out" % pruned) if pruned else ""))
    print("     bytes: %s | record: %s" % (where, BASES_JOURNAL))
    return 0


def prune(root):
    """Keep the newest KEEP snapshots; the journal keeps the history either way."""
    shelf = root / SNAPSHOT_ROOT
    if not shelf.is_dir():
        return 0
    stamps = sorted(p.name for p in shelf.iterdir() if p.is_dir() and STAMP_RE.match(p.name))
    removed = 0
    for name in stamps[:-KEEP] if len(stamps) > KEEP else []:
        shutil.rmtree(str(shelf / name), ignore_errors=True)
        removed += 1
    return removed


def load_base(root, row):
    """The bytes behind a journal line, or the refusal that says they are not here."""
    where = row.get("snapshot") or "%s/%s" % (SNAPSHOT_ROOT, row.get("stamp"))
    if not safe_rel(where):
        return None, "", "the base record names an unsafe path: %r" % where
    manifest_path = root / where / "manifest.json"
    if not manifest_path.is_file():
        return None, where, ("the journal records base %s but its snapshot bytes are not on this "
                             "machine (%s is gitignored state, so a record is not an artifact)"
                             % (row.get("stamp"), where))
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad = [rel for rel in manifest.get("files", {}) if safe_rel(rel) is None]
    if bad:
        return None, where, ("manifest for base %s names %d path(s) outside the repo -- refused: %s"
                             % (row.get("stamp"), len(bad), bad[0]))
    return manifest, where, ""


def recover(root, wanted, note, candidate):
    rows = [r for r in journal_rows(root, BASES_JOURNAL) if "fingerprint" in r]
    if not rows:
        print("REFUSED  no base has ever been recorded here -- run python scripts/base.py --save")
        print("REFUSED  while every gate is green: falling back to a state nobody measured is "
              "how a bad change becomes permanent")
        return 1
    row = rows[-1]
    if wanted:
        matches = [r for r in rows if r.get("stamp") == wanted]
        if not matches:
            print("REFUSED  %s is not a stamp in %s" % (wanted, BASES_JOURNAL))
            return 1
        row = matches[-1]
    if candidate:
        path = Path(candidate)
        if not (path if path.is_absolute() else root / path).is_file():
            print("REFUSED  %s is not a row on the shelf -- a fall back needs to say what it is "
                  "about" % candidate)
            return 1
    manifest, where, refusal = load_base(root, row)
    if refusal:
        print("REFUSED  %s" % refusal)
        return 1
    before = state_fingerprint(root)
    base_fp = manifest["fingerprint"]
    if before == base_fp:
        print("NOTHING  the tree already is base %s (state %s) -- no fall back to record"
              % (row.get("stamp"), base_fp))
        return 0
    current = inventory(root)
    added_since = sorted(set(current) - set(manifest["files"]))
    restored = 0
    missing_bytes = []
    for rel, _digest in sorted(manifest["files"].items()):
        source = root / where / rel
        if not source.is_file():
            missing_bytes.append(rel)
            continue
        destination = root / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(str(source), str(destination))
        restored += 1
    after = state_fingerprint(root, added_since)
    verified = after == base_fp and not missing_bytes
    append_row(root, RECOVERY_JOURNAL, {
        "date": now(), "event": "recovery", "stamp": row.get("stamp"),
        "from_fingerprint": before, "to_fingerprint": base_fp, "restored": restored,
        "added_since": added_since, "missing_bytes": missing_bytes,
        "verified": verified, "fell_back": True, "candidate": candidate or "", "note": note})
    print("RECOVERED base %s | %d file(s) restored | state %s -> %s | fell_back: true"
          % (row.get("stamp"), restored, before, base_fp))
    if added_since:
        print("  left in place, %d file(s) added since the base (named, not deleted):"
              % len(added_since))
        for rel in added_since[:8]:
            print("    + %s" % rel)
        if len(added_since) > 8:
            print("    ... %d more" % (len(added_since) - 8))
    if missing_bytes:
        print("  MISSING %d file(s) the manifest lists but the snapshot does not hold:"
              % len(missing_bytes))
        for rel in missing_bytes[:8]:
            print("    ! %s" % rel)
    print("  %s" % ("identity matches the base, excluding the additions above"
                    if verified else "IDENTITY DOES NOT MATCH the base -- this recovery is "
                                    "recorded as unverified, do not call the tree good"))
    print("  the shelf kept its rows and its ledger: recovery reverts the brain, never the lesson")
    print("  next: python scripts/health.py, then re-run the probe that said hurt")
    return 0 if verified else 1


def status(root):
    rows = [r for r in journal_rows(root, BASES_JOURNAL) if "fingerprint" in r]
    current = state_fingerprint(root)
    if not rows:
        print("NO BASE recorded here -- the state now is %s" % current)
        print("python scripts/base.py --save   (refuses unless every gate is green)")
        return 0
    row = rows[-1]
    manifest, _where, refusal = load_base(root, row)
    print("base    %s | state %s | %s file(s) | gates %s"
          % (row.get("stamp"), row.get("fingerprint"), row.get("files", 0), row.get("gates")))
    print("current              | state %s" % current)
    if refusal:
        print("SNAPSHOT MISSING  %s" % refusal)
        return 1
    changed, added, gone = state_difference(root, manifest)
    print("MATCHES" if not (changed or added or gone) else
          "DIFFERS  %d changed, %d added since base, %d recorded in base but missing here"
          % (changed, added, gone))
    return 0


def state_difference(root, manifest):
    current = inventory(root)
    changed = [rel for rel in manifest["files"] if rel in current
               and current[rel] != manifest["files"][rel]]
    added = [rel for rel in current if rel not in manifest["files"]]
    gone = [rel for rel in manifest["files"] if rel not in current]
    return len(changed), len(added), len(gone)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--save", action="store_true", help="record the current green state")
    parser.add_argument("--recover", action="store_true", help="fall back to a recorded base")
    parser.add_argument("--status", action="store_true", help="base vs current, by fingerprint")
    parser.add_argument("--list", action="store_true", dest="as_list")
    parser.add_argument("--stamp", default=None, help="which base to recover (default: newest)")
    parser.add_argument("--candidate", default=None,
                        help="shelf row this fall back is about, recorded with it")
    parser.add_argument("--note", default="", help="why, in one line")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))

    chosen = [args.save, args.recover, args.status, args.as_list].count(True)
    if chosen != 1:
        print("REFUSED  pick exactly one act: --save | --recover | --status | --list")
        print("         a base is recorded, fallen back to, compared or listed -- never all four")
        return 1
    if args.save:
        return save(root, args.note)
    if args.recover:
        return recover(root, args.stamp, args.note, args.candidate)
    if args.status:
        return status(root)
    rows = journal_rows(root, BASES_JOURNAL)
    if not rows:
        print("NO BASE recorded here.")
        return 0
    for row in rows:
        print("%s | state %s | %s file(s) | gates %s | %s"
              % (row.get("stamp"), row.get("fingerprint"), row.get("files"),
                 row.get("gates"), row.get("note") or "-"))
    print("%d base(s); %d retained on disk (newest %d), the journal keeps them all"
          % (len(rows), len([p for p in (root / SNAPSHOT_ROOT).glob("*")
                             if p.is_dir()]) if (root / SNAPSHOT_ROOT).is_dir() else 0, KEEP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
