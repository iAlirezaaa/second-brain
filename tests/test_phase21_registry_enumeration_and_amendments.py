"""Phase 21 tests — what `apply` writes, every gate enumerates; a wrong record is amendable.

Issue #13: news and wiki_note (markdown-layout kinds) were written by `apply` as
<ID>-<slug>.md, but `iter_records` admitted a markdown record only when its stem was
"note" — so the tools wrote records the registry could never see again, and `doctor`
reported `errors: 0` while doing it. Enumeration now matches on content (a frontmatter
id shaped like a registry id, plus a declared kind), so the two layouts agree and a
human note never sneaks into the registry.

Issue #12: the registry was create-only — a wrong title could only be "fixed" by filing
a second record for the same thing — and `supersedes` was declared in system.json with
a meaning nothing enforced (both records stayed in the active index, doctor stayed
quiet). `hades.py edit` now plans an amendment, `apply --approve` writes it, identity
fields are immutable by edit, and a superseded record really leaves the active index.
"""
import contextlib
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HADES = ROOT / "15_SYSTEM" / "scripts" / "hades.py"


def load_hades():
    spec = importlib.util.spec_from_file_location("hades_phase21", HADES)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fit_record(vault_id, payload=None):
    base = {"id": vault_id, "kind": "wiki_note", "name": "Human Plane Defender",
            "status": "draft", "classification": "internal",
            "created_at": "2026-10-27", "topic": "concept", "tags": []}
    base.update(payload or {})
    return base


