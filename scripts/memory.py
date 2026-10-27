#!/usr/bin/env python
"""The repo's own memory — lessons it learned, with the evidence that taught them.

Issue #7 asked for something that keeps getting smarter and remembers why. A note named
"Mistakes.md" cannot do that: prose is not retrievable, an unweighted lesson is trusted as
much as a measured one, and a pointer to a file that no longer exists is a story, not memory.
So memory here is a ledger plus a rendered index, judged by a gate:

  14_CANDIDATES/... and docs/  say what happened. 15_SYSTEM/memory/lessons.jsonl says what
  to do next time. This script keeps the two in the same shape.

The file layout follows the house rules: the catalog is machine plane (15_SYSTEM/memory/),
the human-readable rendering is MEMORY.md at the root, next to the other root documents.

Usage:
  python scripts/memory.py --recall "probe fingerprint stale"      # retrieve, ordered
  python scripts/memory.py --add --id mem-x --cue ... --lesson ... --evidence a.md,b.md \
      --confidence 0.9 --verdict helped [--source "chat 2026-10-27"] [--supersedes mem-y]
  python scripts/memory.py --render                                # rebuild MEMORY.md
  python scripts/memory.py --check                                 # the gate (health runs it)
  python scripts/memory.py --list                                  # ids and cues, no prose

Exit 0 = memory is trustworthy as written, 1 = a row or the index broke the contract.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import candidate_check
from common import find_root, load_json, run_utf8

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

REQUIRED = ("id", "date", "cue", "lesson", "evidence", "confidence", "verdict")
VERDICTS = ("proposed", "helped", "hurt", "no_observed_effect", "confounded", "keep_base")
STOPWORDS = set("the a an and or of to in on for with that this it is are was be as at by "
                "from not so do does did can could would should has have had i you we they".split())


def catalog_path(root):
    return Path(root) / "15_SYSTEM" / "memory" / "lessons.jsonl"


def index_path(root):
    return Path(root) / "MEMORY.md"


def read_lessons(root):
    """(rows, problems) -- an unparseable line is a problem, never a silent skip."""
    path = catalog_path(root)
    rows, problems = [], []
    if not path.is_file():
        return rows, ["%s is missing — the repo has no memory file" %
                      path.relative_to(root).as_posix()]
    for lineno, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            problems.append("lessons.jsonl:%d is not JSON — append-only, but still machine-readable"
                            % lineno)
    return rows, problems


def active(rows):
    """Rows nobody has superseded: a superseded lesson stays in the ledger for the record."""
    superseded = {str(row.get("supersedes")) for row in rows if row.get("supersedes")}
    return [row for row in rows if str(row.get("id")) not in superseded]


def check_row(row, root, seen):
    problems = []
    cid = str(row.get("id") or "")
    if not cid:
        return ["lessons.jsonl: a row with no id cannot be cited, superseded or trusted"]
    if cid in seen:
        problems.append("%s: id appears twice — one lesson, one label" % cid)
    seen.add(cid)
    for field in REQUIRED:
        if row.get(field) in (None, "", []):
            problems.append("%s: %s is empty — a row missing a field is a slogan" % (cid, field))
    verdict = str(row.get("verdict") or "")
    if verdict and verdict not in VERDICTS:
        problems.append("%s: verdict %r is not one of %s" % (cid, verdict, list(VERDICTS)))
    try:
        confidence = float(row.get("confidence"))
    except (TypeError, ValueError):
        if row.get("confidence") not in (None, ""):
            problems.append("%s: confidence %r is not a number" % (cid, row.get("confidence")))
    else:
        if not 0.0 <= confidence <= 1.0:
            problems.append("%s: confidence %s is outside 0..1" % (cid, confidence))
    date = str(row.get("date") or "")
    if date and not re.match(r"^\d{4}-\d{2}-\d{2}T", date):
        problems.append("%s: date %r is not ISO 8601 — memory that cannot be ordered is a list"
                        % (cid, date))
    evidence = row.get("evidence")
    evidence = [evidence] if isinstance(evidence, str) else list(evidence or [])
    for entry in evidence:
        ok, why = candidate_check.evidence_resolves(entry, root, set())
        if not ok:
            problems.append("%s: %s" % (cid, why))
    superseded_by = row.get("supersedes")
    if superseded_by and str(superseded_by) == cid:
        problems.append("%s: supersedes itself" % cid)
    return problems


def check_index(root, rows):
    """MEMORY.md is a rendering, so it has to agree with what it renders -- both directions."""
    problems = []
    path = index_path(root)
    if not path.is_file():
        return ["MEMORY.md is missing — run python scripts/memory.py --render"]
    text = path.read_text(encoding="utf-8", errors="replace")
    for row in active(rows):
        cid = str(row.get("id"))
        if cid and ("`%s`" % cid) not in text:
            problems.append("%s: an active lesson that the human-readable index does not show "
                            "-- nobody will apply a memory they cannot read" % cid)
    for cid in re.findall(r"`(mem-[a-z0-9][a-z0-9-]*)`", text):
        if cid not in {str(row.get("id")) for row in rows}:
            problems.append("%s: MEMORY.md cites a lesson that is not in the ledger — a "
                            "reference you cannot open is how a fabricated memory starts" % cid)
    for row in rows:
        cid = str(row.get("id") or "")
        if row.get("supersedes"):
            if str(row["supersedes"]) not in {str(item.get("id")) for item in rows}:
                problems.append("%s: supersedes %s, which the ledger never held" % (cid, row["supersedes"]))
    return problems


def check(root):
    rows, problems = read_lessons(root)
    seen = set()
    for row in rows:
        problems += check_row(row, root, seen)
    problems += check_index(root, rows)
    return rows, problems


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")[:48]


def render(root, rows):
    """MEMORY.md from the ledger -- one place decides the shape, so the two cannot drift."""
    today = datetime.date.today().isoformat()
    lines = [
        "---",
        "id: mem-index",
        "type: index",
        "title: Repo memory",
        "status: raw",
        "owner: agent",
        "topics: [memory, lessons, evidence]",
        "created: %s" % today,
        "updated: %s" % today,
        "generated_by: scripts/memory.py --render",
        "---",
        "",
        "# MEMORY — what this repo learned, and what it is allowed to claim",
        "",
        "**This file is generated.** The catalog is `15_SYSTEM/memory/lessons.jsonl`; edit that",
        "with `python scripts/memory.py --add ...` and re-render. A hand-edit here is a claim",
        "the ledger cannot back, and `scripts/memory.py --check` (which `health.py` runs) says so.",
        "",
        "Read it at the start of a session: `python scripts/memory.py --recall \"<what you hit>\"`.",
        "An empty answer is legal and honest -- that is `NO_ENTRY`, and it is data, not a gap.",
        "",
        "| id | cue | lesson | verdict | conf | evidence |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in sorted(active(rows), key=lambda item: (-float(item.get("confidence") or 0),
                                                      str(item.get("id")))):
        evidence = row.get("evidence") or []
        evidence = [evidence] if isinstance(evidence, str) else list(evidence)
        lines.append("| `%s` | %s | %s | `%s` | %s | %s |" % (
            row.get("id"), row.get("cue"), row.get("lesson"), row.get("verdict"),
            row.get("confidence"),
            ", ".join("`%s`" % item for item in evidence)))
    retired = [row for row in rows if str(row.get("id")) not in
               {str(item.get("id")) for item in active(rows)}]
    if retired:
        lines += ["", "## Retired (superseded, kept for the record)", ""]
        for row in retired:
            lines.append("- `%s` superseded by `%s` — %s" % (row.get("id"), row.get("supersedes"),
                                                             row.get("cue")))
    lines += ["", "## How a lesson gets here", "",
              "A lesson is a candidate row that was measured: see",
              "`rules/candidate.schema.json` and `skills/loop/SKILL.md`. The verdict column is",
              "what the measurement said, not what the author hoped.", ""]
    index_path(root).write_text("\n".join(lines), encoding="utf-8")
    return index_path(root)


def tokens(text):
    return {word for word in re.findall(r"[a-z0-9]+", str(text).lower()) if len(word) > 2} - STOPWORDS


def recall(root, query, rows=None, limit=5):
    """Word-overlap retrieval, ordered by hits then confidence -- no model, no network."""
    rows = rows if rows is not None else read_lessons(root)[0]
    wanted = tokens(query)
    scored = []
    for row in active(rows):
        hay = tokens("%s %s %s" % (row.get("cue"), row.get("lesson"), row.get("topics") or []))
        hits = len(wanted & hay) if wanted else 1
        if hits:
            scored.append((hits, float(row.get("confidence") or 0), row))
    scored.sort(key=lambda item: (-item[0], -item[1]))
    return [row for _hits, _conf, row in scored[:limit]]


def add(root, args):
    path = catalog_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows, _problems = read_lessons(root)
    existing = {str(row.get("id")) for row in rows}
    cid = args.id or "mem-%s" % slug(args.cue)
    if cid in existing:
        print("REFUSED  %s is already in the ledger — supersede it (--supersedes) instead of "
              "writing the same label twice" % cid)
        return 1
    if args.verdict not in VERDICTS:
        print("REFUSED  --verdict %r is not one of %s — a lesson needs a verdict the gate "
              "recognises" % (args.verdict, list(VERDICTS)))
        return 1
    try:
        confidence = float(args.confidence)
    except (TypeError, ValueError):
        print("REFUSED  --confidence %r is not a number — a feeling is not a measurement"
              % args.confidence)
        return 1
    if not 0.0 <= confidence <= 1.0:
        print("REFUSED  --confidence %s is outside 0..1" % confidence)
        return 1
    evidence = [item.strip() for item in (args.evidence or "").split(",") if item.strip()]
    row = {
        "id": cid,
        "date": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cue": args.cue,
        "lesson": args.lesson,
        "evidence": evidence,
        "confidence": confidence,
        "verdict": args.verdict,
        "topics": [item.strip() for item in (args.topics or "").split(",") if item.strip()],
        "source": args.source or "",
    }
    if args.supersedes:
        row["supersedes"] = args.supersedes
    if not evidence:
        print("REFUSED  a lesson with no evidence is a preference — cite a path, a URL or a probe id")
        return 1
    for entry in evidence:
        ok, why = candidate_check.evidence_resolves(entry, root, set())
        if not ok:
            print("REFUSED  %s" % why)
            return 1
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    rendered = render(root, read_lessons(root)[0])
    print("ADDED %s -> %s (+ %s)" % (cid, path.relative_to(root).as_posix(),
                                     rendered.relative_to(root).as_posix()))
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--recall", default=None, metavar="QUERY")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--add", action="store_true")
    parser.add_argument("--id", default=None)
    parser.add_argument("--cue", default=None)
    parser.add_argument("--lesson", default=None)
    parser.add_argument("--evidence", default=None, help="comma-separated paths or URLs")
    parser.add_argument("--confidence", default="0.0")
    parser.add_argument("--verdict", default="keep_base")
    parser.add_argument("--topics", default="")
    parser.add_argument("--source", default="")
    parser.add_argument("--supersedes", default=None)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--list", action="store_true", dest="as_list")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))

    if args.add:
        for field in ("cue", "lesson", "evidence"):
            if not getattr(args, field):
                print("REFUSED  --add needs --%s" % field)
                return 1
        return add(root, args)

    if args.render:
        rows, _problems = read_lessons(root)
        path = render(root, rows)
        print("RENDERED %s from %d lesson(s)" % (path.relative_to(root).as_posix(), len(rows)))
        return 0

    if args.recall is not None:
        rows = read_lessons(root)[0]
        found = recall(root, args.recall, rows, args.limit)
        if args.as_json:
            print(json.dumps(found, ensure_ascii=False, indent=1))
            return 0
        if not found:
            print("NO_ENTRY — nothing in memory matched %r. Say so and move on; inventing a "
                  "lesson is how the memory starts lying." % args.recall)
            return 0
        for row in found:
            print("[%s | %s | conf %s] %s" % (row.get("id"), row.get("verdict"),
                                              row.get("confidence"), row.get("lesson")))
            print("    when: %s" % row.get("cue"))
            print("    evidence: %s" % ", ".join(row.get("evidence") or []))
        return 0

    rows, problems = check(root)
    if args.as_list:
        for row in active(rows):
            print("%s\t%s" % (row.get("id"), row.get("cue")))
    if args.as_json:
        print(json.dumps({"lessons": len(rows), "active": len(active(rows)),
                          "problems": problems}, ensure_ascii=False, indent=1))
        return 1 if problems else 0
    if args.check or not args.as_list:
        if problems:
            for problem in problems:
                print("INVALID  %s" % problem)
            print("REFUSED: the repo memory does not meet its own contract "
                  "(rules/memory.schema.json)")
            return 1
        print("OK — %d lesson(s), %d active; MEMORY.md matches the ledger."
              % (len(rows), len(active(rows))))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
