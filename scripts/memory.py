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
      --confidence 0.9 --verdict helped [--source "chat 2026-10-27"] [--plane error] \
      [--supersedes mem-y] [--verified-at 2026-11-02] [--expires 2026-12-01]
  python scripts/memory.py --render                                # rebuild MEMORY.md
  python scripts/memory.py --check                                 # the gate (health runs it)
  python scripts/memory.py --list                                  # ids and cues, no prose
  python scripts/memory.py --contradictions                       # pairs that disagree, measured
  python scripts/memory.py --windows                # every dated claim and the state of its window
  python scripts/memory.py --migrate-planes [--write]             # type the rows that predate #25

Exit 0 = memory is trustworthy as written, 1 = a row or the index broke the contract.

A lesson may also say how long it is certain for (phase 44, Graphiti's bi-temporal edge minus
the LLM that would have to build it): `verified_at` is the day a person last re-checked the
evidence, `expires` is the last day the claim still counts as certain. The rule is one sentence:
**no `expires` = evergreen; `expires` in the past = stale.** A stale row is a named gate row
(`STALE <id>`), never a silent certainty and never a deletion -- the ledger is append-only, so the
gate refuses and `--recall` marks the row while a human re-checks it. An unreadable window (not a
`YYYY-MM-DD` day, verified in the future, closed before it opened) is `invalid` and refused too:
a broken window is not the same thing as no window.
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

# The plane vocabulary is not a second taxonomy: it is the eight names already declared in
# 15_SYSTEM/config/system.json -> memory_planes (issue #25). The one value this file adds is
# UNCLASSIFIED, the honest "the source and topics do not decide" that --migrate-planes states
# rather than guessing. plane_ids() reads the config so the door and the map cannot drift.
UNCLASSIFIED = "unclassified"


def plane_ids(root):
    """The memory planes a lesson may be typed by, straight from the plane map's config."""
    path = Path(root) / "15_SYSTEM" / "config" / "system.json"
    try:
        cfg = load_json(path)
    except (OSError, ValueError):
        return (UNCLASSIFIED,)
    planes = tuple(sorted((cfg.get("memory_planes") or {}).keys()))
    return planes + ((UNCLASSIFIED,) if UNCLASSIFIED not in planes else ())


# Ordered, deterministic keyword -> plane for --migrate-planes and the --add default. The first
# plane whose keyword appears in the folded source + topics wins; nothing matching states
# UNCLASSIFIED instead of guessing. Only planes the config actually declares are eligible, so
# the vocabulary has one source of truth.
PLANE_KEYWORDS = (
    ("decision", ("registry", "amendment", "supersed", "contract", "schema", "generator",
                  "plan door", "one-file")),
    ("agent", ("agent-run", "agent_run", "runtime", "backend", "engine", "superagi", "harness",
               "orchestrator", "mcp", "allowlist", "workflow")),
    ("conversation", ("source", "provenance", "import", "conversation", "recall", "learning")),
    ("error", ("encoding", "parsing", "frontmatter", "path", "validation", "gate", "fence",
               "zone", "fingerprint", "probe", "clone", "ci", "hygiene", "recovery", "keep_base",
               "keep-base", "refusal", "ux", "freshness", "loop", "ledger", "portability")),
    ("knowledge", ("docs", "measurement", "numbers", "honesty", "persian", "onboarding", "lint",
                   "host", "prose", "note", "convention", "canon", "verification")),
    ("repository", ("memory", "lesson", "evidence", "handoff", "vault", "promote")),
)


def derive_plane(source, topics, allowed):
    """The plane the row's own provenance states, or UNCLASSIFIED when it does not decide."""
    if isinstance(topics, str):
        topics = [item for item in topics.split(",")]
    text = ("%s %s" % (source or "", " ".join(str(t) for t in (topics or [])))).lower()
    for plane, keywords in PLANE_KEYWORDS:
        if plane not in allowed:
            continue
        if any(word in text for word in keywords):
            return plane
    return UNCLASSIFIED


