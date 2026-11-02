#!/usr/bin/env python
"""The goldfish review gate — it judges the artifact, never the claim about it.

A review that "happened" inside the same context that drafted the document is not a goldfish
review, and a report that says a round was clean is only evidence that somebody typed the word
*clean*. So this gate reads the artifact and re-derives the verdict from it:

  (a) the stages it claims are recorded, every stage has a persona in this clone, and every
      recorded stage has at least one reviewer row — a pass nobody dispatched is a pass nobody ran;
  (b) every reviewer row carries a status of `run` / `failed` / `not_run`; a reviewer recorded
      as `run` must have returned a report the clone can open (a reviewer that returns no
      report did not review — it is never counted as a reviewer with zero findings), and no
      round may claim clean while any reviewer of that round is not `run`;
  (c) every Blocker and Major is settled / contested / escalated / declined **with a reason**,
      and a contested one must cite a file (optionally `file:symbol`) that really holds it;
  (d) every file the report cites exists in this clone and is not behind the documented git
      boundary, so the evidence survives a `git clone`;
  (e) the document under review really contains the implementation-plan header the range-split
      rule says it contains, and the line ranges in the Target table still land inside it.

The personae are data, not prose: `11_CONTROL/reviewers/<name>.md` declares each reviewer's
stage, range, audit vectors and bounded reading list, and carries the three universal
mandates (`strict-read-only`, `goldfish-isolation`, `no-chitchat`). The roster of a report is
checked against those files, so a report can neither invent a reviewer nor quietly drop one.

Usage:
  python scripts/goldfish_check.py --report <goldfish_review_report.md> [--root path]
  python scripts/goldfish_check.py --drift <drift_report.md> [--root path]
  python scripts/goldfish_check.py --personas [--root path]
  python scripts/goldfish_check.py                 # the gate: personae + every review
                                                   # and drift report this clone contains
  python scripts/goldfish_check.py --self-test     # prove every refusal above actually fires

Exit 0 = the artifact is what it says it is. Exit 1 = refused. Exit 2 = the artifact could not be
read as an artifact at all — no file, or a file with no frontmatter block; a gate that never
opened the thing does not get to call it clean.
"""
import argparse
import re
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import clone_readable, find_root, load_json, parse_frontmatter

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except AttributeError:
    pass

REVIEWERS_DIR = "11_CONTROL/reviewers"
SCOUT_LIMIT = 15            # EGM's bootstrap safety gate: past this the scout reports, not rolls up

# the five stages of a review loop, in dispatch order; `bootstrap` and `drift` belong to the
# scout, never to a round
STAGES = ("zoom_out", "comprehension", "critic", "intermediate_zoom_out",
           "implementation_readiness")
SCOUT_STAGES = ("bootstrap", "drift")
REQUIRED_STAGES = ("zoom_out", "comprehension", "critic", "implementation_readiness")
RANGES = ("feature", "implementation", "document")
CONTEXTS = ("fresh", "shared")
REVIEWER_STATUSES = ("run", "failed", "not_run")
FINDING_STATUSES = ("open", "settled", "contested", "escalated", "declined")
SETTLED = ("settled", "contested", "escalated", "declined")
CATEGORIES = ("", "-", "contest", "escalate", "propose_fix", "decline")
VERDICTS = ("converged", "capped", "aborted", "in_progress")
DRIFT_VERDICTS = ("clean", "drifted")
ROUNDS_CAP = 5
MANDATES = ("strict-read-only", "goldfish-isolation", "no-chitchat")
SPAWN_MODES = ("direct", "synthesizer")

# the split is found by a header, not by a line number: a fix moves lines, a heading survives
SPLIT_HEADERS = ("## Detailed Implementation Plan", "## Implementation Plan",
                 "## Work Breakdown", "## Implementation Steps")
COMPREHENSION_HEADINGS = ("What this proposes",
                          "How the existing system works, per the document")
STOP_CONDITION = ("If your harness has no subagent tool, stop and tell the user: a review in "
                  "the same context is not a Goldfish review.")

# the fields this gate needs to judge at all; the rest of the note contract comes from
# rules/schema.json through the repo's own validator, so the two cannot drift apart
CORE_FIELDS = ("review_of", "stages", "verdict", "rounds")
DRIFT_FIELDS = ("scout_directories", "verdict")
NOTE_FIELDS = ("id", "type", "title", "status", "owner", "created", "updated")

SEVERITY_WORDS = ("blocker", "major", "nit")
SEVERITY_EMOJI = {"\U0001f534": "blocker", "\U0001f7e1": "major", "\U0001f7e2": "nit"}
PATHISH = re.compile(r"^[A-Za-z0-9_.\-/]+$")
SKIPPED_DIRS = (".git", "__pycache__", ".kb", ".brain-data", "12_RUNTIME", "13_LAB",
                "15_SYSTEM/generated", "15_SYSTEM/backups", "15_SYSTEM/logs", "node_modules",
                ".obsidian", "downloads")


# ------------------------------------------------------------------ artifact parsing
def section_body(body, title):
    """The text under the first heading whose line contains `title`, up to the next heading."""
    lines = body.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.lstrip().startswith("#") and title.lower() in line.lower():
            start = index
            break
    if start is None:
        return None
    chunk = []
    for line in lines[start + 1:]:
        if line.lstrip().startswith("#"):
            break
        chunk.append(line)
    return "\n".join(chunk)


def parse_table(chunk):
    """[{header: cell}] for the first pipe table in `chunk`; None when there is none."""
    if chunk is None:
        return None
    rows, header = [], None
    for line in chunk.splitlines():
        text = line.strip()
        if text.startswith("|"):
            cells = [c.strip() for c in text.strip("|").split("|")]
            if all(set(c) <= set("-: ") for c in cells):
                continue
            if header is None:
                header = [c.lower() for c in cells]
                continue
            rows.append(dict(zip(header, cells)))
        elif header is not None and rows:
            break
    return rows if header is not None else None


