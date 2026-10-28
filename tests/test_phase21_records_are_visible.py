"""Phase 21 — what `apply` writes, `doctor` must be able to find (issue #13).

`news` and `wiki_note` are declared as file-layout markdown kinds: `target_path` names the
file `<ID>-<slug>.md`, while `iter_records` only admitted a markdown record whose stem was
exactly `note`. Measured in a scratch vault, in this order:

    new --kind wiki_note --name "Note One" --approve   -> APPLIED ... 02_WIKI/concepts/WIK-...-note-one.md
    show --id WIK-<that id>                            -> NOT FOUND
    list --kind wiki_note                              -> records: 0
    doctor                                             -> registry records: 12 | errors: 0

So the registry could be handed a record through its own sanctioned path and then answer
that nothing exists -- and `errors: 0` after that is a silent gate, not a clean house. The
law is already written for JSON at hades.py:172 ("a name-only match would make them invisible
to every gate"); this phase makes the markdown branch obey it.

Enumeration is by content, not by filename: a markdown file is a registry record when its
frontmatter carries a registry-shaped `id` *and* a declared `kind`. A record body
(`OVERVIEW.md`, `SKILL.md`) carries the same id with `type: note` and no `kind`, so it stays
a body -- otherwise the naive fix would report every record twice and call the house broken.
"""
import glob
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hades_fixture import catalog, hades_json, seeded  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def registry_shaped_ids(vault):
    """Every id the gates can see, straight from `list`."""
    _code, out = vault.hades("list")
    return set(re.findall(r"\b([A-Z]{3}-[0-9A-F]{8})\b", out))


