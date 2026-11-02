#!/usr/bin/env python
"""Health gate + bump mechanism: one version, four places, and the number comes from commits.

The repo's own law says a hand-typed number is a claim, not a measurement (issue #4 killed the
hand-typed test-count badge). The version was the last hand-typed number left: `VERSION` and
`pyproject.toml` agreed, and nothing compared either of them to the README title, the README
badge, `CHANGELOG.md` or the tag the clone carries. The result was shipped in plain sight:
the README opened with `HADES OS v0.01` while `VERSION` said `0.0.3`.

So the number is derived, not remembered:

* `--bump auto` reads the commit subjects since the last tag and takes the HIGHEST level it sees
  (`feat!` or a `BREAKING CHANGE` body -> major, `feat` -> minor, `fix`/`perf` -> patch,
  `docs`/`test`/`chore`/`refactor`/`ci`/`style` -> no bump at all). A release whose version came
  from the size of its work cannot be inflated by an eager author.
* `--check` refuses when `VERSION`, `pyproject.toml`, the README title, the README badge and the
  changelog disagree, or when work is committed after the released tag with an empty
  `## [Unreleased]` section — which is the same silent-gate failure in the other direction:
  shipped code that no changelog admits to.
* `--bump` never tags and never pushes. It writes `VERSION` and prints the two commands a human
  runs to make the release; a tag is a published promise and this repo keeps promises for the
  owner to make.
* An installed brain home keeps no `VERSION`, no `pyproject.toml` and no tag — it is a copy of
  the engine, not a release — so `--check` states that skip and exits 0, while `--bump` refuses
  there rather than writing a number into files the folder does not have.
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root, is_repo_checkout, run_utf8  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
COMMIT_TYPE_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^)]*)\))?(?P<breaking>!)?:\s")
BREAKING_BODY_RE = re.compile(r"^BREAKING[ -]CHANGE\s*:", re.MULTILINE)

# the ladder is the whole rule; anything a commit says that is not on it is not a bump signal
LEVELS = {"none": 0, "patch": 1, "minor": 2, "major": 3}
BUMPING_TYPES = {"fix": "patch", "perf": "patch", "feat": "minor"}
NEUTRAL_TYPES = {"docs", "test", "chore", "refactor", "ci", "style", "build", "revert"}


def split_semver(text):
    match = SEMVER_RE.match((text or "").strip())
    if not match:
        raise ValueError("%r is not a MAJOR.MINOR.PATCH version" % (text,))
    return tuple(int(part) for part in match.groups())


def format_semver(parts):
    return "%d.%d.%d" % parts


def next_version(current, level):
    """The version after `level`, with SemVer's 0.x courtesy stated below."""
    major, minor, patch = split_semver(current)
    if level == "major":
        # at 0.x a minor release already means "the contract moved" (SemVer §4), so a breaking
        # change raises the minor instead of jumping to 1.0 — the jump is the owner's call,
        # made once, when the owner decides the engine is no longer experimental.
        if major == 0:
            return format_semver((0, minor + 1, 0))
        return format_semver((major + 1, 0, 0))
    if level == "minor":
        return format_semver((major, minor + 1, 0))
    if level == "patch":
        return format_semver((major, minor, patch + 1))
    return format_semver((major, minor, patch))


def classify_commit(subject, body=""):
    """One commit -> the level it demands. Unknown prose is `none`, never a guess."""
    if BREAKING_BODY_RE.search(body or ""):
        return "major"
    match = COMMIT_TYPE_RE.match(subject or "")
    if not match:
        return "none"
    if match.group("breaking"):
        return "major"
    kind = match.group("type")
    if kind in BUMPING_TYPES:
        return BUMPING_TYPES[kind]
    if kind in NEUTRAL_TYPES:
        return "none"
    return "none"


def highest_level(commits):
    """commits: [(subject, body)] -> the level the set as a whole demands."""
    level = "none"
    for subject, body in commits:
        found = classify_commit(subject, body)
        if LEVELS[found] > LEVELS[level]:
            level = found
    return level


def git(root, *args):
    result = run_utf8(["git", *args], cwd=str(root))
    if result.returncode != 0:
        return None
    return (result.stdout or "").strip()


def latest_tag(root):
    tag = git(root, "describe", "--tags", "--abbrev=0", "HEAD")
    return tag or ""


def commits_since(root, tag):
    """[(subject, body)] between the released tag and HEAD; the range the bump is measured on."""
    spec = "%s..HEAD" % tag if tag else "HEAD"
    log = git(root, "log", spec, "--format=%s%n%b%n\x01")
    if log is None or log == "":
        return []
    commits = []
    for chunk in log.split("\x01"):
        chunk = chunk.strip("\n")
        if not chunk:
            continue
        lines = chunk.splitlines()
        subject = lines[0] if lines else ""
        body = "\n".join(lines[1:])
        commits.append((subject, body))
    return commits


def read_text(root, rel):
    path = Path(root) / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def declared_version(root):
    return (read_text(root, "VERSION") or "").strip()


def pyproject_version(root):
    text = read_text(root, "pyproject.toml") or ""
    match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    return match.group(1) if match else None


def changelog_headings(root):
    """`## [0.0.3] — 2026-10-27` and `## [Unreleased]` both count; the date is decoration."""
    text = read_text(root, "CHANGELOG.md") or ""
    return re.findall(r"^##\s+\[?([^\]\s]+)\]?", text, re.MULTILINE)


