#!/usr/bin/env python
"""Probe — run a candidate's declared command once and record what actually happened.

Borrowed from google-research/harness2 (Propose -> Probe -> Compose): a claim about
behaviour is only evidence if something was executed and its output looked at. The
promote gate already trusted a hand-written `evaluation.passed` boolean; a checkbox
is not a measurement. This script supplies the missing execution.

What one probe does:
  1. reads the candidate's declared `probe:` command + `probe_args:` / `probe_expects:`
  2. refuses anything outside the allowlisted script dirs, anything that escapes the
     repo, anything that is not a .py file, and the reserved scripts (no shell, argv only)
  3. diffs the repo inventory before and after, so a probe that moves files the
     candidate did not declare under `probe_writes:` is reported as unsafe instead of
     quietly folded into the evidence
  4. fingerprints the *state of the brain* (the tree minus its paperwork: the quarantine
     shelf, the disposable runtime plane, the proposal sink) before and after, so filing
     a decision cannot invalidate a measurement — and hashes the candidate itself, so
     editing a verdict after the run cannot inherit the run's evidence
  5. writes a record to 14_CANDIDATES/loop/probes/<cand>-<fingerprint>.md plus one
     line in probes/index.jsonl (human-readable AND agent-greppable)

Usage:
  python scripts/probe.py --candidate 14_CANDIDATES/loop/cand-x.md
  python scripts/probe.py --candidate ... --root <repo> --timeout 120

Exit 0 only for outcome=pass. undelivered / fail / unsafe-mutating all exit 1, so
nothing that did not actually produce can be promoted on top of it.
"""
import argparse
import datetime
import glob
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (find_root, inventory_diff, parse_frontmatter, state_fingerprint,
                    tree_inventory)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

# where a probe is allowed to live: the repo's own tested tooling, nothing else
ALLOWED_DIRS = ("scripts", "15_SYSTEM/scripts")
# scripts that reach outside the repo (a user's home dir) — running them from an
# unattended candidate is not a measurement, it is a side effect
REFUSED_PROBES = ("scripts/install.py",)


def resolve_command(root, candidate_fm):
    """Return (argv, refusal_reason). argv is empty when the declaration is unusable."""
    raw = candidate_fm.get("probe")
    if not raw:
        return [], "candidate declares no `probe:` command — a behaviour claim with no execution behind it"
    rel = str(raw).replace("\\", "/").lstrip("./")
    if rel.startswith("/") or ".." in Path(rel).parts:
        return [], "probe must be a repo-relative path, got %s" % raw
    if not rel.endswith(".py"):
        return [], "probe must be a .py script (no shell, no interpreter guessing): %s" % rel
    if not any(rel.startswith(d + "/") for d in ALLOWED_DIRS):
        return [], "probe %s is outside the allowlisted script dirs %s" % (rel, list(ALLOWED_DIRS))
    if not (root / rel).is_file():
        return [], "probe script does not exist: %s" % rel
    for refused in REFUSED_PROBES:
        if rel == refused:
            return [], "probe %s is reserved: it writes outside the repo" % rel
    args = candidate_fm.get("probe_args") or []
    if isinstance(args, str):
        args = [args]
    argv = [sys.executable, str(root / rel)] + [str(a) for a in args]
    return argv, ""


def delivered_files(root, patterns):
    """Every declared expectation must exist and be non-empty — produced nothing = unsafe."""
    hits = []
    for pattern in patterns or []:
        matches = [p for p in glob.glob(str(root / str(pattern).replace("\\", "/")))
                   if Path(p).is_file() and Path(p).stat().st_size > 0]
        if matches:
            hits.append((str(pattern), len(matches)))
    return hits


def tail(text, limit=12):
    lines = [l for l in (text or "").splitlines() if l.strip()]
    return lines[-limit:]


def unsanctioned_moves(moves, sanctioned_prefixes):
    """Which files the probe moved that it never said it would.

    harness2 bounces an off-surface edit back by name; the same discipline here —
    a probe may write where the candidate declared it may write, nowhere else.
    """
    return [(rel, kind) for rel, kind in moves
            if not any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in sanctioned_prefixes)]


def outcome_of(returncode, expectations, delivered, unsanctioned, produced_output):
    if returncode != 0:
        return "fail"
    if unsanctioned:
        return "unsafe-mutating"
    if expectations and len(delivered) != len(expectations):
        return "undelivered"
    if not expectations and not produced_output:
        return "undelivered"
    return "pass"


