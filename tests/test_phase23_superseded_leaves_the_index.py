"""Phase 23 — `supersedes` does what its contract says (the second half of issue #12).

`15_SYSTEM/config/system.json` declares the relation as "replaces a record; superseded
leaves the active index", and `link` accepted it. Measured, in a replica of the tracked tree:

    link    : linked SKL-15EE69D8 --supersedes--> SKL-316EDC61
    after   : indexed 12 records (0 unreadable) -> 15_SYSTEM/generated/catalog.json
    catalog : count=12  both still active=True
    doctor  : scanned zones: 14 | registry records: 12 | errors: 0 | warnings: 0

Twelve before, twelve after, both ids in the index, nothing printed. So the retirement the
contract promises was a field on a file: the plane kept two definitions of one thing and
reported itself healthy, which is the failure mode this repo's tests exist to catch for every
other law. Now `cmd_index` and `cmd_doctor` honour it.

The boundary that makes this safe: retirement is a *verdict*, not a delete. Nothing is
removed, `list` still enumerates both records, and the index says which one it left out and
who left it out -- so the next agent can read the history instead of guessing from two twins.
"""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hades_fixture import catalog, seeded  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def active_ids(cat):
    return [r["id"] for r in cat["records"]]


class TestSupersededLeavesTheIndex(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()
        self.ids = []
        for name in ("Old Provider", "New Provider"):
            code, out = self.vault.hades("new", "--kind", "organization", "--name", name,
                                         "--description", "fixture", "--approve")
            self.assertEqual(code, 0, out)
            self.ids.append(re.search(r"\b(ORG-[0-9A-F]{8})\b", out).group(1))
        self.older, self.newer = self.ids

    def tearDown(self):
        self.vault.close()

    def supersede(self, older=None, newer=None):
        code, out = self.vault.hades("link", "--id", newer or self.newer, "--rel", "supersedes",
                                     "--to", older or self.older)
        self.assertEqual(code, 0, out)
        return out

    def rebuild(self):
        code, out = self.vault.hades("index")
        self.assertEqual(code, 0, out)
        return catalog(self.vault)

    def test_a_superseded_record_leaves_the_active_index(self):
        self.supersede()
        cat = self.rebuild()
        self.assertNotIn(self.older, active_ids(cat),
                         "the contract says the superseded record leaves the active index")
        self.assertIn(self.newer, active_ids(cat))
        self.assertEqual(cat["count"], len(cat["records"]),
                         "the count and the records disagree about how many are active")

    def test_the_retired_record_is_named_with_who_retired_it(self):
        self.supersede()
        cat = self.rebuild()
        retired = {r["id"]: r for r in cat["superseded"]}
        self.assertIn(self.older, retired, cat)
        self.assertEqual(retired[self.older]["superseded_by"], self.newer, retired[self.older])
        self.assertTrue(retired[self.older]["path"], "a retirement notice with no path to read")

    def test_a_chain_retires_every_predecessor(self):
        self.supersede()  # newer retires older
        code, out = self.vault.hades("new", "--kind", "organization", "--name", "Newest Provider",
                                     "--description", "fixture", "--approve")
        newest = re.search(r"\b(ORG-[0-9A-F]{8})\b", out).group(1)
        self.supersede(older=self.newer, newer=newest)
        cat = self.rebuild()
        self.assertEqual([i for i in (self.older, self.newer, newest) if i in active_ids(cat)],
                         [newest], "only the newest of the chain is active")

    def test_retiring_deletes_nothing_and_the_record_still_lists(self):
        self.supersede()
        self.rebuild()
        code, out = self.vault.hades("list", "--kind", "organization")
        self.assertIn("records: 3", out, out)
        bodies = list(Path(self.vault.root, "04_INTELLIGENCE").rglob("organization.json"))
        self.assertEqual(len(bodies), 3,
                         "retirement removed bytes; it was only ever meant to leave the index")

    def test_doctor_names_the_retirement_instead_of_silently_double_counting(self):
        self.supersede()
        cat = self.rebuild()
        code, out = self.vault.hades("doctor")
        self.assertEqual(code, 0, out)
        self.assertIn("superseded", out, out)
        self.assertIn(self.older, out, out)
        active = int(re.search(r"registry records: (\d+)", out).group(1))
        self.assertEqual(active, len(cat["records"]),
                         "doctor and the index count different things and call both healthy")


class TestRetirementThatCannotBeTrusted(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()
        code, out = self.vault.hades("new", "--kind", "organization", "--name", "Old Provider",
                                     "--description", "fixture", "--approve")
        self.older = re.search(r"\b(ORG-[0-9A-F]{8})\b", out).group(1)

    def tearDown(self):
        self.vault.close()

    def test_a_record_that_supersedes_itself_is_an_error_not_a_relativity_trick(self):
        code, out = self.vault.hades("link", "--id", self.older, "--rel", "supersedes",
                                     "--to", self.older)
        self.assertEqual(code, 0, out)
        code, doctor = self.vault.hades("doctor")
        self.assertEqual(code, 1, doctor)
        self.assertIn("itself", doctor, doctor)


class TestTheContractAndTheCodeAgree(unittest.TestCase):
    def test_the_declared_meaning_of_supersedes_is_a_law_not_a_comment(self):
        cfg = json.loads((ROOT / "15_SYSTEM" / "config" / "system.json").read_text(encoding="utf-8"))
        meaning = cfg["relations"]["supersedes"]
        self.assertIn("active index", meaning, meaning)
        # and the code honours the sentence it declares, in the same words:
        vault = seeded()
        try:
            ids = []
            for name in ("Old Provider", "New Provider"):
                _code, out = vault.hades("new", "--kind", "organization", "--name", name,
                                         "--description", "fixture", "--approve")
                ids.append(re.search(r"\b(ORG-[0-9A-F]{8})\b", out).group(1))
            vault.hades("link", "--id", ids[1], "--rel", "supersedes", "--to", ids[0])
            vault.hades("index")
            self.assertNotIn(ids[0], active_ids(catalog(vault)),
                             "the config says %r; the index still lists it" % meaning)
        finally:
            vault.close()

    def test_the_law_is_written_in_the_canon(self):
        canon = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("supersedes", canon)
        self.assertIn("active index", canon)


if __name__ == "__main__":
    unittest.main()