# --- contradiction definition (issue #24) --------------------------------------------------
# Two ACTIVE lessons contradict when they describe the same situation and draw opposite
# verdicts from it. Concretely, and all four must hold on the folded text:
#   same plane + at least one shared topic + high cue-overlap + opposite verdict.
# cue-overlap is Jaccard (|intersection| / |union|) over the token sets of the two cues, using
# the repo's own tokens() (fold to lowercase, drop stopwords and short words) -- stdlib, no
# model, reproducible from a clone.
#
# OPPOSITE_VERDICTS is the only pair that is a true disagreement: one lesson measured that the
# change helped, the other that the same situation hurt. keep_base, proposed, confounded and
# no_observed_effect are not opposite to helped; treating them as such would flag agreement
# as conflict.
OPPOSITE_VERDICTS = (frozenset(("helped", "hurt")),)

# CONTRADICTION_JACCARD is measured on the shipped ledger, not guessed (325 active pairs):
#   - the single closest pair of active lessons that share a plane and a topic scores 0.31
#     (mem-gates-that-pass-locally-are-not-green / mem-gates-break-on-local-state) and it
#     AGREES -- a threshold under 0.31 would call two agreeing lessons a conflict;
#   - pairs of opposite verdict (helped vs hurt) on the shipped ledger: 0 at every threshold,
#     so the ledger holds no contradiction to rewrite -- the gate stays honest instead.
# 0.50 sits well above every agreeing pair yet below "identical situation" overlap, so the rule
# fires only on cues that describe the same thing in opposing terms, never on shared vocabulary.
CONTRADICTION_JACCARD = 0.50


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


# --- validity windows (issue: phase 44, "a claim a clone cannot re-check") -------------------
# Graphiti keeps two clocks on every edge: when it was discovered and when it stops being true.
# The LLM that extracts those edges is refused here (charter section 2), the window is free: two
# optional day fields on the row. The rule is deliberately boring and written down in
# rules/memory.schema.json and 02_WIKI/reference_maps/eight-memory-planes.md:
#
#   evergreen  no `expires` at all -- the row claims nothing dated, so nothing can go stale.
#              This is the default, and the shipped ledger is 27/27 evergreen (measured 2026-11-02
#              with `--windows`): no date was invented to make a number appear.
#   current    `expires` >= today (its last day is still a day it is certain).
#   stale      `expires` < today -- the row may still be true, but nobody holding a clone can
#              re-check it, so it is named as a gate row and marked in `--recall`. It is NEVER
#              deleted, rewritten or dropped from the index: a gate that edits the ledger to go
#              green has replaced one lie with another.
#   invalid    a window that cannot be read as a day, a `verified_at` in the future, or an
#              `expires` that closes before it opened. Refused, and never treated as evergreen:
#              a broken window is not the same thing as no window.
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
WINDOW_FIELDS = ("verified_at", "expires")
WINDOW_STATES = ("evergreen", "current", "stale", "invalid")


def parse_day(value):
    """A `YYYY-MM-DD` calendar day, or None. Windows are days because a window that opens on a
    microsecond is not something a person can re-check by hand."""
    text = str(value or "").strip()
    if not DAY_RE.match(text):
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def window_state(row, today=None):
    """The row's own state under the rule above, judged on the row's text and one date."""
    today = today or datetime.date.today()
    stated = {field: row.get(field) for field in WINDOW_FIELDS if row.get(field) not in (None, "")}
    if not stated:
        return "evergreen"
    parsed = {}
    for field, value in stated.items():
        day = parse_day(value)
        if day is None:
            return "invalid"
        parsed[field] = day
    if parsed.get("verified_at") and parsed["verified_at"] > today:
        return "invalid"
    if "verified_at" in parsed and "expires" in parsed and parsed["expires"] < parsed["verified_at"]:
        return "invalid"
    if "expires" not in parsed:
        return "evergreen"          # verified but with no stated end: still a claim of no window
    return "current" if parsed["expires"] >= today else "stale"


