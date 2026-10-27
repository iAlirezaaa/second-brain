#!/usr/bin/env python
"""HADES-plane CI gate — prove the published repo is honest from a pristine clone.

Why this exists: README claimed "zones present: 16/16 | errors: 0" read from the
owner's local folder. A fresh clone cannot reproduce that, because 12_RUNTIME and
13_LAB are gitignored machine state and the vault root's own .git tripped the
nested-repo rule. A number in a document is a claim; this script makes it a gate.

It builds an exact replica of what `git clone` would give (tracked files only, plus
the vault's own .git), in a temp dir, and asserts the state transitions:

  1. pristine clone  -> hades.py doctor exits 0 (documented boundary, not a defect)
  2. pristine clone  -> init_structure.py --check does NOT say OK (the seeder bites)
  3. after seeding   -> init_structure.py --check says OK and doctor stays 0
  4. after seeding   -> status accounts every declared zone (disk + boundary = declared)
  5. --battery       -> run test_hades.py: every negative gate must still fire

Nothing here touches the working vault.

Usage: python scripts/ci_hades_plane.py [--battery]
Exit 0 = the HADES plane is honest from a clone. Exit 1 = a claim in the docs is false.
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# zones the git boundary keeps out of a clone by design; 14_CANDIDATES is NOT here
# because its loop shelf is tracked by exception (see system.json tracked_exception)
BOUNDARY_ZONES = ("12_RUNTIME", "13_LAB")


def run(cwd, *args):
    result = subprocess.run([sys.executable] + [str(a) for a in args], cwd=str(cwd),
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def clone_replica(repo, dest):
    """Rebuild what `git clone` would produce: tracked files only, plus .git.

    Falls back to a plain copy (minus disposable dirs) when git is unavailable, so
    the gate still runs on a machine without git — the fallback states what it did.
    """
    listing = subprocess.run(["git", "-C", str(repo), "ls-files", "-z"],
                             capture_output=True, text=True, encoding="utf-8")
    if listing.returncode != 0:
        shutil.copytree(str(repo), str(dest), symlinks=True,
                        ignore=shutil.ignore_patterns(".git", ".kb", "__pycache__",
                                                      *BOUNDARY_ZONES))
        return "copy (git unavailable: copied tracked tree minus disposable zones)"
    names = [n for n in listing.stdout.split("\0") if n]
    for name in names:
        src = repo / name
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(target))
    git_head = repo / ".git"
    if git_head.is_dir():
        shutil.copytree(str(git_head), str(dest / ".git"), symlinks=True)
    return "%d tracked file(s) + the vault's own .git" % len(names)


def parse_zone_counts(text):
    match = re.search(r"zones on disk:\s*(\d+)/(\d+)", text)
    return (int(match.group(1)), int(match.group(2))) if match else (None, None)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--battery", action="store_true", help="also run test_hades.py")
    args = parser.parse_args()
    repo = find_root(Path(__file__))
    scratch = tempfile.TemporaryDirectory(prefix="hades-clone-")
    clone = Path(scratch.name) / "clone"
    clone.mkdir()
    failures = []

    def require(label, condition, detail):
        print("%s %s" % ("OK  " if condition else "FAIL", label))
        if not condition:
            failures.append(label)
            print("     -> %s" % detail.strip().replace("\n", " | ")[:300])

    try:
        print("HADES plane gate | replica of a fresh clone: %s" % clone_replica(repo, clone))

        code, out = run(clone, "15_SYSTEM/scripts/hades.py", "doctor")
        require("a pristine clone passes doctor (no invented zones, no self-inflicted nested-repo error)",
                code == 0 and "errors: 0" in out, out)
        require("the gitignored machine plane is reported as the boundary, not as a defect",
                "documented git boundary" in out and all(z in out for z in BOUNDARY_ZONES), out)

        code, out = run(clone, "15_SYSTEM/scripts/init_structure.py", "--check")
        require("the seeder still bites: an unseeded clone is INCOMPLETE, never OK",
                code != 0 and "INCOMPLETE" in out, out)

        code, out = run(clone, "15_SYSTEM/scripts/init_structure.py")
        require("seeding the clone succeeds", code == 0, out)

        code, out = run(clone, "15_SYSTEM/scripts/init_structure.py", "--check")
        require("after seeding, --check is OK", code == 0 and "OK" in out, out)

        code, out = run(clone, "15_SYSTEM/scripts/hades.py", "doctor")
        require("doctor stays green on the seeded vault", code == 0 and "errors: 0" in out, out)

        code, out = run(clone, "15_SYSTEM/scripts/hades.py", "status")
        on_disk, declared = parse_zone_counts(out)
        excused = len([z for z in BOUNDARY_ZONES if not (clone / z).exists()])
        accounted = (on_disk or 0) + excused
        require("status accounts every declared zone (on-disk + absent-by-boundary = declared)",
                declared is not None and accounted == declared,
                "disk=%s excused=%s declared=%s | %s" % (on_disk, excused, declared, out))

        code, out = run(clone, "15_SYSTEM/scripts/hades.py", "qc")
        require("persian hygiene is clean across the shipped prose", "clean" in out, out)

        if args.battery:
            code, out = run(clone, "15_SYSTEM/scripts/test_hades.py")
            tail = [l for l in out.splitlines() if l.startswith("checks:")]
            require("the HADES test battery is green", code == 0 and bool(tail), out)
            if tail:
                print("     %s" % tail[-1])
    finally:
        scratch.cleanup()

    if failures:
        print("\n%d HADES-plane claim(s) did not hold: %s" % (len(failures), ", ".join(failures)))
        return 1
    print("\nHADES plane is honest from a clone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