def table_cells(rows, key_column="field"):
    return {bare(row.get(key_column)).lower(): bare(row.get("value")) for row in (rows or [])}


def as_list(value):
    if value is None:
        return []
    return [str(item).strip() for item in value] if isinstance(value, list) else [str(value).strip()]


def bare(value):
    return str(value if value is not None else "").strip().strip("`").strip("'\"")


def is_pathish(value):
    text = bare(value)
    if not text or text in ("-", "--", "—", "none", "n/a", "—"):
        return False
    head = text.split(":")[0]
    if head.startswith(("http://", "https://", "git@")):
        return False
    return "/" in head and bool(PATHISH.match(head))


def citation(value):
    """The path part of a citation: a `path:symbol` claim resolves on its path."""
    return bare(value).split(":")[0].rstrip("/")


def norm_severity(value):
    text = bare(value).lower()
    for emoji, name in SEVERITY_EMOJI.items():
        text = text.replace(emoji, name)
    for word in SEVERITY_WORDS:
        if word in text:
            return word
    return text


def as_int(value):
    digits = re.sub(r"[^0-9-]", "", bare(value))
    try:
        return int(digits)
    except ValueError:
        return None


def is_yes(value):
    return bare(value).lower() in ("yes", "y", "true", "clean")


def exists(root, rel):
    return (Path(root) / rel).is_file()


# ------------------------------------------------------------------ the reviewer set
def load_personae(root):
    """{name: frontmatter} for `11_CONTROL/reviewers/*.md`, plus the problems of reading them."""
    folder = Path(root) / REVIEWERS_DIR
    personae, problems = {}, []
    if not folder.is_dir():
        return personae, problems
    for path in sorted(folder.glob("*.md")):
        fm, _body = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        name = bare(fm.get("id")) or path.stem
        if name != path.stem:
            problems.append("%s: the file is named %s, its frontmatter says %s — one of the "
                            "two is a lie" % (path, path.stem, name))
        personae[name] = fm
    return personae, problems


def persona_stages(fm):
    return [s for s in as_list(fm.get("stage")) if s]


def persona_ranges(fm):
    return [r for r in as_list(fm.get("range")) if r]


def check_personae(personae):
    """The mandates ARE the persona: drop one and the reviewer is an editor with a new name."""
    problems = []
    for name, fm in sorted(personae.items()):
        if bare(fm.get("role")) != "goldfish":
            problems.append("%s: role must be `goldfish` — an elephant may not review itself" % name)
        if bare(fm.get("writes")) != "none":
            problems.append("%s: writes must be `none` — a reviewer holding a write tool "
                            "changes the document it is judging" % name)
        if bare(fm.get("isolation")) != "fresh_subagent":
            problems.append("%s: isolation must be `fresh_subagent`. %s" % (name, STOP_CONDITION))
        missing = [m for m in MANDATES if m not in as_list(fm.get("mandates"))]
        if missing:
            problems.append("%s: missing universal mandate(s): %s" % (name, ", ".join(missing)))
        stages = persona_stages(fm)
        if not stages or [s for s in stages if s not in STAGES + SCOUT_STAGES]:
            problems.append("%s: stage must be one of %s (got %s)"
                            % (name, ", ".join(STAGES + SCOUT_STAGES), stages or "nothing"))
        spawn = bare(fm.get("spawn")).lower()
        if spawn not in SPAWN_MODES:
            problems.append("%s: spawn must be one of %s — a persona with no dispatch mode is "
                            "not a persona anyone can send" % (name, ", ".join(SPAWN_MODES)))
        elif "comprehension" in stages and spawn != "direct":
            problems.append("%s: the comprehension pass is spawned `direct`. A reviewer handed a "
                            "synthesiser's summary of the document read a rumour, not the "
                            "document" % name)
        ranges = persona_ranges(fm)
        if not ranges or [r for r in ranges if r not in RANGES]:
            problems.append("%s: range must be one of %s (got %s)"
                            % (name, ", ".join(RANGES), ranges or "nothing"))
        if not as_list(fm.get("vectors")):
            problems.append("%s: no audit vectors, so it has nothing to look for" % name)
        if not as_list(fm.get("reads")):
            problems.append("%s: no bounded reading list — a reviewer that reads everything is "
                            "not stateless, merely quiet" % name)
    if personae:
        covered = set()
        for fm in personae.values():
            covered.update(persona_stages(fm))
        gap = sorted(set(REQUIRED_STAGES) - covered)
        if gap:
            problems.append("no persona covers the required stage(s): %s" % ", ".join(gap))
    return problems


# ------------------------------------------------------------------ artifact judging
def note_problems(root, fm, label, required):
    """The fields this gate needs, then the repo's own note contract when it is installed."""
    problems = []
    for field in required + NOTE_FIELDS:
        if fm.get(field) in (None, ""):
            problems.append("%s: frontmatter field %s is empty" % (label, field))
    schema_path = Path(root) / "rules" / "schema.json"
    if schema_path.is_file():
        try:
            from frontmatter_check import validate_note
            schema = load_json(schema_path)
        except (ImportError, ValueError, OSError):
            return problems
        for problem in validate_note(fm, schema):
            problems.append("%s: %s" % (label, problem))
    return problems


def find_split(doc_lines):
    """(line_number, header) of the implementation-plan header, or (None, None)."""
    for number, line in enumerate(doc_lines, 1):
        for header in SPLIT_HEADERS:
            if line.strip().lower() == header.lower():
                return number, header
    return None, None


