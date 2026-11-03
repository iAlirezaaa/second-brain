#!/usr/bin/env python3
"""Goal and founding-idea regression gate.

This guards accidental alteration of owner-defined, frozen historical sources.
It is not cryptographic actor authentication, and it cannot substitute for
branch protection plus a human review of changes to GOAL or this guard.
"""
import argparse
import hashlib
import sys
from pathlib import Path

# These are *Git blob* SHA-1 fingerprints of the archived ORIGINAL bytes.
# To amend this list, the owner must explicitly approve a protected-change
# proposal. Existing baselines should never be rewritten; append a new version.
FROZEN_BLOBS = {
    "10_ARCHIVE/foundations/2026-11-03-PROJECT_CHARTER.snapshot.txt": "40dfe74182c8fd574e2b1b890bfd67836ca80dfb",
    "10_ARCHIVE/foundations/2026-11-03-PRODUCT_VNEXT.snapshot.txt": "2a57e4f62dab19d3577ea03dc471e809875323ab",
    "10_ARCHIVE/foundations/2026-11-03-CONSTITUTION.snapshot.txt": "744bb27b7ec03cb6b0fe45600b76d9701ffb2a0a",
    "10_ARCHIVE/foundations/2026-11-03-IDENTITY-v1.md": "44192569113cb31b2426c0dff3f860d7d4d7472d"
}

# These living documents are pinned too: updates require a deliberate, reviewed
# change of both content and this fingerprint. The archived originals stay untouched.
PROTECTED_GOAL_BLOBS = {
    "00_START_HERE/GOAL.md": "406e94cd90d28269566efcd95c3e31f44352731f",
    "00_START_HERE/GOAL_FA.md": "5d0360a92462186f253d4cff2c6f01e4643c0549",
    "00_START_HERE/CHANGE_GOVERNANCE.md": "e1dd2d5e5530bee9510a447240aaa66c873ae62f"
}

REQUIRED_GOAL_FILES = {
    "00_START_HERE/GOAL.md": ("10_ARCHIVE/foundations/", "CHANGE_GOVERNANCE.md"),
    "00_START_HERE/GOAL_FA.md": ("GOAL.md", "10_ARCHIVE/foundations/"),
    "00_START_HERE/CHANGE_GOVERNANCE.md": ("FROM", "TO", "HUMAN"),
    "10_ARCHIVE/foundations/README.md": ("snapshot", "GOAL.md"),
}


def git_blob_sha(content):
    """Return the same hash Git uses for a stored blob, not a file-system mtime."""
    raw = b"blob " + str(len(content)).encode("ascii") + b"\0" + content
    return hashlib.sha1(raw).hexdigest()


def audit(root, frozen=None, required=None):
    """Return a list of explicit failures; never treat a missing archive as empty OK."""
    root = Path(root).resolve()
    frozen = dict(FROZEN_BLOBS, **PROTECTED_GOAL_BLOBS) if frozen is None else frozen
    required = REQUIRED_GOAL_FILES if required is None else required
    problems = []
    for rel, expected in frozen.items():
        path = root / rel
        if not path.is_file() or path.is_symlink():
            problems.append("missing or unsafe frozen idea: " + rel)
            continue
        try:
            actual = git_blob_sha(path.read_bytes())
        except OSError as exc:
            problems.append("cannot read frozen idea %s: %s" % (rel, exc))
            continue
        if actual != expected:
            problems.append("frozen idea modified: %s (expected blob %s; found %s)" %
                            (rel, expected, actual))
    for rel, anchors in required.items():
        path = root / rel
        if not path.is_file() or path.is_symlink():
            problems.append("missing goal/governance entrypoint: " + rel)
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            problems.append("unreadable goal/governance entrypoint %s: %s" % (rel, exc))
            continue
        for anchor in anchors:
            if anchor not in content:
                problems.append("required goal/governance reference %r missing from %s" %
                                (anchor, rel))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--check", action="store_true", help="explicit CI gate (default action)")
    args = parser.parse_args(argv)
    problems = audit(args.root)
    if problems:
        for problem in problems:
            print("REFUSED goal/identity: " + problem)
        return 1
    print("OK goal/identity: %d frozen originals and %d pinned goal documents checked; %d entrypoints present" %
          (len(FROZEN_BLOBS), len(PROTECTED_GOAL_BLOBS), len(REQUIRED_GOAL_FILES)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
