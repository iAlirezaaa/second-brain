"""Phase 43 — the goldfish method, judged by a script instead of by a sentence.

Google's `elephant-goldfish-model` drafts a specification with the whole context (the
elephant) and reviews it with subagents that never saw the conversation (the goldfish). The
discipline is worth porting; the plugin packaging is not. What is shipped here is the same
discipline with a gate behind it, because the failure mode is exact and common: a report that
*says* the round was clean. `scripts/goldfish_check.py` therefore re-derives every verdict from
the artifact — and these tests write the artifact by hand, in a temp root, so the gate cannot
agree with itself about what a well-formed report is.

Every class below is red without its feature:

  1. an honest report is accepted (and four kinds of lie are refused: a clean round over a
     reviewer that did not run, a Blocker left unsettled, a citation a clone cannot open, and
     stage 9 over a document with no implementation-plan header);
  2. the personae are data the gate reads, not prose it is told to admire;
  3. a drift report is re-checked against the tree, so it cannot invent a defect;
  4. the three skills carry the law the gate refuses without: the stop condition verbatim, the
     split header, the resolve categories, the commands.
"""
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from common import iter_notes, load_json, parse_frontmatter, run_utf8  # noqa: E402
import goldfish_check as egm  # noqa: E402

GATE = str(SCRIPTS / "goldfish_check.py")
DOC = "03_PROJECTS/designs/goldfish-method.md"
STOP = ("If your harness has no subagent tool, stop and tell the user: a review in the same "
        "context is not a Goldfish review.")

# what the shipped personae say each reviewer is dispatched for; the test states it independently
SEATS = (("egm-zoom-out", "zoom_out", "document"),
         ("egm-comprehension", "comprehension", "document"),
         ("egm-design", "critic", "feature"),
         ("egm-structural", "critic", "feature"),
         ("egm-style", "critic", "feature"),
         ("egm-zoom-out", "intermediate_zoom_out", "document"),
         ("egm-implementation-readiness", "implementation_readiness", "implementation"),
         ("egm-codebase-details", "implementation_readiness", "implementation"),
         ("egm-style", "implementation_readiness", "implementation"))

DESIGN_BODY = """# Design: the goldfish method

The elephant drafts with the whole context; a zero-context reviewer reads it cold.
The gates the design answers to are listed in scripts/health.py.

## Detailed Implementation Plan

1. Add the reviewer definitions.
2. Add scripts/goldfish_check.py.
3. Add the skills and this test.
"""

DESIGN_BODY_NO_SPLIT = DESIGN_BODY.replace("## Detailed Implementation Plan", "## Rollout")


def design_text(front=True):
    head = ("---\nid: design-goldfish-method\ntype: note\n"
            "title: \"Design: the goldfish method\"\nstatus: raw\nowner: agent\n"
            "topics: [goldfish-review]\ncreated: 2026-11-02\nupdated: 2026-11-02\n---\n\n") \
        if front else ""
    return head + DESIGN_BODY