def judge_report(root, report_path, personae):
    """(problems, summary) — every problem is a sentence a human can act on."""
    root = Path(root)
    label = Path(report_path).name
    problems = []
    text = Path(report_path).read_text(encoding="utf-8", errors="replace")
    fm, body = parse_frontmatter(text)
    if not fm:
        return ["%s: no frontmatter block, so this is prose and cannot be judged" % label], \
            {"unreadable": True}
    problems += note_problems(root, fm, label, CORE_FIELDS)

    stages = as_list(fm.get("stages"))
    verdict = bare(fm.get("verdict")).lower()
    rounds = as_int(fm.get("rounds"))
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        problems.append("%s: unknown stage(s) %s — a stage with no persona is a stage nobody "
                        "ran" % (label, ", ".join(unknown)))
    if verdict not in VERDICTS:
        problems.append("%s: verdict %r is not one of %s" % (label, verdict, ", ".join(VERDICTS)))
    if rounds is None or rounds < 1:
        problems.append("%s: rounds must be a positive integer, not %r" % (label, fm.get("rounds")))
        return problems, {"report": str(report_path)}
    if rounds > ROUNDS_CAP:
        problems.append("%s: %d rounds — the cap is %d; a review that will not converge is a "
                        "design problem, not a reviewer problem" % (label, rounds, ROUNDS_CAP))
    if verdict != "in_progress":
        absent = [s for s in REQUIRED_STAGES if s not in stages]
        if absent:
            problems.append("%s: required stage(s) not recorded: %s" % (label, ", ".join(absent)))

    # (e) the target: the document, the split, and the ranges the reviewers were pointed at
    doc_rel = citation(fm.get("review_of"))
    doc_lines, split_at, split_header = [], None, None
    if not doc_rel:
        problems.append("%s: review_of names no document" % label)
    elif not clone_readable(doc_rel):
        problems.append("%s: review_of cites %s, which a fresh clone never contains" % (label, doc_rel))
    elif not exists(root, doc_rel):
        problems.append("%s: the document under review does not exist: %s" % (label, doc_rel))
    else:
        doc_lines = (root / doc_rel).read_text(encoding="utf-8", errors="replace").splitlines()
        split_at, split_header = find_split(doc_lines)

    target = table_cells(parse_table(section_body(body, "## Target")))
    if not target:
        problems.append("%s: no `## Target` table — a review with no resolvable target is a "
                        "review of a memory, not of a document" % label)
    else:
        claimed_doc = citation(target.get("design doc", ""))
        if claimed_doc and doc_rel and claimed_doc != doc_rel:
            problems.append("%s: the target names %s but the report reviews %s"
                            % (label, claimed_doc, doc_rel))
        claimed_header = target.get("split header", "").strip().strip("`\"'")
        if claimed_header:
            if claimed_header not in SPLIT_HEADERS:
                problems.append("%s: the target claims a split header %r that is not one of %s"
                                % (label, claimed_header, " | ".join(SPLIT_HEADERS)))
            elif split_header and claimed_header != split_header:
                problems.append("%s: the document's real split header is %r, the target says %r"
                                % (label, split_header, claimed_header))
            elif split_header is None:
                problems.append("%s: the target claims split header %r and the document has "
                                "no implementation-plan header at all" % (label, claimed_header))
        for field in ("feature range", "implementation range"):
            numbers = [int(n) for n in re.findall(r"\d+", target.get(field, ""))]
            if target.get(field) and len(numbers) < 2:
                problems.append("%s: target %s %r names no line range" % (label, field, target[field]))
            elif numbers and doc_lines and max(numbers) > len(doc_lines):
                problems.append("%s: target %s points past line %d of a %d-line document — "
                                "re-resolve the ranges to line numbers before every dispatch"
                                % (label, field, max(numbers), len(doc_lines)))
    if "implementation_readiness" in stages and split_at is None:
        problems.append("%s: stage implementation_readiness was claimed, but %s holds no "
                        "implementation-plan header (%s), so there is no implementation range "
                        "to review" % (label, doc_rel or "the document",
                                       " | ".join(SPLIT_HEADERS)))

    # (b) the roster
    roster = parse_table(section_body(body, "## Reviewers")) or []
    if not roster:
        problems.append("%s: no `## Reviewers` table — nothing was dispatched, so nothing was "
                        "reviewed" % label)
    findings = parse_table(section_body(body, "## Findings")) or []
    round_rows = parse_table(section_body(body, "## Rounds")) or []
    row_keys = set()
    for row in roster:
        name, stage, rng = bare(row.get("reviewer")), bare(row.get("stage")), bare(row.get("range"))
        round_no, status = as_int(row.get("round")), bare(row.get("status")).lower()
        context, report = bare(row.get("context")).lower(), bare(row.get("report"))
        where = "%s: reviewer %s/%s round %s" % (label, name or "(nobody)", stage or "?", round_no)
        if name not in personae:
            problems.append("%s: no persona file for %r (expected %s/%s.md)"
                            % (where, name, REVIEWERS_DIR, name or "reviewer"))
        else:
            persona = personae[name]
            if stage not in persona_stages(persona):
                problems.append("%s: %s is not a stage this persona reviews (%s)"
                                % (where, stage, ", ".join(persona_stages(persona))))
            if rng not in persona_ranges(persona):
                problems.append("%s: %s is outside this persona's range (%s)"
                                % (where, rng, ", ".join(persona_ranges(persona))))
            if not clone_readable("%s/%s.md" % (REVIEWERS_DIR, name)):
                problems.append("%s: the persona file sits behind the git boundary" % where)
        if stage and stage not in stages:
            problems.append("%s: a row for a stage the report does not record" % where)
        if status not in REVIEWER_STATUSES:
            problems.append("%s: status %r is not one of %s — an unrecorded reviewer did not "
                            "review" % (where, status, ", ".join(REVIEWER_STATUSES)))
        if context not in CONTEXTS:
            problems.append("%s: context must be `fresh` or `shared`" % where)
        elif context == "shared":
            problems.append("%s: context `shared`. %s" % (where, STOP_CONDITION))
        if round_no is None or not 1 <= round_no <= rounds:
            problems.append("%s: round outside 1..%d" % (where, rounds))
        elif (name, stage, round_no) in row_keys:
            problems.append("%s: dispatched twice for one stage in one round" % where)
        else:
            row_keys.add((name, stage, round_no))
        if status == "run":
            if not is_pathish(report):
                problems.append("%s: marked `run` with no report file. A reviewer that times "
                                "out, fails or returns no report did not review, and is never "
                                "counted as a reviewer with zero findings" % where)
            else:
                rel = citation(report)
                if not clone_readable(rel):
                    problems.append("%s: report %s sits behind the git boundary, so the review "
                                    "is not evidence a clone can read" % (where, rel))
                elif not exists(root, rel):
                    problems.append("%s: report file does not exist: %s" % (where, rel))

    # a recorded stage with no reviewer row is a stage nobody ran
    if roster and verdict != "in_progress":
        dispatched_stages = set(bare(row.get("stage")) for row in roster)
        unrun = [s for s in stages if s not in dispatched_stages]
        if unrun:
            problems.append("%s: stage(s) %s recorded but never dispatched — the frontmatter "
                            "claims a pass no reviewer row shows"
                            % (label, ", ".join(unrun)))

    # (c) + (d) the findings
    ids = {}
    for row in findings:
        fid, reviewer = bare(row.get("id")), bare(row.get("reviewer"))
        round_no = as_int(row.get("round"))
        severity, status = norm_severity(row.get("severity")), bare(row.get("status")).lower()
        category, reason, evidence = bare(row.get("category")).lower(), bare(row.get("reason")), \
            bare(row.get("evidence"))
        where = "%s: finding %s" % (label, fid or "(no id)")
        if severity not in SEVERITY_WORDS:
            problems.append("%s: severity %r is not blocker / major / nit" % (where, severity))
        if status not in FINDING_STATUSES:
            problems.append("%s: status %r is not one of %s"
                            % (where, status, ", ".join(FINDING_STATUSES)))
        if category not in CATEGORIES:
            problems.append("%s: category %r is not one of %s"
                            % (where, category, ", ".join(c or "-" for c in CATEGORIES)))
        if round_no is None or not re.match(r"^%s-%s-\d+$" % (re.escape(reviewer), round_no), fid):
            problems.append("%s: a finding id is `<reviewer>-<round>-<n>` (reviewer %r, round %r)"
                            % (where, reviewer, round_no))
        if (reviewer, round_no) not in [(bare(r.get("reviewer")), as_int(r.get("round")))
                                        for r in roster]:
            problems.append("%s: raised by %s in round %s, which the roster never dispatched"
                            % (where, reviewer or "(nobody)", round_no))
        if fid in ids and ids[fid] != status:
            problems.append("%s: one id carrying two statuses — a settled finding is never "
                            "re-opened under its own id; a fix that recurs gets a new id that "
                            "reopens it" % where)
        ids[fid] = status
        checked = False
        if is_pathish(evidence):
            rel = citation(evidence)
            checked = True
            if not clone_readable(rel):
                problems.append("%s: evidence %s is behind the git boundary — export what you "
                                "measured instead of pointing at local state" % (where, rel))
            elif not exists(root, rel):
                problems.append("%s: evidence names %s, which does not exist in this clone"
                                % (where, rel))
            elif ":" in evidence and evidence.split(":", 1)[1] and rel.endswith(".py"):
                symbol = evidence.split(":", 1)[1]
                if symbol not in (root / rel).read_text(encoding="utf-8", errors="replace"):
                    problems.append("%s: symbol %r is not in %s — a contest must be checkable"
                                    % (where, symbol, rel))
        elif evidence:
            problems.append("%s: evidence %r is neither a path a clone can open nor empty"
                            % (where, evidence))
        if severity in ("blocker", "major"):
            if verdict != "in_progress":
                if status not in SETTLED:
                    problems.append("%s: a %s left `%s` — the review is not finished while a "
                                    "Blocker or Major is unsettled" % (where, severity, status))
                if not reason:
                    problems.append("%s: a %s resolved without a reason is a silent gate"
                                    % (where, severity))
            if status == "contested" and not checked:
                problems.append("%s: contested without a file to check. A contest must be "
                                "checkable evidence, not a request for more context" % where)
            if category == "contest" and status != "contested":
                problems.append("%s: category `contest` with status `%s`" % (where, status))
            if category == "escalate" and status != "escalated":
                problems.append("%s: category `escalate` with status `%s` — escalate means the "
                                "human decides; the document does not absorb the evidence"
                                % (where, status))
            if category == "decline" and severity == "blocker":
                problems.append("%s: `decline` is the answer to a nit, never to a Blocker" % where)

    # the round arithmetic: clean is derived, never granted
    if not round_rows:
        problems.append("%s: no `## Rounds` table — convergence cannot be checked" % label)
    if len(round_rows) != rounds:
        problems.append("%s: rounds=%d but the Rounds table has %d row(s)"
                        % (label, rounds, len(round_rows)))
    clean_by_round = {}
    for row in round_rows:
        round_no = as_int(row.get("round"))
        clean = is_yes(row.get("clean"))
        where = "%s: round %s" % (label, round_no)
        if round_no is None or not 1 <= round_no <= rounds:
            problems.append("%s: outside 1..%d" % (where, rounds))
            continue
        clean_by_round[round_no] = clean
        not_run = len([r for r in roster if as_int(r.get("round")) == round_no
                       and bare(r.get("status")).lower() != "run"])
        raised = len([f for f in findings if as_int(f.get("round")) == round_no
                      and norm_severity(f.get("severity")) in ("blocker", "major")])
        if as_int(row.get("not_run")) != not_run:
            problems.append("%s: claims not_run=%s while the roster holds %d reviewer(s) that "
                            "did not run — a failed reviewer is never zero findings"
                            % (where, row.get("not_run"), not_run))
        if as_int(row.get("unsettled")) != raised:
            problems.append("%s: claims unsettled=%s while the findings table raises %d "
                            "Blocker/Major(s) in that round" % (where, row.get("unsettled"), raised))
        if clean:
            if not_run:
                problems.append("%s: claimed clean while %d reviewer(s) of that round are not "
                                "`run` — the round is not clean until every dispatched reviewer "
                                "actually ran" % (where, not_run))
            if raised:
                problems.append("%s: claimed clean while %d Blocker/Major(s) were raised in it"
                                % (where, raised))
            dispatched = set(bare(r.get("stage")) for r in roster
                             if as_int(r.get("round")) == round_no)
            for stage in sorted(dispatched & set(stages)):
                for name, persona in sorted(personae.items()):
                    if stage not in persona_stages(persona):
                        continue
                    rows = [r for r in roster if as_int(r.get("round")) == round_no
                            and bare(r.get("stage")) == stage and bare(r.get("reviewer")) == name]
                    if not rows:
                        problems.append("%s: stage %s was dispatched but %s has no row — the "
                                        "roster of a clean round is complete or the round is "
                                        "not clean" % (where, stage, name))
                    elif any(bare(r.get("context")).lower() != "fresh" for r in rows):
                        problems.append("%s: stage %s ran in a shared context — the elephant "
                                        "grading its own homework is not a review" % (where, stage))
    ordered = [clean_by_round.get(n) for n in sorted(clean_by_round)]
    two_clean = any(first and second for first, second in zip(ordered, ordered[1:]))
    if verdict == "converged" and not two_clean:
        problems.append("%s: verdict converged without two consecutive clean rounds" % label)
    if verdict == "capped" and rounds != ROUNDS_CAP:
        problems.append("%s: verdict capped after %d rounds; the cap is %d" % (label, rounds, ROUNDS_CAP))
    if verdict == "aborted" and (roster or findings):
        problems.append("%s: verdict aborted with reviewers dispatched — with no subagent tool "
                        "the run stops before the roster, not after it" % label)
    residuals = sorted(fid for fid, status in ids.items()
                       if status in ("escalated", "contested", "declined"))
    if residuals:
        trade_offs = section_body(body, "Accepted trade-offs")
        if trade_offs is None:
            problems.append("%s: findings %s were escalated, contested or declined and are not "
                            "recorded as accepted trade-offs" % (label, ", ".join(residuals)))
        else:
            unrecorded = [fid for fid in residuals if fid not in trade_offs]
            if unrecorded:
                problems.append("%s: `## Accepted trade-offs` does not name %s"
                                % (label, ", ".join(unrecorded)))
    if "comprehension" in stages:
        inline = section_body(body, "## Comprehension") or ""
        paraphrased = all(heading in inline for heading in COMPREHENSION_HEADINGS)
        if not paraphrased:
            # the two headings may live in the reviewer's own report instead — but only in a
            # file the clone can open, never in the summariser that never read the document
            for row in roster:
                if bare(row.get("stage")) == "comprehension" and is_pathish(row.get("report")):
                    path = root / citation(row.get("report"))
                    if path.is_file() and all(heading in path.read_text(encoding="utf-8",
                                                                        errors="replace")
                                              for heading in COMPREHENSION_HEADINGS):
                        paraphrased = True
                        break
        if not paraphrased:
            problems.append("%s: the comprehension pass is not opened by the two verbatim "
                            "paraphrase headings (%s), and it is spawned directly, never "
                            "through a synthesiser"
                            % (label, " / ".join(COMPREHENSION_HEADINGS)))
    summary = {"report": str(report_path), "roster": len(roster), "findings": len(findings),
               "personae": len(personae), "rounds": rounds}
    return problems, summary