def window_field_problems(row, today=None):
    """The format contract for the two window fields, as refusal lines."""
    if window_state(row, today) != "invalid":
        return []
    cid = str(row.get("id") or "(no id)")
    stated = ", ".join("%s=%r" % (field, row.get(field)) for field in WINDOW_FIELDS
                       if row.get(field) not in (None, ""))
    return ["%s: validity window (%s) is not a legal window — each field must be a YYYY-MM-DD "
            "day, verified_at may not name a day that has not happened yet, and expires may not "
            "close before it opens. An unreadable window is refused, never treated as evergreen"
            % (cid, stated)]


def stale_rows(rows, today=None, include_retired=False):
    """Every row whose window has passed, with the number behind the judgement.

    Active rows only unless `include_retired` is set: a superseded row is not presented as
    certainty anywhere, so the gate reports it instead of refusing the house over it.
    """
    today = today or datetime.date.today()
    pool = rows if include_retired else active(rows)
    out = []
    for row in pool:
        if window_state(row, today) != "stale":
            continue
        expired = parse_day(row.get("expires"))
        out.append({"id": str(row.get("id")), "expires": str(row.get("expires")),
                    "days_past": (today - expired).days,
                    "retired": row not in active(rows)})
    return out


def window_problems(rows, today=None):
    """Refusal lines for stale claims: named rows, never edits."""
    return ["STALE %s: expires %s, %d day(s) past its window — this row says nothing that a "
            "reader holding only this clone can re-check, so it is no longer a certainty. "
            "Re-check its evidence and file the row that replaces it (--add --id ... "
            "--supersedes %s), or give it a new --expires through the same door; the gate names "
            "the row, it does not delete or rewrite it" % (row["id"], row["expires"],
                                                           row["days_past"], row["id"])
            for row in stale_rows(rows, today)]


def recall_mark(row, today=None):
    """The window marker `--recall` and the MCP door put on a stale answer.

    The row is still shown -- it is the reason the row exists -- but never as a certainty: the
    reader who asked the memory a question has to see that the answer's window has passed.
    """
    today = today or datetime.date.today()
    if window_state(row, today) != "stale":
        return ""
    expired = parse_day(row.get("expires"))
    if expired is None:
        return ""
    return "  [STALE: expires %s, %d day(s) past — re-check before applying]" % (
        row.get("expires"), (today - expired).days)


def window_counts(rows, today=None):
    """{state: n} over every row, for the report and the OK line."""
    counts = dict((state, 0) for state in WINDOW_STATES)
    for row in rows:
        counts[window_state(row, today)] += 1
    return counts


def report_windows(root):
    """Measure, then judge: the state of every row's window, and the totals on one line."""
    today = datetime.date.today()
    rows, problems = read_lessons(root)
    counts = window_counts(rows, today)
    print("window rule (phase 44): no expires = evergreen | expires >= today = current | "
          "expires < today = stale | unreadable = invalid  (today: %s)" % today.isoformat())
    for row in rows:
        state = window_state(row, today)
        if state == "evergreen" and not row.get("verified_at"):
            continue                      # the shipped default is not a finding, it is the rule
        print("  %-44s %-10s verified_at=%-10s expires=%-10s"
              % (str(row.get("id")), state, row.get("verified_at") or "-",
                 row.get("expires") or "-"))
    print("%d row(s): %d evergreen, %d current, %d stale, %d invalid"
          % (len(rows), counts["evergreen"], counts["current"], counts["stale"],
             counts["invalid"]))
    retired = [row for row in stale_rows(rows, today, include_retired=True) if row["retired"]]
    for row in retired:
        print("  (retired) %s expired %s — kept for the record, not refused" % (row["id"],
                                                                                row["expires"]))
    for problem in problems:
        print("INVALID  %s" % problem)
    for row in rows:
        for problem in window_field_problems(row, today):
            print("INVALID  %s" % problem)
    for problem in window_problems(rows, today):
        print(problem)
    refusals = ([p for row in rows for p in window_field_problems(row, today)] +
                window_problems(rows, today))
    if refusals or problems:
        print("REFUSED: %d lesson(s) carry a window that is stale or unreadable" % len(refusals))
        return 1
    print("OK — every dated claim in the ledger is inside its window; %d evergreen row(s) state "
          "no window at all" % counts["evergreen"])
    return 0