def report_text(rounds=2, broken=None, split=True):
    """A well-formed review artifact, or one carrying a single named lie."""
    seats, files = [], []
    for round_no in range(1, rounds + 1):
        for name, stage, rng in SEATS:
            status = "run"
            if broken == "not_run" and round_no == rounds and name == "egm-style":
                status = "not_run"
            if broken == "no_report" and round_no == rounds and name == "egm-design":
                report = "-"
            else:
                report = "03_PROJECTS/reviews/%s-%s-r%d.md" % (name, stage.replace("_", "-"),
                                                               round_no)
                files.append((report, name))
            context = "shared" if (broken == "shared" and round_no == rounds
                                   and name == "egm-structural") else "fresh"
            seats.append("| %s |" % " | ".join((name, stage, rng, str(round_no), context, status,
                                                report)))
    findings = ["| egm-design-1-1 | egm-design | 1 | nit | declined | decline | wording only | %s |"
                % ("scripts/goldfish_check.py" if broken != "bad_citation"
                   else "scripts/never_written.py")]
    if broken == "open_blocker":
        findings.append("| egm-structural-%d-1 | egm-structural | %d | blocker | open | "
                        "propose_fix | an invariant with no gate behind it | "
                        "scripts/goldfish_check.py |" % (rounds, rounds))
    if broken == "escalated":
        findings.append("| egm-structural-%d-1 | egm-structural | %d | blocker | escalated | "
                        "escalate | the evidence lives outside the files a reviewer can read | "
                        "scripts/goldfish_check.py |" % (rounds, rounds))
    if broken == "fake_contest":
        findings.append("| egm-style-%d-1 | egm-style | %d | major | contested | contest | "
                        "the reviewer misread it | |" % (rounds, rounds))
    round_rows = []
    for round_no in range(1, rounds + 1):
        missed = len([row for row in seats if "| %d |" % round_no in row and " not_run |" in row])
        raised = 1 if (broken in ("open_blocker", "fake_contest", "escalated")
                      and round_no == rounds) else 0
        clean = "no" if (missed and broken != "not_run") or raised else "yes"
        if broken == "not_run" and round_no == rounds:
            clean = "yes"          # the lie this phase exists to catch
        round_rows.append("| %s |" % " | ".join((str(round_no), clean, str(raised), str(missed),
                                                 "both ranges dispatched")))
    split_rows = ("| split header | ## Detailed Implementation Plan |\n"
                  "| feature range | lines 1-5 |\n| implementation range | lines 6-10 |\n"
                  if split else "| feature range | lines 1-10 |\n")
    return "\n".join([
        "---", "id: gfr-goldfish-method", "type: review",
        "title: \"Goldfish review — the goldfish method\"", "status: raw", "owner: agent",
        "topics: [goldfish-review, egm]", "created: 2026-11-02", "updated: 2026-11-02",
        "review_of: %s" % DOC,
        "stages: [zoom_out, comprehension, critic, intermediate_zoom_out, implementation_readiness]",
        "verdict: converged", "rounds: %d" % rounds, "---", "",
        "# Goldfish review — the goldfish method", "",
        "## Target", "", "| field | value |", "| --- | --- |", "| design doc | %s |" % DOC,
        split_rows.rstrip("\n"), "",
        "## Reviewers", "",
        "| reviewer | stage | range | round | context | status | report |",
        "| --- | --- | --- | --- | --- | --- | --- |", "\n".join(seats), "",
        "## Findings", "",
        "| id | reviewer | round | severity | status | category | reason | evidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |", "\n".join(findings), "",
        "## Rounds", "", "| round | clean | unsettled | not_run | note |",
        "| --- | --- | --- | --- | --- |", "\n".join(round_rows), "",
        "## Comprehension", "",
        "### What this proposes", "A gate that re-derives a review verdict from the artifact.", "",
        "### How the existing system works, per the document",
        "health.py runs every gate in one command.", "",
        "## Accepted trade-offs", "",
        "- egm-design-1-1 — a wording nit, declined; it is not a law.",
        "- egm-structural-%d-1 — escalated to the human." % rounds if broken == "escalated" else "",
        "", ""])


def house():
    """A throwaway clone-shaped root: the shipped personae, one design doc, one cited script."""
    root = Path(tempfile.mkdtemp())
    shutil.copytree(ROOT / "11_CONTROL" / "reviewers", root / "11_CONTROL" / "reviewers")
    (root / "scripts").mkdir(parents=True)
    (root / "scripts" / "goldfish_check.py").write_text("# the gate itself\n", encoding="utf-8")
    (root / "scripts" / "health.py").write_text("# the gate list\n", encoding="utf-8")
    return root


