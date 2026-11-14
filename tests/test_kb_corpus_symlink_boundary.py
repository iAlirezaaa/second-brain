"""KB ingestion must never dereference aliased Markdown outside its own note tree.

Each fixture is disposable; the outside sentinel is synthetic, never user data.
"""
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import kb  # noqa: E402


class KbCorpusAliases(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.root = self.base / "brain"
        self.notes = self.root / "02_WIKI"
        self.notes.mkdir(parents=True)
        self.real = self.notes / "real.md"
        self.real.write_text("# Local note\nLOCALORCHID is a synthetic note.\n",
                             encoding="utf-8")

    def link(self, name, target, directory=False):
        dest = self.notes / name
        try:
            dest.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError):
            if os.name == "nt":
                self.skipTest("this Windows runner cannot create symbolic links")
            raise
        return dest

    def indexed(self):
        return {rel for rel, _path in kb.corpus(self.root)}

    def test_ordinary_markdown_is_still_indexed_and_searchable(self):
        self.assertIn("02_WIKI/real.md", self.indexed())
        self.assertEqual(0, kb.ingest(self.root))
        self.assertEqual(["02_WIKI/real.md"],
                         [hit["path"] for hit in kb.find(self.root, "LOCALORCHID")])

    def test_external_file_symlink_is_never_ingested(self):
        outside = self.base / "outside.md"
        outside.write_text("# Outside\nEXTERNALCANARY synthetic only.\n", encoding="utf-8")
        self.link("alias.md", outside)
        self.assertNotIn("02_WIKI/alias.md", self.indexed())
        self.assertEqual(0, kb.ingest(self.root))
        self.assertEqual([], kb.find(self.root, "EXTERNALCANARY"))

    def test_in_root_alias_is_not_a_second_note(self):
        self.link("alias.md", self.real)
        self.assertEqual({"02_WIKI/real.md"}, self.indexed())
        self.assertEqual(0, kb.ingest(self.root))

    def test_broken_symlink_does_not_crash_ingest(self):
        self.link("missing.md", self.base / "not-here.md")
        self.assertNotIn("02_WIKI/missing.md", self.indexed())
        self.assertEqual(0, kb.ingest(self.root))
        self.assertEqual(["02_WIKI/real.md"],
                         [hit["path"] for hit in kb.find(self.root, "LOCALORCHID")])

    def test_aliased_parent_directory_is_rejected_even_if_walked(self):
        outside_dir = self.base / "elsewhere"
        outside_dir.mkdir()
        outside_note = outside_dir / "note.md"
        outside_note.write_text("# Elsewhere\nPARENTALIAS synthetic only.\n",
                                encoding="utf-8")
        linked = self.link("shortcut", outside_dir, directory=True)
        # Some Python versions do not descend into directory symlinks. Model
        # a walker that does, so the boundary is tested on all supported versions.
        with patch.object(kb, "iter_markdown",
                          return_value=[self.real, linked / "note.md"]):
            self.assertEqual({"02_WIKI/real.md"}, self.indexed())

        # The derived SQLite index is not trusted input: aliases to another
        # database must be refused BEFORE sqlite3.connect or table resets.
        foreign_cache = self.base / "external-cache"
        foreign_cache.mkdir()
        foreign_db = foreign_cache / "kb.sqlite"
        with sqlite3.connect(str(foreign_db)) as conn:
            conn.execute("CREATE TABLE sentinel (value TEXT)")
            conn.execute("INSERT INTO sentinel VALUES ('unchanged')")
        before = foreign_db.read_bytes()

        cache_dir = self.root / ".kb"
        cache_dir.symlink_to(foreign_cache, target_is_directory=True)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            kb.ingest(self.root)
        self.assertEqual(before, foreign_db.read_bytes())
        cache_dir.unlink()

        cache_dir.mkdir()
        link = cache_dir / "kb.sqlite"
        link.symlink_to(foreign_db)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            kb.ingest(self.root)
        self.assertEqual(before, foreign_db.read_bytes())

        # A dangling alias must not become a newly created outside database.
        link.unlink()
        missing = self.base / "must-not-create.sqlite"
        link.symlink_to(missing)
        with self.assertRaisesRegex(RuntimeError, "symlink"):
            kb.ingest(self.root)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
