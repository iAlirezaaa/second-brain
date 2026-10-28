"""Phase 22 — the registry is no longer create-only: an applied record can be corrected (issue #12).

The measured defect was the CLI itself:

    $ py -3.10 15_SYSTEM/scripts/hades.py set --id SKL-15EE69D8 --field title --value x
    hades.py: error: argument cmd: invalid choice: 'edit' (choose from 'status', 'doctor', ...)

`11_CONTROL` is the plane an agent reads *before* acting, and the pack's own law makes the
record the definition and the note its body. A create-only definition plane is one that
quietly becomes wrong: the only way to fix a typo, a stale `zone` or a bad `path` was to file
a second record for the same thing -- the duplicate-truth pattern this repo deletes elsewhere.

The contract `set` implements, and what these tests hold it to:

  1. an amendment is an approved structural change, not a file edit: `set` writes a PLAN, and
     `apply --approve` performs it -- the same gate creation goes through;
  2. identity and provenance are immutable (`id`, `kind`, `created_at`): changing those is a
     different record, so the tool refuses rather than pretending to amend;
  3. an amendment that breaks the record's own contract is refused *before* anything is
     written, including one that strands the `entrypoint`;
  4. a plan is bound to the bytes it was written against: if the record moved since the plan
     was made, applying it is refused -- an old measurement is not evidence for a new tree;
  5. every accepted amendment leaves a trail inside the record (`amendments`: field, from, to,
     when) plus `updated_at`, so the next agent can ask how this definition came to be;
  6. retiring a definition is not amending it: that is what `supersedes` is for (phase 23).
"""
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hades_fixture import catalog, hades_json, seeded  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def plan_files(vault):
    return sorted(vault_plans(vault).glob("PLAN-*.json"))


def vault_plans(vault):
    return vault.root / "15_SYSTEM" / "generated" / "plans"


def record_file(vault, ident):
    """Where a record lives, read from the tool's own answer rather than guessed."""
    _code, out = vault.hades("show", "--id", ident)
    assert "NOT FOUND" not in out, out
    return vault.root / out.split("# file:")[-1].strip()


def load_record(vault, ident):
    path = record_file(vault, ident)
    if path.suffix == ".md":
        return _front(path)
    return json.loads(path.read_text(encoding="utf-8"))


def _front(path):
    text = path.read_text(encoding="utf-8")
    block = text[3:text.find("\n---", 3)].strip()
    out = {}
    for line in block.splitlines():
        m = re.match(r"^([A-Za-z_]\w*)\s*:\s*(.*)$", line)
        if m:
            out[m.group(1)] = json.loads(m.group(2)) if m.group(2)[:1] in "[{" else \
                m.group(2).strip("'\"")
    return out