def write(root, rel, text):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def seeded(root, broken=None, rounds=2, split=True):
    """The house plus one report and the files it cites."""
    write(root, DOC, design_text() if split else
          design_text().replace(DESIGN_BODY, DESIGN_BODY_NO_SPLIT))
    text = report_text(rounds=rounds, broken=broken, split=split)
    for rel in re.findall(r"\| (03_PROJECTS/reviews/[a-z0-9\-]+\.md) \|", text):
        name = Path(rel).stem.split("-r")[0]
        body = "# %s\n\nNothing blocking.\n" % name
        if "comprehension" in rel:
            body += ("\n## What this proposes\n\nA gate.\n\n## How the existing system works, "
                     "per the document\n\nhealth.py runs the gates.\n")
        write(root, rel, body)
    return write(root, "03_PROJECTS/reviews/goldfish_review_report.md", text)


def problems_of(root, report):
    personae, read_problems = egm.load_personae(root)
    return read_problems + egm.check_personae(personae) + \
        egm.judge_report(root, report, personae)[0]


class TheGateJudgesTheArtifact(unittest.TestCase):
    def setUp(self):
        self.root = house()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def test_an_honest_report_is_accepted(self):
        report = seeded(self.root)
        self.assertEqual(problems_of(self.root, report), [])

    def test_a_clean_round_over_a_reviewer_that_did_not_run_is_refused(self):
        report = seeded(self.root, broken="not_run")
        problems = problems_of(self.root, report)
        self.assertTrue(problems, "the gate let a round claim clean over a reviewer that did not run")
        self.assertIn("not `run`", "\n".join(problems))

    def test_a_blocker_left_open_is_refused(self):
        report = seeded(self.root, broken="open_blocker")
        problems = problems_of(self.root, report)
        self.assertTrue(any("unsettled" in problem for problem in problems), problems)

    def test_a_citation_a_clone_cannot_open_is_refused(self):
        report = seeded(self.root, broken="bad_citation")
        problems = problems_of(self.root, report)
        self.assertTrue(any("does not exist in this clone" in problem for problem in problems),
                        problems)

    def test_stage_nine_over_a_doc_with_no_implementation_plan_header_is_refused(self):
        report = seeded(self.root, split=False)
        problems = problems_of(self.root, report)
        self.assertTrue(any("no implementation-plan header" in problem for problem in problems),
                        problems)

    def test_a_reviewer_marked_run_that_returned_no_report_did_not_review(self):
        report = seeded(self.root, broken="no_report")
        problems = problems_of(self.root, report)
        self.assertTrue(any("did not review" in problem for problem in problems), problems)

    def test_a_reviewer_reading_the_conversation_is_not_a_goldfish(self):
        report = seeded(self.root, broken="shared")
        problems = problems_of(self.root, report)
        joined = "\n".join(problems)
        self.assertIn("shared context", joined)
        self.assertIn("subagent tool", joined, "the refusal must carry the stop condition: %s" % joined)

    def test_a_contest_must_point_at_a_file_the_clone_can_check(self):
        report = seeded(self.root, broken="fake_contest")
        problems = problems_of(self.root, report)
        self.assertTrue(any("contested without a file" in problem for problem in problems), problems)

    def test_the_gate_refuses_a_report_that_is_only_prose(self):
        write(self.root, "03_PROJECTS/reviews/prose.md", "# Review\n\nlooks fine to me\n")
        done = run_utf8([sys.executable, GATE, "--root", str(self.root), "--report",
                         "03_PROJECTS/reviews/prose.md"], cwd=str(ROOT))
        self.assertEqual(2, done.returncode, done.stdout + done.stderr)

    def test_the_cli_refuses_the_lie_and_accepts_the_honest_artifact(self):
        report = seeded(self.root, broken="not_run")
        done = run_utf8([sys.executable, GATE, "--root", str(self.root), "--report",
                         str(report)], cwd=str(ROOT))
        self.assertEqual(1, done.returncode, done.stdout)
        self.assertIn("REFUSED", done.stdout)
        good_root = house()
        good = seeded(good_root, broken=None)
        try:
            done = run_utf8([sys.executable, GATE, "--root", str(good.parents[2]),
                              "--report", str(good)], cwd=str(ROOT))
            self.assertEqual(0, done.returncode, done.stdout + done.stderr)
            self.assertIn("OK —", done.stdout)
        finally:
            shutil.rmtree(str(good_root), ignore_errors=True)

    def test_the_cli_judges_the_shipped_reviewer_set_alone(self):
        done = run_utf8([sys.executable, GATE, "--personas", "--root", str(ROOT)], cwd=str(ROOT))
        self.assertEqual(0, done.returncode, done.stdout + done.stderr)
        self.assertIn("8 goldfish personae", done.stdout)

    def test_a_round_that_admits_its_failed_reviewer_stays_honest(self):
        """The honest version of the same artifact: the round is dirty, so the run still converges."""
        report = seeded(self.root, broken="not_run", rounds=3)
        write(self.root, "03_PROJECTS/reviews/goldfish_review_report.md",
              report.read_text(encoding="utf-8").replace("| 3 | yes |", "| 3 | no |"))
        self.assertEqual(problems_of(self.root, report), [])


