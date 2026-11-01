"""Phase 36, first step -- a dataset built only from sources the owner marked shareable.

No model is trained here and no improvement is claimed. What is measured is the part that
can be checked on its own: every example cites a source id and a byte range that reproduces
its own text, an unmarked source is refused rather than silently included, the manifest
reproduces the run, and two builds of the same records agree byte for byte.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "15_SYSTEM" / "scripts"))
from backend import dataset, sources  # noqa: E402


class DatasetHarness(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.first = self.import_text("chat.txt", "the first conversation about retrieval",
                                      "conversation", "codex:session-1")
        self.second = self.import_text("memo.txt", "a private client memo", "document",
                                       "local:memo")

    def tearDown(self):
        self._tmp.cleanup()

    def import_text(self, name, text, kind, origin):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return sources.ingest(self.root, path, kind, origin)

    def raw_of(self, meta):
        return (self.root / ".brain-data" / "sources" / meta["id"] / "raw.txt").read_bytes()


class OnlyMarkedSourcesAreUsed(DatasetHarness):
    def test_an_unmarked_source_is_refused_and_nothing_is_written(self):
        dataset.mark_shareable(self.root, self.first["id"], approved=True)
        out = self.root / "out"
        with self.assertRaises(ValueError) as caught:
            dataset.build(self.root, out)
        self.assertIn(self.second["id"], str(caught.exception))
        self.assertIn("shareable", str(caught.exception))
        self.assertFalse(out.exists(), "a refused build writes no folder")

    def test_marking_is_a_decision_and_previews_without_it(self):
        preview = dataset.mark_shareable(self.root, self.first["id"])
        self.assertFalse(preview["approved"])
        self.assertEqual({}, dataset.read_shares(self.root),
                         "a preview must not decide anything")
        done = dataset.mark_shareable(self.root, self.first["id"], approved=True)
        self.assertTrue(done["approved"])
        self.assertIn(self.first["id"], dataset.read_shares(self.root))

    def test_marking_a_source_that_does_not_exist_is_refused(self):
        with self.assertRaises(ValueError):
            dataset.mark_shareable(self.root, "no-such-source", approved=True)


class EveryExampleCitesAByteRange(DatasetHarness):
    def build(self):
        for meta in (self.first, self.second):
            dataset.mark_shareable(self.root, meta["id"], approved=True)
        return dataset.build(self.root, self.root / "out", limit=40)

    def test_the_range_slices_the_raw_bytes_to_the_example_text(self):
        manifest = self.build()
        rows = [json.loads(line) for line in
                (self.root / "out" / "examples.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(manifest["counts"]["examples"], len(rows))
        raws = {self.first["id"]: self.raw_of(self.first),
                self.second["id"]: self.raw_of(self.second)}
        for row in rows:
            raw = raws[row["source_id"]]
            self.assertEqual(row["text"].encode("utf-8"), raw[row["start"]:row["end"]],
                             "%s does not reproduce its own range" % row["id"])

    def test_the_manifest_records_ids_counts_and_a_digest(self):
        manifest = self.build()
        self.assertEqual({self.first["id"], self.second["id"]},
                         {entry["id"] for entry in manifest["sources"]})
        self.assertEqual(64, len(manifest["digest"]))
        self.assertEqual(manifest["digest"],
                         dataset.verify(self.root / "out")["digest"])
        self.assertTrue(dataset.verify(self.root / "out")["ok"])

    def test_two_builds_of_the_same_records_agree(self):
        self.build()
        second = dataset.build(self.root, self.root / "again", limit=40)
        first = json.loads((self.root / "out" / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(first["digest"], second["digest"],
                         "the digest must describe the examples, not the clock")

    def test_a_tampered_dataset_fails_verification(self):
        self.build()
        path = self.root / "out" / "examples.jsonl"
        path.write_text(path.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
        result = dataset.verify(self.root / "out")
        self.assertFalse(result["ok"])
        self.assertTrue(result["problems"])

    def test_an_existing_output_folder_is_not_overwritten(self):
        self.build()
        with self.assertRaises(ValueError):
            dataset.build(self.root, self.root / "out", limit=40)


if __name__ == "__main__":
    unittest.main()