def judge_drift(root, report_path):
    """A drift report is a claim about documents and code that both still have to be there."""
    root = Path(root)
    label = Path(report_path).name
    problems = []
    fm, body = parse_frontmatter(Path(report_path).read_text(encoding="utf-8", errors="replace"))
    if not fm:
        return ["%s: no frontmatter block, so this is prose and cannot be judged" % label], \
            {"unreadable": True}
    problems += note_problems(root, fm, label, DRIFT_FIELDS)
    verdict = bare(fm.get("verdict")).lower()
    if verdict not in DRIFT_VERDICTS:
        problems.append("%s: verdict %r is not clean or drifted" % (label, verdict))
    listed = parse_table(section_body(body, "## Drift")) or []
    counted = as_int(fm.get("scout_directories"))
    enumerated = as_int(table_cells(parse_table(section_body(body, "## Enumeration"))).get("directories"))
    if enumerated is None:
        problems.append("%s: no `## Enumeration` table — the scout's bounded list is not "
                        "recorded, so nobody can tell how much it read" % label)
    elif counted is None:
        pass  # scout_directories is already reported as an empty field
    elif counted != enumerated:
        problems.append("%s: scout_directories=%d but the Enumeration table says %d"
                        % (label, counted, enumerated))
    if counted is not None and counted > SCOUT_LIMIT and "reported_to_human" not in body:
        problems.append("%s: the scout enumerated %d directories; past %d it stops and reports "
                        "the count to the human instead of rolling the folder up"
                        % (label, counted, SCOUT_LIMIT))
    if not listed and verdict == "drifted":
        problems.append("%s: verdict drifted with an empty `## Drift` table" % label)
    for row in listed:
        document, cited = citation(row.get("document")), citation(row.get("citation"))
        state = bare(row.get("verdict")).lower()
        where = "%s: drift row %s" % (label, cited or document or "(empty)")
        if state not in DRIFT_VERDICTS and state not in ("gone", "stale", "moved"):
            problems.append("%s: verdict %r is not gone / stale / moved (an `ok` row is not drift)"
                            % (where, state))
            continue
        if not document or not clone_readable(document) or not exists(root, document):
            problems.append("%s: the document that drifted is not here: %s" % (where, document or "?"))
            continue
        if not cited or not clone_readable(cited):
            problems.append("%s: citation %r is not a path a clone can open" % (where, cited))
            continue
        doc_text = (root / document).read_text(encoding="utf-8", errors="replace")
        if cited.split(":")[0] not in doc_text:
            problems.append("%s: %s does not actually name %s, so nothing drifted — the report "
                            "invented the claim it is reporting" % (where, document, cited))
        elif state == "gone" and exists(root, cited):
            problems.append("%s: called gone, but %s exists — the document is fine, the report "
                            "is stale" % (where, cited))
        elif state != "gone" and not exists(root, cited):
            problems.append("%s: called %s, but %s does not exist; the only honest verdict for a "
                            "missing file is gone" % (where, state, cited))
    if listed and verdict == "clean":
        problems.append("%s: verdict clean with %d drift row(s)" % (label, len(listed)))
    return problems, {"report": str(report_path), "rows": len(listed), "directories": counted}