class ThePersonaeAreData(unittest.TestCase):
    """A persona is a dispatch contract: stage, range, vectors, a bounded list, three mandates."""

    def setUp(self):
        self.personae, self.read_problems = egm.load_personae(ROOT)

    def test_eight_goldfish_ship_and_none_of_them_writes(self):
        self.assertEqual(8, len(self.personae), sorted(self.personae))
        self.assertEqual(self.read_problems, [], self.read_problems)
        self.assertEqual(egm.check_personae(self.personae), [])
        for name, fm in self.personae.items():
            self.assertEqual("none", fm.get("writes"), name)
            self.assertEqual("fresh_subagent", fm.get("isolation"), name)
            for mandate in egm.MANDATES:
                self.assertIn(mandate, egm.as_list(fm.get("mandates")), name)
            self.assertTrue(egm.as_list(fm.get("vectors")), "%s has nothing to look for" % name)
            self.assertTrue(egm.as_list(fm.get("reads")), "%s has no bounded reading list" % name)

    def test_the_required_stages_have_no_gap(self):
        covered = set()
        for fm in self.personae.values():
            covered.update(egm.persona_stages(fm))
        for stage in egm.REQUIRED_STAGES:
            self.assertIn(stage, covered)

    def test_a_persona_that_can_write_is_not_a_reviewer(self):
        root = house()
        path = root / "11_CONTROL" / "reviewers" / "egm-design.md"
        path.write_text(path.read_text(encoding="utf-8").replace("writes: none", "writes: yes"),
                        encoding="utf-8")
        personae, _ = egm.load_personae(root)
        problems = egm.check_personae(personae)
        self.assertTrue(any("writes must be `none`" in problem for problem in problems), problems)
        shutil.rmtree(str(root), ignore_errors=True)

    def test_a_comprehension_persona_routed_through_a_synthesiser_is_refused(self):
        """The anti-summary safeguard is data: `spawn: direct`, not a sentence in a skill."""
        root = house()
        path = root / "11_CONTROL" / "reviewers" / "egm-comprehension.md"
        path.write_text(path.read_text(encoding="utf-8").replace("spawn: direct",
                                                                "spawn: synthesizer"),
                        encoding="utf-8")
        personae, _ = egm.load_personae(root)
        problems = egm.check_personae(personae)
        self.assertTrue(any("spawned `direct`" in problem for problem in problems), problems)
        shutil.rmtree(str(root), ignore_errors=True)

    def test_the_personae_are_notes_the_repo_can_see_not_registry_ghosts(self):
        """No `kind:` and a clean note contract: definitions with a body, the phase-21 law.

        A file declaring a registry kind with a note-shaped id is enumerated by neither
        contract, and `scripts/frontmatter_check.py` refuses that state on purpose.
        """
        from frontmatter_check import (claims_a_kind, is_registry_record, registry_contract,
                                       validate_note)
        schema = load_json(ROOT / "rules" / "schema.json")
        registry = registry_contract(ROOT)
        seen, problems = set(), []
        for path in iter_notes(ROOT):
            if path.parent.name != "reviewers":
                continue
            seen.add(path.name)
            fm, _body = parse_frontmatter(path.read_text(encoding="utf-8", errors="replace"))
            if claims_a_kind(fm, registry) or is_registry_record(fm, registry):
                problems.append("%s: claims a registry kind" % path.name)
            problems += ["%s: %s" % (path.name, problem) for problem in validate_note(fm, schema)]
        self.assertEqual([], problems)
        self.assertEqual(8, len(seen),
                         "the frontmatter gate cannot see 11_CONTROL/reviewers: %s" % sorted(seen))