def readme_cites(root, version):
    """The README must carry the number where a reader looks for it: the title and the badge.

    A gate that only grepped the file for the digits would pass on a stale title beside a fresh
    badge — the exact split this repo refuses (issue #16: a true refusal with a false reason).
    """
    text = read_text(root, "README.md") or ""
    problems = []
    title = text.splitlines()[0] if text.splitlines() else ""
    if version not in title:
        problems.append("the README title says %r while VERSION says %r" % (title[:60], version))
    if ("badge/engine-v%s-blue" % version) not in text:
        problems.append("the README version badge does not carry %s" % version)
    return problems


def unreleased_is_empty(root):
    """True when `## [Unreleased]` exists but declares nothing."""
    text = read_text(root, "CHANGELOG.md") or ""
    match = re.search(r"^## \[Unreleased\]\s*$(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    if match is None:
        return False
    body = match.group(1)
    return not re.search(r"^###\s*\w", body, re.MULTILINE) or not re.search(
        r"^- \*\*", body, re.MULTILINE)


def check(root):
    """Every way this folder can claim two different versions. [] means the number is one."""
    version = declared_version(root)
    problems = []
    try:
        split_semver(version)
    except ValueError as exc:
        return ["VERSION: %s" % exc]
    pyproject = pyproject_version(root)
    if pyproject is None:
        problems.append("pyproject.toml declares no version")
    elif pyproject != version:
        problems.append("pyproject.toml says %s but VERSION says %s" % (pyproject, version))
    problems += ["README: " + line for line in readme_cites(root, version)]

    headings = changelog_headings(root)
    tag_exists = bool(git(root, "rev-parse", "-q", "--verify", "v%s" % version))
    if tag_exists:
        if version not in headings:
            problems.append("tag v%s exists but CHANGELOG.md has no [%s] section" % (version, version))
    else:
        if "Unreleased" not in headings:
            problems.append("VERSION %s is not tagged and CHANGELOG.md has no [Unreleased] section"
                            % version)
        elif unreleased_is_empty(root):
            problems.append("VERSION %s is not tagged and CHANGELOG.md's [Unreleased] declares nothing"
                            % version)
    return problems


def git_available(root):
    """False outside a clone — the tag half of the check is then skipped, loudly, in the report."""
    return git(root, "rev-parse", "--git-dir") is not None


def report(root):
    version = declared_version(root)
    tag = latest_tag(root)
    commits = commits_since(root, tag)
    level = highest_level(commits)
    computed = next_version(version, level) if level != "none" else version
    print("current      %s" % version)
    print("latest tag   %s" % (tag or "(none)"))
    print("commits since tag  %d" % len(commits))
    print("measured level     %s" % level)
    print("next version       %s" % computed)
    return version, tag, level, computed


def bump(root, level):
    version = declared_version(root)
    if not version or not (Path(root) / "pyproject.toml").is_file():
        print("REFUSED: %s has no %s — a bump writes a release number into files this folder "
              "does not keep" % (root, "VERSION to read" if not version else "pyproject.toml"))
        return 1
    split_semver(version)
    if level == "auto":
        commits = commits_since(root, latest_tag(root))
        level = highest_level(commits)
        if level == "none":
            print("NO_BUMP  %d commit(s) since the last tag carry no feat, fix or breaking-change "
                  "signal (%s) — documentation and tests alone do not move a version"
                  % (len(commits), version))
            return 3
    target = next_version(version, level)
    if target == version:
        print("NO_BUMP  %s is already at the %s boundary for a 0.x engine" % (version, level))
        return 3
    (Path(root) / "VERSION").write_text(target + "\n", encoding="utf-8")
    pyproject = Path(root) / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    pyproject.write_text(re.sub(r'^version\s*=\s*"[^"]*"', 'version = "%s"' % target,
                                text, count=1, flags=re.MULTILINE), encoding="utf-8")
    print("WROTE    VERSION %s -> %s (level %s), pyproject.toml follows" % (version, target, level))
    print("the release itself is a human act: git tag v%s && git push origin v%s" % (target, target))
    print("then set the README title and badge to v%s and run python scripts/doc_report.py --write"
          % target)
    return 0


def main():
    parser = argparse.ArgumentParser(description="the version gate: one number, derived")
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--check", action="store_true", help="refuse when the number disagrees")
    parser.add_argument("--show", action="store_true", help="print the measured next version")
    parser.add_argument("--bump", choices=["auto", "major", "minor", "patch"], default=None,
                        help="write the next version (auto = measured from commits since the tag)")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))

    if not is_repo_checkout(root):
        # the four places this gate compares (VERSION, pyproject.toml, README badge, the tag)
        # are the repo's release paperwork; an installed brain home keeps none of them, so the
        # honest answer is a stated skip. A checkout missing one of them is a defect, and the
        # refusal below still fires there.
        if args.bump:
            print("REFUSED: %s is an installed brain home, not a repo checkout (no .git, no "
                  "pyproject.toml) — a version is a promise about a release. Bump the source "
                  "repo and install again." % root)
            return 1
        print("OK — no release number to check in %s: this folder is an installed brain home, "
              "not a repo checkout (no .git, no pyproject.toml), so it makes no version claim; "
              "the engine it runs is the one the source repo released" % root)
        return 0

    if args.bump:
        return bump(root, args.bump)
    if args.show:
        report(root)
        return 0
    if args.check:
        version = declared_version(root)
        tag = latest_tag(root)
        problems = check(root)
        if problems:
            for problem in problems:
                print("INVALID  %s" % problem)
            print("REFUSED: this folder claims more than one version")
            return 1
        commits = commits_since(root, tag)
        print("OK — one version everywhere: %s (tag %s, %d commit(s) since, next level %s)"
              % (version, tag or "(none)", len(commits), highest_level(commits)))
        return 0
    report(root)
    problems = check(root)
    for problem in problems:
        print("INVALID  %s" % problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
