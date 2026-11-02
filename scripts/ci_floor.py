#!/usr/bin/env python
"""Health gate: the Python floor the documents promise is the Python floor CI proves.

Measured on 2026-11-01: `ubuntu-latest` became Ubuntu 26.04, `actions/python-versions` carries
no CPython 3.9 x64 build for it, and every `ci` and `loop` run died inside `setup-python` —
24 seconds, red, five runs in a row — while every local gate stayed green and the README went
on claiming "Python 3.9+". The claim and the harness that proves it lived in different files,
and nothing compared them, which is the silent-gate failure this repo names in its own roadmap.

So the floor is checked in four places at once:

* `pyproject.toml`'s `requires-python` — the number a packager reads;
* `.github/workflows/ci.yml`'s matrix — the number CI actually installs;
* the runner image that matrix names — because a floor with no build on its runner is a claim
  that cannot be measured (this is what broke, and it breaks again the moment someone "fixes"
  the pinned image back to `ubuntu-latest`);
* the `python floor` rows in README.md and 00_START_HERE/START.md — the number a human reads.

Exit 0 = one floor everywhere; 1 = at least one of them disagrees.
"""
import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# `ubuntu-latest` is the image that stopped carrying a build for the floor; a job that tests the
# floor must name a pinned image so the runner's migration cannot silently kill the promise.
UNPINNED_UBUNTU = "ubuntu-latest"


def parse_version(text):
    parts = re.match(r"^(\d+)\.(\d+)", (text or "").strip())
    if not parts:
        return None
    return (int(parts.group(1)), int(parts.group(2)))


def requires_python_floor(root):
    text = (Path(root) / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'requires-python\s*=\s*">=\s*(\d+\.\d+)"', text)
    return match.group(1) if match else None


def workflow_matrix(root, name):
    """(versions, runs_on) declared by a workflow, read as text — no YAML dependency."""
    path = Path(root) / ".github" / "workflows" / name
    if not path.is_file():
        return None, None
    text = path.read_text(encoding="utf-8")
    versions = []
    inline = re.search(r'python-version:\s*\[([^\]]*)\]', text)
    if inline:
        versions += [v.strip().strip("'\"") for v in inline.group(1).split(",") if v.strip()]
    versions += [m.group(1) for m in re.finditer(r'python-version:\s*"?(\d+\.\d+)"?\s*$',
                                                 text, re.MULTILINE)]
    images = re.findall(r'os:\s*\[([^\]]*)\]', text)
    runs = []
    for group in images:
        runs += [image.strip().strip("'\"") for image in group.split(",") if image.strip()]
    runs += re.findall(r'-\s*os:\s*([\w.-]+)', text)
    runs += re.findall(r'runs-on:\s*([\w.-]+)', text)
    return versions, sorted(set(runs))


def ubuntu_images(runs):
    return [image for image in (runs or []) if image.startswith("ubuntu")]


def documented_floor_rows(root):
    """The `| python floor | ... |` table rows a human reads, by file."""
    found = {}
    for rel in ("README.md", "00_START_HERE/START.md"):
        path = Path(root) / rel
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "python floor" in line and line.strip().startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) > 1:
                    found[rel] = cells[1]
                break
    return found


def check(root):
    root = Path(root)
    problems = []
    floor = requires_python_floor(root)
    if floor is None:
        return ['pyproject.toml declares no requires-python = ">=X.Y" floor'], None
    ci_versions, ci_runs = workflow_matrix(root, "ci.yml")
    if ci_versions is None:
        problems.append(".github/workflows/ci.yml is missing — CI cannot prove any floor")
    else:
        if floor not in ci_versions:
            problems.append("the floor is %s but the ci matrix installs %s"
                            % (floor, ", ".join(sorted(ci_versions))))
        for version in ci_versions:
            if parse_version(version) < parse_version(floor):
                problems.append("ci.yml installs %s, below the declared floor %s" % (version, floor))
        ubuntu = ubuntu_images(ci_runs)
        floating = [image for image in ubuntu if image == UNPINNED_UBUNTU]
        if floating:
            problems.append("ci.yml rides the floating image `%s`: measured 2026-11-01, "
                            "`ubuntu-latest` moved to Ubuntu 26.04, that image carries no %s x64 "
                            "build, and every run died in setup-python while the local gates stayed "
                            "green — name the image you actually measured"
                            % (UNPINNED_UBUNTU, floor))
        if ubuntu and not any(image != UNPINNED_UBUNTU for image in ubuntu):
            problems.append("the floor %s has no pinned ubuntu image to be measured on" % floor)
    loop_versions, loop_runs = workflow_matrix(root, "loop.yml")
    if loop_versions is None:
        problems.append(".github/workflows/loop.yml is missing — the nightly loop has no door")
    else:
        for version in loop_versions:
            if parse_version(version) < parse_version(floor):
                problems.append("loop.yml runs %s, below the declared floor %s" % (version, floor))
        if UNPINNED_UBUNTU in ubuntu_images(loop_runs):
            problems.append("loop.yml rides the floating `%s` image — the nightly loop is the one "
                            "promise that has to survive every runner migration, so it names an "
                            "image" % UNPINNED_UBUNTU)
    for rel, claim in sorted(documented_floor_rows(root).items()):
        claim_version = re.search(r"(\d+\.\d+)", claim)
        if claim_version is None:
            problems.append("%s states a python floor this gate cannot read: %r" % (rel, claim))
        elif claim_version.group(1) != floor:
            problems.append("%s tells the reader %s while pyproject.toml requires %s"
                            % (rel, claim_version.group(1), floor))
    return problems, floor


def main():
    parser = argparse.ArgumentParser(description="the python floor: one number, four places")
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    problems, floor = check(root)
    if problems:
        for problem in problems:
            print("INVALID  %s" % problem)
        print("REFUSED: this folder promises a python floor it does not prove")
        return 1
    ci_versions, ci_runs = workflow_matrix(root, "ci.yml")
    loop_versions, _ = workflow_matrix(root, "loop.yml")
    print("OK — python floor %s: pyproject agrees, ci installs %s on %s, the nightly loop runs "
          "%s, and the docs say the same number"
          % (floor, ", ".join(sorted(set(ci_versions))), ", ".join(ci_runs),
             ", ".join(sorted(set(loop_versions)))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