class TheDriftReportIsRechecked(unittest.TestCase):
    """A drift report is a claim about two files; the gate opens both before it believes it."""

    def setUp(self):
        self.root = egm.fixture_house()

    def tearDown(self):
        shutil.rmtree(str(self.root), ignore_errors=True)

    def judge(self, report):
        return egm.judge_drift(self.root, report)[0]

    def test_a_scout_that_found_a_script_that_really_went_missing_is_believed(self):
        self.assertEqual(self.judge(egm.fixture_drift(self.root)), [])

    def test_a_drift_row_that_invents_its_claim_is_refused(self):
        report = egm.fixture_drift(self.root)
        write(self.root, "00_START_HERE/START.md", "# START\n\npython scripts/health.py runs it\n")
        problems = self.judge(report)
        self.assertTrue(any("nothing drifted" in problem for problem in problems), problems)

    def test_a_file_called_gone_that_is_still_on_disk_makes_the_report_the_stale_thing(self):
        report = egm.fixture_drift(self.root)
        write(self.root, "scripts/gone_away.py", "# it came back\n")
        problems = self.judge(report)
        self.assertTrue(any("called gone" in problem for problem in problems), problems)

    def test_a_scout_that_rolled_up_forty_directories_without_stopping_is_refused(self):
        problems = self.judge(egm.fixture_drift(self.root, rows=30, directories=40))
        self.assertTrue(any("past 15 it stops" in problem for problem in problems), problems)

    def test_a_drift_report_that_never_records_what_it_read_is_refused(self):
        report = egm.fixture_drift(self.root)
        write(self.root, "00_START_HERE/drift-report.md",
              report.read_text(encoding="utf-8").replace("## Enumeration", "## Notes"))
        problems = self.judge(report)
        self.assertTrue(any("no `## Enumeration` table" in problem for problem in problems),
                        problems)