class TestAMarkdownRecordIsVisible(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()

    def tearDown(self):
        self.vault.close()

    def create(self, *args):
        code, out = self.vault.hades("new", *args, "--approve")
        self.assertEqual(code, 0, out)
        return re.search(r"\b([A-Z]{3}-[0-9A-F]{8})\b", out).group(1)

    def test_an_applied_wiki_note_is_visible_to_show_list_index_and_doctor(self):
        ident = self.create("--kind", "wiki_note", "--name", "Note One",
                            "--description", "fixture", "--category", "concept")
        shown, _out = hades_json(self.vault, "show", "--id", ident)
        self.assertEqual(shown.get("kind"), "wiki_note", shown)
        self.assertIn(ident, registry_shaped_ids(self.vault),
                      "`list` cannot see a record `apply` just wrote")
        code, out = self.vault.hades("doctor")
        _code, index_out = self.vault.hades("index")
        self.assertIn("indexed", index_out, index_out)
        cat = catalog(self.vault)
        self.assertIn(ident, [r["id"] for r in cat["records"]],
                      "the index was rebuilt while the record stayed invisible")
        _code, doctor = self.vault.hades("doctor")
        self.assertIn("errors: 0", doctor, doctor)
        self.assertIn("registry records: %d" % len(cat["records"]), doctor,
                      "doctor and the index disagree about how many records exist")

    def test_an_applied_news_record_is_visible_and_keeps_its_provenance(self):
        ident = self.create("--kind", "news", "--name", "Release Note",
                            "--description", "a claim", "--url", "https://example.org/x")
        shown, _out = hades_json(self.vault, "show", "--id", ident)
        self.assertEqual(shown.get("source_url"), "https://example.org/x", shown)
        self.assertIn(ident, registry_shaped_ids(self.vault))

    def test_two_wiki_notes_are_two_records_not_zero(self):
        first = self.create("--kind", "wiki_note", "--name", "Note One",
                            "--description", "a", "--category", "concept")
        second = self.create("--kind", "wiki_note", "--name", "Note Two",
                             "--description", "b", "--category", "concept")
        seen = registry_shaped_ids(self.vault)
        self.assertTrue({first, second} <= seen, seen)
        _code, out = self.vault.hades("list", "--kind", "wiki_note")
        self.assertIn("records: 2", out, out)

    def test_a_relation_on_a_markdown_record_survives_the_write(self):
        """`link` wrote the relation into the dict and `to_markdown` dropped it on the floor."""
        first = self.create("--kind", "wiki_note", "--name", "Note One",
                            "--description", "a", "--category", "concept")
        second = self.create("--kind", "wiki_note", "--name", "Note Two",
                             "--description", "b", "--category", "concept")
        code, out = self.vault.hades("link", "--id", second, "--rel", "depends_on", "--to", first)
        self.assertEqual(code, 0, out)
        shown, _out = hades_json(self.vault, "show", "--id", second)
        self.assertEqual((shown.get("relations") or {}).get("depends_on"), [first], shown)

    def test_a_doctor_error_in_a_markdown_record_is_not_silently_unchecked(self):
        """Visibility has to cut both ways: a broken markdown record must become an error."""
        ident = self.create("--kind", "wiki_note", "--name", "Note One",
                            "--description", "a", "--category", "concept")
        path = next(Path(self.vault.root).glob("02_WIKI/**/%s*.md" % ident))
        text = path.read_text(encoding="utf-8")
        path.write_text(text.replace("classification: \"internal\"", "classification: \"leaked\""),
                        encoding="utf-8")
        code, out = self.vault.hades("doctor")
        self.assertEqual(code, 1, out)
        self.assertIn("classification", out, out)


class TestABodyIsNotASecondRecord(unittest.TestCase):
    def setUp(self):
        self.vault = seeded()

    def tearDown(self):
        self.vault.close()

    def test_record_bodies_do_not_count_as_records(self):
        """OVERVIEW.md carries its record's id with `type: note`; it is a body, not a twin."""
        _code, before = self.vault.hades("doctor")
        records_before = int(re.search(r"registry records: (\d+)", before).group(1))
        code, out = self.vault.hades("new", "--kind", "wiki_note", "--name", "Note One",
                                     "--description", "a", "--category", "concept", "--approve")
        self.assertEqual(code, 0, out)
        _code, after = self.vault.hades("doctor")
        self.assertEqual(int(re.search(r"registry records: (\d+)", after).group(1)),
                         records_before + 1, after)
        _code, doctor = self.vault.hades("doctor")
        self.assertIn("errors: 0", doctor, doctor)

    def test_ordinary_notes_never_enter_the_registry(self):
        human_note = self.vault.root / "02_WIKI" / "concepts" / "plain-note.md"
        human_note.parent.mkdir(parents=True, exist_ok=True)
        human_note.write_text("---\nid: plain-note\ntype: note\ntitle: Plain\nstatus: raw\n"
                              "owner: human\ncreated: 2026-01-01\nupdated: 2026-01-01\n"
                              "topics: [concept]\n---\n\nbody\n", encoding="utf-8")
        seen = registry_shaped_ids(self.vault)
        self.assertNotIn("plain-note", seen)
        _code, doctor = self.vault.hades("doctor")
        self.assertIn("errors: 0", doctor, doctor)


class TestWriteAndEnumerateAgree(unittest.TestCase):
    """`target_path` decides where a record lands; `iter_records` decides what counts as one.

    These two are written ten lines apart in the same file and they disagreed. In the
    published repo nothing was lost (measured: zero markdown files carry a registry-shaped
    id), so the test is a tripwire against the next disagreement, not proof of damage.
    """

    def load(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "hades_under_test", str(ROOT / "15_SYSTEM" / "scripts" / "hades.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_every_markdown_record_on_disk_is_enumerated(self):
        hades = self.load()
        cfg = hades.config()
        kinds = {k["kind"] for k in cfg["kinds"]}
        expected = set()
        for path in glob.glob(str(ROOT / "**" / "*.md"), recursive=True):
            rel = Path(path).relative_to(ROOT).as_posix()
            if any(rel.startswith(p) for p in ("12_RUNTIME/", "13_LAB/", "15_SYSTEM/generated/",
                                               "15_SYSTEM/backups/", "vault-template/",
                                               "14_CANDIDATES/loop/probes/")):
                continue
            fm = hades.frontmatter(Path(path))
            if not fm:
                continue
            if re.match(r"^[A-Z]{3}-[0-9A-F]{8}$", str(fm.get("id") or "")) \
                    and fm.get("kind") in kinds:
                expected.add(rel)
        seen = {hades.rel(p) for p, _r in hades.iter_records(cfg) if p.suffix == ".md"}
        self.assertEqual(sorted(expected - seen), [],
                         "these markdown records exist but no gate can see them")

    def test_the_law_is_written_in_the_canon(self):
        canon = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("iter_records", canon,
                      "the enumeration law is nowhere an agent will read it")


if __name__ == "__main__":
    unittest.main()
