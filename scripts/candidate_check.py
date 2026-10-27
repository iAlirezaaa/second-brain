#!/usr/bin/env python
"""Candidate contract enforcer — a shelf row is a claim, and claims carry evidence.

rules/candidate.schema.json is the law; this script is the fence. Borrowed from
google-research/harness2 (Propose -> Probe -> Compose), kept stdlib and offline:

  * a row that claims behaviour must have been executed -- `verdict: helped` with no
    probe record is a checkbox, not a measurement
  * a measurement describes the tree it was taken on -- a probe whose fingerprint does
    not match the current tree is evidence about a repo that no longer exists
  * evidence must resolve: a path on disk, a URL, or a probe id in the index. A pointer
    to nothing is a fabrication, and it is treated as one
  * NO_ENTRY is legal and honest: "nothing in memory applied" is data. A NO_ENTRY row
    that also teaches a lesson is not a NO_ENTRY row
  * `proposed` is legal on the shelf and never promotable: naming a change is not the
    same act as measuring it
  * the shelf reconciles with its ledger -- proposed == adopt + revise + drop +
    keep_base + open, ids are unique, and a row that leaves without a disposition is
    reported as the lost measurement it is
  * `keep_base` is an output, not a failure -- deciding to change nothing needs no run

Usage:
  python scripts/candidate_check.py                 # the whole shelf
  python scripts/candidate_check.py --file 14_CANDIDATES/loop/cand-x.md
  python scripts/candidate_check.py --root <repo> --json

Exit 0 = every candidate on the shelf satisfies the contract, exit 1 = violations.
"""
import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import find_root, load_json, parse_frontmatter, state_fingerprint

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

CONTRACT_KEYS = ("dimension", "cue", "lesson", "verdict")
# what each verdict is claiming about the world, and therefore what it must show
PROBE_OUTCOMES = {
    "helped": ("pass",),
    "hurt": ("fail",),
    "no_observed_effect": ("pass", "fail"),
}
NO_ENTRY = "NO_ENTRY"
# the loop is allowed to name a change it has not measured yet -- that is the whole point
# of a proposal -- but a proposal never leaves the shelf (see promote.candidate_gate)
PROPOSED = "proposed"
DISPOSITIONS = ("adopt", "revise", "drop", "keep_base")


def as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    return [str(v) for v in value]


def is_candidate(fm):
    """Reports are reports; a candidate is a row that makes a claim."""
    return any(fm.get(key) for key in CONTRACT_KEYS)


def probe_index(root):
    """{candidate_id: [record, ...]} from the probe shelf's machine-readable ledger."""
    path = root / "14_CANDIDATES" / "loop" / "probes" / "index.jsonl"
    rows = {}
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        rows.setdefault(str(record.get("candidate", "")), []).append(record)
    return rows


def evidence_resolves(entry, root, known_probe_ids):
    """An evidence line must be openable by a reader who is not the one who wrote it."""
    text = entry.strip().strip("'\"")
    if not text:
        return False, "empty evidence line"
    if text.startswith(("http://", "https://")):
        return True, ""
    if text.startswith("probe-") or text.startswith("probe:"):
        pid = text.split(":", 1)[-1] if text.startswith("probe:") else text
        if pid in known_probe_ids:
            return True, ""
        return False, "probe id %s is not in 14_CANDIDATES/loop/probes/index.jsonl" % pid
    cleaned = text.replace("\\", "/")
    if cleaned.startswith("./"):
        cleaned = cleaned[2:]        # only a ./ prefix -- lstrip would eat ".kb" too
    candidate_path = root / cleaned
    if candidate_path.exists():
        return True, ""
    return False, "evidence path does not exist: %s" % text


def rel_of(path, root):
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return path.name