class TheDraftingSkills(unittest.TestCase):
    """A skill is a promise: the sentence the gate refuses without, and commands that run."""

    MAP = ROOT / "02_WIKI" / "reference_maps" / "elephant-goldfish-to-hades-map.md"
    SURFACES = ("elephant-draft", "goldfish-review", "drift-report")
    # the six EGM lenses, each translated into a constraint this repo actually enforces
    LENSES = ("YAGNI", "Cost / quota / tokens", "UX / ergonomics", "Migration / back-compat",
              "Observability / SRE", "Tech debt")

    def text(self, name):
        return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")

    @staticmethod
    def flat(text):
        """A sentence is verbatim across a line wrap; markdown wrapping is not a changed word."""
        return re.sub(r"\s+", " ", text)

    def test_the_three_skills_are_bodies_not_records(self):
        for name in self.SURFACES:
            fm, _body = parse_frontmatter(self.text(name))
            self.assertEqual(name, fm.get("name"), name)
            self.assertTrue(fm.get("description"), "%s does not say what it is for" % name)
            self.assertIsNone(fm.get("kind"), "%s would become a registry ghost" % name)

    def test_the_isolation_law_is_written_verbatim_where_a_run_can_be_asked_for(self):
        for name in ("goldfish-review", "drift-report"):
            self.assertIn(STOP, self.flat(self.text(name)), "%s softens the stop condition" % name)
        self.assertIn("not a Goldfish review", self.flat(self.text("elephant-draft")))

    def test_the_review_skill_carries_the_split_the_stages_and_the_resolve_words(self):
        text = self.text("goldfish-review")
        for header in egm.SPLIT_HEADERS:
            self.assertIn(header, text)
        for stage in egm.STAGES:
            self.assertIn(stage, text)
        for word in ("CONTEST", "ESCALATE", "PROPOSE FIX", "DECLINE", "<reviewer>-<round>-<n>",
                     "two consecutive clean", "Cap = 5", "did not review",
                     "do not add context only to satisfy a reviewer",
                     "contest a comprehension gap", "do not change a\nseverity"):
            self.assertIn(word, text)

    def test_the_draft_skill_asks_this_repo_and_not_egm(self):
        text = self.text("elephant-draft")
        for lens in self.LENSES:
            self.assertIn(lens, text, "the swarm lost a lens")
        for heading in ("Overview", "Analysis", "Goals vs Non-Goals", "Alternatives Weighed",
                        "Key Decisions", "## Detailed Implementation Plan"):
            self.assertIn(heading, text)
        for constraint in ("standard library", "no network", "approval door", "12_RUNTIME"):
            self.assertIn(constraint, text, "%s is the constraint the lens must carry" % constraint)

    def test_the_drift_skill_sends_the_scout_the_gate_can_check(self):
        text = self.text("drift-report")
        self.assertIn("11_CONTROL/reviewers/egm-explorer.md", text)
        self.assertIn("15 directories", text)
        self.assertIn("reported_to_human", text)
        for verdict in ("gone", "stale", "moved"):
            self.assertIn(verdict, text)
        self.assertIn("python scripts/goldfish_check.py --drift", text)

    def test_every_command_the_skills_run_is_a_script_this_clone_holds(self):
        missing = []
        for name in self.SURFACES:
            for script in re.findall(r"python ([0-9A-Za-z_./-]+\.py)", self.text(name)):
                if not (ROOT / script).is_file():
                    missing.append("%s names %s" % (name, script))
        self.assertEqual([], missing)

    def test_every_path_the_method_names_is_in_this_clone(self):
        """The clone-readable law, applied to the method's own documents."""
        pattern = re.compile(r"`([0-9A-Za-z_.-]+/[0-9A-Za-z_.*/<>-]+\.(?:md|py|json|jsonl))`")
        surfaces = [self.text(name) for name in self.SURFACES]
        surfaces.append(self.MAP.read_text(encoding="utf-8"))
        surfaces += [p.read_text(encoding="utf-8", errors="replace")
                     for p in sorted((ROOT / "11_CONTROL" / "reviewers").glob("*.md"))]
        missing = []
        for text in surfaces:
            for rel in pattern.findall(text):
                if "<" in rel or "*" in rel:
                    continue                      # a template, not a promise
                if not (ROOT / rel).exists():
                    missing.append(rel)
        self.assertEqual([], sorted(set(missing)))

    def test_the_map_is_the_shape_the_other_maps_are(self):
        """Adopt/refuse table, and the script plus the test holding every adopted piece."""
        text = self.MAP.read_text(encoding="utf-8")
        for heading in ("## The verdict in one sentence", "## Adoption table",
                        "## Where each adopted piece lives (script + test)",
                        "## Final folder structure — answer"):
            self.assertIn(heading, text)
        for row in ("skills/elephant-draft/SKILL.md", "11_CONTROL/reviewers/egm-*.md",
                    "scripts/goldfish_check.py", "tests/test_phase43_goldfish_method.py",
                    "skills/drift-report/SKILL.md"):
            self.assertIn(row, text)
        self.assertIn(STOP, self.flat(text))
        self.assertIn("refuse", text.lower())
        self.assertIn("11_CONTROL/agents", text, "the map must state what it did not touch")