def sha(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()


class TestAnAmendmentIsApprovedNotTyped(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()
        _code, out = self.vault.hades("list", "--kind", "project")
        self.ident = re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)

    def tearDown(self):
        self.vault.close()

    def set(self, *args):
        return self.vault.hades("set", "--id", self.ident, *args)

    def test_set_without_approve_plans_and_changes_nothing(self):
        path = record_file(self.vault, self.ident)
        before = sha(path)
        planned = len(plan_files(self.vault))  # seeding planned and applied three records
        code, out = self.set("--field", "name", "--value", "Renamed Project")
        self.assertEqual(code, 0, out)
        self.assertIn("PLAN", out, out)
        self.assertEqual(sha(path), before, "the record moved before anyone approved")
        self.assertEqual(len(plan_files(self.vault)), planned + 1,
                         "no plan file was written to review")
        plan_id = re.search(r"(PLAN-[0-9A-F]+)", out).group(1)
        plan = json.loads((vault_plans(self.vault) / (plan_id + ".json")).read_text(encoding="utf-8"))
        self.assertEqual(plan.get("mode"), "amend", plan)
        self.assertEqual(plan.get("field"), "name")
        self.assertIn(self.ident, str(plan.get("target_path")), plan)

    def test_apply_amends_the_record_and_stamps_the_audit_trail(self):
        _code, out = self.set("--field", "name", "--value", "Renamed Project")
        plan = re.search(r"(PLAN-[0-9A-F]+)", out).group(1)
        code, applied = self.vault.hades("apply", "--plan", plan, "--approve")
        self.assertEqual(code, 0, applied)
        rec = load_record(self.vault, self.ident)
        self.assertEqual(rec["name"], "Renamed Project", rec)
        trail = rec.get("amendments") or []
        self.assertEqual(len(trail), 1, rec)
        self.assertEqual(trail[0]["field"], "name")
        self.assertNotEqual(trail[0]["from"], trail[0]["to"])
        self.assertTrue(rec.get("updated_at"), "an amendment with no timestamp is untraceable")

    def test_apply_refuses_an_amendment_without_approve(self):
        _code, out = self.set("--field", "name", "--value", "Renamed Project")
        plan = re.search(r"(PLAN-[0-9A-F]+)", out).group(1)
        path = record_file(self.vault, self.ident)
        before = sha(path)
        code, refused = self.vault.hades("apply", "--plan", plan)
        self.assertEqual(code, 2, refused)
        self.assertIn("REFUSED", refused, refused)
        self.assertEqual(sha(path), before, "an unapproved amendment was written anyway")

    def test_applying_twice_amends_once(self):
        _code, out = self.set("--field", "name", "--value", "Renamed Project")
        plan = re.search(r"(PLAN-[0-9A-F]+)", out).group(1)
        self.vault.hades("apply", "--plan", plan, "--approve")
        code, again = self.vault.hades("apply", "--plan", plan, "--approve")
        self.assertEqual(code, 2, again)
        self.assertIn("REFUSED", again, again)
        rec = load_record(self.vault, self.ident)
        self.assertEqual(len(rec.get("amendments") or []), 1, rec)

    def test_set_approve_amends_in_one_step_like_new(self):
        code, out = self.set("--field", "classification", "--value", "public", "--approve")
        self.assertEqual(code, 0, out)
        self.assertIn("AMENDED", out, out)
        self.assertEqual(load_record(self.vault, self.ident)["classification"], "public")


class TestWhatCannotBeAmended(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()
        _code, out = self.vault.hades("list", "--kind", "project")
        self.ident = re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)

    def tearDown(self):
        self.vault.close()

    def test_identity_and_provenance_are_refused(self):
        planned = len(plan_files(self.vault))
        for field, value in (("id", "PRJ-DEADBEEF"), ("kind", "model"),
                             ("created_at", "1999-01-01")):
            code, out = self.vault.hades("set", "--id", self.ident, "--field", field,
                                         "--value", value, "--approve")
            self.assertEqual(code, 2, "%s was amended: %s" % (field, out))
            self.assertIn("REFUSED", out, out)
        self.assertEqual(len(plan_files(self.vault)), planned,
                         "a refused amendment still left a plan behind to be approved later")

    def test_an_amendment_that_breaks_the_contract_is_refused_and_writes_nothing(self):
        path = record_file(self.vault, self.ident)
        before = sha(path)
        code, out = self.vault.hades("set", "--id", self.ident, "--field", "status",
                                     "--value", "shipped", "--approve")
        self.assertEqual(code, 2, out)
        self.assertIn("REFUSED", out, out)
        self.assertEqual(sha(path), before, out)

    def test_an_amendment_that_strands_the_entrypoint_is_refused(self):
        """A definition whose body is missing is a promise, and `set` must not mint one."""
        code, out = self.vault.hades("new", "--kind", "skill", "--name", "Guard Skill",
                                     "--description", "fixture", "--approve")
        self.assertEqual(code, 0, out)
        skill = re.search(r"\b(SKL-[0-9A-F]{8})\b", out).group(1)
        code, refused = self.vault.hades("set", "--id", skill, "--field", "entrypoint",
                                         "--value", "NO-SUCH-BODY.md", "--approve")
        self.assertEqual(code, 2, refused)
        self.assertIn("entrypoint", refused, refused)
        shown, _out = hades_json(self.vault, "show", "--id", skill)
        self.assertNotEqual(shown.get("entrypoint"), "NO-SUCH-BODY.md", shown)

    def test_an_unknown_id_is_refused(self):
        code, out = self.vault.hades("set", "--id", "PRJ-00000000", "--field", "name",
                                     "--value", "x", "--approve")
        self.assertEqual(code, 1, out)
        self.assertIn("no record", out.lower(), out)


class TestAPlanIsBoundToTheBytesItSaw(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()
        _code, out = self.vault.hades("list", "--kind", "project")
        self.ident = re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)

    def tearDown(self):
        self.vault.close()

    def test_an_amendment_planned_against_a_moved_record_is_refused_at_apply(self):
        _code, out = self.vault.hades("set", "--id", self.ident, "--field", "name",
                                      "--value", "Renamed Project")
        plan = re.search(r"(PLAN-[0-9A-F]+)", out).group(1)
        path = record_file(self.vault, self.ident)
        moved = json.loads(path.read_text(encoding="utf-8"))
        moved["notes"] = "someone else edited this record after the plan was made"
        path.write_text(json.dumps(moved, ensure_ascii=False, indent=2), encoding="utf-8")
        code, refused = self.vault.hades("apply", "--plan", plan, "--approve")
        self.assertEqual(code, 2, refused)
        self.assertIn("STALE", refused.upper(), refused)
        self.assertNotIn("Renamed Project", path.read_text(encoding="utf-8"),
                         "a stale plan overwrote work it had never seen")

    def test_the_current_owner_can_still_amend_after_the_move(self):
        _code, out = self.vault.hades("set", "--id", self.ident, "--field", "name",
                                      "--value", "Renamed Project")
        plan = re.search(r"(PLAN-[0-9A-F]+)", out).group(1)
        path = record_file(self.vault, self.ident)
        path.write_text(path.read_text(encoding="utf-8").replace('"notes": "fixture"',
                                                                 '"notes": "touched"'),
                        encoding="utf-8")
        self.vault.hades("apply", "--plan", plan, "--approve")
        code, out = self.vault.hades("set", "--id", self.ident, "--field", "name",
                                     "--value", "Renamed Again", "--approve")
        self.assertEqual(code, 0, out)


class TestTheAmendedRecordIsStillOneRecord(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()
        _code, out = self.vault.hades("list", "--kind", "project")
        self.ident = re.search(r"\b(PRJ-[0-9A-F]{8})\b", out).group(1)

    def tearDown(self):
        self.vault.close()

    def test_catalog_and_doctor_agree_with_an_amended_record(self):
        self.vault.hades("set", "--id", self.ident, "--field", "name",
                         "--value", "Renamed Project", "--approve")
        code, out = self.vault.hades("index")
        self.assertEqual(code, 0, out)
        cat = catalog(self.vault)
        row = [r for r in cat["records"] if r["id"] == self.ident]
        self.assertEqual(len(row), 1, cat)
        self.assertEqual(row[0]["name"], "Renamed Project", row)
        _code, doctor = self.vault.hades("doctor")
        self.assertIn("errors: 0", doctor, doctor)
        self.assertIn("registry records: %d" % len(cat["records"]), doctor, doctor)

    def test_a_markdown_record_can_be_amended_too(self):
        """The record kinds an agent writes most are the markdown ones (phase 21)."""
        code, out = self.vault.hades("new", "--kind", "wiki_note", "--name", "Note One",
                                     "--description", "a", "--category", "concept", "--approve")
        self.assertEqual(code, 0, out)
        ident = re.search(r"\b(WIK-[0-9A-F]{8})\b", out).group(1)
        code, out = self.vault.hades("set", "--id", ident, "--field", "topic",
                                     "--value", "decision", "--approve")
        self.assertEqual(code, 0, out)
        shown, _out = hades_json(self.vault, "show", "--id", ident)
        self.assertEqual(shown["topic"], "decision", shown)
        self.assertEqual(len(shown.get("amendments") or []), 1, shown)
        _code, doctor = self.vault.hades("doctor")
        self.assertIn("errors: 0", doctor, doctor)

    def test_an_amendment_does_not_lose_the_prose_of_a_markdown_record(self):
        """Found by dogfooding: the body was prose only, so rewriting the record rewrote it away.

        `to_markdown` rendered `notes` into the body and the reader parsed only the frontmatter,
        so any write-back (an amendment, a link) silently blanked the paragraph. A record is the
        definition and the note is its body -- the body has to come from a field that survives.
        """
        prose = "the reason we chose a gate instead of a habit"
        code, out = self.vault.hades("new", "--kind", "wiki_note", "--name", "Note Three",
                                     "--description", prose, "--category", "concept", "--approve")
        self.assertEqual(code, 0, out)
        ident = re.search(r"\b(WIK-[0-9A-F]{8})\b", out).group(1)
        path = record_file(self.vault, ident)
        self.assertIn(prose, path.read_text(encoding="utf-8"))
        self.vault.hades("set", "--id", ident, "--field", "topic", "--value", "decision",
                         "--approve")
        text = path.read_text(encoding="utf-8")
        self.assertIn(prose, text, "the amendment deleted the paragraph it was never asked to touch")
        shown, _out = hades_json(self.vault, "show", "--id", ident)
        self.assertEqual(shown.get("notes"), prose, shown)


class TestTheLawIsWrittenWhereAnAgentReadsIt(unittest.TestCase):
    def test_the_canon_states_the_amendment_law(self):
        canon = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("hades.py set", canon,
                      "a mechanism no document names is a mechanism nobody uses")
        self.assertIn("immutable", canon.lower())

    def test_set_is_discoverable_from_the_cli_itself(self):
        vault = seeded()
        try:
            _code, out = vault.hades("set", "--help")
            self.assertIn("--field", out, out)
            self.assertIn("--approve", out, out)
        finally:
            vault.close()


if __name__ == "__main__":
    unittest.main()