def check_candidate(path, schema, root, current_fp, probes):
    fm, _body = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    rel = rel_of(path, root)
    problems = []
    if not fm:
        return ["%s: no frontmatter at all — an unlabelled row cannot be judged" % rel]

    for field in schema.get("frontmatter_required", []):
        if not fm.get(field):
            problems.append("%s: missing required frontmatter field %s" % (rel, field))

    required = schema.get("required", {})
    cue = str(fm.get("cue") or "").strip()
    no_entry = cue == NO_ENTRY

    if no_entry:
        lesson = str(fm.get("lesson") or "").strip()
        if lesson and lesson != NO_ENTRY:
            problems.append(
                "%s: cue is NO_ENTRY but a lesson is claimed — a row that says nothing "
                "applied cannot also teach something" % rel)
    else:
        for field in ("dimension", "cue", "lesson", "verdict"):
            if not fm.get(field):
                problems.append("%s: %s is required (NO_ENTRY is the only honest empty row)"
                                % (rel, field))
        for field, spec in required.items():
            if "enum" in spec and fm.get(field) and fm.get(field) not in spec["enum"]:
                problems.append("%s: %s %r is not one of %s"
                                % (rel, field, fm.get(field), spec["enum"]))

        confidence = fm.get("confidence")
        if confidence is not None:
            try:
                value = float(confidence)
            except (TypeError, ValueError):
                problems.append("%s: confidence %r is not a number" % (rel, confidence))
            else:
                if not 0.0 <= value <= 1.0:
                    problems.append("%s: confidence %s is outside 0..1" % (rel, value))
        elif not no_entry:
            problems.append("%s: confidence is required — an unweighted lesson will be "
                            "trusted exactly as much as a measured one" % rel)

        evidence = as_list(fm.get("evidence"))
        if not evidence:
            problems.append("%s: evidence is empty — a claim with nothing behind it" % rel)
        known_ids = set()
        for records in probes.values():
            for record in records:
                known_ids.add(str(record.get("id", "")))
                known_ids.add(Path(str(record.get("record", ""))).stem)
        for entry in evidence:
            ok, why = evidence_resolves(entry, root, known_ids)
            if not ok:
                problems.append("%s: %s" % (rel, why))

    verdict = str(fm.get("verdict") or "")
    dimension = str(fm.get("dimension") or "")
    needs_probe = verdict in PROBE_OUTCOMES or (dimension == "invariant" and verdict != PROPOSED)
    if needs_probe and not no_entry:
        if not fm.get("probe"):
            problems.append("%s: claims %s but declares no `probe:` command — a behaviour "
                            "claim with no execution behind it" % (rel, verdict or dimension))
        else:
            records = probes.get(str(fm.get("id") or path.stem), [])
            digest = hashlib.sha1(path.read_bytes()).hexdigest()[:16]
            wanted = PROBE_OUTCOMES.get(verdict)  # invariant + keep_base: any record will not do
            fresh = [r for r in records
                     if r.get("fingerprint_at") == current_fp
                     and r.get("fingerprint_after") == current_fp
                     and r.get("candidate_digest") == digest]
            if not records:
                problems.append("%s: no probe has ever been run for this id (shelf: %s)"
                                % (rel, "14_CANDIDATES/loop/probes/"))
            elif not fresh:
                measured = [r for r in records if r.get("candidate_digest") == digest]
                if measured:
                    problems.append(
                        "%s: the probe is stale — it measured state %s, the repo is now %s. "
                        "Re-run scripts/probe.py before promoting"
                        % (rel, measured[-1].get("fingerprint_at"), current_fp))
                else:
                    problems.append(
                        "%s: every probe on record measured a different row — the candidate "
                        "was edited after it was measured. Re-run scripts/probe.py" % rel)
            elif wanted:
                outcomes = {str(r.get("outcome")) for r in fresh}
                if not outcomes & set(wanted):
                    problems.append("%s: verdict %r needs a probe with outcome in %s, the fresh "
                                    "records say %s" % (rel, verdict, list(wanted), sorted(outcomes)))
    return problems


