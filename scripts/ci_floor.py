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

Exit 0 = one floor everywhere; 1 = at least one of them disagrees. An installed brain home keeps
neither `.git` nor `pyproject.toml` and runs no CI, so the promise being compared does not live
there: the gate says so in one stated line and exits 0. A checkout missing the manifest is a
defect and still refuses.
"""
import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root, is_repo_checkout  # noqa: E402

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
    path = Path(root) / "pyproject.toml"
    if not path.is_file():
        return None
    match = re.search(r'requires-python\s*=\s*">=\s*(\d+\.\d+)"',
                      path.read_text(encoding="utf-8"))
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


def expected_required_test_contexts(root):
    """Derive the four `test (os, version)` check names from the actual CI matrix.

    Read only the `test` job: backup jobs and the nightly loop are separate
    checks, and treating their versions as a second matrix would create a lie.
    Refuse an unfamiliar layout or custom job name rather than guess.
    """
    path = Path(root) / ".github/workflows/ci.yml"
    if not path.is_file():
        raise ValueError("ci.yml is missing")
    source = path.read_text(encoding="utf-8")
    match = re.search(r"(?ms)^  test:\s*\n(.*?)(?=^  [\w-]+:\s*(?:\n|$)|\Z)", source)
    if not match:
        raise ValueError("ci.yml has no recognizable jobs.test matrix")
    block = match.group(1)
    if re.search(r"(?m)^    name:\s*", block):
        raise ValueError("jobs.test has a custom name; inspect emitted check names manually")

    def values(key):
        fields = re.findall(r"(?m)^\s+" + re.escape(key) +
                            r":\s*\[([^\]\n]+)\]\s*$", block)
        if len(fields) != 1:
            raise ValueError("jobs.test must have one inline %s matrix" % key)
        parsed = [item.strip().strip("'\"") for item in fields[0].split(",")]
        if not parsed or any(not item for item in parsed) or len(set(parsed)) != len(parsed):
            raise ValueError("jobs.test %s matrix contains empty/duplicate values" % key)
        return parsed

    images, versions = values("os"), values("python-version")
    return sorted("test (%s, %s)" % (image, version)
                  for image in images for version in versions)


def required_status_context_problems(root, branch):
    """Compare public branches/main metadata to the actual jobs, fail closed.

    Branch metadata is read-only data; this audit never edits protection or
    treats a green Actions job as permission to bypass an obsolete requirement.
    """
    if not isinstance(branch, dict) or branch.get("protected") is not True:
        return ["main protection is absent or unverifiable"]
    protection = branch.get("protection")
    checks = protection.get("required_status_checks") if isinstance(protection, dict) else None
    contexts = checks.get("contexts") if isinstance(checks, dict) else None
    if not isinstance(contexts, list) or not contexts or not all(
            isinstance(item, str) and item for item in contexts):
        return ["main required check contexts are absent or unverifiable"]
    try:
        expected = set(expected_required_test_contexts(root))
    except (OSError, ValueError) as exc:
        return ["cannot derive the CI test matrix: %s" % exc]
    current = set(contexts)
    problems = []
    for name in sorted(expected - current):
        problems.append("required check missing: %s" % name)
    for name in sorted(current - expected):
        if name.startswith("test ("):
            problems.append("obsolete/unmatched required test check: %s" % name)
    return problems


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
        if not (root / "pyproject.toml").is_file():
            return ['pyproject.toml is missing — no packaging manifest, so no floor to prove'], None
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
    parser.add_argument("--branch-json", default=None,
                        help="offline exported GitHub GET /branches/main response (read-only)")
    parser.add_argument("--live-protection", action="store_true",
                        help="opt-in public GitHub API read; no token, config write or bypass")
    args = parser.parse_args()
    if args.branch_json and args.live_protection:
        parser.error("choose --branch-json OR --live-protection")
    root = Path(args.root) if args.root else find_root(Path(__file__))
    if not is_repo_checkout(root) and (args.branch_json or args.live_protection):
        print("REFUSED: CI protection can only be audited from a repository checkout")
        return 1
    if not is_repo_checkout(root):
        print("OK — no floor to prove in %s: this folder is an installed brain home, not a repo "
              "checkout (no .git, no pyproject.toml), and the promise this gate inspects is the "
              "repo's CI matrix. The runtime floor itself is unchanged and still stated to the "
              "reader in 00_START_HERE/START.md" % root)
        return 0
    problems, floor = check(root)
    if problems:
        for problem in problems:
            print("INVALID  %s" % problem)
        print("REFUSED: this folder promises a python floor it does not prove")
        return 1
    if args.branch_json or args.live_protection:
        try:
            if args.branch_json:
                branch = json.loads(Path(args.branch_json).read_text(encoding="utf-8"))
            else:
                url = ("https://api.github.com/repos/"
                       "iAlirezaaa/second-brain-os/branches/main")
                request = urllib.request.Request(
                    url, headers={"Accept": "application/vnd.github+json",
                                  "User-Agent": "second-brain-os-ci-protection-audit"})
                with urllib.request.urlopen(request, timeout=10) as response:
                    branch = json.loads(response.read(262145).decode("utf-8"))
            problems = required_status_context_problems(root, branch)
        except (OSError, ValueError, UnicodeError) as exc:
            print("REFUSED: cannot inspect required checks (%s: %s)" %
                  (type(exc).__name__, exc))
            return 1
        if problems:
            for problem in problems:
                print("INVALID  %s" % problem)
            print("REFUSED: protected main requires checks the current CI cannot emit")
            return 1
        print("OK — required protected-main test checks match ci.yml; "
              "this does not certify other branch rules or authorize a merge")
        return 0
    ci_versions, ci_runs = workflow_matrix(root, "ci.yml")
    loop_versions, _ = workflow_matrix(root, "loop.yml")
    print("OK — python floor %s: pyproject agrees, ci installs %s on %s, the nightly loop runs "
          "%s, and the docs say the same number"
          % (floor, ", ".join(sorted(set(ci_versions))), ", ".join(ci_runs),
             ", ".join(sorted(set(loop_versions)))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