def find_artifacts(root, field):
    """Every tracked markdown file whose frontmatter claims this kind of artifact."""
    found = []
    for path in sorted(Path(root).rglob("*.md")):
        rel = path.relative_to(root).as_posix()
        if any(part in SKIPPED_DIRS for part in path.relative_to(root).parts[:-1]):
            continue
        if not clone_readable(rel):
            continue
        try:
            fm, _body = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
        if fm.get(field):
            found.append(path)
    return found


# ------------------------------------------------------------------ fixtures + self-test
def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


DESIGN_DOC = "\n".join([
    "---", "id: design-goldfish-method", "type: note", "title: \"Design: the goldfish method\"",
    "status: raw", "owner: agent", "topics: [goldfish-review]", "created: 2026-11-02",
    "updated: 2026-11-02", "---", "", "# Design: the goldfish method", "",
    "The elephant drafts with the whole context; a zero-context reviewer reads it cold. The",
    "gates it must answer to are listed in scripts/health.py.", "",
    "## Detailed Implementation Plan", "", "1. Add scripts/goldfish_check.py.",
    "2. Add the personae.", ""])
DESIGN_DOC_NO_SPLIT = "\n".join(line for line in DESIGN_DOC.splitlines()
                               if not line.startswith("## Detailed")) + "\n"

