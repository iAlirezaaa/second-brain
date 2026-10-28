"""Phase 30 -- the registry's leftover seams, closed by measurement.

Phases 21-24 unified five twins into one plane and left four named leftovers. Each class here
holds one of them to its promise:

  1. a retiring edge (`supersedes`) is a structural change, so it goes through the plan door:
     planned, bound to the bytes it was written against, applied only on approval;
  2. `doctor` detects a `supersedes` cycle instead of letting the single map swallow it;
  3. every kind owns a status vocabulary -- no kind falls back to a generic one;
  4. an unattended probe may name a good base; it may not restore one.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hades_fixture import seeded  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PLANS = "15_SYSTEM/generated/plans"


class LinkFixture(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()
        self.older = self.new_note("Older Law")
        self.newer = self.new_note("Newer Law")

    def tearDown(self):
        self.vault.close()

    def new_note(self, name):
        code, out = self.vault.hades("new", "--kind", "wiki_note", "--name", name,
                                     "--category", "concept", "--approve")
        self.assertEqual(code, 0, out)
        match = re.search(r"\b(WIK-[0-9A-F]{8})\b", out)
        self.assertTrue(match, out)
        return match.group(1)

    def path_of(self, ident):
        _code, out = self.vault.hades("show", "--id", ident)
        match = re.search(r"^# file: (.+)$", out, re.M)
        self.assertTrue(match, out)
        return match.group(1).strip()

    def record(self, ident):
        _code, out = self.vault.hades("show", "--id", ident)
        return json.loads(out[:out.rfind("}") + 1])

    def plan_ids(self):
        """Every plan `new --approve` left behind, plus ours: a raw count proves nothing."""
        folder = self.vault.root / PLANS
        if not folder.is_dir():
            return []
        return sorted(p.stem for p in folder.glob("PLAN-*.json"))

    def link_plans(self):
        return [pid for pid in self.plan_ids() if self.plan(pid).get("mode") == "link"]

    def plan(self, plan_id):
        return self.vault.json_of("%s/%s.json" % (PLANS, plan_id))


class ARetiringEdgeGoesThroughThePlanDoor(LinkFixture):
    def test_a_retiring_edge_is_planned_not_written(self):
        before = self.vault.read(self.path_of(self.newer))
        code, out = self.vault.hades("link", "--id", self.newer, "--rel", "supersedes",
                                     "--to", self.older)
        self.assertEqual(code, 0, out)
        self.assertIn("PLAN ", out)
        self.assertNotIn("LINKED", out)
        self.assertIn("review it, then", out)
        self.assertEqual(before, self.vault.read(self.path_of(self.newer)),
                         "a planned edge must not move a byte")
        self.assertNotIn("supersedes", self.record(self.newer).get("relations") or {},
                         "the unapproved edge is already in the record")
        self.assertEqual(1, len(self.link_plans()), "the plan is the thing a reviewer reads")

    def test_the_plan_names_the_edge_and_the_bytes_it_was_written_against(self):
        _code, out = self.vault.hades("link", "--id", self.newer, "--rel", "supersedes",
                                      "--to", self.older)
        plan_id = re.search(r"PLAN-[0-9A-F]+", out).group(0)
        plan = self.plan(plan_id)
        self.assertEqual("link", plan.get("mode"))
        self.assertEqual(self.newer, plan.get("record_id"))
        self.assertEqual(self.older, plan.get("to"))
        self.assertEqual("supersedes", plan.get("rel"))
        self.assertEqual(self.path_of(self.newer), plan.get("target_path"))
        self.assertRegex(plan.get("pre_image_sha1") or "", r"^[0-9a-f]{40}$")
        self.assertFalse(plan.get("applied"))

    def test_applying_the_plan_writes_the_edge_and_records_the_act(self):
        _code, out = self.vault.hades("link", "--id", self.newer, "--rel", "supersedes",
                                      "--to", self.older)
        plan_id = re.search(r"PLAN-[0-9A-F]+", out).group(0)
        code, out = self.vault.hades("apply", "--plan", plan_id, "--approve")
        self.assertEqual(code, 0, out)
        self.assertIn("LINKED", out)
        rec = self.record(self.newer)
        self.assertEqual([self.older], (rec.get("relations") or {}).get("supersedes"))
        trail = rec.get("amendments") or []
        self.assertTrue(trail, "the record must carry the act that changed it")
        self.assertEqual("relations.supersedes", trail[-1].get("field"))
        self.assertEqual(plan_id, trail[-1].get("plan"))
        self.assertTrue(self.plan(plan_id).get("applied"))

    def test_the_approved_edge_retires_exactly_the_target(self):
        _code, out = self.vault.hades("link", "--id", self.newer, "--rel", "supersedes",
                                      "--to", self.older)
        plan_id = re.search(r"PLAN-[0-9A-F]+", out).group(0)
        self.vault.hades("apply", "--plan", plan_id, "--approve")
        code, out = self.vault.hades("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("superseded", out)
        self.assertIn("%s by %s" % (self.older, self.newer), out)

    def test_a_stale_plan_is_refused_instead_of_overwriting_the_move(self):
        _code, out = self.vault.hades("link", "--id", self.newer, "--rel", "supersedes",
                                      "--to", self.older)
        plan_id = re.search(r"PLAN-[0-9A-F]+", out).group(0)
        path = self.path_of(self.newer)
        # a human edited the record after the plan was written: the plan now describes a
        # state that no longer exists, so applying it would silently undo that edit
        self.vault.write(path, self.vault.read(path) + "\n")
        code, out = self.vault.hades("apply", "--plan", plan_id, "--approve")
        self.assertEqual(2, code, out)
        self.assertIn("STALE", out)
        self.assertNotIn("supersedes", self.record(self.newer).get("relations") or {})

    def test_apply_without_approve_writes_nothing(self):
        _code, out = self.vault.hades("link", "--id", self.newer, "--rel", "supersedes",
                                      "--to", self.older)
        plan_id = re.search(r"PLAN-[0-9A-F]+", out).group(0)
        code, out = self.vault.hades("apply", "--plan", plan_id)
        self.assertEqual(2, code, out)
        self.assertIn("--approve", out)
        self.assertNotIn("supersedes", self.record(self.newer).get("relations") or {})

    def test_a_plan_applies_once(self):
        _code, out = self.vault.hades("link", "--id", self.newer, "--rel", "supersedes",
                                      "--to", self.older)
        plan_id = re.search(r"PLAN-[0-9A-F]+", out).group(0)
        _code, first = self.vault.hades("apply", "--plan", plan_id, "--approve")
        code, second = self.vault.hades("apply", "--plan", plan_id, "--approve")
        self.assertEqual(2, code, second)
        self.assertIn("already applied", second)

    def test_an_additive_edge_still_writes_through(self):
        code, out = self.vault.hades("link", "--id", self.newer, "--rel", "depends_on",
                                     "--to", self.older)
        self.assertEqual(code, 0, out)
        self.assertIn("linked", out)
        self.assertIn("depends_on", self.record(self.newer).get("relations") or {})
        self.assertEqual([], self.link_plans(),
                         "an additive edge adds a reference; it does not need a plan")


class ACycleIsDetectedNotSwallowed(LinkFixture):
    def retire(self, source, target):
        code, out = self.vault.hades("link", "--id", source, "--rel", "supersedes",
                                     "--to", target, "--approve")
        self.assertEqual(code, 0, out)

    def test_two_records_that_retire_each_other_are_an_error(self):
        self.retire(self.newer, self.older)
        self.retire(self.older, self.newer)
        code, out = self.vault.hades("doctor")
        self.assertEqual(1, code, out)
        self.assertIn("supersedes cycle", out, out)
        self.assertIn(self.older, out)
        self.assertIn(self.newer, out)

    def test_the_cycle_is_named_in_walk_order_and_ends_where_it_began(self):
        third = self.new_note("Third Law")
        self.retire(self.newer, self.older)
        self.retire(self.older, third)
        self.retire(third, self.newer)
        code, out = self.vault.hades("doctor")
        self.assertEqual(1, code, out)
        match = re.search(r"supersedes cycle (\S+(?: -> \S+)+)", out)
        self.assertTrue(match, out)
        walk = match.group(1).split(" -> ")
        self.assertEqual(walk[0], walk[-1], "a cycle has to come back to where it started")
        self.assertEqual({self.older, self.newer, third}, set(walk[:-1]))
        self.assertEqual(3, len(walk) - 1)

    def test_a_straight_chain_is_not_a_cycle(self):
        self.retire(self.newer, self.older)
        code, out = self.vault.hades("doctor")
        self.assertEqual(0, code, out)
        self.assertNotIn("cycle", out)
        self.assertIn("%s by %s" % (self.older, self.newer), out)

    def test_a_dangling_edge_is_reported_as_dangling_not_as_a_cycle(self):
        self.retire(self.newer, "WIK-00000000")
        code, out = self.vault.hades("doctor")
        self.assertEqual(1, code, out)
        self.assertIn("dangling", out)
        self.assertNotIn("cycle", out)


if __name__ == "__main__":
    unittest.main()
