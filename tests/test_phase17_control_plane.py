"""Phase 17 tests — the control plane has inhabitants, and a pointer must open (issue #8).

11_CONTROL used to be seventeen empty folders with a README that promised agents, skills
and loops. An empty registry is a claim: "the machine plane defines the workers" while
nothing is defined. So the skills an agent actually reads are now registered records, and
`doctor` refuses a record whose entrypoint does not exist -- because a definition whose body
is missing is a rumour, and the next agent will act on it.
"""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HADES = ROOT / "15_SYSTEM" / "scripts" / "hades.py"
sys.path.insert(0, str(ROOT / "scripts"))
from common import run_utf8  # noqa: E402

NEW_SKILLS = ("first-session", "memory", "self-audit")


def load_hades():
    spec = importlib.util.spec_from_file_location("hades_under_test", HADES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def records():
    out = []
    for path in sorted((ROOT / "11_CONTROL").rglob("*.json")):
        out.append((path, json.loads(path.read_text(encoding="utf-8"))))
    return out


class TestRegisteredSkills(unittest.TestCase):
    def test_every_skill_in_the_pack_is_a_registry_record(self):
        """Two places describe the same skill only if one of them is the index of the other."""
        bodies = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")}
        registered = {rec.get("name") for _p, rec in records() if rec.get("kind") == "skill"}
        self.assertEqual(sorted(bodies - registered), [],
                         "a skill nobody can find in the registry will never be synced")

    def test_every_skill_record_points_at_a_body_that_exists(self):
        checked = 0
        for path, rec in records():
            if rec.get("kind") != "skill":
                continue
            entry = rec.get("entrypoint") or ""
            checked += 1
            self.assertTrue((ROOT / entry).is_file() or (path.parent / entry).is_file(),
                            "%s points at %s, which is not there" % (rec.get("name"), entry))
        self.assertGreaterEqual(checked, len(NEW_SKILLS) + 7, checked)

    def test_the_three_new_skills_are_registered_and_runnable(self):
        for name in NEW_SKILLS:
            body = (ROOT / "skills" / name / "SKILL.md")
            self.assertTrue(body.is_file(), "%s has no body" % name)
            text = body.read_text(encoding="utf-8")
            self.assertIn("python scripts/", text,
                          "%s describes vibes instead of commands" % name)
            self.assertLessEqual(len(text.splitlines()), 90,
                                 "%s is a manual, not a procedure" % name)

    def test_the_agents_that_do_the_work_have_capabilities_that_exist(self):
        skill_names = {rec.get("name") for _p, rec in records() if rec.get("kind") == "skill"}
        agents = [(p, rec) for p, rec in records() if rec.get("kind") == "agent"]
        self.assertGreaterEqual(len(agents), 2, "no workers are defined, so nothing runs itself")
        for _path, rec in agents:
            for capability in rec.get("capabilities") or []:
                self.assertIn(capability, skill_names,
                              "%s claims %s, which the pack does not have" %
                              (rec.get("name"), capability))


class TestTheEntrypointGate(unittest.TestCase):
    def setUp(self):
        self.hades = load_hades()
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._root = self.hades.ROOT
        self.hades.ROOT = self.tmp
        self.record_dir = self.tmp / "11_CONTROL" / "skills" / "SKL-1-demo"
        self.record_dir.mkdir(parents=True)

    def tearDown(self):
        self.hades.ROOT = self._root
        self._tmp.cleanup()

    def test_a_record_pointing_at_nothing_is_an_error_not_a_warning(self):
        problems = self.hades.check_entrypoints(
            self.record_dir / "skill.json", {"entrypoint": "SKILL.md"})
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("does not exist", problems[0])

    def test_a_body_next_to_the_record_satisfies_it(self):
        (self.record_dir / "SKILL.md").write_text("# demo\n", encoding="utf-8")
        self.assertEqual(self.hades.check_entrypoints(
            self.record_dir / "skill.json", {"entrypoint": "SKILL.md"}), [])

    def test_a_body_at_the_named_path_from_the_root_satisfies_it(self):
        body = self.tmp / "skills" / "demo" / "SKILL.md"
        body.parent.mkdir(parents=True)
        body.write_text("# demo\n", encoding="utf-8")
        self.assertEqual(self.hades.check_entrypoints(
            self.record_dir / "skill.json", {"entrypoint": "skills/demo/SKILL.md"}), [])

    def test_a_record_that_promises_no_file_is_not_judged_for_one(self):
        self.assertEqual(self.hades.check_entrypoints(self.record_dir / "agent.json",
                                                     {"kind": "agent"}), [])

    def test_a_new_skill_registration_finds_the_body_instead_of_inventing_a_default(self):
        slug = self.tmp / "skills" / "demo-two"
        slug.mkdir(parents=True)
        (slug / "SKILL.md").write_text("# demo\n", encoding="utf-8")
        self.assertEqual(self.hades.skill_entrypoint("Demo Two"), "skills/demo-two/SKILL.md")
        self.assertEqual(self.hades.skill_entrypoint("never-written"), "SKILL.md")


class TestTheHouseStillStands(unittest.TestCase):
    def test_doctor_counts_the_new_records_and_stays_green(self):
        result = run_utf8([sys.executable, str(HADES), "doctor"], cwd=str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("errors: 0 | warnings: 0", result.stdout)
        listed = int([line for line in result.stdout.splitlines()
                      if "registry records:" in line][0].split("registry records:")[1])
        self.assertGreaterEqual(listed, len(NEW_SKILLS) + 9, "the registry is still empty")

    def test_the_agent_entrypoint_names_the_first_session_briefing(self):
        """A stranger who only has the URL must be routed to the briefing by every host door."""
        for rel in ("CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md",
                    ".cursor/rules/agents.mdc", ".windsurf/rules/agents.md", "AGENTS.md"):
            text = (ROOT / rel).read_text(encoding="utf-8")
            self.assertIn("skills/first-session/SKILL.md", text,
                          "%s sends an agent nowhere for orientation" % rel)


if __name__ == "__main__":
    sys.exit(unittest.main())