PERSONA_STAGES = {"egm-zoom-out": (("zoom_out", "document"),),
                  "egm-comprehension": (("comprehension", "document"),),
                  "egm-design": (("critic", "feature"),),
                  "egm-structural": (("critic", "feature"),),
                  # style is dispatched in both stages: the feature range and the plan
                  "egm-style": (("critic", "feature"), ("implementation_readiness",
                                                         "implementation")),
                  "egm-codebase-details": (("implementation_readiness", "implementation"),),
                  "egm-implementation-readiness": (("implementation_readiness",
                                                    "implementation"),)}

REVIEWER_COLUMNS = ("reviewer", "stage", "range", "round", "context", "status", "report")
FINDING_COLUMNS = ("id", "reviewer", "round", "severity", "status", "category", "reason", "evidence")
ROUND_COLUMNS = ("round", "clean", "unsettled", "not_run", "note")


def fixture_report(root, rounds=2, not_run=False, open_finding=False, bad_citation=False,
                   strip_split=False, clean_last=None):
    """One well-formed report — or one deliberate lie, chosen by the keyword arguments."""
    stages = ["zoom_out", "comprehension", "critic", "implementation_readiness"]
    rows, reports, missed_by_round = [], [], {}
    for round_no in range(1, rounds + 1):
        for name, seats in sorted(PERSONA_STAGES.items()):
            for stage, rng in seats:
                status = "not_run" if (not_run and round_no == rounds
                                       and name == "egm-style") else "run"
                if status != "run":
                    missed_by_round[round_no] = missed_by_round.get(round_no, 0) + 1
                report = "03_PROJECTS/reviews/%s-r%d-%s.md" % (name, round_no, stage)
                rows.append("| %s |" % " | ".join((name, stage, rng, str(round_no), "fresh",
                                                   status, report)))
                reports.append((report, name))
    for report, name in reports:
        text = "# %s\n\nNothing blocking.\n" % name
        if name == "egm-comprehension":
            text += "\n## What this proposes\n\nA gate over review artifacts.\n\n"
            text += ("## How the existing system works, per the document\n\n"
                     "health.py runs the gates.\n")
        _write(root / report, text)
    evidence = "scripts/nope.py" if bad_citation else "scripts/health.py"
    if open_finding:
        findings = ["| %s |" % " | ".join(("egm-design-%d-1" % rounds, "egm-design", str(rounds),
                                           "major", "open", "propose_fix",
                                           "an invariant with no gate", "scripts/health.py"))]
    else:
        findings = ["| %s |" % " | ".join(("egm-design-1-1", "egm-design", "1", "nit", "declined",
                                          "decline", "wording only", evidence))]
    raised_last = 1 if open_finding else 0
    round_rows = []
    for round_no in range(1, rounds + 1):
        raised = raised_last if round_no == rounds else 0
        missed = missed_by_round.get(round_no, 0)
        if round_no == rounds and clean_last is not None:
            clean = clean_last
        else:
            clean = "no" if (raised or missed) else "yes"
        round_rows.append("| %s |" % " | ".join((str(round_no), clean, str(raised), str(missed),
                                                 "both ranges dispatched")))
    lines = ["---", "id: gfr-goldfish-method", "type: review",
             "title: \"Goldfish review — the goldfish method\"", "status: raw", "owner: agent",
             "topics: [goldfish-review]", "created: 2026-11-02", "updated: 2026-11-02",
             "review_of: 03_PROJECTS/designs/goldfish-method.md",
             "stages: [%s]" % ", ".join(stages), "verdict: converged", "rounds: %d" % rounds,
             "---", "", "# Goldfish review — the goldfish method", "",
             "## Target", "", "| field | value |", "| --- | --- |",
             "| design doc | 03_PROJECTS/designs/goldfish-method.md |",
             "| split header | ## Detailed Implementation Plan |",
             "| feature range | lines 1-13 |", "| implementation range | lines 14-17 |", "",
             "## Reviewers", "",
             "| %s |" % " | ".join(REVIEWER_COLUMNS),
             "| %s |" % " | ".join(["---"] * len(REVIEWER_COLUMNS)),
             "\n".join(rows), "",
             "## Findings", "",
             "| %s |" % " | ".join(FINDING_COLUMNS),
             "| %s |" % " | ".join(["---"] * len(FINDING_COLUMNS)),
             "\n".join(findings), "",
             "## Rounds", "",
             "| %s |" % " | ".join(ROUND_COLUMNS),
             "| %s |" % " | ".join(["---"] * len(ROUND_COLUMNS)),
             "\n".join(round_rows), "",
             "## Comprehension", "",
             "### What this proposes", "", "A gate over review artifacts.", "",
             "### How the existing system works, per the document", "",
             "health.py runs the gates.", "",
             "## Accepted trade-offs", "",
             "- egm-design-1-1 — wording only, declined as a nit.", ""]
    _write(root / "03_PROJECTS" / "designs" / "goldfish-method.md",
           DESIGN_DOC_NO_SPLIT if strip_split else DESIGN_DOC)
    return _write(root / "03_PROJECTS" / "reviews" / "goldfish_review_report.md",
                  "\n".join(lines) + "\n")