def check_row(row, root, seen, allowed=None):
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
    # plane (issue #25): a lesson must say which memory plane it belongs to, or state that the
    # evidence does not decide. An unlabelled lesson is why the error plane's claim was honest
    # but weak -- a run failure and a design choice looked identical until you read the prose.
    if allowed is None:
        allowed = plane_ids(root)
    plane = str(row.get("plane") or "")
    if not plane:
        problems.append("%s: plane is empty — error memory that is not typed by plane cannot be "
                        "told apart by kind (issue #25); assign one with --plane or run "
                        "python scripts/memory.py --migrate-planes --write" % cid)
    elif plane not in allowed:
        problems.append("%s: plane %r is not one of the mapped planes %s"
                        % (cid, plane, list(allowed)))
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
    # validity window (phase 44): the format is a row contract, so it is judged here; whether the
    # window has *passed* is a ledger-level verdict, named by check() through window_problems.
    problems += window_field_problems(row)
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
    allowed = plane_ids(root)
    seen = set()
    for row in rows:
        problems += check_row(row, root, seen, allowed)
    problems += check_index(root, rows)
    problems += contradiction_problems(rows)
    problems += window_problems(rows)
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
    # A stale row keeps its place in the active table -- deleting it from the rendering would be
    # the same silence as deleting it from the ledger -- but it is named here as well, so a reader
    # of the human plane sees the window before the claim. No stale row, no section: the shipped
    # rendering is byte-identical to what it was before the window rule existed.
    stale = stale_rows(rows)
    if stale:
        lines += ["", "## Out of date (window passed; the row is kept, the certainty is not)", ""]
        for row in stale:
            lines.append("- `%s` expired `%s` (%d day(s) ago) — re-check its evidence before "
                         "applying it, or supersede it" % (row["id"], row["expires"],
                                                           row["days_past"]))
    lines += ["", "## How a lesson gets here", "",
              "A lesson is a candidate row that was measured: see",
              "`rules/candidate.schema.json` and `skills/loop/SKILL.md`. The verdict column is",
              "what the measurement said, not what the author hoped.", ""]
    index_path(root).write_text("\n".join(lines), encoding="utf-8")
    return index_path(root)


def tokens(text):
    return {word for word in re.findall(r"[a-z0-9]+", str(text).lower()) if len(word) > 2} - STOPWORDS


