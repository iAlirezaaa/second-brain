#!/usr/bin/env python
"""Roadmap citation gate — every path the plan names must be a path that is here.

Why this gate exists: on 2026-11-02 three phase-36 rows still read `- [ ]` while the code they
described had already shipped and been released twice over (`git tag --contains 3cb54da` answers
`v0.1.0 v0.2.0`). Checking those rows by hand also caught two citations that were simply wrong —
a command written with flags it does not take, and a function described as returning a list when
it returns a verdict dict. A roadmap whose citations nobody checks is a second truth, and this
repo's law is that a rule without a refusing script is a comment.

What it judges, and what it deliberately does not:

  * a CLOSED row (`- [x]`) that cites a repo path which is not here, and is not runtime state and
    is not declared by the code, is refused. That is the renamed-or-never-shipped defect class.
  * a CLOSED row that cites `backend/vector.py` when the repo holds
    `15_SYSTEM/scripts/backend/vector.py` is refused as well: citations stay repo-relative so a
    stranger can open them from a clone, which is the same law `common.clone_readable` enforces
    on generated artifacts.
  * an OPEN row citing a path that does not exist yet is a plan, not a claim, and is never refused
    — a roadmap that cannot name a file before it writes it would only encourage vagueness.
  * a path a script declares by name (its basename appears in tracked source) and a path inside the
    gitignored machine plane are both accepted and NAMED: journals a tool creates on its first run
    are honest evidence, and a gate that calls them defects teaches people to stop citing them.
  * `file.py:123` past the end of the file and `file.py::symbol` that the file does not define are
    refused in any row: they are stated as observations, and a wrong observation is a defect even
    in an open row.
  * a path whose first segment is not a top-level entry of this repo and whose basename is found
    nowhere here is FOREIGN — it belongs to an upstream project the row is describing. It is
    counted and printed, not refused, because this gate cannot see outside the clone and will not
    report green over what it cannot read.

Usage:
  python scripts/roadmap_check.py                 # check ROADMAP.md at the repo root
  python scripts/roadmap_check.py --root DIR --plan FILE   # fixtures and tests

Exit 0 with exactly one `OK` line when nothing is refused; exit 1 with one `REFUSED` line per
finding. In an installed brain home the roadmap is the source repo's plan, not the home's own, so
the gate says so in one OK line rather than judging promises the home never made.
"""
import argparse
import difflib
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root, is_repo_checkout

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

ROW = re.compile(r"^\s*- \[(?P<mark>[ xX])\]\s*(?P<text>.*)$")
CODE = re.compile(r"`([^`\n]+)`")
ANCHOR = re.compile(r"^(?P<base>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$")
MEMBER = re.compile(r"^(?P<base>.+?)::(?P<name>[A-Za-z_][\w.]*)$")
# a slug that can never be a repo path, however it is punctuated
NOT_A_PATH = re.compile(r"^https?://")


def read_rows(text):
    """Every checklist row with its continuation lines folded in, so a citation never strays
    outside the row that made it."""
    rows, current = [], None
    for number, line in enumerate(text.splitlines(), 1):
        match = ROW.match(line)
        if match:
            if current:
                rows.append(current)
            current = {"line": number, "closed": match.group("mark").lower() == "x",
                       "text": match.group("text")}
            continue
        if current and line.strip() and (len(line) - len(line.lstrip())) >= 2 and not ROW.match(line):
            current["text"] += " " + line.strip()
    if current:
        rows.append(current)
    return rows


def shape_of(token):
    """Split a backticked token into (path, line anchor, member) or None when it is not a path.

    Path-shaped here means repo-relative and file-like: it contains a `/` that is not the last
    character and its final segment carries an extension. A bare folder name (`indexes/`) is prose
    about a folder, not a claim that a path resolves, and this gate does not pretend otherwise.
    """
    token = token.strip()
    if not token or NOT_A_PATH.match(token) or token.startswith("http"):
        return None
    # Backticks can contain flags; judge their leading repo-relative path.
    token = token.split()[0]
    member = None
    matched = MEMBER.match(token)
    if matched:
        token, member = matched.group("base"), matched.group("name")
    anchor = None
    matched = ANCHOR.match(token)
    if matched:
        token, anchor = matched.group("base"), int(matched.group("start"))
    if token.startswith("-") or "%" in token or "<" in token or ">" in token:
        return None
    if "/" not in token:
        return None
    if "<" in token or ">" in token:
        return None
    last = token.rstrip("/").rsplit("/", 1)[-1]
    if not token.rstrip("/"):
        return None
    directory = token.endswith("/")
    if not directory and ("." not in last or last.startswith(".")) and token != ".github/CODEOWNERS":
        return None
    if token.startswith("/"):
        return ("ABSOLUTE", token, anchor, member)
    if ".." in Path(token).parts:
        return ("ESCAPES", token, anchor, member)
    if token.endswith("/") and "/" not in token.rstrip("/"):
        # `reference_maps/` names a folder in prose; `02_WIKI/reference_maps/` claims a location.
        # Only the second is a citation -- and a bare name must not reach the resolver with an
        # empty basename, or every "declared by code" lookup matches the empty string and a path
        # that exists nowhere is reported as evidence. That false green was this gate's first bug.
        return None
    return ("path", token, anchor, member)