def fixture_house():
    """A throwaway clone-shaped root: the shipped personae, a design doc, one cited script."""
    root = Path(tempfile.mkdtemp())
    source = find_root(Path(__file__))
    if (source / REVIEWERS_DIR).is_dir():
        shutil.copytree(source / REVIEWERS_DIR, root / REVIEWERS_DIR)
    _write(root / "03_PROJECTS" / "designs" / "goldfish-method.md", DESIGN_DOC)
    _write(root / "scripts" / "health.py", "#!/usr/bin/env python\n\"\"\"the gate list\"\"\"\n")
    return root


def fixture_drift(root, rows=1, directories=12):
    """A scout's drift report: the document names a script the tree no longer holds."""
    _write(root / "00_START_HERE" / "START.md",
           "# START\n\npython scripts/gone_away.py runs it\n")
    lines = ["---", "id: drift-2026-11-02", "type: review", "title: \"Drift report\"",
             "status: raw", "owner: agent", "topics: [drift-report]", "created: 2026-11-02",
             "updated: 2026-11-02", "scout_directories: %d" % directories,
             "verdict: %s" % ("drifted" if rows else "clean"), "---", "",
             "# Drift report", "", "## Enumeration", "", "| field | value |", "| --- | --- |",
             "| directories | %d |" % directories, "", "## Drift", "",
             "| document | citation | verdict | note |", "| --- | --- | --- | --- |"]
    for index in range(rows):
        lines.append("| 00_START_HERE/START.md | scripts/gone_away.py | gone | step %d names a "
                     "script the tree does not hold |" % (index + 1))
    return _write(root / "00_START_HERE" / "drift-report.md", "\n".join(lines) + "\n")