class TempVault:
    """A throwaway registry: real config and schema, zero real records."""

    def setUp(self):
        self.hades = load_hades()
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        shutil.copytree(ROOT / "15_SYSTEM" / "config", self.root / "15_SYSTEM" / "config")
        shutil.copytree(ROOT / "15_SYSTEM" / "schemas", self.root / "15_SYSTEM" / "schemas")
        (self.root / "02_WIKI" / "concepts").mkdir(parents=True)
        # a minimal doctor-green house: every ungitignored zone exists with its README,
        # and .gitignore states the machine-plane boundary the config requires
        cfg = json.loads((ROOT / "15_SYSTEM/config/system.json").read_text(encoding="utf-8"))
        (self.root / ".gitignore").write_text("\n".join(cfg["gitignore_required_paths"]) + "\n",
                                              encoding="utf-8")
        for z in cfg["zones"]:
            if z["dir"] in ("12_RUNTIME", "13_LAB"):
                continue  # absent at the documented git boundary by design
            d = self.root / z["dir"]
            d.mkdir(parents=True, exist_ok=True)
            (d / "README.md").write_text("# zone %s\n" % z["dir"], encoding="utf-8")
        h = self.hades
        self._saved = (h.ROOT, h.CONFIG_PATH, h.SCHEMA_PATH, h.GEN, h.PLANS, h.KIND_NAMES)
        h.ROOT = self.root
        h.CONFIG_PATH = self.root / "15_SYSTEM/config/system.json"
        h.SCHEMA_PATH = self.root / "15_SYSTEM/schemas/manifest.schema.json"
        h.GEN = self.root / "15_SYSTEM/generated"
        h.PLANS = h.GEN / "plans"
        h.KIND_NAMES = None

    def tearDown(self):
        h = self.hades
        h.ROOT, h.CONFIG_PATH, h.SCHEMA_PATH, h.GEN, h.PLANS, h.KIND_NAMES = self._saved
        self._tmp.cleanup()

    def cli(self, *argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = self.hades.main(list(argv))
        return code, buf.getvalue()

    def new_wiki_note(self, name):
        code, out = self.cli("new", "--kind", "wiki_note", "--name", name,
                             "--description", "body", "--approve")
        self.assertEqual(0, code, out)
        row = [ln for ln in out.splitlines() if ln.startswith("APPLIED WIK-")][0]
        return row.split()[1]

    def records(self):
        return {r.get("id"): (p, r) for p, r in self.hades.iter_records(self.hades.config())}

    def bytes_of(self, wid):
        for p, r in self.hades.iter_records(self.hades.config()):
            if r.get("id") == wid:
                return p, p.read_bytes()
        raise AssertionError("record %s vanished from enumeration" % wid)

    def catalog(self):
        return json.loads((self.hades.GEN / "catalog.json").read_text(encoding="utf-8"))


class TestMarkdownRecordsStayEnumerable(TempVault, unittest.TestCase):
    """Issue #13: the file `apply` just wrote must be visible to every command."""

    def setUp(self):
        TempVault.setUp(self)

    def tearDown(self):
        TempVault.tearDown(self)

    def test_a_wiki_note_apply_wrote_is_seen_by_every_command(self):
        wid = self.new_wiki_note("Gates Law")
        path, _ = self.bytes_of(wid)
        self.assertTrue(path.as_posix().endswith(".md"))
        code, out = self.cli("show", "--id", wid)
        self.assertEqual(0, code, out)
        self.assertIn(wid, out)
        code, out = self.cli("list", "--kind", "wiki_note")
        self.assertEqual(0, code, out)
        self.assertIn("records: 1", out)
        self.assertIn(wid, out)
        code, out = self.cli("index")
        self.assertEqual(0, code, out)
        catalog = self.catalog()
        ids = [row["id"] for row in catalog["records"]]
        self.assertEqual([wid], ids)
        self.assertEqual(1, catalog["count"])
        code, out = self.cli("doctor")
        self.assertEqual(0, code, out)
        self.assertIn("errors: 0 | warnings: 0", out)
        self.assertIn("registry records: 1", out)

    def test_a_news_record_apply_wrote_is_seen_by_every_command(self):
        code, out = self.cli("new", "--kind", "news", "--name", "Claim Shelf",
                             "--description", "a claim with a source",
                             "--url", "https://example.com/proof", "--approve")
        self.assertEqual(0, code, out)
        nid = [ln.split()[1] for ln in out.splitlines() if ln.startswith("APPLIED NWS-")][0]
        for argv in (("show", "--id", nid),
                     ("list", "--kind", "news")):
            code, res = self.cli(*argv)
            self.assertEqual(0, code, res)
            self.assertIn(nid, res)
        code, res = self.cli("doctor")
        self.assertEqual(0, code, res)
        self.assertIn("errors: 0 | warnings: 0", res)

    def test_enumeration_matches_on_content_not_on_a_filename(self):
        wid = self.new_wiki_note("Renamed On Disk")
        path, _ = self.bytes_of(wid)
        path.rename(path.with_name("a-completely-different-name.md"))
        code, out = self.cli("show", "--id", wid)
        self.assertEqual(0, code, out)
        self.assertIn(wid, out)

    def test_human_plane_notes_stay_out_of_the_registry(self):
        wid = self.new_wiki_note("Baseline Note")
        human = self.root / "02_WIKI/concepts/human-entry.md"
        human.write_text("---\nid: wikipage-42\ntype: note\ntitle: ordinary note\n"
                         "---\n\n# ordinary note\n", encoding="utf-8")
        # the OVERVIEW.md shape: a registry-shaped id with no declared kind
        registrar = self.root / "02_WIKI/concepts/WIK-99999999-similar.md"
        registrar.write_text("---\nid: \"WIK-99999999\"\ntype: project\ntitle: body copy\n"
                             "---\n\n# body copy\n", encoding="utf-8")
        ids = set(self.records())
        self.assertEqual({wid}, ids, "an ordinary note became a registry record")
        code, out = self.cli("doctor")
        self.assertEqual(0, code, out)
        self.assertIn("errors: 0 | warnings: 0", out)


class TestRegistryAmendments(TempVault, unittest.TestCase):
    """Issue #12: correct a record through the same door that created it."""

    def setUp(self):
        TempVault.setUp(self)
        self.wid = self.new_wiki_note("Gates Law")
        self.path, _bytes = self.bytes_of(self.wid)

    def tearDown(self):
        TempVault.tearDown(self)

    def test_edit_of_an_unenumerated_record_is_refused(self):
        code, out = self.cli("edit", "--id", "WIK-DEADBEEF", "--set", "name=x")
        self.assertEqual(2, code, out)
        self.assertIn("REFUSED", out)

    def test_an_amendment_round_trips_through_plan_and_apply(self):
        code, out = self.cli("edit", "--id", self.wid, "--set", "name=Gates Law Renamed")
        self.assertEqual(0, code, out)
        plan_id = [ln.split()[1] for ln in out.splitlines()
                   if ln.startswith("PLAN ")][0]
        plan = json.loads((self.hades.PLANS / ("%s.json" % plan_id)).read_text(encoding="utf-8"))
        self.assertEqual("amend", plan["mode"])
        self.assertEqual({"name": {"old": "Gates Law", "new": "Gates Law Renamed"}}, plan["changes"])
        before = self.bytes_of(self.wid)[1]
        code, out = self.cli("apply", "--plan", plan_id, "--approve")
        self.assertEqual(0, code, out)
        self.assertIn("AMENDED", out)
        _p, rec = list(self.records().values())[0]
        self.assertEqual("Gates Law Renamed", rec["name"])
        self.assertTrue(rec.get("updated_at"), "an amendment must stamp updated_at")
        self.assertNotEqual(before, self.bytes_of(self.wid)[1])
        code, out = self.cli("index")
        self.assertEqual("Gates Law Renamed", self.catalog()["records"][0]["name"])
        code, out = self.cli("doctor")
        self.assertEqual(0, code, out)
        self.assertIn("errors: 0 | warnings: 0", out)

    def test_refused_amendments_change_nothing_on_disk(self):
        snapshot = self.bytes_of(self.wid)[1]
        for value in ("id=WIK-FFFFFFF1", "kind=project", "created_at=2000-01-01",
                      "nams=Gates Law Renamed"):
            code, out = self.cli("edit", "--id", self.wid, "--set", value)
            self.assertEqual(2, code, out)
            self.assertIn("REFUSED", out, out)
        self.assertEqual(snapshot, self.bytes_of(self.wid)[1],
                         "a refused amendment must leave the disk untouched")

    def test_an_amendment_breaking_the_contract_is_refused_at_the_plan(self):
        snapshot = self.bytes_of(self.wid)[1]
        code, out = self.cli("edit", "--id", self.wid, "--set", "classification=topless")
        self.assertEqual(2, code, out)
        self.assertIn("REFUSED", out)
        self.assertIn("classification", out)
        self.assertEqual(snapshot, self.bytes_of(self.wid)[1])

    def test_a_markdown_record_keeps_its_fields_over_link_and_amendment(self):
        wid2 = self.new_wiki_note("Second Law")
        code, out = self.cli("link", "--id", wid2, "--rel", "supersedes", "--to", self.wid)
        self.assertEqual(0, code, out)
        _p, rec = self.records()[wid2]
        self.assertEqual("wiki_note", rec.get("kind"), "the link rewrite dropped the record's kind")
        self.assertEqual([self.wid], (rec.get("relations") or {}).get("supersedes"),
                         "the link rewrite dropped the edge it just added")
        code, out = self.cli("edit", "--id", wid2, "--set", 'tags=["Gates, comma"]')
        self.assertEqual(0, code, out)
        plan_id = [ln.split()[1] for ln in out.splitlines() if ln.startswith("PLAN ")][0]
        self.cli("apply", "--plan", plan_id, "--approve")
        _p, rec = self.records()[wid2]
        self.assertEqual(["Gates, comma"], rec.get("tags"),
                         "the roundtrip re-split a list value")
        self.assertEqual([self.wid], rec.get("relations", {}).get("supersedes"),
                         "the amendment dropped the supersedes edge")


class TestSupersedesIsEnforced(TempVault, unittest.TestCase):
    """Issue #12: the declared meaning of supersedes has to actually hold."""

    def setUp(self):
        TempVault.setUp(self)
        self.old_id = self.new_wiki_note("Old Definition")
        self.new_id = self.new_wiki_note("New Definition")
        code, out = self.cli("link", "--id", self.new_id, "--rel", "supersedes",
                             "--to", self.old_id)
        self.assertEqual(0, code, out)

    def tearDown(self):
        TempVault.tearDown(self)

    def test_a_superseded_record_leaves_the_active_index(self):
        code, out = self.cli("index")
        self.assertEqual(0, code, out)
        self.assertIn("active: 1 | superseded (left the active index): 1", out)
        rows = {row["id"]: row for row in self.catalog()["records"]}
        self.assertEqual(2, self.catalog()["count"], "the file stays, the index still shows it")
        self.assertEqual(1, self.catalog()["active_count"])
        self.assertFalse(rows[self.old_id]["active"])
        self.assertEqual([self.new_id], rows[self.old_id]["superseded_by"])
        self.assertTrue(rows[self.new_id]["active"])

    def test_doctor_names_the_retirement_instead_of_staying_quiet(self):
        code, out = self.cli("doctor")
        self.assertEqual(0, code, out)
        named = [ln for ln in out.splitlines()
                 if "superseded by" in ln and self.old_id in ln and self.new_id in ln]
        self.assertTrue(named, out)
        self.assertIn("errors: 0", out)

    def test_status_counts_one_record_for_one_thing(self):
        code, out = self.cli("status")
        self.assertEqual(0, code, out)
        self.assertIn("registry records: 2", out)
        self.assertIn("active: 1 | superseded (left the active index): 1", out)
        self.assertNotIn("superseded (left the active index): 0", out)


if __name__ == "__main__":
    sys.exit(unittest.main())