def write_record(root, candidate, fm, record):
    shelf = root / "14_CANDIDATES" / "loop" / "probes"
    shelf.mkdir(parents=True, exist_ok=True)
    cand_id = str(fm.get("id") or candidate.stem)
    path = shelf / ("%s-%s.md" % (cand_id, record["fingerprint_at"]))
    body = [
        "---", "type: probe", "owner: agent", "status: raw",
        "title: Probe record",
        "id: probe-%s-%s" % (cand_id, record["fingerprint_at"]),
        "created: %s" % record["date"],
        "updated: %s" % record["date"],
        "topics: [probe, evidence, loop]",
        "candidate: %s" % cand_id,
        "outcome: %s" % record["outcome"],
        "delivered: %s" % ("true" if record["delivered"] else "false"),
        "mutated: %s" % ("true" if record["unsanctioned"] else "false"),
        "changed_paths: %s" % json.dumps(["%s:%s" % (k, r) for r, k in record["moves"]]),
        "returncode: %s" % record["returncode"],
        "fingerprint_at: %s" % record["fingerprint_at"],
        "fingerprint_after: %s" % record["fingerprint_after"],
        "candidate_digest: %s" % record["candidate_digest"],
        "command: %s" % record["command"],
        "---",
        "",
        "# Probe — %s" % cand_id,
        "",
        "One real execution of the candidate's declared command. Facts only: no verdict",
        "is inferred here, the verdict belongs to the human or the promote gate.",
        "",
        "- outcome: **%s**" % record["outcome"],
        "- command: `%s`" % record["command"],
        "- returncode: %s in %.1fs" % (record["returncode"], record["duration_s"]),
        "- delivered expectations: %s" % (json.dumps(record["delivered_expectations"])
                                          if record["delivered_expectations"] else "(none declared)"),
        "- tree before: `%s`  after: `%s`" % (record["fingerprint_at"], record["fingerprint_after"]),
        "- moved by this probe: %s" % (", ".join("%s (%s)" % (r, k) for r, k in record["moves"])
                                       or "(nothing — the measured tree stayed exactly as it was)"),
        "- moved outside what the candidate declared: %s"
        % (", ".join("%s (%s)" % (r, k) for r, k in record["unsanctioned"]) or "nothing"),
        "",
        "```text",
        "\n".join(record["stdout_tail"] + record["stderr_tail"]) or "(no output)",
        "```",
    ]
    path.write_text("\n".join(body) + "\n", encoding="utf-8")
    with (shelf / "index.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({
            "date": record["date"], "candidate": cand_id, "outcome": record["outcome"],
            "returncode": record["returncode"], "delivered": record["delivered"],
            "mutated": bool(record["unsanctioned"]),
            "changed": [r for r, _k in record["moves"]],
            "fingerprint_at": record["fingerprint_at"],
            "fingerprint_after": record["fingerprint_after"],
            "candidate_digest": record["candidate_digest"],
            "command": record["command"], "record": path.relative_to(root).as_posix(),
        }, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", required=True, help="candidate markdown with a probe declaration")
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--timeout", type=int, default=120)
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    candidate = Path(args.candidate)
    if not candidate.is_absolute():
        candidate = root / candidate
    if not candidate.is_file():
        print("REFUSED: candidate not found: %s" % candidate)
        return 1
    fm, _body = parse_frontmatter(candidate.read_text(encoding="utf-8", errors="replace"))
    argv, refusal = resolve_command(root, fm)
    if refusal:
        print("REFUSED: %s" % refusal)
        return 1
    expectations = fm.get("probe_expects") or []
    if isinstance(expectations, str):
        expectations = [expectations]

    sanctioned = fm.get("probe_writes") or []
    if isinstance(sanctioned, str):
        sanctioned = [sanctioned]

    inv_before = tree_inventory(root)
    fingerprint_before = state_fingerprint(root)
    started = time.monotonic()
    try:
        result = subprocess.run(argv, cwd=str(root), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=args.timeout)
        returncode = result.returncode
        stdout, stderr = result.stdout or "", result.stderr or ""
    except subprocess.TimeoutExpired:
        returncode, stdout = 124, "TIMEOUT after %ss" % args.timeout
        stderr = ""
    duration = time.monotonic() - started
    inv_after = tree_inventory(root)
    fingerprint_after = state_fingerprint(root)
    moves = inventory_diff(inv_before, inv_after)
    off_surface = unsanctioned_moves(moves, sanctioned)
    hits = delivered_files(root, expectations)
    outcome = outcome_of(returncode, expectations, hits, off_surface,
                         bool(stdout.strip() or stderr.strip()))

    record = {
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "outcome": outcome, "returncode": returncode,
        "delivered": bool(outcome == "pass"),
        "moves": moves, "unsanctioned": off_surface, "sanctioned_prefixes": sanctioned,
        "delivered_expectations": [{"pattern": p, "matches": n} for p, n in hits],
        "fingerprint_at": fingerprint_before, "fingerprint_after": fingerprint_after,
        # the claim itself is hashed: editing a verdict after the run must not inherit
        # the run's evidence
        "candidate_digest": hashlib.sha1(candidate.read_bytes()).hexdigest()[:16],
        "duration_s": duration,
        "command": " ".join([Path(argv[0]).name, str(Path(argv[1]).relative_to(root).as_posix())]
                            + argv[2:]).replace("\\", "/"),
        "stdout_tail": tail(stdout), "stderr_tail": tail(stderr),
    }
    path = write_record(root, candidate, fm, record)
    print("PROBE %s — outcome=%s rc=%s delivered=%s off-surface=%s (%.1fs)"
          % (fm.get("id") or candidate.stem, outcome, returncode, record["delivered"],
             len(off_surface), duration))
    print("record: %s" % path.relative_to(root).as_posix())
    if outcome == "undelivered":
        print("NOTE: the run produced nothing to look at — harness2 rule: an edit whose "
              "rollout produced nothing is UNSAFE, not merely unproven.")
    if off_surface:
        print("NOTE: the probe moved files the candidate never declared it would write:")
        for rel, kind in off_surface[:10]:
            print("  %s  (%s)" % (rel, kind))
        print("A measurement that rewrites its own subject is not evidence; declare "
              "`probe_writes:` in the candidate or fix the script.")
    return 0 if outcome == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