def cue_overlap(a, b):
    """Jaccard over the token sets of two cues -- the only similarity a stdlib clone can prove."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def is_opposite(v1, v2):
    return frozenset((str(v1 or ""), str(v2 or ""))) in OPPOSITE_VERDICTS


def find_contradictions(rows):
    """Every same-plane, shared-topic, high-overlap, opposite-verdict pair -- with its numbers.

    Scanned over ALL rows, not only the active ones, so a resolved pair (one lesson superseded
    the other) can be reported as resolved instead of vanishing. `status` is what the gate acts
    on: `active` (both lessons live -> refuse), `resolved` (one retires the other, or neither
    is live -> report, never refuse).
    """
    live = {str(row.get("id")) for row in active(rows)}
    out = []
    for i in range(len(rows)):
        for j in range(i + 1, len(rows)):
            x, y = rows[i], rows[j]
            xid, yid = str(x.get("id")), str(y.get("id"))
            if not xid or not yid or xid == yid:
                continue
            same_plane = str(x.get("plane") or "") == str(y.get("plane") or "") != ""
            topics_x = {str(t) for t in (x.get("topics") or [])}
            topics_y = {str(t) for t in (y.get("topics") or [])}
            shared = sorted(topics_x & topics_y)
            score = cue_overlap(x.get("cue", ""), y.get("cue", ""))
            if not (same_plane and shared and score >= CONTRADICTION_JACCARD
                    and is_opposite(x.get("verdict"), y.get("verdict"))):
                continue
            retires = {str(x.get("supersedes") or ""), str(y.get("supersedes") or "")}
            if xid in retires or yid in retires or xid not in live or yid not in live:
                status = "resolved"
            else:
                status = "active"
            out.append({"a": xid, "b": yid, "plane": str(x.get("plane")),
                        "topics": shared, "overlap": round(score, 3),
                        "verdicts": [str(x.get("verdict")), str(y.get("verdict"))],
                        "status": status})
    return out


def contradiction_problems(rows):
    """Refusal strings for the pairs the gate must refuse -- active conflicts only."""
    return ["CONTRADICTION %s and %s: same plane '%s', share topic '%s', cue-overlap %.2f "
            ">= %.2f, opposite verdicts %s vs %s — two active lessons disagree about the same "
            "situation. Retire one with --supersedes or correct the evidence; the gate reports "
            "the conflict, it does not rewrite the ledger" % (
                pair["a"], pair["b"], pair["plane"], ", ".join(pair["topics"]), pair["overlap"],
                CONTRADICTION_JACCARD, pair["verdicts"][0], pair["verdicts"][1])
            for pair in find_contradictions(rows) if pair["status"] == "active"]


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
    # retirement is validated at the door too (issue #17): a row pointing at an id nobody
    # holds retires nothing, and the old behaviour wrote it and left `--check` to complain
    # about a row that was already in the ledger and already rendered into MEMORY.md.
    if args.supersedes:
        if args.supersedes == cid:
            print("REFUSED  %s cannot supersede itself — a row that retires itself retires nothing"
                  % cid)
            return 1
        if args.supersedes not in existing:
            print("REFUSED  --supersedes %s names no row this ledger holds (it holds: %s) — "
                  "retirement must point at a lesson that exists, and a refusal after the "
                  "write is a cleanup task, not a gate"
                  % (args.supersedes, ", ".join(sorted(existing)) or "nothing"))
            return 1
    if args.verdict not in VERDICTS:
        print("REFUSED  --verdict %r is not one of %s — a lesson needs a verdict the gate "
              "recognises" % (args.verdict, list(VERDICTS)))
        return 1
    # plane, refused at the door beside the verdict: an unlabelled lesson cannot be typed by
    # kind, and a refusal after the write would only be a cleanup task (issue #25). When the
    # author does not pass --plane, the row's --source / topics decide it (that is the whole
    # point of the field); nothing matching states unclassified rather than inventing a plane.
    allowed = plane_ids(root)
    if args.plane is not None:
        if args.plane == "":
            print("REFUSED  --plane needs a value — a blank plane types the lesson nowhere")
            return 1
        if args.plane not in allowed:
            print("REFUSED  --plane %r is not one of the mapped planes %s — the plane vocabulary "
                  "lives in 15_SYSTEM/config/system.json -> memory_planes, there is no second "
                  "taxonomy here" % (args.plane, list(allowed)))
            return 1
        plane = args.plane
    else:
        plane = derive_plane(args.source, args.topics, allowed)
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
    # the window, refused at the door like the plane and the verdict (issue #17's lesson): a row
    # whose window cannot be read must never reach the ledger, and a row whose author says nothing
    # gets no field at all -- absent means evergreen, so inventing a date would be the lie.
    verified_at = str(args.verified_at or "").strip()
    expires = str(args.expires or "").strip()
    for problem in window_field_problems({"id": cid, "verified_at": verified_at,
                                          "expires": expires}):
        print("REFUSED  %s" % problem)
        return 1
    row = {
        "id": cid,
        "date": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cue": args.cue,
        "lesson": args.lesson,
        "evidence": evidence,
        "confidence": confidence,
        "verdict": args.verdict,
        "plane": plane,
        "topics": [item.strip() for item in (args.topics or "").split(",") if item.strip()],
        "source": args.source or "",
    }
    if verified_at:
        row["verified_at"] = verified_at
    if expires:
        row["expires"] = expires
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
    print("ADDED %s [plane: %s, window: %s] -> %s (+ %s)"
          % (cid, plane, "expires %s" % expires if expires else "evergreen (none stated)",
             path.relative_to(root).as_posix(), rendered.relative_to(root).as_posix()))
    return 0


def migrate_planes(root, write):
    """Type the rows that predate issue #25, deterministically from their own source/topics.

    Additive and idempotent: a row that already carries a plane is kept untouched (rewriting a
    plane would be rewriting history), a row that does not gets the plane its provenance states
    or the stated UNCLASSIFIED where it does not decide. It prints what it would do and only
    touches the ledger with an explicit --write; a broken ledger is refused, never migrated over.
    """
    path = catalog_path(root)
    if not path.is_file():
        print("REFUSED  no lessons.jsonl here to migrate")
        return 1
    rows, problems = read_lessons(root)
    if problems:
        for problem in problems:
            print("INVALID  %s" % problem)
        print("REFUSED: the ledger is not readable as JSON — nothing is migrated over a "
              "corrupted row; fix the line first")
        return 1
    allowed = plane_ids(root)
    plan = []
    for row in rows:
        current = str(row.get("plane") or "")
        if current:
            plan.append((str(row.get("id")), current, "kept"))
        else:
            plane = derive_plane(row.get("source", ""), row.get("topics") or [], allowed)
            plan.append((str(row.get("id")), plane, "assign"))
    assigned = [p for p in plan if p[2] == "assign"]
    undecided = [p for p in assigned if p[1] == UNCLASSIFIED]
    print("plane vocabulary (from 15_SYSTEM/config/system.json -> memory_planes): %s"
          % ", ".join(allowed))
    for cid, plane, kind in plan:
        print("  %-42s %-14s %s" % (cid, plane, kind))
    print("%d row(s): %d already typed, %d would gain a plane, %d the evidence does not "
          "decide (stated as '%s', which the gate tolerates)"
          % (len(plan), len(plan) - len(assigned), len(assigned), len(undecided), UNCLASSIFIED))
    if not write:
        print("DRY RUN — nothing was written; re-run with --write to apply the %d assignment(s)"
              % len(assigned))
        return 0
    if not assigned:
        print("NO CHANGE — every row is already typed by plane")
        return 0
    new_rows = []
    decisions = {cid: plane for cid, plane, kind in plan if kind == "assign"}
    for row in rows:
        if str(row.get("id")) in decisions:
            row = dict(row)
            row["plane"] = decisions[str(row.get("id"))]
        new_rows.append(row)
    with path.open("w", encoding="utf-8") as handle:
        for row in new_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    print("MIGRATED %d row(s) -> plane added in %s (MEMORY.md is untouched: the field is typed "
          "in the ledger, not the table)" % (len(assigned), path.relative_to(root).as_posix()))
    return 0


def report_contradictions(root):
    """Print every measured conflict pair with the numbers behind the judgement."""
    rows, problems = read_lessons(root)
    pairs = find_contradictions(rows)
    active = [pair for pair in pairs if pair["status"] == "active"]
    resolved = [pair for pair in pairs if pair["status"] == "resolved"]
    print("contradiction rule (issue #24): same plane + shared topic + cue-overlap "
          "Jaccard >= %.2f + opposite verdict (helped vs hurt)" % CONTRADICTION_JACCARD)
    if not pairs:
        print("NONE — no pair of lessons meets all four conditions on this ledger.")
    for pair in pairs:
        print("  [%s] %s <-> %s | plane=%s topics=%s overlap=%.3f verdicts=%s" % (
            pair["status"], pair["a"], pair["b"], pair["plane"], ",".join(pair["topics"]),
            pair["overlap"], "/".join(pair["verdicts"])))
    if problems:
        for problem in problems:
            print("INVALID  %s" % problem)
    if active:
        print("REFUSED: %d active contradiction(s) (resolved pairs reported, not refused)"
              % len(active))
        return 1
    print("OK — %d active conflict(s), %d resolved pair(s) shown for the record."
          % (len(active), len(resolved)))
    return 1 if problems else 0


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
    parser.add_argument("--plane", default=None,
                        help="memory plane (one of system.json -> memory_planes, or "
                             "'unclassified'); when omitted the row's --source/topics decide it")
    parser.add_argument("--supersedes", default=None)
    parser.add_argument("--verified-at", default="", dest="verified_at", metavar="YYYY-MM-DD",
                        help="the day a person last re-checked this row's evidence (phase 44); "
                             "omit it entirely when nobody re-checked it -- a blank window is a "
                             "refusal, an absent one is evergreen")
    parser.add_argument("--expires", default="", metavar="YYYY-MM-DD",
                        help="the last day this claim counts as certain (phase 44); when it is "
                             "past, --check names the row STALE and --recall marks it. Omit it "
                             "for a claim that states no window.")
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--contradictions", action="store_true",
                        help="report measured conflict pairs (same plane+topic, high cue "
                             "overlap, opposite verdict); refuse on an active pair")
    parser.add_argument("--windows", action="store_true",
                        help="report the validity window of every dated claim (phase 44); "
                             "refuse when one is stale or unreadable")
    parser.add_argument("--migrate-planes", action="store_true", dest="migrate_planes",
                        help="type the rows that predate the plane field, deterministically "
                             "from source/topics; prints what it would do")
    parser.add_argument("--write", action="store_true",
                        help="with --migrate-planes: actually write the ledger (else dry run)")
    parser.add_argument("--list", action="store_true", dest="as_list")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    root = Path(args.root) if args.root else find_root(Path(__file__))

    if args.migrate_planes:
        return migrate_planes(root, args.write)

    if args.contradictions:
        return report_contradictions(root)

    if args.windows:
        return report_windows(root)

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
            print("[%s | %s | conf %s] %s%s" % (row.get("id"), row.get("verdict"),
                                                row.get("confidence"), row.get("lesson"),
                                                recall_mark(row)))
            print("    when: %s" % row.get("cue"))
            print("    evidence: %s" % ", ".join(row.get("evidence") or []))
        return 0

    rows, problems = check(root)
    counts = window_counts(rows)
    if args.as_list:
        for row in active(rows):
            print("%s\t%s" % (row.get("id"), row.get("cue")))
    if args.as_json:
        print(json.dumps({"lessons": len(rows), "active": len(active(rows)),
                          "evergreen": counts["evergreen"], "current": counts["current"],
                          "stale": counts["stale"], "invalid_window": counts["invalid"],
                          "problems": problems}, ensure_ascii=False, indent=1))
        return 1 if problems else 0
    if args.check or not args.as_list:
        if problems:
            for problem in problems:
                print("INVALID  %s" % problem)
            print("REFUSED: the repo memory does not meet its own contract "
                  "(rules/memory.schema.json)")
            return 1
        print("OK — %d lesson(s), %d active, %d carrying a stated window; "
              "MEMORY.md matches the ledger."
              % (len(rows), len(active(rows)), counts["current"] + counts["stale"]))
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