def citations(row_text):
    out = []
    for token in CODE.findall(row_text):
        shaped = shape_of(token)
        if shaped:
            out.append((token, shaped))
    return out


class Checker:
    def __init__(self, root):
        self.root = Path(root)
        self._tracked = None
        self._grep = {}

    def tracked_files(self):
        if self._tracked is None:
            listing = self._run(["git", "ls-files", "-z"])
            if listing:
                self._tracked = sorted(p for p in listing.split("\0") if p)
            else:
                self._tracked = sorted(
                    p.as_posix() for p in self.root.rglob("*")
                    if p.is_file() and ".git" not in p.parts and "__pycache__" not in p.parts)
        return self._tracked

    def _run(self, argv):
        try:
            done = subprocess.run(argv, cwd=str(self.root), capture_output=True, text=True,
                                  encoding="utf-8", errors="replace")
        except OSError:
            return ""
        return done.stdout if done.returncode == 0 else ""

    def sources_text(self, rel):
        path = self.root / rel
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def declared_by(self, rel):
        """Tracked Python that names this exact repo-relative path, not merely its basename.

        Only source code counts: a path mentioned in a prose note is a quotation, and calling that
        "the code declares it" would let an upstream file masquerade as this repo's own state.
        """
        if rel not in self._grep:
            hits = [source for source in self.tracked_files()
                    if source.endswith(".py") and rel in self.sources_text(source)]
            self._grep[rel] = hits
        return self._grep[rel]

    def resolve(self, rel):
        """EXISTS / glob hit, or nothing — the caller decides whether that is a defect."""
        path = self.root / rel
        if any(ch in rel for ch in "*?["):
            return [m.as_posix() for m in sorted(self.root.glob(rel))]
        return [rel] if path.exists() else []

    def is_ignored(self, rel):
        """True when git says this exact path is machine-plane state the repo never tracks.

        The path is probed as the roadmap wrote it, never with a slash invented on the way in:
        on a Windows checkout `core.autocrlf` leaves a bare `\\r` line in the working copy of
        `.gitignore`, and git then matches anything probed as a directory -- so `docs/` looks
        "ignored" here while the tracked blob has no such rule. A gate may not launder an upstream
        path into this repo's runtime state because of a line ending.
        """
        try:
            return subprocess.run(["git", "check-ignore", "-q", "--", rel],
                                  cwd=str(self.root), capture_output=True).returncode == 0
        except OSError:
            return False

    def local_roots(self):
        return {p.split("/", 1)[0] for p in self.tracked_files()} | {
            p.name for p in self.root.iterdir() if p.is_dir() and not p.name.startswith(".")}