def self_test():
    """Each lie below is the reason the gate exists; the phase 43 tests re-run them via --report."""
    cases, houses = [], []

    def house():
        root = fixture_house()
        houses.append(root)
        return root

    root = house()
    problems, _ = judge_report(root, fixture_report(root), load_personae(root)[0])
    cases.append(("a well-formed report is accepted", problems == [], problems))

    root = house()
    problems, _ = judge_report(root, fixture_report(root, not_run=True, clean_last="yes"),
                               load_personae(root)[0])
    cases.append(("a clean round over a reviewer that did not run is refused",
                  any("not `run`" in problem for problem in problems), problems))

    root = house()
    problems, _ = judge_report(root, fixture_report(root, open_finding=True),
                               load_personae(root)[0])
    cases.append(("an unsettled Major is refused",
                  any("unsettled" in problem for problem in problems), problems))

    root = house()
    problems, _ = judge_report(root, fixture_report(root, bad_citation=True),
                               load_personae(root)[0])
    cases.append(("a citation a fresh clone cannot open is refused",
                  any("does not exist in this clone" in problem for problem in problems),
                  problems))

    root = house()
    problems, _ = judge_report(root, fixture_report(root, strip_split=True),
                               load_personae(root)[0])
    cases.append(("stage 9 over a document with no implementation-plan header is refused",
                  any("no implementation-plan header" in problem for problem in problems),
                  problems))

    root = house()
    report = fixture_report(root)
    _write(report, report.read_text(encoding="utf-8").replace(
        "stages: [zoom_out, comprehension, critic, implementation_readiness]",
        "stages: [zoom_out, comprehension, critic, intermediate_zoom_out, "
        "implementation_readiness]"))
    problems, _ = judge_report(root, report, load_personae(root)[0])
    cases.append(("a stage recorded with no reviewer row is refused",
                  any("recorded but never dispatched" in problem for problem in problems),
                  problems))

    root = house()
    persona = root / REVIEWERS_DIR / "egm-comprehension.md"
    _write(persona, persona.read_text(encoding="utf-8").replace("spawn: direct",
                                                                 "spawn: synthesizer"))
    personae, _ = load_personae(root)
    problems = check_personae(personae)
    cases.append(("a comprehension persona routed through a synthesiser is refused",
                  any("spawned `direct`" in problem for problem in problems), problems))

    root = house()
    problems, _ = judge_report(root, fixture_report(root, not_run=True, clean_last="no",
                                                    rounds=3), load_personae(root)[0])
    cases.append(("a round that admits its failed reviewer stays honest and converges",
                  problems == [], problems))

    root = house()
    problems, _ = judge_drift(root, fixture_drift(root))
    cases.append(("a drift report naming a script that really went missing is accepted",
                  problems == [], problems))

    root = house()
    problems, _ = judge_drift(root, fixture_drift(root, rows=30, directories=40))
    cases.append(("a scout list past 15 directories without a stop is refused",
                  any("past 15 it stops" in problem for problem in problems), problems))

    root = house()
    drift = fixture_drift(root)
    _write(root / "scripts" / "gone_away.py", "# it came back\n")
    problems, _ = judge_drift(root, drift)
    cases.append(("a file reported gone that still exists is refused",
                  any("called gone" in problem for problem in problems), problems))

    personae, read_problems = load_personae(find_root(Path(__file__)))
    persona_problems = check_personae(personae)
    cases.append(("the shipped reviewer set is a complete goldfish set",
                  bool(personae) and not read_problems and not persona_problems,
                  read_problems + persona_problems))

    for root in houses:
        shutil.rmtree(str(root), ignore_errors=True)
    failures = [case for case in cases if not case[1]]
    for label, passed, detail in cases:
        print("  %s  %s" % ("PASS" if passed else "FAIL", label))
        if detail and not passed:
            for problem in detail[:4]:
                print("        %s" % problem)
    if failures:
        print("FAILED — %d of %d self-test cases did not behave" % (len(failures), len(cases)))
        return 1
    print("SELF-TEST OK — %d cases: the honest artifacts pass and every lie is refused"
          % len(cases))
    return 0


# ------------------------------------------------------------------ main
def report_result(problems, label, exit_code=1):
    if problems:
        print("REFUSED — %s is not a goldfish artifact" % label)
        for problem in problems:
            print("  %s" % problem)
        return exit_code
    print("OK — %s: stages, roster, findings and citations say the same thing" % label)
    return 0


def code_for(problems, summary, label):
    """Exit 2 only when the thing never opened as an artifact; 1 when it opened and lied."""
    return report_result(problems, label, 2 if summary.get("unreadable") else 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", default=None, help="a goldfish review report to judge")
    parser.add_argument("--drift", default=None, help="a drift report to judge")
    parser.add_argument("--root", default=None, help="repo root override (tests)")
    parser.add_argument("--personas", action="store_true", help="judge the reviewer set only")
    parser.add_argument("--self-test", action="store_true", help="prove the refusals fire")
    parser.add_argument("--vault", default=None,
                        help="accepted and ignored: this gate judges the clone, not a vault")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    root = Path(args.root) if args.root else find_root(Path(__file__))
    personae, problems = load_personae(root)

    if args.personas:
        problems = problems + check_personae(personae)
        if personae and not problems:
            print("OK — %d goldfish personae in %s: mandates, audit vectors and bounded reading "
                  "lists all present" % (len(personae), REVIEWERS_DIR))
            return 0
        if not personae:
            problems.append("no persona file in %s: a reviewer set that is empty reviewed "
                            "nothing, and cannot be judged a goldfish set" % REVIEWERS_DIR)
        print("REFUSED — the reviewer set is not a goldfish set")
        for problem in problems:
            print("  %s" % problem)
        return 1

    if args.report:
        path = Path(args.report)
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            print("REFUSED — the report could not be read, so it is not clean: %s" % path)
            return 2
        problems = problems + check_personae(personae)
        judged, summary = judge_report(root, path, personae)
        return code_for(problems + judged, summary, path.name)

    if args.drift:
        path = Path(args.drift)
        if not path.is_absolute():
            path = root / path
        if not path.is_file():
            print("REFUSED — the drift report could not be read, so it is not clean: %s" % path)
            return 2
        judged, summary = judge_drift(root, path)
        return code_for(judged, summary, path.name)

    # the gate you run on its own: judge the reviewer set, then every artifact this clone holds
    reports = find_artifacts(root, "review_of")
    drifts = [path for path in find_artifacts(root, "scout_directories") if path not in reports]
    unreadable = False
    if personae:
        problems += check_personae(personae)
    elif reports or drifts:
        problems.append("%d goldfish artifact(s) in this clone with no %s/ folder: a report "
                        "whose reviewers have no definitions is a claim about a review"
                        % (len(reports) + len(drifts), REVIEWERS_DIR))
    for report in reports:
        judged, summary = judge_report(root, report, personae)
        problems += judged
        unreadable = unreadable or bool(summary.get("unreadable"))
    for report in drifts:
        judged, summary = judge_drift(root, report)
        problems += judged
        unreadable = unreadable or bool(summary.get("unreadable"))
    if problems:
        print("REFUSED — the goldfish method is not what its artifacts claim")
        for problem in problems:
            print("  %s" % problem)
        return 2 if unreadable else 1
    if not personae and not reports and not drifts:
        print("OK — nothing to judge: no reviewer set installed (%s is absent) and no goldfish "
              "review or drift report in this clone" % REVIEWERS_DIR)
        return 0
    print("OK — %d goldfish personae, %d review report(s) and %d drift report(s) judged"
          % (len(personae), len(reports), len(drifts)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