def shelf_candidates(root, directory):
    shelf = Path(directory) if Path(directory).is_absolute() else root / directory
    if not shelf.is_dir():
        return []
    out = []
    for path in sorted(shelf.rglob("*.md")):
        if "probes" in path.relative_to(shelf).as_posix().split("/"):
            continue  # probe records are the evidence, not candidates
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        if is_candidate(fm):
            out.append(path)
    return out


def append_event(shelf_dir, event):
    """Append one ledger line -- the loop writes `proposed`, a decision writes a disposition.

    Append-only, one json object per line, because the ledger is the shelf's memory: a
    reader has to be able to grep it, and rewriting it would let a decision be edited out.
    """
    shelf = Path(shelf_dir)
    shelf.mkdir(parents=True, exist_ok=True)
    with (shelf / "ledger.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def read_ledger(shelf_dir):
    """Ledger events in append order, plus the lines a reader could not parse."""
    path = Path(shelf_dir) / "ledger.jsonl"
    events, broken = [], []
    if not path.is_file():
        return events, broken
    text = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            broken.append("ledger.jsonl:%d is not JSON — the ledger is greppable or it is nothing"
                          % lineno)
    return events, broken


def ledger_state(events):
    """{id: {"proposed": n, "dispositions": [label, ...]}} in the order first seen."""
    state = {}
    for event in events:
        cid = str(event.get("id") or "")
        if not cid:
            continue
        row = state.setdefault(cid, {"proposed": 0, "dispositions": []})
        if event.get("event") == "proposed":
            row["proposed"] += 1
        if event.get("disposition"):
            row["dispositions"].append(str(event["disposition"]))
    return state


def ledger_problems(root, shelf_dir, targets):
    """Reconcile shelf with ledger: proposed == adopt + revise + drop + keep_base + open.

    A row that disappears without a disposition is a lost measurement, and a disposition
    for a row nobody proposed is a decision from nowhere. Both get counted here because a
    ratchet that cannot see its own gaps reports a stability it did not earn.
    """
    events, problems = read_ledger(shelf_dir)
    state = ledger_state(events)
    on_shelf = {}
    for path in targets:
        fm, _ = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        on_shelf[str(fm.get("id") or path.stem)] = rel_of(path, root)

    for cid, row in sorted(state.items()):
        if row["proposed"] > 1:
            problems.append("%s: proposed %d times — the same label was used for two things"
                            % (cid, row["proposed"]))
        elif not row["proposed"]:
            problems.append("%s: has a disposition but the ledger never proposed it" % cid)
        if len(set(row["dispositions"])) > 1:
            problems.append("%s: %d different dispositions for one row — a decision gets "
                            "superseded by a new row, not re-litigated"
                            % (cid, len(set(row["dispositions"]))))
        for label in row["dispositions"]:
            if label not in DISPOSITIONS:
                problems.append("%s: disposition %r is not one of %s"
                                % (cid, label, list(DISPOSITIONS)))
    for cid, rel in sorted(on_shelf.items()):
        if cid not in state:
            problems.append("%s: a candidate on the shelf the ledger never proposed (%s) — "
                            "write it to 14_CANDIDATES/loop/ledger.jsonl or delete the row"
                            % (cid, rel))
            continue
        labels = state[cid]["dispositions"]
        if labels and any(label in ("adopt", "drop") for label in labels):
            problems.append("%s: decided %s but still sits on the shelf (%s) — an adopted row "
                            "moves with promote.py and a dropped row leaves; only revise and "
                            "keep_base stay where they can be read"
                            % (cid, "/".join(labels), rel))
    open_ids = sorted(cid for cid, row in state.items()
                      if row["proposed"] and not row["dispositions"])
    for cid in open_ids:
        if cid not in on_shelf:
            problems.append("%s: the row left the shelf without a disposition — a vanished "
                            "candidate is a lost measurement, record adopt/revise/drop/keep_base"
                            % cid)
    decided = sorted(cid for cid, row in state.items() if row["dispositions"])
    counts = {label: sum(1 for cid in decided if label in state[cid]["dispositions"])
              for label in DISPOSITIONS}
    identity = {"proposed": sum(1 for row in state.values() if row["proposed"]),
                "decided": len(decided), "open": len(open_ids)}
    identity.update(counts)
    if identity["proposed"] != identity["decided"] + identity["open"]:
        problems.append("count identity broken: proposed=%d, decided=%d, open=%d "
                        "(proposed == adopt + revise + drop + keep_base + open)"
                        % (identity["proposed"], identity["decided"], identity["open"]))
    return problems, identity


def register(root, file_arg):
    """Enter a hand-authored row into the ledger.

    The loop is not the only author -- 15_SYSTEM/templates/loop-candidate-NOTE.md exists for
    a human or another agent writing down something they learned. A row nobody counted is a
    row the count identity cannot see, so registering it is part of writing it.
    """
    path = Path(file_arg)
    if not path.is_absolute():
        path = root / path
    if not path.is_file():
        print("REFUSED  no such row to register: %s" % file_arg)
        return 1
    fm, _body = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
    if not is_candidate(fm):
        print("REFUSED  %s is not a candidate row (no dimension/cue/lesson/verdict) — "
              "a report does not get counted" % rel_of(path, root))
        return 1
    cid = str(fm.get("id") or path.stem)
    events, _broken = read_ledger(path.parent)
    if events and ledger_state(events).get(cid, {}).get("proposed"):
        print("ALREADY  %s is in the ledger" % cid)
        return 0
    append_event(path.parent, {
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "id": cid, "event": "proposed", "priority": "hand",
        "dimension": str(fm.get("dimension") or ""), "cue": str(fm.get("cue") or "")})
    print("REGISTERED %s -> %s" % (cid, (path.parent / "ledger.jsonl").name))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--dir", default="14_CANDIDATES/loop", help="shelf to scan")
    parser.add_argument("--file", default=None, help="check one candidate instead of the shelf")
    parser.add_argument("--register", metavar="FILE", default=None,
                        help="enter a hand-authored row into the shelf ledger so it can be counted")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()

    root = Path(args.root) if args.root else find_root(Path(__file__))

    if args.register:
        return register(root, args.register)
    schema_path = root / "rules" / "candidate.schema.json"
    if not schema_path.is_file():
        print("INVALID  rules/candidate.schema.json is missing — the contract cannot be enforced")
        return 1
    schema = load_json(schema_path)
    probes = probe_index(root)
    current_fp = state_fingerprint(root)

    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = root / path
        targets = [path] if path.is_file() else []
        if not targets:
            print("INVALID  candidate file not found: %s" % args.file)
            return 1
    else:
        targets = shelf_candidates(root, args.dir)

    results = []
    for path in targets:
        results.append((path, check_candidate(path, schema, root, current_fp, probes)))

    bad = [(p, probs) for p, probs in results if probs]
    ledger_issues, identity = [], {}
    if not args.file:
        shelf_dir = Path(args.dir) if Path(args.dir).is_absolute() else root / args.dir
        ledger_issues, identity = ledger_problems(root, shelf_dir, targets)

    if args.as_json:
        print(json.dumps({
            "checked": len(targets), "invalid": len(bad), "fingerprint": current_fp,
            "ledger": identity, "ledger_problems": ledger_issues,
            "problems": [[rel_of(p, root), probs] for p, probs in bad],
        }, ensure_ascii=False, indent=1))
        return 1 if (bad or ledger_issues) else 0

    for path, probs in bad:
        for problem in probs:
            print("INVALID  %s" % problem)
    for problem in ledger_issues:
        print("INVALID  %s" % problem)
    if bad or ledger_issues:
        print("REFUSED: %d of %d shelf candidate(s) do not meet the contract "
              "(rules/candidate.schema.json)" % (len(bad), len(targets)))
        return 1
    print("OK — %d shelf candidate(s) meet the contract; %d proposed / %d decided / %d open; "
          "state %s." % (len(targets), identity.get("proposed", 0), identity.get("decided", 0),
                         identity.get("open", 0), current_fp))
    return 0


if __name__ == "__main__":
    sys.exit(main())