def classify(checker, kind, rel, anchor, member, row):
    """One citation, one state, and the advice a person needs to fix it in the roadmap."""
    root = checker.root
    if kind in ("ABSOLUTE", "ESCAPES"):
        return ("OUT_OF_BOUNDARY", "%s cannot be opened from a clone of this repo" % rel,
                "rewrite it repo-relative to this folder")
    found = checker.resolve(rel)
    target = found[0] if found else None
    if target:
        text = checker.sources_text(target)
        lines = [ln for ln in text.splitlines()]
        if anchor is not None and anchor > len(lines):
            return ("BAD_ANCHOR", "%s has %d line(s), so :%d is not a line anyone can open"
                    % (target, len(lines), anchor), "re-measure the line or drop the anchor")
        if member and member.split(".")[0] not in text:
            return ("BAD_MEMBER", "%s does not contain %s" % (target, member),
                    "name the symbol the file actually defines")
        return ("EXISTS", "%s is here" % target, "")
    basename = rel.rsplit("/", 1)[-1].rstrip("/")
    # `backend/schedules.is_due` is a module and a function, not a file: look for the file it means
    names = [basename] if "." not in basename or basename.endswith((".py", ".md", ".json")) else \
        [basename, basename.split(".")[0] + ".py"]
    same_name = [p for p in checker.tracked_files()
                 if p.rsplit("/", 1)[-1] in names and p != rel]
    if same_name:
        return ("NOT_REPO_RELATIVE",
                "%s is not here; the repo holds %s" % (rel, same_name[0]),
                "cite the repo-relative path so a stranger can open it")
    # only a file name can be declared: a folder's last word (`maps`) is a substring of half the
    # repo, and treating that as a witness would turn a missing directory into evidence
    declared = checker.declared_by(rel) if "." in basename else []
    if declared:
        return ("DECLARED", "%s is created or read by %s" % (rel, declared[0]), "")
    if checker.is_ignored(rel):
        return ("STATE", "%s is gitignored machine-plane state" % rel, "")
    first = rel.split("/", 1)[0]
    close_root = difflib.get_close_matches(first, checker.local_roots(), n=1, cutoff=0.85)
    if first in checker.local_roots() or close_root:
        hint = " (did you mean %s?)" % close_root[0] if close_root and first not in checker.local_roots() else ""
        return ("MISSING", "%s is not in this repo and no code names it%s" % (rel, hint),
                "the row claims it: ship it, or correct the row to the path that exists")
    return ("FOREIGN", "%s belongs outside this clone (an upstream path the row describes)" % rel,
            "")


def check(root, plan_path):
    checker = Checker(root)
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        print("REFUSED  %s cannot be read: %s" % (plan_path, exc))
        return 1
    rows = read_rows(text)
    counts, findings, notes, uncited, skipped = {}, [], [], 0, 0
    for row in rows:
        found = citations(row["text"])
        skipped += len(CODE.findall(row["text"])) - len(found)
        if not found and row["closed"]:
            uncited += 1
        for token, (kind, rel, anchor, member) in found:
            state, advice, fix = classify(checker, kind, rel, anchor, member, row)
            if state == "MISSING" and not row["closed"]:
                # a plan may name a file it has not written yet; only a closed row claims it exists
                state, advice, fix = "PLANNED", "%s is not in this repo yet" % rel, ""
            counts[state] = counts.get(state, 0) + 1
            if state in ("FOREIGN", "STATE"):
                notes.append("NOTED    %s:%d `%s` — %s" % (plan_path.name, row["line"], token, advice))
            if state in ("MISSING", "NOT_REPO_RELATIVE", "BAD_ANCHOR", "BAD_MEMBER",
                         "OUT_OF_BOUNDARY"):
                findings.append("REFUSED  %s:%d %s row cites `%s` — %s; %s"
                                % (plan_path.name, row["line"],
                                   "closed" if row["closed"] else "open", token, advice, fix))
    for line in notes:
        print(line)
    for line in findings:
        print(line)
    if findings:
        print("REFUSED  %d citation(s) in %s do not resolve; a plan that cites what is not there "
              "is a claim nobody can check" % (len(findings), plan_path.name))
        return 1
    closed = sum(1 for r in rows if r["closed"])
    print("OK — %d row(s) in %s (%d closed, %d open); %d path citation(s) checked: %s; "
          "%d skipped non-path token(s); %d closed row(s) carry no path citation at all — counted, not refused, because the "
          "honest gap in this roadmap is evidence that was never written down, and a number that "
          "moves here is a number that can be closed"
          % (len(rows), plan_path.name, closed, len(rows) - closed, sum(counts.values()),
             ", ".join("%s %d" % (k, counts[k]) for k in sorted(counts)) or "none", skipped, uncited))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--plan", default=None, help="plan file override (tests)")
    parser.add_argument("--check", action="store_true", help="the only act; explicit for health")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    if not is_repo_checkout(root):
        print("OK — no roadmap promises to judge in %s: this folder is an installed brain home, "
              "not a repo checkout, so it inherited the source repo's plan instead of making one"
              % root)
        return 0
    plan = Path(args.plan) if args.plan else root / "ROADMAP.md"
    if not plan.is_file():
        print("OK — %s carries no ROADMAP.md: nothing here claims work in progress, so there is "
              "no citation to check" % root)
        return 0
    return check(root, plan)


if __name__ == "__main__":
    sys.exit(main())
