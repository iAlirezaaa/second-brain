"""Phase 27 tests — the brain searches its own corpus, not its template.

Phase 4's golden gate asks whether `kb.py` ranks well. These tests ask the prior
questions: which files are corpus at all, does the same walk work in an installed home
and in this repo, and does the index refuse a stale corpus instead of answering from it.
"""
import json
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import kb  # noqa: E402
from common import clone_readable  # noqa: E402


def note(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class CorpusBoundary(unittest.TestCase):
    def setUp(self):
        self.rels = [rel for rel, _path in kb.corpus(ROOT)]

    def test_the_corpus_is_clone_readable_and_human_plane(self):
        self.assertGreaterEqual(len(self.rels), 40, self.rels)
        for rel in self.rels:
            self.assertTrue(clone_readable(rel), "%s is not in a clone" % rel)
            self.assertFalse(rel.startswith(kb.MACHINE_PLANE), "%s is machine plane" % rel)
            self.assertFalse(rel.startswith(kb.NOT_CORPUS), "%s is the template" % rel)

    def test_the_repo_documents_are_corpus(self):
        for rel in ("AGENTS.md", "HANDOFF.md", "ROADMAP.md",
                    "00_START_HERE/PROJECT_CHARTER.md",
                    "02_WIKI/reference_maps/eight-memory-planes.md",
                    "skills/kb-search/SKILL.md"):
            self.assertIn(rel, self.rels)

    def test_the_doors_the_template_and_the_machine_plane_are_not(self):
        for rel in ("CLAUDE.md", "GEMINI.md", ".github/copilot-instructions.md",
                    ".cursor/rules/agents.mdc", ".windsurf/rules/agents.md",
                    "vault-template/index.md", "vault-template/AGENTS.md",
                    "15_SYSTEM/memory/README.md", "14_CANDIDATES/README.md"):
            self.assertNotIn(rel, self.rels, rel)

    def test_a_gitignored_note_is_not_shared_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            note(tmp, "12_RUNTIME/run.md", "scratch")
            note(tmp, ".brain-data/source.md", "raw import")
            note(tmp, "20_Notes/kept.md", "a real note")
            self.assertEqual([rel for rel, _ in kb.corpus(tmp)], ["20_Notes/kept.md"])


class InstalledHome(unittest.TestCase):
    """install.py copies vault-template to the home root: zones sit at the top."""

    def test_zones_at_the_root_are_indexed_with_their_zone(self):
        with tempfile.TemporaryDirectory() as tmp:
            note(tmp, "10_Projects/launch.md",
                 "---\ntitle: Launch checklist\nupdated: 2026-01-02\n---\n"
                 "# Launch\nBackup before the restore.\n")
            note(tmp, "20_Notes/plain.md", "# Plain note\nNothing to see.\n")
            kb.ingest(tmp)
            hit = kb.find(tmp, "backup", 3)[0]
            self.assertEqual("10_Projects/launch.md", hit["path"])
            self.assertEqual("Launch checklist", hit["title"])
            self.assertEqual("10_Projects", hit["zone"])
            # the snippet is the note's prose, never its frontmatter line
            self.assertNotIn("---", hit["snippet"])
            self.assertIn("Backup before the restore", hit["snippet"])
            plain = kb.find(tmp, "plain", 3)[0]
            self.assertEqual("Plain note", plain["title"], "a document's H1 is its title")

    def test_persian_matches_across_arabic_and_persian_letters(self):
        with tempfile.TemporaryDirectory() as tmp:
            note(tmp, "20_Notes/ml.md", "يادگيري ماشين و مديريت اطلاعات\n")
            kb.ingest(tmp)
            hits = kb.find(tmp, "یادگیری ماشین", 3)
            self.assertEqual(["20_Notes/ml.md"], [hit["path"] for hit in hits])

    def test_the_snippet_keeps_the_original_letters(self):
        with tempfile.TemporaryDirectory() as tmp:
            note(tmp, "20_Notes/case.md", "The CLONE_READABLE boundary is declared once.\n")
            kb.ingest(tmp)
            self.assertIn("CLONE_READABLE", kb.find(tmp, "clone_readable", 1)[0]["snippet"])

    def test_missing_index_is_named_and_not_created_by_a_search(self):
        with tempfile.TemporaryDirectory() as tmp:
            note(tmp, "20_Notes/a.md", "anything\n")
            with self.assertRaises(RuntimeError) as caught:
                kb.find(tmp, "anything")
            self.assertIn("ingest", str(caught.exception))
            self.assertFalse((Path(tmp) / ".kb").exists())

    def test_a_stale_index_is_refused_then_repaired_by_ingest(self):
        with tempfile.TemporaryDirectory() as tmp:
            note(tmp, "20_Notes/a.md", "# A\nrestore the backup\n")
            (Path(tmp) / ".kb").mkdir()
            with closing(sqlite3.connect(str(Path(tmp) / ".kb" / "kb.sqlite"))) as conn:
                conn.execute("CREATE TABLE kb_meta (key TEXT PRIMARY KEY, value TEXT)")
                conn.execute("INSERT INTO kb_meta VALUES ('schema', '1')")
                conn.execute("CREATE TABLE notes (path TEXT PRIMARY KEY, title TEXT, "
                             "zone TEXT, body TEXT, updated TEXT)")
                conn.commit()
            with self.assertRaises(RuntimeError) as caught:
                kb.find(tmp, "backup")
            self.assertIn("older corpus rule", str(caught.exception))
            kb.ingest(tmp)
            self.assertEqual("20_Notes/a.md", kb.find(tmp, "backup", 1)[0]["path"])


class SharedGoldenSet(unittest.TestCase):
    """The same fixture the measured source engine is judged by, run through the KB."""

    def test_every_golden_query_ranks_its_document_first(self):
        fixture = json.loads((ROOT / "tests" / "fixtures" / "retrieval-golden.json")
                             .read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            for doc in fixture["documents"]:
                note(tmp, "20_Notes/%s.md" % doc["name"], doc["text"])
            kb.ingest(tmp)
            misses = []
            for case in fixture["cases"]:
                hits = kb.find(tmp, case["query"], 3)
                got = [hit["path"] for hit in hits]
                expected = "20_Notes/%s.md" % case["expected"]
                if not got or got[0] != expected:
                    misses.append({"query": case["query"], "expected": expected, "got": got})
            self.assertEqual([], misses, misses)


if __name__ == "__main__":
    unittest.main()
